import streamlit as st
import logging
from datetime import datetime

# Import from our modules
from fx_news.config.settings import configure_page, setup_logging
from fx_news.config.styles import load_styles
from fx_news.data.session import initialize_session_state, ensure_initial_news_loaded, switch_market_type
from fx_news.data.currencies import get_available_currencies
from fx_news.services.rates_service import update_rates, setup_auto_refresh, calculate_market_volatility, calculate_percentage_variation
from fx_news.services.events_service import fetch_all_economic_events
from fx_news.services.news_service import fetch_news, refresh_news_callback
from fx_news.services.sentiment_service import update_all_sentiment_data
from fx_news.utils.notifications import add_notification
from fx_news.ui.components.cards import display_currency_pair
from fx_news.ui.components.charts import display_volatility_index
from fx_news.ui.components.maps import display_indices_world_map, display_indices_visualization, display_crypto_market_visualization
from fx_news.ui.components.news import display_news_sidebar
from fx_news.ui.layout import create_layout
from fx_news.ui.components.sidebar import create_sidebar

# Set up logging
logger = logging.getLogger("Market Monitor page")

# Configure page and load styles
configure_page()
load_styles()

# Initialize the session state
initialize_session_state()

# Ensure news data is loaded initially
ensure_initial_news_loaded()

# Set up auto-refresh
setup_auto_refresh()

# Main layout creation
def main():
    # Calculate volatility indices
    volatility_index, pair_volatility = calculate_market_volatility(st.session_state.subscriptions)
    
    # Create the main layout
    create_layout(volatility_index, pair_volatility)
    
    # Add sidebar
    create_sidebar()
    
    # Load the economic calendar on app start if needed
    if 'economic_events' not in st.session_state or st.session_state.economic_events is None:
        with st.spinner("Updating economic calendar..."):
            fetch_all_economic_events(force=True)
            st.rerun()

    # Update currency rates if needed
    if st.session_state.last_refresh is None: 
        with st.spinner("Updating currency rates..."):
            update_rates()

# # Create sidebar with all controls and navigation
# def create_sidebar():
#     with st.sidebar:
#         # Add some space
#         st.markdown("---")
#         st.subheader("Navigation")
        
#         # Button to navigate to News Summarizer
#         if st.button("📰 Go to News Summarizer", use_container_width=True):
#             st.switch_page("pages/2_News_Summarizer.py")
        
#         # Button to return to home
#         if st.button("🏠 Return to Home", use_container_width=True):
#             st.switch_page("Home.py")
            
#         st.header("Market Selection")
         
#         # Create toggle buttons for market selection
#         col1, col2 = st.columns(2)
#         col3, col4 = st.columns(2)

#         with col1:
#             fx_button = st.button(
#                 "FX Market", 
#                 key="fx_toggle",
#                 help="Switch to Foreign Exchange market pairs",
#                 use_container_width=True
#             )

#         with col2:
#             crypto_button = st.button(
#                 "Crypto Market", 
#                 key="crypto_toggle",
#                 help="Switch to Cryptocurrency market pairs",
#                 use_container_width=True
#             )

#         with col3:
#             indices_button = st.button(
#                 "Indices", 
#                 key="indices_toggle",
#                 help="Switch to Stock Indices",
#                 use_container_width=True
#             )
        
#         # Show current market selection
#         current_market = st.session_state.market_type
        
#         # Create a styled indicator for the current market
#         if current_market == 'FX':
#             st.markdown(
#                 """
#                 <div style="display: flex; justify-content: center; margin-bottom: 15px;">
#                     <div style="background-color: #1E88E5; color: white; padding: 5px 15px; 
#                     border-radius: 20px; font-weight: bold;">
#                         🌐 FX Market Mode
#                     </div>
#                 </div>
#                 """, 
#                 unsafe_allow_html=True
#             )
#         elif current_market == 'Crypto':
#             st.markdown(
#                 """
#                 <div style="display: flex; justify-content: center; margin-bottom: 15px;">
#                     <div style="background-color: #9C27B0; color: white; padding: 5px 15px; 
#                     border-radius: 20px; font-weight: bold;">
#                         ₿ Crypto Market Mode
#                     </div>
#                 </div>
#                 """, 
#                 unsafe_allow_html=True
#             )
#         elif current_market == 'Indices':
#             st.markdown(
#                 """
#                 <div style="display: flex; justify-content: center; margin-bottom: 15px;">
#                     <div style="background-color: #FF9800; color: white; padding: 5px 15px; 
#                     border-radius: 20px; font-weight: bold;">
#                         📈 Indices Mode
#                     </div>
#                 </div>
#                 """, 
#                 unsafe_allow_html=True
#             )
#         # Add a separator
#         st.markdown("<hr>", unsafe_allow_html=True)
        
#         # Handle market switching logic
#         if fx_button:
#             switch_market_type('FX')
#             st.rerun()

#         if crypto_button:
#             switch_market_type('Crypto')
#             st.rerun()

#         if indices_button:
#             switch_market_type('Indices')
#             st.rerun()

#         # Button to go to Sentiment Dashboard
#         if st.button("👥 Go to Sentiment Dashboard", use_container_width=True):
#             st.switch_page("pages/3_Trader_Sentiment.py")

#         # Subscription management
#         st.header("Currency Subscriptions")

#         # Add new subscription form
#         st.subheader("Add New Subscription")
#         with st.form("add_subscription"):
#             # Get available currencies based on current market type
#             available_currencies = get_available_currencies(st.session_state.market_type)
            
#             base_curr = st.selectbox("Base Currency", options=list(available_currencies.keys()))
#             quote_curr = st.selectbox("Quote Currency",
#                                     options=[c for c in available_currencies.keys() if c != base_curr])
#             threshold = st.slider("Alert Threshold (%)", min_value=0.1, max_value=5.0, value=0.5, step=0.1)

#             submitted = st.form_submit_button("Add Subscription")
#             if submitted:
#                 # Check if subscription already exists
#                 exists = any(sub["base"] == base_curr and sub["quote"] == quote_curr
#                             for sub in st.session_state.subscriptions)

#                 if exists:
#                     add_notification(f"Subscription {base_curr}/{quote_curr} already exists", "error")
#                 else:
#                     st.session_state.subscriptions.append({
#                         "base": base_curr,
#                         "quote": quote_curr,
#                         "threshold": threshold,
#                         "last_rate": None,
#                         "current_rate": None
#                     })
#                     add_notification(f"Added subscription: {base_curr}/{quote_curr}", "system")
#                     # Trigger an immediate update
#                     update_rates()

#         st.header("Display Controls")
        
#         # Add a collapse all button
#         if st.button("Collapse All Currency Cards"):
#             # Set a session state variable to indicate all cards should be collapsed
#             st.session_state.collapse_all_cards = True
#             add_notification("All currency cards collapsed", "info")
#             st.rerun()
        
#         # Add an expand all button too for convenience
#         if st.button("Expand All Currency Cards"):
#             # Set a session state variable to indicate all cards should be expanded
#             st.session_state.collapse_all_cards = False
#             add_notification("All currency cards expanded", "info")
#             st.rerun()   
        
#         st.header("Manual Refreshes Calendar")
#         if st.button("📅 Refresh Economic Calendar"):
#             fetch_all_economic_events(force=True)
#             add_notification("Economic calendar refreshed", "success")

#         # Manual refresh button
#         st.button("🔄 Refresh Rates", on_click=update_rates)
#         st.button("📰 Refresh News", on_click=refresh_news_callback)
#         st.button("🔄📰 Refresh Both", on_click=lambda: (update_rates(), refresh_news_callback()))

#         st.sidebar.button("👥 Refresh Sentiment", on_click=lambda: update_all_sentiment_data(force=True))

#         st.sidebar.checkbox("Run background sentiment analysis", 
#                         key="run_background_sentiment",
#                         value=True,
#                         help="Enable to analyze sentiment in the background (may slow down the app)")

#         # Then in your sidebar, for the auto-refresh toggle:
#         auto_refresh = st.sidebar.checkbox("Auto-refresh (Rates: 15s, News: 5min)", value=st.session_state.auto_refresh)
#         if auto_refresh != st.session_state.auto_refresh:
#             st.session_state.auto_refresh = auto_refresh
#             # This will force the page to reload with the new auto_refresh setting
#             st.rerun()

#         # In your sidebar, show the last refresh times (optional)
#         if st.session_state.auto_refresh:
#             if 'last_auto_refresh_time' in st.session_state and st.session_state.last_auto_refresh_time:
#                 st.sidebar.caption(f"Last rates refresh: {st.session_state.last_auto_refresh_time.strftime('%H:%M:%S')}")
            
#             if 'last_news_auto_refresh_time' in st.session_state and st.session_state.last_news_auto_refresh_time:
#                 st.sidebar.caption(f"Last news refresh: {st.session_state.last_news_auto_refresh_time.strftime('%H:%M:%S')}")

#         # Show notification history
#         st.header("Notifications")

#         if st.button("Clear All Notifications"):
#             st.session_state.notifications = []

#         for notification in st.session_state.notifications:
#             timestamp = notification["timestamp"].strftime("%H:%M:%S")

#             # Determine color based on notification type
#             if notification['type'] == 'price':
#                 color = "orange"
#                 emoji = "💰"
#             elif notification['type'] == 'error':
#                 color = "red"
#                 emoji = "❌"
#             elif notification['type'] == 'info':
#                 color = "blue"
#                 emoji = "ℹ️"
#             elif notification['type'] == 'success':
#                 color = "green"
#                 emoji = "✅"
#             else:  # system
#                 color = "gray"
#                 emoji = "🔔"

#             # Create a custom notification element
#             st.markdown(
#                 f"""<div style="padding:8px; margin-bottom:8px; border-left:4px solid {color}; background-color:#f8f9fa;">
#                     <div>{emoji} <strong>{notification['message']}</strong></div>
#                     <div style="font-size:0.8em; color:#6c757d;">{timestamp}</div>
#                 </div>""",
#                 unsafe_allow_html=True
#             )

# Run the main application
if __name__ == "__main__":
    main()