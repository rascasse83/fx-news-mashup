# scraper.py
import requests
import time
import random
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from textblob import TextBlob
import logging

def format_currency_pair_for_yahoo(base, quote):
    """
    Format currency pair for Yahoo Finance URL
    
    Examples:
    - EUR/USD -> EURUSD=X
    - USD/JPY -> JPY=X (when base is USD, only quote currency is used)
    
    Args:
        base: Base currency code (e.g., 'EUR')
        quote: Quote currency code (e.g., 'USD')
        
    Returns:
        Formatted symbol for Yahoo Finance URL
    """
    # Convert to uppercase for consistency
    base = base.upper()
    quote = quote.upper()
    
    # Different format when base currency is USD
    if base == 'USD':
        return f"{quote}%3DX"  # URL encoded form of JPY=X
    else:
        return f"{base}{quote}%3DX"  # URL encoded form of EURUSD=X

def scrape_yahoo_finance_news(currency_pairs, max_articles=5, debug_log=None):
    """
    Scrape news from Yahoo Finance for specified currency pairs
    """
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("yahoo_scraper")
    
    all_news = []
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
    ]
    
    # More robust headers
    headers = {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }
    
    if debug_log is None:
        debug_log = []
    
    total_found = 0
    
    # Use a session for better cookie handling
    session = requests.Session()
    
    for base, quote in currency_pairs:
        try:
            # Format currency pair for Yahoo Finance URL
            yahoo_symbol = format_currency_pair_for_yahoo(base, quote)
            
            # Try both .com and uk domains
            domains = ["https://finance.yahoo.com", "https://uk.finance.yahoo.com"]
            
            for domain in domains:
                url = f"{domain}/quote/{yahoo_symbol}/news?{random.random()}"
                logger.info(f"Fetching news for {base}/{quote} from URL: {url}")
                debug_log.append(f"Fetching news for {base}/{quote} from URL: {url}")
                
                # Add a random delay to avoid being blocked
                time.sleep(random.uniform(1.5, 3.5))
                
                # Make request with retries
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        # Rotate user agent with each attempt
                        headers['User-Agent'] = random.choice(user_agents)
                        response = session.get(url, headers=headers, timeout=10)
                        
                        if response.status_code == 200:
                            break
                        elif response.status_code == 403 or response.status_code == 429:
                            # Forbidden or rate limited - wait longer and retry
                            logger.warning(f"Rate limited (status {response.status_code}). Waiting before retry...")
                            debug_log.append(f"Rate limited (status {response.status_code}). Waiting before retry...")
                            time.sleep(random.uniform(5, 10))
                        else:
                            logger.warning(f"Failed with status {response.status_code}. Attempt {attempt+1}/{max_retries}")
                            debug_log.append(f"Failed with status {response.status_code}. Attempt {attempt+1}/{max_retries}")
                            time.sleep(random.uniform(2, 4))
                    except requests.exceptions.RequestException as e:
                        logger.warning(f"Request exception: {e}. Attempt {attempt+1}/{max_retries}")
                        debug_log.append(f"Request exception: {e}. Attempt {attempt+1}/{max_retries}")
                        time.sleep(random.uniform(2, 4))
                
                if response.status_code != 200:
                    logger.error(f"Failed to fetch data for {base}/{quote}: {response.status_code}")
                    debug_log.append(f"Failed to fetch data for {base}/{quote}: {response.status_code}")
                    continue
                
                # Parse HTML with error handling
                try:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Save HTML for debugging if needed
                    if "yahoo_finance_news" not in response.text.lower():
                        logger.warning("Response doesn't appear to contain Yahoo Finance news content")
                        debug_log.append("Response doesn't appear to contain Yahoo Finance news content")
                        # Optionally save the HTML for inspection
                        # with open(f"yahoo_response_{base}_{quote}.html", "w", encoding="utf-8") as f:
                        #     f.write(response.text)
                    
                    # Find news container (based on the HTML structure)
                    # Try multiple selectors as Yahoo might change their page structure
                    selectors = [
                        'div[data-testid="news-tabs-container"]',
                        'div.news-stream',
                        'div#news-tabs-container',
                        'ul.Pos\\(r\\)'
                    ]
                    
                    news_container = None
                    for selector in selectors:
                        news_container = soup.select_one(selector)
                        if news_container:
                            logger.info(f"Found news container using selector: {selector}")
                            debug_log.append(f"Found news container using selector: {selector}")
                            break
                    
                    if not news_container:
                        logger.warning(f"News container not found for {base}/{quote}")
                        debug_log.append(f"News container not found for {base}/{quote}")
                        continue
                    
                    # Try multiple selectors for news items
                    news_items_selectors = [
                        'li.stream-item.story-item',
                        'li.js-stream-content',
                        'div[data-test="mrt-node"]'
                    ]
                    
                    news_items = []
                    for selector in news_items_selectors:
                        items = soup.select(selector)
                        if items:
                            news_items = items
                            logger.info(f"Found {len(items)} news items using selector: {selector}")
                            debug_log.append(f"Found {len(items)} news items using selector: {selector}")
                            break
                    
                    if not news_items:
                        logger.warning(f"No news found for {base}/{quote}")
                        debug_log.append(f"No news found for {base}/{quote}")
                        continue
                    
                    logger.info(f"Found {len(news_items)} news items for {base}/{quote}")
                    debug_log.append(f"Found {len(news_items)} news items for {base}/{quote}")
                    total_found += len(news_items)
                    
                    # Process each news item
                    pair_news = []
                    for item in news_items[:max_articles]:
                        try:
                            # Try different title selectors
                            title_selectors = ['h3.clamp', 'a h3', 'h3', 'a[data-test="title"]']
                            title_element = None
                            for selector in title_selectors:
                                title_element = item.select_one(selector)
                                if title_element:
                                    break
                                    
                            if not title_element:
                                logger.warning("No title found for news item, skipping")
                                continue
                                
                            title = title_element.text.strip()
                            
                            # Try different link selectors
                            link_selectors = [
                                'a.subtle-link[data-ylk*="elm:hdln"]',
                                'a[data-test="title"]',
                                'a.mega-item-header-link',
                                'a.js-content-viewer'
                            ]
                            
                            link_element = None
                            for selector in link_selectors:
                                link_element = item.select_one(selector)
                                if link_element:
                                    break
                                    
                            link = link_element['href'] if link_element and 'href' in link_element.attrs else ''
                            if link and not link.startswith('http'):
                                link = f"{domain}{link}"
                            
                            # Extract source and timestamp
                            publishing_selectors = ['div.publishing', 'div.C(#959595)', 'div.provider-name']
                            publishing_element = None
                            for selector in publishing_selectors:
                                publishing_element = item.select_one(selector)
                                if publishing_element:
                                    break
                                    
                            source = "Yahoo Finance"
                            timestamp = datetime.now()
                            
                            if publishing_element:
                                source_text = publishing_element.text.strip()
                                parts = source_text.split('•')
                                
                                if len(parts) >= 1:
                                    source = parts[0].strip()
                                
                                if len(parts) >= 2:
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
                            
                            # Find ticker tags for the news item
                            tickers = []
                            ticker_selectors = ['a.ticker', 'span.symbol']
                            for selector in ticker_selectors:
                                ticker_elements = item.select(selector)
                                for ticker_elem in ticker_elements:
                                    ticker_symbol = ticker_elem.select_one('span.symbol')
                                    if ticker_symbol:
                                        tickers.append(ticker_symbol.text.strip())
                                    else:
                                        # If no nested span, use the element text directly
                                        ticker_text = ticker_elem.text.strip()
                                        if ticker_text and len(ticker_text) < 10:  # Reasonable length for a ticker
                                            tickers.append(ticker_text)
                            
                            # Create news item
                            news_item = {
                                "title": title,
                                "timestamp": timestamp,
                                "currency": f"{base}/{quote}",
                                "source": source,
                                "url": link,
                                "related_tickers": tickers
                            }
                            
                            # Extract summary if available
                            summary_selectors = ['p.clamp', 'p.summary', 'div.summary']
                            for selector in summary_selectors:
                                summary_element = item.select_one(selector)
                                if summary_element:
                                    news_item["summary"] = summary_element.text.strip()
                                    break
                            
                            # Analyze sentiment using TextBlob
                            text_for_sentiment = title
                            if "summary" in news_item:
                                text_for_sentiment += " " + news_item["summary"]
                                
                            analysis = TextBlob(text_for_sentiment)
                            news_item["score"] = round(analysis.sentiment.polarity, 2)  # -1 to 1
                            
                            if news_item["score"] > 0.2:
                                news_item["sentiment"] = "positive"
                            elif news_item["score"] < -0.2:
                                news_item["sentiment"] = "negative"
                            else:
                                news_item["sentiment"] = "neutral"
                            
                            pair_news.append(news_item)
                            
                        except Exception as e:
                            logger.error(f"Error processing news item for {base}/{quote}: {e}")
                            debug_log.append(f"Error processing news item for {base}/{quote}: {e}")
                            continue
                    
                    # If we found news items, we can break the domain loop
                    if pair_news:
                        all_news.extend(pair_news)
                        break
                        
                except Exception as e:
                    logger.error(f"Error parsing HTML for {base}/{quote}: {e}")
                    debug_log.append(f"Error parsing HTML for {base}/{quote}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error scraping news for {base}/{quote}: {e}")
            debug_log.append(f"Error scraping news for {base}/{quote}: {e}")
    
    # Sort all news by timestamp (newest first)
    all_news.sort(key=lambda x: x["timestamp"], reverse=True)
    
    # Log final results
    logger.info(f"Total news articles found: {len(all_news)}")
    debug_log.append(f"Total news articles found: {len(all_news)}")
    
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