import os
import re
import requests
from bs4 import BeautifulSoup
import time
import random
import logging
from datetime import datetime
import glob

# Set up logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SESSION_PROCESSED_URLS = set()
SESSION_PROCESSED_TIMESTAMPS = {}

def debug_article_processing(url, symbol, folder):
    """Debug function to diagnose why duplicate detection is failing"""
    try:
        # Get latest timestamp from cache
        latest_timestamp = get_latest_timestamp(folder, symbol)
        
        # Extract timestamp from URL
        url_timestamp_match = re.search(r'[/-](\d{10})(?:[/-]|\.|\?|$)', url)
        url_timestamp = int(url_timestamp_match.group(1)) if url_timestamp_match else 0
        
        # Check session timestamps
        symbol_lower = symbol.lower()
        in_session = symbol_lower in SESSION_PROCESSED_TIMESTAMPS
        session_timestamps = SESSION_PROCESSED_TIMESTAMPS.get(symbol_lower, set())
        
        # Check for existing files with this timestamp
        exact_file = None
        if url_timestamp > 0:
            exact_file = os.path.join(folder, f"article_{url_timestamp}_{symbol_lower}.txt")
            file_exists = os.path.exists(exact_file)
        else:
            file_exists = False
            
        # Log all diagnostic information
        logger.info("==== ARTICLE DUPLICATE DETECTION DIAGNOSIS ====")
        logger.info(f"URL: {url}")
        logger.info(f"Symbol: {symbol}")
        logger.info(f"Latest timestamp in cache: {latest_timestamp}")
        logger.info(f"URL timestamp: {url_timestamp}")
        logger.info(f"Symbol in SESSION_PROCESSED_TIMESTAMPS: {in_session}")
        logger.info(f"Timestamps in session for this symbol: {session_timestamps}")
        logger.info(f"Looking for exact file: {exact_file}")
        logger.info(f"Exact file exists: {file_exists}")
        
        # Check timestamp cache file directly
        cache_dir = os.path.join(folder, "timestamp_cache")
        cache_file = os.path.join(cache_dir, f"{symbol_lower}_latest.txt")
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cached_content = f.read().strip()
                logger.info(f"Timestamp cache file content: {cached_content}")
        else:
            logger.info("Timestamp cache file does not exist")
            
        logger.info("=================================================")
        
    except Exception as e:
        logger.error(f"Error in debug function: {str(e)}")

def is_timestamp_processed(symbol: str, timestamp: int) -> bool:
    """Check if a timestamp has been processed for a symbol in this session"""
    symbol = symbol.lower()
    return symbol in SESSION_PROCESSED_TIMESTAMPS and timestamp in SESSION_PROCESSED_TIMESTAMPS[symbol]

def mark_timestamp_processed(symbol: str, timestamp: int) -> None:
    """Mark a timestamp as processed for a symbol in this session"""
    symbol = symbol.lower()
    if symbol not in SESSION_PROCESSED_TIMESTAMPS:
        SESSION_PROCESSED_TIMESTAMPS[symbol] = set()
    SESSION_PROCESSED_TIMESTAMPS[symbol].add(timestamp)
    
    # Also update the timestamp cache file
    update_timestamp_cache(symbol, timestamp, "fx_news/scrapers/news/yahoo")

def extract_unix_timestamp(soup):
    """
    Extract the unix timestamp from the article's HTML
    """
    try:
        # Look for the time tag with datetime attribute
        time_element = soup.select_one('time.byline-attr-meta-time')
        if time_element and time_element.has_attr('data-timestamp'):
            timestamp_str = time_element['data-timestamp']
            # Parse the ISO format timestamp to datetime
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            # Convert to unix timestamp
            unix_timestamp = int(dt.timestamp())
            logger.info(f"Extracted timestamp: {unix_timestamp} from {timestamp_str}")
            return unix_timestamp
        
        # Fallback to other time elements
        time_element = soup.select_one('time[datetime]')
        if time_element and time_element.has_attr('datetime'):
            timestamp_str = time_element['datetime']
            # Parse the ISO format timestamp to datetime
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            # Convert to unix timestamp
            unix_timestamp = int(dt.timestamp())
            logger.info(f"Extracted timestamp from alternate element: {unix_timestamp} from {timestamp_str}")
            return unix_timestamp
        
        # If no timestamp found, use current time
        logger.warning("No timestamp found in article, using current time")
        return int(time.time())
    
    except Exception as e:
        logger.error(f"Error extracting timestamp: {str(e)}")
        return int(time.time())

def sanitize_filename(title, unix_timestamp):
    """
    Convert article title to a valid filename including the unix timestamp
    """
    if not title or title.strip() == "" or title.lower() == "yahoo finance":
        return f"article_{unix_timestamp}"

    sanitized = re.sub(r'[^\w\s-]', '_', title)
    sanitized = re.sub(r'\s+', '_', sanitized)
    sanitized = sanitized.strip('_')
    if not sanitized:
        return f"article_{unix_timestamp}"
    
    # Limit the title length and append timestamp
    return f"{sanitized[:80]}_{unix_timestamp}"

def get_unique_filename(base_filepath):
    """
    Ensure the filename is unique by adding a counter if needed
    """
    if not os.path.exists(base_filepath):
        return base_filepath

    root, ext = os.path.splitext(base_filepath)
    counter = 1
    while os.path.exists(f"{root}_{counter}{ext}"):
        counter += 1

    return f"{root}_{counter}{ext}"

# Changes to get_latest_timestamp in article_downloader.py
def get_latest_timestamp(folder, symbol):
    """
    Get the latest unix timestamp from existing article files for a symbol
    Returns 0 if no files are found
    """
    try:
        symbol = symbol.lower()
        # Create a cache file path for timestamp tracking
        cache_dir = os.path.join(folder, "timestamp_cache")
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"{symbol}_latest.txt")
        
        # Check if cache file exists and is recent (less than 1 hour old)
        if os.path.exists(cache_file):
            file_age = time.time() - os.path.getmtime(cache_file)
            if file_age < 3600:  # 1 hour in seconds
                try:
                    with open(cache_file, 'r') as f:
                        cached_timestamp = int(f.read().strip())
                        logger.info(f"Using cached timestamp for {symbol}: {cached_timestamp}")
                        return cached_timestamp
                except (ValueError, IOError) as e:
                    logger.warning(f"Error reading cached timestamp: {str(e)}")
                    # Continue to recalculate if cache read fails
        
        # Find all files for this symbol
        pattern = os.path.join(folder, f"*_{symbol}.txt")
        files = glob.glob(pattern)
        
        # If no files found with direct pattern, try more flexible pattern
        if not files:
            pattern = os.path.join(folder, f"*{symbol}*.txt")
            files = glob.glob(pattern)
            
        latest_timestamp = 0
        
        for file_path in files:
            try:
                # Extract timestamp from filename
                filename = os.path.basename(file_path)
                
                # Look for article_TIMESTAMP pattern (like article_1741642246_btc_usd.txt)
                # First try the exact pattern for article_TIMESTAMP_symbol
                timestamp_match = re.search(r'article_(\d{10})(?:_|\.)', filename)
                
                if timestamp_match:
                    try:
                        timestamp = int(timestamp_match.group(1))
                        # Validate timestamp is reasonable (after 2020 and before future)
                        if timestamp > 1577836800 and timestamp < int(time.time()) + 86400:
                            latest_timestamp = max(latest_timestamp, timestamp)
                            logger.debug(f"Found timestamp {timestamp} in {filename}")
                    except ValueError:
                        continue
                else:
                    # Fallback to looking for any 10-digit number in the filename that could be a timestamp
                    timestamp_matches = re.findall(r'_(\d{10})_', filename)
                    for match in timestamp_matches:
                        try:
                            timestamp = int(match)
                            # Validate timestamp is reasonable (after 2020 and before future)
                            if timestamp > 1577836800 and timestamp < int(time.time()) + 86400:
                                latest_timestamp = max(latest_timestamp, timestamp)
                                logger.debug(f"Found timestamp {timestamp} in {filename}")
                        except ValueError:
                            continue
                    
            except Exception as e:
                logger.error(f"Error parsing timestamp from {filename}: {str(e)}")
                continue
        
        # If we found a valid timestamp, cache it
        if latest_timestamp > 0:
            try:
                with open(cache_file, 'w') as f:
                    f.write(str(latest_timestamp))
                logger.info(f"Cached latest timestamp for {symbol}: {latest_timestamp}")
            except IOError as e:
                logger.error(f"Error writing timestamp cache: {str(e)}")
        
        logger.info(f"Latest timestamp for {symbol}: {latest_timestamp}")
        return latest_timestamp
    
    except Exception as e:
        logger.error(f"Error getting latest timestamp: {str(e)}")
        return 0

# Add this function to update the timestamp cache when new articles are downloaded
def update_timestamp_cache(symbol, timestamp, folder):
    """
    Update the cached timestamp for a symbol when a new article is downloaded
    """
    try:
        symbol = symbol.lower()
        cache_dir = os.path.join(folder, "timestamp_cache")
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"{symbol}_latest.txt")
        
        # Read current cached timestamp
        current_timestamp = 0
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    current_timestamp = int(f.read().strip())
            except (ValueError, IOError):
                current_timestamp = 0
        
        # Only update if new timestamp is more recent
        if timestamp > current_timestamp:
            with open(cache_file, 'w') as f:
                f.write(str(timestamp))
            logger.info(f"Updated timestamp cache for {symbol}: {timestamp}")
        
    except Exception as e:
        logger.error(f"Error updating timestamp cache: {str(e)}")

def download_article_content(url, headers=None):
    """
    Download the full content of a news article from its URL
    """
    if headers is None:
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
        headers = {
            'User-Agent': random.choice(user_agents),
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }

    try:
        time.sleep(random.uniform(0.5, 1.5))

        if not url.startswith('http'):
            if 'yahoo' in url:
                url = f"https://finance.yahoo.com{url}"
            else:
                logger.error(f"Invalid URL format: {url}")
                return None

        logger.info(f"Downloading article from: {url}")

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            logger.error(f"Failed to fetch article content: HTTP {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract unix timestamp from the article
        unix_timestamp = extract_unix_timestamp(soup)

        # Try multiple sources for the title in order of preference
        title = None
        
        # 1. First try the page title tag (usually most reliable)
        title_tag = soup.find('title')
        if title_tag and title_tag.string:
            raw_title = title_tag.string.strip()
            
            # Clean up title (remove site name, etc.)
            title_parts = raw_title.split(' - ')
            if len(title_parts) > 1:
                # Usually the article title is the first part, site name at the end
                title = title_parts[0].strip()
            else:
                title = raw_title
                
            # Clean up Yahoo Finance specific titles
            if ' | Yahoo Finance' in title:
                title = title.split(' | Yahoo Finance')[0].strip()
                
            logger.info(f"Found title from <title> tag: {title}")
        
        # 2. If title tag isn't useful, try HTML selectors
        if not title or title == "" or "Yahoo" in title or "Finance" in title:
            title_selectors = [
                'h1[data-test="article-header"]',  # Yahoo Finance article header
                'h1.caas-title-wrapper',           # Yahoo caas template
                'h3.clamp',                        # Yahoo headline in listing
                'h1',                              # Generic h1
                'header h1',                       # Header with h1
                '.article-header h1',              # Article header with h1
                '.headline'                        # Generic headline class
            ]
            
            for selector in title_selectors:
                title_element = soup.select_one(selector)
                if title_element:
                    title = title_element.get_text().strip()
                    logger.info(f"Found title using selector '{selector}': {title}")
                    break
        
        # 3. Try meta tags as another alternative
        if not title or title == "" or "Yahoo" in title or "Finance" in title:
            meta_selectors = [
                'meta[property="og:title"]',
                'meta[name="twitter:title"]',
                'meta[name="title"]'
            ]
            
            for selector in meta_selectors:
                meta_title = soup.select_one(selector)
                if meta_title and 'content' in meta_title.attrs:
                    meta_content = meta_title['content'].strip()
                    
                    # Clean up site name from meta title
                    if ' - Yahoo Finance' in meta_content:
                        meta_content = meta_content.split(' - Yahoo Finance')[0].strip()
                    elif ' | Yahoo Finance' in meta_content:
                        meta_content = meta_content.split(' | Yahoo Finance')[0].strip()
                        
                    title = meta_content
                    logger.info(f"Found title in meta tag: {title}")
                    break
        
        # 4. Last resort - use URL
        if not title or title == "" or title.lower() == "yahoo finance":
            url_title = url.split('/')[-1].replace('-', ' ').replace('.html', '')
            # Capitalize words for readability
            title = ' '.join(word.capitalize() for word in url_title.split())
            logger.warning(f"Could not find title element, using URL-based title: {title}")

        article_content = ""
        content_selectors = [
            'div.caas-body',
            'div.canvas-body',
            'article',
            'div.article-body',
            'div[data-component="text-block"]'
        ]

        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                paragraphs = content_div.find_all('p')
                if paragraphs:
                    article_content = "\n\n".join([p.get_text().strip() for p in paragraphs])
                    logger.info(f"Found content using selector: {selector}")
                    break

        if not article_content:
            logger.warning("Could not extract article content with any known selector")
            paragraphs = soup.select('body p')
            if paragraphs:
                article_content = "\n\n".join([p.get_text().strip() for p in paragraphs])
                logger.info("Extracted content using body paragraphs as fallback")

        if not article_content:
            logger.error("Could not extract any article content")
            return None

        return {
            "title": title,
            "content": article_content,
            "url": url,
            "unix_timestamp": unix_timestamp
        }

    except Exception as e:
        logger.error(f"Error downloading article content: {str(e)}")
        return None

def save_article_to_file(symbol, article_data, folder="fx_news/scrapers/news/yahoo"):
    try:
        os.makedirs(folder, exist_ok=True)

        # Include the unix timestamp in the filename
        unix_timestamp = article_data.get("unix_timestamp", int(time.time()))
        symbol = symbol.lower()
        filename = f"article_{unix_timestamp}_{symbol}"
        base_filepath = os.path.join(folder, f"{filename}.txt")

        filepath = get_unique_filename(base_filepath)

        # Make sure we use the actual article title if available
        title = article_data.get("title", "Yahoo Finance")
        if not title or title.strip() == "":
            title = "Yahoo Finance"
            
        # Clean up the title for writing to file
        title = title.replace('\n', ' ').replace('\r', '').strip()

        # Extract a summary from the article content (first 2-3 paragraphs)
        content = article_data['content']
        paragraphs = content.split('\n\n')
        
        # Use the first 2-3 paragraphs as the summary, but limit to reasonable length
        summary_paragraphs = paragraphs[:min(3, len(paragraphs))]
        summary = ' '.join(summary_paragraphs).strip()
        # Limit summary length
        summary = summary[:500] + ('...' if len(summary) > 500 else '')

        # Get sentiment information if available
        sentiment_label = article_data.get("sentiment", "")
        sentiment_score = article_data.get("score", 0.0)

        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(f"# {title}\n\n")
            file.write(f"Source: {article_data['url']}\n")
            file.write(f"Timestamp: {unix_timestamp} ({datetime.fromtimestamp(unix_timestamp).isoformat()})\n\n")
            file.write(f"SUMMARY: {summary}\n\n")  # Clearly labeled summary
            file.write(content)  # Full content follows
            
            # Add sentiment information at the end of the file
            file.write(f"\n\n---\nSENTIMENT: {sentiment_label}\n")
            file.write(f"SCORE: {sentiment_score}\n")

        # Update the timestamp cache with this new article's timestamp
        update_timestamp_cache(symbol, unix_timestamp, folder)
        
        logger.info(f"Saved article to {filepath} with title: {title}")
        return filepath

    except Exception as e:
        logger.error(f"Error saving article to file: {str(e)}")
        return None
    
def is_duplicate_article(title, url, symbol, folder):
    """
    Check if an article is already downloaded by checking for similar titles, URLs, or timestamp
    """
    try:
        # Get the latest timestamp from cache
        latest_timestamp = get_latest_timestamp(folder, symbol)
        logger.info(f"Checking for duplicate against latest timestamp: {latest_timestamp}")
        
        # First, extract any timestamp from the article (either from URL or content)
        article_timestamp = 0
        
        # Check URL for timestamp
        url_timestamp_match = re.search(r'[/-](\d{10})(?:[/-]|\.|\?|$)', url)
        if url_timestamp_match:
            article_timestamp = int(url_timestamp_match.group(1))
            logger.info(f"Found timestamp in URL: {article_timestamp}")
            
            # DIRECT COMPARE TO CACHED TIMESTAMP - Check for exact match
            if latest_timestamp > 0 and article_timestamp == latest_timestamp:
                logger.info(f"DUPLICATE FOUND: Article timestamp {article_timestamp} EXACTLY MATCHES latest known timestamp {latest_timestamp}")
                return True, None
            
            # Also check for older timestamps as before
            if latest_timestamp > 0 and article_timestamp < latest_timestamp:
                logger.info(f"Article timestamp {article_timestamp} is older than latest known timestamp {latest_timestamp}")
                return True, None
        
        # Now check for exact file match with timestamp from URL
        symbol_lower = symbol.lower()
        if article_timestamp > 0:
            exact_file = os.path.join(folder, f"article_{article_timestamp}_{symbol_lower}.txt")
            if os.path.exists(exact_file):
                logger.info(f"DUPLICATE FOUND: Exact file match found: {exact_file}")
                return True, exact_file
        
        # Clean the title for comparison
        clean_title = re.sub(r'[^\w\s]', '', title.lower())
        clean_title = re.sub(r'\s+', '_', clean_title).strip('_')
        symbol = symbol.lower()
        
        # Create patterns to search for
        title_pattern = os.path.join(folder, f"*{clean_title[:30]}*_{symbol}*.txt")
        
        # Extract URL identifier
        url_id = url.split('/')[-1].split('.')[0]
        if url_id and len(url_id) > 5:  # Only use URL if it has a meaningful identifier
            url_pattern = os.path.join(folder, f"*{url_id}*_{symbol}*.txt")
            
            # Check for files matching URL pattern
            url_files = glob.glob(url_pattern)
            if url_files:
                logger.info(f"Found duplicate article by URL: {url}")
                return True, url_files[0]
        
        # Check for files matching title pattern
        title_files = glob.glob(title_pattern)
        if title_files:
            logger.info(f"Found duplicate article by title: {title}")
            return True, title_files[0]
        
        # Check for articles with the same timestamp (regardless of specific format)
        if article_timestamp > 0:
            timestamp_pattern = os.path.join(folder, f"article_{article_timestamp}*_{symbol}*.txt")
            timestamp_files = glob.glob(timestamp_pattern)
            if timestamp_files:
                logger.info(f"Found duplicate article by timestamp in URL: {article_timestamp}")
                return True, timestamp_files[0]
        
        # If no duplicates found
        return False, None
        
    except Exception as e:
        logger.error(f"Error checking for duplicate article: {str(e)}")
        return False, None      
    
# Changes to download_single_article to handle timestamp updates
def download_single_article(symbol, url, folder="fx_news/scrapers/news/yahoo", sentiment_info=None):
    """
    Download and save a single article from its URL with enhanced title extraction
    
    Args:
        symbol: Currency pair symbol (e.g., "BTC_USD")
        url: URL of the article to download
        folder: Folder to save downloaded articles
        sentiment_info: Optional dictionary with 'sentiment' and 'score' keys
    
    Returns:
        Path to the saved file or None if download failed
    """
    # Initialize session tracking from cache if needed
    symbol_lower = symbol.lower()
    if 'SESSION_PROCESSED_TIMESTAMPS' in globals():
        if symbol_lower not in SESSION_PROCESSED_TIMESTAMPS:
            latest_timestamp = get_latest_timestamp(folder, symbol)
            if latest_timestamp > 0:
                SESSION_PROCESSED_TIMESTAMPS[symbol_lower] = {latest_timestamp}
                logger.info(f"Initialized session tracking for {symbol} with timestamp {latest_timestamp}")
    
    # Extract timestamp from URL
    article_timestamp = 0
    url_timestamp_match = re.search(r'[/-](\d{10})(?:[/-]|\.|\?|$)', url)
    if url_timestamp_match:
        article_timestamp = int(url_timestamp_match.group(1))
        
        # Check for files with the same timestamp base (regardless of counter)
        if article_timestamp > 0:
            symbol_lower = symbol.lower()
            base_pattern = os.path.join(folder, f"article_{article_timestamp}_{symbol_lower}*.txt")
            matching_files = glob.glob(base_pattern)
            
            if matching_files:
                logger.info(f"Skipping download: Found {len(matching_files)} existing files with timestamp {article_timestamp}")
                return matching_files[0]  # Return the first matching file
        
        # Also check against the latest timestamp in the cache
        latest_timestamp = get_latest_timestamp(folder, symbol)
        if latest_timestamp > 0:
            if article_timestamp == latest_timestamp:
                logger.info(f"Skipping download: URL timestamp {article_timestamp} exactly matches latest cached timestamp {latest_timestamp}")
                # Try to find an exact file
                exact_file = os.path.join(folder, f"article_{latest_timestamp}_{symbol_lower}.txt")
                if os.path.exists(exact_file):
                    return exact_file
                
                # If not found, try the pattern match again (should be redundant)
                base_pattern = os.path.join(folder, f"article_{latest_timestamp}_{symbol_lower}*.txt")
                matching_files = glob.glob(base_pattern)
                if matching_files:
                    return matching_files[0]
                
                # If still not found, skip the download
                return None
            
            elif article_timestamp < latest_timestamp:
                logger.info(f"Skipping download: URL timestamp {article_timestamp} is older than latest cached timestamp {latest_timestamp}")
                return None
    
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
    ]

    headers = {
        'User-Agent': random.choice(user_agents),
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }

    if not url:
        logger.error("No URL provided")
        return None

    logger.info(f"Starting download for URL: {url}")
    
    # Extract title from URL as fallback
    url_title = url.split('/')[-1].replace('-', ' ').replace('.html', '').strip()
    if url_title and len(url_title) > 10:
        # Clean up URL title for readability
        url_title = ' '.join([word.capitalize() for word in url_title.split()])
        logger.info(f"Extracted title from URL: {url_title}")
    else:
        url_title = None
    
    # First download just the article data to check for duplicates
    article_data = download_article_content(url, headers)
    
    if not article_data:
        logger.error(f"Failed to download article content from {url}")
        return None
    
    # If article has no content, try to at least get the title
    if not article_data.get('content'):
        logger.error(f"No content found in article from {url}")
        return None
    
    # Use URL-based title as fallback if needed
    if not article_data.get('title') or article_data.get('title') == "Yahoo Finance":
        if url_title:
            article_data['title'] = url_title
            logger.info(f"Using URL-based title as fallback: {url_title}")
    
    # Check if this article is already downloaded
    is_duplicate, existing_file = is_duplicate_article(article_data['title'], url, symbol, folder)
    
    if is_duplicate:
        logger.info(f"Skipping duplicate article: {article_data['title']} (already exists at {existing_file})")
        # If we have a file path, return it
        if existing_file:
            return existing_file
        # Otherwise skip
        return None
    
    # Make sure the unix timestamp is set based on the URL if available
    if url_timestamp_match and 'unix_timestamp' not in article_data:
        article_data['unix_timestamp'] = int(url_timestamp_match.group(1))
        logger.info(f"Setting timestamp from URL: {article_data['unix_timestamp']}")
    
    # Extra check: If the article's timestamp matches any existing article files, skip it
    if 'unix_timestamp' in article_data and article_data['unix_timestamp'] > 0:
        article_ts = article_data['unix_timestamp']
        base_pattern = os.path.join(folder, f"article_{article_ts}_{symbol_lower}*.txt")
        matching_files = glob.glob(base_pattern)
        
        if matching_files:
            logger.info(f"Skipping download: Found {len(matching_files)} existing files with same article timestamp {article_ts}")
            return matching_files[0]
    
    # Add sentiment information if provided
    if sentiment_info and isinstance(sentiment_info, dict):
        if 'sentiment' in sentiment_info:
            article_data['sentiment'] = sentiment_info['sentiment']
            logger.info(f"Adding sentiment to article: {sentiment_info['sentiment']}")
        if 'score' in sentiment_info:
            article_data['score'] = sentiment_info['score']
            logger.info(f"Adding sentiment score to article: {sentiment_info['score']}")
    
    # Not a duplicate, save it
    filepath = save_article_to_file(symbol, article_data, folder)
    
    # Verify if title was saved properly
    if filepath and (not article_data.get('title') or article_data.get('title') == "Yahoo Finance"):
        logger.warning(f"Article saved with generic title. URL: {url}")
    
    # Update session tracking with this timestamp if the global variable exists
    if 'unix_timestamp' in article_data and article_data['unix_timestamp'] > 0:
        if 'SESSION_PROCESSED_TIMESTAMPS' in globals() and 'mark_timestamp_processed' in globals():
            try:
                mark_timestamp_processed(symbol, article_data['unix_timestamp'])
            except Exception as e:
                logger.error(f"Error updating session tracking: {str(e)}")
        else:
            # Directly update the timestamp cache file
            update_timestamp_cache(symbol, article_data['unix_timestamp'], folder)
    
    return filepath

# Test function
if __name__ == "__main__":
    test_url = "https://finance.yahoo.com/news/trump-pledges-more-support-for-crypto-world-after-authorizing-a-digital-fort-knox-090057978.html"
    result = download_single_article('EUR_USD', test_url, "fx_news/scrapers/news/yahoo_test")
    print(f"Test result: {result}")

    test_get_filename = get_latest_timestamp ("fx_news/scrapers/news/yahoo","sol_usd")