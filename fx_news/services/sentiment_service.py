"""
Sentiment service for fetching and processing trader sentiment data.
Handles Myfxbook trader sentiment data and other sentiment analysis.
"""
import logging
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
import streamlit as st
from bs4 import BeautifulSoup
import random
import json
import plotly.graph_objects as go

from fx_news.data.models import SentimentData
from fx_news.utils.notifications import add_notification

logger = logging.getLogger("sentiment_service")

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

def get_sentiment_for_pair(base: str, quote: str) -> Optional[Dict[str, Any]]:
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

def scrape_myfxbook_sentiment_all_pairs():
    """
    Scrape sentiment data from MyFXBook for all currency pairs.
    
    In a real application, this would connect to the MyFXBook API.
    For this implementation, we'll return mock data.
    
    Returns:
        dict: Sentiment data for all pairs
    """
    try:
        # This would be a real API call or web scraping in a production app
        # For now, we'll generate mock data
        mock_data = create_mock_sentiment_data()
        
        # Format the data
        return {
            'timestamp': datetime.now().isoformat(),
            'source': 'mock_myfxbook',
            'data': mock_data
        }
    except Exception as e:
        logger.error(f"Error scraping MyFXBook sentiment: {str(e)}")
        return None

def create_mock_sentiment_data():
    """
    Create mock sentiment data for testing.
    
    Returns:
        dict: Mock sentiment data
    """
    pairs = [
        'EURUSD', 'USDJPY', 'GBPUSD', 'AUDUSD', 
        'USDCAD', 'EURGBP', 'EURJPY', 'USDCHF',
        'NZDUSD', 'EURCHF', 'GBPJPY', 'AUDJPY'
    ]
    
    result = {}
    
    for pair in pairs:
        # Create semi-realistic sentiment data
        long_percentage = random.randint(25, 75)
        short_percentage = 100 - long_percentage
        
        # Make the rates look realistic for the pair
        if pair == 'EURUSD':
            current_rate = round(random.uniform(1.05, 1.15), 4)
        elif pair == 'USDJPY':
            current_rate = round(random.uniform(105, 115), 2)
        elif pair == 'GBPUSD':
            current_rate = round(random.uniform(1.20, 1.30), 4)
        elif pair == 'AUDUSD':
            current_rate = round(random.uniform(0.65, 0.75), 4)
        elif pair == 'USDCAD':
            current_rate = round(random.uniform(1.25, 1.35), 4)
        elif pair == 'EURGBP':
            current_rate = round(random.uniform(0.85, 0.95), 4)
        else:
            # Generic range for other pairs
            current_rate = round(random.uniform(0.9, 1.5), 4)
            
        # Create variation in prices
        long_price = round(current_rate * (1 + random.uniform(-0.01, 0.01)), 4)
        short_price = round(current_rate * (1 + random.uniform(-0.01, 0.01)), 4)
        
        # Calculate distances
        long_distance = f"{abs(round((current_rate - long_price) / long_price * 100, 2))}%"
        short_distance = f"{abs(round((current_rate - short_price) / short_price * 100, 2))}%"
        
        # Create detailed info
        detailed = {
            'popularity': str(random.randint(1, 20)),
            'long': {
                'volume': f"{random.randint(1000, 50000)} lots",
                'positions': f"{random.randint(100, 5000)}"
            },
            'short': {
                'volume': f"{random.randint(1000, 50000)} lots",
                'positions': f"{random.randint(100, 5000)}"
            }
        }
        
        result[pair] = {
            'long_percentage': long_percentage,
            'short_percentage': short_percentage,
            'long_price': str(long_price),
            'short_price': str(short_price),
            'long_distance': long_distance,
            'short_distance': short_distance,
            'current_rate': str(current_rate),
            'detailed': detailed
        }
    
    return result

def analyze_news_sentiment(news_items, api_key=None):
    """
    Analyze sentiment for a list of news items.
    In a real application, this would use NLP or a sentiment analysis API.
    
    Args:
        news_items: List of news items to analyze
        api_key: API key for sentiment analysis service
        
    Returns:
        list: Updated news items with sentiment scores
    """
    # In a real application, you would call a sentiment analysis API
    # For now, we'll assign random sentiment scores
    for item in news_items:
        if 'sentiment' not in item or not item['sentiment'] or item['sentiment'] == 'neutral':
            # Randomly assign sentiment
            sentiment_value = random.random() * 2 - 1  # -1 to 1
            
            if sentiment_value > 0.2:
                item['sentiment'] = 'positive'
                item['score'] = round(sentiment_value, 2)
            elif sentiment_value < -0.2:
                item['sentiment'] = 'negative'
                item['score'] = round(sentiment_value, 2)
            else:
                item['sentiment'] = 'neutral'
                item['score'] = 0.0
    
    return news_items



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
