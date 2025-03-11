# pages/3_Trader_Sentiment.py

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import random
import json

from fx_news.scrapers.myfxbook_scraper import (
    scrape_myfxbook_sentiment_all_pairs, 
    get_sentiment_for_pair,
    load_sentiment_data,
    update_all_sentiment_data
)

# Configure page
st.set_page_config(
    page_title="FX Pulsar - Trader Sentiment",
    page_icon="https://images.seeklogo.com/logo-png/60/1/lmax-digital-icon-black-logo-png_seeklogo-609777.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply custom CSS
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
    
    /* Custom styles for the sentiment dashboard */
    .sentiment-header {
        font-size: 2rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    
    .sentiment-subheader {
        font-size: 1.5rem;
        margin-bottom: 1rem;
        color: #888;
    }
    
    .info-card {
        background-color: #1E1E1E;
        border-radius: 5px;
        padding: 15px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# Function to add a notification
def add_notification(message, type='system'):
    if 'notifications' not in st.session_state:
        st.session_state.notifications = []
        
    notification = {
        "id": int(datetime.now().timestamp() * 1000),
        "message": message,
        "type": type,
        "timestamp": datetime.now()
    }
    st.session_state.notifications.insert(0, notification)
    # Keep only the 20 most recent notifications
    if len(st.session_state.notifications) > 20:
        st.session_state.notifications = st.session_state.notifications[:20]

# Page header
st.markdown("<h1 class='sentiment-header'>👥 Trader Sentiment Dashboard</h1>", unsafe_allow_html=True)
st.markdown("<p class='sentiment-subheader'>Real-time trader positioning and sentiment analysis</p>", unsafe_allow_html=True)

# Main content
col1, col2 = st.columns([2, 1])

formatted_time = "Unknown"

with col1:
    # Overview section
    st.subheader("Trader Sentiment Overview")
    
    # Check for selected pair for detailed view
    if 'selected_pair' in st.session_state and st.session_state.selected_pair:
        selected_pair = st.session_state.selected_pair
        # Create a back button
        if st.button("← Back to Overview"):
            del st.session_state.selected_pair
            st.rerun()
        
        # Display detailed view for selected pair
        st.markdown(f"## Detailed Analysis: {selected_pair}")
        
        # Get sentiment data
        sentiment_data = load_sentiment_data()
        
        # Get detailed data for this pair
        pair_data = sentiment_data.get('data', {}).get(selected_pair, {})
        
        if pair_data:
            # Extract data
            long_pct = pair_data.get('long_percentage', 0)
            short_pct = pair_data.get('short_percentage', 0)
            current_rate = pair_data.get('current_rate', 'N/A')
            long_price = pair_data.get('long_price', 'N/A')
            short_price = pair_data.get('short_price', 'N/A')
            long_distance = pair_data.get('long_distance', 'N/A')
            short_distance = pair_data.get('short_distance', 'N/A')
            
            # Get detailed data if available
            volume = pair_data.get('detailed', {}).get('short', {}).get('volume', 'N/A')
            positions = pair_data.get('detailed', {}).get('short', {}).get('positions', 'N/A')
            popularity = pair_data.get('detailed', {}).get('popularity', 'N/A')
            
            # Create two columns for the details
            detail_col1, detail_col2 = st.columns([1, 1])
            
            with detail_col1:
                # Create large donut chart
                fig = go.Figure()
                
                fig.add_trace(go.Pie(
                    labels=['Long', 'Short'],
                    values=[long_pct, short_pct],
                    hole=0.7,
                    marker=dict(
                        colors=['#4CAF50', '#F44336'],  # Green for long, red for short
                    ),
                    textinfo='label+percent',
                    insidetextfont=dict(color='white', size=16),
                    textfont=dict(color='white', size=16),
                    hoverinfo='label+percent',
                    showlegend=False
                ))
                
                # Add current rate as annotation in the center
                fig.update_layout(
                    annotations=[dict(
                        text=f"<b>{current_rate}</b>",
                        x=0.5, y=0.5,
                        font=dict(size=24, color='white'),
                        showarrow=False
                    )]
                )
                
                # Style the chart
                fig.update_layout(
                    height=400,
                    margin=dict(l=10, r=10, t=10, b=10),
                    paper_bgcolor="#121212",
                    plot_bgcolor="#121212",
                    font=dict(color='white')
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            with detail_col2:
                # Display detailed statistics
                st.markdown("### Position Details")
                
                # Create styled cards for detailed info
                st.markdown(
                    f"""
                    <div style="background-color:#1E1E1E; border-radius:5px; padding:15px; margin-bottom:15px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                            <span style="color:white; font-weight:bold; font-size:18px;">Current Rate</span>
                            <span style="color:white; font-weight:bold; font-size:18px;">{current_rate}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:#AAAAAA;">Popularity Rank:</span>
                            <span style="color:white;">{popularity}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:#AAAAAA;">Total Positions:</span>
                            <span style="color:white;">{positions}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:#AAAAAA;">Total Volume:</span>
                            <span style="color:white;">{volume}</span>
                        </div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
                
                # Long positions card
                st.markdown(
                    f"""
                    <div style="background-color:#1E1E1E; border-radius:5px; padding:15px; margin-bottom:15px; border-left: 4px solid #4CAF50;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                            <span style="color:#4CAF50; font-weight:bold; font-size:18px;">LONG</span>
                            <span style="color:#4CAF50; font-weight:bold; font-size:18px;">{long_pct}%</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:#AAAAAA;">Average Price:</span>
                            <span style="color:white;">{long_price}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:#AAAAAA;">Distance to Current:</span>
                            <span style="color:white;">{long_distance}</span>
                        </div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
                
                # Short positions card
                st.markdown(
                    f"""
                    <div style="background-color:#1E1E1E; border-radius:5px; padding:15px; margin-bottom:15px; border-left: 4px solid #F44336;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                            <span style="color:#F44336; font-weight:bold; font-size:18px;">SHORT</span>
                            <span style="color:#F44336; font-weight:bold; font-size:18px;">{short_pct}%</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:#AAAAAA;">Average Price:</span>
                            <span style="color:white;">{short_price}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:#AAAAAA;">Distance to Current:</span>
                            <span style="color:white;">{short_distance}</span>
                        </div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            
            # Add an interpretation section
            st.markdown("### Sentiment Interpretation")
            
            # Generate analysis based on the data
            if long_pct > 70:
                analysis = f"Strong bullish retail sentiment with {long_pct}% of traders long. Typically, strong retail positioning can be a contrarian indicator, suggesting caution for further upside moves."
                risk = "HIGH RISK for further long positions"
                contrarian = f"Consider short positions if technical indicators show signs of reversal."
                color = "#F44336"  # Red
            elif long_pct > 60:
                analysis = f"Moderately bullish retail sentiment with {long_pct}% of traders long. The market may continue its uptrend, but watch for signs of exhaustion."
                risk = "MODERATE RISK for further long positions"
                contrarian = f"Be cautious with new long entries at these levels."
                color = "#FF9800"  # Orange
            elif short_pct > 70:
                analysis = f"Strong bearish retail sentiment with {short_pct}% of traders short. This level of bearish positioning often acts as a contrarian indicator, suggesting potential for upside reversals."
                risk = "HIGH RISK for further short positions"
                contrarian = f"Consider long positions if technical indicators show signs of reversal."
                color = "#4CAF50"  # Green
            elif short_pct > 60:
                analysis = f"Moderately bearish retail sentiment with {short_pct}% of traders short. The market may continue its downtrend, but watch for signs of a bottoming pattern."
                risk = "MODERATE RISK for further short positions"
                contrarian = f"Be cautious with new short entries at these levels."
                color = "#8BC34A"  # Light green
            else:
                analysis = f"Mixed sentiment with {long_pct}% long and {short_pct}% short indicates no clear consensus among retail traders. Price could move in either direction based on upcoming catalysts."
                risk = "NEUTRAL RISK profile"
                contrarian = f"Wait for a clearer sentiment extreme or technical setup before entering."
                color = "#9E9E9E"  # Gray
            
            # Create analysis card
            st.markdown(
                f"""
                <div style="background-color:#1E1E1E; border-radius:5px; padding:20px; margin-bottom:15px; border-left: 4px solid {color};">
                    <div style="font-weight:bold; font-size:18px; margin-bottom:15px; color:white;">{risk}</div>
                    <p style="color:white; margin-bottom:15px;">{analysis}</p>
                    <p style="color:#BBBBBB; font-style:italic; margin-bottom:0px;">{contrarian}</p>
                </div>
                """, 
                unsafe_allow_html=True
            )
            
            # Add simulated historical sentiment chart (since we don't have real historical data)
            st.markdown("### Sentiment History (Simulated)")
            st.caption("Note: This chart shows simulated historical data for demonstration purposes.")
            
            # Create simulated historical data
            days = 14  # Two weeks of data
            base_long = long_pct
            
            # Create random variations around the current value
            np.random.seed(42)  # For reproducibility
            dates = [(datetime.now() - timedelta(days=i)).strftime("%m-%d") for i in range(days)]
            dates.reverse()  # Put in chronological order
            
            # Create somewhat realistic variations
            long_values = []
            base = base_long
            for i in range(days):
                # Add a small random shift between -5 and +5
                shift = np.random.normal(0, 2.5)
                # Ensure we stay within 10-90 range
                new_value = max(10, min(90, base + shift))
                long_values.append(new_value)
                # Update base for next iteration (with a slight trend back to mean)
                base = 0.8 * new_value + 0.2 * base_long
            
            # Create short values as complement
            short_values = [100 - lv for lv in long_values]
            
            # Create DataFrame for plotting
            hist_df = pd.DataFrame({
                'Date': dates,
                'Long %': long_values,
                'Short %': short_values
            })
            
            # Create a stacked area chart
            fig = px.area(hist_df, x='Date', y=['Long %', 'Short %'], 
                         title='Sentiment History', height=350)
            
            # Customize colors
            fig.update_traces(marker=dict(line=dict(width=0)),
                             selector=dict(name='Long %'), 
                             fill='tozeroy', 
                             fillcolor='rgba(76, 175, 80, 0.7)')
            
            fig.update_traces(marker=dict(line=dict(width=0)),
                             selector=dict(name='Short %'), 
                             fill='tonexty', 
                             fillcolor='rgba(244, 67, 54, 0.7)')
            
            # Apply dark theme styling
            fig.update_layout(
                paper_bgcolor="#121212",
                plot_bgcolor="#121212",
                font=dict(color="#FFFFFF"),
                xaxis=dict(
                    showgrid=False,
                    zeroline=False,
                    tickfont=dict(color="#FFFFFF", size=12)
                ),
                yaxis=dict(
                    showgrid=True,
                    gridcolor="#333333",
                    tickcolor="#FFFFFF",
                    tickfont=dict(color="#FFFFFF", size=12)
                ),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="center",
                    x=0.5,
                    font=dict(color="#FFFFFF")
                )
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.warning(f"No detailed data available for {selected_pair}")
        
        # Don't display the overview when showing detailed view
        # Instead of return, we'll use a conditional structure
    else:
        # This is the overview section to show when no pair is selected
        # Load sentiment data
        sentiment_data = load_sentiment_data()
        
        # Check if we have data
        if not sentiment_data or not sentiment_data.get('data'):
            st.info("No sentiment data available. Please fetch the data.")
            if st.button("Fetch Trader Sentiment Data"):
                update_all_sentiment_data(force=True)
                st.rerun()
        else:
            # Create a dashboard of sentiment gauges
            pairs_data = sentiment_data.get('data', {})
            
            # Add sort controls
            st.caption(f"Data as of: {formatted_time}")
            
            # Add sort and filter controls
            sort_col1, sort_col2, filter_col1, filter_col2 = st.columns([1, 1.5, 1, 1.5])
            
            with sort_col1:
                st.caption("Sort by:")
            
            with sort_col2:
                # Initialize session state for sort preference if it doesn't exist
                if 'sentiment_sort_method' not in st.session_state:
                    st.session_state.sentiment_sort_method = 'popularity'
                
                # Create radio buttons for sort method
                sort_method = st.radio(
                    label="",
                    options=["Popularity", "Alphabetical"],
                    index=0 if st.session_state.sentiment_sort_method == 'popularity' else 1,
                    horizontal=True,
                    label_visibility="collapsed"
                )
                
                # Update session state if changed
                if sort_method == "Popularity" and st.session_state.sentiment_sort_method != 'popularity':
                    st.session_state.sentiment_sort_method = 'popularity'
                    st.rerun()
                elif sort_method == "Alphabetical" and st.session_state.sentiment_sort_method != 'alphabetical':
                    st.session_state.sentiment_sort_method = 'alphabetical'
                    st.rerun()
            
            with filter_col1:
                st.caption("Filter:")
                
            with filter_col2:
                # Initialize filter preference if it doesn't exist
                if 'sentiment_filter' not in st.session_state:
                    st.session_state.sentiment_filter = 'all'
                
                # Create filter toggle
                filter_option = st.radio(
                    label="",
                    options=["All Pairs", "Top 10"],
                    index=0 if st.session_state.sentiment_filter == 'all' else 1,
                    horizontal=True,
                    label_visibility="collapsed"
                )
                
                # Update session state if changed
                if filter_option == "All Pairs" and st.session_state.sentiment_filter != 'all':
                    st.session_state.sentiment_filter = 'all'
                    st.rerun()
                elif filter_option == "Top 10" and st.session_state.sentiment_filter != 'top10':
                    st.session_state.sentiment_filter = 'top10'
                    st.rerun()
                
            # Sort pairs based on selected method
            if st.session_state.sentiment_sort_method == 'alphabetical':
                # Sort alphabetically
                sorted_pairs = sorted(pairs_data.keys())
            else:
                # Sort by popularity (default)
                pairs_with_popularity = [(pair, pairs_data[pair].get('detailed', {}).get('popularity', '99')) 
                                        for pair in pairs_data.keys()]
                sorted_pairs = [p[0] for p in sorted(pairs_with_popularity, 
                                                    key=lambda x: int(x[1]) if str(x[1]).isdigit() else 99)]
            
            # Apply filter if needed
            if st.session_state.sentiment_filter == 'top10':
                # Get top 10 by popularity
                pairs_with_popularity = [(pair, pairs_data[pair].get('detailed', {}).get('popularity', '99')) 
                                        for pair in pairs_data.keys()]
                # Sort by popularity (lower number is more popular)
                pairs_by_popularity = sorted(pairs_with_popularity, 
                                            key=lambda x: int(x[1]) if str(x[1]).isdigit() else 99)
                # Take top 10 only
                top10_pairs = [p[0] for p in pairs_by_popularity[:10]]
                # Filter the sorted list to only include top 10 pairs
                sorted_pairs = [pair for pair in sorted_pairs if pair in top10_pairs]
            
            # Refresh button
            if st.button("Refresh Sentiment Data"):
                update_all_sentiment_data(force=True)
                st.rerun()
                
            # Display gauges in a grid - 3 per row
            for i in range(0, len(sorted_pairs), 3):
                row_pairs = sorted_pairs[i:i+3]
                cols = st.columns(3)
                
                for j, pair in enumerate(row_pairs):
                    if j < len(cols):
                        with cols[j]:
                            pair_data = pairs_data[pair]
                            
                            # Extract sentiment data
                            long_pct = pair_data.get('long_percentage', 0)
                            short_pct = pair_data.get('short_percentage', 0)
                            current_rate = pair_data.get('current_rate', 'N/A')
                            
                            # Create donut chart
                            fig = go.Figure()
                            
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
                                title={"text": f"{pair}", "font": {"color": "white", "size": 18}},
                                height=250,
                                margin=dict(l=10, r=10, t=40, b=10),
                                paper_bgcolor="#121212",
                                plot_bgcolor="#121212",
                                font=dict(color='white')
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # Add quick info below the chart
                            st.markdown(
                                f"""
                                <div class="info-card">
                                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                        <span style="color:#AAAAAA;">Long Price:</span>
                                        <span style="color:white;">{pair_data.get('long_price', 'N/A')}</span>
                                    </div>
                                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                        <span style="color:#AAAAAA;">Long Distance:</span>
                                        <span style="color:white;">{pair_data.get('long_distance', 'N/A')}</span>
                                    </div>
                                    <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                        <span style="color:#AAAAAA;">Short Price:</span>
                                        <span style="color:white;">{pair_data.get('short_price', 'N/A')}</span>
                                    </div>
                                    <div style="display:flex; justify-content:space-between;">
                                        <span style="color:#AAAAAA;">Short Distance:</span>
                                        <span style="color:white;">{pair_data.get('short_distance', 'N/A')}</span>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                            
                            # Add a link to detailed analysis
                            if st.button(f"View Details", key=f"details_{pair}"):
                                st.session_state.selected_pair = pair
                                st.rerun()

with col2:
    # Sidebar-like info panel
    st.subheader("Market Insights")
    
    # Create analysis cards based on the sentiment data
    if 'fxbook_sentiment_data' in st.session_state and st.session_state.fxbook_sentiment_data:
        sentiment_data = st.session_state.fxbook_sentiment_data
        pairs_data = sentiment_data.get('data', {})
        
        # Calculate average sentiment 
        total_long = 0
        total_short = 0
        count = 0
        
        for pair, data in pairs_data.items():
            long_pct = data.get('long_percentage', 0)
            short_pct = data.get('short_percentage', 0)
            if long_pct and short_pct:
                total_long += long_pct
                total_short += short_pct
                count += 1
        
        # Calculate averages if we have data
        if count > 0:
            avg_long = round(total_long / count)
            avg_short = round(total_short / count)
            
            # Overall market sentiment gauge
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=avg_long,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Market Sentiment", 'font': {'color': 'white', 'size': 16}},
                gauge={
                    'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
                    'bar': {'color': "#4D9BF5"},
                    'bgcolor': "gray",
                    'borderwidth': 1,
                    'bordercolor': "white",
                    'steps': [
                        {'range': [0, 25], 'color': '#F44336'},  # Red (very bearish)
                        {'range': [25, 40], 'color': '#FF9800'},  # Orange (bearish)
                        {'range': [40, 60], 'color': '#9E9E9E'},  # Gray (neutral)
                        {'range': [60, 75], 'color': '#8BC34A'},  # Light green (bullish)
                        {'range': [75, 100], 'color': '#4CAF50'}  # Green (very bullish)
                    ],
                },
                number={'suffix': "%<br>LONG", 'font': {'color': 'white'}}
            ))
            
            # Make the gauge compact
            fig.update_layout(
                height=200,
                margin=dict(l=10, r=10, t=30, b=10),
                paper_bgcolor="#121212",
                font=dict(color="white", size=12)
            )
            
            # Display the gauge
            st.plotly_chart(fig, use_container_width=True)
            
            # Market bias analysis
            if avg_long > 65:
                bias = "Bullish bias"
                description = "Retail traders are heavily positioned LONG. This often acts as a contrarian indicator, suggesting potential downside risks."
                color = "#4CAF50"  # Green
            elif avg_long > 55:
                bias = "Slight bullish bias"
                description = "Retail traders are leaning LONG. Be cautious of potential trend exhaustion."
                color = "#8BC34A"  # Light green
            elif avg_short > 65:
                bias = "Bearish bias"
                description = "Retail traders are heavily positioned SHORT. This often acts as a contrarian indicator, suggesting potential upside surprises."
                color = "#F44336"  # Red
            elif avg_short > 55:
                bias = "Slight bearish bias"
                description = "Retail traders are leaning SHORT. Be cautious of potential trend exhaustion."
                color = "#FF9800"  # Orange
            else:
                bias = "Neutral bias"
                description = "Retail traders are fairly balanced between long and short positions, indicating no clear consensus."
                color = "#9E9E9E"  # Gray
            
            # Market bias card
            st.markdown(
                f"""
                <div style="background-color:#1E1E1E; border-radius:5px; padding:15px; margin-bottom:15px; border-left: 4px solid {color};">
                    <div style="font-weight:bold; font-size:18px; margin-bottom:10px; color:{color};">{bias}</div>
                    <p style="color:white; margin-bottom:0px;">{description}</p>
                </div>
                """, 
                unsafe_allow_html=True
            )
        
        # Find the most one-sided pairs
        pairs_with_data = []
        for pair, data in pairs_data.items():
            long_pct = data.get('long_percentage', 0)
            short_pct = data.get('short_percentage', 0)
            # Calculate how extreme the sentiment is (distance from neutral 50%)
            extremeness = abs(long_pct - 50)
            pairs_with_data.append((pair, long_pct, short_pct, extremeness))
        
        # Sort by extremeness
        pairs_with_data.sort(key=lambda x: x[3], reverse=True)
        
        # Show the top 3 most extreme sentiment pairs
        st.markdown("### Most Extreme Sentiment")
        
        for i in range(min(3, len(pairs_with_data))):
            pair, long_pct, short_pct, _ = pairs_with_data[i]
            
            # Determine direction and color
            if long_pct > 65:
                direction = "LONG-biased"
                description = f"{long_pct}% long positions - potential contrarian SHORT opportunity."
                color = "#F44336"  # Red (suggesting opposite trade)
            elif short_pct > 65:
                direction = "SHORT-biased"
                description = f"{short_pct}% short positions - potential contrarian LONG opportunity."
                color = "#4CAF50"  # Green (suggesting opposite trade)
            else:
                continue  # Skip if not extreme enough
            
            # Create card for extreme pair
            st.markdown(
                f"""
                <div style="background-color:#1E1E1E; border-radius:5px; padding:15px; margin-bottom:15px; border-left: 4px solid {color};">
                    <div style="display:flex; justify-content:space-between;">
                        <span style="font-weight:bold; font-size:16px; color:white;">{pair}</span>
                        <span style="color:{color}; font-weight:bold;">{direction}</span>
                    </div>
                    <p style="color:#DDDDDD; margin-top:8px; margin-bottom:0px; font-size:14px;">{description}</p>
                </div>
                """, 
                unsafe_allow_html=True
            )
        
        # Risk disclaimer
        st.markdown("### Disclaimer")
        st.markdown(
            """
            <div style="background-color:#1E1E1E; border-radius:5px; padding:15px; margin-bottom:15px; font-size:0.8rem; color:#AAAAAA;">
                Trader sentiment data should be used as one of multiple inputs in your trading decision process. 
                Extreme positioning can signal potential reversals but timing such reversals requires additional 
                technical and fundamental analysis. Past performance is not indicative of future results.
            </div>
            """, 
            unsafe_allow_html=True
        )
    
    else:
        st.info("No sentiment data available to analyze. Please fetch the data first.")

# Complete the file with navigation sidebar
with st.sidebar:
    st.markdown("---")
    st.subheader("Navigation")
    
    # Button to return to Market Monitor
    if st.button("💱 Back to Market Monitor", use_container_width=True):
        st.switch_page("streamlit_app.py")
    
    # Button to go to News Summarizer
    if st.button("📰 Go to News Summarizer", use_container_width=True):
        st.switch_page("pages/2_News_Summarizer.py")
    
    # Button to return to home
    if st.button("🏠 Return to Home", use_container_width=True):
        st.switch_page("Home.py")
    
    st.markdown("---")
    st.subheader("Refresh Controls")
    
    # Refresh button for sentiment data
    if st.button("🔄 Refresh Sentiment Data", use_container_width=True):
        update_all_sentiment_data(force=True)
        add_notification("Sentiment data refreshed", "success")
        st.rerun()
    
    # Show refresh time if available
    if 'fxbook_sentiment_last_fetch' in st.session_state and st.session_state.fxbook_sentiment_last_fetch:
        time_diff = datetime.now() - st.session_state.fxbook_sentiment_last_fetch
        if time_diff.seconds < 60:
            refresh_text = "just now"
        elif time_diff.seconds < 3600:
            refresh_text = f"{time_diff.seconds // 60} minutes ago"
        else:
            refresh_text = f"{time_diff.seconds // 3600} hours ago"
        st.sidebar.caption(f"Last refresh: {refresh_text}")
    
    # Add notifications section
    st.markdown("---")
    st.header("Notifications")
    
    if st.button("Clear All Notifications"):
        st.session_state.notifications = []
    
    if 'notifications' in st.session_state:
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