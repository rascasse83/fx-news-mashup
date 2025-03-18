import streamlit as st
from datetime import datetime

from fx_news.ui.components.charts import display_volatility_index
from fx_news.ui.components.maps import display_indices_world_map, display_indices_visualization, display_crypto_market_visualization
from fx_news.ui.components.news import display_news_sidebar
from fx_news.ui.components.cards import display_currency_pair
from fx_news.services.rates_service import calculate_percentage_variation, prepare_map_data
from fx_news.data.currencies import currency_to_country

def create_layout(volatility_index, pair_volatility):
    """
    Create the main layout for the Market Monitor page.
    
    Args:
        volatility_index: Overall market volatility score
        pair_volatility: Dictionary of volatility scores by pair
    """
    # Main header area with logo and volatility index
    header_col1, header_col2 = st.columns([2, 1])

    with header_col1:
        # Dynamic title based on market type
        if st.session_state.market_type == 'FX':
            st.markdown("<h1 class='main-header'>💱 FX Market Monitor</h1>", unsafe_allow_html=True)
            
            # Display the text with a link on the word "sentiment"
            sentiment_url = "https://huggingface.co/yiyanghkust/finbert-tone"
            st.markdown(
                f"Real-time FX rates and news sentiment monitoring [.]({sentiment_url})",
                unsafe_allow_html=True
            )
        elif st.session_state.market_type == 'Indices':
            st.markdown("<h1 class='main-header'>💱 Indices Market Monitor</h1>", unsafe_allow_html=True)
            
            # Display the text with a link on the word "sentiment"
            sentiment_url = "https://huggingface.co/yiyanghkust/finbert-tone"
            st.markdown(
                f"Real-time FX rates and news sentiment monitoring [.]({sentiment_url})",
                unsafe_allow_html=True
            )
        else:
            st.markdown("<h1 class='main-header'>₿ Crypto Market Monitor</h1>", unsafe_allow_html=True)
            
            # Updated subtitle for crypto mode
            sentiment_url = "https://huggingface.co/yiyanghkust/finbert-tone"
            st.markdown(
                f"Real-time cryptocurrency prices and market sentiment [.]({sentiment_url})",
                unsafe_allow_html=True
            )

    with header_col2:
        # Create a compact volatility gauge
        fig = create_volatility_gauge(volatility_index)
        
        # Display the gauge
        st.plotly_chart(fig, use_container_width=True)
        
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

    # Create the expandable volatility section
    with st.expander("View Detailed Market Volatility Information", expanded=False):
        display_volatility_index(volatility_index, pair_volatility)

    # Add a separator
    st.markdown("<hr style='margin-top:0.5rem; margin-bottom:1rem;'>", unsafe_allow_html=True)

    # Add a collapsible section for trader sentiment overview
    with st.expander("View Trader Sentiment Overview", expanded=False):
        display_trader_sentiment_overview()

    # Add a separator
    st.markdown("<hr style='margin-top:0.5rem; margin-bottom:1rem;'>", unsafe_allow_html=True)

    # Create two columns for the main content area
    col4, col5 = st.columns([3, 1])  # Adjust column widths as needed

    with col4:
        # Market visualizations
        with st.container(key=f"market_container_{st.session_state.ui_refresh_key}"):
            # Calculate percentage variations for maps
            variations = calculate_percentage_variation(st.session_state.subscriptions)
            
            # Prepare data for the geomap
            map_data = prepare_map_data(variations, currency_to_country)
            
            # Display market-specific visualizations
            if map_data:
                if st.session_state.market_type == 'FX':
                    display_fx_maps(map_data)
                elif st.session_state.market_type == 'Crypto':
                    display_crypto_market_visualization()
                elif st.session_state.market_type == 'Indices':
                    display_indices_tabs()
        
        # Currency Rates section
        st.header("Currency Rates")
        
        # Add collapse/expand all buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Collapse All Cards"):
                st.session_state.collapse_all_cards = True
                st.rerun()
        with col2:
            if st.button("Expand All Cards"):
                st.session_state.collapse_all_cards = False
                st.rerun()
        
        # Create a card for each subscription
        for i, sub in enumerate(st.session_state.subscriptions):
            display_currency_pair(sub)
            
            # Add some space between cards
            st.markdown("<div style='margin-bottom:1rem;'></div>", unsafe_allow_html=True)

    # News feed column
    with col5:
        display_news_sidebar()

def create_volatility_gauge(volatility_index):
    """Create a compact volatility gauge for the header"""
    import plotly.graph_objects as go
    
    # Create a compact volatility gauge
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=volatility_index,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Market Volatility", 'font': {'color': 'white', 'size': 14}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white", 'visible': False},
            'bar': {'color': "#4D9BF5"},
            'bgcolor': "gray",
            'borderwidth': 1,
            'bordercolor': "white",
            'steps': [
                {'range': [0, 25], 'color': '#4CAF50'},  # Low volatility - green
                {'range': [25, 50], 'color': '#FFC107'},  # Medium volatility - amber
                {'range': [50, 75], 'color': '#FF9800'},  # Medium-high volatility - orange
                {'range': [75, 100], 'color': '#F44336'}  # High volatility - red
            ],
        }
    ))
    
    # Make the gauge compact
    fig.update_layout(
        height=120,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="#121212",
        font=dict(color="white", size=10)
    )
    
    return fig

def display_trader_sentiment_overview():
    """Display the trader sentiment overview section"""
    # Import here to avoid circular imports
    from fx_news.services.sentiment_service import update_all_sentiment_data, load_sentiment_data
    
    sent_col1, sent_col2, sent_col3 = st.columns([1, 1, 1])
    
    # Check if auto-refresh is enabled before loading sentiment data
    if st.session_state.auto_refresh:
        if 'fxbook_sentiment_data' not in st.session_state or not st.session_state.fxbook_sentiment_data:
            with st.spinner("Loading sentiment data..."):
                update_all_sentiment_data()
        sentiment_data = st.session_state.get('fxbook_sentiment_data', {})
    else:
        # When auto-refresh is disabled, provide an empty dictionary instead of loading data
        sentiment_data = {}
        
    # This will now work even if sentiment_data is an empty dictionary
    pairs_data = {} if sentiment_data is None else sentiment_data.get('data', {})
    
    with sent_col1:
        st.markdown("#### Top Bullish Pairs")
        
        # Find most bullish pairs (highest long percentage)
        bullish_pairs = []
        for pair, data in pairs_data.items():
            long_pct = data.get('long_percentage', 0)
            if long_pct:
                bullish_pairs.append((pair, long_pct))
        
        # Sort by long percentage (highest first)
        bullish_pairs.sort(key=lambda x: x[1], reverse=True)
        
        # Display top 3 bullish pairs
        for pair, long_pct in bullish_pairs[:3]:
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; margin-bottom:5px; 
                        background-color:#1E1E1E; padding:8px; border-radius:5px;">
                <span style="font-weight:bold; color:white;">{pair}</span>
                <span style="color:#4CAF50; font-weight:bold;">{long_pct}% Long</span>
            </div>
            """, unsafe_allow_html=True)
    
    with sent_col2:
        st.markdown("#### Top Bearish Pairs")
        
        # Find most bearish pairs (highest short percentage)
        bearish_pairs = []
        for pair, data in pairs_data.items():
            short_pct = data.get('short_percentage', 0)
            if short_pct:
                bearish_pairs.append((pair, short_pct))
        
        # Sort by short percentage (highest first)
        bearish_pairs.sort(key=lambda x: x[1], reverse=True)
        
        # Display top 3 bearish pairs
        for pair, short_pct in bearish_pairs[:3]:
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; margin-bottom:5px; 
                        background-color:#1E1E1E; padding:8px; border-radius:5px;">
                <span style="font-weight:bold; color:white;">{pair}</span>
                <span style="color:#F44336; font-weight:bold;">{short_pct}% Short</span>
            </div>
            """, unsafe_allow_html=True)
    
    with sent_col3:
        # Create a quick sentiment gauge for the most active pair (if available)
        most_active_pair = None
        highest_positions = 0
        
        for pair, data in pairs_data.items():
            positions = data.get('detailed', {}).get('short', {}).get('positions', '0')
            try:
                positions_count = int(positions.split()[0].replace(',', ''))
                if positions_count > highest_positions:
                    highest_positions = positions_count
                    most_active_pair = pair
            except:
                continue
        
        if most_active_pair:
            st.markdown(f"#### Most Active: {most_active_pair}")
            
            pair_data = pairs_data[most_active_pair]
            long_pct = pair_data.get('long_percentage', 50)
            
            # Create sentiment gauge
            create_sentiment_gauge(long_pct, most_active_pair)
            
            # Add a note with number of positions
            positions = pair_data.get('detailed', {}).get('short', {}).get('positions', 'Unknown')
            st.markdown(f"<div style='text-align:center;'>Active positions: {positions}</div>", unsafe_allow_html=True)
        else:
            st.info("No activity data available")
    
    # Add a link to the full sentiment dashboard
    st.markdown("""
    <div style="text-align:center; margin-top:15px;">
        <a href="./Trader_Sentiment" target="_self" style="background-color:#4D9BF5; color:white; padding:8px 16px; border-radius:5px; text-decoration:none; font-weight:bold;">
            View Full Sentiment Dashboard
        </a>
    </div>
    """, unsafe_allow_html=True)

def create_sentiment_gauge(long_pct, pair_name):
    """Create a sentiment gauge for a given pair"""
    import plotly.graph_objects as go
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=long_pct,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Long Sentiment", 'font': {'color': 'white', 'size': 14}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
            'bar': {'color': "#4CAF50" if long_pct > 50 else "#F44336"},
            'bgcolor': "gray",
            'borderwidth': 1,
            'bordercolor': "white",
            'steps': [
                {'range': [0, 100], 'color': "#1E1E1E"}
            ],
        },
        number={'suffix': "%", 'font': {'color': 'white'}}
    ))
    
    # Make the gauge compact
    fig.update_layout(
        height=150,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="#121212",
        font=dict(color="white", size=12)
    )
    
    # Display the gauge
    st.plotly_chart(fig, use_container_width=True)

def display_fx_maps(map_data):
    """Display FX market maps for different regions"""
    import plotly.graph_objects as go
    
    # Create a layout with three columns
    col1, col2, col3 = st.columns(3)

    # Map for the US continent
    with col1:
        us_locations = ['United States', 'Canada', 'Mexico']
        fig_us = go.Figure(data=go.Choropleth(
            locations=[data["location"] for data in map_data if data["location"] in us_locations],
            z=[data["variation"] for data in map_data if data["location"] in us_locations],
            locationmode='country names',
            colorscale='RdBu',
            showscale=False,  # Hide color scale for US map
            text=[f'{data["variation"]:.2f}%' for data in map_data if data["location"] in us_locations],
            hoverinfo='text'
        ))

        fig_us.update_layout(
            geo=dict(
                showframe=False,
                showcoastlines=False,
                projection_type='equirectangular',
                center=dict(lat=37.0902, lon=-95.7129),
                scope='north america'
            ),
            height=300,
            margin=dict(l=0, r=0, t=0, b=0)
        )

        st.plotly_chart(fig_us, use_container_width=True)

    # Map for Europe
    with col2:
        # Create a list of European countries that includes both Eurozone and UK
        from fx_news.data.currencies import currency_to_country
        euro_countries = currency_to_country['EUR']
        if not isinstance(euro_countries, list):
            euro_countries = [euro_countries]
        
        # Explicitly add the UK to our Europe map
        uk_location = currency_to_country.get('GBP', 'United Kingdom')
        europe_locations = euro_countries + [uk_location]
        
        # Filter the map_data for European countries including UK
        euro_map_data = [data for data in map_data if data["location"] in europe_locations]
        
        if euro_map_data:
            # When setting up the Europe map, make sure to adjust the scope
            fig_europe = go.Figure(data=go.Choropleth(
                locations=[data["location"] for data in euro_map_data],
                z=[data["variation"] for data in euro_map_data],
                locationmode='country names',
                colorscale='RdBu',
                showscale=False,
                text=[f'{data["location"]}: {data["variation"]:.2f}%' for data in euro_map_data],
                hoverinfo='text'
            ))

            # Adjust Europe map settings to ensure UK is visible
            fig_europe.update_layout(
                geo=dict(
                    showframe=False,
                    showcoastlines=False,
                    projection_type='equirectangular',
                    center=dict(lat=50.0, lon=10.0),  # Adjusted to include UK better
                    scope='europe',
                    lonaxis=dict(range=[-15, 30]),  # Ensure UK is in longitude range
                    lataxis=dict(range=[35, 65])     # Adjusted latitude range
                ),
                height=300,
                margin=dict(l=0, r=0, t=0, b=0)
            )

            st.plotly_chart(fig_europe, use_container_width=True)
        else:
            st.info("No variation data available for European countries")

    # Map for Asia - SHOWING SCALE
    with col3:
        asia_countries = ['China', 'Japan', 'India', 'Singapore', 'Hong Kong']
        
        # Filter the map_data for Asian countries
        asia_map_data = [data for data in map_data if data["location"] in asia_countries]
        
        if asia_map_data:
            fig_asia = go.Figure(data=go.Choropleth(
                locations=[data["location"] for data in asia_map_data],
                z=[data["variation"] for data in asia_map_data],
                locationmode='country names',
                colorscale='RdBu',
                showscale=True,  # Show color scale ONLY for Asia map
                colorbar_title="% Variation",
                colorbar=dict(
                    title="% Variation",
                    thickness=15,
                    len=0.7,
                    x=0.9,
                ),
                text=[f'{data["variation"]:.2f}%' for data in asia_map_data],
                hoverinfo='text'
            ))

            fig_asia.update_layout(
                geo=dict(
                    showframe=False,
                    showcoastlines=False,
                    projection_type='equirectangular',
                    center=dict(lat=35.8617, lon=104.1954),
                    scope='asia'
                ),
                height=300,
                margin=dict(l=0, r=0, t=0, b=0)
            )

            st.plotly_chart(fig_asia, use_container_width=True)
        else:
            st.info("No variation data available for Asian countries")

def display_indices_tabs():
    """Display tabs for indices visualizations"""
    tab1, tab2 = st.tabs(["Performance Overview", "World Map"])
    
    with tab1:
        display_indices_visualization()
    
    with tab2:
        display_indices_world_map()