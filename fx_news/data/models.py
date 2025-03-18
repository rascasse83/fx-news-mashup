"""
Data models and structures for the FX Pulsar application.
Contains class definitions and data structures used throughout the application.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Union, Any
from datetime import datetime
import pandas as pd

@dataclass
class CurrencyPair:
    """Model for a currency pair subscription."""
    base: str
    quote: str
    threshold: float = 0.05
    last_rate: Optional[float] = None
    current_rate: Optional[float] = None
    previous_close: Optional[float] = None

    def get_pair_key(self) -> str:
        """Return a unique identifier for this currency pair."""
        return f"{self.base.lower()}_{self.quote.lower()}"
    
    def get_display_name(self) -> str:
        """Return a display name for this currency pair."""
        return f"{self.base}/{self.quote}"
    
    def calculate_percent_change(self) -> Optional[float]:
        """Calculate the percentage change from reference price."""
        reference_price = None
        if self.previous_close is not None:
            reference_price = self.previous_close
        elif self.last_rate is not None:
            reference_price = self.last_rate
            
        if reference_price is not None and self.current_rate is not None:
            return ((self.current_rate - reference_price) / reference_price) * 100
        return None

@dataclass
class NewsItem:
    """Model for a news item."""
    title: str
    summary: str = ""
    source: str = "Unknown"
    timestamp: datetime = field(default_factory=datetime.now)
    currency: str = ""
    currency_pairs: Set[str] = field(default_factory=set)
    sentiment: str = "neutral"
    score: float = 0.0
    url: str = ""
    unix_timestamp: Optional[int] = None
    file_path: str = ""
    is_fx: bool = False
    is_crypto: bool = False
    is_indices: bool = False
    is_market: bool = False

    def __post_init__(self):
        """Initialize after object creation."""
        if self.unix_timestamp is None and self.timestamp:
            self.unix_timestamp = int(self.timestamp.timestamp())

@dataclass
class EconomicEvent:
    """Model for an economic calendar event."""
    event: str
    date: str
    time: str = ""
    country: str = ""
    importance: int = 0
    actual: str = ""
    forecast: str = ""
    previous: str = ""
    impact_currency: str = ""
    event_url: str = ""

@dataclass
class CryptoEvent:
    """Model for a cryptocurrency event."""
    title: str
    description: str = ""
    date: str = ""
    type: str = "Event"
    coin: str = ""
    url: str = ""

@dataclass
class SentimentData:
    """Model for trader sentiment data."""
    pair: str
    long_percentage: float = 50.0
    short_percentage: float = 50.0
    long_price: str = ""
    short_price: str = ""
    long_distance: str = ""
    short_distance: str = ""
    current_rate: str = ""
    detailed: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_bullish(self) -> bool:
        """Return True if sentiment is bullish (more longs than shorts)."""
        return self.long_percentage >= 50

@dataclass
class RateHistory:
    """Model for historical rate data."""
    timestamp: datetime
    rate: float

@dataclass
class MarketVariation:
    """Model for currency market variation data."""
    currency_pair: str
    base: str
    quote: str
    variation: float