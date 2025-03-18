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
from fx_news.scrapers.news_scraper import scrape_yahoo_finance_news, create_mock_news, analyze_news_sentiment, load_news_from_files
from fx_news.data.models import NewsItem
from fx_news.utils.notifications import add_notification

logger = logging.getLogger(__name__)

def refresh_news_callback():
    """
    Callback function for refreshing news.
    Triggered when the user clicks the refresh news button.
    Saves existing news, forces a refresh, and triggers a page rerun.
    """
    # Set the refresh flag
    st.session_state.refresh_news_clicked = True
    
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
    
    # Log the refresh action
    logger.info(f"Manual news refresh requested for {st.session_state.market_type} market")
    
    # IMPORTANT: Save the existing news instead of clearing it
    if news_cache_key in st.session_state and st.session_state[news_cache_key]:
        existing_news = st.session_state[news_cache_key].copy()
        st.session_state[f"{news_cache_key}_temp"] = existing_news
        logger.info(f"Saved {len(existing_news)} existing news items to temp storage")
    
    # Reset the fetch timestamp to force a refresh
    st.session_state[last_fetch_key] = None
    
    # Set the next refresh time to now
    st.session_state[next_refresh_key] = datetime.now()
    
    # Increment UI refresh key to ensure complete UI update
    if 'ui_refresh_key' in st.session_state:
        st.session_state.ui_refresh_key += 1
    
    # Add notification
    add_notification(f"Refreshing {st.session_state.market_type} news...", "info")
    
    # Force a refresh
    st.rerun()
    
def fetch_news(currencies: List[str] = None, use_mock_fallback: bool = True, force: bool = False) -> List[NewsItem]:
    """
    Fetch news for currency pairs, with prioritization of local disk cache.
    
    Args:
        currencies: List of currency codes to fetch news for
        use_mock_fallback: Whether to use mock data if real data can't be fetched
        force: Whether to force a refresh regardless of cache
        
    Returns:
        List of NewsItem objects
    """
    # Check if we need to refresh at all
    if not force and 'last_news_fetch' in st.session_state and st.session_state.last_news_fetch:
        # Don't refresh if it's been less than 60 seconds since last refresh
        seconds_since_refresh = (datetime.now() - st.session_state.last_news_fetch).total_seconds()
        if seconds_since_refresh < 60:
            if 'cached_news' in st.session_state:
                return st.session_state.cached_news
            
    if 'subscriptions' not in st.session_state:
        return []

    # For indices, we want to use just the base (not currency pairs)
    if st.session_state.market_type == 'Indices':
        # Get list of indices
        currency_pairs = [(sub["base"], sub["quote"]) for sub in st.session_state.subscriptions]
    else:
        # Regular currency pairs for FX and Crypto
        currency_pairs = list(set((sub["base"], sub["quote"]) for sub in st.session_state.subscriptions))

    if not currency_pairs:
        return []

    # Initialize debug log
    if 'debug_log' not in st.session_state or not isinstance(st.session_state.debug_log, list):
        st.session_state.debug_log = []
        
    # Force a reset of disk_news_loaded flag when explicitly requested
    if force and 'disk_news_loaded' in st.session_state:
        st.session_state.disk_news_loaded = False
        
    # First check if we have news on disk to display immediately
    show_disk_news = ('disk_news_loaded' not in st.session_state or 
                      not st.session_state.disk_news_loaded or 
                      force)
    
    # Store any previously cached news to avoid losing items
    existing_cached_news = []
    if 'cached_news' in st.session_state and st.session_state.cached_news:
        existing_cached_news = st.session_state.cached_news.copy()
    
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
    
    # Also retrieve market-specific cached news if available
    market_cached_news = []
    if news_cache_key in st.session_state and st.session_state[news_cache_key]:
        market_cached_news = st.session_state[news_cache_key].copy()
    
    if show_disk_news:
        # Convert the currency_pairs format before passing to load_news_from_files
        # load_news_from_files expects a symbol string, not a list of tuples
        formatted_pairs = []
        for base, quote in currency_pairs:
            # For indices, just use the base symbol
            if st.session_state.market_type == 'Indices':
                if base.startswith('^'):
                    # Special handling for indices
                    formatted_pairs.append(base.replace('^', ''))
                else:
                    formatted_pairs.append(base)
            else:
                # For regular FX or crypto, format as base_quote
                formatted_pairs.append(f"{base}_{quote}")
        
        # Try to load news from disk
        disk_news = []
        for pair in formatted_pairs:
            pair_news = load_news_from_files(pair)
            disk_news.extend(pair_news)
        # disk_news = load_news_from_files(formatted_pairs)
        
        if disk_news and len(disk_news) > 0:
            # Always use disk news on first load, regardless of pair coverage
            st.success(f"Found {len(disk_news)} news articles on disk. Displaying these while fetching latest news.")
            
            # Merge with existing cached news to avoid losing items
            all_news = []
            seen_ids = set()
            
            # Add existing cached news first (both general and market-specific)
            for news_sources in [existing_cached_news, market_cached_news]:
                for item in news_sources:
                    item_id = None
                    if item.get('url'):
                        item_id = item.get('url')
                    elif item.get('unix_timestamp'):
                        item_id = f"{item.get('unix_timestamp')}_{item.get('title', '')}"
                    else:
                        item_id = item.get('title', '')
                        
                    if item_id and item_id not in seen_ids:
                        all_news.append(item)
                        seen_ids.add(item_id)
            
            # Then add disk news, avoiding duplicates
            for item in disk_news:
                item_id = None
                if item.get('url'):
                    item_id = item.get('url')
                elif item.get('unix_timestamp'):
                    item_id = f"{item.get('unix_timestamp')}_{item.get('title', '')}"
                else:
                    item_id = item.get('title', '')
                    
                if item_id and item_id not in seen_ids:
                    all_news.append(item)
                    seen_ids.add(item_id)
            
            # Sort by timestamp (newest first)
            all_news.sort(key=lambda x: x.get('timestamp', datetime.now()), reverse=True)
            
            # Tag news by market type
            tagged_news = tag_news_by_market_type(all_news)
            
            # Separate news based on market type
            fx_news = [item for item in tagged_news if item.get('is_fx', False)]
            crypto_news = [item for item in tagged_news if item.get('is_crypto', False)]
            indices_news = [item for item in tagged_news if item.get('is_indices', False)]
            market_news = [item for item in tagged_news if 
                          item.get('is_market', False) or
                          not (item.get('is_fx', False) or 
                               item.get('is_crypto', False) or 
                               item.get('is_indices', False))]
            
            # Add market news to all categories
            for market_item in market_news:
                if market_item not in fx_news:
                    fx_news.append(market_item)
                if market_item not in crypto_news:
                    crypto_news.append(market_item)
                if market_item not in indices_news:
                    indices_news.append(market_item)
            
            # Store in appropriate caches
            st.session_state.fx_news = sorted(fx_news, key=lambda x: x.get('timestamp', datetime.now()), reverse=True)
            st.session_state.crypto_news = sorted(crypto_news, key=lambda x: x.get('timestamp', datetime.now()), reverse=True)
            st.session_state.indices_news = sorted(indices_news, key=lambda x: x.get('timestamp', datetime.now()), reverse=True)
            
            # Update timestamps
            st.session_state.last_fx_news_fetch = datetime.now()
            st.session_state.last_crypto_news_fetch = datetime.now()
            st.session_state.last_indices_news_fetch = datetime.now()
            
            # Set cached_news based on current market type
            if market_type == 'FX':
                st.session_state.cached_news = st.session_state.fx_news
            elif market_type == 'Crypto':
                st.session_state.cached_news = st.session_state.crypto_news
            else:  # Indices
                st.session_state.cached_news = st.session_state.indices_news
            
            st.session_state.disk_news_loaded = True
            
            # Schedule a background refresh for new news after a delay
            st.session_state.last_news_fetch = datetime.now() - timedelta(seconds=50)  # Set to refresh soon
            st.session_state.next_news_refresh_time = datetime.now() + timedelta(seconds=5)
            
            # Return the appropriate news for the current market type
            if market_type == 'FX':
                return st.session_state.fx_news
            elif market_type == 'Crypto':
                return st.session_state.crypto_news
            else:  # Indices
                return st.session_state.indices_news

    st.session_state.debug_log.append(f"Attempting to fetch news for {len(currency_pairs)} currency pairs")

    try:
        with st.spinner("Fetching latest news from Yahoo Finance..."):
            all_news = []
            for base, quote in currency_pairs:
                try:
                    news_items = scrape_yahoo_finance_news(
                        [(base, quote)], 
                        debug_log=st.session_state.debug_log,
                        analyze_sentiment_now=False  # Set to False for faster scraping
                    )
                    
                    for item in news_items:
                        item["currency_pairs"] = {f"{base}/{quote}"}
                        
                        # Ensure all news items have default sentiment values
                        if 'sentiment' not in item:
                            item['sentiment'] = 'neutral'
                        if 'score' not in item:
                            item['score'] = 0.0
                            
                        all_news.append(item)
                except Exception as e:
                    st.session_state.debug_log.append(f"Error fetching news for {base}/{quote}: {str(e)}")
                    # Continue with other pairs

            # Process the news results
            if all_news:
                # Deduplicate by URL or title
                unique_news = {}
                for item in all_news:
                    key = item.get('url', '') if item.get('url') else item.get('title', '')
                    if key:
                        if key in unique_news:
                            # Merge currency pairs for duplicate items
                            unique_news[key]['currency_pairs'].update(item['currency_pairs'])
                        else:
                            unique_news[key] = item

                deduplicated_news = list(unique_news.values())
                
                # Merge with existing cached news
                merged_news = merge_news(deduplicated_news, existing_cached_news, market_cached_news)
                
                # Tag and process the news
                processed_news = process_news(merged_news)
                
                # Add notification and update session state
                add_notification(f"Successfully fetched and merged news items, total: {len(processed_news['all_news'])}", "success")
                st.session_state.last_news_fetch = datetime.now()
                
                # Return the appropriate news for the current market type
                if market_type == 'FX':
                    return processed_news['fx_news']
                elif market_type == 'Crypto':
                    return processed_news['crypto_news']
                else:  # Indices
                    return processed_news['indices_news']
                    
            else:
                if isinstance(st.session_state.debug_log, list):
                    st.session_state.debug_log.append("No news items found from Yahoo Finance")
    except Exception as e:
        if isinstance(st.session_state.debug_log, list):
            st.session_state.debug_log.append(f"Error fetching news from Yahoo Finance: {str(e)}")
        add_notification(f"Error fetching news from Yahoo Finance: {str(e)}", "error")

    # If we got here, return whatever news we might have for the current market type
    if market_type == 'FX' and 'fx_news' in st.session_state and st.session_state.fx_news:
        return st.session_state.fx_news
    elif market_type == 'Crypto' and 'crypto_news' in st.session_state and st.session_state.crypto_news:
        return st.session_state.crypto_news
    elif market_type == 'Indices' and 'indices_news' in st.session_state and st.session_state.indices_news:
        return st.session_state.indices_news
    elif 'cached_news' in st.session_state and st.session_state.cached_news:
        return st.session_state.cached_news
    
    # As a last resort, use mock news
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

    return []

def merge_news(new_items, existing_news, market_cached_news):
    """Merge news items from different sources, avoiding duplicates."""
    merged_news = []
    seen_ids = set()
    
    # Add existing cached news first (both general and market-specific)
    for news_sources in [existing_news, market_cached_news]:
        for item in news_sources:
            item_id = None
            if item.get('url'):
                item_id = item.get('url')
            elif item.get('unix_timestamp'):
                item_id = f"{item.get('unix_timestamp')}_{item.get('title', '')}"
            else:
                item_id = item.get('title', '')
                
            if item_id and item_id not in seen_ids:
                merged_news.append(item)
                seen_ids.add(item_id)
    
    # Then add new items, avoiding duplicates
    for item in new_items:
        item_id = None
        if item.get('url'):
            item_id = item.get('url')
        elif item.get('unix_timestamp'):
            item_id = f"{item.get('unix_timestamp')}_{item.get('title', '')}"
        else:
            item_id = item.get('title', '')
            
        if item_id and item_id not in seen_ids:
            merged_news.append(item)
            seen_ids.add(item_id)
    
    # Sort by timestamp (newest first)
    merged_news.sort(key=lambda x: x.get('timestamp', datetime.now()), reverse=True)
    
    return merged_news

def process_news(news_items):
    """Process and categorize news items by market type."""
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
    
    # Add market news to all categories
    for market_item in market_news:
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
        'market_news': market_news
    }

def tag_news_by_market_type(news_items):
    """
    Tags news items with appropriate market type flags.
    This helps with filtering later.
    
    Args:
        news_items: List of news item dictionaries
    
    Returns:
        List of news items with market_type tags
    """
    if not news_items:
        return []
    
    # Define market-specific currencies and terms
    fx_currencies = {'EUR', 'USD', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'CNY', 'NZD', 
                    'HKD', 'INR', 'SGD', 'NOK', 'SEK', 'MXN', 'ZAR', 'TRY', 'XAG'}
    
    crypto_currencies = {'BTC', 'ETH', 'XRP', 'SOL', 'BNB', 'ADA', 'DOGE', 'DOT', 
                         'AVAX', 'LINK', 'LTC', 'UNI', 'XLM', 'MATIC', 'ATOM', 
                         'USDT', 'USDC', 'BUSD'}
    
    crypto_terms = {'BITCOIN', 'ETHEREUM', 'CRYPTOCURRENCY', 'BLOCKCHAIN', 'CRYPTO', 
                   'TOKEN', 'ALTCOIN', 'DEFI', 'NFT', 'MINING', 'WALLET'}
    
    indices_symbols = {'^DJI', '^GSPC', '^IXIC', '^FTSE', '^GDAXI', '^FCHI', '^N225'}
    indices_names = {'DOW JONES', 'S&P 500', 'NASDAQ', 'FTSE 100', 'DAX', 'CAC 40', 'NIKKEI 225'}
    indices_terms = {'INDEX', 'STOCK MARKET', 'SHARES', 'EQUITY', 'WALL STREET', 'NYSE', 'NASDAQ'}
    
    fx_terms = {'FOREX', 'FX MARKET', 'CURRENCY PAIR', 'EXCHANGE RATE', 'CENTRAL BANK', 
               'INTEREST RATE', 'MONETARY POLICY', 'DOLLAR', 'EURO', 'POUND', 'YEN'}
    
    for item in news_items:
        # Get currency and title/summary for classification
        currency = item.get('currency', '')
        if isinstance(currency, str):
            currency = currency.upper()
        else:
            currency = ""
            
        title = item.get('title', '').upper()
        summary = item.get('summary', '').upper()
        
        # Get currency pairs
        currency_pairs = item.get('currency_pairs', set())
        if not isinstance(currency_pairs, set):
            currency_pairs = set()
            
        # Extract all mentioned currencies from title and summary
        all_text = f"{title} {summary}"
        
        # Initialize market types flags as False
        item['is_fx'] = False
        item['is_crypto'] = False
        item['is_indices'] = False
        item['is_market'] = False
        
        # Check for crypto indicators
        crypto_currency_mentioned = (
            currency in crypto_currencies or
            any(c in all_text for c in crypto_currencies)
        )
        
        crypto_term_mentioned = any(term in all_text for term in crypto_terms)
        
        # Check for indices indicators
        indices_symbol_mentioned = (
            currency in indices_symbols or 
            any(sym in all_text for sym in indices_symbols)
        )
        
        indices_name_mentioned = (
            currency in indices_names or
            any(name in all_text for name in indices_names)
        )
        
        indices_term_mentioned = any(term in all_text for term in indices_terms)
        
        # Check for FX indicators
        fx_currency_mentioned = (
            currency in fx_currencies or 
            any(c in all_text for c in fx_currencies)
        )
        
        fx_term_mentioned = any(term in all_text for term in fx_terms)
        
        # Check currency pairs for additional clues
        has_crypto_pair = False
        has_fx_pair = False
        has_indices_pair = False
        
        for pair in currency_pairs:
            pair_str = str(pair).upper()
            
            # Check if pair contains crypto currency
            if any(c in pair_str for c in crypto_currencies):
                has_crypto_pair = True
                
            # Check if pair contains indices symbol or name
            if any(sym in pair_str for sym in indices_symbols) or any(name in pair_str for name in indices_names):
                has_indices_pair = True
                
            # Check if pair contains FX currency and not crypto
            if any(c in pair_str for c in fx_currencies) and not has_crypto_pair:
                has_fx_pair = True
        
        # Assign market types based on indicators, with crypto taking precedence over FX
        # since FX currencies can be part of crypto pairs (e.g., BTC/USD)
        
        # Tag as crypto if:
        # - Has clear crypto mentions or pairs
        # - Has crypto terms
        if crypto_currency_mentioned or has_crypto_pair or crypto_term_mentioned:
            item['is_crypto'] = True
            
        # Tag as indices if:
        # - Has clear indices mentions or pairs
        # - Has indices terms
        elif indices_symbol_mentioned or indices_name_mentioned or has_indices_pair or indices_term_mentioned:
            item['is_indices'] = True
            
        # Tag as FX if:
        # - Has clear FX mentions or pairs
        # - Has FX terms
        # - Is not already tagged as crypto or indices
        elif (fx_currency_mentioned or has_fx_pair or fx_term_mentioned) and not (item['is_crypto'] or item['is_indices']):
            item['is_fx'] = True
            
        # If still not categorized, mark as general market news
        if not (item['is_fx'] or item['is_crypto'] or item['is_indices']):
            item['is_market'] = True
            
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
            news_items = scrape_indices_news(indices_list, debug_log=st.session_state.debug_log)
            
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
    
    for item in news_items:
        currency = item.get('currency', '')
        currency_pairs = item.get('currency_pairs', set()) if isinstance(item.get('currency_pairs'), set) else set()
        
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