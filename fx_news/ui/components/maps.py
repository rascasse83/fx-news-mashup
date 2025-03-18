"""
Map visualization components for the FX Pulsar application.
Contains functions for creating geospatial visualizations.
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional

def display_fx_maps(map_data: List[Dict[str, Any]]):
    """
    Display FX market maps for different regions.
    
    Args:
        map_data: List of data dictionaries with location and variation
    """
    if not map_data:
        st.info("No market data available for the map visualization.")
        return
    
    # Create a layout with three columns
    col1, col2, col3 = st.columns(3)

    # Map for North America
    with col1:
        us_locations = ['United States', 'Canada', 'Mexico']
        display_region_map(
            map_data=map_data,
            filter_locations=us_locations,
            scope='north america',
            center=dict(lat=37.0902, lon=-95.7129),
            show_scale=False,
            height=300
        )

    # Map for Europe
    with col2:
        # Create a list of European countries that includes both Eurozone and UK
        euro_countries = [
            'Austria', 'Belgium', 'Cyprus', 'Estonia', 'Finland', 'France', 'Germany',
            'Greece', 'Ireland', 'Italy', 'Latvia', 'Lithuania', 'Luxembourg', 'Malta',
            'Netherlands', 'Portugal', 'Slovakia', 'Slovenia', 'Spain', 'United Kingdom'
        ]
        
        display_region_map(
            map_data=map_data,
            filter_locations=euro_countries,
            scope='europe',
            center=dict(lat=50.0, lon=10.0),
            lon_range=[-15, 30],
            lat_range=[35, 65],
            show_scale=False,
            height=300
        )

    # Map for Asia (showing scale)
    with col3:
        asia_countries = ['China', 'Japan', 'India', 'Singapore', 'Hong Kong', 'Australia', 'New Zealand']
        
        display_region_map(
            map_data=map_data,
            filter_locations=asia_countries,
            scope='asia',
            center=dict(lat=35.8617, lon=104.1954),
            show_scale=True,
            height=300
        )

def display_region_map(map_data: List[Dict[str, Any]], filter_locations: List[str], 
                      scope: str, center: Dict[str, float], 
                      lon_range: Optional[List[float]] = None, 
                      lat_range: Optional[List[float]] = None,
                      show_scale: bool = False, height: int = 300):
    """
    Display a map for a specific region.
    
    Args:
        map_data: List of data dictionaries with location and variation
        filter_locations: List of location names to include
        scope: Map scope (e.g., 'world', 'usa', 'europe', 'asia')
        center: Dictionary with lat and lon for map center
        lon_range: Optional list with min and max longitude
        lat_range: Optional list with min and max latitude
        show_scale: Whether to show the color scale
        height: Height of the map in pixels
    """
    # Filter the map_data for the specified locations
    filtered_data = [data for data in map_data if data["location"] in filter_locations]
    
    if not filtered_data:
        st.info(f"No variation data available for {scope}")
        return
    
    # Create the choropleth map
    fig = go.Figure(data=go.Choropleth(
        locations=[data["location"] for data in filtered_data],
        z=[data["variation"] for data in filtered_data],
        locationmode='country names',
        colorscale='RdBu',
        showscale=show_scale,
        colorbar_title="% Variation" if show_scale else None,
        colorbar=dict(
            title="% Variation",
            thickness=15,
            len=0.7,
            x=0.9,
        ) if show_scale else None,
        text=[f'{data["location"]}: {data["variation"]:.2f}%' for data in filtered_data],
        hoverinfo='text'
    ))

    # Set up the geo layout
    geo_dict = dict(
        showframe=False,
        showcoastlines=False,
        projection_type='equirectangular',
        center=center,
        scope=scope
    )
    
    # Add longitude and latitude ranges if provided
    if lon_range:
        geo_dict['lonaxis'] = dict(range=lon_range)
    if lat_range:
        geo_dict['lataxis'] = dict(range=lat_range)
    
    # Update the layout
    fig.update_layout(
        geo=geo_dict,
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="#121212",
        geo_bgcolor="#121212",
    )

    st.plotly_chart(fig, use_container_width=True)

def display_indices_world_map():
    """Create a world map visualization showing performance of major indices by region"""
    
    # Map indices to their countries/regions
    from fx_news.data.currencies import indices_regions
    
    # Create data for the map
    map_data = []
    
    # Get indices data from subscriptions
    for sub in st.session_state.subscriptions:
        if sub["current_rate"] is not None and sub["base"] in indices_regions:
            # Calculate percent change
            percent_change = 0
            if sub.get("previous_close") is not None:
                percent_change = ((sub["current_rate"] - sub["previous_close"]) / sub["previous_close"]) * 100
            elif sub.get("last_rate") is not None:
                percent_change = ((sub["current_rate"] - sub["last_rate"]) / sub["last_rate"]) * 100
            
            # Get country information
            country = indices_regions[sub["base"]]['country']
            from fx_news.data.currencies import indices
            name = indices.get(sub["base"], sub["base"])
            
            map_data.append({
                "country": country,
                "index": name,
                "symbol": sub["base"],
                "change": percent_change,
                "current_value": sub["current_rate"]
            })
    
    if not map_data:
        st.info("No indices data available for map visualization.")
        return
    
    # Create the choropleth map
    fig = go.Figure(data=go.Choropleth(
        locations=[d["country"] for d in map_data],
        locationmode='country names',
        z=[d["change"] for d in map_data],
        text=[f"{d['index']}: {d['change']:.2f}%<br>Value: {d['current_value']:,.2f}" for d in map_data],
        colorscale='RdBu_r',  # Red for negative, Blue for positive
        zmin=-3,  # Set lower bound for color scale
        zmax=3,   # Set upper bound for color scale
        marker_line_color='darkgray',
        marker_line_width=0.5,
        colorbar_title='Change %',
        hoverinfo='text+location'
    ))
    
    # Update layout
    fig.update_layout(
        title_text='Global Market Performance by Country',
        geo=dict(
            showframe=False,
            showcoastlines=True,
            projection_type='natural earth',
            bgcolor='rgba(18,18,18,0)',  # Transparent background
            lakecolor='#121212',  # Dark lakes to match background
            landcolor='#2d2d2d',  # Dark land color
            coastlinecolor='#555555',  # Medium gray coastlines
        ),
        height=450,
        margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor="#121212",
        font=dict(color="white")
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Create regional performance mini cards below the map
    st.markdown("### Regional Market Performance")
    
    # Group data by region
    regions = {}
    for sub in st.session_state.subscriptions:
        if sub["current_rate"] is not None and sub["base"] in indices_regions:
            region = indices_regions[sub["base"]]['region']
            
            if region not in regions:
                regions[region] = []
            
            # Calculate percent change
            percent_change = 0
            if sub.get("previous_close") is not None:
                percent_change = ((sub["current_rate"] - sub["previous_close"]) / sub["previous_close"]) * 100
            elif sub.get("last_rate") is not None:
                percent_change = ((sub["current_rate"] - sub["last_rate"]) / sub["last_rate"]) * 100
            
            from fx_news.data.currencies import indices
            index_name = indices.get(sub["base"], sub["base"])
            
            regions[region].append({
                "index": index_name,
                "change": percent_change,
                "current_value": sub["current_rate"]
            })
    
    # Calculate average performance by region
    region_performance = {}
    for region, indices_list in regions.items():
        if indices_list:
            avg_change = sum(idx["change"] for idx in indices_list) / len(indices_list)
            region_performance[region] = {
                "avg_change": avg_change,
                "indices": indices_list
            }
    
    # Create regional performance cards
    cols = st.columns(len(region_performance) or 1)
    
    for i, (region, data) in enumerate(region_performance.items()):
        with cols[i]:
            # Determine color based on average change
            if data["avg_change"] > 0:
                color = "#4CAF50"  # Green
                icon = "📈"
            else:
                color = "#F44336"  # Red
                icon = "📉"
            
            # Create the region card
            st.markdown(f"""
            <div style="border-left: 4px solid {color}; background-color:#1E1E1E; padding:15px; border-radius:5px; margin-bottom:10px;">
                <div style="font-size:1.2rem; font-weight:bold; margin-bottom:10px;">{icon} {region}</div>
                <div style="font-size:1.4rem; color:{color}; font-weight:bold; margin-bottom:10px;">
                    {'+' if data["avg_change"] > 0 else ''}{data["avg_change"]:.2f}%
                </div>
                <div style="font-size:0.9rem; color:#AAAAAA;">Average of {len(data["indices"])} indices</div>
            </div>
            """, unsafe_allow_html=True)
            
            # List the indices in this region
            for idx in sorted(data["indices"], key=lambda x: x["change"], reverse=True):
                change_color = "#4CAF50" if idx["change"] > 0 else "#F44336"
                
                st.markdown(f"""
                <div style="display:flex; justify-content:space-between; margin-bottom:5px; padding:8px; background-color:#121212; border-radius:3px;">
                    <span style="font-size:0.9rem;">{idx["index"]}</span>
                    <span style="font-size:0.9rem; color:{change_color}; font-weight:bold;">
                        {'+' if idx["change"] > 0 else ''}{idx["change"]:.2f}%
                    </span>
                </div>
                """, unsafe_allow_html=True)




def display_indices_visualization():
    """Display an indices market visualization with performance bars"""
    
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
            from fx_news.data.currencies import indices
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
    
    # Create a bar chart showing change percentages
    fig = go.Figure()
    
    # Add bars
    fig.add_trace(go.Bar(
        x=[d["index"] for d in indices_data],
        y=[d["change"] for d in indices_data],
        text=[f"{d['change']:.2f}%" for d in indices_data],
        textposition='auto',
        marker_color=[
            '#4CAF50' if d["change"] > 0 else '#F44336' for d in indices_data
        ],
        hovertemplate='<b>%{x}</b><br>Change: %{y:.2f}%<br>Value: %{customdata}<extra></extra>',
        customdata=[f"{d['price']:,.2f} {d['quote']}" for d in indices_data]
    ))
    
    # Update layout
    fig.update_layout(
        title="Major Indices Performance",
        height=350,
        margin=dict(l=10, r=10, t=50, b=10),
        paper_bgcolor="#121212",
        plot_bgcolor="#121212",
        font=dict(color="white"),
        xaxis=dict(
            title="",
            tickangle=-45,
            tickfont=dict(size=12),
            gridcolor="#333333"
        ),
        yaxis=dict(
            title="Change (%)",
            ticksuffix="%",
            gridcolor="#333333"
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)

def display_crypto_market_visualization():
    """Display a cryptocurrency market visualization using a treemap"""
    
    # Market cap estimates or scaling factor for common cryptocurrencies
    # These are approximate values that would need to be updated regularly in a real app
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
                "change": percent_change
            })
    
    if not crypto_data:
        st.info("No crypto data available yet. Add some cryptocurrency pairs to see the visualization.")
        return
    
    # Create a treemap
    fig = go.Figure(go.Treemap(
        labels=[f"{d['coin']}/{d['quote']}: ${d['price']:.2f}" for d in crypto_data],
        parents=["" for _ in crypto_data],
        values=[d["value"] for d in crypto_data],  # Using market cap estimates
        textinfo="label",
        hovertemplate='<b>%{label}</b><br>Change: %{customdata:.2f}%<extra></extra>',
        customdata=[[d["change"]] for d in crypto_data],
        marker=dict(
            colors=[
                '#4CAF50' if d["change"] > 1 else 
                '#8BC34A' if d["change"] > 0 else 
                '#F44336' if d["change"] < -1 else 
                '#FFCDD2' 
                for d in crypto_data
            ],
            colorscale=None,  # Use the colors defined above
            showscale=False
        ),
    ))
    
    # Update layout
    fig.update_layout(
        height=300,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="#121212",
        plot_bgcolor="#121212",
        font=dict(color="white")
    )
    
    st.plotly_chart(fig, use_container_width=True)