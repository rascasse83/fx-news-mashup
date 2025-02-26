# scrapers/currency_rates.py
import requests
import time
from datetime import datetime
import random

def fetch_currency_rates(base, api_key=None, debug_log=None):
    """
    Fetch currency exchange rates for a base currency
    
    Args:
        base: Base currency code (e.g., 'EUR')
        api_key: Optional API key for services that require authentication
        debug_log: Optional list to append debug information to
        
    Returns:
        Dictionary with currency rates or None if failed
    """
    if debug_log is None:
        debug_log = []
        
    debug_log.append(f"Fetching rates for {base}...")
    
    try:
        # Try the GitHub Pages API first
        url = f"https://currency-api.pages.dev/v1/currencies/{base.lower()}.json"
        debug_log.append(f"Trying primary API: {url}")
        
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            
        response = requests.get(url, timeout=5, headers=headers)
        
        if response.status_code != 200:
            debug_log.append(f"Primary API failed with status {response.status_code}, trying fallback...")
            # Fall back to the CDN URL
            url = f"https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/{base.lower()}.json"
            debug_log.append(f"Trying fallback API: {url}")
            
            response = requests.get(url, timeout=5, headers=headers)
            
            if response.status_code != 200:
                debug_log.append(f"Fallback API also failed with status {response.status_code}")
                return None

        data = response.json()
        
        # Verify data structure
        if base.lower() not in data:
            debug_log.append(f"API response missing expected base currency key: {base.lower()}")
            return None
            
        # Add a sample of the rates to the debug log
        sample_rates = list(data[base.lower()].items())[:3]
        debug_log.append(f"Sample rates for {base}: {sample_rates}")
        
        return data
    except Exception as e:
        debug_log.append(f"Error fetching rates for {base}: {str(e)}")
        return None

def update_rates_with_variation(current_rate, variation_pct=0.05):
    """
    Add a small random variation to a rate for testing UI updates
    
    Args:
        current_rate: Current exchange rate
        variation_pct: Maximum percentage variation (default 0.05%)
        
    Returns:
        Rate with small random variation
    """
    if current_rate is None:
        return None
        
    # Convert percentage to decimal and apply random variation
    variation_factor = 1 + (random.uniform(-variation_pct, variation_pct) / 100)
    return current_rate * variation_factor

def get_mock_currency_rates():
    """
    Generate mock currency data for testing
    
    Returns:
        Dictionary with mock currency rates
    """
    base_currencies = ['eur', 'usd', 'gbp', 'jpy', 'aud', 'cad', 'chf']
    mock_data = {}
    
    # Create realistic mock rates
    base_rates = {
        'eur': {'usd': 1.08, 'gbp': 0.85, 'jpy': 160.5, 'aud': 1.64, 'cad': 1.47, 'chf': 0.95},
        'usd': {'eur': 0.92, 'gbp': 0.79, 'jpy': 148.5, 'aud': 1.52, 'cad': 1.36, 'chf': 0.88},
        'gbp': {'eur': 1.17, 'usd': 1.27, 'jpy': 192.5, 'aud': 1.93, 'cad': 1.72, 'chf': 1.12},
        'jpy': {'eur': 0.0062, 'usd': 0.0067, 'gbp': 0.0052, 'aud': 0.0102, 'cad': 0.0091, 'chf': 0.0059},
        'aud': {'eur': 0.61, 'usd': 0.66, 'gbp': 0.52, 'jpy': 98.2, 'cad': 0.89, 'chf': 0.58},
        'cad': {'eur': 0.68, 'usd': 0.74, 'gbp': 0.58, 'jpy': 110.1, 'aud': 1.12, 'chf': 0.65},
        'chf': {'eur': 1.05, 'usd': 1.14, 'gbp': 0.89, 'jpy': 168.7, 'aud': 1.72, 'cad': 1.54}
    }
    
    # Add small random variations to make it more realistic
    for base in base_currencies:
        rates = {}
        for quote, rate in base_rates[base].items():
            # Add small random variation (±0.5%)
            variation = random.uniform(-0.005, 0.005)
            rates[quote] = rate * (1 + variation)
            
        # Add a timestamp
        mock_data[base] = rates
        
    return mock_data