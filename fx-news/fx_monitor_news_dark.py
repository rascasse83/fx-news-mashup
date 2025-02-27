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
from bs4 import BeautifulSoup
import os
import random
from scrapers.news_scraper import scrape_yahoo_finance_news, create_mock_news
from apis.rates_fetch import fetch_currency_rates, update_rates_with_variation, get_mock_currency_rates
from scrapers.rates_scraper import scrape_yahoo_finance_rates
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go

# Configure page
st.set_page_config(
    page_title="FX Pulse",
    page_icon="💱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state only once
for key, default_value in {
    'subscriptions': [
        {"base": "EUR", "quote": "USD", "threshold": 0.5, "last_rate": None, "current_rate": None},
        {"base": "USD", "quote": "JPY", "threshold": 0.5, "last_rate": None, "current_rate": None},
        {"base": "GBP", "quote": "EUR", "threshold": 0.5, "last_rate": None, "current_rate": None},
         {"base": "GBP", "quote": "USD", "threshold": 0.5, "last_rate": None, "current_rate": None},
         {"base": "EUR", "quote": "CAD", "threshold": 0.5, "last_rate": None, "current_rate": None},
         {"base": "GBP", "quote": "NZD", "threshold": 0.5, "last_rate": None, "current_rate": None}
    ],
    'notifications': [],
    'last_refresh': None,
    'last_news_fetch': None, 
    'cached_news': [],
    'rate_history': {},
    'debug_log': [],
    'show_debug': False,
    'add_variations': False,
    'auto_refresh': True,
    'last_auto_refresh_time': datetime.now()
}.items():
    # Only set the value if the key doesn't exist in session state
    if key not in st.session_state:
        st.session_state[key] = default_value

# Available currencies
available_currencies = {
    'EUR': 'Euro',
    'USD': 'US Dollar',
    'GBP': 'British Pound',
    'JPY': 'Japanese Yen',
    'XAG': 'Silver',
    'AUD': 'Australian Dollar',
    'CAD': 'Canadian Dollar',
    'CHF': 'Swiss Franc',
    'CNY': 'Chinese Yuan',
    'NZD': 'New Zealand Dollar',
    'HKD': 'Hong Kong Dollar',
    'SGD': 'Singapore Dollar'
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
    'NZD': 'New Zealand',
    'HKD': 'Hong Kong',
    'SGD': 'Singapore',
    'XAG': 'Global'  # Silver is traded globally
}

# Fetch API key from environment variables
API_KEY = os.getenv("CURRENCY_API_KEY")


def setup_auto_refresh():
    """Setup auto-refresh mechanism using streamlit_autorefresh package"""
    # Only enable auto-refresh if the toggle is on in session state
    if 'auto_refresh' in st.session_state and st.session_state.auto_refresh:
        # Set up the 15-second refresh cycle for rates
        # This returns a counter that increases each time your app reruns
        count = st_autorefresh(interval=30000, key="rates_refresher")
        
        # Process refreshes
        current_time = datetime.now()
        
        # Handle rates refresh (every refresh cycle - 30 seconds)
        st.session_state.last_auto_refresh_time = current_time
        update_rates()
        
        # Handle news refresh (every 4th refresh cycle - 2 minutes)
        if count % 4 == 0:  # Every 4th refresh (30 * 4 = 120 seconds)
            st.session_state.last_news_auto_refresh_time = current_time
            fetch_news(use_mock_fallback=True)

# Add the fetch_news function to your main app since it depends on st.session_state
def fetch_news(currencies=None, use_mock_fallback=True):
    """Fetch news for currency pairs, with fallback to mock data if needed."""
    if 'subscriptions' not in st.session_state:
        return []

    currency_pairs = list(set((sub["base"], sub["quote"]) for sub in st.session_state.subscriptions))

    if not currency_pairs:
        return []

    st.session_state.debug_log = []
    st.session_state.debug_log.append(f"Attempting to fetch news for {len(currency_pairs)} currency pairs")

    try:
        with st.spinner("Fetching latest news from Yahoo Finance..."):
            all_news_items = []
            for base, quote in currency_pairs:
                news_items = scrape_yahoo_finance_news([(base, quote)], debug_log=st.session_state.debug_log)
                for item in news_items:
                    item["currency_pairs"] = {f"{base}/{quote}"}
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
                return deduplicated_news
            else:
                st.session_state.debug_log.append("No news items found from Yahoo Finance")
    except Exception as e:
        st.session_state.debug_log.append(f"Error fetching news from Yahoo Finance: {str(e)}")
        add_notification(f"Error fetching news from Yahoo Finance: {str(e)}", "error")

    if use_mock_fallback:
        add_notification("Using mock news data as fallback", "info")
        return create_mock_news(currencies)

    if 'cached_news' in st.session_state and st.session_state.cached_news:
        return st.session_state.cached_news

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

# Update the update_rates function to use the new module
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
            # Attempt to fetch real data using the new scraper
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

                # Normalize results keys to lowercase for case-insensitive comparison
                results_lower = {k.lower(): {kk.lower(): vv for kk, vv in v.items()} for k, v in results.items()}

                if base in results_lower and quote in results_lower[base]:
                    # Store last rate before updating
                    sub["last_rate"] = sub["current_rate"]
                    sub["current_rate"] = results_lower[base][quote]

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

                    # Check for threshold breach if we have both rates
                    if sub["last_rate"] is not None and sub["current_rate"] is not None:
                        percent_change = abs((sub["current_rate"] - sub["last_rate"]) / sub["last_rate"] * 100)
                        if percent_change > sub["threshold"]:
                            direction = "increased" if sub["current_rate"] > sub["last_rate"] else "decreased"
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

# Function to calculate percentage variation
def calculate_percentage_variation(subscriptions):
    variations = []
    for sub in subscriptions:
        if sub["last_rate"] is not None and sub["current_rate"] is not None:
            percent_change = ((sub["current_rate"] - sub["last_rate"]) / sub["last_rate"]) * 100
            variations.append({
                "currency_pair": f"{sub['base']}/{sub['quote']}",
                "base": sub["base"],
                "quote": sub["quote"],
                "variation": percent_change
            })
    return variations

# Call this function right after your session state initialization
setup_auto_refresh()

# Main app header
st.markdown("<h1 class='main-header'>💱 FX-Pulse</h1>", unsafe_allow_html=True)
st.markdown("Real-time FX rates and news sentiment monitoring")

# Calculate percentage variations
variations = calculate_percentage_variation(st.session_state.subscriptions)

# Prepare data for the geomap
map_data = []
for variation in variations:
    # Use the base currency to determine the location
    locations = currency_to_country.get(variation["base"], ["Unknown"])
    for location in locations:
        map_data.append({
            "location": location,
            "variation": variation["variation"]
        })

# Create the geomap
# Conditionally display the geomaps
if map_data:
    # Create a layout with three columns
    col1, col2, col3 = st.columns(3)

    # Map for the US continent
    with col1:
        fig_us = go.Figure(data=go.Choropleth(
            locations=[data["location"] for data in map_data if data["location"] in ['United States', 'Canada', 'Mexico']],
            z=[data["variation"] for data in map_data if data["location"] in ['United States', 'Canada', 'Mexico']],
            locationmode='country names',
            colorscale='RdBu',
            colorbar_title="% Variation"
        ))

        fig_us.update_layout(
            geo=dict(
                showframe=False,
                showcoastlines=False,
                projection_type='equirectangular',
                center=dict(lat=37.0902, lon=-95.7129),  # Center around the US
            ),
            height=300,
            margin=dict(l=0, r=0, t=0, b=0)
        )

        st.plotly_chart(fig_us, use_container_width=True)

    # Map for Europe
    with col2:
        fig_europe = go.Figure(data=go.Choropleth(
            locations=[data["location"] for data in map_data if data["location"] in currency_to_country['EUR']],
            z=[data["variation"] for data in map_data if data["location"] in currency_to_country['EUR']],
            locationmode='country names',
            colorscale='RdBu',
            colorbar_title="% Variation"
        ))

        fig_europe.update_layout(
            geo=dict(
                showframe=False,
                showcoastlines=False,
                projection_type='equirectangular',
                center=dict(lat=54.5260, lon=15.2551),  # Center around Europe
            ),
            height=300,
            margin=dict(l=0, r=0, t=0, b=0)
        )

        st.plotly_chart(fig_europe, use_container_width=True)

    # Map for Asia
    with col3:
        fig_asia = go.Figure(data=go.Choropleth(
            locations=[data["location"] for data in map_data if data["location"] in ['Japan', 'China', 'India', 'Singapore', 'Hong Kong']],
            z=[data["variation"] for data in map_data if data["location"] in ['Japan', 'China', 'India', 'Singapore', 'Hong Kong']],
            locationmode='country names',
            colorscale='RdBu',
            colorbar_title="% Variation"
        ))

        fig_asia.update_layout(
            geo=dict(
                showframe=False,
                showcoastlines=False,
                projection_type='equirectangular',
                center=dict(lat=34.0479, lon=100.6197),  # Center around Asia
            ),
            height=300,
            margin=dict(l=0, r=0, t=0, b=0)
        )

        st.plotly_chart(fig_asia, use_container_width=True)
else:
    st.info("No data available to display on the maps. Please add subscriptions and wait for data to be fetched.")


# Page layout: Two columns for the main content
col1, col4 = st.columns([3, 1])  # Adjust the column widths to give more space to the map


# Right sidebar for subscription management
with st.sidebar:
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

    # Manual refresh button
    st.button("🔄 Refresh Rates", on_click=update_rates)
    st.button("📰 Refresh News", on_click=lambda: fetch_news(use_mock_fallback=True))

    # Then in your sidebar, for the auto-refresh toggle:
    auto_refresh = st.sidebar.checkbox("Auto-refresh (Rates: 30s, News: 2min)", value=st.session_state.auto_refresh)
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

# Main area: Currency rates
with col1:
    st.header("Currency Rates")

    # Check if we need initial data
    if not st.session_state.subscriptions or all(sub["current_rate"] is None for sub in st.session_state.subscriptions):
        with st.spinner("Fetching initial rates..."):
            update_rates()

    # Display each subscription's rate
    for i, sub in enumerate(st.session_state.subscriptions):
        # Create a unique key for this subscription
        key_base = f"{sub['base']}_{sub['quote']}_{i}"

        # Create a card using Streamlit's expander
        with st.expander(f"{sub['base']}/{sub['quote']}", expanded=True):
            # Top row with currency pair and remove button
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"### {sub['base']}/{sub['quote']}")
            with col2:
                if st.button("Remove", key=f"remove_{key_base}"):
                    st.session_state.subscriptions.pop(i)
                    add_notification(f"Removed subscription: {sub['base']}/{sub['quote']}", "system")
                    st.rerun()

            # Rate information
            if sub["current_rate"] is not None:
                # Format the rate with appropriate decimal places
                if sub["current_rate"] < 0.01:
                    formatted_rate = f"{sub['current_rate']:.6f}"
                elif sub["current_rate"] < 1:
                    formatted_rate = f"{sub['current_rate']:.4f}"
                else:
                    formatted_rate = f"{sub['current_rate']:.4f}"

                # Determine rate direction and color
                direction_arrow = ""
                color = "gray"
                direction_class = "rate-neutral"
                if sub["last_rate"] is not None:
                    if sub["current_rate"] > sub["last_rate"]:
                        direction_arrow = "▲"
                        color = "green"
                        direction_class = "rate-up"
                    elif sub["current_rate"] < sub["last_rate"]:
                        direction_arrow = "▼"
                        color = "red"
                        direction_class = "rate-down"

                # Add rate information to HTML
                html = f"""
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <span>Current Rate:</span>
                    <span class="{direction_class}">{formatted_rate} {direction_arrow}</span>
                </div>
                """
                st.markdown(html, unsafe_allow_html=True)

                # Add percent change if available
                if sub["last_rate"] is not None:
                    percent_change = ((sub["current_rate"] - sub["last_rate"]) / sub["last_rate"]) * 100
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

        # Chart of rate history
        pair_key = f"{sub['base'].lower()}_{sub['quote'].lower()}"
        # In the section where we create the rate history chart
        if pair_key in st.session_state.rate_history and len(st.session_state.rate_history[pair_key]) > 1:
            history_data = st.session_state.rate_history[pair_key]
            df = pd.DataFrame(history_data)
            
            fig = px.line(df, x="timestamp", y="rate", 
                        title=f"{sub['base']}/{sub['quote']} Rate History",
                        labels={"timestamp": "Time", "rate": "Rate"})
            
            # Calculate range values for better visualization
            min_rate = df['rate'].min()
            max_rate = df['rate'].max()
            rate_range = max_rate - min_rate
            
            # If range is very small, create a custom range to make changes more visible
            if rate_range < 0.001:
                # Use a small fixed range around the mean
                mean_rate = df['rate'].mean()
                fig.update_yaxes(range=[mean_rate * 0.9995, mean_rate * 1.0005])
            elif rate_range < 0.01:
                # Add some padding to min/max values to make changes more visible
                fig.update_yaxes(range=[min_rate * 0.999, max_rate * 1.001])
            
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)

# News feed
with col4:
    st.header("Currency News")

    # Filter controls
    sentiment_filter = st.selectbox(
        "Filter by sentiment",
        options=["All News", "Positive", "Negative", "Neutral", "Important Only"]
    )

    # Get currencies from subscriptions
    subscription_currencies = list(set([sub["base"] for sub in st.session_state.subscriptions] +
                                   [sub["quote"] for sub in st.session_state.subscriptions]))

    # Check if we need to refresh news
    should_refresh_news = False
    if 'last_news_fetch' not in st.session_state or st.session_state.last_news_fetch is None:
        should_refresh_news = True
    elif 'cached_news' not in st.session_state or not st.session_state.cached_news:
        should_refresh_news = True
    elif (datetime.now() - st.session_state.last_news_fetch).total_seconds() > 900:  # 15 minutes
        should_refresh_news = True
        
    # Fetch news if needed
    if should_refresh_news:
        news_items = fetch_news(subscription_currencies)
    else:
        news_items = st.session_state.cached_news

    # Apply sentiment filter
    if sentiment_filter != "All News":
        if sentiment_filter == "Important Only":
            # Filter for news with strong sentiment (positive or negative)
            news_items = [item for item in news_items if abs(item["score"]) > 0.5]
        else:
            sentiment_map = {"Positive": "positive", "Negative": "negative", "Neutral": "neutral"}
            filter_sentiment = sentiment_map.get(sentiment_filter, "")
            news_items = [item for item in news_items if item["sentiment"] == filter_sentiment]

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
            if item['sentiment'] == 'positive':
                border_color = "green"
                bg_color = "#d4edda"
                text_color = "#28a745"
            elif item['sentiment'] == 'negative':
                border_color = "red"
                bg_color = "#f8d7da"
                text_color = "#dc3545"
            else:  # neutral
                border_color = "gray"
                bg_color = "#f8f9fa"
                text_color = "#6c757d"

            # Create a card with Streamlit markdown and link
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
                                {item['sentiment']} ({'+' if item['score'] > 0 else ''}{item['score']})
                            </span>
                        </div>
                    </div>
                </div>"""
                
                st.markdown(title_html, unsafe_allow_html=True)
    else:
        st.info("No news items match your filters")

# Handle auto-refresh at the end of the script
with st.spinner("Updating currency rates..."):
    update_rates()

with st.spinner("Fetching the latest news..."):
    fetch_news(use_mock_fallback=True)   