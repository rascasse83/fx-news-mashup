"""
Formatting utilities for displaying data in the UI.
Provides functions for formatting numbers, dates, times, and other data.
"""
from datetime import datetime, timedelta
from typing import Any, Union, Optional, Dict


def format_currency_rate(rate: float) -> str:
    """
    Format a currency rate with appropriate decimal places.
    
    Args:
        rate: Currency rate to format
        
    Returns:
        str: Formatted rate
    """
    if rate is None:
        return "N/A"
        
    if rate < 0.01:
        return f"{rate:.6f}"
    elif rate < 1:
        return f"{rate:.4f}"
    else:
        return f"{rate:.4f}"


def format_percentage(value: float, include_sign: bool = True) -> str:
    """
    Format a percentage value.
    
    Args:
        value: Percentage value to format
        include_sign: Whether to include a + sign for positive values
        
    Returns:
        str: Formatted percentage
    """
    if value is None:
        return "N/A"
        
    sign = "+" if include_sign and value > 0 else ""
    return f"{sign}{value:.2f}%"


def format_time_ago(timestamp: datetime) -> str:
    """
    Format a timestamp as a human-readable "time ago" string.
    
    Args:
        timestamp: Timestamp to format
        
    Returns:
        str: Human-readable time difference
    """
    if timestamp is None:
        return "unknown time"
        
    time_diff = datetime.now() - timestamp
    
    if time_diff.days > 0:
        return f"{time_diff.days}d ago"
    elif time_diff.seconds // 3600 > 0:
        return f"{time_diff.seconds // 3600}h ago"
    elif time_diff.seconds // 60 > 0:
        return f"{time_diff.seconds // 60}m ago"
    else:
        return "just now"


def format_news_date(timestamp: datetime) -> str:
    """
    Format a news timestamp into a readable date.
    
    Args:
        timestamp: Timestamp to format
        
    Returns:
        str: Formatted date
    """
    if timestamp is None:
        return "Unknown date"
    
    now = datetime.now()
    
    # If it's today
    if timestamp.date() == now.date():
        return f"Today, {timestamp.strftime('%H:%M')}"
    
    # If it's yesterday
    if timestamp.date() == (now - timedelta(days=1)).date():
        return f"Yesterday, {timestamp.strftime('%H:%M')}"
    
    # If it's this year
    if timestamp.year == now.year:
        return timestamp.strftime('%d %b, %H:%M')
    
    # Otherwise, include the year
    return timestamp.strftime('%d %b %Y, %H:%M')


def format_large_number(value: float, precision: int = 2) -> str:
    """
    Format large numbers with K, M, B suffixes.
    
    Args:
        value: Number to format
        precision: Number of decimal places
        
    Returns:
        str: Formatted number with appropriate suffix
    """
    if value is None:
        return "N/A"
        
    suffix = ""
    
    if value >= 1_000_000_000:
        value /= 1_000_000_000
        suffix = "B"
    elif value >= 1_000_000:
        value /= 1_000_000
        suffix = "M"
    elif value >= 1_000:
        value /= 1_000
        suffix = "K"
        
    format_str = f"{{:.{precision}f}}{suffix}"
    return format_str.format(value)


def get_sentiment_color(sentiment: str) -> str:
    """
    Get a color for a sentiment value.
    
    Args:
        sentiment: Sentiment value ('positive', 'negative', 'neutral')
        
    Returns:
        str: HTML color code
    """
    if sentiment == "positive":
        return "#4CAF50"  # Green
    elif sentiment == "negative":
        return "#F44336"  # Red
    else:
        return "#9E9E9E"  # Gray


def get_sentiment_bg_color(sentiment: str) -> str:
    """
    Get a background color for a sentiment value.
    
    Args:
        sentiment: Sentiment value ('positive', 'negative', 'neutral')
        
    Returns:
        str: HTML color code
    """
    if sentiment == "positive":
        return "#d4edda"  # Light green
    elif sentiment == "negative":
        return "#f8d7da"  # Light red
    else:
        return "#f8f9fa"  # Light gray


def get_direction_arrow(current: float, reference: float) -> str:
    """
    Get a direction arrow based on the comparison of two values.
    
    Args:
        current: Current value
        reference: Reference value
        
    Returns:
        str: Direction arrow (▲, ▼, or empty string)
    """
    if current is None or reference is None:
        return ""
        
    if current > reference:
        return "▲"
    elif current < reference:
        return "▼"
    else:
        return ""


def get_change_color(change: float) -> str:
    """
    Get a color based on the change value.
    
    Args:
        change: Change value
        
    Returns:
        str: HTML color code
    """
    if change is None:
        return "gray"
        
    if change > 0:
        return "green"
    elif change < 0:
        return "red"
    else:
        return "gray"


def format_volume(volume: float, currency: str = "") -> str:
    """
    Format a trading volume value.
    
    Args:
        volume: Volume value
        currency: Optional currency code to include
        
    Returns:
        str: Formatted volume
    """
    if volume is None:
        return "N/A"
        
    formatted = format_large_number(volume)
    
    if currency:
        return f"{formatted} {currency}"
    return formatted


def format_market_cap(market_cap: float) -> str:
    """
    Format a market capitalization value.
    
    Args:
        market_cap: Market cap value
        
    Returns:
        str: Formatted market cap
    """
    if market_cap is None:
        return "N/A"
        
    return f"${format_large_number(market_cap)}"


def format_crypto_price(price: float, show_decimals: bool = True) -> str:
    """
    Format a cryptocurrency price with appropriate precision.
    
    Args:
        price: Price value
        show_decimals: Whether to show decimal places for small values
        
    Returns:
        str: Formatted price
    """
    if price is None:
        return "N/A"
        
    if price < 0.00001 and show_decimals:
        return f"${price:.8f}"
    elif price < 0.001 and show_decimals:
        return f"${price:.6f}"
    elif price < 0.1 and show_decimals:
        return f"${price:.4f}"
    elif price < 1 and show_decimals:
        return f"${price:.4f}"
    elif price < 1000:
        return f"${price:.2f}"
    else:
        return f"${format_large_number(price, 2)}"
    
    
def prepare_map_data(variations, currency_to_country):
    """
    Prepare data for the geomap visualizations
    
    Args:
        variations: List of variation dictionaries
        currency_to_country: Dictionary mapping currencies to countries
        
    Returns:
        list: List of map data dictionaries
    """
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