# test_yahoo_historical.py

import requests
import time
import random
import pandas as pd
from datetime import datetime
import json


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
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }

def test_raw_request():
    """Simple direct test of the Yahoo Finance API without any complex parsing"""
    
    # Test with EUR/USD
    base = "EUR"
    quote = "USD"
    yahoo_symbol = format_currency_pair_for_yahoo(base, quote)
    
    # Construct the URL manually
    url = f"https://query1.finance.yahoo.com/v7/finance/spark?symbols={yahoo_symbol}&range=1d&interval=5m&indicators=close&includeTimestamps=true"
    
    print(f"Testing URL: {url}")
    
    # Make the request
    headers = get_random_headers()
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"Status: {response.status_code}")
        print(f"Content type: {response.headers.get('Content-Type')}")
        
        # Save the raw response
        with open("raw_response.json", "w") as f:
            f.write(response.text)
        print("Raw response saved to raw_response.json")
        
        # Try to parse JSON
        try:
            data = response.json()
            print("JSON parsed successfully!")
            
            # Check key elements
            if "spark" in data:
                print("- Found 'spark' key")
                if "result" in data["spark"]:
                    print("- Found 'result' key with", len(data["spark"]["result"]), "results")
                    
                    # Look for the first result
                    if len(data["spark"]["result"]) > 0:
                        result = data["spark"]["result"][0]
                        print("- Got first result")
                        
                        # Look for response
                        if "response" in result:
                            print("- Found 'response' key with", len(result["response"]), "items")
                            
                            # Look for the first response
                            if len(result["response"]) > 0:
                                response_data = result["response"][0]
                                print("- Got first response item")
                                
                                # Look for timestamps and indicators
                                if "timestamp" in response_data:
                                    timestamps = response_data["timestamp"]
                                    print(f"- Found {len(timestamps)} timestamps")
                                else:
                                    print("! No timestamps found")
                                
                                if "indicators" in response_data:
                                    indicators = response_data["indicators"]
                                    print("- Found indicators")
                                    
                                    if "quote" in indicators:
                                        quotes = indicators["quote"]
                                        print(f"- Found {len(quotes)} quotes")
                                        
                                        if len(quotes) > 0 and "close" in quotes[0]:
                                            close_prices = quotes[0]["close"]
                                            print(f"- Found {len(close_prices)} close prices")
                                        else:
                                            print("! No close prices found")
                                    else:
                                        print("! No quotes found in indicators")
                                else:
                                    print("! No indicators found")
                            else:
                                print("! No response items found")
                        else:
                            print("! No response key found in result")
                    else:
                        print("! No results found")
                else:
                    print("! No result key found in spark")
            else:
                print("! No spark key found")
                print("Available keys:", data.keys())
            
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            
    except Exception as e:
        print(f"Request error: {e}")

if __name__ == "__main__":
    print("Testing Yahoo Finance historical data API...")
    test_raw_request()