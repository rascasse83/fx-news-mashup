import os
import re
import requests
from bs4 import BeautifulSoup
import time
import random
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def sanitize_filename(title):
    """
    Convert article title to a valid filename
    """
    if not title or title.strip() == "" or title.lower() == "yahoo finance":
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"article_{timestamp}"

    sanitized = re.sub(r'[^\w\s-]', '_', title)
    sanitized = re.sub(r'\s+', '_', sanitized)
    sanitized = sanitized.strip('_')
    if not sanitized:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"article_{timestamp}"
    return sanitized[:100]

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

        title_element = soup.select_one('h1')
        if title_element:
            title = title_element.get_text().strip()
            logger.info(f"Found title: {title}")
        else:
            title_element = soup.select_one('header h1')
            if title_element:
                title = title_element.get_text().strip()
                logger.info(f"Found title with alternative selector: {title}")
            else:
                title = url.split('/')[-1].replace('-', ' ').replace('.html', '')
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
            "url": url
        }

    except Exception as e:
        logger.error(f"Error downloading article content: {str(e)}")
        return None

def save_article_to_file(symbol, article_data, folder="fx_news/scrapers/news/yahoo"):
    """
    Save article content to a file in the specified folder with a unique filename
    """
    try:
        os.makedirs(folder, exist_ok=True)

        filename = sanitize_filename(article_data["title"])
        symbol = symbol.lower()
        filename = f"{filename}_{symbol}"
        base_filepath = os.path.join(folder, f"{filename}.txt")

        filepath = get_unique_filename(base_filepath)

        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(f"# {article_data['title']}\n\n")
            file.write(f"Source: {article_data['url']}\n\n")
            file.write(article_data['content'])

        logger.info(f"Saved article to {filepath}")
        return filepath

    except Exception as e:
        logger.error(f"Error saving article to file: {str(e)}")
        return None

def download_single_article(symbol, url, folder="fx_news/scrapers/news/yahoo"):
    """
    Download and save a single article from its URL
    """
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

    article_data = download_article_content(url, headers)

    if article_data and article_data['content']:
        filepath = save_article_to_file(symbol, article_data, folder)
        return filepath
    else:
        logger.error(f"Failed to download article content from {url}")
        return None

# For testing
if __name__ == "__main__":
    test_url = "https://finance.yahoo.com/news/trump-pledges-more-support-for-crypto-world-after-authorizing-a-digital-fort-knox-090057978.html"
    result = download_single_article('EUR_USD', test_url, "fx_news/scrapers/news/yahoo_test")
    print(f"Test result: {result}")
