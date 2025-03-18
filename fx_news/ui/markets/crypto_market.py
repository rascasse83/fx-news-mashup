"""
Crypto market specific UI components for the FX Pulsar application.
Contains functions for displaying cryptocurrency market data and visualizations.
"""
import streamlit as st
import random
from typing import List, Dict, Any, Optional
from datetime import datetime

from fx_news.ui.components.charts import display_treemap, display_volatility_gauge
from fx_news.services.sentiment_service import calculate_market_volatility

def display_crypto_market_overview():
    """Display the cryptocurrency market overview section."""
    # Calculate volatility indices first
    volatility_index, pair_volatility = calculate_market_volatility(st.session_state.subscriptions)
    
    # Header area with volatility index
    header_col1, header_col2 = st.columns([2, 1])

    with header_col1:
        st.markdown("<h1 class='main-header'>₿ Crypto Market Monitor</h1>", unsafe_allow_html=True)
        
        # Updated subtitle for crypto mode
        sentiment_url = "https://huggingface.co/yiyanghkust/finbert-tone"
        st.markdown(
            f"Real-time cryptocurrency prices and market sentiment [.]({sentiment_url})",
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
    
    # Display crypto market visualization
    st.subheader("Cryptocurrency Market Overview")
    display_crypto_market_visualization()
    
    # Add crypto market summary
    display_crypto_market_summary()


def display_crypto_market_visualization():
    """Display a cryptocurrency market visualization using a treemap."""
    
    # Market cap estimates for common cryptocurrencies
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
                "change": percent_change,
                "label": f"{sub['base']}/{sub['quote']}: ${sub['current_rate']:.2f}"
            })
    
    if not crypto_data:
        st.info("No crypto data available yet. Add some cryptocurrency pairs to see the visualization.")
        return
    
    # Use the treemap chart component
    display_treemap(
        data=crypto_data,
        values_field="value",
        labels_field="label",
        color_field="change",
        height=300
    )
    
    # Add a small description
    st.markdown("""
    <div style="margin-top: -15px; text-align: center; font-size: 0.8rem; color: #888;">
    Treemap shows relative market importance with area proportional to market capitalization.
    Green indicates positive change, red indicates negative change.
    </div>
    """, unsafe_allow_html=True)


def display_crypto_market_summary():
    """Display cryptocurrency market summary with top gainers, losers, and volume."""
    if not st.session_state.subscriptions:
        return
        
    # Get crypto data from subscriptions
    crypto_data = []
    
    for sub in st.session_state.subscriptions:
        if sub["current_rate"] is not None:
            # Calculate percent change
            percent_change = 0
            if sub.get("previous_close") is not None:
                percent_change = ((sub["current_rate"] - sub["previous_close"]) / sub["previous_close"]) * 100
            elif sub.get("last_rate") is not None:
                percent_change = ((sub["current_rate"] - sub["last_rate"]) / sub["last_rate"]) * 100
            
            crypto_data.append({
                "coin": sub["base"],
                "quote": sub["quote"],
                "price": sub["current_rate"],
                "change": percent_change
            })
    
    if not crypto_data:
        return
        
    # Create table views for the data
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
            # Create a realistic volume simulation based on coin type and current price
            # Convert price to a more reasonable value for volume calculation
            price_factor = coin["price"] if coin["price"] < 100 else 100
            
            # Base volume on price with some randomization
            if coin["coin"] == "BTC":
                base_volume = 2_000_000_000  # $2B for Bitcoin
            elif coin["coin"] == "ETH":
                base_volume = 1_500_000_000  # $1.5B for Ethereum
            elif coin["coin"] in ["USDT", "USDC", "BUSD"]:
                base_volume = 1_000_000_000  # $1B for stablecoins
            elif coin["coin"] in ["BNB", "SOL", "XRP"]:
                base_volume = 500_000_000  # $500M for high-cap alts
            else:
                base_volume = 100_000_000  # $100M for other alts
                
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


def display_crypto_events(base_currency=None):
    """
    Display cryptocurrency events calendar.
    
    Args:
        base_currency: Optional base currency to filter events for
    """
    from fx_news.services.crypto_service import fetch_all_crypto_events
    
    # Fetch crypto events if not already loaded
    if 'crypto_events' not in st.session_state or not st.session_state.crypto_events:
        events = fetch_all_crypto_events()
    else:
        events = st.session_state.crypto_events
    
    if not events:
        st.info("No cryptocurrency events found. Try refreshing the calendar.")
        return
    
    # Filter events if base_currency is provided
    if base_currency:
        filtered_events = [event for event in events if base_currency.upper() in event['coin'].upper()]
        
        if not filtered_events:
            st.info(f"No events found for {base_currency}. Showing all events instead.")
            filtered_events = events
    else:
        filtered_events = events
    
    # Group events by type
    event_types = set(event['type'] for event in filtered_events)
    
    for event_type in event_types:
        type_events = [e for e in filtered_events if e['type'] == event_type]
        st.markdown(f"### {event_type} Events")
        
        for event in type_events:
            # Determine color based on event type
            type_color = {  
                "Release": "#4CAF50",
                "AMA": "#9C27B0",
                "Airdrop": "#FF9800",
                "Partnership": "#2196F3",
                "Tokenomics": "#F44336"
            }.get(event.get('type'), "#1E88E5")
            
            # Format date
            date_str = event.get('date', '')
            if date_str:
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    date_str = date_obj.strftime('%a, %b %d')
                except:
                    pass
            
            # Create event card
            st.markdown(f"""
            <div style="background-color:#1E1E1E; border-left:4px solid {type_color}; padding:15px; margin-bottom:15px; border-radius:5px;">
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
            """, unsafe_allow_html=True)