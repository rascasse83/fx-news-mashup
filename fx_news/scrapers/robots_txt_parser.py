import requests
import logging
import time
import random
from urllib.parse import urlparse, urljoin

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RobotsTxtParser:
    def __init__(self, user_agent="*"):
        """
        Initialize the robots.txt parser with a specific user agent.
        
        Args:
            user_agent: The user agent to check rules for (default: "*" for all bots)
        """
        self.user_agent = user_agent
        self.cache = {}  # Cache robots.txt content to avoid repeated fetches
        self.cache_expiry = {}  # Store when the cache should expire
        self.CACHE_DURATION = 86400  # Cache duration in seconds (24 hours)
    
    def fetch_robots_txt(self, url):
        """
        Fetch the robots.txt file for a given URL's domain.
        
        Args:
            url: The URL to check (will extract the domain)
            
        Returns:
            str: Content of robots.txt or None if not available
        """
        try:
            # Parse the domain from the URL
            parsed_url = urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            robots_url = f"{base_url}/robots.txt"
            
            # Check if we have a cached version that's still valid
            current_time = time.time()
            if robots_url in self.cache and current_time < self.cache_expiry.get(robots_url, 0):
                logger.info(f"Using cached robots.txt for {base_url}")
                return self.cache[robots_url]
            
            # Fetch robots.txt
            logger.info(f"Fetching robots.txt from {robots_url}")
            
            # Add random delay and user agent rotation for politeness
            time.sleep(random.uniform(1.0, 2.0))
            
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            ]
            
            headers = {'User-Agent': random.choice(user_agents)}
            response = requests.get(robots_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                content = response.text
                # Cache the content
                self.cache[robots_url] = content
                self.cache_expiry[robots_url] = current_time + self.CACHE_DURATION
                return content
            else:
                logger.warning(f"Failed to fetch robots.txt: HTTP {response.status_code}")
                # If we get a 404, assume everything is allowed but cache that result
                if response.status_code == 404:
                    self.cache[robots_url] = ""
                    self.cache_expiry[robots_url] = current_time + self.CACHE_DURATION
                return ""
                
        except Exception as e:
            logger.error(f"Error fetching robots.txt: {str(e)}")
            return ""
    
    def is_path_allowed(self, url):
        """
        Check if a specific URL path is allowed according to robots.txt rules.
        
        Args:
            url: The URL to check
            
        Returns:
            bool: True if allowed, False if disallowed
        """
        try:
            # Get the domain and path
            parsed_url = urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            path = parsed_url.path
            
            # Fetch robots.txt content
            robots_content = self.fetch_robots_txt(url)
            if not robots_content:
                # If no robots.txt or empty, assume allowed
                return True
            
            # Parse the rules
            current_agent = None
            disallowed_paths = []
            allowed_paths = []
            
            for line in robots_content.splitlines():
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Parse User-agent lines
                if line.lower().startswith('user-agent:'):
                    agent = line.split(':', 1)[1].strip()
                    if agent == self.user_agent or agent == '*':
                        current_agent = agent
                    else:
                        current_agent = None
                
                # Parse Disallow lines for current agent
                elif current_agent and line.lower().startswith('disallow:'):
                    path_pattern = line.split(':', 1)[1].strip()
                    if path_pattern:
                        disallowed_paths.append(path_pattern)
                
                # Parse Allow lines for current agent
                elif current_agent and line.lower().startswith('allow:'):
                    path_pattern = line.split(':', 1)[1].strip()
                    if path_pattern:
                        allowed_paths.append(path_pattern)
            
            # First check if path matches any Allow directive
            for allow_path in allowed_paths:
                if path.startswith(allow_path):
                    logger.info(f"Path {path} is explicitly allowed by robots.txt")
                    return True
            
            # Then check if path matches any Disallow directive
            for disallow_path in disallowed_paths:
                if path.startswith(disallow_path):
                    logger.warning(f"Path {path} is disallowed by robots.txt")
                    return False
            
            # If no matching rules found, it's allowed
            return True
            
        except Exception as e:
            logger.error(f"Error checking robots.txt rules: {str(e)}")
            # In case of errors, better to be conservative and assume allowed
            return True
    
    def get_crawl_delay(self, url):
        """
        Extract the Crawl-delay directive from robots.txt if present.
        
        Args:
            url: The URL to check
            
        Returns:
            float: The crawl delay in seconds, or None if not specified
        """
        try:
            robots_content = self.fetch_robots_txt(url)
            if not robots_content:
                return None
            
            current_agent = None
            for line in robots_content.splitlines():
                line = line.strip().lower()
                
                if not line or line.startswith('#'):
                    continue
                
                if line.startswith('user-agent:'):
                    agent = line.split(':', 1)[1].strip()
                    if agent == self.user_agent or agent == '*':
                        current_agent = agent
                    else:
                        current_agent = None
                
                elif current_agent and line.startswith('crawl-delay:'):
                    delay = line.split(':', 1)[1].strip()
                    try:
                        return float(delay)
                    except ValueError:
                        logger.warning(f"Invalid crawl delay value: {delay}")
                        return None
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting crawl delay: {str(e)}")
            return None

# Example usage
if __name__ == "__main__":
    robot_parser = RobotsTxtParser("PythonFinanceScraper/1.0")
    
    # Check Yahoo Finance URLs
    base_url = "https://finance.yahoo.com"
    test_urls = [
        f"{base_url}/quote/EURUSD=X/news",
        f"{base_url}/news/category-stock-market-news",
        f"{base_url}/quote/AAPL/key-statistics"
    ]
    
    for url in test_urls:
        allowed = robot_parser.is_path_allowed(url)
        print(f"URL: {url}")
        print(f"Allowed: {allowed}")
        
        delay = robot_parser.get_crawl_delay(url)
        print(f"Crawl delay: {delay if delay is not None else 'Not specified'}")
        print()