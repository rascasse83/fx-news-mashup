import requests
import time
import random
import re
from datetime import datetime
from bs4 import BeautifulSoup

# Cache-Control Headers: The Cache-Control headers are set to no-cache, no-store, must-revalidate to ensure that the browser does not cache the responses.
# Unique URLs: A random query parameter is appended to the URL to ensure that each request is treated as unique by the browser.

def format_currency_pair_for_yahoo(base, quote):
    base = base.upper()
    quote = quote.upper()
    if base == 'USD':
        return f"{quote}%3DX"
    else:
        return f"{base}{quote}%3DX"

def scrape_yahoo_finance_rates(currency_pairs, debug_log=None):
    all_rates = {}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }

    if debug_log is None:
        debug_log = []

    for base, quote in currency_pairs:
        try:
            yahoo_symbol = format_currency_pair_for_yahoo(base, quote)
            url = f"https://uk.finance.yahoo.com/quote/{yahoo_symbol}?{random.random()}"
            print(f"Fetching rate for {base}/{quote} from URL: {url}")
            debug_log.append(f"Fetching rate for {base}/{quote} from URL: {url}")

            time.sleep(random.uniform(0.5, 1.5))

            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                print(f"Failed to fetch data for {base}/{quote}: {response.status_code}")
                debug_log.append(f"Failed to fetch data for {base}/{quote}: {response.status_code}")
                continue

            soup = BeautifulSoup(response.text, 'html.parser')

            # Debug: Print the page content to inspect
            with open("debug_page.html", "w", encoding="utf-8") as file:
                file.write(soup.prettify())
            print(f"Page content saved to debug_page.html for {base}/{quote}")

            # Find the fin-streamer tag with the correct data-symbol attribute
            fin_streamer_tag = soup.find('fin-streamer', {'data-field': "regularMarketDayRange", 'data-symbol': re.compile(rf'{base}{quote}=X')})

            if fin_streamer_tag:
                rate_text = fin_streamer_tag['data-value']
                # Extract the first rate value from the range
                rate = float(rate_text.split(' - ')[0])

                # Initialize the base currency dictionary if not already present
                if base.lower() not in all_rates:
                    all_rates[base.lower()] = {}

                # Add the rate to the dictionary
                all_rates[base.lower()][quote.lower()] = rate

                print(f"Fetched rate for {base}/{quote}: {rate}")
                debug_log.append(f"Fetched rate for {base}/{quote}: {rate}")
            else:
                print(f"fin-streamer tag with data-symbol {yahoo_symbol} not found")
                debug_log.append(f"fin-streamer tag with data-symbol {yahoo_symbol} not found")

        except Exception as e:
            debug_log.append(f"Error scraping rate for {base}/{quote}: {e}")

    return all_rates

# Example usage
currency_pairs = [('EUR', 'USD'),('GBP', 'USD'),('CAD', 'USD')]
rates = scrape_yahoo_finance_rates(currency_pairs)
print(rates)
