"""
Events service for fetching and processing economic calendar events.
Handles economic events data from various sources.
"""
import logging
import random
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import requests
import streamlit as st
from bs4 import BeautifulSoup

from fx_news.data.models import EconomicEvent
from fx_news.utils.notifications import add_notification
from fx_news.scrapers.economic_calendar_scraper import scrape_investing_economic_calendar, create_mock_economic_events, get_economic_events_for_currency
from fx_news.services.crypto_service import fetch_all_crypto_events

logger = logging.getLogger("events_service")


def display_crypto_calendar_for_currency(base, quote, debug_log=None):
    if debug_log is None:
        debug_log = []
    
    if 'crypto_events' not in st.session_state or not st.session_state.crypto_events:
        fetch_all_crypto_events()
    
    if not st.session_state.crypto_events:
        st.info("No crypto events data available. Please try refreshing the calendar.")
        return
    
    unique_id_2 = f"{base}_{quote}_{random.randint(1000, 9999)}"
    
    base_events = [event for event in st.session_state.crypto_events if base.upper() in event['coin'].upper()]
    
    tab1, tab2 = st.tabs([f"{base} Events", "All Crypto Events"])
    
    with tab1:
        if base_events:
            display_crypto_events(base_events)
        else:
            st.info(f"No upcoming events found for {base}")
    
    with tab2:
        display_crypto_events(st.session_state.crypto_events)
    
    if st.button(f"Refresh Crypto Calendar", key=f"refresh_crypto_calendar_{unique_id_2}"):
        fetch_all_crypto_events(force=True)
        st.rerun()

def display_crypto_events(events, highlight_coins=None):
    if not events:
        st.info("No crypto events to display")
        return

    event_types = set(event['type'] for event in events)
    
    for event_type in event_types:
        filtered_events = [e for e in events if e['type'] == event_type]
        st.markdown(f"### {event_type} Events")
        for event in filtered_events:
            render_crypto_event_card(event, highlight_coins)


def render_crypto_event_card(event, highlight_coins=None):
    highlight = highlight_coins and any(coin.upper() in event['coin'].upper() for coin in highlight_coins)

    bg_color = "#1E1E1E" if highlight else "#121212"
    border_color = "#4CAF50" if highlight else "#333333"

    type_color = {  
        "Release": "#4CAF50",
        "AMA": "#9C27B0",
        "Airdrop": "#FF9800",
        "Partnership": "#2196F3",
        "Tokenomics": "#F44336"
    }.get(event.get('type'), "#1E88E5")
    
    date_str = event.get('date', '')
    if date_str:
        try:
            date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
            date_str = date_obj.strftime('%a, %b %d')
        except:
            pass

    card_html = f"""
    <div style="background-color:{bg_color}; border-left:4px solid {border_color}; padding:15px; margin-bottom:15px; border-radius:5px;">
        <div style="display:flex; align-items:center; margin-bottom:10px;">
            <span style="font-weight:bold; color:white;">{event.get('coin', '')}</span>
            <div style="margin-left:auto; background-color:{type_color}; color:white; padding:3px 8px; border-radius:12px; font-size:0.8rem;">
                {event.get('type', 'Event')}
            </div>
        </div>
        <div>
            <a href="{event.get('url', '#')}" target="_blank" style="color:white; text-decoration:none; font-weight:bold; font-size:1.1rem;">
                {event.get('title', 'Event')} 🔗
            </a>
            <p style="color:#CCCCCC; margin-top:5px; margin-bottom:10px; font-size:0.9rem;">
                {event.get('description', '')}
            </p>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div style="color:#999; font-size:0.8rem;">
                {date_str}
            </div>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

def display_economic_calendar_for_currency_pair(base, quote, debug_log=None):
    """
    Display economic calendar for a currency pair in a tab interface,
    or crypto events for crypto pairs
    
    Args:
        base: Base currency code (e.g. 'EUR' or 'BTC')
        quote: Quote currency code (e.g. 'USD' or 'ETH')
        debug_log: Optional list to append debug information
    """
    if debug_log is None:
        debug_log = []
    
    unique_id_1 = f"{base}_{quote}_{random.randint(1000, 9999)}"

    # Check if we're in crypto mode
    if st.session_state.market_type == 'Crypto':
        # For crypto pairs, show the crypto calendar
        display_crypto_calendar_for_currency(base, quote, debug_log)
        return
    
    # For FX mode, use the existing economic calendar logic
    # Get the cached economic events or fetch them if not available
    if 'economic_events' not in st.session_state or st.session_state.economic_events is None:
        fetch_all_economic_events()
    
    if 'economic_events' not in st.session_state or not st.session_state.economic_events:
        st.info("No economic events data available. Please try refreshing the calendar.")
        return
    
    # Filter events for the base and quote currencies
    base_events = get_economic_events_for_currency(base, st.session_state.economic_events)
    quote_events = get_economic_events_for_currency(quote, st.session_state.economic_events)

    
    # Create tabs for base, quote, and all events (removed sentiment tab)
    tab1, tab2, tab3 = st.tabs([f"{base} Events", f"{quote} Events", "All Events"])
    
    with tab1:
        if base_events:
            display_economic_events(base_events)
        else:
            st.info(f"No upcoming economic events found for {base}")
    
    with tab2:
        if quote_events:
            display_economic_events(quote_events)
        else:
            st.info(f"No upcoming economic events found for {quote}")
    
    with tab3:
        # For the "All Events" tab, show all events but highlight the ones for this pair
        display_economic_events(st.session_state.economic_events, highlight_currencies=[base, quote])
    
    # Add a refresh button at the bottom
    if st.button(f"Refresh Economic Calendar", key=f"refresh_calendar_{unique_id_1}"):
        fetch_all_economic_events(force=True)
        st.rerun()
    

def display_economic_events(events, highlight_currencies=None):
    """
    Display economic events using a custom table layout built with Streamlit components.
    This approach gives more control over the layout and allows for clickable elements.
    
    Args:
        events: List of economic event dictionaries
        highlight_currencies: Optional list of currencies to highlight
    """
    import pandas as pd
    
    if not events:
        st.info("No economic events to display")
        return
    
    # Sort events by date and time
    sorted_events = sorted(events, 
                          key=lambda x: (x.get('date', ''), x.get('time', '')))
    
    # Group events by date for better organization
    events_by_date = {}
    for event in sorted_events:
        date = event.get('date', 'Unknown Date')
        if date not in events_by_date:
            events_by_date[date] = []
        events_by_date[date].append(event)
    
    # Column proportions and headers
    col_sizes = [1, 1, 1, 3, 1, 1, 1]
    headers = ["Time", "Country", "Importance", "Event", "Actual", "Forecast", "Previous"]
    
    # Custom CSS for more compact styling
    st.markdown("""
    <style>
    .compact-table-row p {
        margin-bottom: 0.1rem !important;
        font-size: 0.9rem !important;
        line-height: 1.1 !important;
    }
    .compact-table-row a {
        color: #0066cc !important;
        text-decoration: none !important;
    }
    .compact-table-row a:hover {
        text-decoration: underline !important;
    }
    .compact-divider {
        margin-top: 0.2rem !important;
        margin-bottom: 0.2rem !important;
    }
    .table-header p {
        font-weight: bold !important;
        color: #444444 !important;
        margin-bottom: 0.3rem !important;
    }
    .event-date {
        font-size: 1.1rem !important;
        margin-top: 0.5rem !important;
        margin-bottom: 0.3rem !important;
        color: #333333 !important;
        font-weight: 600 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Display events grouped by date
    for date, date_events in events_by_date.items():
        # Format date for display
        try:
            formatted_date = pd.to_datetime(date).strftime('%A, %B %d, %Y')
        except:
            formatted_date = date
        
        # Show date header    
        st.markdown(f"<div class='event-date'>{formatted_date}</div>", unsafe_allow_html=True)
        
        # Add the column headers first
        header_cols = st.columns(col_sizes)
        for i, header in enumerate(headers):
            with header_cols[i]:
                st.markdown(f"<div class='table-header'><p>{header}</p></div>", unsafe_allow_html=True)
        
        # Add a divider after the header
        st.markdown("<hr style='margin-top: 0.2rem; margin-bottom: 0.5rem;'>", unsafe_allow_html=True)
        
        # Create a table-like structure using columns for each event
        for event in date_events:
            # Determine if we should highlight this row
            highlight_style = ""
            if highlight_currencies and event.get('impact_currency') in highlight_currencies:
                highlight_style = "background-color: rgba(255, 255, 0, 0.2);"
            
            # Container for each event
            with st.container():
                # Use columns to create a table-like row
                cols = st.columns(col_sizes)
                
                # Add the compact-table-row class to make rows more condensed
                for i, col in enumerate(cols):
                    with col:
                        if i == 0:  # Time
                            st.markdown(f"<div class='compact-table-row' style='{highlight_style}'><p>{event.get('time', '')}</p></div>", unsafe_allow_html=True)
                        elif i == 1:  # Country
                            st.markdown(f"<div class='compact-table-row' style='{highlight_style}'><p>{event.get('country', '')}</p></div>", unsafe_allow_html=True)
                        elif i == 2:  # Importance
                            # Format importance as stars
                            importance = event.get('importance', 0)
                            importance_str = '⭐' * importance if importance else ''
                            st.markdown(f"<div class='compact-table-row' style='{highlight_style}'><p>{importance_str}</p></div>", unsafe_allow_html=True)
                        elif i == 3:  # Event
                            # Format event name with link if URL is available
                            event_name = event.get('event', '')
                            event_url = event.get('event_url', '')
                            
                            if event_url:
                                # Make URLs absolute
                                if not event_url.startswith('http'):
                                    event_url = f"https://www.investing.com{event_url}"
                                
                                st.markdown(f"<div class='compact-table-row' style='{highlight_style}'><p><a href='{event_url}' target='_blank'>{event_name}</a></p></div>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<div class='compact-table-row' style='{highlight_style}'><p>{event_name}</p></div>", unsafe_allow_html=True)
                        elif i == 4:  # Actual
                            st.markdown(f"<div class='compact-table-row' style='{highlight_style}'><p>{event.get('actual', '-')}</p></div>", unsafe_allow_html=True)
                        elif i == 5:  # Forecast
                            st.markdown(f"<div class='compact-table-row' style='{highlight_style}'><p>{event.get('forecast', '-')}</p></div>", unsafe_allow_html=True)
                        elif i == 6:  # Previous
                            st.markdown(f"<div class='compact-table-row' style='{highlight_style}'><p>{event.get('previous', '-')}</p></div>", unsafe_allow_html=True)
            
            # Add a thin divider between events (more compact)
            st.markdown("<hr class='compact-divider' style='margin-top: 0.2rem; margin-bottom: 0.2rem;'>", unsafe_allow_html=True)



def fetch_all_economic_events(force=False):
    """
    Fetch all economic events and cache them in the session state
    
    Args:
        force: If True, forces a refresh regardless of cache
    
    Returns:
        list: List of economic events
    """
    # Check if we need to refresh events
    should_refresh = force
    
    if 'economic_events_last_fetch' not in st.session_state:
        st.session_state.economic_events_last_fetch = None
        should_refresh = True
    
    if not should_refresh and st.session_state.economic_events_last_fetch:
        # Refresh every 6 hours
        time_since_last_fetch = (datetime.now() - st.session_state.economic_events_last_fetch).total_seconds()
        if time_since_last_fetch > 6 * 3600:  # 6 hours in seconds
            should_refresh = True
    
    if should_refresh:
        with st.spinner("Fetching economic calendar..."):
            # Try to fetch real data
            debug_log = []
            events = scrape_investing_economic_calendar(days=7, debug_log=debug_log)
            
            # Fall back to mock data if needed
            if not events:
                st.info("Using sample economic calendar data")
                events = create_mock_economic_events()
            
            st.session_state.economic_events = events
            st.session_state.economic_events_last_fetch = datetime.now()
            
            # Notify user
            add_notification(f"Economic calendar updated with {len(events)} events", "success")
            return events
    
    return st.session_state.economic_events

