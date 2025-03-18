# Indices names mapping
indices = {
    '^DJI': 'Dow Jones',
    '^GSPC': 'S&P 500',
    '^IXIC': 'NASDAQ',
    '^FTSE': 'FTSE 100',
    '^GDAXI': 'DAX',
    '^FCHI': 'CAC 40',
    '^N225': 'Nikkei 225',
}

# Add indices regions mapping for map visualization
indices_regions = {
    '^DJI': {'country': 'United States', 'region': 'North America'},
    '^GSPC': {'country': 'United States', 'region': 'North America'},
    '^IXIC': {'country': 'United States', 'region': 'North America'},
    '^FTSE': {'country': 'United Kingdom', 'region': 'Europe'},
    '^GDAXI': {'country': 'Germany', 'region': 'Europe'},
    '^FCHI': {'country': 'France', 'region': 'Europe'},
    '^N225': {'country': 'Japan', 'region': 'Asia'},
}

# FX Currencies
fx_currencies = {
    'EUR': 'Euro',
    'USD': 'US Dollar',
    'GBP': 'British Pound',
    'JPY': 'Japanese Yen',
    'AUD': 'Australian Dollar',
    'CAD': 'Canadian Dollar',
    'CHF': 'Swiss Franc',
    'CNY': 'Chinese Yuan',
    'NZD': 'New Zealand Dollar',
    'HKD': 'Hong Kong Dollar',
    'INR': 'Indian Rupee',
    'SGD': 'Singapore Dollar',
    'NOK': 'Norwegian Krone',
    'SEK': 'Swedish Krona',
    'MXN': 'Mexican Peso',
    'ZAR': 'South African Rand',
    'TRY': 'Turkish Lira',
    'XAG': 'Silver'
}


# Currency symbols
currency_symbols = {
    'USD': '$',
    'EUR': '€',
    'GBP': '£',
    'JPY': '¥',
    'AUD': 'A$',
    'CAD': 'C$',
    'CHF': 'Fr',
    'CNY': '¥',
    'INR': '₹',
    'NZD': 'NZ$',
    'HKD': 'HK$',
    'SGD': 'S$',
    'NOK': 'kr',
    'SEK': 'kr',
    'MXN': '$',
    'ZAR': 'R',
    'TRY': '₺',
    'XAG': 'XAG'
}

# Crypto Currencies
crypto_currencies = {
    'BTC': 'Bitcoin',
    'ETH': 'Ethereum',
    'XRP': 'Ripple',
    'SOL': 'Solana',
    'BNB': 'Binance Coin',
    'ADA': 'Cardano',
    'DOGE': 'Dogecoin',
    'DOT': 'Polkadot',
    'AVAX': 'Avalanche',
    'LINK': 'Chainlink',
    'LTC': 'Litecoin',
    'UNI': 'Uniswap',
    'XLM': 'Stellar',
    'MATIC': 'Polygon',
    'ATOM': 'Cosmos',
    'USDT': 'Tether',
    'USDC': 'USD Coin',
    'BUSD': 'Binance USD'
}

# Map currencies to countries
currency_to_country = {
    'EUR': [
        'Austria', 'Belgium', 'Cyprus', 'Estonia', 'Finland', 'France', 'Germany',
        'Greece', 'Ireland', 'Italy', 'Latvia', 'Lithuania', 'Luxembourg', 'Malta',
        'Netherlands', 'Portugal', 'Slovakia', 'Slovenia', 'Spain'
    ],
    'USD': 'United States',
    'GBP': 'United Kingdom',
    'JPY': 'Japan',
    'AUD': 'Australia',
    'CAD': 'Canada',
    'CHF': 'Switzerland',
    'CNY': 'China',
    'INR': 'India',
    'NZD': 'New Zealand',
    'HKD': 'Hong Kong',
    'SGD': 'Singapore',
    'XAG': 'Global'  # Silver is traded globally
}


# Major stock indices by region
north_america_indices = [
    '^DJI',   # Dow Jones
    '^GSPC',  # S&P 500
    '^IXIC',  # NASDAQ
    '^GSPTSE', # S&P/TSX Composite (Canada)
    '^MXX',   # Mexican IPC
]

europe_indices = [
    '^FTSE',  # FTSE 100 (UK)
    '^GDAXI', # DAX (Germany)
    '^FCHI',  # CAC 40 (France)
    '^STOXX50E', # EURO STOXX 50
    '^IBEX',  # IBEX 35 (Spain)
    '^FTMIB', # FTSE MIB (Italy)
    '^AEX',   # AEX (Netherlands)
]

asia_pacific_indices = [
    '^N225',  # Nikkei 225 (Japan)
    '^HSI',   # Hang Seng (Hong Kong)
    '^SSEC',  # Shanghai Composite
    '^AXJO',  # S&P/ASX 200 (Australia)
    '^BSESN', # BSE Sensex (India)
    '^KOSPI', # KOSPI (South Korea)
]

# Regional currency groups
european_currencies = ['EUR', 'GBP', 'CHF', 'NOK', 'SEK']
north_american_currencies = ['USD', 'CAD', 'MXN']
asia_pacific_currencies = ['JPY', 'CNY', 'AUD', 'NZD', 'HKD', 'SGD', 'INR']
emerging_currencies = ['TRY', 'ZAR', 'BRL', 'RUB', 'INR', 'MXN']


def get_available_currencies(market_type):
    """Return the appropriate currency mapping based on market type"""
    if market_type == 'FX':
        return fx_currencies
    elif market_type == 'Crypto':
        return crypto_currencies
    else:  # Indices
        return indices