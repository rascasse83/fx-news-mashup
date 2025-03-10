import requests
import time
import random
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from textblob import TextBlob
import logging
import os
from fx_news.scrapers.article_downloader import download_single_article, get_latest_timestamp
from fx_news.scrapers.robots_txt_parser import RobotsTxtParser
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
import backoff
from transformers import BertTokenizer, BertForSequenceClassification
import torch
from typing import List, Dict, Tuple, Set, Any, Optional, Union

# Session tracking sets to avoid re-processing the same content
SESSION_PROCESSED_URLS = set()
SESSION_PROCESSED_TIMESTAMPS = {}

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

def analyze_sentiment(text: str, mode: str = "textblob") -> Tuple[str, float]:
    """
    Analyze sentiment using either FinBERT or TextBlob
    
    Args:
        text: Text to analyze
        mode: "finbert" or "textblob"
    
    Returns:
        tuple: (sentiment_label, sentiment_score)
    """
    if mode == "finbert":
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
    pattern = os.path.join(folder, f"article_*_{symbol}.txt")
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
            
            # Extract content as summary (first paragraph after metadata)
            summary = ""
            content_parts = content.split('\n\n')
            
            # Skip title and metadata sections (usually first 3 parts)
            for part in content_parts[3:]:
                if part and len(part.strip()) > 10:  # Skip empty or very short parts
                    summary = part.strip()
                    break
            
            if not summary and len(content_parts) > 3:
                # Fallback to using any non-empty part
                summary = content_parts[3].strip()
            
            # Get currency pair from symbol
            symbol_parts = symbol.split('_')
            if len(symbol_parts) == 2:
                currency = f"{symbol_parts[0].upper()}/{symbol_parts[1].upper()}"
            else:
                currency = symbol.upper()
            
            # Create news item
            news_item = {
                "title": title,
                "timestamp": timestamp,
                "unix_timestamp": file_timestamp,
                "currency": currency,
                "source": source,
                "url": url,
                "summary": summary[:300] + ("..." if len(summary) > 300 else ""),
                "related_tickers": []
            }
            
            # Analyze sentiment for the content
            text_for_sentiment = title + " " + summary
            sentiment_label, sentiment_score = analyze_sentiment(text_for_sentiment, mode='finbert')
            
            # Add sentiment to news item
            news_item["score"] = sentiment_score
            news_item["sentiment"] = sentiment_label
            
            loaded_news.append(news_item)
            logger.info(f"Loaded news item from {file_path}: {title} ({timestamp.isoformat()})")
            
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
        
        # Download the article
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
            "related_tickers": tickers
        }
        
        # Extract summary if available
        summary_element = item.select_one('p.clamp')
        if summary_element:
            news_item["summary"] = summary_element.text.strip()
        
        # Analyze sentiment 
        if article_file:
            try:
                # Read the full article content from the downloaded file
                with open(article_file, 'r', encoding='utf-8') as f:
                    full_content = f.read()
                    
                # Use the full content for sentiment analysis
                text_for_sentiment = full_content
            except Exception as e:
                logger.error(f"Error reading article file for sentiment analysis: {str(e)}")
                # Fall back to title and summary if file reading fails
                text_for_sentiment = title
                if "summary" in news_item:
                    text_for_sentiment += " " + news_item["summary"]
        else:
            # Fall back to title and summary if article file doesn't exist
            text_for_sentiment = title
            if "summary" in news_item:
                text_for_sentiment += " " + news_item["summary"]

        # Get the sentiment label and score
        sentiment_label, sentiment_score = analyze_sentiment(text_for_sentiment, mode='finbert')

        # Add sentiment to news item
        news_item["score"] = sentiment_score
        news_item["sentiment"] = sentiment_label

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
    request_timeout: int = 10
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
    """
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
            from fx_news.scrapers.article_downloader import get_latest_timestamp
            latest_timestamp = get_latest_timestamp(news_folder, symbol)
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
            # Add cached news if requested
            if include_cached:
                try:
                    cached_news = load_news_from_files(symbol, folder=news_folder, max_days_old=max_cached_days)
                    
                    # Filter out duplicates (by URL or timestamp)
                    for news_item in cached_news:
                        if not any(n.get("url") == news_item.get("url") for n in all_news) and \
                           not any(n.get("unix_timestamp") == news_item.get("unix_timestamp") for n in all_news):
                            all_news.append(news_item)
                            logger.info(f"Added cached news item: {news_item.get('title')}")
                            if debug_log is not None:
                                debug_log.append(f"Added cached news item: {news_item.get('title')}")
                except Exception as e:
                    logger.error(f"Error loading cached news for {symbol}: {str(e)}")
                    if debug_log is not None:
                        debug_log.append(f"Error loading cached news for {symbol}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error processing currency pair {base}/{quote}: {str(e)}")
            if debug_log is not None:
                debug_log.append(f"Error processing currency pair {base}/{quote}: {str(e)}")
    
    # Sort news by timestamp (newest first)
    all_news.sort(key=lambda x: x.get("timestamp", datetime.now()), reverse=True)
    
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