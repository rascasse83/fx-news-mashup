# scraper.py
import requests
import time
import random
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from textblob import TextBlob

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
    
    total_found = 0  # Add a counter for total articles found
    
    for base, quote in currency_pairs:
        try:
            # Format currency pair for Yahoo Finance URL
            yahoo_symbol = format_currency_pair_for_yahoo(base, quote)
            url = f"https://uk.finance.yahoo.com/quote/{yahoo_symbol}/news/?{random.random()}"
            print(f"Fetching news for {base}/{quote} from URL: {url}")  # Console logging
            debug_log.append(f"Fetching news for {base}/{quote} from URL: {url}")
            
            # Add a random delay to avoid being blocked
            time.sleep(random.uniform(0.5, 1.5))
            
            # Make request
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                print(f"Failed to fetch data for {base}/{quote}: {response.status_code}")  # Console logging
                debug_log.append(f"Failed to fetch data for {base}/{quote}: {response.status_code}")
                continue
                
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find news container (based on the HTML structure)
            news_container = soup.select_one('div[data-testid="news-tabs-container"]')
            if not news_container:
                print(f"News container not found for {base}/{quote}")  # Console logging
                debug_log.append(f"News container not found for {base}/{quote}")
                # Try finding the general news stream
                news_container = soup.select_one('div.news-stream')
                if not news_container:
                    print(f"Alternate news container not found for {base}/{quote}")  # Console logging
                    debug_log.append(f"Alternate news container not found for {base}/{quote}")
                    continue
            
            # Find all news items in the stream
            news_items = soup.select('li.stream-item.story-item')
            
            if not news_items:
                print(f"No news found for {base}/{quote}")  # Console logging
                debug_log.append(f"No news found for {base}/{quote}")
                continue
            
            print(f"Found {len(news_items)} news items for {base}/{quote}")  # Console logging
            debug_log.append(f"Found {len(news_items)} news items for {base}/{quote}")
            total_found += len(news_items)
                
            # Process each news item
            pair_news = []
            for item in news_items[:max_articles]:
                try:
                    # Extract title and other data...
                    # ... [rest of your function remains the same]
                    # Extract title
                    title_element = item.select_one('h3.clamp')
                    if not title_element:
                        continue
                    title = title_element.text.strip()
                    
                    # Extract link
                    link_element = item.select_one('a.subtle-link[data-ylk*="elm:hdln"]')
                    link = link_element['href'] if link_element and 'href' in link_element.attrs else ''
                    if link and not link.startswith('http'):
                        link = f"https://uk.finance.yahoo.com{link}"
                    
                    # Extract source and timestamp
                    publishing_element = item.select_one('div.publishing')
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
                    ticker_elements = item.select('a.ticker')
                    for ticker_elem in ticker_elements:
                        ticker_symbol = ticker_elem.select_one('span.symbol')
                        if ticker_symbol:
                            tickers.append(ticker_symbol.text.strip())
                    
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
                    summary_element = item.select_one('p.clamp')
                    if summary_element:
                        news_item["summary"] = summary_element.text.strip()
                    
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
                    debug_log.append(f"Error processing news item for {base}/{quote}: {e}")
                    continue
            
            all_news.extend(pair_news)
            
        except Exception as e:
            debug_log.append(f"Error scraping news for {base}/{quote}: {e}")
    
    # Sort all news by timestamp (newest first)
    all_news.sort(key=lambda x: x["timestamp"], reverse=True)
    
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