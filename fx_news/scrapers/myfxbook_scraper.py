import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime
import os
import json
import re

def scrape_myfxbook_sentiment_all_pairs(debug_log=None, use_mock_fallback=True):
    """
    Scrape sentiment data for all currency pairs from MyFxBook's sentiment page.
    
    Args:
        debug_log: Optional list for logging debug information
        use_mock_fallback: Whether to use mock data if scraping fails
    
    Returns:
        Dictionary containing sentiment data for all pairs
    """
    if debug_log is None:
        debug_log = []
        
    url = "https://www.myfxbook.com/community/outlook"
    debug_log.append(f"Scraping MyFxBook sentiment data from {url}")
    
    try:
        # Add headers to mimic a browser request
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            debug_log.append(f"Successfully retrieved page with status code {response.status_code}")
            
            # Parse HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for the table with id "outlookSymbolsTable"
            table = soup.find('table', id='outlookSymbolsTable')
            
            if table:
                debug_log.append("Found outlookSymbolsTable in the page")
                
                # Get the table rows
                rows = table.find('tbody', id='outlookSymbolsTableContent').find_all('tr')
                
                sentiment_data = {
                    "timestamp": datetime.now().isoformat(),
                    "data": {}
                }
                
                for row in rows:
                    # Extract the currency pair name
                    symbol_cell = row.find('td', id=re.compile(r'symbolNameCell.*'))
                    if not symbol_cell:
                        continue
                        
                    symbol = symbol_cell.text.strip()
                    
                    # Extract the sentiment progress bars
                    progress_bars = row.find('div', class_='progress').find_all('div', class_='progress-bar')
                    if len(progress_bars) != 2:
                        continue
                        
                    # Extract short and long percentages
                    try:
                        short_percentage = int(progress_bars[0]['style'].split(':')[1].replace('%;', '').strip())
                        long_percentage = int(progress_bars[1]['style'].split(':')[1].replace('%;', '').strip())
                    except (ValueError, IndexError, KeyError) as e:
                        debug_log.append(f"Error parsing percentages for {symbol}: {str(e)}")
                        continue
                    
                    # Extract short and long prices
                    short_price_cell = row.find('span', id=re.compile(f'shortPriceCell{symbol}'))
                    long_price_cell = row.find('span', id=re.compile(f'longPriceCell{symbol}'))
                    
                    short_price = short_price_cell.text.strip() if short_price_cell else "N/A"
                    long_price = long_price_cell.text.strip() if long_price_cell else "N/A"
                    
                    # Extract short and long distances from price
                    short_dis_cell = row.find('span', id=re.compile(f'shortDisCell{symbol}'))
                    long_dis_cell = row.find('span', id=re.compile(f'longDisCell{symbol}'))
                    
                    short_distance = short_dis_cell.text.strip() if short_dis_cell else "N/A"
                    long_distance = long_dis_cell.text.strip() if long_dis_cell else "N/A"
                    
                    # Extract current price
                    rate_cell = row.find('span', id=re.compile(f'rateCell{symbol}'))
                    current_rate = rate_cell.text.strip() if rate_cell else "N/A"
                    
                    # Extract detailed sentiment data from hidden popover
                    popover_div = row.find('div', id=re.compile(f'outlookSymbolPopover.*'))
                    detailed_data = {}
                    
                    if popover_div:
                        # Extract trader counts and volume from the table
                        table_rows = popover_div.find_all('tr')
                        for table_row in table_rows[1:]:  # Skip header row
                            cells = table_row.find_all('td')
                            if len(cells) >= 5:
                                action = cells[1].text.strip()
                                percentage = cells[2].text.strip().replace('%', '').strip()
                                volume = cells[3].text.strip()
                                positions = cells[4].text.strip()
                                
                                detailed_data[action.lower()] = {
                                    "percentage": percentage,
                                    "volume": volume,
                                    "positions": positions
                                }
                        
                        # Extract popularity percentage
                        popularity_text = popover_div.find(text=re.compile(r'.*traders are currently trading.*'))
                        if popularity_text:
                            popularity_match = re.search(r'(\d+)% of traders', popularity_text)
                            if popularity_match:
                                detailed_data["popularity"] = popularity_match.group(1)
                    
                    # Store all the data for this currency pair
                    sentiment_data["data"][symbol] = {
                        "short_percentage": short_percentage,
                        "long_percentage": long_percentage,
                        "short_price": short_price,
                        "long_price": long_price,
                        "short_distance": short_distance,
                        "long_distance": long_distance,
                        "current_rate": current_rate,
                        "detailed": detailed_data
                    }
                
                # Save the data to disk
                save_sentiment_data(sentiment_data)
                
                return sentiment_data
            else:
                debug_log.append("Could not find outlookSymbolsTable in the page")
        else:
            debug_log.append(f"Failed to retrieve page: Status code {response.status_code}")
            
    except Exception as e:
        debug_log.append(f"Error scraping MyFxBook sentiment: {str(e)}")
    
    # If we reach here, something went wrong - use mock data as fallback
    if use_mock_fallback:
        debug_log.append("Using mock sentiment data as fallback")
        return create_mock_sentiment_data()
    
    return None

def save_sentiment_data(data):
    """
    Save sentiment data to disk for future reference.
    
    Args:
        data: The sentiment data dictionary
    """
    try:
        # Create directory if it doesn't exist
        save_dir = "fx_news/scrapers/sentiment"
        os.makedirs(save_dir, exist_ok=True)
        
        # Save with timestamp for historical tracking
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{save_dir}/sentiment_all_pairs_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            
        # Also save as latest for quick access
        latest_filename = f"{save_dir}/sentiment_all_pairs_latest.json"
        with open(latest_filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            
    except Exception as e:
        print(f"Error saving sentiment data: {str(e)}")

def load_sentiment_data():
    """
    Load the latest sentiment data for all pairs from disk.
    
    Returns:
        Dictionary containing sentiment data, or None if not found
    """
    try:
        filename = "fx_news/scrapers/sentiment/sentiment_all_pairs_latest.json"
        
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading sentiment data: {str(e)}")
        
    return None

def create_mock_sentiment_data():
    """
    Create mock sentiment data for testing purposes.
    
    Returns:
        Dictionary containing mock sentiment data
    """
    import random
    
    mock_pairs = [
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", 
        "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"
    ]
    
    mock_data = {
        "timestamp": datetime.now().isoformat(),
        "data": {}
    }
    
    for pair in mock_pairs:
        # Generate random sentiment percentages that add up to 100%
        long_pct = random.randint(20, 80)
        short_pct = 100 - long_pct
        
        # Generate random prices and values
        base_price = round(random.uniform(0.5, 2.0), 5)
        current_rate = round(base_price * (1 + random.uniform(-0.01, 0.01)), 5)
        short_price = round(base_price * (1 + random.uniform(-0.05, 0.02)), 5)
        long_price = round(base_price * (1 + random.uniform(-0.02, 0.05)), 5)
        
        # Generate random positions and volumes
        long_positions = random.randint(5000, 25000)
        short_positions = random.randint(5000, 25000)
        long_volume = round(random.uniform(2000, 10000), 2)
        short_volume = round(random.uniform(2000, 10000), 2)
        
        # Create distance strings with red/green formatting
        short_distance = f"<span class='{'red' if short_price < current_rate else 'green'}'>{round((short_price - current_rate) * 10000):+} pips</span>"
        long_distance = f"<span class='{'red' if long_price < current_rate else 'green'}'>{round((long_price - current_rate) * 10000):+} pips</span>"
        
        mock_data["data"][pair] = {
            "short_percentage": short_pct,
            "long_percentage": long_pct,
            "short_price": str(short_price),
            "long_price": str(long_price),
            "short_distance": short_distance,
            "long_distance": long_distance,
            "current_rate": str(current_rate),
            "detailed": {
                "short": {
                    "percentage": str(short_pct),
                    "volume": f"{short_volume:,.2f} lots",
                    "positions": f"{short_positions:,}"
                },
                "long": {
                    "percentage": str(long_pct),
                    "volume": f"{long_volume:,.2f} lots",
                    "positions": f"{long_positions:,}"
                },
                "popularity": str(random.randint(1, 30))
            }
        }
    
    return mock_data

def get_sentiment_for_pair(pair, sentiment_data=None):
    """
    Get sentiment data for a specific currency pair.
    
    Args:
        pair: Currency pair (e.g., "EURUSD")
        sentiment_data: Optional sentiment data dictionary (if not provided, will attempt to load from disk)
        
    Returns:
        Dictionary containing sentiment data for the specified pair, or None if not found
    """
    if sentiment_data is None:
        sentiment_data = load_sentiment_data()
        
    if not sentiment_data or "data" not in sentiment_data:
        return None
        
    # First try direct match
    if pair in sentiment_data["data"]:
        return sentiment_data["data"][pair]
    
    # Try case-insensitive match
    pair_upper = pair.upper()
    for key in sentiment_data["data"].keys():
        if key.upper() == pair_upper:
            return sentiment_data["data"][key]
    
    return None

def display_sentiment_data_in_streamlit(pair=None, sentiment_data=None):
    """
    Display sentiment data in a Streamlit UI.
    
    Args:
        pair: Optional currency pair to display (if None, displays all pairs)
        sentiment_data: Optional sentiment data (if None, will attempt to load from disk)
    """
    import streamlit as st
    import plotly.graph_objects as go
    
    if sentiment_data is None:
        sentiment_data = load_sentiment_data()
        
    if not sentiment_data or "data" not in sentiment_data:
        st.error("No sentiment data available. Please try refreshing the data.")
        return
    
    if pair:
        # Display single pair
        pair_data = get_sentiment_for_pair(pair, sentiment_data)
        if not pair_data:
            st.error(f"No sentiment data found for {pair}")
            return
            
        st.subheader(f"Market Sentiment for {pair}")
        
        # Create a gauge chart for long percentage
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=pair_data["long_percentage"],
            title={'text': "Long Sentiment", 'font': {'size': 24}},
            domain={'x': [0, 1], 'y': [0, 1]},
            gauge={
                'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
                'bar': {'color': "royalblue"},
                'bgcolor': "white",
                'borderwidth': 2,
                'bordercolor': "gray",
                'steps': [
                    {'range': [0, 20], 'color': 'firebrick'},
                    {'range': [20, 40], 'color': 'darkorange'},
                    {'range': [40, 60], 'color': 'gold'},
                    {'range': [60, 80], 'color': 'yellowgreen'},
                    {'range': [80, 100], 'color': 'forestgreen'}
                ],
            }
        ))
        
        fig.update_layout(height=250, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)
        
        # Display detailed data
        col1, col2 = st.columns(2)
        
        if "detailed" in pair_data and "long" in pair_data["detailed"]:
            with col1:
                st.markdown(f"""
                <div style="background-color:#E3F2FD; border-left:4px solid #2196F3; padding:10px; border-radius:5px;">
                    <h3 style="color:#2196F3; margin:0;">LONG {pair_data["long_percentage"]}%</h3>
                    <p style="margin:5px 0;">Price: {pair_data["long_price"]}</p>
                    <p style="margin:5px 0;">Distance: {pair_data["long_distance"]}</p>
                    <p style="margin:5px 0;">Volume: {pair_data["detailed"]["long"]["volume"]}</p>
                    <p style="margin:5px 0;">Positions: {pair_data["detailed"]["long"]["positions"]}</p>
                </div>
                """, unsafe_allow_html=True)
        
        if "detailed" in pair_data and "short" in pair_data["detailed"]:
            with col2:
                st.markdown(f"""
                <div style="background-color:#FFEBEE; border-left:4px solid #F44336; padding:10px; border-radius:5px;">
                    <h3 style="color:#F44336; margin:0;">SHORT {pair_data["short_percentage"]}%</h3>
                    <p style="margin:5px 0;">Price: {pair_data["short_price"]}</p>
                    <p style="margin:5px 0;">Distance: {pair_data["short_distance"]}</p>
                    <p style="margin:5px 0;">Volume: {pair_data["detailed"]["short"]["volume"]}</p>
                    <p style="margin:5px 0;">Positions: {pair_data["detailed"]["short"]["positions"]}</p>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="background-color:#F5F5F5; padding:10px; border-radius:5px; margin-top:10px;">
            <p style="margin:5px 0;">Current Rate: {pair_data["current_rate"]}</p>
            <p style="margin:5px 0;">Popularity: {pair_data["detailed"].get("popularity", "N/A")}% of traders</p>
        </div>
        """, unsafe_allow_html=True)
    
    else:
        # Display all pairs as a comparative chart
        st.subheader("Market Sentiment Comparison")
        
        # Prepare data for the chart
        pairs = []
        long_percentages = []
        short_percentages = []
        popularity = []
        
        for pair, data in sentiment_data["data"].items():
            pairs.append(pair)
            long_percentages.append(data["long_percentage"])
            short_percentages.append(data["short_percentage"])
            if "detailed" in data and "popularity" in data["detailed"]:
                try:
                    popularity.append(int(data["detailed"]["popularity"]))
                except (ValueError, TypeError):
                    popularity.append(0)
            else:
                popularity.append(0)
        
        # Sort pairs by popularity
        sorted_indices = sorted(range(len(popularity)), key=lambda i: popularity[i], reverse=True)
        sorted_pairs = [pairs[i] for i in sorted_indices]
        sorted_long = [long_percentages[i] for i in sorted_indices]
        sorted_short = [short_percentages[i] for i in sorted_indices]
        sorted_popularity = [popularity[i] for i in sorted_indices]
        
        # Take top 20 pairs by popularity
        top_n = min(20, len(sorted_pairs))
        sorted_pairs = sorted_pairs[:top_n]
        sorted_long = sorted_long[:top_n]
        sorted_short = sorted_short[:top_n]
        sorted_popularity = sorted_popularity[:top_n]
        
        # Create horizontal bar chart
        fig = go.Figure()
        
        # Add bars for long percentages
        fig.add_trace(go.Bar(
            y=sorted_pairs,
            x=sorted_long,
            name='Long',
            orientation='h',
            marker=dict(
                color='rgba(33, 150, 243, 0.8)',
                line=dict(color='rgba(33, 150, 243, 1.0)', width=2)
            )
        ))
        
        # Add bars for short percentages
        fig.add_trace(go.Bar(
            y=sorted_pairs,
            x=sorted_short,
            name='Short',
            orientation='h',
            marker=dict(
                color='rgba(244, 67, 54, 0.8)',
                line=dict(color='rgba(244, 67, 54, 1.0)', width=2)
            )
        ))
        
        # Update layout
        fig.update_layout(
            title="Market Sentiment Comparison (Top 20 by Popularity)",
            barmode='group',
            xaxis_title="Percentage (%)",
            yaxis_title="Currency Pair",
            legend_title="Position Type",
            height=600,
            margin=dict(l=10, r=10, t=50, b=10),
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Display a table with the data
        st.subheader("Detailed Sentiment Data")
        
        # Convert to dataframe for table display
        sentiment_rows = []
        for pair in sorted_pairs:
            data = sentiment_data["data"][pair]
            
            # Extract volumes and positions
            short_volume = ""
            short_positions = ""
            long_volume = ""
            long_positions = ""
            
            if "detailed" in data:
                if "short" in data["detailed"]:
                    short_volume = data["detailed"]["short"]["volume"]
                    short_positions = data["detailed"]["short"]["positions"]
                if "long" in data["detailed"]:
                    long_volume = data["detailed"]["long"]["volume"]
                    long_positions = data["detailed"]["long"]["positions"]
                    
            # Add row
            sentiment_rows.append({
                "Pair": pair,
                "Long %": data["long_percentage"],
                "Short %": data["short_percentage"],
                "Long Volume": long_volume,
                "Short Volume": short_volume,
                "Long Positions": long_positions,
                "Short Positions": short_positions,
                "Current Rate": data["current_rate"],
                "Popularity": f"{data['detailed'].get('popularity', 'N/A')}%"
            })
        
        # Display the dataframe
        st.dataframe(pd.DataFrame(sentiment_rows))

def create_sentiment_tab_ui(base, quote):
    """
    Create a sentiment tab UI for the FX monitoring app.
    
    Args:
        base: Base currency code
        quote: Quote currency code
    """
    import streamlit as st
    
    # Format the pair for MyFxBook
    pair = f"{base}{quote}"
    
    # Try to load sentiment data
    sentiment_data = load_sentiment_data()
    
    if not sentiment_data or "data" not in sentiment_data:
        st.info(f"No sentiment data available for {base}/{quote}. Try refreshing the data.")
        
        if st.button(f"Fetch {base}/{quote} Sentiment Data"):
            with st.spinner("Fetching sentiment data..."):
                # Scrape all sentiment data
                sentiment_data = scrape_myfxbook_sentiment_all_pairs()
                if sentiment_data:
                    st.success("Sentiment data updated successfully!")
                    st.rerun()
                else:
                    st.error("Failed to fetch sentiment data. Please try again later.")
        return
    
    # Get sentiment data for this pair
    pair_data = get_sentiment_for_pair(pair, sentiment_data)
    
    if not pair_data:
        st.info(f"No sentiment data available for {base}/{quote}.")
        return
    
    # Display the sentiment data
    # Create columns for Long and Short
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
        <div style="background-color:#E3F2FD; border-left:4px solid #2196F3; padding:10px; border-radius:5px;">
            <h3 style="color:#2196F3; margin:0;">LONG {pair_data["long_percentage"]}%</h3>
            <p style="margin:5px 0;">Price: {pair_data["long_price"]}</p>
            <p style="margin:5px 0;">Distance: {pair_data["long_distance"]}</p>
        </div>
        """, unsafe_allow_html=True)
        
        if "detailed" in pair_data and "long" in pair_data["detailed"]:
            st.markdown(f"""
            <div style="background-color:#E3F2FD; border-left:4px solid #2196F3; padding:10px; border-radius:5px; margin-top:10px;">
                <p style="margin:5px 0;">Volume: {pair_data["detailed"]["long"]["volume"]}</p>
                <p style="margin:5px 0;">Positions: {pair_data["detailed"]["long"]["positions"]}</p>
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div style="background-color:#FFEBEE; border-left:4px solid #F44336; padding:10px; border-radius:5px;">
            <h3 style="color:#F44336; margin:0;">SHORT {pair_data["short_percentage"]}%</h3>
            <p style="margin:5px 0;">Price: {pair_data["short_price"]}</p>
            <p style="margin:5px 0;">Distance: {pair_data["short_distance"]}</p>
        </div>
        """, unsafe_allow_html=True)
        
        if "detailed" in pair_data and "short" in pair_data["detailed"]:
            st.markdown(f"""
            <div style="background-color:#FFEBEE; border-left:4px solid #F44336; padding:10px; border-radius:5px; margin-top:10px;">
                <p style="margin:5px 0;">Volume: {pair_data["detailed"]["short"]["volume"]}</p>
                <p style="margin:5px 0;">Positions: {pair_data["detailed"]["short"]["positions"]}</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Create a simple gauge chart for long percentage
    import plotly.graph_objects as go
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pair_data["long_percentage"],
        title={'text': "Long Sentiment", 'font': {'size': 24}},
        domain={'x': [0, 1], 'y': [0, 1]},
        gauge={
            'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "royalblue"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 20], 'color': 'firebrick'},
                {'range': [20, 40], 'color': 'darkorange'},
                {'range': [40, 60], 'color': 'gold'},
                {'range': [60, 80], 'color': 'yellowgreen'},
                {'range': [80, 100], 'color': 'forestgreen'}
            ],
        }
    ))
    
    fig.update_layout(height=250, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)
    
    # Display current rate and popularity
    st.markdown(f"""
    <div style="background-color:#F5F5F5; padding:10px; border-radius:5px; margin-top:10px;">
        <p style="margin:5px 0;">Current Rate: {pair_data["current_rate"]}</p>
        <p style="margin:5px 0;">Popularity: {pair_data["detailed"].get("popularity", "N/A")}% of traders</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Add a refresh button
    if st.button(f"Refresh Sentiment Data"):
        with st.spinner("Refreshing sentiment data..."):
            new_data = scrape_myfxbook_sentiment_all_pairs()
            if new_data:
                st.success("Sentiment data updated successfully!")
                st.rerun()
            else:
                st.error("Failed to refresh sentiment data. Please try again later.")

def update_all_sentiment_data():
    """
    Update sentiment data for all pairs.
    
    Returns:
        Dictionary containing the updated sentiment data
    """
    return scrape_myfxbook_sentiment_all_pairs()

# Example usage (for testing)
if __name__ == "__main__":
    # Test the scraper
    sentiment_data = scrape_myfxbook_sentiment_all_pairs()
    
    if sentiment_data:
        print(f"Successfully scraped sentiment data for {len(sentiment_data['data'])} currency pairs")
        print(sentiment_data)
        # Print a sample of the data
        for pair, data in list(sentiment_data["data"].items())[:3]:
            print(f"\n{pair}:")
            print(f"  Long: {data['long_percentage']}%, Short: {data['short_percentage']}%")
            print(f"  Current Rate: {data['current_rate']}")
            if "detailed" in data and "popularity" in data["detailed"]:
                print(f"  Popularity: {data['detailed']['popularity']}% of traders")
    else:
        print("Failed to scrape sentiment data")