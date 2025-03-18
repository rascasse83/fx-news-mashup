"""
Indices market specific UI components for the FX Pulsar application.
Contains functions for displaying stock indices data and visualizations.
"""
import streamlit as st
from typing import List, Dict, Any, Optional
from datetime import datetime

from fx_news.ui.components.charts import display_bar_chart
from fx_news.ui.components.maps import display_indices_world_map
from fx_news.data.currencies import indices
from fx_news.services.sentiment_service import calculate_market_volatility
from fx_news.ui.components.charts import display_volatility_gauge

def display_indices_market_overview():
    """Display the indices market overview section."""
    # Calculate volatility indices
    volatility_index, pair_volatility = calculate_market_volatility(st.session_state.subscriptions)
    
    # Header area with volatility index
    header_col1, header_col2 = st.columns([2, 1])

    with header_col1:
        st.markdown("<h1 class='main-header'>📈 Indices Market Monitor</h1>", unsafe_allow_html=True)
        
        # Display the text with a link on the word "sentiment"
        sentiment_url = "https://huggingface.co/yiyanghkust/finbert-tone"
        st.markdown(
            f"Real-time stock indices and news sentiment monitoring [.]({sentiment_url})",
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
    
    # Create tabs for different views
    tab1, tab2 = st.tabs(["Performance Overview", "World Map"])
    
    with tab1:
        display_indices_performance()
    
    with tab2:
        display_indices_world_map()

def display_indices_performance():
    """Display indices performance visualization with bar chart and heatmap."""
    # Get data from subscriptions
    indices_data = []
    
    for sub in st.session_state.subscriptions:
        if sub["current_rate"] is not None:
            # Calculate percent change
            percent_change = 0
            if sub.get("previous_close") is not None:
                percent_change = ((sub["current_rate"] - sub["previous_close"]) / sub["previous_close"]) * 100
            elif sub.get("last_rate") is not None:
                percent_change = ((sub["current_rate"] - sub["last_rate"]) / sub["last_rate"]) * 100
            
            # Get the human-readable name
            name = indices.get(sub["base"], sub["base"])
            
            indices_data.append({
                "index": name,
                "symbol": sub["base"],
                "price": sub["current_rate"],
                "change": percent_change,
                "quote": sub["quote"]
            })
    
    if not indices_data:
        st.info("No indices data available yet. Add some indices to see the visualization.")
        return
    
    # Sort by percent change (descending)
    indices_data = sorted(indices_data, key=lambda x: x["change"], reverse=True)
    
    # Use the bar chart component
    display_bar_chart(
        data=indices_data,
        x_field="index",
        y_field="change",
        title="Major Indices Performance",
        height=350
    )
    
    # Add a heatmap showing the current indices values
    st.subheader("Global Indices Heatmap")
    
    # Set up the grid for the heatmap
    cols = st.columns(3)
    
    for i, index_data in enumerate(indices_data):
        col_idx = i % 3
        with cols[col_idx]:
            # Determine color based on change percentage
            if index_data["change"] > 1.5:
                bg_color = "#1B5E20"  # Dark green
            elif index_data["change"] > 0:
                bg_color = "#4CAF50"  # Green
            elif index_data["change"] > -1.5