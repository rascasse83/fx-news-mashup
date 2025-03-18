import streamlit as st
import logging
import os

# API Keys
API_KEY = os.getenv("CURRENCY_API_KEY")


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
    'INR': 'Indian Rupee',
    'XAG': 'Silver'
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

# Indices
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

# Mapping of currencies to countries
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

# Major currency pairs
major_pairs = [
    'EUR/USD',
    'USD/JPY',
    'GBP/USD',
    'USD/CHF',
    'AUD/USD',
    'USD/CAD',
    'NZD/USD',
]

# Minor currency pairs (crosses)
minor_pairs = [
    'EUR/GBP',
    'EUR/JPY',
    'EUR/CHF',
    'EUR/AUD',
    'GBP/JPY',
    'CHF/JPY',
    'AUD/JPY',
    'AUD/CAD',
    'AUD/NZD',
    'AUD/CHF',
    'CAD/JPY',
    'NZD/JPY',
]

# Exotic currency pairs
exotic_pairs = [
    'USD/TRY',
    'USD/MXN',
    'USD/ZAR',
    'USD/HKD',
    'USD/SGD',
    'USD/NOK',
    'USD/SEK',
    'EUR/TRY',
    'EUR/NOK',
    'EUR/SEK',
    'GBP/TRY',
    'GBP/ZAR',
]

# Major cryptocurrencies
major_cryptos = [
    'BTC/USD',
    'ETH/USD',
    'BTC/USDT',
    'ETH/USDT',
    'BNB/USD',
    'SOL/USD',
    'XRP/USD',
    'ADA/USD',
]

# Cryptocurrency crosses
crypto_crosses = [
    'ETH/BTC',
    'BNB/BTC',
    'SOL/BTC',
    'XRP/BTC',
    'ADA/BTC',
    'DOT/BTC',
    'DOGE/BTC',
]

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

# Default Pairs
default_fx_pairs = [
    {"base": "EUR", "quote": "USD", "threshold": 0.05, "last_rate": None, "current_rate": None},
    {"base": "USD", "quote": "JPY", "threshold": 0.05, "last_rate": None, "current_rate": None},
    {"base": "EUR", "quote": "GBP", "threshold": 0.05, "last_rate": None, "current_rate": None},
    {"base": "AUD", "quote": "USD", "threshold": 0.05, "last_rate": None, "current_rate": None},
    {"base": "USD", "quote": "CAD", "threshold": 0.05, "last_rate": None, "current_rate": None},
    {"base": "USD", "quote": "CHF", "threshold": 0.05, "last_rate": None, "current_rate": None},
    {"base": "CNY", "quote": "USD", "threshold": 0.05, "last_rate": None, "current_rate": None},
    {"base": "USD", "quote": "INR", "threshold": 0.05, "last_rate": None, "current_rate": None},    
]

default_crypto_pairs = [
    {"base": "BTC", "quote": "USD", "threshold": 0.5, "last_rate": None, "current_rate": None},
    {"base": "ETH", "quote": "USD", "threshold": 0.5, "last_rate": None, "current_rate": None},
    {"base": "SOL", "quote": "USD", "threshold": 0.5, "last_rate": None, "current_rate": None},
    {"base": "BNB", "quote": "USD", "threshold": 0.5, "last_rate": None, "current_rate": None},
    {"base": "XRP", "quote": "USD", "threshold": 0.5, "last_rate": None, "current_rate": None},
    {"base": "ETH", "quote": "BTC", "threshold": 0.5, "last_rate": None, "current_rate": None},
]

default_indices = [
    {"base": "^DJI", "quote": "USD", "threshold": 0.5, "last_rate": None, "current_rate": None},     # Dow Jones
    {"base": "^GSPC", "quote": "USD", "threshold": 0.5, "last_rate": None, "current_rate": None},    # S&P 500
    {"base": "^IXIC", "quote": "USD", "threshold": 0.5, "last_rate": None, "current_rate": None},    # NASDAQ
    {"base": "^FTSE", "quote": "GBP", "threshold": 0.5, "last_rate": None, "current_rate": None},    # FTSE 100
    {"base": "^GDAXI", "quote": "EUR", "threshold": 0.5, "last_rate": None, "current_rate": None},   # DAX
    {"base": "^FCHI", "quote": "EUR", "threshold": 0.5, "last_rate": None, "current_rate": None},    # CAC 40
    {"base": "^N225", "quote": "JPY", "threshold": 0.5, "last_rate": None, "current_rate": None},    # Nikkei 225
]

def setup_logging(name):
    """Set up logging configuration"""
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
        level=logging.INFO
    )
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)  # Set to INFO for production, DEBUG for development
    return logger

def configure_page():
    """Configure the Streamlit page settings"""
    st.set_page_config(
        page_title="FX Pulsar - Market Monitor",
        page_icon="https://images.seeklogo.com/logo-png/60/1/lmax-digital-icon-black-logo-png_seeklogo-609777.png",
        layout="wide",
        initial_sidebar_state="expanded"
    )