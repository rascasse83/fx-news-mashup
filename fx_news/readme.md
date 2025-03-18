# FX Pulsar

FX Pulsar is a Streamlit-based application for monitoring forex markets, summarizing financial news, and analyzing trader sentiment.

## 📂 Project Structure

```plaintext
fx_pulsar/
│
├── Home.py                   # Main Home page (entry point)
│
├── pages/                     # App pages
│   ├── 1_FX_Monitor.py        # FX Monitor (loads modules)
│   ├── 2_News_Summarizer.py   # News summarization
│   └── 3_Trader_Sentiment.py  # Trader sentiment analysis
│
├── config/                    # Configuration and settings
│   ├── __init__.py
│   ├── settings.py            # App settings and constants
│   └── styles.py              # CSS and styling
│
├── data/                      # Data models and structures
│   ├── __init__.py
│   ├── currencies.py          # Currency definitions
│   ├── models.py              # Data structures
│   └── session.py             # Session state management
│
├── services/                  # API and data processing services
│   ├── __init__.py
│   ├── rates_service.py       # Fetch and process currency rates
│   ├── news_service.py        # Fetch and process news data
│   ├── sentiment_service.py   # Process sentiment data
│   ├── events_service.py      # Economic events & calendar data
│   └── crypto_service.py      # Crypto-specific functionality
│
├── utils/                     # Utility functions
│   ├── __init__.py
│   ├── notifications.py       # Notification handling
│   ├── formatting.py          # Formatting utilities
│   └── helpers.py             # Misc helper functions
│
└── ui/                        # UI components and layout
    ├── __init__.py
    ├── components/            # UI elements
    │   ├── __init__.py
    │   ├── cards.py           # Currency cards display
    │   ├── charts.py          # Chart visualizations
    │   ├── maps.py            # Geographic visualizations
    │   ├── news.py            # News display components
    │   └── sidebar.py         # Sidebar UI components
    │
    ├── markets/               # Market-specific UI components
    │   ├── __init__.py
    │   ├── fx_market.py       # FX market UI
    │   ├── crypto_market.py   # Crypto market UI
    │   └── indices_market.py  # Indices market UI
    │
    └── layout.py              # Main layout components
```

---

## 🛠 Module Breakdown for `FX_Monitor.py`

### `config/`
- **settings.py**
  - Default pairs (`default_fx_pairs`, `default_crypto_pairs`, `default_indices`)
  - API keys and credentials
  - Page configuration
  - Logging setup
- **styles.py**
  - All CSS styling definitions
  - Style loading functions

### `data/`
- **currencies.py**
  - `indices`, `indices_regions`
  - `fx_currencies`, `crypto_currencies`
  - `currency_to_country` mappings
  - `get_available_currencies()` function
- **session.py**
  - `initialize_session_state()`
  - `ensure_initial_news_loaded()`
  - `switch_market_type()`

### `services/`
- **rates_service.py**
  - `setup_auto_refresh()`
  - `update_rates()`
  - `calculate_percentage_variation()`
  - `calculate_market_volatility()`
- **news_service.py**
  - `fetch_news()`
  - `load_news_from_disk()`
  - `create_mock_news()`
  - `tag_news_by_market_type()`
  - `filter_news_by_market_type()`
  - `fetch_indices_news()`
  - `create_mock_indices_news()`
  - `refresh_news_callback()`
- **sentiment_service.py**
  - `update_all_sentiment_data()`
  - `get_sentiment_for_pair()`
  - `load_sentiment_data()`
  - `create_sentiment_tab_ui()`
- **events_service.py**
  - `fetch_all_economic_events()`
  - `display_economic_calendar_for_currency_pair()`
  - `display_economic_events()`
  - `get_economic_events_for_currency()`
  - `create_mock_economic_events()`
  - `fetch_all_crypto_events()`
  - `display_crypto_calendar_for_currency()`
  - `display_crypto_events()`
  - `render_crypto_event_card()`

### `utils/`
- **notifications.py**
  - `add_notification()`
- **formatting.py**
  - `prepare_map_data()`
  - Helper functions for formatting data

### `ui/components/`
- **cards.py**
  - `display_currency_pair()`
- **charts.py**
  - `display_combined_charts()`
  - `blended_display_rate_history()`
  - `display_volatility_index()`
- **maps.py**
  - `display_indices_world_map()`
  - `display_indices_visualization()`
  - `display_crypto_market_visualization()`
- **news.py**
  - `display_news_sidebar()`
  - `display_news_items()`
- **sidebar.py**
  - Functions for sidebar navigation and controls

### `ui/markets/`
- **fx_market.py**
  - FX market-specific visualization and components
- **crypto_market.py**
  - Crypto market-specific visualization and components
- **indices_market.py**
  - Indices market-specific visualization and components

### `ui/layout.py`
- **layout.py**
  - `create_layout()`
  - Main page layout structure

---

## 🚀 Features
- 📊 **FX Market Monitoring** – Live tracking of forex rates  
- 📰 **News Summarization** – AI-driven summarization of financial news  
- 📈 **Trader Sentiment Analysis** – Aggregated market sentiment data  
- 🌎 **Geographic Visualizations** – Interactive market insights  

## 📌 Getting Started

### 🔧 Installation
```bash
git clone https://github.com/your-repo/fx_pulsar.git
cd fx_pulsar
pip install -r requirements.txt
```

### ▶️ Running the App
```bash
streamlit run Home.py
```

---

This `README.md` is now structured, detailed, and ready for use. Let me know if you need any modifications! 🚀