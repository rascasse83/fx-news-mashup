import requests
import time
import random
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
    base_rates = {}
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
    ]
    headers = {
        'User-Agent': random.choice(user_agents),
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }

    if debug_log is None:
        debug_log = []

    for base, quote in currency_pairs:
        try:
            yahoo_symbol = format_currency_pair_for_yahoo(base, quote)
            spark_url = f"https://query1.finance.yahoo.com/v7/finance/spark?includePrePost=false&includeTimestamps=false&indicators=close&interval=5m&range=1d&symbols={yahoo_symbol}&lang=en-GB&region=GB"
            print(f"Fetching rate for {base}/{quote} from Spark URL: {spark_url}")
            debug_log.append(f"Fetching rate for {base}/{quote} from Spark URL: {spark_url}")

            time.sleep(random.uniform(1, 3))  # Increase delay to mimic human browsing

            spark_response = requests.get(spark_url, headers=headers)
            if spark_response.status_code == 200:
                spark_data = spark_response.json()
                if spark_data and "spark" in spark_data and "result" in spark_data["spark"]:
                    spark_result = spark_data["spark"]["result"][0]
                    if "response" in spark_result and "meta" in spark_result["response"][0]:
                        rate = spark_result["response"][0]["meta"]["regularMarketPrice"]
                        if base not in base_rates:
                            base_rates[base] = {}
                        base_rates[base][quote] = rate
                        print(f"Fetched rate for {base}/{quote} from Spark API: {rate}")
                        debug_log.append(f"Fetched rate for {base}/{quote} from Spark API: {rate}")
                    else:
                        print(f"No regularMarketPrice found in Spark API response for {base}/{quote}")
                        debug_log.append(f"No regularMarketPrice found in Spark API response for {base}/{quote}")
                else:
                    print(f"Invalid Spark API response for {base}/{quote}")
                    debug_log.append(f"Invalid Spark API response for {base}/{quote}")
            else:
                print(f"Failed to fetch data from Spark API for {base}/{quote}: {spark_response.status_code}")
                debug_log.append(f"Failed to fetch data from Spark API for {base}/{quote}: {spark_response.status_code}")

                # Fallback: Use the existing scraping method
                url = f"https://uk.finance.yahoo.com/quote/{yahoo_symbol}?{random.random()}"
                print(f"Fetching rate for {base}/{quote} from URL: {url}")
                debug_log.append(f"Fetching rate for {base}/{quote} from URL: {url}")

                response = requests.get(url, headers=headers)
                if response.status_code == 200:
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
                        if base not in base_rates:
                            base_rates[base] = {}
                        base_rates[base][quote] = rate
                        print(f"Fetched rate for {base}/{quote}: {rate}")
                        debug_log.append(f"Fetched rate for {base}/{quote}: {rate}")
                    else:
                        print(f"fin-streamer tag with data-symbol {yahoo_symbol} not found")
                        debug_log.append(f"fin-streamer tag with data-symbol {yahoo_symbol} not found")
                else:
                    print(f"Failed to fetch data for {base}/{quote}: {response.status_code}")
                    debug_log.append(f"Failed to fetch data for {base}/{quote}: {response.status_code}")

        except Exception as e:
            debug_log.append(f"Error scraping rate for {base}/{quote}: {e}")

    return base_rates


# Example usage
# currency_pairs = [('EUR', 'USD'),('GBP', 'USD'),('CAD', 'USD')]
# rates = scrape_yahoo_finance_rates(currency_pairs)
# print(rates)
