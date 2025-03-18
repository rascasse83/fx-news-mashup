"""
Helper functions used throughout the application.
Various utility functions that don't fit into more specific modules.
"""
import random
from typing import List, Dict, Any, Tuple, Set, Optional
from datetime import datetime, timedelta
import streamlit as st

def ensure_initial_news_loaded():
    """
    Ensure news are loaded from disk on first page load.
    Sets up initial news data for the current market type.
    """
    if not st.session_state.get("initial_news_loaded", False):
        # Get currencies from subscriptions
        currencies = list(set([sub["base"] for sub in st.session_state.subscriptions] + 
                         [sub["quote"] for sub in st.session_state.subscriptions]))
        
        # Load news from disk based on market type
        if st.session_state.market_type == 'Indices':
            indices_list = [sub["base"] for sub in st.session_state.subscriptions]
            # Check if we have any cached news already
            if not st.session_state.get('indices_news'):
                with st.spinner("Loading news from disk..."):
                    # This should try to load from disk first
                    from fx_news.services.news_service import fetch_news
                    news_items = fetch_news(currencies, use_mock_fallback=True)
                    if news_items:
                        st.session_state.indices_news = news_items
                        st.session_state.last_indices_news_fetch = datetime.now()
                        from fx_news.utils.notifications import add_notification
                        add_notification(f"Loaded {len(news_items)} news items from disk", "success")
        else:
            # For FX or Crypto
            news_cache_key = 'fx_news' if st.session_state.market_type == 'FX' else 'crypto_news'
            last_fetch_key = 'last_fx_news_fetch' if st.session_state.market_type == 'FX' else 'last_crypto_news_fetch'
            
            # Check if we have any cached news already
            if not st.session_state.get(news_cache_key):
                with st.spinner("Loading news from disk..."):
                    # The fetch_news function should load from disk first
                    from fx_news.services.news_service import fetch_news
                    news_items = fetch_news(currencies, use_mock_fallback=True)
                    if news_items:
                        st.session_state[news_cache_key] = news_items
                        st.session_state[last_fetch_key] = datetime.now()
                        from fx_news.utils.notifications import add_notification
                        add_notification(f"Loaded {len(news_items)} news items from disk", "success")
        
        # Mark that we've done the initial load
        st.session_state.initial_news_loaded = True


def switch_market_type(new_market_type):
    """
    Switch the application to a different market type with clean state transition.
    
    Args:
        new_market_type: The market type to switch to ('FX', 'Crypto', or 'Indices')
    """
    current_market_type = st.session_state.market_type
    
    # Only proceed if we're actually changing market types
    if current_market_type == new_market_type:
        return
    
    # Log the switch for debugging
    import logging
    logger = logging.getLogger("market_switcher")
    logger.info(f"Switching market type from {current_market_type} to {new_market_type}")
    
    # Save current subscriptions to the appropriate market-specific variable
    if current_market_type == 'FX':
        st.session_state.fx_subscriptions = st.session_state.subscriptions.copy()
    elif current_market_type == 'Crypto':
        st.session_state.crypto_subscriptions = st.session_state.subscriptions.copy()
    else:  # Indices
        st.session_state.indices_subscriptions = st.session_state.subscriptions.copy()
    
    # Update market type
    st.session_state.market_type = new_market_type
    
    # Load the appropriate subscriptions for the new market type
    if new_market_type == 'FX':
        if hasattr(st.session_state, 'fx_subscriptions') and st.session_state.fx_subscriptions:
            st.session_state.subscriptions = st.session_state.fx_subscriptions.copy()
        else:
            from fx_news.config.settings import default_fx_pairs
            st.session_state.subscriptions = default_fx_pairs.copy()
            st.session_state.fx_subscriptions = default_fx_pairs.copy()
    elif new_market_type == 'Crypto':
        if hasattr(st.session_state, 'crypto_subscriptions') and st.session_state.crypto_subscriptions:
            st.session_state.subscriptions = st.session_state.crypto_subscriptions.copy()
        else:
            from fx_news.config.settings import default_crypto_pairs
            st.session_state.subscriptions = default_crypto_pairs.copy()
            st.session_state.crypto_subscriptions = default_crypto_pairs.copy()
    else:  # Indices
        if hasattr(st.session_state, 'indices_subscriptions') and st.session_state.indices_subscriptions:
            st.session_state.subscriptions = st.session_state.indices_subscriptions.copy()
        else:
            from fx_news.config.settings import default_indices
            st.session_state.subscriptions = default_indices.copy()
            st.session_state.indices_subscriptions = default_indices.copy()
    
    # Update available currencies based on the new market type
    # (This would be done in the UI where the global variable is accessible)
    
    # Reset UI-related state
    st.session_state.collapse_all_cards = False
    
    # Force complete UI refresh
    if 'ui_refresh_key' not in st.session_state:
        st.session_state.ui_refresh_key = 0
    st.session_state.ui_refresh_key += 1
    
    # Refresh rates for the new market type
    try:
        from fx_news.services.rates_service import update_rates
        update_rates()  # Update rates for new subscriptions
        
        # Reset cache keys for the new market type
        if new_market_type == 'FX':
            st.session_state.next_fx_news_refresh_time = datetime.now()
        elif new_market_type == 'Crypto':
            st.session_state.next_crypto_news_refresh_time = datetime.now()
        else:  # Indices
            st.session_state.next_indices_news_refresh_time = datetime.now()
            
        # Force cached_news to be based on the current market type
        if new_market_type == 'FX' and 'fx_news' in st.session_state:
            st.session_state.cached_news = st.session_state.fx_news
        elif new_market_type == 'Crypto' and 'crypto_news' in st.session_state:
            st.session_state.cached_news = st.session_state.crypto_news
        elif new_market_type == 'Indices' and 'indices_news' in st.session_state:
            st.session_state.cached_news = st.session_state.indices_news
        else:
            # If no news is available for the new market type, clear the cache
            st.session_state.cached_news = []
            
        # Mark that we need a fresh news fetch
        st.session_state.refresh_news_clicked = True
    except Exception as e:
        logger.error(f"Error during market switch: {str(e)}")
        from fx_news.utils.notifications import add_notification
        add_notification(f"Error refreshing data after market switch: {str(e)}", "error")
    
    # Notify user
    from fx_news.utils.notifications import add_notification
    add_notification(f"Switched to {new_market_type} Market", "system")


def calculate_percentage_variation(subscriptions):
    """
    Calculate percentage variation for currency pairs.
    Used for visualizing changes on maps and charts.
    
    Args:
        subscriptions: List of subscription dictionaries
        
    Returns:
        list: List of variation dictionaries
    """
    variations = []
    for sub in subscriptions:
        # Check if current_rate exists
        if sub["current_rate"] is not None:
            # Determine the previous rate to use for comparison
            previous_rate = None
            if sub.get("previous_close") is not None:
                previous_rate = sub["previous_close"]
            elif sub.get("last_rate") is not None:
                previous_rate = sub["last_rate"]
                
            # Only calculate variation if we have a valid previous rate
            if previous_rate is not None:
                percent_change = ((sub["current_rate"] - previous_rate) / previous_rate) * 100
                variations.append({
                    "currency_pair": f"{sub['base']}/{sub['quote']}",
                    "base": sub["base"],
                    "quote": sub["quote"],
                    "variation": percent_change
                })
    return variations


def prepare_map_data(variations, currency_to_country):
    """
    Prepare data for the geographic map visualization.
    
    Args:
        variations: List of variation dictionaries
        currency_to_country: Dictionary mapping currencies to countries
        
    Returns:
        list: List of map data dictionaries
    """
    map_data = []
    
    # Create a dictionary to store aggregated variations by country
    country_variations = {}
    
    for variation in variations:
        # Process base currency locations
        base_locations = currency_to_country.get(variation["base"], [])
        # Ensure we have a list of locations even if it's a single country
        if not isinstance(base_locations, list):
            base_locations = [base_locations]
            
        # Add locations for base currency
        for location in base_locations:
            if location not in country_variations:
                country_variations[location] = []
            country_variations[location].append(variation["variation"])
        
        # Also process quote currency locations (with inverted variation)
        quote_locations = currency_to_country.get(variation["quote"], [])
        # Ensure we have a list of locations even if it's a single country
        if not isinstance(quote_locations, list):
            quote_locations = [quote_locations]
            
        # Add locations for quote currency (with inverted variation)
        for location in quote_locations:
            if location not in country_variations:
                country_variations[location] = []
            # Invert the variation for quote currency
            country_variations[location].append(-variation["variation"])
    
    # Create the final map data by averaging the variations for each country
    for location, variations_list in country_variations.items():
        if variations_list:
            avg_variation = sum(variations_list) / len(variations_list)
            map_data.append({
                "location": location,
                "variation": avg_variation
            })
    
    return map_data


def initialize_session_state():
    """Initialize the session state with default values if not already set."""
    from fx_news.config.settings import (
        default_fx_pairs, default_crypto_pairs, default_indices
    )
    
    # Initial default market type
    if 'market_type' not in st.session_state:
        st.session_state.market_type = 'FX'  # Default to FX market
    
    # Initialize indices subscriptions
    if 'indices_subscriptions' not in st.session_state:
        st.session_state.indices_subscriptions = default_indices
    
    # Initialize indices news cache
    if 'indices_news' not in st.session_state:
        st.session_state.indices_news = []
    
    # Initialize indices news fetch timestamp
    if 'last_indices_news_fetch' not in st.session_state:
        st.session_state.last_indices_news_fetch = None
    
    # Initialize next indices news refresh time
    if 'next_indices_news_refresh_time' not in st.session_state:
        st.session_state.next_indices_news_refresh_time = datetime.now() + timedelta(seconds=300)
    
    # Initialize subscriptions based on market type
    if 'subscriptions' not in st.session_state:
        if st.session_state.market_type == 'FX':
            st.session_state.subscriptions = default_fx_pairs.copy()
        elif st.session_state.market_type == 'Crypto':
            st.session_state.subscriptions = default_crypto_pairs.copy()
        else:  # Indices
            st.session_state.subscriptions = default_indices.copy()
    
    # Initialize other session state variables
    for key, default_value in {
        'notifications': [],
        'last_refresh': None,
        'last_news_fetch': None, 
        'cached_news': [],
        'rate_history': {},
        'debug_log': [],
        'show_debug': False,
        'add_variations': False,
        'auto_refresh': True,
        'fx_news': [],
        'crypto_news': [],
        'last_fx_news_fetch': None,
        'last_crypto_news_fetch': None,
        'last_auto_refresh_time': datetime.now(),
        'fx_subscriptions': default_fx_pairs,  # Store FX subscriptions separately
        'crypto_subscriptions': default_crypto_pairs,  # Store crypto subscriptions separately
        'collapse_all_cards': False,  # Default to collapsed cards
        'historical_rate_cache': {},
        'refresh_news_clicked': False,
        'initial_news_loaded': False,
        'economic_events': None,
        'economic_events_last_fetch': None,
        'fxbook_sentiment_data': None,
        'fxbook_sentiment_last_fetch': None,
        'next_news_refresh_time': datetime.now() + timedelta(seconds=300),
        'crypto_events': None,
        'crypto_events_last_fetch': None,
        'ui_refresh_key': 0,
    }.items():
        # Only set the value if the key doesn't exist in session state
        if key not in st.session_state:
            st.session_state[key] = default_value