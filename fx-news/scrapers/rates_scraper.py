import requests
import time
import random
import re
from datetime import datetime
from bs4 import BeautifulSoup
import concurrent.futures
from functools import lru_cache

def format_currency_pair_for_yahoo(base, quote):
    """
    Format currency pair for Yahoo Finance URL
    
    Args:
        base: Base currency code (e.g., 'EUR', 'BTC')
        quote: Quote currency code (e.g., 'USD', 'JPY')
        
    Returns:
        Formatted symbol for Yahoo Finance
    """
    base = base.upper()
    quote = quote.upper()
    
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

# Cache quote results for 1 minute (60 seconds)
@lru_cache(maxsize=128)
def fetch_quote_with_cache(symbol, timestamp):
    """
    Fetch a single quote with caching
    timestamp parameter is used to invalidate cache after desired time
    """
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbol}"
    headers = get_random_headers()
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'quoteResponse' in data and 'result' in data['quoteResponse'] and len(data['quoteResponse']['result']) > 0:
                quote_data = data['quoteResponse']['result'][0]
                return {
                    "price": quote_data.get('regularMarketPrice'),
                    "previous_close": quote_data.get('previousClose')
                }
    except Exception as e:
        print(f"Error fetching quote for {symbol}: {e}")
    
    return None

def fetch_single_currency_pair(pair_info):
    """Fetch data for a single currency pair"""
    base, quote = pair_info
    yahoo_symbol = format_currency_pair_for_yahoo(base, quote)
    
    # Create a timestamp rounded to the nearest minute for cache invalidation
    cache_timestamp = int(time.time() / 60)
    
    result = fetch_quote_with_cache(yahoo_symbol, cache_timestamp)
    if result:
        return (base, quote, result)
    
    # If the quote API fails, try the spark API as fallback
    try:
        spark_url = f"https://query1.finance.yahoo.com/v7/finance/spark?symbols={yahoo_symbol}&range=1d&interval=5m&indicators=close&includeTimestamps=false"
        headers = get_random_headers()
        
        response = requests.get(spark_url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if "spark" in data and "result" in data["spark"] and len(data["spark"]["result"]) > 0:
                spark_result = data["spark"]["result"][0]
                if "response" in spark_result and len(spark_result["response"]) > 0 and "meta" in spark_result["response"][0]:
                    meta_data = spark_result["response"][0]["meta"]
                    return (base, quote, {
                        "price": meta_data.get("regularMarketPrice"),
                        "previous_close": meta_data.get("previousClose")
                    })
    except Exception as e:
        print(f"Error fetching spark data for {base}/{quote}: {e}")
    
    return (base, quote, None)

def scrape_yahoo_finance_rates(currency_pairs, debug_log=None):
    """
    Scrape currency exchange rates from Yahoo Finance for multiple currency pairs
    using parallel processing for faster results.
    
    Args:
        currency_pairs: List of tuples containing (base, quote) currency pairs
        debug_log: Optional list to append debug information
    
    Returns:
        Dictionary with structure: {base_currency: {quote_currency: {price: value, previous_close: value}}}
    """
    if debug_log is None:
        debug_log = []
    
    base_rates = {}
    start_time = time.time()
    debug_log.append(f"Starting to fetch rates for {len(currency_pairs)} currency pairs")
    
    # Use ThreadPoolExecutor for parallel requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(currency_pairs))) as executor:
        futures = [executor.submit(fetch_single_currency_pair, pair) for pair in currency_pairs]
        
        for future in concurrent.futures.as_completed(futures):
            try:
                base, quote, result = future.result()
                if result:
                    if base not in base_rates:
                        base_rates[base] = {}
                    base_rates[base][quote] = result
                    debug_log.append(f"Successfully fetched {base}/{quote}: {result}")
                else:
                    debug_log.append(f"Failed to fetch data for {base}/{quote}")
            except Exception as e:
                debug_log.append(f"Error processing result: {e}")
    
    end_time = time.time()
    debug_log.append(f"Completed fetching rates in {end_time - start_time:.2f} seconds")
        
    return base_rates

# Example usage
if __name__ == "__main__":
    # Test with a few currency pairs
    currency_pairs = [('EUR', 'USD'), ('GBP', 'USD'), ('USD', 'JPY'), ('BTC', 'USD')]
    
    print("Testing parallel processing approach:")
    start = time.time()
    rates1 = scrape_yahoo_finance_rates(currency_pairs)
    end = time.time()
    print(f"Parallel method took {end - start:.2f} seconds")
    print(rates1)
   