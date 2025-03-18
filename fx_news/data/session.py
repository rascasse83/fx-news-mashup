import streamlit as st
from datetime import datetime, timedelta
import logging

from fx_news.config.settings import default_fx_pairs, default_crypto_pairs, default_indices
from fx_news.services.news_service import fetch_news, fetch_indices_news
from fx_news.utils.notifications import add_notification

logger = logging.getLogger("session_state")

def initialize_session_state():
    """Initialize all session state variables"""
    
    # Initialize market type if not already set
    if 'market_type' not in st.session_state:
        st.session_state.market_type = 'FX'  # Default to FX market

    # Initialize indices subscriptions
    if 'indices_subscriptions' not in st.session_state:
        st.session_state.indices_subscriptions = default_indices

    # Initialize indices news-related state
    if 'indices_news' not in st.session_state:
        st.session_state.indices_news = []

    if 'last_indices_news_fetch' not in st.session_state:
        st.session_state.last_indices_news_fetch = None

    if 'next_indices_news_refresh_time' not in st.session_state:
        st.session_state.next_indices_news_refresh_time = datetime.now() + timedelta(seconds=300)  # 5 minutes
    
    # Initialize session state for core variables with default values
    session_defaults = {
        'subscriptions': default_fx_pairs if st.session_state.get('market_type', 'FX') == 'FX' else default_crypto_pairs,
        'notifications': [],
        'last_refresh': None,
        'last_news_fetch': None, 
        'cached_news': [],
        'rate_history': {},
        'debug_log': True,
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
    }
    
    # Only set the value if the key doesn't exist in session state
    for key, default_value in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

    # Initialize historical rate cache
    if 'historical_rate_cache' not in st.session_state:
        st.session_state.historical_rate_cache = {}

    # Initialize sentiment data
    if 'fxbook_sentiment_data' not in st.session_state:
        st.session_state.fxbook_sentiment_data = None

    if 'fxbook_sentiment_last_fetch' not in st.session_state:
        st.session_state.fxbook_sentiment_last_fetch = None

    # Initialize news refresh state
    if 'next_news_refresh_time' not in st.session_state:
        st.session_state.next_news_refresh_time = datetime.now() + timedelta(seconds=300)  # 5 minutes from now

    if 'refresh_news_clicked' not in st.session_state:
        st.session_state.refresh_news_clicked = False

    if 'initial_news_loaded' not in st.session_state:
        st.session_state.initial_news_loaded = False

    # Initialize economic events
    if 'economic_events' not in st.session_state:
        st.session_state.economic_events = None

    if 'economic_events_last_fetch' not in st.session_state:
        st.session_state.economic_events_last_fetch = None

    # Initialize UI refresh key
    if 'ui_refresh_key' not in st.session_state:
        st.session_state.ui_refresh_key = 0

    # Initialize crypto events
    if 'crypto_events' not in st.session_state:
        st.session_state.crypto_events = None

    if 'crypto_events_last_fetch' not in st.session_state:
        st.session_state.crypto_events_last_fetch = None

def ensure_initial_news_loaded():
    """Ensure news are loaded from disk on first page load"""
    if not st.session_state.initial_news_loaded:
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
                    news_items = fetch_indices_news(indices_list, use_mock_fallback=True)
                    if news_items:
                        st.session_state.indices_news = news_items
                        st.session_state.last_indices_news_fetch = datetime.now()
                        add_notification(f"Loaded {len(news_items)} news items from disk", "success")
        else:
            # For FX or Crypto
            news_cache_key = 'fx_news' if st.session_state.market_type == 'FX' else 'crypto_news'
            last_fetch_key = 'last_fx_news_fetch' if st.session_state.market_type == 'FX' else 'last_crypto_news_fetch'
            
            # Check if we have any cached news already
            if not st.session_state.get(news_cache_key):
                with st.spinner("Loading news from disk..."):
                    # The fetch_news function should load from disk first
                    news_items = fetch_news(currencies, use_mock_fallback=True)
                    if news_items:
                        st.session_state[news_cache_key] = news_items
                        st.session_state[last_fetch_key] = datetime.now()
                        add_notification(f"Loaded {len(news_items)} news items from disk", "success")
        
        # Mark that we've done the initial load
        st.session_state.initial_news_loaded = True


def switch_market_type(new_market_type):
    """
    Switch the application to a different market type with clean state transition.
    
    Args:
        new_market_type: The market type to switch to ('FX', 'Crypto', or 'Indices')
    """
    import logging
    from fx_news.data.currencies import get_available_currencies
    from fx_news.services.rates_service import update_rates
    
    logger = logging.getLogger(__name__)
    
    current_market_type = st.session_state.market_type
    
    # Only proceed if we're actually changing market types
    if current_market_type == new_market_type:
        return
    
    # Log the switch for debugging
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
            st.session_state.subscriptions = default_fx_pairs.copy()
            st.session_state.fx_subscriptions = default_fx_pairs.copy()
    elif new_market_type == 'Crypto':
        if hasattr(st.session_state, 'crypto_subscriptions') and st.session_state.crypto_subscriptions:
            st.session_state.subscriptions = st.session_state.crypto_subscriptions.copy()
        else:
            st.session_state.subscriptions = default_crypto_pairs.copy()
            st.session_state.crypto_subscriptions = default_crypto_pairs.copy()
    else:  # Indices
        if hasattr(st.session_state, 'indices_subscriptions') and st.session_state.indices_subscriptions:
            st.session_state.subscriptions = st.session_state.indices_subscriptions.copy()
        else:
            st.session_state.subscriptions = default_indices.copy()
            st.session_state.indices_subscriptions = default_indices.copy()
    
    # Update available currencies based on the new market type
    st.session_state.available_currencies = get_available_currencies(new_market_type)
    
    # Reset UI-related state
    st.session_state.collapse_all_cards = False
    
    # Force complete UI refresh
    if 'ui_refresh_key' not in st.session_state:
        st.session_state.ui_refresh_key = 0
    st.session_state.ui_refresh_key += 1
    
    # Refresh rates and news for the new market type
    try:
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
        add_notification(f"Error refreshing data after market switch: {str(e)}", "error")
    
    # Notify user
    add_notification(f"Switched to {new_market_type} Market", "system")