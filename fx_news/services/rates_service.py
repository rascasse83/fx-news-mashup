import streamlit as st
import numpy as np
from datetime import datetime, timedelta
import logging
import time
import random

from streamlit_autorefresh import st_autorefresh
from fx_news.apis.rates_fetch import fetch_currency_rates, update_rates_with_variation, get_mock_currency_rates
from fx_news.scrapers.rates_scraper import scrape_yahoo_finance_rates

from fx_news.utils.notifications import add_notification
from fx_news.services.sentiment_service import update_all_sentiment_data
from fx_news.services.events_service import fetch_all_economic_events

logger = logging.getLogger(__name__)

def setup_auto_refresh():
    """Setup auto-refresh mechanism using streamlit_autorefresh package"""
    # Only enable auto-refresh if the toggle is on in session state
    if 'auto_refresh' in st.session_state and st.session_state.auto_refresh:
        # Set up the 15-second refresh cycle for rates
        count = st_autorefresh(interval=30000, key="rates_refresher")
        
        # Process refreshes
        current_time = datetime.now()
        
        # Handle rates refresh (every refresh cycle - 15 seconds)
        st.session_state.last_auto_refresh_time = current_time
        update_rates()
        
        # Check if it's time to refresh news (every 20th cycle)
        if count % 20 == 0:
            # Instead of refreshing right away, just schedule the next refresh
            current_time = datetime.now()
            st.session_state.next_news_refresh_time = current_time  # Set to current time to trigger refresh on next run
            add_notification("Scheduled news refresh", "info")
        else:
            # Mark that we're not auto-refreshing news this cycle
            st.session_state.news_auto_refreshing = False
            
        # Handle economic calendar refresh (every 240th refresh cycle - 1 hour)
        if count % 240 == 0:
            st.session_state.last_calendar_auto_refresh_time = current_time
            fetch_all_economic_events(force=True)
            
        # Handle sentiment data refresh (every 60th refresh cycle - 30 minutes)
        if count % 60 == 0:
            st.session_state.last_sentiment_auto_refresh_time = current_time
            update_all_sentiment_data(force=True)

def update_rates(use_mock_data=False):
    """
    Update currency rates for all subscriptions
    
    Args:
        use_mock_data (bool): Whether to use mock data for testing
        
    Returns:
        bool: Whether the update was successful
    """
    try:
        updated_any = False
        bases_to_fetch = set(sub["base"].lower() for sub in st.session_state.subscriptions)
        
        results = {}
        
        if use_mock_data:
            # Use mock data for testing
            mock_data = get_mock_currency_rates()
            for base in bases_to_fetch:
                if base in mock_data:
                    results[base] = mock_data[base]
                    updated_any = True
            add_notification("Using mock currency data for testing", "info")
        else:
            # Use the optimized scraper method
            currency_pairs = [(sub["base"], sub["quote"]) for sub in st.session_state.subscriptions]
            
            # Determine if we should also fetch YTD data (once per day is enough)
            fetch_ytd = False
            if 'last_ytd_fetch' not in st.session_state or st.session_state.last_ytd_fetch is None:
                fetch_ytd = True
            elif (datetime.now() - st.session_state.last_ytd_fetch).days >= 1:
                fetch_ytd = True
                
            results = scrape_yahoo_finance_rates(currency_pairs, fetch_ytd=fetch_ytd, debug_log=st.session_state.debug_log)
            
            # Update last YTD fetch time if we fetched YTD data
            if fetch_ytd:
                st.session_state.last_ytd_fetch = datetime.now()
                add_notification("Updated YTD data for all currency pairs", "success")
                
            # Check if any rates were fetched
            if results:
                updated_any = True

        if updated_any:
            # Update subscriptions with new rates
            for sub in st.session_state.subscriptions:
                base = sub["base"].lower()
                quote = sub["quote"].lower()

                # Create normalized results keys dictionary for case-insensitive comparison
                results_lower = {}
                for k, v in results.items():
                    results_lower[k.lower()] = {}
                    for kk, vv in v.items():
                        results_lower[k.lower()][kk.lower()] = vv

                if base in results_lower and quote in results_lower[base]:
                    rate_data = results_lower[base][quote]
                    
                    # Handle both new dictionary format and old scalar format
                    if isinstance(rate_data, dict) and "price" in rate_data:
                        # New format with price and previous_close
                        sub["previous_close"] = rate_data.get("previous_close")
                        sub["current_rate"] = rate_data["price"]
                    else:
                        # Old format with just a rate value
                        sub["last_rate"] = sub["current_rate"]
                        sub["current_rate"] = rate_data

                    # Optional: Add small random variations for testing UI updates
                    if 'show_debug' in st.session_state and st.session_state.show_debug and 'add_variations' in st.session_state and st.session_state.add_variations:
                        sub["current_rate"] = update_rates_with_variation(sub["current_rate"])

                    # Initialize rate history if needed
                    pair_key = f"{base}_{quote}"
                    if pair_key not in st.session_state.rate_history:
                        st.session_state.rate_history[pair_key] = []

                    # Add to history (keep only last 100 points)
                    st.session_state.rate_history[pair_key].append({
                        "timestamp": datetime.now(),
                        "rate": sub["current_rate"]
                    })
                    if len(st.session_state.rate_history[pair_key]) > 100:
                        st.session_state.rate_history[pair_key] = st.session_state.rate_history[pair_key][-100:]

                    # Check for threshold breach using previous_close if available
                    reference_price = None
                    if sub.get("previous_close") is not None:
                        reference_price = sub["previous_close"]
                    elif sub.get("last_rate") is not None:
                        reference_price = sub["last_rate"]
                        
                    if reference_price is not None and sub["current_rate"] is not None:
                        percent_change = abs((sub["current_rate"] - reference_price) / reference_price * 100)
                        if percent_change > sub["threshold"]:
                            direction = "increased" if sub["current_rate"] > reference_price else "decreased"
                            add_notification(
                                f"{sub['base']}/{sub['quote']} {direction} by {percent_change:.2f}% (threshold: {sub['threshold']}%)",
                                "price"
                            )

            st.session_state.last_refresh = datetime.now()
            add_notification("Currency rates updated successfully", "success")
            return True
        else:
            add_notification("Failed to update any currency rates", "error")
            return False

    except Exception as e:
        add_notification(f"Error updating rates: {str(e)}", "error")
        return False

def calculate_percentage_variation(subscriptions):
    """
    Calculate percentage variation for each currency pair
    
    Args:
        subscriptions: List of subscription dictionaries
        
    Returns:
        list: List of variation dictionaries
    """
    variations = []
    for sub in subscriptions:
        # Check if current_rate exists
        if sub["current_rate"] is not None:
            # Determine the previous rate to use for comparison
            previous_rate = None
            if sub.get("previous_close") is not None:
                previous_rate = sub["previous_close"]
            elif sub.get("last_rate") is not None:
                previous_rate = sub["last_rate"]
                
            # Only calculate variation if we have a valid previous rate
            if previous_rate is not None:
                percent_change = ((sub["current_rate"] - previous_rate) / previous_rate) * 100
                variations.append({
                    "currency_pair": f"{sub['base']}/{sub['quote']}",
                    "base": sub["base"],
                    "quote": sub["quote"],
                    "variation": percent_change
                })
    return variations

def calculate_market_volatility(subscriptions):
    """
    Calculate a market volatility index based on the short-term 
    movement of all currency pairs.
    
    Args:
        subscriptions: List of subscription dictionaries containing currency data
    
    Returns:
        volatility_index: Overall market volatility score (0-100)
        pair_volatility: Dictionary of volatility scores by pair
    """
    if not subscriptions:
        return 0, {}
    
    pair_volatility = {}
    volatility_scores = []
    
    for sub in subscriptions:
        # Skip pairs with insufficient data
        if sub.get("current_rate") is None:
            continue
            
        # Get reference price for calculating volatility
        reference_rate = None
        if sub.get("previous_close") is not None:
            reference_rate = sub["previous_close"]
        elif sub.get("last_rate") is not None:
            reference_rate = sub["last_rate"]
            
        if reference_rate is None:
            continue
            
        # Calculate percent change as basic volatility measure
        percent_change = abs((sub["current_rate"] - reference_rate) / reference_rate * 100)
        
        # Get historical data if available
        pair_key = f"{sub['base'].lower()}_{sub['quote'].lower()}"
        historical_volatility = 0
        
        if pair_key in st.session_state.rate_history and len(st.session_state.rate_history[pair_key]) > 3:
            # Get recent history
            history = st.session_state.rate_history[pair_key][-20:]  # Last 20 data points
            rates = [point["rate"] for point in history]
            
            # Calculate standard deviation as a volatility measure if we have enough data
            if len(rates) >= 3:
                std_dev = np.std(rates)
                mean_rate = np.mean(rates)
                if mean_rate > 0:
                    # Coefficient of variation (normalized standard deviation)
                    historical_volatility = (std_dev / mean_rate) * 100
        
        # Combine recent change and historical volatility
        # Weight recent change more heavily (70%) than historical volatility (30%)
        volatility_score = (0.7 * percent_change) + (0.3 * historical_volatility)
        
        # Store pair-specific volatility
        pair_volatility[f"{sub['base']}/{sub['quote']}"] = volatility_score
        volatility_scores.append(volatility_score)
    
    # Calculate overall market volatility index (scale 0-100)
    # We use the 80th percentile to reduce impact of outliers
    if volatility_scores:
        # Get the 80th percentile of all volatility scores
        high_volatility = np.percentile(volatility_scores, 80) if len(volatility_scores) >= 5 else max(volatility_scores)
        
        # Scale to 0-100 range (assuming 5% change is very volatile -> 100)
        # This scaling factor can be adjusted based on normal market conditions
        volatility_index = min(100, (high_volatility / 5) * 100)
    else:
        volatility_index = 0
    
    return volatility_index, pair_volatility


# Prepare data for the geomap
def prepare_map_data(variations, currency_to_country):
    map_data = []
    
    # Create a dictionary to store aggregated variations by country
    country_variations = {}
    
    for variation in variations:
        # Process base currency locations
        base_locations = currency_to_country.get(variation["base"], [])
        # Ensure we have a list of locations even if it's a single country
        if not isinstance(base_locations, list):
            base_locations = [base_locations]
            
        # Add locations for base currency
        for location in base_locations:
            if location not in country_variations:
                country_variations[location] = []
            country_variations[location].append(variation["variation"])
        
        # Also process quote currency locations (with inverted variation)
        quote_locations = currency_to_country.get(variation["quote"], [])
        # Ensure we have a list of locations even if it's a single country
        if not isinstance(quote_locations, list):
            quote_locations = [quote_locations]
            
        # Add locations for quote currency (with inverted variation)
        for location in quote_locations:
            if location not in country_variations:
                country_variations[location] = []
            # Invert the variation for quote currency
            country_variations[location].append(-variation["variation"])
    
    # Create the final map data by averaging the variations for each country
    for location, variations_list in country_variations.items():
        if variations_list:
            avg_variation = sum(variations_list) / len(variations_list)
            map_data.append({
                "location": location,
                "variation": avg_variation
            })
    
    return map_data