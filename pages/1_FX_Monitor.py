import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from textblob import TextBlob
import json
import re
import glob
from bs4 import BeautifulSoup
import os
import random
from fx_news.scrapers.news_scraper import scrape_yahoo_finance_news, create_mock_news, analyze_news_sentiment
from fx_news.apis.rates_fetch import fetch_currency_rates, update_rates_with_variation, get_mock_currency_rates
from fx_news.scrapers.rates_scraper import scrape_yahoo_finance_rates, fetch_historical_rates
from fx_news.scrapers.economic_calendar_scraper import scrape_investing_economic_calendar, create_mock_economic_events, get_economic_events_for_currency
from fx_news.scrapers.coinmarketcap_scraper import fetch_crypto_events
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go
from fx_news.scrapers.myfxbook_scraper import (
    scrape_myfxbook_sentiment_all_pairs, 
    get_sentiment_for_pair,
    load_sentiment_data,
    create_sentiment_tab_ui,
    update_all_sentiment_data
)
# import arrow



# Configure page
st.set_page_config(
    page_title="FX Pulsar - Market Monitor",
    page_icon="https://images.seeklogo.com/logo-png/60/1/lmax-digital-icon-black-logo-png_seeklogo-609777.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* Custom expandable card */
    .currency-card {
        margin-bottom: 10px;
        border: 1px solid #333;
        border-radius: 5px;
        overflow: hidden;
    }
    .card-header {
        background-color: #1E1E1E;
        padding: 10px 15px;
        cursor: pointer;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #333;
    }
    .card-header:hover {
        background-color: #2C2C2C;
    }
    .card-header-left {
        font-weight: bold;
        font-size: 16px;
    }
    .card-header-right {
        display: flex;
        align-items: center;
    }
    .card-change {
        margin-right: 15px;
        font-weight: bold;
    }
    .card-sentiment {
        font-size: 13px;
    }
    .card-content {
        padding: 15px;
        display: none;
    }
    .show-content .card-content {
        display: block;
    }
    .arrow-icon {
        margin-left: 10px;
        transition: transform 0.3s;
    }
    .show-content .arrow-icon {
        transform: rotate(180deg);
    }
    /* Add colors */
    .positive {
        color: #4CAF50;
    }
    .negative {
        color: #F44336;
    }
</style>
""", unsafe_allow_html=True)

default_fx_pairs = [
    {"base": "EUR", "quote": "USD", "threshold": 0.05, "last_rate": None, "current_rate": None},
    {"base": "USD", "quote": "JPY", "threshold": 0.05, "last_rate": None, "current_rate": None},
    {"base": "EUR", "quote": "GBP", "threshold": 0.05, "last_rate": None, "current_rate": None},
    {"base": "AUD", "quote": "USD", "threshold": 0.05, "last_rate": None, "current_rate": None},
    {"base": "USD", "quote": "CAD", "threshold": 0.05, "last_rate": None, "current_rate": None},
    {"base": "USD", "quote": "CHF", "threshold": 0.05, "last_rate": None, "current_rate": None},
    {"base": "CNY", "quote": "USD", "threshold": 0.05, "last_rate": None, "current_rate": None},
    {"base": "USD", "quote": "INR", "threshold": 0.05, "last_rate": None, "current_rate": None},    
]

default_crypto_pairs = [
    {"base": "BTC", "quote": "USD", "threshold": 0.5, "last_rate": None, "current_rate": None},
    {"base": "ETH", "quote": "USD", "threshold": 0.5, "last_rate": None, "current_rate": None},
    {"base": "SOL", "quote": "USD", "threshold": 0.5, "last_rate": None, "current_rate": None},
    {"base": "BNB", "quote": "USD", "threshold": 0.5, "last_rate": None, "current_rate": None},
    {"base": "XRP", "quote": "USD", "threshold": 0.5, "last_rate": None, "current_rate": None},
    {"base": "ETH", "quote": "BTC", "threshold": 0.5, "last_rate": None, "current_rate": None},
]


# FX Currencies
fx_currencies = {
    'EUR': 'Euro',
    'USD': 'US Dollar',
    'GBP': 'British Pound',
    'JPY': 'Japanese Yen',
    'AUD': 'Australian Dollar',
    'CAD': 'Canadian Dollar',
    'CHF': 'Swiss Franc',
    'CNY': 'Chinese Yuan',
    'NZD': 'New Zealand Dollar',
    'HKD': 'Hong Kong Dollar',
    'INR': 'Indian Rupee',
    'SGD': 'Singapore Dollar',
    'NOK': 'Norwegian Krone',
    'SEK': 'Swedish Krona',
    'MXN': 'Mexican Peso',
    'ZAR': 'South African Rand',
    'TRY': 'Turkish Lira',
    'INR': 'Indian Rupee',
    'XAG': 'Silver'
}

# Crypto Currencies
crypto_currencies = {
    'BTC': 'Bitcoin',
    'ETH': 'Ethereum',
    'XRP': 'Ripple',
    'SOL': 'Solana',
    'BNB': 'Binance Coin',
    'ADA': 'Cardano',
    'DOGE': 'Dogecoin',
    'DOT': 'Polkadot',
    'AVAX': 'Avalanche',
    'LINK': 'Chainlink',
    'LTC': 'Litecoin',
    'UNI': 'Uniswap',
    'XLM': 'Stellar',
    'MATIC': 'Polygon',
    'ATOM': 'Cosmos',
    'USDT': 'Tether',
    'USDC': 'USD Coin',
    'BUSD': 'Binance USD'
}

currency_to_country = {
    'EUR': [
        'Austria', 'Belgium', 'Cyprus', 'Estonia', 'Finland', 'France', 'Germany',
        'Greece', 'Ireland', 'Italy', 'Latvia', 'Lithuania', 'Luxembourg', 'Malta',
        'Netherlands', 'Portugal', 'Slovakia', 'Slovenia', 'Spain'
    ],
    'USD': 'United States',
    'GBP': 'United Kingdom',
    'JPY': 'Japan',
    'AUD': 'Australia',
    'CAD': 'Canada',
    'CHF': 'Switzerland',
    'CNY': 'China',
    'INR': 'India',
    'NZD': 'New Zealand',
    'HKD': 'Hong Kong',
    'SGD': 'Singapore',
    'XAG': 'Global'  # Silver is traded globally
}

if 'market_type' not in st.session_state:
    st.session_state.market_type = 'Crypto'  # Default to FX market

# Initialize session state only once
for key, default_value in {
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
    'collapse_all_cards': True,  # Default to collapsed cards
}.items():
    # Only set the value if the key doesn't exist in session state
    if key not in st.session_state:
        st.session_state[key] = default_value

# Initialize session state only once
if 'historical_rate_cache' not in st.session_state:
    st.session_state.historical_rate_cache = {}

# fxbook_sentiment session variables
if 'fxbook_sentiment_data' not in st.session_state:
    st.session_state.fxbook_sentiment_data = None

if 'fxbook_sentiment_last_fetch' not in st.session_state:
    st.session_state.fxbook_sentiment_last_fetch = None

# news refresh
if 'next_news_refresh_time' not in st.session_state:
    st.session_state.next_news_refresh_time = datetime.now() + timedelta(seconds=300)  # 5 minutes from now

# Set up a session state variable to track if we need to refresh
if 'refresh_news_clicked' not in st.session_state:
    st.session_state.refresh_news_clicked = False

# Update the currency mappings based on market type
# This section should come after the session state initialization
if st.session_state.market_type == 'FX':
    available_currencies = fx_currencies
    # Also update the currency to country mapping - may need to modify for Crypto
else:
    available_currencies = crypto_currencies
    # For crypto, we might want to create a special mapping
    # or just use a simpler representation for the map


# Initialize the session state for crypto events if not yet done
if 'crypto_events' not in st.session_state:
    st.session_state.crypto_events = None

if 'crypto_events_last_fetch' not in st.session_state:
    st.session_state.crypto_events_last_fetch = None

# Fetch API key from environment variables
API_KEY = os.getenv("CURRENCY_API_KEY")

def setup_auto_refresh():
    """Setup auto-refresh mechanism using streamlit_autorefresh package"""
    # Only enable auto-refresh if the toggle is on in session state
    if 'auto_refresh' in st.session_state and st.session_state.auto_refresh:
        # Set up the 15-second refresh cycle for rates
        count = st_autorefresh(interval=30000, key="rates_refresher")
        
        # Process refreshes
        current_time = datetime.now()
        
        # Handle rates refresh (every refresh cycle - 15 seconds)
        st.session_state.last_auto_refresh_time = current_time
        update_rates()
        
        # Check if it's time to refresh news (every 20th cycle)
        if count % 20 == 0:
            # Instead of refreshing right away, just schedule the next refresh
            current_time = datetime.now()
            st.session_state.next_news_refresh_time = current_time  # Set to current time to trigger refresh on next run
            add_notification("Scheduled news refresh", "info")
        else:
            # Mark that we're not auto-refreshing news this cycle
            st.session_state.news_auto_refreshing = False
            
        # Handle economic calendar refresh (every 240th refresh cycle - 1 hour)
        if count % 240 == 0:
            st.session_state.last_calendar_auto_refresh_time = current_time
            fetch_all_economic_events(force=True)
            
        # Handle sentiment data refresh (every 60th refresh cycle - 30 minutes)
        if count % 60 == 0:
            st.session_state.last_sentiment_auto_refresh_time = current_time
            update_all_sentiment_data(force=True)



# def display_rate_info(sub, index):
#     """Display rate information for a currency pair"""
#     # Top row with currency pair and remove button
#     col1, col2 = st.columns([3, 1])
#     with col1:
#         st.markdown(f"### {sub['base']}/{sub['quote']}")
#     with col2:
#         key_base = f"{sub['base']}_{sub['quote']}_{index}"
#         if st.button("Remove", key=f"remove_{key_base}"):
#             st.session_state.subscriptions.pop(index)
#             add_notification(f"Removed subscription: {sub['base']}/{sub['quote']}", "system")
#             st.rerun()

#     # Rate information
#     if sub["current_rate"] is not None:
#         # Format the current rate with appropriate decimal places
#         if sub["current_rate"] < 0.01:
#             formatted_rate = f"{sub['current_rate']:.6f}"
#         elif sub["current_rate"] < 1:
#             formatted_rate = f"{sub['current_rate']:.4f}"
#         else:
#             formatted_rate = f"{sub['current_rate']:.4f}"
        
#         # Format the previous close rate if available
#         previous_rate_text = "N/A"
#         if sub.get("previous_close") is not None:
#             prev_rate = sub["previous_close"]
#             if prev_rate < 0.01:
#                 previous_rate_text = f"{prev_rate:.6f}"
#             elif prev_rate < 1:
#                 previous_rate_text = f"{prev_rate:.4f}"
#             else:
#                 previous_rate_text = f"{prev_rate:.4f}"

#         # Determine rate direction and color
#         direction_arrow = ""
#         color = "gray"
#         direction_class = "rate-neutral"
        
#         # Use previous_close if available, otherwise fall back to last_rate
#         reference_rate = None
#         if sub.get("previous_close") is not None:
#             reference_rate = sub["previous_close"]
#         elif sub.get("last_rate") is not None:
#             reference_rate = sub["last_rate"]
            
#         if reference_rate is not None:
#             if sub["current_rate"] > reference_rate:
#                 direction_arrow = "▲"
#                 color = "green"
#                 direction_class = "rate-up"
#             elif sub["current_rate"] < reference_rate:
#                 direction_arrow = "▼"
#                 color = "red"
#                 direction_class = "rate-down"

#         # Add rate information to HTML
#         html = f"""
#         <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
#             <span>Current Rate:</span>
#             <span class="{direction_class}">{formatted_rate} {direction_arrow}</span>
#         </div>
#         <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
#             <span>Previous Close:</span>
#             <span style="color: #6c757d;">{previous_rate_text}</span>
#         </div>
#         """
#         st.markdown(html, unsafe_allow_html=True)

#         # Add percent change if available
#         if reference_rate is not None:
#             percent_change = ((sub["current_rate"] - reference_rate) / reference_rate) * 100
#             change_color = "green" if percent_change > 0 else "red" if percent_change < 0 else "gray"
#             sign = "+" if percent_change > 0 else ""
#             st.markdown(f"**Change:** <span style='color:{change_color};font-weight:bold;'>{sign}{percent_change:.4f}%</span>", unsafe_allow_html=True)
#     else:
#         st.info("Loading rate data...")

#     # Threshold slider
#     new_threshold = st.slider(
#         "Alert threshold (%)",
#         min_value=0.1,
#         max_value=5.0,
#         value=float(sub["threshold"]),
#         step=0.1,
#         key=f"threshold_slider_{key_base}"
#     )

#     if new_threshold != sub["threshold"]:
#         st.session_state.subscriptions[index]["threshold"] = new_threshold
#         add_notification(f"Updated threshold for {sub['base']}/{sub['quote']} to {new_threshold}%", "system")

# Updated function to blend historical data with real-time rates
def blended_display_rate_history(sub):
    """
    Display rate history blending Yahoo Finance historical data with real-time updates
    
    Args:
        sub: Subscription dictionary containing currency pair information
    """
    import plotly.express as px
    import plotly.graph_objects as go
    import pandas as pd
    from datetime import datetime, timedelta
    import streamlit as st
    
    # First check if we have cached historical data for this pair
    pair_key = f"{sub['base'].lower()}_{sub['quote'].lower()}"
    
    # Initialize the historical data cache if it doesn't exist
    if 'historical_rate_cache' not in st.session_state:
        st.session_state.historical_rate_cache = {}
    
    # Check if we need to fetch new data
    should_fetch = False
    if pair_key not in st.session_state.historical_rate_cache:
        should_fetch = True
    else:
        # Check if cache is older than 15 minutes
        cached_data = st.session_state.historical_rate_cache[pair_key]
        if 'last_fetch_time' in cached_data:
            if (datetime.now() - cached_data['last_fetch_time']).total_seconds() > 900:  # 15 minutes
                should_fetch = True
        else:
            should_fetch = True
    
    # Fetch new historical data if needed
    if should_fetch:
        with st.spinner(f"Fetching historical data for {sub['base']}/{sub['quote']}..."):
            # Determine appropriate range and interval based on market type
            if st.session_state.market_type == 'Crypto':
                # Crypto markets are more volatile, use shorter timeframe
                range_val = "1d"
                interval = "5m"
            else:
                # FX markets, use slightly longer timeframe
                range_val = "5d"
                interval = "15m"
            
            # Fetch the historical data
            df = fetch_historical_rates(sub['base'], sub['quote'], range_val, interval)
            
            if df is not None and not df.empty:
                # Cache the data
                st.session_state.historical_rate_cache[pair_key] = {
                    'data': df,
                    'last_fetch_time': datetime.now()
                }
    
    # Get real-time rate history from session state
    realtime_df = None
    if pair_key in st.session_state.rate_history and len(st.session_state.rate_history[pair_key]) > 1:
        realtime_df = pd.DataFrame(st.session_state.rate_history[pair_key])
    
    # Use historical data from cache if available
    if pair_key in st.session_state.historical_rate_cache:
        historical_df = st.session_state.historical_rate_cache[pair_key]['data']
        
        # Now blend historical and real-time data
        blended_df = historical_df.copy()
        
        # If we have real-time data, filter and append it
        if realtime_df is not None and not realtime_df.empty:
            # Find the last timestamp in historical data
            last_historical_time = historical_df['timestamp'].max()
            
            # Filter real-time data to only include points after the historical data
            new_realtime_df = realtime_df[realtime_df['timestamp'] > last_historical_time]
            
            # If we have new real-time data points, append them
            if not new_realtime_df.empty:
                blended_df = pd.concat([blended_df, new_realtime_df], ignore_index=True)
        
        # Create dark-themed figure
        fig = go.Figure()
        
        # Add historical data trace
        fig.add_trace(go.Scatter(
            x=historical_df['timestamp'],
            y=historical_df['rate'],
            mode='lines',
            name='Historical',
            line=dict(color='#4D9BF5', width=2),
            hovertemplate='%{x}<br>Rate: %{y:.4f}<extra></extra>'
        ))
        
        # Add real-time data trace if available
        if realtime_df is not None and not realtime_df.empty:
            new_realtime_df = realtime_df[realtime_df['timestamp'] > last_historical_time]
            if not new_realtime_df.empty:
                fig.add_trace(go.Scatter(
                    x=new_realtime_df['timestamp'],
                    y=new_realtime_df['rate'],
                    mode='lines',
                    name='Real-time',
                    line=dict(color='#00FF00', width=2.5),  # Brighter green for real-time data
                    hovertemplate='%{x}<br>Rate: %{y:.4f}<extra></extra>'
                ))
        
        # Add chart title
        fig.update_layout(
            title=f"{sub['base']}/{sub['quote']} Rate History",
            title_font_color="#FFFFFF"
        )
        
        # Calculate range values for better visualization
        min_rate = blended_df['rate'].min()
        max_rate = blended_df['rate'].max()
        rate_range = max_rate - min_rate
        
        # If range is very small, create a custom range to make changes more visible
        if rate_range < 0.001:
            # Use a small fixed range around the mean
            mean_rate = blended_df['rate'].mean()
            fig.update_yaxes(range=[mean_rate * 0.9995, mean_rate * 1.0005])
        elif rate_range < 0.01:
            # Add some padding to min/max values to make changes more visible
            fig.update_yaxes(range=[min_rate * 0.999, max_rate * 1.001])
        
        # Add current price line
        if 'current_rate' in sub and sub['current_rate'] is not None:
            fig.add_hline(
                y=sub['current_rate'], 
                line_dash="dash", 
                line_color="green",
                annotation_text="Current",
                annotation_position="top right"
            )
        
        # Add previous close line
        if 'previous_close' in sub and sub['previous_close'] is not None:
            fig.add_hline(
                y=sub['previous_close'], 
                line_dash="dot", 
                line_color="red",
                annotation_text="Prev Close",
                annotation_position="bottom right"
            )
        
        # Apply dark theme styling
        fig.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=40, b=0),
                paper_bgcolor="#121212",  # Dark background
                plot_bgcolor="#121212",   # Dark background
                font=dict(color="#FFFFFF"),  # Pure white text for better visibility
                xaxis=dict(
                    gridcolor="#333333",  # Darker grid
                    tickcolor="#FFFFFF",  # Pure white tick marks
                    linecolor="#555555",  # Medium gray axis line
                    tickfont=dict(color="#FFFFFF", size=12),  # Brighter, larger tick labels
                    title_font=dict(color="#FFFFFF", size=14)  # Brighter, larger axis title
                ),
                yaxis=dict(
                    gridcolor="#333333",  # Darker grid
                    tickcolor="#FFFFFF",  # Pure white tick marks
                    linecolor="#555555",  # Medium gray axis line
                    tickfont=dict(color="#FFFFFF", size=12),  # Brighter, larger tick labels
                    title_font=dict(color="#FFFFFF", size=14)  # Brighter, larger axis title
                ),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1,
                    font=dict(color="#FFFFFF", size=12),  # White legend text
                    bgcolor="rgba(18, 18, 18, 0.5)",  # Semi-transparent background
                    bordercolor="#555555"  # Medium gray border
                )
            )
        
        # Add high/low markers for today
        # Filter for today's data
        today = datetime.now().date()
        today_data = blended_df[blended_df['timestamp'].dt.date == today]
        
        if not today_data.empty:
            today_high = today_data['rate'].max()
            today_low = today_data['rate'].min()
            
            # Add high marker
            fig.add_trace(go.Scatter(
                x=[today_data.loc[today_data['rate'].idxmax(), 'timestamp']],
                y=[today_high],
                mode='markers+text',
                marker=dict(color='#4CAF50', size=10, symbol='triangle-up'),
                text=['High'],
                textposition='top center',
                hoverinfo='text+y',
                name='Today\'s High',
                textfont=dict(color='#4CAF50')
            ))
            
            # Add low marker
            fig.add_trace(go.Scatter(
                x=[today_data.loc[today_data['rate'].idxmin(), 'timestamp']],
                y=[today_low],
                mode='markers+text',
                marker=dict(color='#F44336', size=10, symbol='triangle-down'),
                text=['Low'],
                textposition='bottom center',
                hoverinfo='text+y',
                name='Today\'s Low',
                textfont=dict(color='#F44336')
            ))

            # Add the FX-Pulsar watermark here
            fig.add_annotation(
                text="FX-PULSAR",
                x=0.95,  # Position at 95% from the left
                y=0.10,  # Position at 10% from the bottom
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(
                    family="Arial",
                    size=28,
                    color="rgba(255, 255, 255, 0.15)"  # Semi-transparent white
                ),
                align="right",
                opacity=0.7,
                textangle=0
            )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Add interesting statistics below the chart (same as in previous implementation)
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("### Today's Range")
            if not today_data.empty:
                today_high = today_data['rate'].max()
                today_low = today_data['rate'].min()
                today_range_pct = ((today_high - today_low) / today_low) * 100
                st.markdown(f"""
                <div style="background-color:#1E1E1E; padding:10px; border-radius:5px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span style="color:white;">High:</span>
                        <span style="color:#4CAF50;">{today_high:.4f}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span style="color:white;">Low:</span>
                        <span style="color:#F44336;">{today_low:.4f}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:white;">Range:</span>
                        <span style="color:white;">{today_range_pct:.2f}%</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("No data available for today")
        
        with col2:
            st.markdown("### Volatility")
            # Calculate volatility (standard deviation of returns)
            if len(blended_df) > 1:
                blended_df['return'] = blended_df['rate'].pct_change() * 100
                recent_volatility = blended_df['return'].std()
                
                # Determine volatility level
                if recent_volatility < 0.05:
                    vol_level = "Very Low"
                    color = "#9E9E9E"  # Gray
                elif recent_volatility < 0.1:
                    vol_level = "Low"
                    color = "#4CAF50"  # Green
                elif recent_volatility < 0.2:
                    vol_level = "Moderate"
                    color = "#FFC107"  # Amber
                elif recent_volatility < 0.3:
                    vol_level = "High"
                    color = "#FF9800"  # Orange
                else:
                    vol_level = "Very High"
                    color = "#F44336"  # Red
                    
                st.markdown(f"""
                <div style="background-color:#1E1E1E; padding:10px; border-radius:5px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span style="color:white;">Volatility:</span>
                        <span style="color:{color};">{vol_level}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span style="color:white;">Std Dev:</span>
                        <span style="color:white;">{recent_volatility:.4f}%</span>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:white;">Sample Points:</span>
                        <span style="color:white;">{len(blended_df)}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            else:
                st.info("Insufficient data for volatility calculation")
                
        with col3:
            st.markdown("### Trend Analysis")
            # Simple trend analysis using rolling averages
            if len(blended_df) > 20:
                # Add simple moving averages
                blended_df['SMA5'] = blended_df['rate'].rolling(window=5).mean()
                blended_df['SMA20'] = blended_df['rate'].rolling(window=20).mean()
                
                # Determine trend based on SMA crossovers
                latest_sma5 = blended_df['SMA5'].iloc[-1]
                latest_sma20 = blended_df['SMA20'].iloc[-1]
                
                if latest_sma5 > latest_sma20:
                    trend = "Bullish"
                    color = "#4CAF50"  # Green
                elif latest_sma5 < latest_sma20:
                    trend = "Bearish"
                    color = "#F44336"  # Red
                else:
                    trend = "Neutral"
                    color = "#9E9E9E"  # Gray
                
                # Calculate momentum
                recent_change = ((blended_df['rate'].iloc[-1] - blended_df['rate'].iloc[-20]) / blended_df['rate'].iloc[-20]) * 100
                
                momentum = "Positive" if recent_change > 0 else "Negative"
                momentum_color = "#4CAF50" if recent_change > 0 else "#F44336"
                
                st.markdown(f"""
                <div style="background-color:#1E1E1E; padding:10px; border-radius:5px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span style="color:white;">Trend:</span>
                        <span style="color:{color};">{trend}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                        <span style="color:white;">Momentum:</span>
                        <span style="color:{momentum_color};">{momentum}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:white;">Change:</span>
                        <span style="color:{momentum_color};">{recent_change:.2f}%</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("Insufficient data for trend analysis")
    
    # If no historical data is available, fall back to the existing rate history display
    elif realtime_df is not None and not realtime_df.empty:
        # Your existing rate history chart code
        fig = px.line(realtime_df, x="timestamp", y="rate", 
                    title=f"{sub['base']}/{sub['quote']} Rate History",
                    labels={"timestamp": "Time", "rate": "Rate"})
        
        # Calculate range values for better visualization
        min_rate = realtime_df['rate'].min()
        max_rate = realtime_df['rate'].max()
        rate_range = max_rate - min_rate
        
        # If range is very small, create a custom range to make changes more visible
        if rate_range < 0.001:
            # Use a small fixed range around the mean
            mean_rate = realtime_df['rate'].mean()
            fig.update_yaxes(range=[mean_rate * 0.9995, mean_rate * 1.0005])
        elif rate_range < 0.01:
            # Add some padding to min/max values to make changes more visible
            fig.update_yaxes(range=[min_rate * 0.999, max_rate * 1.001])
        
        # Apply dark theme styling
        fig.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=40, b=0),
                paper_bgcolor="#121212",  # Dark background
                plot_bgcolor="#121212",   # Dark background
                font=dict(color="#FFFFFF"),  # Pure white text for better visibility
                title_font_color="#FFFFFF",  # Pure white title text
                xaxis=dict(
                    gridcolor="#333333",  # Darker grid
                    tickcolor="#FFFFFF",  # Pure white tick marks
                    linecolor="#555555",  # Medium gray axis line
                    tickfont=dict(color="#FFFFFF", size=12),  # Brighter, larger tick labels
                    title_font=dict(color="#FFFFFF", size=14)  # Brighter, larger axis title
                ),
                yaxis=dict(
                    gridcolor="#333333",  # Darker grid
                    tickcolor="#FFFFFF",  # Pure white tick marks
                    linecolor="#555555",  # Medium gray axis line
                    tickfont=dict(color="#FFFFFF", size=12),  # Brighter, larger tick labels
                    title_font=dict(color="#FFFFFF", size=14)  # Brighter, larger axis title
                )
            )
        
        # Change line color to a brighter shade
        fig.update_traces(
            line=dict(color="#4D9BF5", width=2)  # Bright blue line
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No rate history data available yet. Please wait for more data to be collected.")
        
# Add this to your main app to handle crypto calendar events

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

def is_valid_event(event):
    """
    Validate if the event has the necessary structure and data.
    Modify this function based on what constitutes a valid event.
    """
    # Updated keys based on the event structure
    required_keys = ['title', 'description', 'type', 'coin', 'date', 'url']
    
    if not isinstance(event, dict):
        return False
    
    # Check if all required keys are present
    for key in required_keys:
        if key not in event:
            return False
    
    # Additional checks can be added here, such as checking the date format
    if event.get('date'):
        try:
            # Example: Check if the date is a valid date string (you can refine this check as needed)
            datetime.strptime(event['date'], '%Y-%m-%d')
        except ValueError:
            return False
    
    return True

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
            print("Fetching crypto calendar")
            debug_log = []  # Placeholder for debugging, consider using it for logging if needed
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
                    # Debugging
                    print(f"Fetched valid events: {valid_events}")
                else:
                    st.warning("No valid events found")
                    st.session_state.crypto_events = []
            else:
                st.warning("Could not fetch crypto events")
                st.session_state.crypto_events = []
    
    # Return the cached or fetched valid events
    return st.session_state.get('crypto_events', [])

def update_all_sentiment_data(force=False):
    """
    Fetch and update all sentiment data from MyFXBook
    
    Args:
        force: If True, force refresh regardless of cache
    
    Returns:
        dict: The sentiment data
    """
    # Check if we need to refresh at all
    should_refresh = force
    
    if 'fxbook_sentiment_last_fetch' not in st.session_state:
        st.session_state.fxbook_sentiment_last_fetch = None
        should_refresh = True
    
    if not should_refresh and st.session_state.fxbook_sentiment_last_fetch:
        # Refresh every 15 minutes
        time_since_last_fetch = (datetime.now() - st.session_state.fxbook_sentiment_last_fetch).total_seconds()
        if time_since_last_fetch > 15 * 60:  # 15 minutes in seconds
            should_refresh = True
    
    if should_refresh:
        with st.spinner("Fetching trader sentiment data..."):
            try:
                sentiment_data = scrape_myfxbook_sentiment_all_pairs()
                
                if sentiment_data:
                    st.session_state.fxbook_sentiment_data = sentiment_data
                    st.session_state.fxbook_sentiment_last_fetch = datetime.now()
                    
                    # Notify user
                    pairs_count = len(sentiment_data.get('data', {}))
                    add_notification(f"Trader sentiment updated for {pairs_count} currency pairs", "success")
                    return sentiment_data
                else:
                    add_notification("Failed to fetch trader sentiment data", "error")
            except Exception as e:
                add_notification(f"Error fetching trader sentiment: {str(e)}", "error")
    
    return st.session_state.get('fxbook_sentiment_data', {})

def get_sentiment_for_pair(base, quote):
    """
    Get sentiment data for a specific currency pair
    
    Args:
        base: Base currency code (e.g. 'EUR')
        quote: Quote currency code (e.g. 'USD')
    
    Returns:
        dict: Sentiment data for the pair or None if not available
    """
    pair = f"{base}{quote}"
    
    # Make sure we have data
    if 'fxbook_sentiment_data' not in st.session_state:
        update_all_sentiment_data()
    
    if not st.session_state.get('fxbook_sentiment_data'):
        return None
    
    # Try to get data for this pair
    return st.session_state.fxbook_sentiment_data.get('data', {}).get(pair)

def load_sentiment_data():
    """
    Load sentiment data for all pairs if not already loaded
    """
    if 'fxbook_sentiment_data' not in st.session_state:
        update_all_sentiment_data()
    
    return st.session_state.get('fxbook_sentiment_data', {})

def create_sentiment_tab_ui():
    """
    Create a standalone sentiment analysis tab UI for the main dashboard
    """
    # Load sentiment data if not already loaded
    sentiment_data = load_sentiment_data()
    
    if not sentiment_data or not sentiment_data.get('data'):
        st.info("No sentiment data available. Please refresh the data.")
        if st.button("Refresh Sentiment Data"):
            update_all_sentiment_data(force=True)
            st.rerun()
        return
    
    # Get the timestamp
    timestamp = sentiment_data.get('timestamp', 'Unknown')
    try:
        # Try to format the timestamp nicely
        dt = datetime.fromisoformat(timestamp)
        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        st.caption(f"Data as of: {formatted_time}")
    except:
        st.caption(f"Data as of: {timestamp}")
    
    # Add refresh button
    if st.button("Refresh Sentiment Data", key="refresh_sentiment_main"):
        update_all_sentiment_data(force=True)
        st.rerun()
    
    # Get all available pairs
    pairs_data = sentiment_data.get('data', {})
    
    if not pairs_data:
        st.warning("No pairs data available")
        return
    
    # Create a grid of sentiment dials
    # Split into rows of 3 dials each
    pairs = list(pairs_data.keys())
    
    # Sort pairs by popularity if available
    pairs_with_popularity = [(pair, pairs_data[pair].get('detailed', {}).get('popularity', '99')) 
                             for pair in pairs]
    
    # Sort by popularity (convert to int with a fallback to 99 if not a number)
    sorted_pairs = [p[0] for p in sorted(pairs_with_popularity, 
                                       key=lambda x: int(x[1]) if str(x[1]).isdigit() else 99)]
    
    # Create a table of sentiment gauges - 3 per row
    for i in range(0, len(sorted_pairs), 3):
        row_pairs = sorted_pairs[i:i+3]
        cols = st.columns(3)
        
        for j, pair in enumerate(row_pairs):
            if j < len(cols):
                with cols[j]:
                    pair_data = pairs_data[pair]
                    
                    # Create a compact sentiment gauge
                    long_pct = pair_data.get('long_percentage', 0)
                    short_pct = pair_data.get('short_percentage', 0)
                    
                    # Determine gauge color based on sentiment
                    if long_pct > 70:
                        color = "#4CAF50"  # Green - strongly bullish
                    elif long_pct > 55:
                        color = "#8BC34A"  # Light green - moderately bullish
                    elif short_pct > 70:
                        color = "#F44336"  # Red - strongly bearish
                    elif short_pct > 55:
                        color = "#FF9800"  # Orange - moderately bearish
                    else:
                        color = "#9E9E9E"  # Gray - mixed/neutral
                    
                    # Create a circular gauge indicating sentiment balance
                    fig = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=long_pct,
                        domain={'x': [0, 1], 'y': [0, 1]},
                        title={'text': pair, 'font': {'color': 'white', 'size': 16}},
                        gauge={
                            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
                            'bar': {'color': color},
                            'bgcolor': "gray",
                            'borderwidth': 2,
                            'bordercolor': "white",
                            'steps': [
                                {'range': [0, 100], 'color': "#1E1E1E"}
                            ],
                        },
                        number={'suffix': "%<br>LONG", 'font': {'color': 'white'}}
                    ))
                    
                    # Update layout
                    fig.update_layout(
                        height=200,
                        margin=dict(l=10, r=10, t=30, b=10),
                        paper_bgcolor="#121212",
                        font=dict(color="white", size=12)
                    )
                    
                    # Display the gauge
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Display key information below gauge
                    current_rate = pair_data.get('current_rate', 'N/A')
                    
                    st.markdown(
                        f"""
                        <div style="background-color:#1E1E1E; padding:10px; border-radius:5px; margin-top:-15px; text-align:center;">
                            <div style="font-size:1.2rem; font-weight:bold; margin-bottom:5px;">{current_rate}</div>
                            <div style="display:flex; justify-content:space-between;">
                                <span style="color:#F44336;">{short_pct}% Short</span>
                                <span style="color:#4CAF50;">{long_pct}% Long</span>
                            </div>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )

def display_sentiment_tab(base, quote, debug_log=None):
    """
    Display MyFXBook sentiment data for a currency pair in a tab interface
    
    Args:
        base: Base currency code (e.g. 'EUR')
        quote: Quote currency code (e.g. 'USD')
        debug_log: Optional list to append debug information
    """
    if debug_log is None:
        debug_log = []
    
    # Generate unique ID to avoid conflicts when multiple tabs are open
    unique_id = f"{base}_{quote}_sentiment_{random.randint(1000, 9999)}"
    
    # Check if we have sentiment data cached
    if 'fxbook_sentiment_data' not in st.session_state:
        with st.spinner("Fetching sentiment data..."):
            try:
                st.session_state.fxbook_sentiment_data = scrape_myfxbook_sentiment_all_pairs()
                st.session_state.last_sentiment_fetch = datetime.now()
            except Exception as e:
                debug_log.append(f"Error fetching sentiment data: {str(e)}")
                st.error("Could not fetch sentiment data. Please try again later.")
                return
    
    # Create a button to refresh the sentiment data
    if st.button(f"Refresh Sentiment Data", key=f"refresh_sentiment_{unique_id}"):
        with st.spinner("Refreshing sentiment data..."):
            try:
                st.session_state.fxbook_sentiment_data = scrape_myfxbook_sentiment_all_pairs()
                st.session_state.last_sentiment_fetch = datetime.now()
                add_notification("Sentiment data refreshed successfully", "success")
            except Exception as e:
                debug_log.append(f"Error refreshing sentiment data: {str(e)}")
                st.error("Could not refresh sentiment data. Please try again later.")
    
    # Display last refresh time if available
    if 'last_sentiment_fetch' in st.session_state:
        time_diff = datetime.now() - st.session_state.last_sentiment_fetch
        if time_diff.seconds < 60:
            refresh_text = "just now"
        elif time_diff.seconds < 3600:
            refresh_text = f"{time_diff.seconds // 60} minutes ago"
        else:
            refresh_text = f"{time_diff.seconds // 3600} hours ago"
        st.caption(f"Sentiment data last updated: {refresh_text}")
    
    # Get the pair string (e.g., "EURUSD")
    pair_string = f"{base}{quote}"
    
    if 'fxbook_sentiment_data' in st.session_state and st.session_state.fxbook_sentiment_data:
        try:
            # Extract sentiment data for this pair if available
            sentiment_data = st.session_state.fxbook_sentiment_data.get('data', {}).get(pair_string)
            
            if sentiment_data:
                # Create three columns for layout
                col1, col2 = st.columns(2)
                
                with col1:
                    # Create the sentiment donut chart
                    fig = go.Figure()
                    
                    # Add donut chart for long/short percentages
                    long_pct = sentiment_data.get('long_percentage', 0)
                    short_pct = sentiment_data.get('short_percentage', 0)
                    
                    fig.add_trace(go.Pie(
                        labels=['Long', 'Short'],
                        values=[long_pct, short_pct],
                        hole=0.7,
                        marker=dict(
                            colors=['#4CAF50', '#F44336'],  # Green for long, red for short
                        ),
                        textinfo='label+percent',
                        insidetextfont=dict(color='white', size=14),
                        textfont=dict(color='white', size=14),
                        hoverinfo='label+percent',
                        showlegend=False
                    ))
                    
                    # Add current rate as annotation in the center
                    current_rate = sentiment_data.get('current_rate', 'N/A')
                    fig.update_layout(
                        annotations=[dict(
                            text=f"<b>{current_rate}</b>",
                            x=0.5, y=0.5,
                            font=dict(size=18, color='white'),
                            showarrow=False
                        )]
                    )
                    
                    # Style the chart
                    fig.update_layout(
                        title=f"{base}/{quote} Sentiment",
                        height=300,
                        margin=dict(l=10, r=10, t=40, b=10),
                        paper_bgcolor="#121212",
                        plot_bgcolor="#121212",
                        font=dict(color='white')
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # Display the sentiment details in a table
                    st.subheader("Sentiment Details")
                    
                    # Create a stylized card for short positions
                    st.markdown(
                        f"""
                        <div style="background-color:#1E1E1E; border-radius:5px; padding:15px; margin-bottom:15px;">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                                <span style="color:#F44336; font-weight:bold; font-size:18px;">SHORT</span>
                                <span style="color:#F44336; font-weight:bold; font-size:18px;">{short_pct}%</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                <span style="color:#AAAAAA;">Average Price:</span>
                                <span style="color:white;">{sentiment_data.get('short_price', 'N/A')}</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                <span style="color:#AAAAAA;">Distance to Current:</span>
                                <span style="color:white;">{sentiment_data.get('short_distance', 'N/A')}</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                <span style="color:#AAAAAA;">Volume:</span>
                                <span style="color:white;">{sentiment_data.get('detailed', {}).get('short', {}).get('volume', 'N/A')}</span>
                            </div>
                            <div style="display:flex; justify-content:space-between;">
                                <span style="color:#AAAAAA;">Positions:</span>
                                <span style="color:white;">{sentiment_data.get('detailed', {}).get('short', {}).get('positions', 'N/A')}</span>
                            </div>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                    
                    # Create a stylized card for long positions
                    st.markdown(
                        f"""
                        <div style="background-color:#1E1E1E; border-radius:5px; padding:15px;">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                                <span style="color:#4CAF50; font-weight:bold; font-size:18px;">LONG</span>
                                <span style="color:#4CAF50; font-weight:bold; font-size:18px;">{long_pct}%</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                <span style="color:#AAAAAA;">Average Price:</span>
                                <span style="color:white;">{sentiment_data.get('long_price', 'N/A')}</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                <span style="color:#AAAAAA;">Distance to Current:</span>
                                <span style="color:white;">{sentiment_data.get('long_distance', 'N/A')}</span>
                            </div>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                
                # Show popularity if available
                popularity = sentiment_data.get('detailed', {}).get('popularity')
                if popularity:
                    st.markdown(f"**Popularity Rank:** {popularity}")
                
                # Add an analysis section
                st.subheader("Quick Analysis")
                
                # Generate trading sentiment analysis based on the data
                if long_pct > 65:
                    analysis = f"Strong bullish sentiment with {long_pct}% of traders long. This could indicate an overbought condition."
                    trend_color = "#4CAF50"  # Green
                elif long_pct > 55:
                    analysis = f"Moderately bullish sentiment with {long_pct}% of traders long."
                    trend_color = "#8BC34A"  # Light green
                elif short_pct > 65:
                    analysis = f"Strong bearish sentiment with {short_pct}% of traders short. This could indicate an oversold condition."
                    trend_color = "#F44336"  # Red
                elif short_pct > 55:
                    analysis = f"Moderately bearish sentiment with {short_pct}% of traders short."
                    trend_color = "#FF9800"  # Orange
                else:
                    analysis = f"Mixed sentiment with {long_pct}% long and {short_pct}% short, indicating no clear consensus."
                    trend_color = "#9E9E9E"  # Gray
                
                # Check for potential contrarian opportunities
                if short_pct > 75:
                    contrarian = "Extremely high short interest could present a contrarian long opportunity if price starts to rise."
                elif long_pct > 75:
                    contrarian = "Extremely high long interest could present a contrarian short opportunity if price starts to fall."
                else:
                    contrarian = "No extreme positioning detected. Trade with the trend."
                
                # Display the analysis with styling
                st.markdown(
                    f"""
                    <div style="background-color:#1E1E1E; border-radius:5px; padding:15px; margin-bottom:15px; border-left: 4px solid {trend_color};">
                        <p style="color:white; margin-bottom:10px;">{analysis}</p>
                        <p style="color:#BBBBBB; font-style:italic; margin-bottom:0px;">{contrarian}</p>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
                
            else:
                st.warning(f"No sentiment data available for {base}/{quote}")
                
                # Show available pairs
                if 'data' in st.session_state.fxbook_sentiment_data:
                    available_pairs = list(st.session_state.fxbook_sentiment_data['data'].keys())
                    st.info(f"Available pairs: {', '.join(available_pairs)}")
        
        except Exception as e:
            debug_log.append(f"Error displaying sentiment data: {str(e)}")
            st.error(f"Error displaying sentiment data: {str(e)}")
    else:
        st.info("Sentiment data not available. Please refresh the data.")


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

# Initialize the session state for economic events
if 'economic_events' not in st.session_state:
    st.session_state.economic_events = None

if 'economic_events_last_fetch' not in st.session_state:
    st.session_state.economic_events_last_fetch = None


# Add the fetch_news function to your main app since it depends on st.session_state
def fetch_news(currencies=None, use_mock_fallback=True, force=False):
    """Fetch news for currency pairs, with prioritization of local disk cache."""
    
    # Check if we need to refresh at all
    if not force and 'last_news_fetch' in st.session_state and st.session_state.last_news_fetch:
        # Don't refresh if it's been less than 60 seconds since last refresh
        # This prevents excessive API calls even with manual refreshes
        seconds_since_refresh = (datetime.now() - st.session_state.last_news_fetch).total_seconds()
        if seconds_since_refresh < 60:
            if 'show_debug' in st.session_state and st.session_state.show_debug:
                st.info(f"Skipping news refresh (last refresh {seconds_since_refresh:.0f}s ago)")
            if 'cached_news' in st.session_state:
                return st.session_state.cached_news
            
    if 'subscriptions' not in st.session_state:
        return []

    currency_pairs = list(set((sub["base"], sub["quote"]) for sub in st.session_state.subscriptions))

    if not currency_pairs:
        return []

    # Initialize debug log
    if 'debug_log' not in st.session_state or not isinstance(st.session_state.debug_log, list):
        st.session_state.debug_log = []
        
    # Force a reset of disk_news_loaded flag when explicitly requested
    if force and 'disk_news_loaded' in st.session_state:
        st.session_state.disk_news_loaded = False
        
    # NEW: First check if we have news on disk to display immediately
    show_disk_news = ('disk_news_loaded' not in st.session_state or 
                      not st.session_state.disk_news_loaded or 
                      force)
    
    if show_disk_news:
        # Make spinner explicitly visible
        with st.spinner("Loading news from disk..."):
            # Add debug notification to ensure this section is reached
            add_notification("Checking for news files in fx_news/scrapers/news/yahoo/", "info")
            
            # Try to load news from disk
            disk_news = load_news_from_disk(currency_pairs)
            
            # Report what we found
            if disk_news:
                add_notification(f"Found {len(disk_news)} news articles on disk", "success")
            else:
                add_notification("No news articles found on disk", "info")
            
            if disk_news and len(disk_news) > 0:
                # Always use disk news on first load, regardless of pair coverage
                st.success(f"Found {len(disk_news)} news articles on disk. Displaying these while fetching latest news.")
                st.session_state.cached_news = disk_news
                st.session_state.disk_news_loaded = True
                
                # Schedule a background refresh for new news after a delay
                st.session_state.last_news_fetch = datetime.now() - timedelta(seconds=50)  # Set to refresh soon
                st.session_state.next_news_refresh_time = datetime.now() + timedelta(seconds=5)
                
                # Return the disk news immediately
                return disk_news

    st.session_state.debug_log.append(f"Attempting to fetch news for {len(currency_pairs)} currency pairs")

    try:
        with st.spinner("Fetching latest news from Yahoo Finance..."):
            all_news_items = []
            for base, quote in currency_pairs:
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
                        
                    all_news_items.append(item)

            if all_news_items:
                unique_news = {}
                for item in all_news_items:
                    key = item.get('url', '') if item.get('url') else item.get('title', '')
                    if key:
                        if key in unique_news:
                            unique_news[key]['currency_pairs'].update(item['currency_pairs'])
                        else:
                            unique_news[key] = item

                deduplicated_news = list(unique_news.values())
                deduplicated_news.sort(key=lambda x: x["timestamp"], reverse=True)

                add_notification(f"Successfully fetched {len(deduplicated_news)} unique news items from Yahoo Finance", "success")
                st.session_state.last_news_fetch = datetime.now()
                st.session_state.cached_news = deduplicated_news
                st.session_state.disk_news_loaded = True  # Mark that we've loaded news
                
                # Always run background sentiment analysis, but optimize for performance
                if deduplicated_news:
                    # Use threading to run sentiment analysis in background
                    import threading
                    from fx_news.scrapers.news_scraper import analyze_sentiment
                    
                    # Create a local logger that doesn't depend on st.session_state
                    import logging
                    thread_logger = logging.getLogger("sentiment_thread")
                    if not thread_logger.handlers:
                        handler = logging.StreamHandler()
                        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                        handler.setFormatter(formatter)
                        thread_logger.addHandler(handler)
                        thread_logger.setLevel(logging.INFO)
                    
                    # Save necessary variables as local copies for the thread
                    news_folder = "fx_news/scrapers/news/yahoo"
                    api_key = '1i1PR8oSJwazWAyOj3iXiRoiCThZI6qj'
                    
                    def background_sentiment_task():
                        try:
                            # Find items without sentiment or with default neutral/0.0 values
                            items_needing_sentiment = [
                                item for item in deduplicated_news 
                                if 'sentiment' not in item or not item['sentiment'] or 
                                (item.get('sentiment') == 'neutral' and item.get('score', 0) == 0.0)
                            ]
                            
                            # Limit to processing just a few items at a time for better performance
                            max_items_per_batch = 3  # Reduced to 3 for better performance
                            items_to_process = items_needing_sentiment[:max_items_per_batch]
                            
                            if items_to_process:
                                thread_logger.info(f"Starting background sentiment analysis for {len(items_to_process)}/{len(items_needing_sentiment)} articles")
                                
                                # Process each item and update both the item and file
                                for i, item in enumerate(items_to_process):
                                    try:
                                        # Find the file path
                                        file_path = None
                                        
                                        # Try to get file_path from item if it exists
                                        if 'file_path' in item and item['file_path'] and os.path.exists(item['file_path']):
                                            file_path = item['file_path']
                                        # Otherwise try to find it based on timestamp and currency
                                        elif 'unix_timestamp' in item and 'currency' in item:
                                            timestamp = item['unix_timestamp']
                                            currency = item['currency'].replace('/', '_').lower()
                                            potential_path = os.path.join(news_folder, f"article_{timestamp}_{currency}.txt")
                                            
                                            if os.path.exists(potential_path):
                                                file_path = potential_path
                                                thread_logger.info(f"Found file path based on timestamp and currency: {file_path}")
                                            else:
                                                # Try pattern matching
                                                pattern = os.path.join(news_folder, f"article_{timestamp}_*.txt")
                                                matching_files = glob.glob(pattern)
                                                if matching_files:
                                                    file_path = matching_files[0]
                                                    thread_logger.info(f"Found file path based on timestamp pattern: {file_path}")
                                        
                                        if not file_path:
                                            thread_logger.warning(f"Could not find file for article: {item.get('title', 'Unknown')}")
                                            continue
                                        
                                        # Read file content
                                        with open(file_path, 'r', encoding='utf-8') as f:
                                            content = f.read()
                                        
                                        # Extract title and summary
                                        title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
                                        title = title_match.group(1).strip() if title_match else item.get('title', '')
                                        
                                        summary_match = re.search(r'SUMMARY:\s(.*?)(?:\n\n|\Z)', content, re.DOTALL)
                                        summary = summary_match.group(1).strip() if summary_match else ''
                                        
                                        # Analyze sentiment
                                        text_for_sentiment = f"{title} {summary}"
                                        thread_logger.info(f"Analyzing sentiment for {title}")
                                        sentiment_label, sentiment_score = analyze_sentiment(
                                            text_for_sentiment, 
                                            mode='ensemble', 
                                            api_key=api_key
                                        )
                                        thread_logger.info(f"Sentiment result: {sentiment_label} ({sentiment_score})")
                                        
                                        # Update item in memory
                                        item['sentiment'] = sentiment_label
                                        item['score'] = sentiment_score
                                        
                                        # Check if file already has sentiment markers
                                        has_sentiment_markers = '---\nSENTIMENT:' in content
                                        
                                        # Update the file
                                        if has_sentiment_markers:
                                            # Replace existing markers
                                            new_content = re.sub(
                                                r'---\nSENTIMENT:.*?\nSCORE:.*?(?=\n\n|\Z)', 
                                                f"---\nSENTIMENT: {sentiment_label}\nSCORE: {sentiment_score}", 
                                                content, 
                                                flags=re.DOTALL
                                            )
                                            with open(file_path, 'w', encoding='utf-8') as f:
                                                f.write(new_content)
                                            thread_logger.info(f"Updated existing sentiment markers in {os.path.basename(file_path)}")
                                        else:
                                            # Append new markers
                                            with open(file_path, 'a', encoding='utf-8') as f:
                                                f.write(f"\n\n---\nSENTIMENT: {sentiment_label}\nSCORE: {sentiment_score}\n")
                                            thread_logger.info(f"Added new sentiment markers to {os.path.basename(file_path)}")
                                        
                                        # Add longer delay between API requests to reduce load
                                        if i < len(items_to_process) - 1:
                                            time.sleep(1.5)  # 1.5 second delay
                                            
                                    except Exception as e:
                                        thread_logger.error(f"Error updating sentiment for article: {str(e)}")
                                
                            else:
                                thread_logger.info("No articles need sentiment analysis")
                                
                        except Exception as e:
                            # Log any errors from the thread
                            thread_logger.error(f"Error in background sentiment task: {str(e)}")
                    
                    # Start the background thread with a longer delay
                    sentiment_thread = threading.Thread(target=background_sentiment_task)
                    sentiment_thread.daemon = True  # Allow app to exit even if thread is running
                    # Add a longer delay before starting the thread to let main UI render completely
                    time.sleep(1.0)  # Increased delay
                    sentiment_thread.start()
                
                return deduplicated_news
            else:
                if isinstance(st.session_state.debug_log, list):
                    st.session_state.debug_log.append("No news items found from Yahoo Finance")
    except Exception as e:
        if isinstance(st.session_state.debug_log, list):
            st.session_state.debug_log.append(f"Error fetching news from Yahoo Finance: {str(e)}")
        add_notification(f"Error fetching news from Yahoo Finance: {str(e)}", "error")

    if use_mock_fallback:
        add_notification("Using mock news data as fallback", "info")
        return create_mock_news(currencies)

    if 'cached_news' in st.session_state and st.session_state.cached_news:
        return st.session_state.cached_news

    return []

def load_news_from_disk(currency_pairs):
    """
    Load existing news articles from disk for the given currency pairs.
    
    Args:
        currency_pairs: List of (base, quote) tuples
    
    Returns:
        List of news items loaded from disk
    """
    news_folder = "fx_news/scrapers/news/yahoo"
    all_news = []
    
    try:
        # Print debug info about the directory we're looking in
        print(f"Looking for news files in {news_folder}")
        
        # Check if directory exists
        if not os.path.exists(news_folder):
            print(f"Warning: News folder {news_folder} does not exist")
            return []
            
        # List all files in the directory to debug
        all_files = os.listdir(news_folder)
        print(f"All files in directory: {all_files}")
        
        # Look for all .txt files in the news folder
        article_files = glob.glob(os.path.join(news_folder, "article_*.txt"))
        print(f"Found {len(article_files)} article files matching pattern")
        
        if not article_files:
            return []
            
        # Process each file and extract relevant information
        for file_path in article_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract timestamp from filename using regex
                filename = os.path.basename(file_path)
                print(f"Processing file: {filename}")
                
                timestamp_match = re.search(r'article_([0-9]+)_', filename)
                if not timestamp_match:
                    print(f"Could not extract timestamp from filename {filename}")
                    # Use file modification time as fallback
                    timestamp = datetime.fromtimestamp(os.path.getmtime(file_path))
                    print(f"Using file modification time: {timestamp}")
                else:
                    timestamp_str = timestamp_match.group(1)
                    try:
                        timestamp = datetime.fromtimestamp(int(timestamp_str))
                        print(f"Extracted timestamp: {timestamp}")
                    except ValueError as e:
                        print(f"Error converting timestamp {timestamp_str}: {e}")
                        # If timestamp conversion fails, use file modification time
                        timestamp = datetime.fromtimestamp(os.path.getmtime(file_path))
                        print(f"Using file modification time: {timestamp}")
                
                # Extract title from content
                title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
                title = title_match.group(1).strip() if title_match else "Unknown Title"
                
                # Extract summary
                summary_match = re.search(r'SUMMARY:\s(.*?)(?:\n\n|\Z)', content, re.DOTALL)
                summary = summary_match.group(1).strip() if summary_match else ""
                
                # Extract source if available
                source_match = re.search(r'SOURCE:\s(.*?)(?:\n|\Z)', content, re.MULTILINE)
                source = source_match.group(1).strip() if source_match else "Yahoo Finance"
                
                # Extract currency pair from filename or make an educated guess
                currency_pairs_set = set()
                
                # First try to extract directly from filename
                filename_lower = os.path.basename(file_path).lower()
                currency_pattern = re.search(r'article_\d+_([a-z]+)_([a-z]+)\.txt', filename_lower)
                if currency_pattern:
                    extracted_base = currency_pattern.group(1)
                    extracted_quote = currency_pattern.group(2)
                    print(f"Extracted from filename: {extracted_base}/{extracted_quote}")
                    # Normalize the case to match available currencies
                    for base, quote in currency_pairs:
                        if base.lower() == extracted_base and quote.lower() == extracted_quote:
                            currency_pairs_set.add(f"{base}/{quote}")
                            print(f"Matched to subscription pair: {base}/{quote}")
                
                # If no direct match, try other approaches
                if not currency_pairs_set:
                    for base, quote in currency_pairs:
                        # Check if this currency pair is mentioned in the filename
                        pair_str = f"{base.lower()}_{quote.lower()}"
                        if pair_str in filename_lower:
                            currency_pairs_set.add(f"{base}/{quote}")
                            print(f"Found pair in filename: {base}/{quote}")
                        # Also check content for mentions
                        elif base.lower() in content.lower() and quote.lower() in content.lower():
                            currency_pairs_set.add(f"{base}/{quote}")
                            print(f"Found currencies mentioned in content: {base}/{quote}")
                
                # If no currency pairs were found, assign to the first currency pair
                if not currency_pairs_set and currency_pairs:
                    base, quote = currency_pairs[0]
                    currency_pairs_set.add(f"{base}/{quote}")
                    print(f"No match found, defaulting to: {base}/{quote}")
                
                # Extract sentiment if available
                sentiment_match = re.search(r'SENTIMENT:\s(.*?)(?:\n|\Z)', content, re.MULTILINE)
                sentiment = sentiment_match.group(1).strip() if sentiment_match else "neutral"
                
                score_match = re.search(r'SCORE:\s(.*?)(?:\n|\Z)', content, re.MULTILINE)
                try:
                    score = float(score_match.group(1).strip()) if score_match else 0.0
                except ValueError:
                    score = 0.0
                
                # Get URL if it exists
                url_match = re.search(r'URL:\s(.*?)(?:\n|\Z)', content, re.MULTILINE)
                url = url_match.group(1).strip() if url_match else ""
                
                # Create news item
                news_item = {
                    "title": title,
                    "summary": summary,
                    "source": source,
                    "timestamp": timestamp,
                    "unix_timestamp": int(timestamp.timestamp()),
                    "currency_pairs": currency_pairs_set,
                    "currency": next(iter(currency_pairs_set)) if currency_pairs_set else "Unknown",
                    "sentiment": sentiment,
                    "score": score,
                    "url": url,
                    "file_path": file_path  # Store the file path for future updates
                }
                
                all_news.append(news_item)
                
            except Exception as e:
                print(f"Error processing news file {file_path}: {str(e)}")
                continue
        
        # Sort by timestamp, newest first
        all_news.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return all_news
            
    except Exception as e:
        print(f"Error loading news from disk: {str(e)}")
        return []
        
# Function to add a notification
def add_notification(message, type='system'):
    notification = {
        "id": int(time.time() * 1000),
        "message": message,
        "type": type,
        "timestamp": datetime.now()
    }
    st.session_state.notifications.insert(0, notification)
    # Keep only the 20 most recent notifications
    if len(st.session_state.notifications) > 20:
        st.session_state.notifications = st.session_state.notifications[:20]

    #https://pixabay.com/sound-effects/search/ai%20generated/
    # Play buzz sound for alert notifications
    if type == 'price':
        st.markdown(
            """
            <audio autoplay>
                <source src="price_sound.mp3" type="audio/mpeg">
            </audio>
            """,
            unsafe_allow_html=True
        )

# separate function for manual refresh that can also fetch news
def manual_refresh_rates_and_news():
    """Function for manual refresh button that updates rates and then optionally fetches news"""
    success = update_rates()
    if success:
        fetch_news(use_mock_fallback=True)

# Function to update rates with fixed logic for handling the new data format
def update_rates(use_mock_data=False):
    try:
        updated_any = False
        bases_to_fetch = set(sub["base"].lower() for sub in st.session_state.subscriptions)
        
        results = {}
        
        if use_mock_data:
            # Use mock data for testing
            mock_data = get_mock_currency_rates()
            for base in bases_to_fetch:
                if base in mock_data:
                    results[base] = mock_data[base]
                    updated_any = True
            add_notification("Using mock currency data for testing", "info")
        else:
            # Use the optimized scraper method
            currency_pairs = [(sub["base"], sub["quote"]) for sub in st.session_state.subscriptions]
            results = scrape_yahoo_finance_rates(currency_pairs, debug_log=st.session_state.debug_log)
            # Check if any rates were fetched
            if results:
                updated_any = True

        if updated_any:
            # Update subscriptions with new rates
            for sub in st.session_state.subscriptions:
                base = sub["base"].lower()
                quote = sub["quote"].lower()

                # Create normalized results keys dictionary for case-insensitive comparison
                results_lower = {}
                for k, v in results.items():
                    results_lower[k.lower()] = {}
                    for kk, vv in v.items():
                        results_lower[k.lower()][kk.lower()] = vv

                if base in results_lower and quote in results_lower[base]:
                    rate_data = results_lower[base][quote]
                    
                    # Handle both new dictionary format and old scalar format
                    if isinstance(rate_data, dict) and "price" in rate_data:
                        # New format with price and previous_close
                        sub["previous_close"] = rate_data.get("previous_close")
                        sub["current_rate"] = rate_data["price"]
                    else:
                        # Old format with just a rate value
                        sub["last_rate"] = sub["current_rate"]
                        sub["current_rate"] = rate_data

                    # Optional: Add small random variations for testing UI updates
                    if 'show_debug' in st.session_state and st.session_state.show_debug and 'add_variations' in st.session_state and st.session_state.add_variations:
                        sub["current_rate"] = update_rates_with_variation(sub["current_rate"])

                    # Initialize rate history if needed
                    pair_key = f"{base}_{quote}"
                    if pair_key not in st.session_state.rate_history:
                        st.session_state.rate_history[pair_key] = []

                    # Add to history (keep only last 100 points)
                    st.session_state.rate_history[pair_key].append({
                        "timestamp": datetime.now(),
                        "rate": sub["current_rate"]
                    })
                    if len(st.session_state.rate_history[pair_key]) > 100:
                        st.session_state.rate_history[pair_key] = st.session_state.rate_history[pair_key][-100:]

                    # Check for threshold breach using previous_close if available
                    reference_price = None
                    if sub.get("previous_close") is not None:
                        reference_price = sub["previous_close"]
                    elif sub.get("last_rate") is not None:
                        reference_price = sub["last_rate"]
                        
                    if reference_price is not None and sub["current_rate"] is not None:
                        percent_change = abs((sub["current_rate"] - reference_price) / reference_price * 100)
                        if percent_change > sub["threshold"]:
                            direction = "increased" if sub["current_rate"] > reference_price else "decreased"
                            add_notification(
                                f"{sub['base']}/{sub['quote']} {direction} by {percent_change:.2f}% (threshold: {sub['threshold']}%)",
                                "price"
                            )

            st.session_state.last_refresh = datetime.now()
            add_notification("Currency rates updated successfully", "success")
            return True
        else:
            add_notification("Failed to update any currency rates", "error")
            return False

    except Exception as e:
        add_notification(f"Error updating rates: {str(e)}", "error")
        return False


def display_crypto_market_visualization():
    """Display a crypto market visualization using a better scaling approach"""
    
    # Market cap estimates or scaling factor for common cryptocurrencies
    # These are approximate values that would need to be updated regularly in a real app
    # In a production app, you'd fetch these from an API
    market_cap_estimates = {
        "BTC": 1000,  # Bitcoin
        "ETH": 500,   # Ethereum
        "BNB": 100,   # Binance Coin
        "SOL": 80,    # Solana
        "XRP": 70,    # Ripple
        "ADA": 50,    # Cardano
        "AVAX": 40,   # Avalanche
        "DOGE": 30,   # Dogecoin
        "DOT": 25,    # Polkadot
        "LINK": 20,   # Chainlink
        "MATIC": 15,  # Polygon
        "LTC": 12,    # Litecoin
        "XLM": 10,    # Stellar
        "UNI": 8,     # Uniswap
        "ATOM": 5,    # Cosmos
        "USDT": 80,   # Tether
        "USDC": 30,   # USD Coin
        "BUSD": 10    # Binance USD
    }
    
    # Get data for the visualization
    crypto_data = []
    
    for sub in st.session_state.subscriptions:
        if sub["current_rate"] is not None:
            # Calculate percent change
            percent_change = 0
            if sub.get("previous_close") is not None:
                percent_change = ((sub["current_rate"] - sub["previous_close"]) / sub["previous_close"]) * 100
            elif sub.get("last_rate") is not None:
                percent_change = ((sub["current_rate"] - sub["last_rate"]) / sub["last_rate"]) * 100
            
            # Use market cap estimate if available, otherwise use a default value
            market_value = market_cap_estimates.get(sub["base"], 10)
            
            crypto_data.append({
                "coin": sub["base"],
                "quote": sub["quote"],
                "price": sub["current_rate"],
                "value": market_value,
                "change": percent_change
            })
    
    if not crypto_data:
        st.info("No crypto data available yet. Add some cryptocurrency pairs to see the visualization.")
        return
    
    # Create a treemap
    fig = go.Figure(go.Treemap(
        labels=[f"{d['coin']}/{d['quote']}: ${d['price']:.2f}" for d in crypto_data],
        parents=["" for _ in crypto_data],
        values=[d["value"] for d in crypto_data],  # Using our market cap estimates instead of price
        textinfo="label",
        hovertemplate='<b>%{label}</b><br>Change: %{customdata:.2f}%<extra></extra>',
        customdata=[[d["change"]] for d in crypto_data],
        marker=dict(
            colors=[
                '#4CAF50' if d["change"] > 1 else 
                '#8BC34A' if d["change"] > 0 else 
                '#F44336' if d["change"] < -1 else 
                '#FFCDD2' 
                for d in crypto_data
            ],
            colorscale=None,  # Use the colors defined above
            showscale=False
        ),
    ))
    
    # Update layout
    fig.update_layout(
        height=300,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="#121212",
        plot_bgcolor="#121212",
        font=dict(color="white")
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Add a small description
    st.markdown("""
    <div style="margin-top: -15px; text-align: center; font-size: 0.8rem; color: #888;">
    Treemap shows relative market importance with area proportional to market capitalization.
    Green indicates positive change, red indicates negative change.
    </div>
    """, unsafe_allow_html=True)
    
    # Add a table view of the data as well
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("#### Top Gainers")
        # Sort by change, show top 3 gainers
        gainers = sorted([d for d in crypto_data if d["change"] > 0], 
                        key=lambda x: x["change"], reverse=True)
        
        if gainers:
            for coin in gainers[:3]:
                st.markdown(f"""
                <div style="display:flex; justify-content:space-between; margin-bottom:5px; 
                            background-color:#1E1E1E; padding:8px; border-radius:5px;">
                    <span style="font-weight:bold; color:white;">{coin['coin']}/{coin['quote']}</span>
                    <span style="color:#4CAF50; font-weight:bold;">+{coin['change']:.2f}%</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("<div style='color:white;'>No gainers found</div>", unsafe_allow_html=True)

    with col2:
        st.markdown("#### Top Losers")
        # Sort by change, show top 3 losers
        losers = sorted([d for d in crypto_data if d["change"] < 0], 
                        key=lambda x: x["change"])
        
        if losers:
            for coin in losers[:3]:
                st.markdown(f"""
                <div style="display:flex; justify-content:space-between; margin-bottom:5px; 
                            background-color:#1E1E1E; padding:8px; border-radius:5px;">
                    <span style="font-weight:bold; color:white;">{coin['coin']}/{coin['quote']}</span>
                    <span style="color:#F44336; font-weight:bold;">{coin['change']:.2f}%</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("<div style='color:white;'>No losers found</div>", unsafe_allow_html=True)

    with col3:
        st.markdown("#### Highest Volume")
        
        # In a real implementation, you would fetch actual trading volume data from an API
        # For now, we'll simulate it based on market cap and price
        volume_data = []
        for coin in crypto_data:
            # Create a realistic volume simulation
            # In reality, BTC and ETH typically have the highest volumes
            # Base volume on market cap (value) with some randomization
            base_volume = coin["value"] * 1_000_000  # Scale to millions
            
            # Add extra volume for certain major coins
            if coin["coin"] == "BTC":
                base_volume *= 2.5
            elif coin["coin"] == "ETH":
                base_volume *= 2.0
            elif coin["coin"] in ["USDT", "USDC", "BNB"]:
                base_volume *= 1.5
                
            # Add some randomness (±30%)
            randomness = 0.7 + (random.random() * 0.6)  # 0.7 to 1.3
            volume = base_volume * randomness
            
            volume_data.append({
                "coin": coin["coin"],
                "quote": coin["quote"],
                "volume": volume
            })
        
        # Sort by volume
        volume_data = sorted(volume_data, key=lambda x: x["volume"], reverse=True)
        
        for coin in volume_data[:3]:
            # Format volume for display
            if coin['volume'] > 1_000_000_000:
                vol_formatted = f"${coin['volume']/1_000_000_000:.1f}B"
            elif coin['volume'] > 1_000_000:
                vol_formatted = f"${coin['volume']/1_000_000:.1f}M"
            else:
                vol_formatted = f"${coin['volume']/1_000:.1f}K"
                
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; margin-bottom:5px; 
                        background-color:#1E1E1E; padding:8px; border-radius:5px;">
                <span style="font-weight:bold; color:white;">{coin['coin']}/{coin['quote']}</span>
                <span style="color:white;">{vol_formatted}</span>
            </div>
            """, unsafe_allow_html=True)

# Function to calculate percentage variation
# All currencies (both base and quote) will now appear on the map
# Variations are properly aggregated when multiple currency pairs affect the same country
# Inverts the variation value for quote currencies (since a positive change in EUR/USD is negative for USD)
# Function to calculate percentage variation using previous close
def calculate_percentage_variation(subscriptions):
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

# Add this function to calculate market volatility
def calculate_market_volatility(subscriptions):
    """
    Calculate a market volatility index based on the short-term 
    movement of all currency pairs.
    
    Args:
        subscriptions: List of subscription dictionaries containing currency data
    
    Returns:
        volatility_index: Overall market volatility score (0-100)
        pair_volatility: Dictionary of volatility scores by pair
    """
    if not subscriptions:
        return 0, {}
    
    pair_volatility = {}
    volatility_scores = []
    
    for sub in subscriptions:
        # Skip pairs with insufficient data
        if sub.get("current_rate") is None:
            continue
            
        # Get reference price for calculating volatility
        reference_rate = None
        if sub.get("previous_close") is not None:
            reference_rate = sub["previous_close"]
        elif sub.get("last_rate") is not None:
            reference_rate = sub["last_rate"]
            
        if reference_rate is None:
            continue
            
        # Calculate percent change as basic volatility measure
        percent_change = abs((sub["current_rate"] - reference_rate) / reference_rate * 100)
        
        # Get historical data if available
        pair_key = f"{sub['base'].lower()}_{sub['quote'].lower()}"
        historical_volatility = 0
        
        if pair_key in st.session_state.rate_history and len(st.session_state.rate_history[pair_key]) > 3:
            # Get recent history
            history = st.session_state.rate_history[pair_key][-20:]  # Last 20 data points
            rates = [point["rate"] for point in history]
            
            # Calculate standard deviation as a volatility measure if we have enough data
            if len(rates) >= 3:
                std_dev = np.std(rates)
                mean_rate = np.mean(rates)
                if mean_rate > 0:
                    # Coefficient of variation (normalized standard deviation)
                    historical_volatility = (std_dev / mean_rate) * 100
        
        # Combine recent change and historical volatility
        # Weight recent change more heavily (70%) than historical volatility (30%)
        volatility_score = (0.7 * percent_change) + (0.3 * historical_volatility)
        
        # Store pair-specific volatility
        pair_volatility[f"{sub['base']}/{sub['quote']}"] = volatility_score
        volatility_scores.append(volatility_score)
    
    # Calculate overall market volatility index (scale 0-100)
    # We use the 80th percentile to reduce impact of outliers
    if volatility_scores:
        # Get the 80th percentile of all volatility scores
        high_volatility = np.percentile(volatility_scores, 80) if len(volatility_scores) >= 5 else max(volatility_scores)
        
        # Scale to 0-100 range (assuming 5% change is very volatile -> 100)
        # This scaling factor can be adjusted based on normal market conditions
        volatility_index = min(100, (high_volatility / 5) * 100)
    else:
        volatility_index = 0
    
    return volatility_index, pair_volatility

# Add this to display the market volatility index
def display_volatility_index(volatility_index, pair_volatility):
    """
    Display the market volatility index as a gauge and pair-specific volatility.
    
    Args:
        volatility_index: Overall market volatility score (0-100)
        pair_volatility: Dictionary of volatility scores by pair
    """
    # Create a gauge chart for the volatility index
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=volatility_index,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Market Volatility Index", 'font': {'color': 'white', 'size': 16}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
            'bar': {'color': "#4D9BF5"},
            'bgcolor': "gray",
            'borderwidth': 2,
            'bordercolor': "white",
            'steps': [
                {'range': [0, 25], 'color': '#4CAF50'},  # Low volatility - green
                {'range': [25, 50], 'color': '#FFC107'},  # Medium volatility - amber
                {'range': [50, 75], 'color': '#FF9800'},  # Medium-high volatility - orange
                {'range': [75, 100], 'color': '#F44336'}  # High volatility - red
            ],
        }
    ))
    
    # Apply dark theme styling to gauge
    fig.update_layout(
        height=200,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="#121212",
        font=dict(color="white", size=12)
    )
    
    # Display the gauge
    st.plotly_chart(fig, use_container_width=True)
    
    # Display pair-specific volatility in a table
    if pair_volatility:
        # Sort pairs by volatility (highest to lowest)
        sorted_pairs = sorted(pair_volatility.items(), key=lambda x: x[1], reverse=True)
        
        # Create a small table with the most volatile pairs
        st.markdown("#### Most Volatile Pairs")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Format as a simple table
            for pair, score in sorted_pairs[:3]:  # Top 3 pairs
                # Color code based on volatility
                if score > 4:
                    color = "#F44336"  # Red
                elif score > 2:
                    color = "#FF9800"  # Orange
                elif score > 1:
                    color = "#FFC107"  # Amber
                else:
                    color = "#4CAF50"  # Green
                
                st.markdown(f"<div style='display:flex;justify-content:space-between;'><span>{pair}</span><span style='color:{color};font-weight:bold;'>{score:.2f}</span></div>", unsafe_allow_html=True)
        
        with col2:
            # Show the next 3 pairs
            for pair, score in sorted_pairs[3:6]:  # Next 3 pairs
                # Color code based on volatility
                if score > 4:
                    color = "#F44336"  # Red
                elif score > 2:
                    color = "#FF9800"  # Orange
                elif score > 1:
                    color = "#FFC107"  # Amber
                else:
                    color = "#4CAF50"  # Green
                
                st.markdown(f"<div style='display:flex;justify-content:space-between;'><span>{pair}</span><span style='color:{color};font-weight:bold;'>{score:.2f}</span></div>", unsafe_allow_html=True)

# Prepare data for the geomap
def prepare_map_data(variations, currency_to_country):
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


# The callback just sets a flag
def refresh_news_callback():
    st.session_state.refresh_news_clicked = True

# Call this function right after your session state initialization
setup_auto_refresh()

# # Display the logo
# logo_url = ""
# st.image(logo_url, width=50, align=right)

st.markdown("""
<style>
    .block-container {
        padding-top: 1rem !important;
    }
    
    /* This helps reduce space around the header */
    header {
        visibility: hidden;
    }
    
    /* Optional: Reduce space taken by the sidebar header */
    #MainMenu {visibility: hidden;}
    .stDeployButton {display:none;}
</style>
""", unsafe_allow_html=True)

# Calculate volatility indices first
volatility_index, pair_volatility = calculate_market_volatility(st.session_state.subscriptions)

# Main header area with logo and volatility index
header_col1, header_col2 = st.columns([2, 1])

with header_col1:
    # Dynamic title based on market type
    if st.session_state.market_type == 'FX':
        st.markdown("<h1 class='main-header'>💱 FX Market Monitor</h1>", unsafe_allow_html=True)
        
        # Display the text with a link on the word "sentiment"
        sentiment_url = "https://huggingface.co/yiyanghkust/finbert-tone"
        st.markdown(
            f"Real-time FX rates and news sentiment monitoring [.]({sentiment_url})",
            unsafe_allow_html=True
        )
    else:
        st.markdown("<h1 class='main-header'>₿ Crypto Market Monitor</h1>", unsafe_allow_html=True)
        
        # Updated subtitle for crypto mode
        sentiment_url = "https://huggingface.co/yiyanghkust/finbert-tone"
        st.markdown(
            f"Real-time cryptocurrency prices and market sentiment [.]({sentiment_url})",
            unsafe_allow_html=True
        )

with header_col2:
    # Volatility index calculation remains the same
    volatility_index, pair_volatility = calculate_market_volatility(st.session_state.subscriptions)
    
    # Create a compact volatility gauge
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=volatility_index,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Market Volatility", 'font': {'color': 'white', 'size': 14}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white", 'visible': False},
            'bar': {'color': "#4D9BF5"},
            'bgcolor': "gray",
            'borderwidth': 1,
            'bordercolor': "white",
            'steps': [
                {'range': [0, 25], 'color': '#4CAF50'},  # Low volatility - green
                {'range': [25, 50], 'color': '#FFC107'},  # Medium volatility - amber
                {'range': [50, 75], 'color': '#FF9800'},  # Medium-high volatility - orange
                {'range': [75, 100], 'color': '#F44336'}  # High volatility - red
            ],
        }
    ))
    
    # Make the gauge compact
    fig.update_layout(
        height=120,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="#121212",
        font=dict(color="white", size=10)
    )
    
    # Display the gauge
    st.plotly_chart(fig, use_container_width=True)
    
    # Add most volatile pair below the gauge
    if pair_volatility:
        # Get the most volatile pair
        most_volatile_pair, highest_score = sorted(pair_volatility.items(), key=lambda x: x[1], reverse=True)[0]
        
        # Determine color based on volatility
        if highest_score > 4:
            color = "#F44336"  # Red
        elif highest_score > 2:
            color = "#FF9800"  # Orange
        elif highest_score > 1:
            color = "#FFC107"  # Amber
        else:
            color = "#4CAF50"  # Green
            
        # Display in compact format
        st.markdown(f"<div style='background-color:#121212;padding:5px;border-radius:5px;margin-top:-15px;'><span style='color:white;font-size:0.8rem;'>Most volatile: </span><span style='color:white;font-weight:bold;'>{most_volatile_pair}</span> <span style='color:{color};font-weight:bold;float:right;'>{highest_score:.2f}</span></div>", unsafe_allow_html=True)
# Add a separator
st.markdown("<hr style='margin-top:0.5rem; margin-bottom:1rem;'>", unsafe_allow_html=True)

# Create an expandable section for detailed volatility information
with st.expander("View Detailed Market Volatility Information", expanded=False):
    vol_col1, vol_col2, vol_col3 = st.columns([1.5, 1, 1])
    
    with vol_col1:
        # Pairs volatility
        st.markdown("#### Volatility by Pair")
        
        if pair_volatility:
            # Sort pairs by volatility (highest to lowest)
            sorted_pairs = sorted(pair_volatility.items(), key=lambda x: x[1], reverse=True)
            
            # Create two columns for the pairs
            pair_col1, pair_col2 = st.columns(2)
            
            with pair_col1:
                # First half of the pairs
                for i, (pair, score) in enumerate(sorted_pairs):
                    if i >= len(sorted_pairs) / 2:
                        break
                        
                    # Color code based on volatility
                    if score > 4:
                        color = "#F44336"  # Red
                    elif score > 2:
                        color = "#FF9800"  # Orange
                    elif score > 1:
                        color = "#FFC107"  # Amber
                    else:
                        color = "#4CAF50"  # Green
                    
                    st.markdown(f"<div style='display:flex;justify-content:space-between;'><span>{pair}</span><span style='color:{color};font-weight:bold;'>{score:.2f}</span></div>", unsafe_allow_html=True)
            
            with pair_col2:
                # Second half of the pairs
                for i, (pair, score) in enumerate(sorted_pairs):
                    if i < len(sorted_pairs) / 2:
                        continue
                        
                    # Color code based on volatility
                    if score > 4:
                        color = "#F44336"  # Red
                    elif score > 2:
                        color = "#FF9800"  # Orange
                    elif score > 1:
                        color = "#FFC107"  # Amber
                    else:
                        color = "#4CAF50"  # Green
                    
                    st.markdown(f"<div style='display:flex;justify-content:space-between;'><span>{pair}</span><span style='color:{color};font-weight:bold;'>{score:.2f}</span></div>", unsafe_allow_html=True)
    
    with vol_col2:
        # Market status
        st.markdown("#### Market Status")
        
        # Determine market status based on volatility
        if volatility_index < 25:
            status_color = "#4CAF50"  # Green
            status_text = "Low Volatility"
            status_desc = "Markets are calm with minimal price movement."
        elif volatility_index < 50:
            status_color = "#FFC107"  # Amber
            status_text = "Normal Volatility"
            status_desc = "Typical intraday movements within expected ranges."
        elif volatility_index < 75:
            status_color = "#FF9800"  # Orange
            status_text = "Elevated Volatility"
            status_desc = "Increased market movements. Monitor positions closely."
        else:
            status_color = "#F44336"  # Red
            status_text = "High Volatility"
            status_desc = "Extreme market movements. Use caution when trading."
        
        # Display status with color coding
        st.markdown(f"<div style='background-color:#121212;padding:10px;border-radius:5px;'><p style='color:{status_color};font-weight:bold;font-size:18px;margin-bottom:5px;'>{status_text}</p><p style='color:white;font-size:14px;'>{status_desc}</p></div>", unsafe_allow_html=True)
        
        # Add a tip based on the volatility
        st.markdown("#### Trading Tip")
        if volatility_index < 25:
            st.info("Consider range-bound strategies in this low volatility environment.")
        elif volatility_index < 50:
            st.info("Normal market conditions favor balanced trading approaches.")
        elif volatility_index < 75:
            st.warning("Consider reducing position sizes in elevated volatility.")
        else:
            st.error("High volatility suggests caution and reduced exposure.")
    
    with vol_col3:
        # Volatility trend chart
        st.markdown("#### Volatility Trend")
        
        # Check if we have volatility history
        if 'volatility_history' not in st.session_state:
            st.session_state.volatility_history = []
        
        # Add current volatility to history (keep last 30 points)
        current_time = datetime.now()
        st.session_state.volatility_history.append({
            "timestamp": current_time,
            "volatility": volatility_index
        })
        
        # Keep only the latest 30 entries
        if len(st.session_state.volatility_history) > 30:
            st.session_state.volatility_history = st.session_state.volatility_history[-30:]
        
        # Create a trend chart if we have enough data
        if len(st.session_state.volatility_history) > 1:
            trend_df = pd.DataFrame(st.session_state.volatility_history)
            
            # Create a line chart
            fig = px.line(trend_df, x="timestamp", y="volatility", 
                         height=200)
            
            # Apply dark theme styling
            fig.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="#121212",
                plot_bgcolor="#121212",
                font=dict(color="#FFFFFF"),
                xaxis=dict(
                    showgrid=False,
                    zeroline=False,
                    tickfont=dict(color="#FFFFFF", size=10)
                ),
                yaxis=dict(
                    range=[0, 100],
                    showgrid=True,
                    gridcolor="#333333",
                    tickcolor="#FFFFFF",
                    tickfont=dict(color="#FFFFFF", size=10)
                )
            )
            
            # Change line color and add reference zones
            fig.update_traces(line=dict(color="#4D9BF5", width=2))
            
            # Add color zones
            fig.add_hrect(y0=0, y1=25, fillcolor="#4CAF50", opacity=0.1, line_width=0)
            fig.add_hrect(y0=25, y1=50, fillcolor="#FFC107", opacity=0.1, line_width=0)
            fig.add_hrect(y0=50, y1=75, fillcolor="#FF9800", opacity=0.1, line_width=0)
            fig.add_hrect(y0=75, y1=100, fillcolor="#F44336", opacity=0.1, line_width=0)
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Collecting volatility trend data...")


# Fxbook sentiment

# Add a separator
st.markdown("<hr style='margin-top:0.5rem; margin-bottom:1rem;'>", unsafe_allow_html=True)

# Add a collapsible section for trader sentiment overview
with st.expander("View Trader Sentiment Overview", expanded=False):
    sent_col1, sent_col2, sent_col3 = st.columns([1, 1, 1])
    
    # First load sentiment data if needed
    if 'fxbook_sentiment_data' not in st.session_state or not st.session_state.fxbook_sentiment_data:
        with st.spinner("Loading sentiment data..."):
            update_all_sentiment_data()
    
    sentiment_data = st.session_state.get('fxbook_sentiment_data', {})
    pairs_data = sentiment_data.get('data', {})
    
    with sent_col1:
        st.markdown("#### Top Bullish Pairs")
        
        # Find most bullish pairs (highest long percentage)
        bullish_pairs = []
        for pair, data in pairs_data.items():
            long_pct = data.get('long_percentage', 0)
            if long_pct:
                bullish_pairs.append((pair, long_pct))
        
        # Sort by long percentage (highest first)
        bullish_pairs.sort(key=lambda x: x[1], reverse=True)
        
        # Display top 3 bullish pairs
        for pair, long_pct in bullish_pairs[:3]:
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; margin-bottom:5px; 
                        background-color:#1E1E1E; padding:8px; border-radius:5px;">
                <span style="font-weight:bold; color:white;">{pair}</span>
                <span style="color:#4CAF50; font-weight:bold;">{long_pct}% Long</span>
            </div>
            """, unsafe_allow_html=True)
    
    with sent_col2:
        st.markdown("#### Top Bearish Pairs")
        
        # Find most bearish pairs (highest short percentage)
        bearish_pairs = []
        for pair, data in pairs_data.items():
            short_pct = data.get('short_percentage', 0)
            if short_pct:
                bearish_pairs.append((pair, short_pct))
        
        # Sort by short percentage (highest first)
        bearish_pairs.sort(key=lambda x: x[1], reverse=True)
        
        # Display top 3 bearish pairs
        for pair, short_pct in bearish_pairs[:3]:
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; margin-bottom:5px; 
                        background-color:#1E1E1E; padding:8px; border-radius:5px;">
                <span style="font-weight:bold; color:white;">{pair}</span>
                <span style="color:#F44336; font-weight:bold;">{short_pct}% Short</span>
            </div>
            """, unsafe_allow_html=True)
    
    with sent_col3:
        # Create a quick sentiment gauge for the most active pair (if available)
        most_active_pair = None
        highest_positions = 0
        
        for pair, data in pairs_data.items():
            positions = data.get('detailed', {}).get('short', {}).get('positions', '0')
            try:
                positions_count = int(positions.split()[0].replace(',', ''))
                if positions_count > highest_positions:
                    highest_positions = positions_count
                    most_active_pair = pair
            except:
                continue
        
        if most_active_pair:
            st.markdown(f"#### Most Active: {most_active_pair}")
            
            pair_data = pairs_data[most_active_pair]
            long_pct = pair_data.get('long_percentage', 50)
            
            # Create sentiment gauge
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=long_pct,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Long Sentiment", 'font': {'color': 'white', 'size': 14}},
                gauge={
                    'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
                    'bar': {'color': "#4CAF50" if long_pct > 50 else "#F44336"},
                    'bgcolor': "gray",
                    'borderwidth': 1,
                    'bordercolor': "white",
                    'steps': [
                        {'range': [0, 100], 'color': "#1E1E1E"}
                    ],
                },
                number={'suffix': "%", 'font': {'color': 'white'}}
            ))
            
            # Make the gauge compact
            fig.update_layout(
                height=150,
                margin=dict(l=10, r=10, t=30, b=10),
                paper_bgcolor="#121212",
                font=dict(color="white", size=12)
            )
            
            # Display the gauge
            st.plotly_chart(fig, use_container_width=True)
            
            # Add a note with number of positions
            positions = pair_data.get('detailed', {}).get('short', {}).get('positions', 'Unknown')
            st.markdown(f"<div style='text-align:center;'>Active positions: {positions}</div>", unsafe_allow_html=True)
        else:
            st.info("No activity data available")
    
    # Add a link to the full sentiment dashboard
    st.markdown("""
    <div style="text-align:center; margin-top:15px;">
        <a href="./Trader_Sentiment" target="_self" style="background-color:#4D9BF5; color:white; padding:8px 16px; border-radius:5px; text-decoration:none; font-weight:bold;">
            View Full Sentiment Dashboard
        </a>
    </div>
    """, unsafe_allow_html=True)

# Right sidebar for subscription management
with st.sidebar:

    # Add some space
    st.markdown("---")
    st.subheader("Navigation")
    
    # Button to navigate to News Summarizer
    if st.button("📰 Go to News Summarizer", use_container_width=True):
        st.switch_page("pages/2_News_Summarizer.py")
    
    # Button to return to home
    if st.button("🏠 Return to Home", use_container_width=True):
        st.switch_page("Home.py")
        
    st.header("Market Selection")
     
    # Create toggle buttons for market selection
    col1, col2 = st.columns(2)
    
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
    else:
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
    
    # Add a separator
    st.markdown("<hr>", unsafe_allow_html=True)
    
    # Handle market switching logic
    if fx_button and st.session_state.market_type != 'FX':
        # Save current crypto subscriptions
        st.session_state.crypto_subscriptions = st.session_state.subscriptions
        
        # Switch to FX
        st.session_state.market_type = 'FX'
        
        # Restore FX subscriptions
        st.session_state.subscriptions = st.session_state.fx_subscriptions
        
        # Clear cached news and refresh data
        st.session_state.cached_news = []
        st.session_state.last_news_fetch = None
        
        # Update available currencies
        available_currencies = fx_currencies
        
        # Notify user
        add_notification("Switched to FX Market", "system")
        
        # Rerun to refresh the UI
        st.rerun()
        
    if crypto_button and st.session_state.market_type != 'Crypto':
        # Save current FX subscriptions
        st.session_state.fx_subscriptions = st.session_state.subscriptions
        
        # Switch to Crypto
        st.session_state.market_type = 'Crypto'
        
        # Restore crypto subscriptions
        st.session_state.subscriptions = st.session_state.crypto_subscriptions
        
        # Clear cached news and refresh data
        st.session_state.cached_news = []
        st.session_state.last_news_fetch = None
        
        # Update available currencies
        available_currencies = crypto_currencies
        
        # Notify user
        add_notification("Switched to Crypto Market", "system")
        
        # Rerun to refresh the UI
        st.rerun()

    # After your existing navigation buttons, add:
    if st.button("👥 Go to Sentiment Dashboard", use_container_width=True):
        st.switch_page("pages/3_Trader_Sentiment.py")

    # Subscription management
    st.header("Currency Subscriptions")

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
    
    
    st.header("Manual Refreshes Calendar")
    if st.button("📅 Refresh Economic Calendar"):
        fetch_all_economic_events(force=True)
        add_notification("Economic calendar refreshed", "success")

    # Manual refresh button
    st.button("🔄 Refresh Rates", on_click=update_rates)
    st.button("📰 Refresh News", on_click=refresh_news_callback)
    st.button("🔄📰 Refresh Both", on_click=manual_refresh_rates_and_news)

    st.sidebar.button("👥 Refresh Sentiment", on_click=lambda: update_all_sentiment_data(force=True))

    st.sidebar.checkbox("Run background sentiment analysis", 
                    key="run_background_sentiment",
                    value=True,
                    help="Enable to analyze sentiment in the background (may slow down the app)")

    # Then in your sidebar, for the auto-refresh toggle:
    auto_refresh = st.sidebar.checkbox("Auto-refresh (Rates: 15s, News: 5min)", value=st.session_state.auto_refresh)
    if auto_refresh != st.session_state.auto_refresh:
        st.session_state.auto_refresh = auto_refresh
        # This will force the page to reload with the new auto_refresh setting
        st.rerun()

    # In your sidebar, show the last refresh times (optional)
    if st.session_state.auto_refresh:
        if 'last_auto_refresh_time' in st.session_state and st.session_state.last_auto_refresh_time:
            st.sidebar.caption(f"Last rates refresh: {st.session_state.last_auto_refresh_time.strftime('%H:%M:%S')}")
        
        if 'last_news_auto_refresh_time' in st.session_state and st.session_state.last_news_auto_refresh_time:
            st.sidebar.caption(f"Last news refresh: {st.session_state.last_news_auto_refresh_time.strftime('%H:%M:%S')}")


    # Check the flag elsewhere in your code
    if st.session_state.refresh_news_clicked:
        # Do the refresh
        news_items = fetch_news(use_mock_fallback=True, force=True)
        # Reset the flag
        st.session_state.refresh_news_clicked = False
    else:
        # Normal fetch
        news_items = fetch_news(use_mock_fallback=True)

    # run_sentiment_analysis = st.sidebar.checkbox("Analyze sentiment", value=False, 
    #                                             help="Run sentiment analysis on new articles (slower)")
    # st.session_state.run_sentiment_analysis = run_sentiment_analysis    

    # Show notification history
    st.header("Notifications")

    if st.button("Clear All Notifications"):
        st.session_state.notifications = []

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


# Calculate percentage variations
variations = calculate_percentage_variation(st.session_state.subscriptions)

# Prepare data for the geomap
map_data = prepare_map_data(variations, currency_to_country)

# Page layout: Two columns for the main content
col4, col5 = st.columns([3, 1])  # Adjust the column widths to give more space to the map

with col4:

    # Conditionally display the geomaps
    if map_data:
        if st.session_state.market_type == 'FX':
            # Use existing FX maps code
            # Create a layout with three columns
            col1, col2, col3 = st.columns(3)

            # Map for the US continent
            # Map for the US continent
            with col1:
                us_locations = ['United States', 'Canada', 'Mexico']
                fig_us = go.Figure(data=go.Choropleth(
                    locations=[data["location"] for data in map_data if data["location"] in us_locations],
                    z=[data["variation"] for data in map_data if data["location"] in us_locations],
                    locationmode='country names',
                    colorscale='RdBu',
                    showscale=False,  # Hide color scale for US map
                    text=[f'{data["variation"]:.2f}%' for data in map_data if data["location"] in us_locations],
                    hoverinfo='text'
                ))

                fig_us.update_layout(
                    geo=dict(
                        showframe=False,
                        showcoastlines=False,
                        projection_type='equirectangular',
                        center=dict(lat=37.0902, lon=-95.7129),
                        scope='north america'
                    ),
                    height=300,
                    margin=dict(l=0, r=0, t=0, b=0)
                )

                st.plotly_chart(fig_us, use_container_width=True)

            # Map for Europe
            with col2:
                # Create a list of European countries that includes both Eurozone and UK
                euro_countries = currency_to_country['EUR']
                if not isinstance(euro_countries, list):
                    euro_countries = [euro_countries]
                
                # Explicitly add the UK to our Europe map
                uk_location = currency_to_country.get('GBP', 'United Kingdom')
                europe_locations = euro_countries + [uk_location]
                
                # Filter the map_data for European countries including UK
                euro_map_data = [data for data in map_data if data["location"] in europe_locations]
                
                # Debug to verify UK is included
                uk_data = [data for data in map_data if data["location"] == uk_location]
                if uk_data:
                    print(f"UK data found: {uk_data}")
                else:
                    print("UK data not found in map_data")
                
                if euro_map_data:
                    # When setting up the Europe map, make sure to adjust the scope
                    fig_europe = go.Figure(data=go.Choropleth(
                        locations=[data["location"] for data in euro_map_data],
                        z=[data["variation"] for data in euro_map_data],
                        locationmode='country names',
                        colorscale='RdBu',
                        showscale=False,
                        text=[f'{data["location"]}: {data["variation"]:.2f}%' for data in euro_map_data],
                        hoverinfo='text'
                    ))

                    # Adjust Europe map settings to ensure UK is visible
                    fig_europe.update_layout(
                        geo=dict(
                            showframe=False,
                            showcoastlines=False,
                            projection_type='equirectangular',
                            center=dict(lat=50.0, lon=10.0),  # Adjusted to include UK better
                            scope='europe',
                            lonaxis=dict(range=[-15, 30]),  # Ensure UK is in longitude range
                            lataxis=dict(range=[35, 65])     # Adjusted latitude range
                        ),
                        height=300,
                        margin=dict(l=0, r=0, t=0, b=0)
                    )

                    st.plotly_chart(fig_europe, use_container_width=True)
                else:
                    st.info("No variation data available for European countries")

            # Map for Asia - SHOWING SCALE
            with col3:
                asia_countries = ['China', 'Japan', 'India', 'Singapore', 'Hong Kong']
                
                # Filter the map_data for Asian countries
                asia_map_data = [data for data in map_data if data["location"] in asia_countries]
                
                if asia_map_data:
                    fig_asia = go.Figure(data=go.Choropleth(
                        locations=[data["location"] for data in asia_map_data],
                        z=[data["variation"] for data in asia_map_data],
                        locationmode='country names',
                        colorscale='RdBu',
                        showscale=True,  # Show color scale ONLY for Asia map
                        colorbar_title="% Variation",
                        colorbar=dict(
                            title="% Variation",
                            thickness=15,
                            len=0.7,
                            x=0.9,
                        ),
                        text=[f'{data["variation"]:.2f}%' for data in asia_map_data],
                        hoverinfo='text'
                    ))

                    fig_asia.update_layout(
                        geo=dict(
                            showframe=False,
                            showcoastlines=False,
                            projection_type='equirectangular',
                            center=dict(lat=35.8617, lon=104.1954),
                            scope='asia'
                        ),
                        height=300,
                        margin=dict(l=0, r=0, t=0, b=0)
                    )

                    st.plotly_chart(fig_asia, use_container_width=True)
                else:
                    st.info("No variation data available for Asian countries")
        else:
            # Use crypto visualization instead
            st.subheader("Cryptocurrency Market Overview")
            display_crypto_market_visualization()

    # Currency Rates middle section
    st.header("Currency Rates")

    # Add collapse/expand all buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Collapse All Cards"):
            st.session_state.collapse_all_cards = True
            st.rerun()
    with col2:
        if st.button("Expand All Cards"):
            st.session_state.collapse_all_cards = False
            st.rerun()

    # Create a card for each subscription
    for i, sub in enumerate(st.session_state.subscriptions):
        # Create a unique key for this subscription
        key_base = f"{sub['base']}_{sub['quote']}_{i}"
        
        # Calculate percentage change to show in the header
        percent_change_text = ""
        if sub["current_rate"] is not None:
            # Determine reference rate
            reference_rate = None
            if sub.get("previous_close") is not None:
                reference_rate = sub["previous_close"]
            elif sub.get("last_rate") is not None:
                reference_rate = sub["last_rate"]
                
            # Calculate percent change if reference rate is available
            if reference_rate is not None:
                percent_change = ((sub["current_rate"] - reference_rate) / reference_rate) * 100
                sign = "+" if percent_change > 0 else ""
                percent_change_text = f" {sign}{percent_change:.2f}%"
        
        # Create a container for the card with a border and padding
        with st.container():
            st.markdown("""
            <style>
            .header-container {
                background-color: #1E1E1E;
                border-radius: 5px 5px 0 0;
                padding: 10px 15px;
                margin-bottom: 0;
                border: 1px solid #333;
                border-bottom: none;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Create a visually distinct header
            st.markdown('<div class="header-container">', unsafe_allow_html=True)
            header_cols = st.columns([2, 1, 3])
            
            with header_cols[0]:
                # Currency pair
                st.markdown(f"**{sub['base']}/{sub['quote']}**")
            
            with header_cols[1]:
                # Percentage change with color
                if percent_change_text:
                    color = "green" if "+" in percent_change_text else "red" if "-" in percent_change_text else "gray"
                    st.markdown(f"<span style='color:{color};font-weight:bold;'>{percent_change_text}</span>", unsafe_allow_html=True)
            
            with header_cols[2]:
                # Get sentiment data for FX pairs
                if st.session_state.market_type == 'FX':
                    sentiment_data = get_sentiment_for_pair(sub['base'], sub['quote'])
                    if sentiment_data:
                        long_pct = sentiment_data.get('long_percentage', 0)
                        short_pct = sentiment_data.get('short_percentage', 0)
                        
                        # Determine if bullish or bearish
                        sentiment_label = "Bullish" if long_pct >= 50 else "Bearish"
                        sentiment_color = "#4CAF50" if long_pct >= 50 else "#F44336"
                        
                        # Create a sentiment bar visualization with percentages
                        st.markdown(f"""
                        <div style="width:100%; display:flex; align-items:center; justify-content:flex-end;">
                            <span style="color:#4CAF50; margin-right:5px; font-size:0.8em; font-weight:bold;">
                                L:{long_pct}%
                            </span>
                            <span style="color:#F44336; margin-right:5px; font-size:0.8em; font-weight:bold;">
                                S:{short_pct}%
                            </span>
                            <span style="color:{sentiment_color}; margin-right:5px; font-size:0.8em; font-weight:bold;">
                                {sentiment_label}
                            </span>
                            <div style="width:80px; height:15px; background:#F44336; border-radius:3px; overflow:hidden;">
                                <div style="width:{long_pct}%; height:100%; background-color:#4CAF50;"></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                elif st.session_state.market_type == 'Crypto':
                    # For crypto, add a placeholder or different visualization
                    pass
                    
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Actual expandable content
            with st.expander("Details", expanded=not st.session_state.collapse_all_cards):
                # Add tabs for Rate Info, Economic Calendar, and Sentiment
                rate_tab, calendar_tab, sentiment_tab = st.tabs(["Rate Info", "Economic Calendar", "Sentiment"])
                
                with rate_tab:
                    # Top row with remove button
                    col3, col4 = st.columns([3, 1])
                    with col4:
                        if st.button("Remove", key=f"remove_{key_base}"):
                            st.session_state.subscriptions.pop(i)
                            add_notification(f"Removed subscription: {sub['base']}/{sub['quote']}", "system")
                            st.rerun()

                    # Rate information
                    if sub["current_rate"] is not None:
                        # Format the current rate with appropriate decimal places
                        if sub["current_rate"] < 0.01:
                            formatted_rate = f"{sub['current_rate']:.6f}"
                        elif sub["current_rate"] < 1:
                            formatted_rate = f"{sub['current_rate']:.4f}"
                        else:
                            formatted_rate = f"{sub['current_rate']:.4f}"
                        
                        # Format the previous close rate if available
                        previous_rate_text = "N/A"
                        if sub.get("previous_close") is not None:
                            prev_rate = sub["previous_close"]
                            if prev_rate < 0.01:
                                previous_rate_text = f"{prev_rate:.6f}"
                            elif prev_rate < 1:
                                previous_rate_text = f"{prev_rate:.4f}"
                            else:
                                previous_rate_text = f"{prev_rate:.4f}"

                        # Determine rate direction and color
                        direction_arrow = ""
                        color = "gray"
                        direction_class = "rate-neutral"
                        
                        # Use previous_close if available, otherwise fall back to last_rate
                        reference_rate = None
                        if sub.get("previous_close") is not None:
                            reference_rate = sub["previous_close"]
                        elif sub.get("last_rate") is not None:
                            reference_rate = sub["last_rate"]
                            
                        if reference_rate is not None:
                            if sub["current_rate"] > reference_rate:
                                direction_arrow = "▲"
                                color = "green"
                                direction_class = "rate-up"
                            elif sub["current_rate"] < reference_rate:
                                direction_arrow = "▼"
                                color = "red"
                                direction_class = "rate-down"

                        # Add rate information to HTML
                        html = f"""
                        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                            <span>Current Rate:</span>
                            <span style="color: {color};">{formatted_rate} {direction_arrow}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                            <span>Previous Close:</span>
                            <span style="color: #6c757d;">{previous_rate_text}</span>
                        </div>
                        """
                        st.markdown(html, unsafe_allow_html=True)

                        # Add percent change if available
                        if reference_rate is not None:
                            percent_change = ((sub["current_rate"] - reference_rate) / reference_rate) * 100
                            change_color = "green" if percent_change > 0 else "red" if percent_change < 0 else "gray"
                            sign = "+" if percent_change > 0 else ""
                            st.markdown(f"**Change:** <span style='color:{change_color};font-weight:bold;'>{sign}{percent_change:.4f}%</span>", unsafe_allow_html=True)
                    else:
                        st.info("Loading rate data...")

                    # Threshold slider
                    new_threshold = st.slider(
                        "Alert threshold (%)",
                        min_value=0.1,
                        max_value=5.0,
                        value=float(sub["threshold"]),
                        step=0.1,
                        key=f"threshold_slider_{key_base}"
                    )

                    if new_threshold != sub["threshold"]:
                        st.session_state.subscriptions[i]["threshold"] = new_threshold
                        add_notification(f"Updated threshold for {sub['base']}/{sub['quote']} to {new_threshold}%", "system")
                
                with calendar_tab:
                    # Existing calendar tab code
                    display_economic_calendar_for_currency_pair(sub['base'], sub['quote'])
                
                with sentiment_tab:
                    # Existing sentiment tab code
                    display_sentiment_tab(sub['base'], sub['quote'])

                # Chart of rate history (outside the tabs)
                blended_display_rate_history(sub)
        
        # Add some space between cards
        st.markdown("<div style='margin-bottom:1rem;'></div>", unsafe_allow_html=True)
      
    # if is_expanded:
    #     st.session_state.expanded_cards.add(card_id)
    # else:
    #     st.session_state.expanded_cards.discard(card_id)

    # # Check if we need initial data
    # if not st.session_state.subscriptions or all(sub["current_rate"] is None for sub in st.session_state.subscriptions):
    #     with st.spinner("Fetching initial rates..."):
    #         update_rates()

    # for i, sub in enumerate(st.session_state.subscriptions):
    #     # Create a unique key for this subscription
    #     key_base = f"{sub['base']}_{sub['quote']}_{i}"
        
    #     # Simple text header for the expander (no HTML)
    #     basic_header = f"{sub['base']}/{sub['quote']}"
        
    #     # Create a card using Streamlit's expander with basic header
    #     with st.expander(basic_header, expanded=not st.session_state.get('collapse_all_cards', True)):
    #         # First thing inside the expander: add an enhanced header with HTML styling
    #         # This replaces the basic header once the expander is open
            
    #         # Calculate percentage change to include in the enhanced header
    #         percent_change_text = ""
    #         if sub["current_rate"] is not None:
    #             # Determine reference rate (previous close or last rate)
    #             reference_rate = None
    #             if sub.get("previous_close") is not None:
    #                 reference_rate = sub["previous_close"]
    #             elif sub.get("last_rate") is not None:
    #                 reference_rate = sub["last_rate"]
                    
    #             # Calculate percent change if reference rate is available
    #             if reference_rate is not None:
    #                 percent_change = ((sub["current_rate"] - reference_rate) / reference_rate) * 100
    #                 change_color = "green" if percent_change > 0 else "red" if percent_change < 0 else "gray"
    #                 sign = "+" if percent_change > 0 else ""
    #                 percent_change_text = f"{sign}{percent_change:.2f}%"
                    
    #                 # Add enhanced header with HTML styling
    #                 st.markdown(f"""
    #                 <div style="display: flex; justify-content: space-between; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid #444;">
    #                     <span style="font-size: 1.2em; font-weight: bold;">{sub['base']}/{sub['quote']}</span>
    #                     <span style="color: {change_color}; font-weight: bold;">{percent_change_text}</span>
    #                 </div>
    #                 """, unsafe_allow_html=True)
                    
    #                 # For FX market, add sentiment data in a row below the header
    #                 if st.session_state.market_type == 'FX':
    #                     # Get sentiment data for this pair
    #                     sentiment_data = get_sentiment_for_pair(sub['base'], sub['quote'])
    #                     if sentiment_data:
    #                         long_pct = sentiment_data.get('long_percentage', 0)
    #                         short_pct = sentiment_data.get('short_percentage', 0)
                            
    #                         # Add sentiment info in a neat format below the header
    #                         st.markdown(f"""
    #                         <div style="display: flex; justify-content: space-between; margin-bottom: 15px; background-color: #1E1E1E; padding: 8px; border-radius: 4px;">
    #                             <span>Trader Sentiment:</span>
    #                             <span>
    #                                 <span style="color: #4CAF50; margin-right: 10px;">Long: {long_pct}%</span>
    #                                 <span style="color: #F44336;">Short: {short_pct}%</span>
    #                             </span>
    #                         </div>
    #                         """, unsafe_allow_html=True)
            
    #         # Add tabs for Rate Info, Economic Calendar, and Sentiment
    #         rate_tab, calendar_tab, sentiment_tab = st.tabs(["Rate Info", "Economic Calendar", "Sentiment"])
            
    #         with rate_tab:
    #             # Top row with remove button
    #             col6, col7 = st.columns([3, 1])
    #             with col7:
    #                 if st.button("Remove", key=f"remove_{key_base}"):
    #                     st.session_state.subscriptions.pop(i)
    #                     add_notification(f"Removed subscription: {sub['base']}/{sub['quote']}", "system")
    #                     st.rerun()

    #             # Rate information
    #             if sub["current_rate"] is not None:
    #                 # Format the current rate with appropriate decimal places
    #                 if sub["current_rate"] < 0.01:
    #                     formatted_rate = f"{sub['current_rate']:.6f}"
    #                 elif sub["current_rate"] < 1:
    #                     formatted_rate = f"{sub['current_rate']:.4f}"
    #                 else:
    #                     formatted_rate = f"{sub['current_rate']:.4f}"
                    
    #                 # Format the previous close rate if available
    #                 previous_rate_text = "N/A"
    #                 if sub.get("previous_close") is not None:
    #                     prev_rate = sub["previous_close"]
    #                     if prev_rate < 0.01:
    #                         previous_rate_text = f"{prev_rate:.6f}"
    #                     elif prev_rate < 1:
    #                         previous_rate_text = f"{prev_rate:.4f}"
    #                     else:
    #                         previous_rate_text = f"{prev_rate:.4f}"

    #                 # Determine rate direction and color
    #                 direction_arrow = ""
    #                 color = "gray"
    #                 direction_class = "rate-neutral"
                    
    #                 # Use previous_close if available, otherwise fall back to last_rate
    #                 reference_rate = None
    #                 if sub.get("previous_close") is not None:
    #                     reference_rate = sub["previous_close"]
    #                 elif sub.get("last_rate") is not None:
    #                     reference_rate = sub["last_rate"]
                        
    #                 if reference_rate is not None:
    #                     if sub["current_rate"] > reference_rate:
    #                         direction_arrow = "▲"
    #                         color = "green"
    #                         direction_class = "rate-up"
    #                     elif sub["current_rate"] < reference_rate:
    #                         direction_arrow = "▼"
    #                         color = "red"
    #                         direction_class = "rate-down"

    #                 # Add rate information to HTML
    #                 html = f"""
    #                 <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
    #                     <span>Current Rate:</span>
    #                     <span class="{direction_class}">{formatted_rate} {direction_arrow}</span>
    #                 </div>
    #                 <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
    #                     <span>Previous Close:</span>
    #                     <span style="color: #6c757d;">{previous_rate_text}</span>
    #                 </div>
    #                 """
    #                 st.markdown(html, unsafe_allow_html=True)

    #                 # Add percent change if available
    #                 if reference_rate is not None:
    #                     percent_change = ((sub["current_rate"] - reference_rate) / reference_rate) * 100
    #                     change_color = "green" if percent_change > 0 else "red" if percent_change < 0 else "gray"
    #                     sign = "+" if percent_change > 0 else ""
    #                     st.markdown(f"**Change:** <span style='color:{change_color};font-weight:bold;'>{sign}{percent_change:.4f}%</span>", unsafe_allow_html=True)
    #             else:
    #                 st.info("Loading rate data...")

    #             # Threshold slider
    #             new_threshold = st.slider(
    #                 "Alert threshold (%)",
    #                 min_value=0.1,
    #                 max_value=5.0,
    #                 value=float(sub["threshold"]),
    #                 step=0.1,
    #                 key=f"threshold_slider_{key_base}"
    #             )

    #             if new_threshold != sub["threshold"]:
    #                 st.session_state.subscriptions[i]["threshold"] = new_threshold
    #                 add_notification(f"Updated threshold for {sub['base']}/{sub['quote']} to {new_threshold}%", "system")
            
    #         with calendar_tab:
    #             # Your existing calendar tab code
    #             display_economic_calendar_for_currency_pair(sub['base'], sub['quote'])
            
    #         with sentiment_tab:
    #             # Your existing sentiment tab code
    #             display_sentiment_tab(sub['base'], sub['quote'])

    #         # Chart of rate history (outside the tabs)
    #         pair_key = f"{sub['base'].lower()}_{sub['quote'].lower()}"
    #         if pair_key in st.session_state.rate_history and len(st.session_state.rate_history[pair_key]) > 1:
    #             # Your existing rate history chart code
    #             history_data = st.session_state.rate_history[pair_key]
    #             df = pd.DataFrame(history_data)
                
    #             # Create dark-themed figure
    #             fig = px.line(df, x="timestamp", y="rate", 
    #                         title=f"{sub['base']}/{sub['quote']} Rate History",
    #                         labels={"timestamp": "Time", "rate": "Rate"})
                
    #             # Calculate range values for better visualization
    #             min_rate = df['rate'].min()
    #             max_rate = df['rate'].max()
    #             rate_range = max_rate - min_rate
                
    #             # If range is very small, create a custom range to make changes more visible
    #             if rate_range < 0.001:
    #                 # Use a small fixed range around the mean
    #                 mean_rate = df['rate'].mean()
    #                 fig.update_yaxes(range=[mean_rate * 0.9995, mean_rate * 1.0005])
    #             elif rate_range < 0.01:
    #                 # Add some padding to min/max values to make changes more visible
    #                 fig.update_yaxes(range=[min_rate * 0.999, max_rate * 1.001])
                
    #             # Apply dark theme styling
    #             fig.update_layout(
    #                     height=300,
    #                     margin=dict(l=0, r=0, t=40, b=0),
    #                     paper_bgcolor="#121212",  # Dark background
    #                     plot_bgcolor="#121212",   # Dark background
    #                     font=dict(color="#FFFFFF"),  # Pure white text for better visibility
    #                     title_font_color="#FFFFFF",  # Pure white title text
    #                     xaxis=dict(
    #                         gridcolor="#333333",  # Darker grid
    #                         tickcolor="#FFFFFF",  # Pure white tick marks
    #                         linecolor="#555555",  # Medium gray axis line
    #                         tickfont=dict(color="#FFFFFF", size=12),  # Brighter, larger tick labels
    #                         title_font=dict(color="#FFFFFF", size=14)  # Brighter, larger axis title
    #                     ),
    #                     yaxis=dict(
    #                         gridcolor="#333333",  # Darker grid
    #                         tickcolor="#FFFFFF",  # Pure white tick marks
    #                         linecolor="#555555",  # Medium gray axis line
    #                         tickfont=dict(color="#FFFFFF", size=12),  # Brighter, larger tick labels
    #                         title_font=dict(color="#FFFFFF", size=14)  # Brighter, larger axis title
    #                     )
    #                 )
                
    #             # Change line color to a brighter shade
    #             fig.update_traces(
    #                 line=dict(color="#4D9BF5", width=2)  # Bright blue line
    #             )
                
    #             st.plotly_chart(fig, use_container_width=True)

# News feed
with col5:
    st.header("Currency News")

    # Filter controls
    sentiment_filter = st.selectbox(
        "Filter by sentiment using Finbert-Tone AI Model",
        options=["All News", "Positive", "Negative", "Neutral", "Important Only"]
    )

    # Get currencies from subscriptions
    subscription_currencies = list(set([sub["base"] for sub in st.session_state.subscriptions] +
                                   [sub["quote"] for sub in st.session_state.subscriptions]))

    market_type = st.session_state.market_type  # Get the current market type (Crypto or FX)
    
    # Initialize market-specific news cache keys if they don't exist
    if 'fx_news' not in st.session_state:
        st.session_state.fx_news = []
        
    if 'crypto_news' not in st.session_state:
        st.session_state.crypto_news = []
        
    if 'last_fx_news_fetch' not in st.session_state:
        st.session_state.last_fx_news_fetch = None
        
    if 'last_crypto_news_fetch' not in st.session_state:
        st.session_state.last_crypto_news_fetch = None

    current_time = datetime.now()
    should_refresh_news = False
    
    # Use market-specific cache keys
    if market_type == 'FX':
        news_cache_key = 'fx_news'
        last_fetch_key = 'last_fx_news_fetch'
        next_refresh_key = 'next_fx_news_refresh_time'
    else:  # Crypto
        news_cache_key = 'crypto_news'
        last_fetch_key = 'last_crypto_news_fetch'
        next_refresh_key = 'next_crypto_news_refresh_time'
    
    # Initialize the next refresh time if it doesn't exist
    if next_refresh_key not in st.session_state:
        st.session_state[next_refresh_key] = current_time
    
    # Only refresh news if:
    # 1. We don't have any cached news yet for this market type
    # 2. We're past the scheduled next refresh time for this market type
    if st.session_state[last_fetch_key] is None:
        should_refresh_news = True
        reason = f"Initial {market_type} fetch"
        # Set the next refresh time
        st.session_state[next_refresh_key] = current_time + timedelta(seconds=300)
    elif not st.session_state[news_cache_key]:
        should_refresh_news = True
        reason = f"No cached {market_type} news"
        # Set the next refresh time
        st.session_state[next_refresh_key] = current_time + timedelta(seconds=300)
    elif current_time >= st.session_state[next_refresh_key]:
        should_refresh_news = True
        reason = f"Scheduled 5-minute {market_type} refresh"
        # Schedule the next refresh
        st.session_state[next_refresh_key] = current_time + timedelta(seconds=300)
    elif st.session_state.refresh_news_clicked:
        should_refresh_news = True
        reason = f"Manual {market_type} refresh"
        # Schedule the next refresh
        st.session_state[next_refresh_key] = current_time + timedelta(seconds=300)
        # Reset the flag
        st.session_state.refresh_news_clicked = False
        
    # Fetch news if needed
    if should_refresh_news:
        # Add notification to make refresh visible
        add_notification(f"Refreshing {market_type} news: {reason}", "info")
        news_items = fetch_news(subscription_currencies)
        # Store in the market-specific cache
        st.session_state[news_cache_key] = news_items
        st.session_state[last_fetch_key] = current_time
    else:
        # Use the market-specific cached news
        news_items = st.session_state[news_cache_key]
        
    # Add a small caption showing when news was last updated
    if st.session_state[last_fetch_key]:
        time_diff = current_time - st.session_state[last_fetch_key]
        if time_diff.seconds < 60:
            update_text = "just now"
        elif time_diff.seconds < 3600:
            update_text = f"{time_diff.seconds // 60} minutes ago"
        else:
            update_text = f"{time_diff.seconds // 3600} hours ago"
        st.caption(f"{market_type} news last updated: {update_text}")
        
    # Apply sentiment filter
    if sentiment_filter != "All News":
        if sentiment_filter == "Important Only":
            # Filter for news with strong sentiment (positive or negative)
            news_items = [item for item in news_items if abs(item.get("score", 0)) > 0.5]
        else:
            sentiment_map = {"Positive": "positive", "Negative": "negative", "Neutral": "neutral"}
            filter_sentiment = sentiment_map.get(sentiment_filter, "")
            news_items = [item for item in news_items if item.get("sentiment", "neutral") == filter_sentiment]

    # Display news items
    if news_items:
        for item in news_items:
            # Format timestamp
            time_diff = datetime.now() - item["timestamp"]
            if time_diff.days > 0:
                time_str = f"{time_diff.days}d ago"
            elif time_diff.seconds // 3600 > 0:
                time_str = f"{time_diff.seconds // 3600}h ago"
            else:
                time_str = f"{time_diff.seconds // 300}m ago"

            # Create color based on sentiment
            if 'sentiment' in item and item['sentiment'] == 'positive':
                border_color = "green"
                bg_color = "#d4edda"
                text_color = "#28a745"
            elif 'sentiment' in item and item['sentiment'] == 'negative':
                border_color = "red"
                bg_color = "#f8d7da"
                text_color = "#dc3545"
            else:  # neutral
                border_color = "gray"
                bg_color = "#f8f9fa"
                text_color = "#6c757d"

            # Rest of your display code remains the same
            with st.container():
                # Title with link if available
                title_html = f"""<div style="padding:12px; margin-bottom:12px; border-left:4px solid {border_color}; border-radius:4px; background-color:#ffffff;">"""
                
                if 'url' in item and item['url']:
                    title_html += f"""<div style="font-weight:bold; margin-bottom:8px;">
                        <a href="{item['url']}" target="_blank" style="text-decoration:none; color:#1e88e5;">
                            {item['title']} <span style="font-size:0.8em;">🔗</span>
                        </a>
                    </div>"""
                else:
                    title_html += f"""<div style="font-weight:bold; margin-bottom:8px;">{item['title']}</div>"""
                
                # Add the rest of the card
                title_html += f"""
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="background-color:#e0e8ff; padding:2px 6px; border-radius:3px; margin-right:5px;">
                                {item['currency']}
                            </span>
                            <span style="color:#6c757d; font-size:0.8em;">{item['source']}</span>
                        </div>
                        <div>
                            <span style="color:#6c757d; font-size:0.8em; margin-right:5px;">{time_str}</span>
                            <span style="background-color:{bg_color}; color:{text_color}; padding:2px 6px; border-radius:10px; font-size:0.8em;">
                                {item.get('sentiment', 'neutral')} ({'+' if item.get('score', 0) > 0 else ''}{item.get('score', 0)})
                            </span>
                        </div>
                    </div>
                </div>"""
                
                st.markdown(title_html, unsafe_allow_html=True)
    else:
        st.info("No news items match your filters")

# 7. Fetch the economic calendar data on app load (if not already cached)
# Add this at the end of your script
if 'economic_events' not in st.session_state or st.session_state.economic_events is None:
    with st.spinner("Updating economic calendar..."):
            fetch_all_economic_events(force=True)
            st.rerun()

if st.session_state.last_refresh is None: 
    with st.spinner("Updating currency rates..."):
        update_rates()

if st.session_state.last_news_fetch is None: 
    with st.spinner("Fetching the latest news..."):
        fetch_news(use_mock_fallback=True)   