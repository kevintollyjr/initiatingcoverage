"""
Configuration management for the equity research application
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import os


@dataclass
class AppConfig:
    """Main application configuration"""

    # Data paths
    data_dir: Path = Path("data")
    cache_dir: Path = Path(".cache")

    # SEC EDGAR settings
    sec_user_agent: str = "Research App contact@example.com"  # MUST be overridden
    sec_rate_limit: float = 0.1  # 10 requests per second max

    # Default settings
    default_lookback_years: int = 10
    max_crawl_depth: int = 3
    max_pages_per_domain: int = 100

    # API endpoints
    sec_edgar_base: str = "https://www.sec.gov"

    def __post_init__(self):
        """Ensure directories exist"""
        self.data_dir.mkdir(exist_ok=True)
        self.cache_dir.mkdir(exist_ok=True)


@dataclass
class TickerConfig:
    """Configuration for a specific ticker research job"""

    ticker: str
    cik: Optional[str] = None
    lookback_years: int = 10

    # Layer toggles
    enable_base_layer: bool = True
    enable_market_layer: bool = True
    enable_extra_layer: bool = True

    # Base Layer - Granular controls
    collect_10k: bool = True
    collect_10q: bool = True
    collect_def14a: bool = True
    collect_8k: bool = True
    collect_ir_presentations: bool = True
    collect_transcripts: bool = True

    # Market Layer - Granular controls
    collect_price_history: bool = True
    collect_fundamentals: bool = True
    collect_earnings_estimates: bool = True
    collect_analyst_ratings: bool = True
    collect_press_releases: bool = True
    collect_external_news: bool = True

    # Extra Layer - Granular controls
    collect_website_segments: bool = True
    collect_management_profiles: bool = True
    collect_comprehensive_website: bool = True  # NEW: Crawl entire website for business info
    max_website_pages: int = 100
    website_crawl_depth: int = 2

    # SEC Filing format preference
    sec_filing_format: str = "html"  # "html", "pdf", or "both"

    # API keys (from Streamlit secrets or environment)
    alpha_vantage_key: Optional[str] = None
    fmp_key: Optional[str] = None  # FinancialModelingPrep
    finnhub_key: Optional[str] = None  # Finnhub (for earnings call transcripts)

    # Contact info for SEC (required)
    sec_user_agent: Optional[str] = None

    def __post_init__(self):
        """Load from environment if not provided"""
        if not self.alpha_vantage_key:
            self.alpha_vantage_key = os.getenv("ALPHA_VANTAGE_KEY")
        if not self.fmp_key:
            self.fmp_key = os.getenv("FMP_KEY")
        if not self.finnhub_key:
            self.finnhub_key = os.getenv("FINNHUB_KEY")
        if not self.sec_user_agent:
            self.sec_user_agent = os.getenv("SEC_USER_AGENT", "Research App contact@example.com")

    def get_ticker_dir(self, base_dir: Path) -> Path:
        """Get the data directory for this ticker"""
        ticker_dir = base_dir / self.ticker.upper()
        ticker_dir.mkdir(parents=True, exist_ok=True)
        return ticker_dir


# Global app config instance
APP_CONFIG = AppConfig()
