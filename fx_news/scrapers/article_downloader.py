import os
import re
import requests
from bs4 import BeautifulSoup
import time
import random

def sanitize_filename(title):
    """
    Convert article title to a valid filename
    """
    # Replace any non-alphanumeric characters with underscore
    sanitized = re.sub(r'[^\w\s-]', '_', title)
    # Replace multiple spaces with single underscore
    sanitized = re.sub(r'\s+', '_', sanitized)
    # Truncate to reasonable length
    return sanitized[:100]

def download_article_content(url, headers):
    """
    Download the full content of a news article from its URL
    """
    try:
        # Add a random delay to avoid being blocked
        time.sleep(random.uniform(0.5, 1.5))
        
        # Make request
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"Failed to fetch article content: {response.status_code}")
            return None
            
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the article content
        # Yahoo Finance articles usually have their content in div tags with specific classes
        article_content = ""
        
        # Look for the article body - this may need adjustment based on Yahoo's HTML structure
        content_div = soup.select_one('div.caas-body')
        
        if content_div:
            # Extract all paragraphs
            paragraphs = content_div.find_all('p')
            article_content = "\n\n".join([p.get_text().strip() for p in paragraphs])
        
        # If we couldn't find the content using the primary method, try alternatives
        if not article_content:
            # Try another common structure
            paragraphs = soup.select('div.canvas-body p')
            if paragraphs:
                article_content = "\n\n".join([p.get_text().strip() for p in paragraphs])
        
        # Return the title and article content
        title_element = soup.select_one('h1')
        title = title_element.get_text().strip() if title_element else "Unknown Title"
        
        return {
            "title": title,
            "content": article_content
        }
    
    except Exception as e:
        print(f"Error downloading article content: {e}")
        return None

def save_article_to_file(article_data, folder="yahoo"):
    """
    Save article content to a file in the specified folder
    """
    try:
        # Create the folder if it doesn't exist
        os.makedirs(folder, exist_ok=True)
        
        # Create a valid filename from the title
        filename = sanitize_filename(article_data["title"])
        filepath = os.path.join(folder, f"{filename}.txt")
        
        # Save the content to the file
        with open(filepath, 'w', encoding='utf-8') as file:
            # Write the title
            file.write(f"# {article_data['title']}\n\n")
            # Write the content
            file.write(article_data['content'])
        
        print(f"Saved article to {filepath}")
        return filepath
    
    except Exception as e:
        print(f"Error saving article to file: {e}")
        return None

def download_news_articles(news_items, folder="yahoo"):
    """
    Download and save all news articles from a list of news items
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
    
    saved_files = []
    
    for item in news_items:
        if 'url' in item and item['url']:
            print(f"Downloading article: {item['title']}")
            
            # Download the article content
            article_data = download_article_content(item['url'], headers)
            
            if article_data and article_data['content']:
                # Save the article to a file
                filepath = save_article_to_file(article_data, folder)
                if filepath:
                    saved_files.append(filepath)
            else:
                print(f"Could not extract content for article: {item['title']}")
        else:
            print(f"No URL found for article: {item['title']}")
    
    return saved_files

# Example usage:
# from scraper import scrape_yahoo_finance_news
# 
# # Get news items from the scraper
# currency_pairs = [('EUR', 'USD'), ('GBP', 'USD'), ('USD', 'JPY')]
# news_items = scrape_yahoo_finance_news(currency_pairs)
# 
# # Download and save the articles
# saved_files = download_news_articles(news_items, folder="yahoo")