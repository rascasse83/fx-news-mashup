"""
Chart visualization components for the FX Pulsar application.
Contains functions for creating various charts and visualizations.
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime
import random
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

def display_rate_history_chart(pair_key: str, title: str = None):
    """
    Display a chart of rate history for a currency pair.
    
    Args:
        pair_key: Key for the rate history in session state (base_quote)
        title: Optional title for the chart
    """
    if pair_key not in st.session_state.rate_history or len(st.session_state.rate_history[pair_key]) <= 1:
        st.info("Not enough rate history data to display a chart.")
        return
        
    # Prepare data
    history_data = st.session_state.rate_history[pair_key]
    df = pd.DataFrame(history_data)
    
    # Create dark-themed figure
    fig = px.line(df, x="timestamp", y="rate", 
                title=title or f"Rate History",
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

def display_volatility_gauge(volatility_index: float, height: int = 200, show_title: bool = True):
    """
    Display a gauge chart for market volatility.
    
    Args:
        volatility_index: Volatility index value (0-100)
        height: Height of the chart in pixels
        show_title: Whether to show the chart title
    """
    # Create a gauge chart for the volatility index
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=volatility_index,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Market Volatility Index" if show_title else "", 'font': {'color': 'white', 'size': 16}},
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
        height=height,
        margin=dict(l=20, r=20, t=50 if show_title else 20, b=20),
        paper_bgcolor="#121212",
        font=dict(color="white", size=12)
    )
    
    # Display the gauge
    st.plotly_chart(fig, use_container_width=True)

def display_sentiment_gauge(long_percentage: float, title: str = None, height: int = 200):
    """
    Display a gauge chart for sentiment data.
    
    Args:
        long_percentage: Percentage of long positions (0-100)
        title: Optional title for the chart
        height: Height of the chart in pixels
    """
    # Determine color based on sentiment
    if long_percentage > 65:
        color = "#4CAF50"  # Strong bullish - green
    elif long_percentage > 55:
        color = "#8BC34A"  # Moderately bullish - light green
    elif long_percentage < 35:
        color = "#F44336"  # Strong bearish - red
    elif long_percentage < 45:
        color = "#FF9800"  # Moderately bearish - orange
    else:
        color = "#9E9E9E"  # Neutral - gray
    
    # Create the gauge chart
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=long_percentage,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title or "Long Sentiment", 'font': {'color': 'white', 'size': 14}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
            'bar': {'color': color},
            'bgcolor': "gray",
            'borderwidth': 1,
            'bordercolor': "white",
            'steps': [
                {'range': [0, 100], 'color': "#1E1E1E"}
            ],
        },
        number={'suffix': "%", 'font': {'color': 'white'}}
    ))
    
    # Update layout
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="#121212",
        font=dict(color="white", size=12)
    )
    
    # Display the gauge
    st.plotly_chart(fig, use_container_width=True)

def display_sentiment_donut(long_percentage: float, short_percentage: float, current_rate: str = None):
    """
    Display a donut chart for long/short sentiment.
    
    Args:
        long_percentage: Percentage of long positions (0-100)
        short_percentage: Percentage of short positions (0-100)
        current_rate: Optional current rate to display in the center
    """
    # Create the sentiment donut chart
    fig = go.Figure()
    
    # Add donut chart for long/short percentages
    fig.add_trace(go.Pie(
        labels=['Long', 'Short'],
        values=[long_percentage, short_percentage],
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
    
    # Add current rate as annotation in the center if provided
    if current_rate:
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
        height=300,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="#121212",
        plot_bgcolor="#121212",
        font=dict(color='white')
    )
    
    st.plotly_chart(fig, use_container_width=True)

def display_volatility_trend_chart(volatility_history: List[Dict], height: int = 200):
    """
    Display a trend chart for volatility history.
    
    Args:
        volatility_history: List of volatility history dictionaries
        height: Height of the chart in pixels
    """
    if not volatility_history or len(volatility_history) <= 1:
        st.info("Not enough volatility data to display a trend chart.")
        return
    
    # Create a dataframe from the volatility history
    trend_df = pd.DataFrame(volatility_history)
    
    # Create a line chart
    fig = px.line(trend_df, x="timestamp", y="volatility", height=height)
    
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
    fig.add_hrect(y0=0, y1=25, fillcolor="#4CAF50", opacity=0.1, line_width=0)  # Low volatility
    fig.add_hrect(y0=25, y1=50, fillcolor="#FFC107", opacity=0.1, line_width=0)  # Medium volatility
    fig.add_hrect(y0=50, y1=75, fillcolor="#FF9800", opacity=0.1, line_width=0)  # Medium-high volatility
    fig.add_hrect(y0=75, y1=100, fillcolor="#F44336", opacity=0.1, line_width=0)  # High volatility
    
    st.plotly_chart(fig, use_container_width=True)

def display_bar_chart(data: List[Dict], x_field: str, y_field: str, color_field: str = None, 
                     title: str = None, height: int = 350):
    """
    Display a bar chart for various data.
    
    Args:
        data: List of data dictionaries
        x_field: Field name for x-axis values
        y_field: Field name for y-axis values
        color_field: Optional field name for bar colors
        title: Optional title for the chart
        height: Height of the chart in pixels
    """
    if not data:
        st.info("No data available for the chart.")
        return
    
    # Create a dataframe from the data
    df = pd.DataFrame(data)
    
    # Create color mapping function if color_field is provided
    color_values = None
    if color_field and color_field in df.columns:
        if df[color_field].dtype in ['float64', 'int64']:
            # For numeric fields, use a continuous color scale
            color_values = df[color_field]
        else:
            # For categorical fields, map to distinct colors
            color_values = df[color_field]
    
    # Create the bar chart
    fig = px.bar(
        df, 
        x=x_field, 
        y=y_field,
        color=color_values,
        title=title,
        height=height,
        labels={x_field: x_field, y_field: y_field}
    )
    
    # Apply dark theme styling
    fig.update_layout(
        margin=dict(l=10, r=10, t=50 if title else 10, b=10),
        paper_bgcolor="#121212",
        plot_bgcolor="#121212",
        font=dict(color="#FFFFFF"),
        title_font_color="#FFFFFF",
        xaxis=dict(
            gridcolor="#333333",
            tickcolor="#FFFFFF",
            tickfont=dict(color="#FFFFFF")
        ),
        yaxis=dict(
            gridcolor="#333333",
            tickcolor="#FFFFFF",
            tickfont=dict(color="#FFFFFF")
        ),
        legend=dict(
            font=dict(color="#FFFFFF")
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)

def display_treemap(data: List[Dict], values_field: str, labels_field: str, 
                   color_field: str = None, title: str = None, height: int = 300):
    """
    Display a treemap visualization.
    
    Args:
        data: List of data dictionaries
        values_field: Field name for size values
        labels_field: Field name for labels
        color_field: Optional field name for colors
        title: Optional title for the chart
        height: Height of the chart in pixels
    """
    if not data:
        st.info("No data available for the treemap.")
        return
    
    # Create the treemap
    fig = go.Figure(go.Treemap(
        labels=[item[labels_field] for item in data],
        parents=["" for _ in data],  # All items at root level
        values=[item[values_field] for item in data],
        textinfo="label",
        hovertemplate='<b>%{label}</b><br>Value: %{value}<extra></extra>',
    ))
    
    # Apply color if provided
    if color_field:
        # Get color values
        color_values = [item.get(color_field, 0) for item in data]
        
        # Create a custom colorscale based on the values
        # Green for positive, red for negative
        colors = []
        for val in color_values:
            if val > 1:
                colors.append('#4CAF50')  # Strong positive - green
            elif val > 0:
                colors.append('#8BC34A')  # Moderate positive - light green
            elif val < -1:
                colors.append('#F44336')  # Strong negative - red
            elif val < 0:
                colors.append('#FF9800')  # Moderate negative - orange
            else:
                colors.append('#9E9E9E')  # Neutral - gray
        
        # Update marker colors
        fig.update_traces(marker=dict(colors=colors, showscale=False))
    
    # Add title if provided
    if title:
        fig.update_layout(title=title)
    
    # Apply dark theme styling
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=30 if title else 0, b=0),
        paper_bgcolor="#121212",
        font=dict(color="#FFFFFF"),
        title_font_color="#FFFFFF"
    )
    
    st.plotly_chart(fig, use_container_width=True)

def display_combined_charts(base: str, quote: str):
    """
    Display combination of charts for a currency pair.
    Includes recent history, price and volume, and forecasts.
    
    Args:
        base: Base currency code
        quote: Quote currency code
    """
    # Generate pair key
    pair_key = f"{base.lower()}_{quote.lower()}"
    
    # Check if we have any rate history
    if pair_key not in st.session_state.rate_history or len(st.session_state.rate_history[pair_key]) <= 1:
        st.info("Not enough rate history data to display charts. Please wait for more data to be collected.")
        return
    
    # Create tabs for different timeframes
    tab1, tab2, tab3 = st.tabs(["Intraday", "Last 5 Days", "Historical"])
    
    with tab1:
        # Display the intraday chart
        display_rate_history_chart(pair_key, title=f"{base}/{quote} Intraday Rate")
    
    with tab2:
        # In a real app, you would fetch 5-day data
        # For now, we'll simulate it
        display_simulated_5day_chart(base, quote)
    
    with tab3:
        # In a real app, you would fetch historical data
        # For now, we'll simulate it
        display_simulated_historical_chart(base, quote)

def display_simulated_5day_chart(base: str, quote: str):
    """
    Display a simulated 5-day chart for a currency pair.
    
    Args:
        base: Base currency code
        quote: Quote currency code
    """
    # Create simulated data
    # This would be replaced with actual historical data in a real app
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5)
    
    # Generate dates at hourly intervals
    dates = []
    current_date = start_date
    while current_date <= end_date:
        # Only include business hours (8 AM to 6 PM)
        if 8 <= current_date.hour <= 18:
            dates.append(current_date)
        current_date += timedelta(hours=1)
    
    # Generate a base rate
    if base == "EUR" and quote == "USD":
        base_rate = 1.1
    elif base == "USD" and quote == "JPY":
        base_rate = 110.0
    elif base == "GBP" and quote == "USD":
        base_rate = 1.35
    else:
        # Default to a random base rate between 0.5 and 1.5
        base_rate = 0.5 + random.random()
    
    # Generate rates with some volatility
    rates = []
    current_rate = base_rate
    for _ in dates:
        # Add some random noise to create volatility
        change = (random.random() - 0.5) * 0.002 * base_rate
        current_rate += change
        rates.append(current_rate)
    
    # Create a dataframe
    df = pd.DataFrame({
        'timestamp': dates,
        'rate': rates
    })
    
    # Create the chart
    fig = px.line(df, x="timestamp", y="rate", 
                title=f"{base}/{quote} - Last 5 Days",
                labels={"timestamp": "Time", "rate": "Rate"})
    
    # Apply dark theme styling
    fig.update_layout(
        height=300,
        margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor="#121212",
        plot_bgcolor="#121212",
        font=dict(color="#FFFFFF"),
        title_font_color="#FFFFFF",
        xaxis=dict(
            gridcolor="#333333",
            tickcolor="#FFFFFF",
            linecolor="#555555",
            tickfont=dict(color="#FFFFFF", size=12),
            title_font=dict(color="#FFFFFF", size=14)
        ),
        yaxis=dict(
            gridcolor="#333333",
            tickcolor="#FFFFFF",
            linecolor="#555555",
            tickfont=dict(color="#FFFFFF", size=12),
            title_font=dict(color="#FFFFFF", size=14)
        )
    )
    
    # Change line color to a brighter shade
    fig.update_traces(
        line=dict(color="#4D9BF5", width=2)
    )
    
    st.plotly_chart(fig, use_container_width=True)

def display_simulated_historical_chart(base: str, quote: str):
    """
    Display a simulated historical chart for a currency pair.
    
    Args:
        base: Base currency code
        quote: Quote currency code
    """
    # Create simulated data for a longer period (e.g., 1 year)
    # This would be replaced with actual historical data in a real app
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)  # 1 year
    
    # Generate dates at daily intervals
    dates = []
    current_date = start_date
    while current_date <= end_date:
        # Only include weekdays
        if current_date.weekday() < 5:  # 0-4 are Monday to Friday
            dates.append(current_date)
        current_date += timedelta(days=1)
    
    # Generate a base rate
    if base == "EUR" and quote == "USD":
        base_rate = 1.1
        volatility = 0.04  # 4% annual volatility
    elif base == "USD" and quote == "JPY":
        base_rate = 110.0
        volatility = 0.05  # 5% annual volatility
    elif base == "GBP" and quote == "USD":
        base_rate = 1.35
        volatility = 0.06  # 6% annual volatility
    else:
        # Default to a random base rate between 0.5 and 1.5
        base_rate = 0.5 + random.random()
        volatility = 0.05  # 5% annual volatility
    
    # Generate rates with some trend and volatility
    rates = []
    current_rate = base_rate
    
    # Add a slight trend bias (50% chance of uptrend, 50% chance of downtrend)
    trend_bias = (random.random() - 0.5) * 0.0002  # Small daily trend
    
    for i in range(len(dates)):
        # Calculate daily volatility
        daily_vol = volatility / np.sqrt(252)  # Annualized to daily
        
        # Add some random noise based on volatility
        change = trend_bias + np.random.normal(0, daily_vol) * current_rate
        current_rate += change
        
        # Ensure the rate doesn't go negative
        current_rate = max(0.001, current_rate)
        
        rates.append(current_rate)
    
    # Create a dataframe
    df = pd.DataFrame({
        'timestamp': dates,
        'rate': rates
    })
    
    # Create the chart
    fig = px.line(df, x="timestamp", y="rate", 
                title=f"{base}/{quote} - Historical Data",
                labels={"timestamp": "Date", "rate": "Rate"})
    
    # Apply dark theme styling
    fig.update_layout(
        height=300,
        margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor="#121212",
        plot_bgcolor="#121212",
        font=dict(color="#FFFFFF"),
        title_font_color="#FFFFFF",
        xaxis=dict(
            gridcolor="#333333",
            tickcolor="#FFFFFF",
            linecolor="#555555",
            tickfont=dict(color="#FFFFFF", size=12),
            title_font=dict(color="#FFFFFF", size=14)
        ),
        yaxis=dict(
            gridcolor="#333333",
            tickcolor="#FFFFFF",
            linecolor="#555555",
            tickfont=dict(color="#FFFFFF", size=12),
            title_font=dict(color="#FFFFFF", size=14)
        )
    )
    
    # Change line color to a brighter shade
    fig.update_traces(
        line=dict(color="#4D9BF5", width=2)
    )
    
    st.plotly_chart(fig, use_container_width=True)


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
