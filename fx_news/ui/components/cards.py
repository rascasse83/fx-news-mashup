import streamlit as st
import random
from datetime import datetime

from fx_news.services.sentiment_service import get_sentiment_for_pair
from fx_news.services.events_service import display_economic_calendar_for_currency_pair
from fx_news.utils.notifications import add_notification
from fx_news.scrapers.rates_scraper import display_combined_charts
from fx_news.predict.predictions import add_forecast_to_dashboard, add_forecast_comparison_card, add_darts_forecast_tab

def display_currency_pair(sub):
    """
    Display a currency pair card with real-time data, charts, and forecasts
    
    Args:
        sub: Subscription dictionary containing currency pair information
    """
    # Create a unique key for this subscription
    pair_key = f"{sub['base'].lower()}_{sub['quote'].lower()}"
    key_base = f"{sub['base']}_{sub['quote']}_{random.randint(1000, 9999)}"
    
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
            # Add tabs for Rate Info, Economic Calendar, Sentiment, and Forecasts
            rate_tab, chart_tab, prophet_tab, darts_tab, calendar_tab, sentiment_tab = st.tabs([
                "Rate Info", "Chart", "Prophet Forecast", "DARTS Forecast", "Economic Calendar", "Sentiment"
            ])
            
            with rate_tab:
                display_rate_info_tab(sub, key_base)
            
            with chart_tab:
                # Display the standard rate history chart
                display_combined_charts(sub['base'], sub['quote'])
            
            with prophet_tab:
                # Prophet forecasting tab
                add_forecast_to_dashboard(sub, use_expander=False)
            
            with darts_tab:
                # NEW: DARTS forecasting tab
                add_darts_forecast_tab(sub)
            
            with calendar_tab:
                # Economic calendar
                display_economic_calendar_for_currency_pair(sub['base'], sub['quote'])
            
            with sentiment_tab:
                # Sentiment analysis
                from fx_news.services.sentiment_service import display_sentiment_tab
                display_sentiment_tab(sub['base'], sub['quote'])

def display_rate_info_tab(sub, key_base):
    """Display the rate information tab content"""
    # Top row with remove button
    col3, col4 = st.columns([3, 1])
    with col4:
        if st.button("Remove", key=f"remove_{key_base}"):
            # Find the index of this subscription
            for i, s in enumerate(st.session_state.subscriptions):
                if s['base'] == sub['base'] and s['quote'] == sub['quote']:
                    st.session_state.subscriptions.pop(i)
                    add_notification(f"Removed subscription: {sub['base']}/{sub['quote']}", "system")
                    st.rerun()
                    break

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
            elif sub["current_rate"] < reference_rate:
                direction_arrow = "▼"
                color = "red"

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
        # Find the subscription and update it
        for i, s in enumerate(st.session_state.subscriptions):
            if s['base'] == sub['base'] and s['quote'] == sub['quote']:
                st.session_state.subscriptions[i]["threshold"] = new_threshold
                add_notification(f"Updated threshold for {sub['base']}/{sub['quote']} to {new_threshold}%", "system")
                break