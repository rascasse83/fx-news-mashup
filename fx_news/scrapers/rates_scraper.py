import requests
import time
import random
import re
from datetime import datetime
from bs4 import BeautifulSoup
import concurrent.futures
from functools import lru_cache
import pandas as pd
import logging

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger("yahoo_finance_scraper")

# To enable debug logs during development:
# logger.setLevel(logging.DEBUG)

# To disable debug logs in production:
logger.setLevel(logging.WARNING)

def format_currency_pair_for_yahoo(base, quote):
    """
    Format currency pair for Yahoo Finance URL
    
    Args:
        base: Base currency code (e.g., 'EUR', 'BTC', '^DJI')
        quote: Quote currency code (e.g., 'USD', 'JPY')
        
    Returns:
        Formatted symbol for Yahoo Finance
    """
    base = base.upper()
    quote = quote.upper()
    
    # Handle indices (^DJI, ^GSPC, etc.)
    if base.startswith('^'):
        return base
    
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
        logger.error(f"Error fetching quote for {symbol}: {e}")
    
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
        logger.debug(f"Trying fallback URL: {spark_url}")
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
        logger.error(f"Error fetching spark data for {base}/{quote}: {e}")
    
    return (base, quote, None)

def fetch_historical_rates(base, quote, range_val="1d", interval="5m", debug_log=None):
    """
    Fetch historical rate data for a currency pair using Yahoo Finance spark API
    
    Args:
        base: Base currency code (e.g., 'EUR', 'BTC')
        quote: Quote currency code (e.g., 'USD', 'JPY')
        range_val: Time range (1d, 5d, 1mo, 3mo, 6mo, 1y, etc.)
        interval: Data interval (1m, 5m, 15m, 1h, 1d, etc.)
        debug_log: Optional list to append debug information
    
    Returns:
        DataFrame with historical rate data or None if fetch fails
    """
    if debug_log is None:
        debug_log = []
    
    # Format the Yahoo Finance symbol
    yahoo_symbol = format_currency_pair_for_yahoo(base, quote)
    
    # Construct the spark API URL
    spark_url = f"https://query1.finance.yahoo.com/v7/finance/spark?symbols={yahoo_symbol}&range={range_val}&interval={interval}&indicators=close&includeTimestamps=true"
    
    logger.debug(f"Fetching from URL: {spark_url}")
    
    # Random headers to avoid detection
    headers = get_random_headers()
    
    try:
        debug_log.append(f"Fetching historical data for {base}/{quote} with range={range_val}, interval={interval}")
        start_time = time.time()
        
        response = requests.get(spark_url, headers=headers, timeout=10)
        
        logger.debug(f"API response status code: {response.status_code}")
        
        if response.status_code == 200:
            # Save raw response only in DEBUG level
            if logger.isEnabledFor(logging.DEBUG):
                try:
                    with open(f"{base}_{quote}_response.json", "w") as f:
                        f.write(response.text)
                    logger.debug(f"Saved raw response to {base}_{quote}_response.json")
                except Exception as e:
                    logger.warning(f"Could not save raw response: {e}")
            
            try:
                data = response.json()
                logger.debug("Successfully parsed JSON response")
                
                # Navigate through nested JSON to get to the timestamp and close data
                if "spark" in data and "result" in data["spark"] and len(data["spark"]["result"]) > 0:
                    result = data["spark"]["result"][0]
                    logger.debug("Found spark result data")
                    
                    if "response" in result and len(result["response"]) > 0:
                        response_data = result["response"][0]
                        logger.debug("Found response data")
                        
                        # Extract timestamps and close prices
                        timestamps = response_data.get("timestamp", [])
                        logger.debug(f"Found {len(timestamps)} timestamps")
                        
                        close_prices = response_data.get("indicators", {}).get("quote", [{}])[0].get("close", [])
                        logger.debug(f"Found {len(close_prices)} close prices")
                        
                        # Also extract metadata for additional information
                        meta = response_data.get("meta", {})
                        current_price = meta.get("regularMarketPrice")
                        previous_close = meta.get("previousClose")
                        
                        logger.debug(f"Metadata - Current price: {current_price}, Previous close: {previous_close}")
                        
                        # Create DataFrame
                        if timestamps and close_prices and len(timestamps) == len(close_prices):
                            df = pd.DataFrame({
                                "timestamp": [datetime.fromtimestamp(ts) for ts in timestamps],
                                "rate": close_prices
                            })
                            
                            # Add metadata
                            df["current_price"] = current_price
                            df["previous_close"] = previous_close
                            
                            end_time = time.time()
                            logger.info(f"Successfully fetched {len(df)} historical data points for {base}/{quote} in {end_time - start_time:.2f} seconds")
                            debug_log.append(f"Successfully fetched {len(df)} historical data points in {end_time - start_time:.2f} seconds")
                            return df
                        else:
                            logger.warning("Timestamps and close prices don't match or are empty")
                            logger.debug(f"Timestamps length: {len(timestamps)}")
                            logger.debug(f"Close prices length: {len(close_prices)}")
                            debug_log.append("Timestamps and close prices don't match or are empty")
                    else:
                        logger.warning("No response data found in spark result")
                        logger.debug("Available keys in result:", result.keys() if isinstance(result, dict) else "Not a dict")
                        debug_log.append("No response data found in spark result")
                else:
                    logger.warning("No spark result found in response")
                    logger.debug("Response keys: %s", data.keys())
                    if "spark" in data and "error" in data["spark"]:
                        logger.warning("Error message from Yahoo: %s", data["spark"]["error"])
                    debug_log.append("No spark result found in response")
            except Exception as parsing_error:
                logger.error(f"Error parsing JSON response: {parsing_error}")
                debug_log.append(f"Error parsing JSON response: {str(parsing_error)}")
        else:
            logger.error(f"API request failed with status code: {response.status_code}")
            logger.debug("Response: %s", response.text[:500] + ("..." if len(response.text) > 500 else ""))
            debug_log.append(f"API request failed with status code: {response.status_code}")
    
    except Exception as e:
        logger.error(f"Error fetching historical data: {str(e)}")
        debug_log.append(f"Error fetching historical data: {str(e)}")
    
    return None

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
    
    logger.info(f"Starting to fetch rates for {len(currency_pairs)} currency pairs")
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
                    logger.debug(f"Successfully fetched {base}/{quote}: {result}")
                    debug_log.append(f"Successfully fetched {base}/{quote}: {result}")
                else:
                    logger.warning(f"Failed to fetch data for {base}/{quote}")
                    debug_log.append(f"Failed to fetch data for {base}/{quote}")
            except Exception as e:
                logger.error(f"Error processing result: {e}")
                debug_log.append(f"Error processing result: {e}")
    
    end_time = time.time()
    logger.info(f"Completed fetching rates for {len(currency_pairs)} pairs in {end_time - start_time:.2f} seconds")
    debug_log.append(f"Completed fetching rates in {end_time - start_time:.2f} seconds")
        
    return base_rates

# Example usage
if __name__ == "__main__":
    # Set log level for testing
    logger.setLevel(logging.DEBUG)
    
    # Test with historical data
    logger.info("Testing historical rate fetching...")
    df = fetch_historical_rates('^DJI', 'USD', '1d', '5m')
    if df is not None:
        logger.info(f"Retrieved {len(df)} data points")
        logger.info(f"Sample data:\n{df.head()}")  # Display the first few rows
    else:
        logger.error("Failed to retrieve data")
    
    # Uncomment to test real-time rates
    # currency_pairs = [('EUR', 'USD'), ('GBP', 'USD'), ('USD', 'JPY'), ('BTC', 'USD')]
    # logger.info("Testing parallel processing approach...")
    # start = time.time()
    # rates = scrape_yahoo_finance_rates(currency_pairs)
    # end = time.time()
    # logger.info(f"Parallel method took {end - start:.2f} seconds")
    # logger.info(f"Results: {rates}")