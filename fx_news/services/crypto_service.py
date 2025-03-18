"""
Crypto service for fetching and processing cryptocurrency data.
Handles cryptocurrency rates, events, and related functionality.
"""
import logging
import json
import random
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import requests
import streamlit as st

from fx_news.data.models import CryptoEvent
from fx_news.utils.notifications import add_notification
from fx_news.scrapers.coinmarketcap_scraper import fetch_crypto_events, create_mock_crypto_events

logger = logging.getLogger("crypto_service")


def fetch_all_crypto_events(force=False):
    """
    Fetch all crypto events and cache them in the session state
    
    Args:
        force: If True, forces a refresh regardless of cache
    """
    # Check if we need to refresh events
    if force:
        should_refresh = True
    else:
        # Only refresh if the cache has expired or it's the first time fetching
        last_fetch = st.session_state.get('crypto_events_last_fetch', None)
        if last_fetch is None or (datetime.now() - last_fetch).total_seconds() > 3 * 3600:  # 3 hours
            should_refresh = True
        else:
            should_refresh = False

    if should_refresh:
        with st.spinner("Fetching crypto calendar..."):
            logger.info("Fetching crypto calendar")
            debug_log = []
            events_json_str = fetch_crypto_events(days=7, use_mock_fallback=True, debug_log=debug_log)
            
            # Parse the JSON string into a Python list
            try:
                events = json.loads(events_json_str)
            except json.JSONDecodeError:
                st.warning("Failed to parse crypto events data.")
                events = []

            if events:
                # Filter only valid events
                valid_events = [event for event in events if is_valid_event(event)]
                    
                if valid_events:
                    # Save to session state
                    st.session_state.crypto_events = valid_events
                    st.session_state.crypto_events_last_fetch = datetime.now()

                    # Notify user
                    add_notification(f"Crypto calendar updated with {len(valid_events)} valid events", "success")
                else:
                    st.warning("No valid events found")
                    st.session_state.crypto_events = []
            else:
                st.warning("Could not fetch crypto events")
                st.session_state.crypto_events = []
    
    # Return the cached or fetched valid events
    return st.session_state.get('crypto_events', [])

def is_valid_event(event):
    """
    Validate if the event has the necessary structure and data.
    
    Args:
        event: Event dictionary to validate
    
    Returns:
        bool: True if event is valid, False otherwise
    """
    # Required keys for a valid event
    required_keys = ['title', 'description', 'type', 'coin', 'date', 'url']
    
    if not isinstance(event, dict):
        return False
    
    # Check if all required keys are present
    for key in required_keys:
        if key not in event:
            return False
    
    # Additional checks for date format
    if event.get('date'):
        try:
            # Check if the date is a valid date string
            datetime.strptime(event['date'], '%Y-%m-%d')
        except ValueError:
            return False
    
    return True