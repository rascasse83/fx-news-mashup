import os
import json
import time
import random
import requests
import concurrent.futures
import logging
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from functools import lru_cache

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger("rates scraper")
logger.setLevel(logging.WARNING)  # Set to INFO for production, DEBUG for development

# Base directory for storing rate data
BASE_DIR = "fx_news/scrapers/rates"
YTD_DIR = f"{BASE_DIR}/ytd"
FIVE_D_DIR = f"{BASE_DIR}/5d"

# Create directories if they don't exist
for directory in [YTD_DIR, FIVE_D_DIR]:
    os.makedirs(directory, exist_ok=True)

#################################
# Rate Scraper Functionality
#################################

def format_currency_pair_for_yahoo(base, quote):
    """Format currency pair for Yahoo Finance URL"""
    base = base.upper()
    quote = quote.upper()
    
    # Handle indices (^DJI, ^GSPC, etc.)
    if base.startswith('^'):
        return base
    
    # Handle cryptocurrencies (BTC-USD, ETH-USD, etc.)
    crypto_currencies = ['BTC', 'ETH', 'XRP', 'LTC', 'BCH', 'ADA', 'DOT', 'LINK', 'XLM', 'DOGE', 'SOL']
    
    if base in crypto_currencies and quote == 'USD':
        return f"{base}-{quote}"
    elif base == 'USD':
        return f"{quote}%3DX"
    else:
        return f"{base}{quote}%3DX"

def get_random_headers():
    """Generate random headers to avoid detection"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
    ]
    return {
        'User-Agent': random.choice(user_agents),
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }

def fetch_spark_data(symbol, range_val, interval):
    """
    Fetch data from Yahoo Finance spark API
    
    Args:
        symbol: Yahoo Finance symbol
        range_val: Time range (1d, 5d, ytd, etc.)
        interval: Data interval (1m, 5m, 1d, etc.)
        
    Returns:
        JSON response data or None if fetch fails
    """
    spark_url = f"https://query1.finance.yahoo.com/v7/finance/spark?symbols={symbol}&range={range_val}&interval={interval}&indicators=close&includeTimestamps=true"
    logger.debug(f"Fetching from URL: {spark_url}")
    
    headers = get_random_headers()
    
    try:
        response = requests.get(spark_url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "spark" in data and "result" in data["spark"] and len(data["spark"]["result"]) > 0:
                return data
        else:
            logger.warning(f"Failed to fetch {range_val} data for {symbol}: Status code {response.status_code}")
    except Exception as e:
        logger.error(f"Error fetching {range_val} data for {symbol}: {e}")
    
    return None

def fetch_and_save_ytd_data(currency_pairs):
    """
    Fetch and save YTD data for all currency pairs
    
    Args:
        currency_pairs: List of tuples containing (base, quote) currency pairs
    """
    today = date.today().strftime("%Y-%m-%d")
    logger.info(f"Fetching YTD data for {len(currency_pairs)} pairs on {today}")
    
    for base, quote in currency_pairs:
        symbol = format_currency_pair_for_yahoo(base, quote)
        filename = f"{YTD_DIR}/{base.lower()}_{quote.lower()}.json"
        
        # Check if we already fetched YTD data today
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    existing_data = json.load(f)
                
                # Check if the data is from today (assuming we can extract the last timestamp)
                if "spark" in existing_data and "result" in existing_data["spark"] and len(existing_data["spark"]["result"]) > 0:
                    response_data = existing_data["spark"]["result"][0].get("response", [{}])[0]
                    meta = response_data.get("meta", {})
                    last_time = meta.get("regularMarketTime")
                    
                    if last_time:
                        last_date = datetime.fromtimestamp(last_time).date()
                        if last_date == date.today():
                            logger.info(f"YTD data for {base}/{quote} already fetched today, skipping")
                            continue
            except Exception as e:
                logger.warning(f"Error checking existing YTD data for {base}/{quote}: {e}")
        
        # Fetch new YTD data
        ytd_data = fetch_spark_data(symbol, "ytd", "1d")
        if ytd_data:
            with open(filename, 'w') as f:
                json.dump(ytd_data, f)
            logger.info(f"Successfully saved YTD data for {base}/{quote}")
        else:
            logger.error(f"Failed to fetch YTD data for {base}/{quote}")
        
        # Avoid rate limiting
        time.sleep(random.uniform(0.5, 1.5))

def fetch_and_save_five_day_data(currency_pairs):
    """
    Fetch and save 5-day data for all currency pairs
    
    Args:
        currency_pairs: List of tuples containing (base, quote) currency pairs
        
    Returns:
        Dictionary with real-time rates data
    """
    logger.info(f"Fetching 5-day data for {len(currency_pairs)} pairs")
    rates_data = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(currency_pairs))) as executor:
        future_to_pair = {}
        
        for base, quote in currency_pairs:
            symbol = format_currency_pair_for_yahoo(base, quote)
            future = executor.submit(fetch_spark_data, symbol, "5d", "5m")
            future_to_pair[future] = (base, quote)
        
        for future in concurrent.futures.as_completed(future_to_pair):
            base, quote = future_to_pair[future]
            try:
                five_day_data = future.result()
                if five_day_data:
                    # Save to file
                    filename = f"{FIVE_D_DIR}/{base.lower()}_{quote.lower()}.json"
                    with open(filename, 'w') as f:
                        json.dump(five_day_data, f)
                    
                    # Extract rate data for returning
                    if base.upper() not in rates_data:
                        rates_data[base.upper()] = {}
                    
                    if "spark" in five_day_data and "result" in five_day_data["spark"] and len(five_day_data["spark"]["result"]) > 0:
                        spark_result = five_day_data["spark"]["result"][0]
                        if "response" in spark_result and len(spark_result["response"]) > 0:
                            response_data = spark_result["response"][0]
                            meta = response_data.get("meta", {})
                            
                            # For 5-day data, we should have previousClose
                            rates_data[base.upper()][quote.upper()] = {
                                "price": meta.get("regularMarketPrice"),
                                "previous_close": meta.get("previousClose")
                            }
                            
                            logger.info(f"Successfully processed 5-day data for {base}/{quote}")
                    
            except Exception as e:
                logger.error(f"Error processing 5-day data for {base}/{quote}: {e}")
    
    return rates_data

def get_blended_rates(currency_pairs):
    """
    Get blended rates from both YTD and 5-day data
    
    Args:
        currency_pairs: List of tuples containing (base, quote) currency pairs
        
    Returns:
        Dictionary with blended rates data
    """
    blended_rates = {}
    
    for base, quote in currency_pairs:
        base_upper = base.upper()
        quote_upper = quote.upper()
        
        if base_upper not in blended_rates:
            blended_rates[base_upper] = {}
        
        ytd_filename = f"{YTD_DIR}/{base.lower()}_{quote.lower()}.json"
        five_d_filename = f"{FIVE_D_DIR}/{base.lower()}_{quote.lower()}.json"
        
        price = None
        previous_close = None
        
        # First try to get current price and previous close from 5-day data
        if os.path.exists(five_d_filename):
            try:
                with open(five_d_filename, 'r') as f:
                    five_d_data = json.load(f)
                
                if "spark" in five_d_data and "result" in five_d_data["spark"] and len(five_d_data["spark"]["result"]) > 0:
                    response_data = five_d_data["spark"]["result"][0].get("response", [{}])[0]
                    meta = response_data.get("meta", {})
                    price = meta.get("regularMarketPrice")
                    previous_close = meta.get("previousClose")
            except Exception as e:
                logger.warning(f"Error reading 5-day data for {base}/{quote}: {e}")
        
        # If we couldn't get price from 5-day data, try YTD data for price only
        if price is None and os.path.exists(ytd_filename):
            try:
                with open(ytd_filename, 'r') as f:
                    ytd_data = json.load(f)
                
                if "spark" in ytd_data and "result" in ytd_data["spark"] and len(ytd_data["spark"]["result"]) > 0:
                    response_data = ytd_data["spark"]["result"][0].get("response", [{}])[0]
                    meta = response_data.get("meta", {})
                    price = meta.get("regularMarketPrice")
                    # Note: We don't use chartPreviousClose from YTD data as it's not reliable
            except Exception as e:
                logger.warning(f"Error reading YTD data for {base}/{quote}: {e}")
        
        if price is not None:
            blended_rates[base_upper][quote_upper] = {
                "price": price,
                "previous_close": previous_close
            }
        else:
            logger.warning(f"Could not get price data for {base}/{quote}")
    
    return blended_rates

def scrape_yahoo_finance_rates(currency_pairs, fetch_ytd=False, debug_log=None):
    """
    Scrape currency exchange rates from Yahoo Finance
    
    Args:
        currency_pairs: List of tuples containing (base, quote) currency pairs
        fetch_ytd: Whether to fetch YTD data (should be done once per day)
        debug_log: Optional list to append debug information
        
    Returns:
        Dictionary with rates data
    """
    if debug_log is None:
        debug_log = []
        
    # Fetch YTD data if requested (should be done once daily)
    if fetch_ytd:
        debug_log.append("Fetching YTD data for all currency pairs")
        fetch_and_save_ytd_data(currency_pairs)
    
    # Always fetch 5-day data for real-time rates
    debug_log.append("Fetching 5-day data for all currency pairs")
    rates = fetch_and_save_five_day_data(currency_pairs)
    
    # If we're missing any rates, try to blend with YTD data
    for base, quote in currency_pairs:
        base_upper = base.upper()
        quote_upper = quote.upper()
        
        if base_upper not in rates or quote_upper not in rates.get(base_upper, {}) or rates.get(base_upper, {}).get(quote_upper, {}).get("price") is None:
            debug_log.append(f"Missing or incomplete rate data for {base}/{quote}, trying to blend with YTD data")
            blended_rates = get_blended_rates([(base, quote)])
            
            if base_upper in blended_rates and quote_upper in blended_rates[base_upper]:
                if base_upper not in rates:
                    rates[base_upper] = {}
                rates[base_upper][quote_upper] = blended_rates[base_upper][quote_upper]
    
    return rates

#################################
# Chart Functionality
#################################

def load_ytd_chart_data(base, quote):
    """
    Load YTD chart data from stored JSON for the given currency pair
    
    Args:
        base: Base currency code
        quote: Quote currency code
        
    Returns:
        DataFrame with YTD chart data or None if not available
    """
    filename = f"{YTD_DIR}/{base.lower()}_{quote.lower()}.json"
    
    if not os.path.exists(filename):
        logger.warning(f"YTD data file not found for {base}/{quote}")
        return None
    
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        
        # Extract timestamps and close prices
        if "spark" in data and "result" in data["spark"] and len(data["spark"]["result"]) > 0:
            result = data["spark"]["result"][0]
            
            if "response" in result and len(result["response"]) > 0:
                response_data = result["response"][0]
                
                timestamps = response_data.get("timestamp", [])
                close_prices = response_data.get("indicators", {}).get("quote", [{}])[0].get("close", [])
                
                if timestamps and close_prices and len(timestamps) == len(close_prices):
                    df = pd.DataFrame({
                        "timestamp": [datetime.fromtimestamp(ts) for ts in timestamps],
                        "rate": close_prices
                    })
                    
                    # Get metadata
                    meta = response_data.get("meta", {})
                    current_price = meta.get("regularMarketPrice")
                    previous_close = meta.get("previousClose") or meta.get("chartPreviousClose")
                    
                    # Add metadata to the dataframe
                    df["current_price"] = current_price
                    df["previous_close"] = previous_close
                    
                    logger.info(f"Successfully loaded YTD chart data for {base}/{quote} with {len(df)} points")
                    return df
                else:
                    logger.warning(f"Invalid YTD data structure for {base}/{quote}")
    except Exception as e:
        logger.error(f"Error loading YTD chart data for {base}/{quote}: {e}")
    
    return None

def load_five_day_chart_data(base, quote):
    """
    Load 5-day chart data from stored JSON for the given currency pair
    
    Args:
        base: Base currency code
        quote: Quote currency code
        
    Returns:
        DataFrame with 5-day chart data or None if not available
    """
    filename = f"{FIVE_D_DIR}/{base.lower()}_{quote.lower()}.json"
    
    if not os.path.exists(filename):
        logger.warning(f"5-day data file not found for {base}/{quote}")
        return None
    
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        
        # Extract timestamps and close prices
        if "spark" in data and "result" in data["spark"] and len(data["spark"]["result"]) > 0:
            result = data["spark"]["result"][0]
            
            if "response" in result and len(result["response"]) > 0:
                response_data = result["response"][0]
                
                timestamps = response_data.get("timestamp", [])
                close_prices = response_data.get("indicators", {}).get("quote", [{}])[0].get("close", [])
                
                if timestamps and close_prices and len(timestamps) == len(close_prices):
                    df = pd.DataFrame({
                        "timestamp": [datetime.fromtimestamp(ts) for ts in timestamps],
                        "rate": close_prices
                    })
                    
                    # Get metadata
                    meta = response_data.get("meta", {})
                    current_price = meta.get("regularMarketPrice")
                    previous_close = meta.get("previousClose")
                    
                    # Add metadata to the dataframe
                    df["current_price"] = current_price
                    df["previous_close"] = previous_close
                    
                    logger.info(f"Successfully loaded 5-day chart data for {base}/{quote} with {len(df)} points")
                    return df
                else:
                    logger.warning(f"Invalid 5-day data structure for {base}/{quote}")
    except Exception as e:
        logger.error(f"Error loading 5-day chart data for {base}/{quote}: {e}")
    
    return None

def create_ytd_chart(base, quote, height=400):
    """
    Create and display a YTD chart for the given currency pair
    
    Args:
        base: Base currency code
        quote: Quote currency code
        height: Chart height in pixels
        
    Returns:
        Plotly figure object or None if chart creation fails
    """
    df = load_ytd_chart_data(base, quote)
    
    if df is None or df.empty:
        logger.warning(f"No YTD data available for {base}/{quote}")
        return None
    
    try:
        # Create the figure
        fig = go.Figure()
        
        # Add trace for historical data
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['rate'],
            mode='lines',
            name='YTD',
            line=dict(color='#4D9BF5', width=2),
            hovertemplate='%{x}<br>Rate: %{y:.4f}<extra></extra>'
        ))
        
        # Add chart title
        fig.update_layout(
            title=f"{base}/{quote} Year-to-Date Performance",
            title_font_color="#FFFFFF"
        )
        
        # Add current price line
        current_price = df['current_price'].iloc[0] if 'current_price' in df.columns else None
        if current_price is not None:
            fig.add_hline(
                y=current_price, 
                line_dash="dash", 
                line_color="green",
                annotation_text="Current",
                annotation_position="top right"
            )
        
        # Add previous close line
        previous_close = df['previous_close'].iloc[0] if 'previous_close' in df.columns else None
        if previous_close is not None:
            fig.add_hline(
                y=previous_close, 
                line_dash="dot", 
                line_color="red",
                annotation_text="Prev Close",
                annotation_position="bottom right"
            )
        
        # Apply dark theme styling
        fig.update_layout(
            height=height,
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
        
        # Add year start marker
        year_start = df[df['timestamp'].dt.year == df['timestamp'].iloc[0].year].iloc[0]
        fig.add_trace(go.Scatter(
            x=[year_start['timestamp']],
            y=[year_start['rate']],
            mode='markers',
            marker=dict(color='#FFFFFF', size=10, symbol='diamond'),
            name='Year Start',
            hoverinfo='y',
            showlegend=True
        ))
        
        # Add the FX-Pulsar watermark
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
        
        return fig
    
    except Exception as e:
        logger.error(f"Error creating YTD chart for {base}/{quote}: {e}")
        return None

def create_five_day_chart(base, quote, height=400):
    """
    Create and display a 5-day chart for the given currency pair
    
    Args:
        base: Base currency code
        quote: Quote currency code
        height: Chart height in pixels
        
    Returns:
        Plotly figure object or None if chart creation fails
    """
    df = load_five_day_chart_data(base, quote)
    
    if df is None or df.empty:
        logger.warning(f"No 5-day data available for {base}/{quote}")
        return None
    
    try:
        # Create the figure
        fig = go.Figure()
        
        # Add trace for historical data
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['rate'],
            mode='lines',
            name='5-Day',
            line=dict(color='#00FF00', width=2),
            hovertemplate='%{x}<br>Rate: %{y:.4f}<extra></extra>'
        ))
        
        # Add chart title
        fig.update_layout(
            title=f"{base}/{quote} 5-Day Performance",
            title_font_color="#FFFFFF"
        )
        
        # Add current price line
        current_price = df['current_price'].iloc[0] if 'current_price' in df.columns else None
        if current_price is not None:
            fig.add_hline(
                y=current_price, 
                line_dash="dash", 
                line_color="green",
                annotation_text="Current",
                annotation_position="top right"
            )
        
        # Add previous close line
        previous_close = df['previous_close'].iloc[0] if 'previous_close' in df.columns else None
        if previous_close is not None:
            fig.add_hline(
                y=previous_close, 
                line_dash="dot", 
                line_color="red",
                annotation_text="Prev Close",
                annotation_position="bottom right"
            )
        
        # Apply dark theme styling
        fig.update_layout(
            height=height,
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
        
        # Add high/low markers for the 5-day period
        high_idx = df['rate'].idxmax()
        low_idx = df['rate'].idxmin()
        
        fig.add_trace(go.Scatter(
            x=[df.iloc[high_idx]['timestamp']],
            y=[df.iloc[high_idx]['rate']],
            mode='markers+text',
            marker=dict(color='#4CAF50', size=10, symbol='triangle-up'),
            text=['High'],
            textposition='top center',
            hoverinfo='text+y',
            name='5-Day High',
            textfont=dict(color='#4CAF50')
        ))
        
        fig.add_trace(go.Scatter(
            x=[df.iloc[low_idx]['timestamp']],
            y=[df.iloc[low_idx]['rate']],
            mode='markers+text',
            marker=dict(color='#F44336', size=10, symbol='triangle-down'),
            text=['Low'],
            textposition='bottom center',
            hoverinfo='text+y',
            name='5-Day Low',
            textfont=dict(color='#F44336')
        ))
        
        # Add the FX-Pulsar watermark
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
        
        return fig
    
    except Exception as e:
        logger.error(f"Error creating 5-day chart for {base}/{quote}: {e}")
        return None

def display_combined_charts(base, quote):
    """
    Display both YTD and 5-day charts for a currency pair in tabs
    
    Args:
        base: Base currency code
        quote: Quote currency code
    """
    # Create tabs for different timeframes
    five_day_tab, ytd_tab = st.tabs(["5-Day","Year-to-Date"])
       
    with five_day_tab:
        # Create and display 5-day chart
        five_day_fig = create_five_day_chart(base, quote)
        if five_day_fig:
            st.plotly_chart(five_day_fig, use_container_width=True)
            
            # Add 5-day stats
            five_day_df = load_five_day_chart_data(base, quote)
            if five_day_df is not None and not five_day_df.empty:
                # Calculate 5-day performance
                five_day_start_rate = five_day_df.iloc[0]['rate']
                current_rate = five_day_df.iloc[-1]['rate']
                five_day_change = ((current_rate - five_day_start_rate) / five_day_start_rate) * 100
                
                # Create stats container
                stats_cols = st.columns(3)
                
                with stats_cols[0]:
                    st.markdown("### 5-Day Performance")
                    change_color = "#4CAF50" if five_day_change > 0 else "#F44336"
                    sign = "+" if five_day_change > 0 else ""
                    st.markdown(f"""
                    <div style="background-color:#1E1E1E; padding:10px; border-radius:5px;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:white;">Change:</span>
                            <span style="color:{change_color};">{sign}{five_day_change:.2f}%</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:white;">High:</span>
                            <span style="color:#4CAF50;">{five_day_df['rate'].max():.4f}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:white;">Low:</span>
                            <span style="color:#F44336;">{five_day_df['rate'].min():.4f}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with stats_cols[1]:
                    st.markdown("### Daily Range")
                    
                    # Group by day and calculate daily ranges
                    five_day_df['date'] = five_day_df['timestamp'].dt.date
                    daily_stats = five_day_df.groupby('date').agg({
                        'rate': ['min', 'max']
                    }).reset_index()
                    
                    daily_stats['range'] = daily_stats[('rate', 'max')] - daily_stats[('rate', 'min')]
                    daily_stats['range_pct'] = (daily_stats['range'] / daily_stats[('rate', 'min')]) * 100
                    
                    # Average daily range
                    avg_daily_range_pct = daily_stats['range_pct'].mean()
                    
                    # Today's range
                    today = datetime.now().date()
                    today_stats = daily_stats[daily_stats['date'] == today]
                    if not today_stats.empty:
                        today_range_pct = today_stats['range_pct'].iloc[0]
                        today_high = today_stats[('rate', 'max')].iloc[0]
                        today_low = today_stats[('rate', 'min')].iloc[0]
                        
                        # Compare today's range with average
                        if today_range_pct > avg_daily_range_pct * 1.5:
                            range_comment = "High volatility today"
                            range_color = "#F44336"  # Red
                        elif today_range_pct < avg_daily_range_pct * 0.5:
                            range_comment = "Low volatility today"
                            range_color = "#4CAF50"  # Green
                        else:
                            range_comment = "Normal volatility today"
                            range_color = "#FFC107"  # Amber
                        
                        st.markdown(f"""
                        <div style="background-color:#1E1E1E; padding:10px; border-radius:5px;">
                            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                <span style="color:white;">Today's Range:</span>
                                <span style="color:white;">{today_range_pct:.2f}%</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                <span style="color:white;">Avg Daily Range:</span>
                                <span style="color:white;">{avg_daily_range_pct:.2f}%</span>
                            </div>
                            <div style="display:flex; justify-content:space-between;">
                                <span style="color:white;">Status:</span>
                                <span style="color:{range_color};">{range_comment}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.info("No data available for today")
                
                with stats_cols[2]:
                    st.markdown("### Intraday Analysis")
                    
                    # Calculate short-term trend using moving averages
                    if len(five_day_df) > 10:
                        # Add simple moving averages
                        five_day_df['SMA10'] = five_day_df['rate'].rolling(window=10).mean()
                        five_day_df['SMA30'] = five_day_df['rate'].rolling(window=30).mean()
                        
                        # Determine trend based on SMA crossovers
                        latest_sma10 = five_day_df['SMA10'].iloc[-1]
                        latest_sma30 = five_day_df['SMA30'].iloc[-1]
                        
                        if latest_sma10 > latest_sma30:
                            intraday_trend = "Bullish"
                            intraday_color = "#4CAF50"  # Green
                        elif latest_sma10 < latest_sma30:
                            intraday_trend = "Bearish"
                            intraday_color = "#F44336"  # Red
                        else:
                            intraday_trend = "Neutral"
                            intraday_color = "#9E9E9E"  # Gray
                        
                        # Calculate intraday momentum 
                        latest_points = five_day_df.iloc[-20:]
                        momentum = (latest_points['rate'].iloc[-1] - latest_points['rate'].iloc[0]) / latest_points['rate'].iloc[0] * 100
                        
                        momentum_str = "Strong" if abs(momentum) > 0.2 else "Moderate" if abs(momentum) > 0.1 else "Weak"
                        momentum_color = "#4CAF50" if momentum > 0 else "#F44336" if momentum < 0 else "#9E9E9E"
                        
                        st.markdown(f"""
                        <div style="background-color:#1E1E1E; padding:10px; border-radius:5px;">
                            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                <span style="color:white;">Intraday Trend:</span>
                                <span style="color:{intraday_color};">{intraday_trend}</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                <span style="color:white;">Momentum:</span>
                                <span style="color:{momentum_color};">{momentum_str}</span>
                            </div>
                            <div style="display:flex; justify-content:space-between;">
                                <span style="color:white;">Last Hour:</span>
                                <span style="color:{momentum_color};">
                                    {'+' if momentum > 0 else ''}{momentum:.2f}%
                                </span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.info("Insufficient data for intraday analysis")
            else:
                st.error("Failed to load 5-day chart data for analysis")
        else:
            st.error("Failed to create 5-day chart. Please check if data is available.")

    with ytd_tab:
        # Create and display YTD chart
        ytd_fig = create_ytd_chart(base, quote)
        if ytd_fig:
            st.plotly_chart(ytd_fig, use_container_width=True)
            
            # Add YTD stats
            ytd_df = load_ytd_chart_data(base, quote)
            if ytd_df is not None and not ytd_df.empty:
                # Calculate YTD performance
                year_start_rate = ytd_df.iloc[0]['rate']
                current_rate = ytd_df.iloc[-1]['rate']
                ytd_change = ((current_rate - year_start_rate) / year_start_rate) * 100
                
                # Create stats container
                stats_cols = st.columns(3)
                
                with stats_cols[0]:
                    st.markdown("### YTD Performance")
                    change_color = "#4CAF50" if ytd_change > 0 else "#F44336"
                    sign = "+" if ytd_change > 0 else ""
                    st.markdown(f"""
                    <div style="background-color:#1E1E1E; padding:10px; border-radius:5px;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:white;">Change:</span>
                            <span style="color:{change_color};">{sign}{ytd_change:.2f}%</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:white;">Start Rate:</span>
                            <span style="color:white;">{year_start_rate:.4f}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:white;">Current Rate:</span>
                            <span style="color:white;">{current_rate:.4f}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with stats_cols[1]:
                    st.markdown("### Volatility")
                    # Calculate volatility (standard deviation of returns)
                    ytd_df['return'] = ytd_df['rate'].pct_change() * 100
                    ytd_volatility = ytd_df['return'].std()
                    
                    # Determine volatility level
                    if ytd_volatility < 0.05:
                        vol_level = "Very Low"
                        color = "#9E9E9E"  # Gray
                    elif ytd_volatility < 0.1:
                        vol_level = "Low"
                        color = "#4CAF50"  # Green
                    elif ytd_volatility < 0.2:
                        vol_level = "Moderate"
                        color = "#FFC107"  # Amber
                    elif ytd_volatility < 0.3:
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
                            <span style="color:white;">{ytd_volatility:.4f}%</span>
                        </div>
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:white;">Sample Points:</span>
                            <span style="color:white;">{len(ytd_df)}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with stats_cols[2]:
                    st.markdown("### Trend Analysis")
                    # Calculate monthly performance
                    if len(ytd_df) > 20:
                        # Add simple moving averages
                        ytd_df['SMA20'] = ytd_df['rate'].rolling(window=20).mean()
                        ytd_df['SMA50'] = ytd_df['rate'].rolling(window=50).mean()
                        
                        # Determine trend based on SMA crossovers
                        latest_sma20 = ytd_df['SMA20'].iloc[-1]
                        latest_sma50 = ytd_df['SMA50'].iloc[-1]
                        
                        if latest_sma20 > latest_sma50:
                            trend = "Bullish"
                            color = "#4CAF50"  # Green
                        elif latest_sma20 < latest_sma50:
                            trend = "Bearish"
                            color = "#F44336"  # Red
                        else:
                            trend = "Neutral"
                            color = "#9E9E9E"  # Gray
                        
                        # Calculate monthly change
                        if len(ytd_df) >= 30:  # About a month of daily data
                            month_ago_rate = ytd_df.iloc[-30]['rate']
                            monthly_change = ((current_rate - month_ago_rate) / month_ago_rate) * 100
                            
                            st.markdown(f"""
                            <div style="background-color:#1E1E1E; padding:10px; border-radius:5px;">
                                <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                    <span style="color:white;">Trend:</span>
                                    <span style="color:{color};">{trend}</span>
                                </div>
                                <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                    <span style="color:white;">Monthly Change:</span>
                                    <span style="color:{'#4CAF50' if monthly_change > 0 else '#F44336'};">
                                        {'+' if monthly_change > 0 else ''}{monthly_change:.2f}%
                                    </span>
                                </div>
                                <div style="display:flex; justify-content:space-between;">
                                    <span style="color:white;">SMA 20/50:</span>
                                    <span style="color:{color};">
                                        {latest_sma20:.4f}/{latest_sma50:.4f}
                                    </span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.info("Insufficient data for monthly statistics")
                    else:
                        st.info("Insufficient data for trend analysis")
            else:
                st.error("Failed to load YTD chart data for analysis")
        else:
            st.error("Failed to create YTD chart. Please check if data is available.")
 
#################################
# Dashboard Integration
#################################

def integrated_forex_dashboard():
    """Main function to run the integrated forex dashboard"""
    st.title("Forex Charts Dashboard")
    
    # Add a description
    st.markdown("""
    This dashboard provides detailed charts and analysis for forex currency pairs.
    It fetches data from Yahoo Finance and stores it locally for better performance.
    - YTD data is fetched once per day
    - 5-day data is fetched in real-time
    """)
    
    # Create a form to select currency pair
    with st.form("currency_selection"):
        cols = st.columns(3)
        
        with cols[0]:
            base_currency = st.selectbox("Base Currency", options=["EUR", "USD", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"])
        
        with cols[1]:
            quote_options = ["EUR", "USD", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]
            # Filter out the base currency
            quote_options = [q for q in quote_options if q != base_currency]
            quote_currency = st.selectbox("Quote Currency", options=quote_options)
        
        with cols[2]:
            fetch_ytd = st.checkbox("Fetch new YTD data", value=False, help="Check this to force a fresh YTD data fetch (once per day is usually sufficient)")
        
        submitted = st.form_submit_button("Load Charts")
    
    if submitted:
        # Show a spinner while fetching data
        with st.spinner(f"Fetching data for {base_currency}/{quote_currency}..."):
            # Fetch and save rate data
            currency_pairs = [(base_currency, quote_currency)]
            rates = scrape_yahoo_finance_rates(currency_pairs, fetch_ytd=fetch_ytd)
            
            # Extract current rate and previous close
            current_rate = None
            previous_close = None
            
            if rates and base_currency in rates and quote_currency in rates[base_currency]:
                rate_data = rates[base_currency][quote_currency]
                current_rate = rate_data.get("price")
                previous_close = rate_data.get("previous_close")
                
                # Display current rate information
                if current_rate is not None:
                    # Calculate percent change
                    percent_change = 0
                    if previous_close is not None:
                        percent_change = ((current_rate - previous_close) / previous_close) * 100
                    
                    # Create a styled header with current rate info
                    col1, col2, col3 = st.columns([1, 2, 1])
                    
                    with col1:
                        st.markdown(f"### {base_currency}/{quote_currency}")
                    
                    with col2:
                        if current_rate < 0.01:
                            formatted_rate = f"{current_rate:.6f}"
                        elif current_rate < 1:
                            formatted_rate = f"{current_rate:.4f}"
                        else:
                            formatted_rate = f"{current_rate:.4f}"
                        
                        st.markdown(f"**Current Rate:** {formatted_rate}")
                        
                        if previous_close is not None:
                            if previous_close < 0.01:
                                prev_formatted = f"{previous_close:.6f}"
                            elif previous_close < 1:
                                prev_formatted = f"{previous_close:.4f}"
                            else:
                                prev_formatted = f"{previous_close:.4f}"
                            
                            st.markdown(f"**Previous Close:** {prev_formatted}")
                    
                    with col3:
                        if percent_change != 0:
                            change_color = "green" if percent_change > 0 else "red"
                            sign = "+" if percent_change > 0 else ""
                            st.markdown(f"**Change:** <span style='color:{change_color};'>{sign}{percent_change:.4f}%</span>", unsafe_allow_html=True)
                
                # Display the charts
                display_combined_charts(base_currency, quote_currency)
                
            else:
                st.error(f"Failed to fetch rate data for {base_currency}/{quote_currency}")
    
    # Add a section for subscription pairs if integrated with the main app
    st.subheader("Subscription Pairs")
    st.markdown("If you have loaded subscription pairs from the main app, they will appear here.")
    
    # This section would check for subscriptions from the main app's session state
    # Placeholder for demonstration
    if 'session_state' in globals() and hasattr(st, 'session_state') and 'subscriptions' in st.session_state:
        for sub in st.session_state.subscriptions:
            if 'base' in sub and 'quote' in sub:
                st.markdown(f"**{sub['base']}/{sub['quote']}**")
                if st.button(f"View Charts for {sub['base']}/{sub['quote']}"):
                    # The same process as above, but for this subscription pair
                    with st.spinner(f"Fetching data for {sub['base']}/{sub['quote']}..."):
                        # Similar code to above, but using the subscription pair
                        pass
    else:
        st.info("No subscription pairs found. Add some in the main app.")
    
    # Add an about section
    with st.expander("About this Dashboard"):
        st.markdown("""
        ### How it works
        
        This dashboard uses the Yahoo Finance API to fetch forex data:
        
        1. **YTD Data**: Fetched once per day and stored for long-term trend analysis
        2. **5-Day Data**: Fetched in real-time for short-term analysis
        3. **Blended Charts**: Combines both data sources for comprehensive visualization
        
        ### Storage
        
        Data is stored locally in:
        - `fx_news/scrapers/rates/ytd/` for YTD data
        - `fx_news/scrapers/rates/5d/` for 5-day data
        
        This allows the dashboard to:
        - Reduce API calls
        - Work offline with previously fetched data
        - Provide faster chart rendering
        
        ### Technical Analysis
        
        The dashboard provides:
        - Moving averages (SMA)
        - Volatility metrics
        - Trend identification
        - Range analysis
        """)

# Check for the current module to decide whether to run standalone or as a module
if __name__ == "__main__":
    integrated_forex_dashboard()
else:
    # When imported, just make functions available
    pass
                