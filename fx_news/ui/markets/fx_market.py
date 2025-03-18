"""
FX market specific UI components for the FX Pulsar application.
Contains functions for displaying FX market data and visualizations.
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional

from fx_news.utils.helpers import calculate_percentage_variation, prepare_map_data
from fx_news.data.currencies import currency_to_country
from fx_news.ui.components.maps import display_fx_maps
from fx_news.services.sentiment_service import calculate_market_volatility
from fx_news.ui.components.charts import display_volatility_gauge, display_volatility_trend_chart

def display_fx_market_overview():
    """Display the FX market overview section."""
    # Calculate volatility indices first
    volatility_index, pair_volatility = calculate_market_volatility(st.session_state.subscriptions)
    
    # Header area with logo and volatility index
    header_col1, header_col2 = st.columns([2, 1])

    with header_col1:
        st.markdown("<h1 class='main-header'>💱 FX Market Monitor</h1>", unsafe_allow_html=True)
        
        # Display the text with a link on the word "sentiment"
        sentiment_url = "https://huggingface.co/yiyanghkust/finbert-tone"
        st.markdown(
            f"Real-time FX rates and news sentiment monitoring [.]({sentiment_url})",
            unsafe_allow_html=True
        )

    with header_col2:
        # Create compact volatility gauge in the header
        display_volatility_gauge(volatility_index, height=120, show_title=True)
        
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
    
    # Detailed market overview section
    with st.expander("View Detailed Market Analysis", expanded=False):
        display_detailed_fx_market_analysis(volatility_index, pair_volatility)

def display_detailed_fx_market_analysis(volatility_index, pair_volatility):
    """
    Display detailed FX market analysis in an expandable section.
    
    Args:
        volatility_index: Overall market volatility index
        pair_volatility: Dictionary of volatility scores by pair
    """
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
        
        # Display the volatility trend chart
        if len(st.session_state.volatility_history) > 1:
            display_volatility_trend_chart(st.session_state.volatility_history, height=200)
        else:
            st.info("Collecting volatility trend data...")

def display_fx_market_maps():
    """Display the FX market geographic maps."""
    # Calculate percentage variations
    variations = calculate_percentage_variation(st.session_state.subscriptions)

    # Prepare data for the geomap
    map_data = prepare_map_data(variations, currency_to_country)
    
    # Display the maps
    if map_data:
        display_fx_maps(map_data)
    else:
        st.info("No market data available for the map visualization.")