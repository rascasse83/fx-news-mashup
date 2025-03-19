"""
News service for fetching and processing news data.
Handles fetching, caching, and processing news from various sources.
"""
import os
import re
import json
import glob
import random
import logging
import re
from typing import List, Dict, Any, Set, Tuple, Optional
from datetime import datetime, timedelta
import streamlit as st
from bs4 import BeautifulSoup
import requests
from fx_news.scrapers.news_scraper import scrape_yahoo_finance_news, create_mock_news, analyze_news_sentiment, load_news_from_files, scrape_indices_news
from fx_news.scrapers.article_downloader import is_timestamp_processed
from fx_news.data.models import NewsItem
from fx_news.utils.notifications import add_notification
import gc

# To Do FT 19th MArch
# Downloading of articles works but i think the market type categorisation/sentiment causes filtering issues

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.DEBUG
)
logger = logging.getLogger("news_service")
logger.setLevel(logging.INFO)  # Set to INFO for production, DEBUG for development

def refresh_news_callback():
    """
    Callback function for refreshing news.
    Triggered when the user clicks the refresh news button.
    Saves existing news, forces a refresh, and triggers a page rerun.
    """

    # reset_news_session_state()
    from fx_news.scrapers.news_scraper import SESSION_PROCESSED_TIMESTAMPS, SESSION_PROCESSED_URLS
    # Reset timestamp tracking
    SESSION_PROCESSED_TIMESTAMPS.clear()
    SESSION_PROCESSED_URLS.clear()

    # Rest of your function remains the same
    reset_news_session_state()

    # Set the refresh flag
    st.session_state.refresh_news_clicked = True
    logger.info("Refresh news button clicked!")
    
    # Determine the appropriate cache keys based on market type
    if st.session_state.market_type == 'FX':
        news_cache_key = 'fx_news'
        last_fetch_key = 'last_fx_news_fetch'
        next_refresh_key = 'next_fx_news_refresh_time'
    elif st.session_state.market_type == 'Crypto':
        news_cache_key = 'crypto_news'
        last_fetch_key = 'last_crypto_news_fetch'
        next_refresh_key = 'next_crypto_news_refresh_time'
    else:  # Indices
        news_cache_key = 'indices_news'
        last_fetch_key = 'last_indices_news_fetch'
        next_refresh_key = 'next_indices_news_refresh_time'
    
    logger.info(f"Using cache keys: {news_cache_key}, {last_fetch_key}, {next_refresh_key}")
    
    # IMPORTANT: Save the existing news instead of clearing it
    if news_cache_key in st.session_state and st.session_state[news_cache_key]:
        existing_news = st.session_state[news_cache_key].copy()
        st.session_state[f"{news_cache_key}_temp"] = existing_news
        logger.info(f"Saved {len(existing_news)} existing news items to temp storage")
    else:
        logger.info("No existing news to save")
    
    # Reset the fetch timestamp to force a refresh
    st.session_state[last_fetch_key] = None
    logger.info(f"Reset {last_fetch_key} to None")
    
    # Set the next refresh time to now
    st.session_state[next_refresh_key] = datetime.now()
    logger.info(f"Set {next_refresh_key} to {datetime.now()}")
    
    # Add notification
    add_notification(f"Refreshing {st.session_state.market_type} news...", "info")
    logger.info("Added notification and will now trigger rerun")
    
    # Force a refresh
    st.rerun()


def debug_news_file_loading(folder="fx_news/scrapers/news/yahoo", symbol="gbp_usd"):
    """
    Debug function to check why news files aren't being loaded.
    Add this to your news.py file temporarily and call it from display_news_sidebar.
    
    Args:
        folder: News folder path
        symbol: Symbol to check (e.g., "gbp_usd")
        
    Returns:
        Dict with diagnostic information
    """
    import os
    import glob
    import logging
    from datetime import datetime, timedelta
    import streamlit as st
    
    logger = logging.getLogger("debug_news")
    logger.setLevel(logging.INFO)
    
    results = {
        "folder_exists": False,
        "folder_path": os.path.abspath(folder),
        "cwd": os.getcwd(),
        "files_found": 0,
        "symbol_files_found": 0,
        "file_list": [],
        "symbol_file_list": [],
        "symbol_used": symbol,
        "cutoff_days": 5,
        "error": None
    }
    
    try:
        # Check if folder exists
        results["folder_exists"] = os.path.exists(folder)
        
        if not results["folder_exists"]:
            # Try parent directories
            parent_folder = os.path.dirname(folder)
            results["parent_folder_exists"] = os.path.exists(parent_folder)
            results["parent_folder"] = parent_folder
            
            # Check alternative paths
            alt_paths = [
                "scrapers/news/yahoo",
                os.path.join(os.getcwd(), "scrapers/news/yahoo"),
                os.path.join(os.getcwd(), "fx_news/scrapers/news/yahoo")
            ]
            
            results["alt_paths_check"] = {}
            for path in alt_paths:
                results["alt_paths_check"][path] = os.path.exists(path)
            
            # Get all drive folders
            results["root_dirs"] = os.listdir(os.path.abspath('/'))
        else:
            # Folder exists, check files
            try:
                all_files = os.listdir(folder)
                results["files_found"] = len(all_files)
                results["file_list"] = all_files[:10]  # First 10 files
                
                # Check for symbol-specific files
                pattern = os.path.join(folder, f"*_{symbol}.txt")
                symbol_files = glob.glob(pattern)
                results["symbol_files_found"] = len(symbol_files)
                results["symbol_file_list"] = [os.path.basename(f) for f in symbol_files]
                
                # Check cutoff date logic
                max_days_old = 5
                cutoff_timestamp = int((datetime.now() - timedelta(days=max_days_old)).timestamp())
                results["cutoff_timestamp"] = cutoff_timestamp
                results["cutoff_date"] = datetime.fromtimestamp(cutoff_timestamp).isoformat()
                
                # Check sample file
                if symbol_files:
                    sample_file = symbol_files[0]
                    results["sample_file"] = os.path.basename(sample_file)
                    
                    # Check file content
                    with open(sample_file, 'r', encoding='utf-8') as f:
                        content = f.read(500)  # First 500 chars
                        results["sample_content"] = content
                        
                        # Check timestamp in file
                        timestamp_match = re.search(r'Timestamp: (\d+)', content)
                        if timestamp_match:
                            file_timestamp = int(timestamp_match.group(1))
                            results["file_timestamp"] = file_timestamp
                            results["file_date"] = datetime.fromtimestamp(file_timestamp).isoformat()
                            results["file_passes_cutoff"] = file_timestamp >= cutoff_timestamp
                            results["days_old"] = (datetime.now() - datetime.fromtimestamp(file_timestamp)).days
                            
                            # Check if we'd process this timestamp
                            results["timestamp_processed"] = is_timestamp_processed(symbol, file_timestamp)
                        else:
                            results["timestamp_found"] = False
            except Exception as e:
                results["file_listing_error"] = str(e)
    
    except Exception as e:
        results["error"] = str(e)
    
    # Display results in Streamlit
    st.write("### News File Loading Debug")
    st.json(results)
    
    # Log results
    logger.info(f"News debug results: {results}")
    
    return results




def reset_news_session_state():
    """
    Reset all news-related session state to force a fresh load from disk.
    Add this function to your code and call it when you need to reset everything.
    """
    import streamlit as st
    from datetime import datetime
    import logging
    import importlib
    
    logger = logging.getLogger("reset_news")
    
    # Reset news cache
    news_keys = ['fx_news', 'crypto_news', 'indices_news', 'cached_news']
    for key in news_keys:
        if key in st.session_state:
            st.session_state[key] = []
            logger.info(f"Reset {key}")
    
    # Reset timestamps
    timestamp_keys = ['last_fx_news_fetch', 'last_crypto_news_fetch', 'last_indices_news_fetch', 'last_news_fetch']
    for key in timestamp_keys:
        if key in st.session_state:
            st.session_state[key] = None
            logger.info(f"Reset {key}")
    
    # Reset disk_news_loaded flag
    if 'disk_news_loaded' in st.session_state:
        st.session_state.disk_news_loaded = False
        logger.info("Reset disk_news_loaded flag")
    
    # Reset timestamp tracking in article_downloader
    try:
        article_downloader = importlib.import_module('fx_news.scrapers.article_downloader')
        if hasattr(article_downloader, 'SESSION_PROCESSED_TIMESTAMPS'):
            article_downloader.SESSION_PROCESSED_TIMESTAMPS = {}
            logger.info("Reset SESSION_PROCESSED_TIMESTAMPS")
        if hasattr(article_downloader, 'SESSION_PROCESSED_URLS'):
            article_downloader.SESSION_PROCESSED_URLS = set()
            logger.info("Reset SESSION_PROCESSED_URLS")
    except (ImportError, AttributeError) as e:
        logger.error(f"Error resetting session variables: {str(e)}")
    
    # Reset next refresh times
    refresh_keys = ['next_fx_news_refresh_time', 'next_crypto_news_refresh_time', 'next_indices_news_refresh_time']
    for key in refresh_keys:
        if key in st.session_state:
            st.session_state[key] = datetime.now()
            logger.info(f"Reset {key}")
    
    return "Session state reset complete!"


def fetch_news(currencies: List[str] = None, use_mock_fallback: bool = True, 
              force: bool = False, page: int = 1, items_per_page: int = 20) -> List[NewsItem]:
    """
    Fetch news for currency pairs, with improved error handling and fallbacks.
    
    Args:
        currencies: List of currency codes to fetch news for
        use_mock_fallback: Whether to use mock data if real data can't be fetched
        force: Whether to force a refresh regardless of cache
        
    Returns:
        List of NewsItem objects
    """
    # Add notification to track progress
    import logging
    import os
    import glob
    from fx_news.utils.notifications import add_notification
    
    logger = logging.getLogger("fetch_news")
    
    # Debug logging
    logger.info(f"Fetch news called with {len(currencies) if currencies else 0} currencies, mock_fallback={use_mock_fallback}, force={force}")
    
    # Start by checking if we have any subscriptions
    if 'subscriptions' not in st.session_state or not st.session_state.subscriptions:
        logger.warning("No subscriptions found, returning empty news list")
        add_notification("No subscriptions found. Please add currency pairs to see news.", "info")
        return []
    
    # Get the appropriate news cache key based on market type
    market_type = st.session_state.market_type
    if market_type == 'FX':
        news_cache_key = 'fx_news'
        last_fetch_key = 'last_fx_news_fetch'
    elif market_type == 'Crypto':
        news_cache_key = 'crypto_news'
        last_fetch_key = 'last_crypto_news_fetch'
    else:  # Indices
        news_cache_key = 'indices_news'
        last_fetch_key = 'last_indices_news_fetch'
    
    # Log the current cache state
    has_cached_news = news_cache_key in st.session_state and st.session_state[news_cache_key]
    logger.info(f"Refreshing {market_type} news: {'Has cached news' if has_cached_news else 'No cached ' + market_type + ' news'}")
    
    # Check if we need to refresh at all
    if not force and 'last_news_fetch' in st.session_state and st.session_state.last_news_fetch:
        # Don't refresh if it's been less than 60 seconds since last refresh
        seconds_since_refresh = (datetime.now() - st.session_state.last_news_fetch).total_seconds()
        if seconds_since_refresh < 60:
            # Return cached news if available
            if 'cached_news' in st.session_state and st.session_state.cached_news:
                return st.session_state.cached_news
            elif has_cached_news:
                # If market-specific news is available but not in cached_news, use that
                st.session_state.cached_news = st.session_state[news_cache_key]
                return st.session_state.cached_news

    # For indices, we want to use just the base (not currency pairs)
    if st.session_state.market_type == 'Indices':
        # Get list of indices
        currency_pairs = [(sub["base"], sub["quote"]) for sub in st.session_state.subscriptions]
    else:
        # Regular currency pairs for FX and Crypto
        currency_pairs = list(set((sub["base"], sub["quote"]) for sub in st.session_state.subscriptions))

    if not currency_pairs:
        logger.warning("No currency pairs found in subscriptions, returning empty news list")
        add_notification("No currency pairs found in subscriptions.", "info")
        return []

    # Initialize debug log
    if 'debug_log' not in st.session_state or not isinstance(st.session_state.debug_log, list):
        st.session_state.debug_log = []
    
    # Step 1: Load news from disk
    all_loaded_news = []
    news_folder = "fx_news/scrapers/news/yahoo"
    
    try:
        logger.info("Loading news from disk")
        
        # Get list of all currency symbols as lowercase for matching
        currency_symbols = set()
        if currencies:
            for currency in currencies:
                currency_symbols.add(currency.lower())
        
        # Load files for all currencies
        from fx_news.scrapers.news_scraper import load_news_from_files
        
        for currency in currency_symbols:
            # Load with a reasonable max_days_old
            news_items = load_news_from_files(currency, folder=news_folder, max_days_old=7)
            logger.info(f"Loaded {len(news_items)} news items for {currency} from disk")
            all_loaded_news.extend(news_items)
            
        logger.info(f"Total news loaded from disk: {len(all_loaded_news)}")
        
    except Exception as e:
        logger.error(f"Error loading news from disk: {str(e)}")
        # Continue with scraping anyway
    
    # Step 2: Scrape new articles
    scraped_news = []
    
    try:
        logger.info("Scraping new articles from Yahoo Finance")
        add_notification("Scraping new articles from Yahoo Finance...", "info")
        
        # Scrape Yahoo Finance
        scraped_news = scrape_yahoo_finance_news(
            currency_pairs=currency_pairs,
            max_articles=10,  # Adjust as needed
            include_cached=False,  # We already loaded from disk separately
            news_folder=news_folder,
            debug_log=st.session_state.debug_log,
            force_refresh=force
        )
        
        logger.info(f"Scraped {len(scraped_news)} new articles from Yahoo Finance")
        
    except Exception as e:
        logger.error(f"Error scraping Yahoo Finance: {str(e)}")
        add_notification(f"Error scraping news: {str(e)}", "error")
    
    # Step 3: Merge the results
    combined_news = []
    
    # First add all loaded news
    combined_news.extend(all_loaded_news)
    
    # Then add newly scraped news, avoiding duplicates
    seen_urls = set(item.get('url', '') for item in combined_news if item.get('url'))
    seen_ids = set(item.get('unix_timestamp', 0) for item in combined_news if item.get('unix_timestamp'))
    
    for item in scraped_news:
        # Skip if we've already seen this URL or timestamp
        url = item.get('url', '')
        timestamp = item.get('unix_timestamp', 0)
        
        if url and url in seen_urls:
            continue
            
        if timestamp and timestamp in seen_ids:
            continue
            
        # Add to combined news
        combined_news.append(item)
        
        # Update seen sets
        if url:
            seen_urls.add(url)
        if timestamp:
            seen_ids.add(timestamp)
    
    logger.info(f"Combined {len(all_loaded_news)} disk items and {len(scraped_news)} scraped items into {len(combined_news)} total news items")
    
    # If we have combined news, process and return it
    if combined_news:
        # Process the news to add market type tags
        processed_news = process_news(combined_news)
        
        # Return the appropriate market-specific news
        if market_type == 'FX':
            return processed_news['fx_news']
        elif market_type == 'Crypto':
            return processed_news['crypto_news']
        else:  # Indices
            return processed_news['indices_news']
    
    # If no real news, try mock news as fallback
    if use_mock_fallback:
        add_notification("Using mock news data as fallback", "info")
        mock_news = create_mock_news(currencies)
        
        # Tag and categorize mock news
        processed_news = process_news(mock_news)
        
        # Return the appropriate news for the current market type
        if market_type == 'FX':
            return processed_news['fx_news']
        elif market_type == 'Crypto':
            return processed_news['crypto_news']
        else:  # Indices
            return processed_news['indices_news']

    # As a last resort, return empty list
    logger.warning("No news sources available, returning empty list")
    add_notification("No news sources available. Please try again later.", "warning")
    # gc.collect()  # Force garbage collection
    return []

def merge_news(new_items, existing_news, market_cached_news):
    """
    Merge news items from different sources, using article IDs for improved deduplication.
    
    Args:
        new_items: Newly fetched news items
        existing_news: Existing cached news items (general cache)
        market_cached_news: Market-specific cached news items
        
    Returns:
        List of merged news items with duplicates removed
    """
    merged_news = []
    seen_ids = set()
    
    # Add existing cached news first (both general and market-specific)
    for news_sources in [existing_news, market_cached_news]:
        for item in news_sources:
            # Try to extract or create a unique ID for each item
            item_id = None
            
            # First check if we already have an article_id in the item
            if 'article_id' in item and item['article_id']:
                item_id = item['article_id']
            # Next try to extract it from URL
            elif item.get('url'):
                from fx_news.scrapers.article_downloader import extract_article_id_from_url
                item_id = extract_article_id_from_url(item.get('url'))
                # Store the extracted ID in the item for future use
                item['article_id'] = item_id
            # If still no ID, use timestamp + title
            elif item.get('unix_timestamp'):
                item_id = f"{item.get('unix_timestamp')}_{item.get('title', '')}"
            # Last resort: just use title
            else:
                item_id = item.get('title', '')
                
            if item_id and item_id not in seen_ids:
                merged_news.append(item)
                seen_ids.add(item_id)
    
    # Then add new items, avoiding duplicates
    for item in new_items:
        # Try to extract or create a unique ID for each item
        item_id = None
        
        # First check if we already have an article_id in the item
        if 'article_id' in item and item['article_id']:
            item_id = item['article_id']
        # Next try to extract it from URL
        elif item.get('url'):
            from fx_news.scrapers.article_downloader import extract_article_id_from_url
            item_id = extract_article_id_from_url(item.get('url'))
            # Store the extracted ID in the item for future use
            item['article_id'] = item_id
        # If still no ID, use timestamp + title
        elif item.get('unix_timestamp'):
            item_id = f"{item.get('unix_timestamp')}_{item.get('title', '')}"
        # Last resort: just use title
        else:
            item_id = item.get('title', '')
            
        if item_id and item_id not in seen_ids:
            merged_news.append(item)
            seen_ids.add(item_id)
    
    # Sort by timestamp (newest first)
    merged_news.sort(key=lambda x: x.get('timestamp', datetime.now()), reverse=True)
    
    return merged_news

def process_news(news_items):
    """
    Process and categorize news items by market type, with robust error handling.
    
    Args:
        news_items: List of news items to process
        
    Returns:
        Dictionary with categorized news
    """
    import streamlit as st
    from datetime import datetime
    
    # Guard against None or empty news_items
    if not news_items:
        # Return empty categorized news
        empty_result = {
            'all_news': [],
            'fx_news': [],
            'crypto_news': [],
            'indices_news': [],
            'market_news': []
        }
        
        # Update session state with empty lists
        st.session_state.fx_news = []
        st.session_state.crypto_news = []
        st.session_state.indices_news = []
        
        # Update timestamps to avoid immediate refresh
        st.session_state.last_fx_news_fetch = datetime.now()
        st.session_state.last_crypto_news_fetch = datetime.now()
        st.session_state.last_indices_news_fetch = datetime.now()
        
        return empty_result
    
    # Try to add article IDs, but don't fail if it's not possible
    try:
        for item in news_items:
            if 'article_id' not in item or not item['article_id']:
                if item.get('url'):
                    try:
                        from fx_news.scrapers.article_downloader import extract_article_id_from_url
                        item['article_id'] = extract_article_id_from_url(item.get('url'))
                    except (ImportError, AttributeError):
                        # Skip if the function isn't available
                        pass
    except Exception as e:
        # Log the error but continue processing
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error adding article IDs: {str(e)}")
        
    # Tag news by market type
    tagged_news = tag_news_by_market_type(news_items)
    
    # Separate news based on market type
    fx_news = [item for item in tagged_news if item.get('is_fx', False)]
    crypto_news = [item for item in tagged_news if item.get('is_crypto', False)]
    indices_news = [item for item in tagged_news if item.get('is_indices', False)]
    market_news = [item for item in tagged_news if 
                  item.get('is_market', False) or
                  not (item.get('is_fx', False) or 
                       item.get('is_crypto', False) or 
                       item.get('is_indices', False))]
    
    # Deduplicate market news using URLs or titles as fallbacks
    market_news_deduplicated = []
    seen_ids = set()
    
    for item in market_news:
        # Try multiple identification methods in order of preference
        item_id = (
            item.get('article_id') or 
            item.get('url') or 
            (f"{item.get('unix_timestamp')}_{item.get('title', '')}" if item.get('unix_timestamp') else None) or
            item.get('title', '')
        )
        
        if item_id and item_id not in seen_ids:
            market_news_deduplicated.append(item)
            seen_ids.add(item_id)
    
    # Add deduplicated market news to all categories
    for market_item in market_news_deduplicated:
        if market_item not in fx_news:
            fx_news.append(market_item)
        if market_item not in crypto_news:
            crypto_news.append(market_item)
        if market_item not in indices_news:
            indices_news.append(market_item)
    
    # Sort each category by timestamp
    fx_news = sorted(fx_news, key=lambda x: x.get('timestamp', datetime.now()), reverse=True)
    crypto_news = sorted(crypto_news, key=lambda x: x.get('timestamp', datetime.now()), reverse=True)
    indices_news = sorted(indices_news, key=lambda x: x.get('timestamp', datetime.now()), reverse=True)
    
    # Store in session state
    st.session_state.fx_news = fx_news
    st.session_state.crypto_news = crypto_news
    st.session_state.indices_news = indices_news
    
    # Update timestamps
    st.session_state.last_fx_news_fetch = datetime.now()
    st.session_state.last_crypto_news_fetch = datetime.now()
    st.session_state.last_indices_news_fetch = datetime.now()
    
    # Set cached_news based on current market type
    market_type = st.session_state.market_type
    if market_type == 'FX':
        st.session_state.cached_news = fx_news
    elif market_type == 'Crypto':
        st.session_state.cached_news = crypto_news
    else:  # Indices
        st.session_state.cached_news = indices_news
    
    return {
        'all_news': tagged_news,
        'fx_news': fx_news,
        'crypto_news': crypto_news,
        'indices_news': indices_news,
        'market_news': market_news_deduplicated
    }

# def tag_news_by_market_type(news_items):
#     """
#     Tags news items with appropriate market type flags.
#     This helps with filtering later.
    
#     Args:
#         news_items: List of news item dictionaries
    
#     Returns:
#         List of news items with market_type tags
#     """
#     if not news_items:
#         return []
    
#     # Define market-specific currencies and terms
#     fx_currencies = {'EUR', 'USD', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'CNY', 'NZD', 
#                     'HKD', 'INR', 'SGD', 'NOK', 'SEK', 'MXN', 'ZAR', 'TRY', 'XAG'}
    
#     crypto_currencies = {'BTC', 'ETH', 'XRP', 'SOL', 'BNB', 'ADA', 'DOGE', 'DOT', 
#                          'AVAX', 'LINK', 'LTC', 'UNI', 'XLM', 'MATIC', 'ATOM', 
#                          'USDT', 'USDC', 'BUSD'}
    
#     crypto_terms = {'BITCOIN', 'ETHEREUM', 'CRYPTOCURRENCY', 'BLOCKCHAIN', 'CRYPTO', 
#                    'TOKEN', 'ALTCOIN', 'DEFI', 'NFT', 'MINING', 'WALLET'}
    
#     indices_symbols = {'^DJI', '^GSPC', '^IXIC', '^FTSE', '^GDAXI', '^FCHI', '^N225'}
#     indices_names = {'DOW JONES', 'S&P 500', 'NASDAQ', 'FTSE 100', 'DAX', 'CAC 40', 'NIKKEI 225'}
#     indices_terms = {'INDEX', 'STOCK MARKET', 'SHARES', 'EQUITY', 'WALL STREET', 'NYSE', 'NASDAQ'}
    
#     fx_terms = {'FOREX', 'FX MARKET', 'CURRENCY PAIR', 'EXCHANGE RATE', 'CENTRAL BANK', 
#                'INTEREST RATE', 'MONETARY POLICY', 'DOLLAR', 'EURO', 'POUND', 'YEN'}
    
#     for item in news_items:
#         # Get currency and title/summary for classification
#         currency = item.get('currency', '')
#         if isinstance(currency, str):
#             currency = currency.upper()
#         else:
#             currency = ""
            
#         title = item.get('title', '').upper()
#         summary = item.get('summary', '').upper()
        
#         # Get currency pairs
#         currency_pairs = item.get('currency_pairs', set())
#         if not isinstance(currency_pairs, set):
#             currency_pairs = set()
            
#         # Extract all mentioned currencies from title and summary
#         all_text = f"{title} {summary}"
        
#         # Initialize market types flags as False
#         item['is_fx'] = False
#         item['is_crypto'] = False
#         item['is_indices'] = False
#         item['is_market'] = False
        
#         # Check for crypto indicators
#         crypto_currency_mentioned = (
#             currency in crypto_currencies or
#             any(c in all_text for c in crypto_currencies)
#         )
        
#         crypto_term_mentioned = any(term in all_text for term in crypto_terms)
        
#         # Check for indices indicators
#         indices_symbol_mentioned = (
#             currency in indices_symbols or 
#             any(sym in all_text for sym in indices_symbols)
#         )
        
#         indices_name_mentioned = (
#             currency in indices_names or
#             any(name in all_text for name in indices_names)
#         )
        
#         indices_term_mentioned = any(term in all_text for term in indices_terms)
        
#         # Check for FX indicators
#         fx_currency_mentioned = (
#             currency in fx_currencies or 
#             any(c in all_text for c in fx_currencies)
#         )
        
#         fx_term_mentioned = any(term in all_text for term in fx_terms)
        
#         # Check currency pairs for additional clues
#         has_crypto_pair = False
#         has_fx_pair = False
#         has_indices_pair = False
        
#         for pair in currency_pairs:
#             pair_str = str(pair).upper()
            
#             # Check if pair contains crypto currency
#             if any(c in pair_str for c in crypto_currencies):
#                 has_crypto_pair = True
                
#             # Check if pair contains indices symbol or name
#             if any(sym in pair_str for sym in indices_symbols) or any(name in pair_str for name in indices_names):
#                 has_indices_pair = True
                
#             # Check if pair contains FX currency and not crypto
#             if any(c in pair_str for c in fx_currencies) and not has_crypto_pair:
#                 has_fx_pair = True
        
#         # Assign market types based on indicators, with crypto taking precedence over FX
#         # since FX currencies can be part of crypto pairs (e.g., BTC/USD)
        
#         # Tag as crypto if:
#         # - Has clear crypto mentions or pairs
#         # - Has crypto terms
#         if crypto_currency_mentioned or has_crypto_pair or crypto_term_mentioned:
#             item['is_crypto'] = True
            
#         # Tag as indices if:
#         # - Has clear indices mentions or pairs
#         # - Has indices terms
#         elif indices_symbol_mentioned or indices_name_mentioned or has_indices_pair or indices_term_mentioned:
#             item['is_indices'] = True
            
#         # Tag as FX if:
#         # - Has clear FX mentions or pairs
#         # - Has FX terms
#         # - Is not already tagged as crypto or indices
#         elif (fx_currency_mentioned or has_fx_pair or fx_term_mentioned) and not (item['is_crypto'] or item['is_indices']):
#             item['is_fx'] = True
            
#         # If still not categorized, mark as general market news
#         if not (item['is_fx'] or item['is_crypto'] or item['is_indices']):
#             item['is_market'] = True
    
            
#     return news_items

def tag_news_by_market_type(news_items):
    """
    Tags news items with appropriate market type flags based on market-specific currencies.
    
    Args:
        news_items: List of news item dictionaries
    
    Returns:
        List of news items with market_type tags
    """
    if not news_items:
        return []
    
    # Define market-specific currencies
    fx_currencies = {'EUR', 'USD', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'CNY', 'NZD', 
                     'HKD', 'INR', 'SGD', 'NOK', 'SEK', 'MXN', 'ZAR', 'TRY', 'XAG'}
    
    crypto_currencies = {'BTC', 'ETH', 'XRP', 'SOL', 'BNB', 'ADA', 'DOGE', 'DOT', 
                         'AVAX', 'LINK', 'LTC', 'UNI', 'XLM', 'MATIC', 'ATOM', 
                         'USDT', 'USDC', 'BUSD'}
    
    indices_symbols = {'^DJI', '^GSPC', '^IXIC', '^FTSE', '^GDAXI', '^FCHI', '^N225',
                       'DJI', 'GSPC', 'IXIC', 'FTSE', 'GDAXI', 'FCHI', 'N225'}
    
    indices_names = {'DOW JONES', 'S&P 500', 'NASDAQ', 'FTSE 100', 'DAX', 'CAC 40', 'NIKKEI 225'}
    
    for item in news_items:
        # Reset market type flags
        item['is_fx'] = False
        item['is_crypto'] = False
        item['is_indices'] = False
        item['is_market'] = False
        
        # Get the currency from the item
        currency = item.get('currency', '')
        if isinstance(currency, str):
            currency = currency.upper()
        else:
            currency = ""
        
        # Extract file path to check file name pattern
        file_path = item.get('file_path', '')
        file_name = os.path.basename(file_path) if file_path else ''
        
        # First check currency pair structure
        if '/' in currency:
            base, quote = currency.split('/')
            
            # Crypto pair: if base is a crypto currency, it's crypto news
            if base in crypto_currencies:
                item['is_crypto'] = True
            # FX pair: if both base and quote are FX currencies, it's FX news
            elif base in fx_currencies and quote in fx_currencies:
                item['is_fx'] = True
            # If base is an index symbol, it's indices news
            elif base in indices_symbols or base in indices_names:
                item['is_indices'] = True
            # Default to market news
            else:
                item['is_market'] = True
        
        # If not a pair, check the file name pattern
        elif file_name:
            # Extract market type from file name
            match = re.search(r'article_\d+_([a-z0-9]+)_([a-z0-9]+)\.txt', file_name.lower())
            if match:
                base, quote = match.group(1).upper(), match.group(2).upper()
                
                # Crypto file: if base is a crypto currency, it's crypto news
                if base in crypto_currencies:
                    item['is_crypto'] = True
                # FX file: if both base and quote are FX currencies, it's FX news
                elif base in fx_currencies and quote in fx_currencies:
                    item['is_fx'] = True
                # Default to market news
                else:
                    item['is_market'] = True
            else:
                # Check for indices in file name (no quote currency)
                match = re.search(r'article_\d+_([a-z0-9]+)\.txt', file_name.lower())
                if match and match.group(1).upper() in indices_symbols:
                    item['is_indices'] = True
                else:
                    item['is_market'] = True
        
        # If no classification yet, check currency directly
        if not (item['is_fx'] or item['is_crypto'] or item['is_indices'] or item['is_market']):
            if currency in indices_names or currency in indices_symbols:
                item['is_indices'] = True
            elif currency in crypto_currencies:
                item['is_crypto'] = True
            elif currency in fx_currencies:
                item['is_fx'] = True
            else:
                item['is_market'] = True
        
        # Special case for Market news (applies to all market types)
        if currency == "MARKET":
            item['is_market'] = True
            # Market news should appear in all categories
            item['is_fx'] = True
            item['is_crypto'] = True
            item['is_indices'] = True
    
    return news_items

def fetch_market_specific_news(force=False):
    """
    Fetch news specific to the current market type.
    
    Args:
        force: If True, forces a refresh regardless of cache
    
    Returns:
        List of news items for the current market type
    """
    market_type = st.session_state.market_type
    
    # Determine which news cache to use
    if market_type == 'FX':
        news_cache_key = 'fx_news'
        last_fetch_key = 'last_fx_news_fetch'
    elif market_type == 'Crypto':
        news_cache_key = 'crypto_news'
        last_fetch_key = 'last_crypto_news_fetch'
    else:  # Indices
        news_cache_key = 'indices_news'
        last_fetch_key = 'last_indices_news_fetch'
    
    # Check if we need to refresh
    should_refresh = force
    
    if not should_refresh and last_fetch_key in st.session_state:
        last_fetch = st.session_state.get(last_fetch_key)
        if last_fetch is None:
            should_refresh = True
        elif (datetime.now() - last_fetch).total_seconds() > 300:  # 5 minutes
            should_refresh = True
    
    if should_refresh:
        # Get currencies from current subscriptions
        subscription_currencies = list(set([sub["base"] for sub in st.session_state.subscriptions] +
                                      [sub["quote"] for sub in st.session_state.subscriptions]))
        
        # Fetch news using market-specific approach
        if market_type == 'FX':
            # For FX, filter out crypto currencies
            fx_currencies = [c for c in subscription_currencies if c not in 
                           ['BTC', 'ETH', 'XRP', 'SOL', 'BNB', 'ADA', 'DOGE', 'DOT']]
            news_items = fetch_news(fx_currencies, force=True)
        elif market_type == 'Crypto':
            # For crypto, specifically target crypto currencies
            crypto_currencies = [c for c in subscription_currencies if c in 
                               ['BTC', 'ETH', 'XRP', 'SOL', 'BNB', 'ADA', 'DOGE', 'DOT']]
            news_items = fetch_news(crypto_currencies, force=True)
        else:  # Indices
            indices_list = [sub["base"] for sub in st.session_state.subscriptions]
            news_items = fetch_indices_news(indices_list, force=True)
        
        # Return the fetched news
        return news_items
    
    # If no refresh needed, return the cached news
    return st.session_state.get(news_cache_key, [])



def fetch_indices_news(indices_list=None, use_mock_fallback=True, force=False):
    """Fetch news for indices, with fallback to mock data."""
    
    # Check if we need to refresh at all
    if not force and 'last_indices_news_fetch' in st.session_state and st.session_state.last_indices_news_fetch:
        # Don't refresh if it's been less than 60 seconds since last refresh
        seconds_since_refresh = (datetime.now() - st.session_state.last_indices_news_fetch).total_seconds()
        if seconds_since_refresh < 60:
            if 'show_debug' in st.session_state and st.session_state.show_debug:
                st.info(f"Skipping indices news refresh (last refresh {seconds_since_refresh:.0f}s ago)")
            if 'indices_news' in st.session_state and st.session_state.indices_news:
                return st.session_state.indices_news
    
    # Get list of indices from subscriptions
    if indices_list is None and 'subscriptions' in st.session_state:
        indices_list = [sub["base"] for sub in st.session_state.subscriptions 
                      if sub["base"].startswith('^') or sub["base"] in indices]
    
    if not indices_list:
        indices_list = ['^DJI', '^GSPC', '^IXIC', '^FTSE', '^GDAXI', '^FCHI', '^N225']
    
    # Initialize debug log
    if 'debug_log' not in st.session_state or not isinstance(st.session_state.debug_log, list):
        st.session_state.debug_log = []
    
    st.session_state.debug_log.append(f"Attempting to fetch news for {len(indices_list)} indices")
    
    try:
        with st.spinner("Fetching latest indices news..."):
            news_items = scrape_indices_news(indices_list, debug_log=st.session_state.debug_log, news_folder="fx_news/scrapers/news/yahoo")            
            if news_items:
                add_notification(f"Successfully fetched {len(news_items)} indices news items", "success")
                st.session_state.last_indices_news_fetch = datetime.now()
                st.session_state.indices_news = news_items
                return news_items
            else:
                st.session_state.debug_log.append("No indices news items found")
    except Exception as e:
        if isinstance(st.session_state.debug_log, list):
            st.session_state.debug_log.append(f"Error fetching indices news: {str(e)}")
        add_notification(f"Error fetching indices news: {str(e)}", "error")
    
    if use_mock_fallback:
        add_notification("Using mock indices news data as fallback", "info")
        mock_news = create_mock_indices_news(indices_list)
        st.session_state.indices_news = mock_news
        st.session_state.last_indices_news_fetch = datetime.now()
        return mock_news
    
    if 'indices_news' in st.session_state and st.session_state.indices_news:
        return st.session_state.indices_news
    
    return []




def create_mock_indices_news(indices_list=None):
    """Create mock news items for indices when real data cannot be fetched"""
    if indices_list is None:
        indices_list = ['^DJI', '^GSPC', '^IXIC', '^FTSE', '^GDAXI', '^FCHI', '^N225']
    
    # Map indices to their proper names
    indices_names = {
        '^DJI': 'Dow Jones',
        '^GSPC': 'S&P 500',
        '^IXIC': 'NASDAQ',
        '^FTSE': 'FTSE 100',
        '^GDAXI': 'DAX',
        '^FCHI': 'CAC 40',
        '^N225': 'Nikkei 225',
    }
    
    mock_news = []
    current_time = datetime.now()
    
    # Sample news templates
    news_templates = [
        {"title": "{index} {direction} by {value}% as {factor} {impact} markets", 
         "summary": "The {index} {direction} {value}% {timeframe} as investors react to {factor}. Analysts suggest this trend might {future}.",
         "sentiment": "positive" if random.random() > 0.5 else "negative"},
        
        {"title": "{sector} stocks lead {index} {movement}",
         "summary": "{sector} companies showed strong performance today, leading the {index} to {movement}. This comes after {news_event}.",
         "sentiment": "positive" if random.random() > 0.5 else "negative"},
        
        {"title": "{index} {trades} as economic data {surprises} expectations",
         "summary": "The latest economic figures {compared} analyst forecasts, causing the {index} to {trade_action}. Market watchers now anticipate {outlook}.",
         "sentiment": "neutral"},
        
        {"title": "Market Report: {index} {closes} amid global {condition}",
         "summary": "Global markets experienced {volatility} today with the {index} {closing}. Key factors include {factor1} and {factor2}.",
         "sentiment": "positive" if random.random() > 0.5 else "negative"},
    ]
    
    # Sample data to fill templates
    directions = ["rises", "jumps", "climbs", "advances", "gains", "falls", "drops", "declines", "retreats", "slides"]
    positive_directions = ["rises", "jumps", "climbs", "advances", "gains"]
    values = [round(random.uniform(0.1, 3.5), 2) for _ in range(20)]
    factors = ["interest rate expectations", "inflation data", "economic growth concerns", "corporate earnings", 
               "central bank policy", "geopolitical tensions", "trade negotiations", "supply chain issues",
               "consumer sentiment", "employment figures", "manufacturing data", "commodity prices"]
    impacts = ["boost", "lift", "support", "pressure", "weigh on", "drag down"]
    timeframes = ["today", "in early trading", "in late trading", "this morning", "this afternoon", "in volatile trading"]
    futures = ["continue in the short term", "reverse in coming sessions", "stabilize as markets digest the news",
               "depend on upcoming economic data", "be closely watched by investors"]
    
    sectors = ["Technology", "Financial", "Healthcare", "Energy", "Industrial", "Consumer", "Utility", "Communication"]
    movements = ["higher", "gains", "advances", "rally", "decline", "losses", "lower"]
    news_events = ["positive earnings reports", "new product announcements", "regulatory approvals", 
                  "merger activity", "analyst upgrades", "economic data releases"]
    
    trades = ["trades higher", "moves upward", "edges higher", "trades lower", "moves downward", "stabilizes"]
    surprises = ["beats", "exceeds", "falls short of", "disappoints", "matches", "comes in line with"]
    compareds = ["came in stronger than", "were weaker than", "matched", "surprised to the upside of", "disappointed relative to"]
    trade_actions = ["rise", "gain", "advance", "fall", "decline", "drift lower", "trade in a tight range"]
    outlooks = ["further volatility", "stabilization", "careful positioning ahead of key data", "sector rotation"]
    
    closes = ["finishes higher", "closes lower", "ends mixed", "finishes flat", "closes up", "ends down"]
    conditions = ["uncertainty", "optimism", "concerns", "volatility", "recovery hopes", "recession fears"]
    volatilitys = ["heightened volatility", "cautious trading", "strong momentum", "mixed sentiment", "sector rotation"]
    closings = ["finishing in positive territory", "ending the session lower", "closing mixed", "recovering from early losses"]
    factor1s = ["interest rate decisions", "inflation concerns", "economic data", "earnings season", "geopolitical events"]
    factor2s = ["currency movements", "commodity price shifts", "investor sentiment", "technical factors", "liquidity conditions"]
    
    # Create mock news for each index
    for index_symbol in indices_list:
        index_name = indices_names.get(index_symbol, index_symbol)
        
        # Create 2-3 news items per index
        for _ in range(random.randint(2, 3)):
            template = random.choice(news_templates)
            sentiment = template["sentiment"]
            
            # Ensure direction matches sentiment for first template
            if "direction" in template["title"]:
                direction = random.choice([d for d in directions if (d in positive_directions) == (sentiment == "positive")])
                value = random.choice(values)
                factor = random.choice(factors)
                impact = random.choice([i for i in impacts if (i in ["boost", "lift", "support"]) == (sentiment == "positive")])
                timeframe = random.choice(timeframes)
                future = random.choice(futures)
                
                title = template["title"].format(index=index_name, direction=direction, value=value, factor=factor, impact=impact)
                summary = template["summary"].format(index=index_name, direction=direction, value=value, 
                                                    timeframe=timeframe, factor=factor, future=future)
            
            # For sector-led template
            elif "sector" in template["title"]:
                sector = random.choice(sectors)
                movement = random.choice([m for m in movements if (m in ["higher", "gains", "advances", "rally"]) == (sentiment == "positive")])
                news_event = random.choice(news_events)
                
                title = template["title"].format(sector=sector, index=index_name, movement=movement)
                summary = template["summary"].format(sector=sector, index=index_name, movement=movement, news_event=news_event)
            
            # For economic data template
            elif "economic data" in template["title"]:
                trade = random.choice(trades)
                surprise = random.choice(surprises)
                compared = random.choice(compareds)
                trade_action = random.choice(trade_actions)
                outlook = random.choice(outlooks)
                
                title = template["title"].format(index=index_name, trades=trade, surprises=surprise)
                summary = template["summary"].format(compared=compared, index=index_name, trade_action=trade_action, outlook=outlook)
            
            # For market report template
            else:
                close = random.choice(closes)
                condition = random.choice(conditions)
                volatility = random.choice(volatilitys)
                closing = random.choice(closings)
                factor1 = random.choice(factor1s)
                factor2 = random.choice(factor2s)
                
                title = template["title"].format(index=index_name, closes=close, condition=condition)
                summary = template["summary"].format(volatility=volatility, index=index_name, closing=closing, 
                                                    factor1=factor1, factor2=factor2)
            
            # Create timestamp (randomly distributed over the last 24 hours)
            hours_ago = random.randint(0, 23)
            minutes_ago = random.randint(0, 59)
            timestamp = current_time - timedelta(hours=hours_ago, minutes=minutes_ago)
            
            # Set a score based on sentiment
            if sentiment == "positive":
                score = random.uniform(0.2, 0.8)
            elif sentiment == "negative":
                score = random.uniform(-0.8, -0.2)
            else:
                score = random.uniform(-0.2, 0.2)
            
            # Create the news item
            news_item = {
                "title": title,
                "summary": summary,
                "source": random.choice(["Yahoo Finance", "Market Watch", "Bloomberg", "CNBC", "Financial Times", "Reuters"]),
                "timestamp": timestamp,
                "unix_timestamp": int(timestamp.timestamp()),
                "currency": index_name,
                "currency_pairs": {index_name},
                "sentiment": sentiment,
                "score": score,
                "url": f"https://example.com/mock-news/{index_symbol.replace('^', '')}/{int(timestamp.timestamp())}"
            }
            
            mock_news.append(news_item)
    
    # Add some general market news
    for _ in range(5):
        is_positive = random.random() > 0.5
        sentiment = "positive" if is_positive else "negative"
        
        templates = [
            "Global markets {direction} as investors weigh {factor1} against {factor2}",
            "Markets {move} {timeframe} amid {condition} and {event}",
            "Investors {action} stocks as {indicator} {performance}"
        ]
        
        template = random.choice(templates)
        
        if "direction" in template:
            direction = random.choice(["rise", "advance", "climb higher"]) if is_positive else random.choice(["fall", "retreat", "move lower"])
            factor1 = random.choice(factors)
            factor2 = random.choice([f for f in factors if f != factor1])
            title = template.format(direction=direction, factor1=factor1, factor2=factor2)
            
        elif "move" in template:
            move = random.choice(["gain", "rally", "advance"]) if is_positive else random.choice(["decline", "fall", "retreat"])
            timeframe = random.choice(["today", "in early trading", "across the board"])
            condition = random.choice(conditions)
            event = random.choice(news_events)
            title = template.format(move=move, timeframe=timeframe, condition=condition, event=event)
            
        else:
            action = random.choice(["buy", "favor", "embrace"]) if is_positive else random.choice(["sell", "avoid", "reduce exposure to"])
            indicator = random.choice(["economic data", "corporate earnings", "central bank comments", "technical indicators"])
            performance = random.choice(["surpasses expectations", "shows improving trends", "indicates growth"]) if is_positive else random.choice(["disappoints", "suggests weakness", "indicates slowdown"])
            title = template.format(action=action, indicator=indicator, performance=performance)
        
        # Create summary
        summary_templates = [
            "Investors are closely monitoring developments in {area1} and {area2} as markets continue to {trend}.",
            "Analysts point to {factor} as a key driver of market sentiment, with {outlook} for the coming {period}.",
            "Trading volumes {volume} as {participants} {activity}, with particular focus on {sector} stocks."
        ]
        
        summary_template = random.choice(summary_templates)
        
        if "area" in summary_template:
            area1 = random.choice(["monetary policy", "fiscal spending", "corporate earnings", "international trade", "supply chains"])
            area2 = random.choice(["inflation expectations", "growth forecasts", "interest rate paths", "geopolitical tensions", "commodity markets"])
            trend = random.choice(["show resilience", "seek direction", "adjust to new data", "price in future expectations", "respond to mixed signals"])
            summary = summary_template.format(area1=area1, area2=area2, trend=trend)
            
        elif "factor" in summary_template:
            factor = random.choice(["recent economic data", "central bank communication", "earnings surprises", "global risk sentiment", "technical positioning"])
            outlook = random.choice(["cautious expectations", "optimistic forecasts", "mixed projections", "revised estimates", "continued uncertainty"])
            period = random.choice(["weeks", "months", "quarter", "reporting season", "economic cycle"])
            summary = summary_template.format(factor=factor, outlook=outlook, period=period)
            
        else:
            volume = random.choice(["increased", "remained elevated", "were mixed", "fell below average", "reflected caution"])
            participants = random.choice(["institutional investors", "retail traders", "hedge funds", "foreign investors", "market makers"])
            activity = random.choice(["repositioned portfolios", "adjusted exposure", "evaluated opportunities", "reassessed risks", "took profits"])
            sector = random.choice(sectors)
            summary = summary_template.format(volume=volume, participants=participants, activity=activity, sector=sector)
        
        # Create timestamp
        hours_ago = random.randint(0, 12)
        minutes_ago = random.randint(0, 59)
        timestamp = current_time - timedelta(hours=hours_ago, minutes=minutes_ago)
        
        # Set a score based on sentiment
        if sentiment == "positive":
            score = random.uniform(0.2, 0.8)
        elif sentiment == "negative":
            score = random.uniform(-0.8, -0.2)
        else:
            score = random.uniform(-0.2, 0.2)
        
        # Create the news item for general market
        news_item = {
            "title": title,
            "summary": summary,
            "source": random.choice(["Yahoo Finance", "Market Watch", "Bloomberg", "CNBC", "Financial Times", "Reuters"]),
            "timestamp": timestamp,
            "unix_timestamp": int(timestamp.timestamp()),
            "currency": "Market",  # Use Market as the currency for general market news
            "currency_pairs": {"Market"},
            "sentiment": sentiment,
            "score": score,
            "url": f"https://example.com/mock-news/market/{int(timestamp.timestamp())}"
        }
        
        mock_news.append(news_item)
    
    # Sort by timestamp, newest first
    mock_news.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return mock_news


def filter_news_by_market_type(news_items, subscription_pairs, market_type):
    """
    Filter news items based on market type and subscriptions.
    Ensures strict separation between FX, Crypto, and Indices news.
    
    Args:
        news_items: List of news item dictionaries
        subscription_pairs: Set of subscribed currency pairs
        market_type: Current market type ('FX', 'Crypto', or 'Indices')
    
    Returns:
        List of filtered news items
    """
    filtered_news = []
    
    # Define market-specific currencies
    fx_currencies = {'EUR', 'USD', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'CNY', 'NZD', 
                    'HKD', 'INR', 'SGD', 'NOK', 'SEK', 'MXN', 'ZAR', 'TRY', 'XAG'}
    
    crypto_currencies = {'BTC', 'ETH', 'XRP', 'SOL', 'BNB', 'ADA', 'DOGE', 'DOT', 
                         'AVAX', 'LINK', 'LTC', 'UNI', 'XLM', 'MATIC', 'ATOM', 
                         'USDT', 'USDC', 'BUSD'}
    
    indices_symbols = {'^DJI', '^GSPC', '^IXIC', '^FTSE', '^GDAXI', '^FCHI', '^N225'}
    indices_names = {'Dow Jones', 'S&P 500', 'NASDAQ', 'FTSE 100', 'DAX', 'CAC 40', 'Nikkei 225'}

    subscription_pairs_upper = {pair.upper() for pair in subscription_pairs}

    for item in news_items:
        # Convert currency to uppercase for comparison
        currency = item.get('currency', '').upper() if isinstance(item.get('currency', ''), str) else ''
        
        # Make sure currency_pairs is case-insensitive too
        currency_pairs = set()
        for pair in item.get('currency_pairs', set()):
            if isinstance(pair, str):
                currency_pairs.add(pair.upper())
            else:
                currency_pairs.add(pair)
        
        # Skip items if they don't match market type
        if market_type == 'FX':
            # Skip crypto news in FX mode
            if currency in crypto_currencies or any(curr in crypto_currencies for curr in currency_pairs):
                continue
            # Skip indices news in FX mode
            if (currency in indices_symbols or currency in indices_names or 
                any(idx in indices_symbols or idx in indices_names for idx in currency_pairs)):
                continue
        
        elif market_type == 'Crypto':
            # Only include crypto-related news
            if not (currency in crypto_currencies or 
                   any(curr in crypto_currencies for pair in currency_pairs for curr in pair.split('/') if '/' in pair)):
                # Allow general market news
                if currency != "Market" and "Market" not in currency_pairs:
                    continue
        
        elif market_type == 'Indices':
            # Only include indices-related news
            if not (currency in indices_symbols or currency in indices_names or
                   any(idx in indices_symbols or idx in indices_names for idx in currency_pairs)):
                # Allow general market news
                if currency != "Market" and "Market" not in currency_pairs:
                    continue
        
        # Now filter by subscriptions
        include_item = False
        
        # Include if currency matches any subscription
        if currency in subscription_pairs:
            include_item = True
        # Include if any currency pair matches
        elif any(pair in subscription_pairs for pair in currency_pairs):
            include_item = True
        # Include market news
        elif currency == "Market" or "Market" in currency_pairs:
            include_item = True
            
        if include_item:
            filtered_news.append(item)
    
    return filtered_news