"""
Sidebar UI components for the FX Pulsar application.
Contains functions for creating and managing the sidebar UI.
"""
import streamlit as st
from typing import Dict, List, Any, Callable
from datetime import datetime
import gc
from fx_news.utils.notifications import add_notification
from fx_news.data.session import switch_market_type
from fx_news.services.rates_service import update_rates
from fx_news.services.sentiment_service import update_all_sentiment_data
from fx_news.config.settings import (
    default_fx_pairs, default_crypto_pairs, default_indices,
    fx_currencies, crypto_currencies, indices
)

def create_sidebar():
    """Create the sidebar UI for the FX Monitor page."""
    with st.sidebar:
        # Add some space
        st.markdown("---")
        create_navigation_section()
        create_market_selection_section()
        create_subscription_management_section()
        create_display_controls_section()
        create_refresh_controls_section()
        create_memory_saving_section()
        # To DO: add as a function !!
        if st.sidebar.button("Debug News Session State"):
            st.sidebar.write({
            'fx_news': len(st.session_state.get('fx_news', [])),
            'cached_news': len(st.session_state.get('cached_news', [])),
            'market_type': st.session_state.get('market_type', 'Unknown'),
            'last_fx_news_fetch': st.session_state.get('last_fx_news_fetch')
        })
        create_notification_section()
        

def create_navigation_section():
    """Create the navigation section in the sidebar."""
    st.subheader("Navigation")
    
    # Button to navigate to News Summarizer
    if st.button("📰 Go to News Summarizer", use_container_width=True):
        st.switch_page("pages/2_News_Summarizer.py")
    
    # Button to return to home
    if st.button("🏠 Return to Home", use_container_width=True):
        st.switch_page("Home.py")
        
    # Button to navigate to Sentiment Dashboard
    if st.button("👥 Go to Sentiment Dashboard", use_container_width=True):
        st.switch_page("pages/3_Trader_Sentiment.py")

def create_market_selection_section():
    """Create the market selection section in the sidebar."""
    st.header("Market Selection")
     
    # Create toggle buttons for market selection
    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)

    with col1:
        fx_button = st.button(
            "FX Market", 
            key="fx_toggle",
            help="Switch to Foreign Exchange market pairs",
            use_container_width=True
        )

    with col2:
        crypto_button = st.button(
            "Crypto Market", 
            key="crypto_toggle",
            help="Switch to Cryptocurrency market pairs",
            use_container_width=True
        )

    with col3:
        indices_button = st.button(
            "Indices", 
            key="indices_toggle",
            help="Switch to Stock Indices",
            use_container_width=True
        )
    
    # Show current market selection
    current_market = st.session_state.market_type
    
    # Create a styled indicator for the current market
    if current_market == 'FX':
        st.markdown(
            """
            <div style="display: flex; justify-content: center; margin-bottom: 15px;">
                <div style="background-color: #1E88E5; color: white; padding: 5px 15px; 
                border-radius: 20px; font-weight: bold;">
                    🌐 FX Market Mode
                </div>
            </div>
            """, 
            unsafe_allow_html=True
        )
    elif current_market == 'Crypto':
        st.markdown(
            """
            <div style="display: flex; justify-content: center; margin-bottom: 15px;">
                <div style="background-color: #9C27B0; color: white; padding: 5px 15px; 
                border-radius: 20px; font-weight: bold;">
                    ₿ Crypto Market Mode
                </div>
            </div>
            """, 
            unsafe_allow_html=True
        )
    elif current_market == 'Indices':
        st.markdown(
            """
            <div style="display: flex; justify-content: center; margin-bottom: 15px;">
                <div style="background-color: #FF9800; color: white; padding: 5px 15px; 
                border-radius: 20px; font-weight: bold;">
                    📈 Indices Mode
                </div>
            </div>
            """, 
            unsafe_allow_html=True
        )
    
    # Add a separator
    st.markdown("<hr>", unsafe_allow_html=True)
    
    # Handle market switching logic
    if fx_button and current_market != 'FX':
        switch_market_type('FX')
        st.rerun()

    if crypto_button and current_market != 'Crypto':
        switch_market_type('Crypto')
        st.rerun()

    if indices_button and current_market != 'Indices':
        switch_market_type('Indices')
        st.rerun()

def create_subscription_management_section():
    """Create the subscription management section in the sidebar."""
    # Subscription management
    st.header("Currency Subscriptions")

    # Determine available currencies based on market type
    if st.session_state.market_type == 'FX':
        available_currencies = fx_currencies
    elif st.session_state.market_type == 'Crypto':
        available_currencies = crypto_currencies
    else:  # Indices
        available_currencies = indices

    # Add new subscription form
    st.subheader("Add New Subscription")
    with st.form("add_subscription"):
        base_curr = st.selectbox("Base Currency", options=list(available_currencies.keys()))
        quote_curr = st.selectbox("Quote Currency",
                                options=[c for c in available_currencies.keys() if c != base_curr])
        threshold = st.slider("Alert Threshold (%)", min_value=0.1, max_value=5.0, value=0.5, step=0.1)

        submitted = st.form_submit_button("Add Subscription")
        if submitted:
            # Check if subscription already exists
            exists = any(sub["base"] == base_curr and sub["quote"] == quote_curr
                        for sub in st.session_state.subscriptions)

            if exists:
                add_notification(f"Subscription {base_curr}/{quote_curr} already exists", "error")
            else:
                st.session_state.subscriptions.append({
                    "base": base_curr,
                    "quote": quote_curr,
                    "threshold": threshold,
                    "last_rate": None,
                    "current_rate": None
                })
                add_notification(f"Added subscription: {base_curr}/{quote_curr}", "system")
                # Trigger an immediate update
                update_rates()

def create_display_controls_section():
    """Create the display controls section in the sidebar."""
    st.header("Display Controls")
    
    # Add a collapse all button
    if st.button("Collapse All Currency Cards"):
        # Set a session state variable to indicate all cards should be collapsed
        st.session_state.collapse_all_cards = True
        add_notification("All currency cards collapsed", "info")
        st.rerun()
    
    # Add an expand all button too for convenience
    if st.button("Expand All Currency Cards"):
        # Set a session state variable to indicate all cards should be expanded
        st.session_state.collapse_all_cards = False
        add_notification("All currency cards expanded", "info")
        st.rerun()
    
    # Auto refresh toggle
    auto_refresh = st.checkbox(
        "Auto-refresh (Rates: 15s, News: 5min)", 
        value=st.session_state.auto_refresh,
        help="Enable automatic refreshing of data"
    )
    
    if auto_refresh != st.session_state.auto_refresh:
        st.session_state.auto_refresh = auto_refresh
        # This will force the page to reload with the new auto_refresh setting
        st.rerun()
    
    # Background sentiment analysis toggle
    st.checkbox(
        "Run background sentiment analysis", 
        key="run_background_sentiment",
        value=True,
        help="Enable to analyze sentiment in the background (may slow down the app)"
    )
    
    # Show last refresh times if auto-refresh is enabled
    if st.session_state.auto_refresh:
        st.markdown("---")
        st.subheader("Last Update Times")
        
        if 'last_auto_refresh_time' in st.session_state and st.session_state.last_auto_refresh_time:
            st.caption(f"Last rates refresh: {st.session_state.last_auto_refresh_time.strftime('%H:%M:%S')}")
        
        if 'last_news_auto_refresh_time' in st.session_state and st.session_state.last_news_auto_refresh_time:
            st.caption(f"Last news refresh: {st.session_state.last_news_auto_refresh_time.strftime('%H:%M:%S')}")
            
        if 'last_calendar_auto_refresh_time' in st.session_state and st.session_state.last_calendar_auto_refresh_time:
            st.caption(f"Last calendar refresh: {st.session_state.last_calendar_auto_refresh_time.strftime('%H:%M:%S')}")
            
        if 'last_sentiment_auto_refresh_time' in st.session_state and st.session_state.last_sentiment_auto_refresh_time:
            st.caption(f"Last sentiment refresh: {st.session_state.last_sentiment_auto_refresh_time.strftime('%H:%M:%S')}")

def create_memory_saving_section():
    
    st.header("Performance Settings")
    memory_saving = st.toggle("Memory-Saving Mode", 
                        value=st.session_state.memory_saving_mode,
                        help="Reduces memory usage but may affect responsiveness")

    if memory_saving != st.session_state.memory_saving_mode:
        st.session_state.memory_saving_mode = memory_saving
        if memory_saving:
            st.session_state.news_max_days_old = 3  # More aggressive limit
            gc.collect()  # Force garbage collection
            add_notification("Memory-saving mode enabled", "system")
        else:
            st.session_state.news_max_days_old = 5  # Default limit
            add_notification("Memory-saving mode disabled", "system")

def create_refresh_controls_section():
    """Create the refresh controls section in the sidebar."""
    st.header("Manual Refreshes")
    
    # Create buttons for refreshing specific data
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📅 Refresh Calendar", use_container_width=True):
            from fx_news.services.events_service import fetch_all_economic_events
            fetch_all_economic_events(force=True)
            add_notification("Economic calendar refreshed", "success")

        if st.button("👥 Refresh Sentiment", use_container_width=True):
            update_all_sentiment_data(force=True)
            add_notification("Trader sentiment refreshed", "success")
    
    with col2:    
        # Manual rates refresh button
        if st.button("🔄 Refresh Rates", use_container_width=True):
            update_rates()
            add_notification("Currency rates refreshed", "success")

        # Manual news refresh button
        if st.button("📰 Refresh News", use_container_width=True):
            st.session_state.refresh_news_clicked = True
            add_notification("News refresh initiated", "info")
            st.rerun()
    
    # Combined refresh button
    if st.button("🔄📰 Refresh All Data", use_container_width=True):
        # Update rates
        update_rates()
        
        # Schedule news refresh
        st.session_state.refresh_news_clicked = True
        
        # Refresh economic calendar
        from fx_news.services.events_service import fetch_all_economic_events
        fetch_all_economic_events(force=True)
        
        # Refresh sentiment data
        update_all_sentiment_data(force=True)
        
        add_notification("Full data refresh initiated", "success")
        st.rerun()

def create_notification_section():
    """Create the notification section in the sidebar."""
    st.header("Notifications")

    if st.button("Clear All Notifications"):
        st.session_state.notifications = []
        add_notification("Notifications cleared", "system")

    for notification in st.session_state.notifications:
        timestamp = notification["timestamp"].strftime("%H:%M:%S")

        # Determine color based on notification type
        if notification['type'] == 'price':
            color = "orange"
            emoji = "💰"
        elif notification['type'] == 'error':
            color = "red"
            emoji = "❌"
        elif notification['type'] == 'info':
            color = "blue"
            emoji = "ℹ️"
        elif notification['type'] == 'success':
            color = "green"
            emoji = "✅"
        else:  # system
            color = "gray"
            emoji = "🔔"

        # Create a custom notification element
        st.markdown(
            f"""<div style="padding:8px; margin-bottom:8px; border-left:4px solid {color}; background-color:#f8f9fa;">
                <div>{emoji} <strong>{notification['message']}</strong></div>
                <div style="font-size:0.8em; color:#6c757d;">{timestamp}</div>
            </div>""",
            unsafe_allow_html=True
        )

def handle_sidebar_inputs():
    """Process all sidebar inputs and update state accordingly."""
    # This function would be called after rendering the sidebar
    # to handle any state changes that require a page rerun
    
    # Check market switching buttons
    current_market = st.session_state.market_type
    
    # For FX button in session state
    if st.session_state.get('fx_toggle', False) and current_market != 'FX':
        switch_market_type('FX')
        st.rerun()
    
    # For Crypto button in session state
    if st.session_state.get('crypto_toggle', False) and current_market != 'Crypto':
        switch_market_type('Crypto')
        st.rerun()
    
    # For Indices button in session state
    if st.session_state.get('indices_toggle', False) and current_market != 'Indices':
        switch_market_type('Indices')
        st.rerun()
        
    # Check auto-refresh toggle
    if 'auto_refresh' in st.session_state and st.session_state.auto_refresh != st.session_state.get('auto_refresh_toggle', True):
        st.session_state.auto_refresh = st.session_state.get('auto_refresh_toggle', True)
        st.rerun()