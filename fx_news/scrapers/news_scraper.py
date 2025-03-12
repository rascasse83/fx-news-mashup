import requests
import time
import random
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from textblob import TextBlob
import logging
import os
import glob
from fx_news.scrapers.article_downloader import download_single_article, get_latest_timestamp, update_timestamp_cache, download_article_content
from fx_news.scrapers.robots_txt_parser import RobotsTxtParser
from fx_news.scrapers.analyze_sentiment import analyze_sentiment_with_mistral
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
import backoff
from transformers import BertTokenizer, BertForSequenceClassification
import torch
from typing import List, Dict, Tuple, Set, Any, Optional, Union

# Session tracking sets to avoid re-processing the same content
SESSION_PROCESSED_URLS = set()
SESSION_PROCESSED_TIMESTAMPS = {}

# Tentative backoff not working
timestamp_cache = {}  # Existing cache for individual pairs
latest_timestamp = 0  # New global variable to track latest timestamp across all pairs
last_refresh_time = 0  # Track when we last successfully refreshed
# The configurable back-off threshold (5 minutes = 300 seconds)
REFRESH_BACKOFF_THRESHOLD = 300  # seconds


# Load the FinBERT model and tokenizer - only when needed
# We'll use lazy loading to improve startup time
tokenizer = None
model = None

def load_finbert_model():
    """Lazily load the FinBERT model when needed"""
    global tokenizer, model
    if tokenizer is None or model is None:
        model_name = "yiyanghkust/finbert-tone"
        tokenizer = BertTokenizer.from_pretrained(model_name)
        model = BertForSequenceClassification.from_pretrained(model_name)
        
# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def is_url_processed(url: str) -> bool:
    """Check if a URL has been processed in this session"""
    return url in SESSION_PROCESSED_URLS

def mark_url_processed(url: str) -> None:
    """Mark a URL as processed in this session"""
    SESSION_PROCESSED_URLS.add(url)

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



def analyze_news_sentiment(news_items, folder="fx_news/scrapers/news/yahoo", api_key=None, delay_between_requests=1.0):
    """
    Process sentiment for a list of news items as a background job
    
    Args:
        news_items: List of news items with file_path property
        folder: Folder containing news articles
        api_key: Optional Mistral API key
        delay_between_requests: Delay in seconds between API requests
    """
    logger.info(f"Starting sentiment analysis for {len(news_items)} articles")
    
    for i, news_item in enumerate(news_items):
        try:
            file_path = news_item.get('file_path')
            if not file_path or not os.path.exists(file_path):
                # Try to find the file based on timestamp and symbol
                if 'unix_timestamp' in news_item and 'currency' in news_item:
                    timestamp = news_item['unix_timestamp']
                    currency = news_item['currency'].replace('/', '_').lower()
                    potential_path = os.path.join(folder, f"article_{timestamp}_{currency}.txt")
                    
                    if os.path.exists(potential_path):
                        file_path = potential_path
                        logger.info(f"Found file path based on timestamp and currency: {file_path}")
                    else:
                        # Try with a pattern search
                        pattern = os.path.join(folder, f"article_{timestamp}_*.txt")
                        matching_files = glob.glob(pattern)
                        if matching_files:
                            file_path = matching_files[0]
                            logger.info(f"Found file path based on timestamp pattern: {file_path}")
            
            if not file_path or not os.path.exists(file_path):
                logger.warning(f"File not found for sentiment analysis: {file_path}")
                continue
                
            # Read the file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if the file already has sentiment markers
            has_sentiment_markers = '---\nSENTIMENT:' in content
            
            # Extract title and summary for sentiment analysis
            title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else ""
            
            summary_match = re.search(r'SUMMARY:\s(.*?)(?:\n\n|\Z)', content, re.DOTALL)
            summary = summary_match.group(1).strip() if summary_match else ""
            
            # Prepare text for sentiment analysis
            text_for_sentiment = f"{title} {summary}"
            
            # Analyze sentiment
            logger.info(f"Analyzing sentiment for: {title}")
            sentiment_label, sentiment_score = analyze_sentiment(text_for_sentiment, mode='ensemble', api_key=api_key)
            logger.info(f"Sentiment result: {sentiment_label} ({sentiment_score})")
            
            # Update news item
            news_item['sentiment'] = sentiment_label
            news_item['score'] = sentiment_score
            
            # Update the file, replacing existing sentiment markers if they exist
            if has_sentiment_markers:
                # Replace existing sentiment markers
                new_content = re.sub(
                    r'---\nSENTIMENT:.*?\nSCORE:.*?(?=\n\n|\Z)', 
                    f"---\nSENTIMENT: {sentiment_label}\nSCORE: {sentiment_score}", 
                    content, 
                    flags=re.DOTALL
                )
                
                # Write the updated content
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                logger.info(f"Updated existing sentiment markers in {os.path.basename(file_path)}")
            else:
                # Append new sentiment markers
                with open(file_path, 'a', encoding='utf-8') as f:
                    f.write(f"\n\n---\nSENTIMENT: {sentiment_label}\nSCORE: {sentiment_score}\n")
                
                logger.info(f"Added new sentiment markers to {os.path.basename(file_path)}")
            
            logger.info(f"Sentiment for {os.path.basename(file_path)}: {sentiment_label} ({sentiment_score})")
            
            # Add delay between API requests
            if api_key and i < len(news_items) - 1:
                logger.debug(f"Sleeping for {delay_between_requests}s between API requests")
                time.sleep(delay_between_requests)
                
        except Exception as e:
            logger.error(f"Error analyzing sentiment for {news_item.get('title', 'unknown')}: {str(e)}")
            logger.exception(e)  # This logs the full stack trace
    
    logger.info(f"Completed sentiment analysis for {len(news_items)} articles")
    return news_items

def batch_analyze_sentiment(folder="fx_news/scrapers/news/yahoo", max_days_old=30, api_key=None):
    """
    Run a batch job to analyze sentiment for all articles without sentiment
    
    Args:
        folder: Folder containing news articles
        max_days_old: Maximum age of articles to analyze in days
        api_key: Mistral API key
    """
    import glob
    
    # Get all article files
    pattern = os.path.join(folder, "*.txt")
    files = glob.glob(pattern)
    
    # Calculate cutoff date
    cutoff_timestamp = int((datetime.now() - timedelta(days=max_days_old)).timestamp())
    
    # Filter files to those without sentiment
    files_without_sentiment = []
    
    for file_path in files:
        try:
            # Extract timestamp from filename
            filename = os.path.basename(file_path)
            timestamp_match = re.search(r'article_(\d{10})_', filename)
            
            if not timestamp_match:
                continue
                
            file_timestamp = int(timestamp_match.group(1))
            
            # Skip if too old
            if file_timestamp < cutoff_timestamp:
                continue
                
            # Check if file already has sentiment
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if 'SENTIMENT:' in content and 'SCORE:' in content:
                continue
                
            # File needs sentiment analysis
            files_without_sentiment.append(file_path)
            
        except Exception as e:
            logger.error(f"Error checking file {file_path}: {str(e)}")
    
    logger.info(f"Found {len(files_without_sentiment)} files without sentiment data")
    
    # Process files in batches with rate limiting
    for i, file_path in enumerate(files_without_sentiment):
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract title and summary
            title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else ""
            
            summary_match = re.search(r'SUMMARY:\s(.*?)(?:\n\n|\Z)', content, re.DOTALL)
            summary = summary_match.group(1).strip() if summary_match else ""
            
            # Prepare text for sentiment analysis
            text_for_sentiment = f"{title} {summary}"
            
            # Analyze sentiment
            sentiment_label, sentiment_score = analyze_sentiment(text_for_sentiment, mode='ensemble', api_key=api_key)
            
            # Append sentiment to file
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(f"\n\n---\nSENTIMENT: {sentiment_label}\n")
                f.write(f"SCORE: {sentiment_score}\n")
                
            logger.info(f"Added sentiment to {os.path.basename(file_path)}: {sentiment_label} ({sentiment_score})")
            
            # Add delay between API requests
            if api_key and i < len(files_without_sentiment) - 1:
                logger.info(f"Sleeping for 1.0s between API requests ({i+1}/{len(files_without_sentiment)})")
                time.sleep(1.0)
                
        except Exception as e:
            logger.error(f"Error analyzing sentiment for {os.path.basename(file_path)}: {str(e)}")
    
    logger.info(f"Completed sentiment analysis for {len(files_without_sentiment)} files")


def analyze_sentiment_ensemble(text: str, api_key: str = None) -> tuple[str, float]:
    """
    Analyze sentiment using an ensemble of FinBERT and Mistral models
    
    Args:
        text: Text to analyze
        api_key: API key for Mistral
    
    Returns:
        tuple: (sentiment_label, sentiment_score)
    """
    # Get FinBERT sentiment
    finbert_label, finbert_score = analyze_sentiment(text, mode="finbert")
    
    # Convert finbert score to a -1 to 1 scale for easier combination
    # FinBERT gives a confidence score between 0 and 1, we need to scale it
    if finbert_label == "positive":
        finbert_normalized = finbert_score  # Already 0 to 1
    elif finbert_label == "negative":
        finbert_normalized = -finbert_score  # Convert to -1 to 0
    else:  # neutral
        finbert_normalized = 0  # Center neutral at 0
    
    # Only use Mistral if API key is provided
    if api_key:
        try:
            # Get Mistral sentiment
            mistral_label, mistral_score = analyze_sentiment(text, mode="mistral", api_key=api_key)
            
            # Combine scores (weighted average)
            # You can adjust the weights based on which model you find more reliable
            if mistral_score == 0:
                ensemble_score = finbert_normalized  # Use 100% FinBERT when Mistral is 0
            else:
                ensemble_score = (finbert_normalized * 0.2) + (mistral_score * 0.8)
            
            # Log both scores for analysis
            logger.info(f"FinBERT: {finbert_label} ({finbert_normalized:.2f}), " 
                        f"Mistral: {mistral_label} ({mistral_score:.2f}), "
                        f"Ensemble: {ensemble_score:.2f}")
            
        except Exception as e:
            # Fixed error handling - use the error message in the logger call
            error_msg = str(e)
            logger.error(f"Error using Mistral API, falling back to FinBERT: {error_msg}")
            ensemble_score = finbert_normalized
    else:
        # No API key, just use FinBERT
        ensemble_score = finbert_normalized
    
    # Determine final sentiment label based on ensemble score
    if ensemble_score > 0.2:
        final_label = "positive"
    elif ensemble_score < -0.2:
        final_label = "negative"
    else:
        final_label = "neutral"
    
    return final_label, round(ensemble_score, 2)

def analyze_sentiment(text: str, mode: str = "textblob", api_key: str = None) -> Tuple[str, float]:
    """
    Analyze sentiment using various methods
    
    Args:
        text: Text to analyze
        mode: "finbert", "textblob", "mistral", or "ensemble"
        api_key: API key for Mistral (required for mistral and ensemble modes)
    
    Returns:
        tuple: (sentiment_label, sentiment_score)
    """
    if mode == "ensemble":
        return analyze_sentiment_ensemble(text, api_key)
    
    elif mode == "finbert":
        # Load model if needed
        load_finbert_model()
        
        # Tokenize the input text
        inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)

        # Perform inference
        with torch.no_grad():
            outputs = model(**inputs)

        # Get the predicted sentiment score
        logits = outputs.logits
        predicted_class = torch.argmax(logits, dim=1).item()
        
        # Get the raw score (confidence)
        score = torch.softmax(logits, dim=1)[0][predicted_class].item()

        # Map the predicted class to a sentiment label
        sentiment_label = {
            0: "negative",
            1: "neutral",
            2: "positive"
        }[predicted_class]

        return sentiment_label, round(score, 2)
    
    elif mode == "mistral":
        if not api_key:
            logger.warning("No API key provided for Mistral, falling back to TextBlob")
            return analyze_sentiment(text, "textblob")
        
        return analyze_sentiment_with_mistral(text, api_key)
    
    # Analyze sentiment using TextBlob
    else:            
        analysis = TextBlob(text)
        sentiment_score = round(analysis.sentiment.polarity, 2)  # -1 to 1
        
        if sentiment_score > 0.2:
            sentiment_label = "positive"
        elif sentiment_score < -0.2:
            sentiment_label = "negative"
        else:
            sentiment_label = "neutral"
                        
        return sentiment_label, sentiment_score

def format_currency_pair_for_yahoo(base: str, quote: str) -> str:
    """
    Format currency pair for Yahoo Finance URL
    
    Args:
        base: Base currency code (e.g., 'EUR', 'BTC')
        quote: Quote currency code (e.g., 'USD', 'JPY')
        
    Returns:
        Formatted symbol for Yahoo Finance
    """
    base = base.upper()
    quote = quote.upper()
    
    # Handle cryptocurrencies (BTC-USD, ETH-USD, etc.)
    crypto_currencies = ['BTC', 'ETH', 'XRP', 'LTC', 'BCH', 'ADA', 'DOT', 'LINK', 'XLM', 'DOGE', 'SOL']
    
    if base in crypto_currencies and quote == 'USD':
        return f"{base}-{quote}"
    elif base == 'USD':
        return f"{quote}%3DX"
    else:
        return f"{base}{quote}%3DX"

def load_news_from_files(symbol: str, folder: str = "fx_news/scrapers/news/yahoo", max_days_old: int = 7) -> List[Dict[str, Any]]:
    """
    Load previously saved news articles from filesystem
    
    Args:
        symbol: Currency pair symbol (e.g., "BTC_USD")
        folder: Folder where articles are stored
        max_days_old: Maximum age of articles to load in days
    
    Returns:
        List of news items loaded from files
    """
    import glob
    
    symbol = symbol.lower()
    loaded_news = []
    
    # Get files for this symbol
    pattern = os.path.join(folder, f"*_{symbol}.txt")
    files = glob.glob(pattern)
    
    # Sort by timestamp (newest first)
    files.sort(reverse=True)
    
    # Calculate cutoff date
    cutoff_timestamp = int((datetime.now() - timedelta(days=max_days_old)).timestamp())
    
    logger.info(f"Looking for cached news for {symbol}, found {len(files)} files")
    
    for file_path in files:
        try:
            # Extract timestamp from filename
            filename = os.path.basename(file_path)
            timestamp_match = re.search(r'article_(\d{10})_', filename)
            
            if not timestamp_match:
                logger.debug(f"No timestamp found in filename: {filename}")
                continue
                
            file_timestamp = int(timestamp_match.group(1))
            
            # Skip if too old
            if file_timestamp < cutoff_timestamp:
                logger.debug(f"Skipping old article: {filename} ({datetime.fromtimestamp(file_timestamp).isoformat()})")
                continue
                
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract title from first line ("# Title")
            title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()
            else:
                # Fallback to filename
                title = os.path.basename(file_path).replace('_', ' ').replace('.txt', '')
                logger.warning(f"No title found in file, using filename: {title}")
            
            # Extract source URL
            source_match = re.search(r'^Source: (.+)$', content, re.MULTILINE)
            url = source_match.group(1).strip() if source_match else ""
            
            # Extract source name from URL or use default
            source = "Yahoo Finance"  # Default source
            if "bloomberg" in url.lower():
                source = "Bloomberg"
            elif "reuters" in url.lower():
                source = "Reuters"
            elif "cnbc" in url.lower():
                source = "CNBC"
            elif "ft.com" in url.lower() or "financial-times" in url.lower():
                source = "Financial Times"
            elif "wsj.com" in url.lower():
                source = "Wall Street Journal"
            elif "nytimes" in url.lower():
                source = "New York Times"
                
            # Convert timestamp to datetime
            timestamp = datetime.fromtimestamp(file_timestamp)
            
            # Extract summary from content (look for SUMMARY label first)
            summary = ""
            summary_match = re.search(r'SUMMARY:\s(.*?)(?:\n\n|\Z)', content, re.DOTALL)
            if summary_match:
                summary = summary_match.group(1).strip()
            else:
                # Fall back to using content after metadata sections
                content_parts = content.split('\n\n')
                # Skip title and metadata sections (usually first 3-4 parts)
                for part in content_parts[3:6]:
                    if part and len(part.strip()) > 10:  # Skip empty or very short parts
                        summary += part.strip() + " "
            
            # If summary is still empty, use first paragraph of content
            if not summary:
                content_parts = content.split('\n\n')
                for part in content_parts[3:]:  # Skip metadata
                    if part and len(part.strip()) > 10:
                        summary = part.strip()
                        break
            
            # Get currency pair from symbol
            symbol_parts = symbol.split('_')
            if len(symbol_parts) == 2:
                currency = f"{symbol_parts[0].upper()}/{symbol_parts[1].upper()}"
            else:
                currency = symbol.upper()
            
            # Extract sentiment and score from the file if available
            sentiment_label = "neutral"  # Default sentiment
            sentiment_score = 0.0  # Default score
            
            # Look for sentiment data at the end of the file
            sentiment_match = re.search(r'SENTIMENT:\s(.*?)$', content, re.MULTILINE)
            if sentiment_match:
                sentiment_label = sentiment_match.group(1).strip()
                logger.debug(f"Found saved sentiment in file: {sentiment_label}")
            
            score_match = re.search(r'SCORE:\s([-\d\.]+)$', content, re.MULTILINE)
            if score_match:
                try:
                    sentiment_score = float(score_match.group(1).strip())
                    logger.debug(f"Found saved sentiment score in file: {sentiment_score}")
                except ValueError:
                    logger.warning(f"Could not parse sentiment score from file: {score_match.group(1)}")
            
            # Create news item
            news_item = {
                "title": title,
                "timestamp": timestamp,
                "unix_timestamp": file_timestamp,
                "currency": currency,
                "source": source,
                "url": url,
                "summary": summary,
                "related_tickers": [],
                "file_path": file_path,  # Add this line to store the file path
                "sentiment": sentiment_label,
                "score": sentiment_score
            }
            
            # Only recalculate sentiment if not found in the file
            if not sentiment_match or not score_match:
                logger.info(f"No saved sentiment found for {filename}, calculating now")
                # Calculate sentiment using title and summary
                text_for_sentiment = title + " " + summary
                try:
                    # First try with FinBERT for faster processing
                    sentiment_label, sentiment_score = analyze_sentiment(text_for_sentiment, 'finbert')
                    
                    # Then with the ensemble if API key is available
                    if 'api_key' in globals() and api_key:
                        sentiment_label, sentiment_score = analyze_sentiment(
                            text_for_sentiment, 
                            mode='ensemble', 
                            api_key='1i1PR8oSJwazWAyOj3iXiRoiCThZI6qj'
                        )
                    
                    # Update the news item
                    news_item["sentiment"] = sentiment_label
                    news_item["score"] = sentiment_score
                    
                    # Optionally, update the file with the calculated sentiment
                    try:
                        with open(file_path, 'a', encoding='utf-8') as f:
                            f.write(f"\n\n---\nSENTIMENT: {sentiment_label}\n")
                            f.write(f"SCORE: {sentiment_score}\n")
                        logger.info(f"Updated file {filename} with calculated sentiment")
                    except Exception as e:
                        logger.warning(f"Could not update file with sentiment: {str(e)}")
                        
                except Exception as e:
                    logger.error(f"Error calculating sentiment: {str(e)}")
            
            loaded_news.append(news_item)
            logger.info(f"Loaded news item from {file_path}: {title} ({timestamp.isoformat()}) - {sentiment_label} ({sentiment_score})")
            
        except Exception as e:
            logger.error(f"Error loading news from file {file_path}: {str(e)}")
            continue
    
    logger.info(f"Loaded {len(loaded_news)} news items for {symbol}")
    return loaded_news

@backoff.on_exception(
    backoff.expo,
    (requests.exceptions.RequestException, requests.exceptions.Timeout),
    max_tries=3,
    max_time=30
)
def make_request(url: str, headers: Dict[str, str], timeout: int = 10) -> requests.Response:
    """Make HTTP request with retry logic"""
    return requests.get(url, headers=headers, timeout=timeout)

def process_news_item(
    item: Any, 
    symbol: str, 
    base: str, 
    quote: str, 
    latest_timestamp: int, 
    headers: Dict[str, str],
    news_folder: str,
    debug_log: List[str]
) -> Optional[Dict[str, Any]]:
    """Process a single news item from Yahoo Finance"""
    try:
        # Extract title
        title_element = item.select_one('h3.clamp')
        if not title_element:
            return None
        title = title_element.text.strip()
        
        # Extract link
        link_element = item.select_one('a.subtle-link[data-ylk*="elm:hdln"]')
        link = link_element['href'] if link_element and 'href' in link_element.attrs else ''
        if link and not link.startswith('http'):
            link = f"https://uk.finance.yahoo.com{link}"
        
        # Skip if we've already processed this URL in the current session
        if is_url_processed(link):
            logger.info(f"Skipping already processed URL in this session: {link}")
            debug_log.append(f"Skipping duplicate within session: {link}")
            return None
        
        # Extract timestamp from URL if possible
        url_timestamp = None
        url_timestamp_match = re.search(r'/(\d{10})(?:\.|$)', link)
        if url_timestamp_match:
            url_timestamp = int(url_timestamp_match.group(1))
            
            # Skip if this timestamp is already processed in this session
            if is_timestamp_processed(symbol, url_timestamp):
                logger.info(f"Skipping already processed timestamp in this session: {url_timestamp}")
                debug_log.append(f"Skipping duplicate timestamp in session: {url_timestamp}")
                return None
            
            # Skip if this timestamp is older than or equal to our latest known timestamp
            if latest_timestamp > 0 and url_timestamp <= latest_timestamp:
                logger.info(f"Skipping article as timestamp is older than latest: {url_timestamp} <= {latest_timestamp}")
                debug_log.append(f"Skipping old article: {url_timestamp} <= {latest_timestamp}")
                return None
            
            # Mark this timestamp as being processed
            mark_timestamp_processed(symbol, url_timestamp)
        
        # Mark this URL as being processed
        mark_url_processed(link)
        
        # Extract timestamp from the article list view if possible
        article_timestamp = 0
        if url_timestamp:
            article_timestamp = url_timestamp
        else:
            time_element = item.select_one('time[datetime]')
            if time_element and time_element.has_attr('datetime'):
                try:
                    timestamp_str = time_element['datetime']
                    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    article_timestamp = int(dt.timestamp())
                    
                    # Skip if this timestamp is already processed in this session
                    if is_timestamp_processed(symbol, article_timestamp):
                        logger.info(f"Skipping already processed timestamp in this session: {article_timestamp}")
                        debug_log.append(f"Skipping duplicate timestamp in session: {article_timestamp}")
                        return None
                    
                    # Skip if this timestamp is older than our latest
                    if latest_timestamp > 0 and article_timestamp <= latest_timestamp:
                        logger.info(f"Skipping article as timestamp is older than latest: {article_timestamp} <= {latest_timestamp}")
                        debug_log.append(f"Skipping old article: {article_timestamp} <= {latest_timestamp}")
                        return None
                    
                    # Mark this timestamp as being processed
                    mark_timestamp_processed(symbol, article_timestamp)
                    
                    logger.info(f"Found article timestamp in list: {article_timestamp} for {title}")
                except Exception as e:
                    logger.error(f"Error parsing timestamp from list: {str(e)}")
        
        # Extract source and timestamp from publishing info if not already extracted
        publishing_element = item.select_one('div.publishing')
        source = "Yahoo Finance"
        timestamp = datetime.now()
        
        if publishing_element:
            source_text = publishing_element.text.strip()
            parts = source_text.split('•')
            
            if len(parts) >= 1:
                source = parts[0].strip()
            
            # Parse relative time if we don't have the timestamp yet
            if article_timestamp == 0 and len(parts) >= 2:
                time_text = parts[1].strip().lower()
                
                # Parse relative time
                if 'yesterday' in time_text:
                    timestamp = datetime.now() - timedelta(days=1)
                elif 'days ago' in time_text:
                    days = 1  # Default
                    try:
                        days_match = re.search(r'(\d+)\s+days ago', time_text)
                        if days_match:
                            days = int(days_match.group(1))
                    except:
                        pass
                    timestamp = datetime.now() - timedelta(days=days)
                elif 'hours ago' in time_text:
                    hours = 1  # Default
                    try:
                        hours_match = re.search(r'(\d+)\s+hours ago', time_text)
                        if hours_match:
                            hours = int(hours_match.group(1))
                    except:
                        pass
                    timestamp = datetime.now() - timedelta(hours=hours)
                elif 'minutes ago' in time_text:
                    minutes = 5  # Default
                    try:
                        minutes_match = re.search(r'(\d+)\s+minutes ago', time_text)
                        if minutes_match:
                            minutes = int(minutes_match.group(1))
                    except:
                        pass
                    timestamp = datetime.now() - timedelta(minutes=minutes)
                elif 'last month' in time_text:
                    timestamp = datetime.now() - timedelta(days=30)
                elif 'months ago' in time_text:
                    months = 1  # Default
                    try:
                        months_match = re.search(r'(\d+)\s+months ago', time_text)
                        if months_match:
                            months = int(months_match.group(1))
                    except:
                        pass
                    timestamp = datetime.now() - timedelta(days=30*months)
                
                if article_timestamp == 0:
                    article_timestamp = int(timestamp.timestamp())
                    
                    # Skip if this timestamp is older than our latest
                    if latest_timestamp > 0 and article_timestamp <= latest_timestamp:
                        logger.info(f"Skipping article as timestamp is older than latest: {article_timestamp} <= {latest_timestamp}")
                        debug_log.append(f"Skipping old article: {article_timestamp} <= {latest_timestamp}")
                        return None
        
        # Download the article without sentiment analysis
        logger.info(f"Downloading article: {title} -> {link}")
        article_file = download_single_article(symbol, link, folder=news_folder)

        # Process the downloaded article
        if not article_file:
            logger.warning(f"Failed to download article or article already exists: {title}")
            debug_log.append(f"Failed to download or duplicate: {title}")
            return None
            
        logger.info(f"Downloaded article: {title} -> {article_file}")
        debug_log.append(f"Downloaded article: {title} -> {article_file}")
        
        # Find ticker tags for the news item
        tickers = []
        ticker_elements = item.select('a.ticker')
        for ticker_elem in ticker_elements:
            ticker_symbol = ticker_elem.select_one('span.symbol')
            if ticker_symbol:
                tickers.append(ticker_symbol.text.strip())
        
        # Create news item
        news_item = {
            "title": title,
            "timestamp": timestamp,
            "unix_timestamp": article_timestamp,
            "currency": f"{base}/{quote}",
            "source": source,
            "url": link,
            "related_tickers": tickers,
            "file_path": article_file  # Store file path for later sentiment analysis
        }
        
        return news_item
    
    except Exception as e:
        logger.error(f"Error processing news item: {str(e)}")
        debug_log.append(f"Error processing news item: {str(e)}")
        return None

def scrape_yahoo_finance_news(
    currency_pairs: List[Tuple[str, str]], 
    max_articles: int = 5, 
    include_cached: bool = True, 
    max_cached_days: int = 7, 
    debug_log: Optional[List[str]] = None, 
    news_folder: str = "fx_news/scrapers/news/yahoo", 
    respect_robots_txt: bool = True,
    max_workers: int = 4,
    request_timeout: int = 10,
    analyze_sentiment_now: bool = False,
    sentiment_api_key: Optional[str] = None,
    force_refresh=False
) -> List[Dict[str, Any]]:
    """
    Scrape news from Yahoo Finance for specified currency pairs, using timestamp tracking to avoid duplicates.
    
    Args:
        currency_pairs: List of tuples containing (base, quote) currency pairs
        max_articles: Maximum number of articles to fetch per currency pair
        include_cached: Whether to include cached articles from filesystem
        max_cached_days: Maximum age in days for cached articles
        debug_log: List to append debug info to
        news_folder: Folder to save downloaded articles
        respect_robots_txt: Whether to check and respect robots.txt rules
        max_workers: Maximum number of concurrent download workers
        request_timeout: Timeout for HTTP requests in seconds
        analyze_sentiment_now: Whether to analyze sentiment after downloading articles
        sentiment_api_key: API key for sentiment analysis
    """

    global global_latest_timestamp, last_refresh_time
    
    current_time = int(time.time())
    
    # Check if we need to back off (unless force_refresh is True)
    if not force_refresh:
        time_since_last_refresh = current_time - last_refresh_time
        if time_since_last_refresh < REFRESH_BACKOFF_THRESHOLD:
            print(f"Backing off. Only {time_since_last_refresh} seconds since last refresh (threshold: {REFRESH_BACKOFF_THRESHOLD})")
            return None

    # Create a robots.txt parser if we're respecting robots.txt
    robot_parser = None
    if respect_robots_txt:
        from fx_news.scrapers.robots_txt_parser import RobotsTxtParser
        robot_parser = RobotsTxtParser(user_agent="PythonFinanceScraper/1.0")
        
        # Check if we're allowed to scrape Yahoo Finance
        yahoo_base_url = "https://finance.yahoo.com"
        if not robot_parser.is_path_allowed(yahoo_base_url):
            logger.error("Scraping Yahoo Finance is disallowed by robots.txt")
            if debug_log is not None:
                debug_log.append("Scraping Yahoo Finance is disallowed by robots.txt")
            return []
        
        # Get crawl delay if specified
        crawl_delay = robot_parser.get_crawl_delay(yahoo_base_url)
        if crawl_delay:
            logger.info(f"Using crawl delay of {crawl_delay} seconds from robots.txt")
            if debug_log is not None:
                debug_log.append(f"Using crawl delay of {crawl_delay} seconds from robots.txt")
        else:
            crawl_delay = random.uniform(0.5, 1.5)  # Default delay
    
    all_news = []
   
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
    
    if debug_log is None:
        debug_log = []
    
    # Ensure the news folder exists
    os.makedirs(news_folder, exist_ok=True)
    
    # Process each currency pair
    for base, quote in currency_pairs:
        try:
            # Format currency pair for Yahoo Finance URL
            yahoo_symbol = format_currency_pair_for_yahoo(base, quote)
            symbol = f"{base}_{quote}"
            
            # Get the latest timestamp for this currency pair
            latest_timestamp = get_latest_timestamp(news_folder, symbol)
            if latest_timestamp > 0:
                symbol_lower = symbol.lower()
                if symbol_lower not in SESSION_PROCESSED_TIMESTAMPS:
                    SESSION_PROCESSED_TIMESTAMPS[symbol_lower] = set()
                SESSION_PROCESSED_TIMESTAMPS[symbol_lower].add(latest_timestamp)
            latest_date = datetime.fromtimestamp(latest_timestamp) if latest_timestamp > 0 else None
            
            logger.info(f"Scraping {base}/{quote} with latest timestamp: {latest_timestamp} ({latest_date})")
            debug_log.append(f"Scraping {base}/{quote} with latest timestamp: {latest_timestamp} ({latest_date})")
            
            url = f"https://finance.yahoo.com/quote/{yahoo_symbol}/news?{random.random()}"

            # Check if this URL is allowed by robots.txt
            if respect_robots_txt and robot_parser and not robot_parser.is_path_allowed(url):
                logger.warning(f"URL {url} is disallowed by robots.txt, skipping")
                if debug_log is not None:
                    debug_log.append(f"URL {url} is disallowed by robots.txt, skipping")
                continue
                        
            logger.info(f"Fetching news for {base}/{quote} from URL: {url}")
            debug_log.append(f"Fetching news for {base}/{quote} from URL: {url}")
            
            # Add a random delay to avoid being blocked
            time.sleep(random.uniform(0.5, 1.5))
            
            # Make request with retry logic
            try:
                response = make_request(url, headers, timeout=request_timeout)
                if response.status_code != 200:
                    logger.error(f"Failed to fetch data for {base}/{quote}: {response.status_code}")
                    debug_log.append(f"Failed to fetch data for {base}/{quote}: {response.status_code}")
                    continue
            except Exception as e:
                logger.error(f"Request error for {base}/{quote}: {str(e)}")
                debug_log.append(f"Request error for {base}/{quote}: {str(e)}")
                continue
                
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find news container (based on the HTML structure)
            news_container = soup.select_one('div[data-testid="news-tabs-container"]')
            if not news_container:
                logger.warning(f"News container not found for {base}/{quote}")
                debug_log.append(f"News container not found for {base}/{quote}")
                # Try finding the general news stream
                news_container = soup.select_one('div.news-stream')
                if not news_container:
                    logger.warning(f"Alternate news container not found for {base}/{quote}")
                    debug_log.append(f"Alternate news container not found for {base}/{quote}")
                    continue
            
            # Find all news items in the stream
            news_items = soup.select('li.stream-item.story-item')
            
            if not news_items:
                logger.warning(f"No news found for {base}/{quote}")
                debug_log.append(f"No news found for {base}/{quote}")
                continue
            
            logger.info(f"Found {len(news_items)} news items for {base}/{quote}")
            debug_log.append(f"Found {len(news_items)} news items for {base}/{quote}")
                
            # Process each news item with a thread pool
            pair_news = []
            new_articles_count = 0
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all items for processing
                future_to_item = {
                    executor.submit(
                        process_news_item, 
                        item, 
                        symbol, 
                        base, 
                        quote, 
                        latest_timestamp, 
                        headers,
                        news_folder,
                        debug_log
                    ): item for item in news_items[:max_articles]
                }
                
                # Process results as they complete
                for future in future_to_item:
                    try:
                        news_item = future.result()
                        if news_item:
                            pair_news.append(news_item)
                            new_articles_count += 1
                    except Exception as e:
                        logger.error(f"Error processing news item: {str(e)}")
                        debug_log.append(f"Error processing news item: {str(e)}")
            
            logger.info(f"Downloaded {new_articles_count} new articles for {base}/{quote}")
            debug_log.append(f"Downloaded {new_articles_count} new articles for {base}/{quote}")
            all_news.extend(pair_news)
        except Exception as e:
            logger.error(f"Error processing currency pair {base}/{quote}: {str(e)}")
            if debug_log is not None:
                debug_log.append(f"Error processing currency pair {base}/{quote}: {str(e)}")
    
    # Load cached news if requested
    cached_news = []
    if include_cached:
        for base, quote in currency_pairs:
            try:
                symbol = f"{base}_{quote}"
                symbol_cached_news = load_news_from_files(symbol, folder=news_folder, max_days_old=max_cached_days)
                
                # Filter out duplicates
                for news_item in symbol_cached_news:
                    if not any(n.get("url") == news_item.get("url") for n in all_news) and \
                       not any(n.get("unix_timestamp") == news_item.get("unix_timestamp") for n in all_news):
                        cached_news.append(news_item)
                        logger.info(f"Added cached news item: {news_item.get('title')}")
                        if debug_log is not None:
                            debug_log.append(f"Added cached news item: {news_item.get('title')}")
            except Exception as e:
                logger.error(f"Error loading cached news for {symbol}: {str(e)}")
                if debug_log is not None:
                    debug_log.append(f"Error loading cached news for {symbol}: {str(e)}")
    
    # Add cached news to the result
    all_news.extend(cached_news)
    
    # Sort news by timestamp (newest first)
    all_news.sort(key=lambda x: x.get("timestamp", datetime.now()), reverse=True)
    
    # Analyze sentiment in background if requested
    if analyze_sentiment_now:
        # Find news items without sentiment
        news_items_without_sentiment = [n for n in all_news if 'sentiment' not in n or not n['sentiment']]
        
        if news_items_without_sentiment:
            logger.info(f"Running sentiment analysis for {len(news_items_without_sentiment)} news items")
            # Run sentiment analysis with rate limiting
            analyze_news_sentiment(
                news_items_without_sentiment, 
                api_key=sentiment_api_key, 
                delay_between_requests=1.0  # 1 second delay between requests
            )
    
    # After all the processing is done and timestamp_cache is updated
    # Update the global_latest_timestamp based on all values in timestamp_cache
    if timestamp_cache:
        new_global_latest = max(timestamp_cache.values())
        if new_global_latest > global_latest_timestamp:
            global_latest_timestamp = new_global_latest
            last_refresh_time = current_time
    
    # Return whatever your function was already returning
    return all_news

def create_mock_news(currencies=None):
    """Create mock news data with realistic timestamps."""
    now = datetime.now()
    
    # Mock news data with recent timestamps and summaries
    mock_news = [
        {
            "title": "ECB signals potential rate cuts in coming months",
            "summary": "In the wake of recent economic data, European Central Bank officials have hinted at potential interest rate cuts in the coming months. ECB President Christine Lagarde suggested that inflation pressures are easing, opening the door for monetary policy adjustments.",
            "timestamp": now - timedelta(minutes=45),
            "currency": "EUR/USD",
            "source": "Bloomberg",
            "url": "https://finance.yahoo.com/news/ecb-signals-potential-rate-cuts",
            "related_tickers": ["EURUSD=X", "EUR=X", "USD=X"]
        },
        {
            "title": "UK inflation rises unexpectedly in January",
            "summary": "Recent data shows UK inflation increased unexpectedly in January, challenging the Bank of England's outlook. Consumer prices rose at a higher rate than economist forecasts, potentially delaying interest rate cuts.",
            "timestamp": now - timedelta(hours=2),
            "currency": "GBP/USD",
            "source": "Financial Times",
            "url": "https://finance.yahoo.com/news/uk-inflation-rises-unexpectedly",
            "related_tickers": ["GBPUSD=X", "GBP=X"]
        },
        {
            "title": "Silver demand surges amid industrial applications growth",
            "summary": "Silver prices have been climbing as industrial demand increases, particularly in electronics and renewable energy sectors. Analysts point to growing applications in solar panels and electric vehicles as key drivers.",
            "timestamp": now - timedelta(hours=3),
            "currency": "XAG/USD",
            "source": "Reuters",
            "url": "https://finance.yahoo.com/news/silver-demand-surges",
            "related_tickers": ["SI=F", "XAG=X"]
        },
        {
            "title": "Bank of Japan maintains ultra-low interest rates",
            "summary": "The Bank of Japan has decided to keep its ultra-low interest rates unchanged, despite rising inflation pressures. Governor Kazuo Ueda cited the need for more evidence of sustainable economic growth before policy tightening.",
            "timestamp": now - timedelta(hours=5),
            "currency": "USD/JPY",
            "source": "Nikkei",
            "url": "https://finance.yahoo.com/news/boj-maintains-ultra-low-rates",
            "related_tickers": ["JPY=X", "USDJPY=X"]
        },
        {
            "title": "US Dollar weakens following Federal Reserve comments",
            "summary": "The US Dollar index declined after Federal Reserve officials signaled a patient approach to rate cuts. Chair Jerome Powell emphasized data dependency in future policy decisions, leading to some weakening in dollar strength.",
            "timestamp": now - timedelta(hours=6),
            "currency": "EUR/USD",
            "source": "CNBC",
            "url": "https://finance.yahoo.com/news/us-dollar-weakens-following-fed",
            "related_tickers": ["DX-Y.NYB", "EURUSD=X"]
        },
        {
            "title": "Australian economy shows resilience in quarterly report",
            "summary": "Australia's economy demonstrated unexpected strength in the latest quarterly GDP report, outperforming economist expectations. Strong exports and consumer spending contributed to the positive results.",
            "timestamp": now - timedelta(hours=8),
            "currency": "AUD/USD",
            "source": "ABC News",
            "url": "https://finance.yahoo.com/news/australian-economy-shows-resilience",
            "related_tickers": ["AUDUSD=X", "AUD=X"]
        },
        {
            "title": "Euro strengthens against major currencies after positive economic data",
            "summary": "The Euro gained ground against major currencies following better-than-expected economic indicators from several Eurozone countries. Manufacturing activity showed signs of recovery in Germany and France.",
            "timestamp": now - timedelta(hours=10),
            "currency": "EUR/GBP",
            "source": "Reuters",
            "url": "https://finance.yahoo.com/news/euro-strengthens-after-positive-data",
            "related_tickers": ["EURGBP=X", "EUR=X", "GBP=X"]
        },
        {
            "title": "British Pound volatility expected ahead of Bank of England meeting",
            "summary": "Currency analysts are predicting increased volatility for the British Pound as the Bank of England's monetary policy meeting approaches. Markets are closely watching for signals about the timing of potential rate cuts.",
            "timestamp": now - timedelta(hours=12),
            "currency": "GBP/EUR",
            "source": "Sky News",
            "url": "https://finance.yahoo.com/news/pound-volatility-expected",
            "related_tickers": ["GBPEUR=X", "GBP=X", "EUR=X"]
        }
    ]
    
    # Filter by currencies if specified
    if currencies:
        currencies = [c.upper() for c in currencies]
        filtered_news = []
        for news in mock_news:
            pair_currencies = news["currency"].split('/')
            if any(c in currencies for c in pair_currencies):
                filtered_news.append(news)
        mock_news = filtered_news
    
    # Add sentiment analysis using TextBlob
    for news in mock_news:
        # Analyze title for sentiment
        analysis = TextBlob(news["title"] + " " + news["summary"])
        news["score"] = round(analysis.sentiment.polarity, 2)  # -1 to 1
        
        if news["score"] > 0.2:
            news["sentiment"] = "positive"
        elif news["score"] < -0.2:
            news["sentiment"] = "negative"
        else:
            news["sentiment"] = "neutral"
    
    return mock_news

# Example usage
if __name__ == "__main__":
    currency_pairs = [("EUR", "USD"), ("GBP", "USD"), ("USD", "JPY")]
    news = scrape_yahoo_finance_news(currency_pairs, max_articles=10)
    print(f"Total news articles: {len(news)}")
    for article in news[:5]:
        print(f"{article['timestamp']} - {article['title']} ({article['sentiment']})")

    sample_text = "The economy is showing signs of recovery with increased consumer spending and positive job growth."
    sentiment_label, sentiment_score = analyze_sentiment(sample_text, mode='finbert')
    print(f"Sentiment Label: {sentiment_label}, Sentiment Score: {sentiment_score}")