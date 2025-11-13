"""
Market Layer: Market data, analyst estimates, ratings, and news
"""
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any
import logging
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf

from ..models import EarningsEstimate, PressRelease, NewsArticle
from ..config import TickerConfig
from ..utils import ensure_dir, save_json, save_text
from ..utils.web_utils import WebCrawler, find_links
from ..utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class MarketDataCollector:
    """Collect market data (prices, volumes, basic fundamentals)"""

    def __init__(self, ticker_config: TickerConfig, data_dir: Path):
        self.config = ticker_config
        self.data_dir = data_dir
        self.market_dir = ensure_dir(data_dir / "market_data")

    def collect(
        self,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Collect market data using yfinance

        Returns:
            Dictionary with market data results
        """
        results = {
            'price_history': None,
            'fundamentals': None,
            'info': None
        }

        try:
            if progress_callback:
                progress_callback(f"Fetching market data for {self.config.ticker}...")

            # Get ticker object
            ticker = yf.Ticker(self.config.ticker)

            # Get price history
            if progress_callback:
                progress_callback("Downloading price history...")

            period = f"{self.config.lookback_years}y"
            hist = ticker.history(period=period, auto_adjust=True)

            if not hist.empty:
                # Save to CSV
                price_path = self.market_dir / "price_history.csv"
                hist.to_csv(price_path)
                results['price_history'] = str(price_path)

                if progress_callback:
                    progress_callback(f"Saved {len(hist)} days of price history")

                # Calculate some derived metrics
                self._calculate_metrics(hist)

            # Get company info / fundamentals
            if progress_callback:
                progress_callback("Fetching company fundamentals...")

            info = ticker.info
            if info:
                # Save basic info
                info_path = self.market_dir / "basic_fundamentals.json"
                save_json(info, info_path)
                results['info'] = info

                if progress_callback:
                    progress_callback(f"Company: {info.get('longName', 'Unknown')}")

            # Try to get financial statements
            try:
                financials = ticker.financials
                if financials is not None and not financials.empty:
                    financials.to_csv(self.market_dir / "income_statement.csv")

                balance_sheet = ticker.balance_sheet
                if balance_sheet is not None and not balance_sheet.empty:
                    balance_sheet.to_csv(self.market_dir / "balance_sheet.csv")

                cashflow = ticker.cashflow
                if cashflow is not None and not cashflow.empty:
                    cashflow.to_csv(self.market_dir / "cashflow.csv")

                if progress_callback:
                    progress_callback("Saved financial statements")

            except Exception as e:
                logger.warning(f"Could not fetch financial statements: {e}")

            results['fundamentals'] = info

        except Exception as e:
            logger.error(f"Error collecting market data: {e}")
            if progress_callback:
                progress_callback(f"Error: {str(e)}")

        return results

    def _calculate_metrics(self, price_df: pd.DataFrame):
        """Calculate and save derived metrics"""
        try:
            metrics = {}

            # Volatility windows
            for window in [30, 60, 90, 252]:
                vol = price_df['Close'].pct_change().rolling(window).std() * (252 ** 0.5)
                metrics[f'volatility_{window}d'] = vol.iloc[-1] if not vol.empty else None

            # Returns
            metrics['return_1m'] = (price_df['Close'].iloc[-1] / price_df['Close'].iloc[-21] - 1) if len(price_df) >= 21 else None
            metrics['return_3m'] = (price_df['Close'].iloc[-1] / price_df['Close'].iloc[-63] - 1) if len(price_df) >= 63 else None
            metrics['return_1y'] = (price_df['Close'].iloc[-1] / price_df['Close'].iloc[-252] - 1) if len(price_df) >= 252 else None

            # Simple stats
            metrics['current_price'] = price_df['Close'].iloc[-1]
            metrics['52w_high'] = price_df['Close'].tail(252).max() if len(price_df) >= 252 else price_df['Close'].max()
            metrics['52w_low'] = price_df['Close'].tail(252).min() if len(price_df) >= 252 else price_df['Close'].min()
            metrics['avg_volume_30d'] = price_df['Volume'].tail(30).mean()

            # Save metrics
            metrics_path = self.market_dir / "derived_metrics.json"
            save_json(metrics, metrics_path)

        except Exception as e:
            logger.error(f"Error calculating metrics: {e}")


class EstimatesCollector:
    """Collect analyst estimates and earnings data"""

    def __init__(self, ticker_config: TickerConfig, data_dir: Path):
        self.config = ticker_config
        self.data_dir = data_dir
        self.estimates_dir = ensure_dir(data_dir / "estimates")

    def collect(
        self,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[EarningsEstimate]:
        """
        Collect earnings estimates and actuals

        Returns:
            List of EarningsEstimate objects
        """
        estimates = []

        try:
            if progress_callback:
                progress_callback("Fetching earnings estimates...")

            # Use yfinance for earnings calendar
            ticker = yf.Ticker(self.config.ticker)

            # Get earnings calendar
            try:
                calendar = ticker.calendar
                if calendar is not None:
                    if progress_callback:
                        progress_callback(f"Found earnings calendar data")
                    # Save calendar
                    save_json(calendar, self.estimates_dir / "earnings_calendar.json")
            except Exception as e:
                logger.warning(f"Could not fetch earnings calendar: {e}")

            # Get earnings history
            try:
                earnings = ticker.earnings_dates
                if earnings is not None and not earnings.empty:
                    # Convert to our format
                    for date, row in earnings.iterrows():
                        estimate = EarningsEstimate(
                            fiscal_period=f"{date.year}Q{(date.month-1)//3 + 1}",
                            report_date=date,
                            actual_eps=row.get('Reported EPS'),
                            consensus_eps=row.get('EPS Estimate'),
                            surprise=row.get('Surprise(%)'),
                            provider='yfinance'
                        )

                        # Calculate surprise if we have both values
                        if estimate.actual_eps and estimate.consensus_eps:
                            estimate.surprise = estimate.actual_eps - estimate.consensus_eps
                            if estimate.consensus_eps != 0:
                                estimate.surprise_percent = (estimate.surprise / estimate.consensus_eps) * 100

                        estimates.append(estimate)

                    if progress_callback:
                        progress_callback(f"Collected {len(estimates)} earnings records")

            except Exception as e:
                logger.warning(f"Could not fetch earnings history: {e}")

            # Try Alpha Vantage if key is provided
            if self.config.alpha_vantage_key:
                av_estimates = self._fetch_from_alpha_vantage()
                estimates.extend(av_estimates)

        except Exception as e:
            logger.error(f"Error collecting estimates: {e}")
            if progress_callback:
                progress_callback(f"Error: {str(e)}")

        # Save estimates index
        self._save_estimates_index(estimates)

        return estimates

    def _fetch_from_alpha_vantage(self) -> List[EarningsEstimate]:
        """Fetch earnings data from Alpha Vantage"""
        estimates = []

        try:
            from alpha_vantage.fundamentaldata import FundamentalData

            fd = FundamentalData(key=self.config.alpha_vantage_key, output_format='pandas')

            # Get earnings
            earnings_data, _ = fd.get_company_earnings(self.config.ticker)

            if earnings_data is not None and not earnings_data.empty:
                for _, row in earnings_data.iterrows():
                    estimate = EarningsEstimate(
                        fiscal_period=row.get('fiscalDateEnding', ''),
                        report_date=pd.to_datetime(row.get('reportedDate')) if 'reportedDate' in row else None,
                        actual_eps=row.get('reportedEPS'),
                        consensus_eps=row.get('estimatedEPS'),
                        surprise=row.get('surprise'),
                        surprise_percent=row.get('surprisePercentage'),
                        provider='alpha_vantage'
                    )
                    estimates.append(estimate)

        except Exception as e:
            logger.error(f"Error fetching from Alpha Vantage: {e}")

        return estimates

    def _save_estimates_index(self, estimates: List[EarningsEstimate]):
        """Save estimates to JSON"""
        index_path = self.estimates_dir / "earnings_estimates.json"
        index_data = [e.to_dict() for e in estimates]
        save_json(index_data, index_path)


class NewsCollector:
    """Collect press releases and news articles"""

    def __init__(self, ticker_config: TickerConfig, data_dir: Path):
        self.config = ticker_config
        self.data_dir = data_dir
        self.news_dir = ensure_dir(data_dir / "news")

        self.crawler = WebCrawler(
            user_agent=ticker_config.sec_user_agent,
            rate_limit=2.0,
            respect_robots=True
        )

    def collect(
        self,
        company_website: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, List]:
        """
        Collect news and press releases

        Returns:
            Dictionary with press_releases and news_articles lists
        """
        results = {
            'press_releases': [],
            'news_articles': []
        }

        # Collect press releases from IR website
        if company_website:
            if progress_callback:
                progress_callback("Collecting press releases from IR website...")
            results['press_releases'] = self._collect_press_releases(company_website)

        # Collect external news
        if progress_callback:
            progress_callback("Fetching external news articles...")
        results['news_articles'] = self._collect_external_news()

        return results

    def _collect_press_releases(self, website: str) -> List[PressRelease]:
        """Collect press releases from IR website"""
        press_releases = []

        try:
            # Find IR or News section
            soup = self.crawler.fetch_html(website)
            if not soup:
                return []

            # Look for news/press release links
            news_patterns = ['news', 'press release', 'press-release', 'media']
            news_links = find_links(soup, website, news_patterns)

            # Visit news page
            for news_url in news_links[:3]:  # Limit to first 3 pages
                news_soup = self.crawler.fetch_html(news_url)
                if not news_soup:
                    continue

                # Find article links
                # This is a simplified example - would need customization per site
                for a_tag in news_soup.find_all('a', href=True):
                    title = a_tag.get_text(strip=True)
                    if len(title) < 10:  # Skip short titles
                        continue

                    href = a_tag['href']
                    from urllib.parse import urljoin
                    article_url = urljoin(news_url, href)

                    # Try to extract date from context
                    date_str = ""
                    parent = a_tag.parent
                    if parent:
                        import re
                        date_match = re.search(r'\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}', parent.get_text())
                        if date_match:
                            date_str = date_match.group()

                    parsed_date = None
                    if date_str:
                        try:
                            import dateparser
                            parsed_date = dateparser.parse(date_str)
                        except:
                            pass

                    pr = PressRelease(
                        title=title,
                        date=parsed_date,
                        url=article_url,
                        category='general'
                    )
                    press_releases.append(pr)

                    if len(press_releases) >= 50:  # Limit total
                        break

                if len(press_releases) >= 50:
                    break

        except Exception as e:
            logger.error(f"Error collecting press releases: {e}")

        # Save press releases
        self._save_press_releases_index(press_releases)

        return press_releases

    def _collect_external_news(self) -> List[NewsArticle]:
        """Collect external news articles using yfinance"""
        articles = []

        try:
            ticker = yf.Ticker(self.config.ticker)
            news = ticker.news

            if news:
                for item in news[:50]:  # Limit to 50 most recent
                    article = NewsArticle(
                        headline=item.get('title', 'No title'),
                        source=item.get('publisher', 'Unknown'),
                        timestamp=datetime.fromtimestamp(item.get('providerPublishTime', 0)),
                        url=item.get('link', ''),
                        snippet=item.get('summary', ''),
                        provider='yfinance'
                    )
                    articles.append(article)

        except Exception as e:
            logger.error(f"Error collecting external news: {e}")

        # Save news articles
        self._save_news_articles_index(articles)

        return articles

    def _save_press_releases_index(self, press_releases: List[PressRelease]):
        """Save press releases to JSON"""
        index_path = self.news_dir / "press_releases.json"
        index_data = [pr.to_dict() for pr in press_releases]
        save_json(index_data, index_path)

    def _save_news_articles_index(self, articles: List[NewsArticle]):
        """Save news articles to JSON"""
        index_path = self.news_dir / "external_news.json"
        index_data = [a.to_dict() for a in articles]
        save_json(index_data, index_path)


class MarketLayer:
    """Orchestrates Market Layer data collection"""

    def __init__(self, ticker_config: TickerConfig, data_dir: Path):
        self.config = ticker_config
        self.data_dir = data_dir

        # Initialize collectors
        self.market_collector = MarketDataCollector(ticker_config, data_dir)
        self.estimates_collector = EstimatesCollector(ticker_config, data_dir)
        self.news_collector = NewsCollector(ticker_config, data_dir)

    def collect(
        self,
        company_website: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> dict:
        """
        Run full Market Layer collection

        Args:
            company_website: Company website URL
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with collection results
        """
        results = {
            'market_data': {},
            'estimates': [],
            'news': {}
        }

        # Collect market data
        if self.config.collect_price_history or self.config.collect_fundamentals:
            if progress_callback:
                progress_callback("Starting market data collection...")
            results['market_data'] = self.market_collector.collect(progress_callback)
        else:
            if progress_callback:
                progress_callback("Market data collection skipped (disabled in settings)")

        # Collect estimates
        if self.config.collect_earnings_estimates:
            if progress_callback:
                progress_callback("Starting estimates collection...")
            results['estimates'] = self.estimates_collector.collect(progress_callback)
        else:
            if progress_callback:
                progress_callback("Estimates collection skipped (disabled in settings)")

        # Collect news
        if self.config.collect_press_releases or self.config.collect_external_news:
            if progress_callback:
                progress_callback("Starting news collection...")
            results['news'] = self.news_collector.collect(company_website, progress_callback)
        else:
            if progress_callback:
                progress_callback("News collection skipped (disabled in settings)")

        return results
