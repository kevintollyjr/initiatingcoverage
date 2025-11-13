"""
Streamlit Application for Deep Fundamental Equity Research
"""
import streamlit as st
from pathlib import Path
import logging
from typing import Optional
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import zipfile
import io

from src.config import TickerConfig, APP_CONFIG
from src.models import TickerMetadata
from src.layers import BaseLayer, MarketLayer, ExtraLayer
from src.utils import load_json, ensure_dir

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Equity Research Data Aggregator",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stProgress > div > div > div > div {
        background-color: #1f77b4;
    }
    .reportview-container .main .block-container {
        padding-top: 2rem;
    }
    h1 {
        color: #1f77b4;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables"""
    if 'progress_log' not in st.session_state:
        st.session_state.progress_log = []
    if 'collection_results' not in st.session_state:
        st.session_state.collection_results = None
    if 'ticker_metadata' not in st.session_state:
        st.session_state.ticker_metadata = None


def add_progress(message: str):
    """Add message to progress log"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.progress_log.append(f"[{timestamp}] {message}")
    logger.info(message)


def create_zip_bundle(ticker: str, data_dir: Path) -> bytes:
    """Create ZIP bundle of all ticker data"""
    ticker_dir = data_dir / ticker.upper()

    if not ticker_dir.exists():
        return None

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in ticker_dir.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(ticker_dir)
                zip_file.write(file_path, arcname)

    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def run_pipeline(ticker_config: TickerConfig, company_website: Optional[str] = None):
    """Run the data collection pipeline"""
    st.session_state.progress_log = []
    add_progress(f"Starting data collection for {ticker_config.ticker}")

    # Get ticker directory
    ticker_dir = ticker_config.get_ticker_dir(APP_CONFIG.data_dir)
    add_progress(f"Data will be saved to: {ticker_dir}")

    results = {
        'base_layer': None,
        'market_layer': None,
        'extra_layer': None
    }

    # Initialize metadata
    metadata = TickerMetadata(
        ticker=ticker_config.ticker.upper(),
        cik=ticker_config.cik,
        website=company_website
    )

    # Layer 1: Base Layer
    if ticker_config.enable_base_layer:
        add_progress("="*50)
        add_progress("LAYER 1: BASE LAYER (SEC + IR + Transcripts)")
        add_progress("="*50)

        base_layer = BaseLayer(ticker_config, ticker_dir)
        results['base_layer'] = base_layer.collect(company_website, add_progress)

        metadata.filings_count = len(results['base_layer'].get('filings', []))
        metadata.presentations_count = len(results['base_layer'].get('presentations', []))
        metadata.transcripts_count = len(results['base_layer'].get('transcripts', []))
        metadata.layers_completed.append('base')

    # Layer 2: Market Layer
    if ticker_config.enable_market_layer:
        add_progress("="*50)
        add_progress("LAYER 2: MARKET CONTEXT (Data + Estimates + News)")
        add_progress("="*50)

        market_layer = MarketLayer(ticker_config, ticker_dir)
        results['market_layer'] = market_layer.collect(company_website, add_progress)

        if results['market_layer'].get('news'):
            news_data = results['market_layer']['news']
            metadata.press_releases_count = len(news_data.get('press_releases', []))
            metadata.news_articles_count = len(news_data.get('news_articles', []))

        metadata.layers_completed.append('market')

    # Layer 3: Extra Layer
    if ticker_config.enable_extra_layer:
        add_progress("="*50)
        add_progress("LAYER 3: EXTRA DATA (Website + Management)")
        add_progress("="*50)

        extra_layer = ExtraLayer(ticker_config, ticker_dir)
        results['extra_layer'] = extra_layer.collect(company_website, add_progress)

        metadata.layers_completed.append('extra')

    # Save metadata
    metadata.last_updated = datetime.now()
    metadata_path = ticker_dir / "metadata.json"
    metadata.save(str(metadata_path))

    add_progress("="*50)
    add_progress("✅ PIPELINE COMPLETE!")
    add_progress(f"Total filings: {metadata.filings_count}")
    add_progress(f"Total presentations: {metadata.presentations_count}")
    add_progress(f"Total news articles: {metadata.news_articles_count}")
    add_progress("="*50)

    st.session_state.collection_results = results
    st.session_state.ticker_metadata = metadata


def main():
    """Main Streamlit app"""
    init_session_state()

    # Title
    st.title("📊 Deep Fundamental Equity Research")
    st.markdown("Automated data aggregation for initiating coverage reports")

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Ticker input
        ticker = st.text_input(
            "Ticker Symbol *",
            value="AAPL",
            help="Required: US equity ticker symbol"
        ).strip().upper()

        # Optional CIK
        cik = st.text_input(
            "CIK (Optional)",
            value="",
            help="Optional: SEC CIK number"
        ).strip()

        # Company website
        company_website = st.text_input(
            "Company Website",
            value="https://www.apple.com",
            help="Company website URL for IR/news crawling"
        ).strip()

        # Lookback period
        lookback_years = st.slider(
            "Years of History",
            min_value=1,
            max_value=10,
            value=10,
            help="Number of years to look back for data"
        )

        st.divider()

        # Layer toggles
        st.subheader("📁 Data Layers")

        enable_base = st.checkbox(
            "Base Layer",
            value=True,
            help="SEC filings, IR presentations, transcripts"
        )

        enable_market = st.checkbox(
            "Market Context",
            value=True,
            help="Market data, estimates, news"
        )

        enable_extra = st.checkbox(
            "Extra Data",
            value=False,
            help="Website crawl, segments, management"
        )

        st.divider()

        # API Keys
        st.subheader("🔑 API Keys (Optional)")

        alpha_vantage_key = st.text_input(
            "Alpha Vantage API Key",
            type="password",
            help="Free key from alphavantage.co"
        )

        fmp_key = st.text_input(
            "FMP API Key",
            type="password",
            help="FinancialModelingPrep key (optional)"
        )

        # SEC user agent (required)
        sec_user_agent = st.text_input(
            "SEC User Agent *",
            value="Research research@example.com",
            help="Required: Your name and email for SEC requests"
        )

        st.divider()

        # Action buttons
        col1, col2 = st.columns(2)

        with col1:
            run_button = st.button(
                "▶️ Run Pipeline",
                type="primary",
                use_container_width=True
            )

        with col2:
            clear_button = st.button(
                "🗑️ Clear Log",
                use_container_width=True
            )

        if clear_button:
            st.session_state.progress_log = []
            st.session_state.collection_results = None
            st.rerun()

    # Main area
    if run_button:
        if not ticker:
            st.error("❌ Please enter a ticker symbol")
            return

        if not sec_user_agent or '@' not in sec_user_agent:
            st.error("❌ Please provide a valid SEC user agent with email")
            return

        # Create ticker config
        ticker_config = TickerConfig(
            ticker=ticker,
            cik=cik if cik else None,
            lookback_years=lookback_years,
            enable_base_layer=enable_base,
            enable_market_layer=enable_market,
            enable_extra_layer=enable_extra,
            alpha_vantage_key=alpha_vantage_key if alpha_vantage_key else None,
            fmp_key=fmp_key if fmp_key else None,
            sec_user_agent=sec_user_agent
        )

        # Run pipeline
        with st.spinner("🔄 Running data collection pipeline..."):
            try:
                run_pipeline(ticker_config, company_website if company_website else None)
                st.success("✅ Pipeline completed successfully!")
            except Exception as e:
                st.error(f"❌ Error running pipeline: {str(e)}")
                logger.exception("Pipeline error")

    # Display progress log
    if st.session_state.progress_log:
        st.header("📋 Progress Log")
        log_container = st.container()
        with log_container:
            log_text = "\n".join(st.session_state.progress_log)
            st.text_area(
                "Log",
                value=log_text,
                height=300,
                label_visibility="collapsed"
            )

    # Display results in tabs
    if st.session_state.ticker_metadata:
        st.header("📊 Results")

        # Summary metrics
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric("Filings", st.session_state.ticker_metadata.filings_count)
        with col2:
            st.metric("Presentations", st.session_state.ticker_metadata.presentations_count)
        with col3:
            st.metric("Transcripts", st.session_state.ticker_metadata.transcripts_count)
        with col4:
            st.metric("Press Releases", st.session_state.ticker_metadata.press_releases_count)
        with col5:
            st.metric("News Articles", st.session_state.ticker_metadata.news_articles_count)

        # Download button
        st.divider()
        ticker_upper = st.session_state.ticker_metadata.ticker
        zip_data = create_zip_bundle(ticker_upper, APP_CONFIG.data_dir)

        if zip_data:
            st.download_button(
                label="📥 Download Full ZIP Bundle",
                data=zip_data,
                file_name=f"{ticker_upper}_coverage_bundle.zip",
                mime="application/zip",
                type="primary"
            )
        else:
            st.warning("No data available to download")

        # Tabs for detailed views
        tabs = st.tabs([
            "📄 SEC Filings",
            "📊 IR Decks & Transcripts",
            "📈 Market Data",
            "📰 News",
            "🌐 Website & Management"
        ])

        # Tab 1: SEC Filings
        with tabs[0]:
            st.subheader("SEC Filings")
            ticker_dir = APP_CONFIG.data_dir / ticker_upper
            filings_index_path = ticker_dir / "sec_filings" / "filings_index.json"

            if filings_index_path.exists():
                filings_data = load_json(filings_index_path)
                if filings_data:
                    df = pd.DataFrame(filings_data)
                    df['filing_date'] = pd.to_datetime(df['filing_date'])
                    df = df.sort_values('filing_date', ascending=False)

                    # Display table
                    st.dataframe(
                        df[['form_type', 'filing_date', 'accession_number', 'sec_url']],
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("No filings data available")
            else:
                st.info("No filings index found")

        # Tab 2: IR Decks & Transcripts
        with tabs[1]:
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Presentations")
                presentations_index_path = ticker_dir / "ir" / "presentations_index.json"

                if presentations_index_path.exists():
                    presentations_data = load_json(presentations_index_path)
                    if presentations_data:
                        df = pd.DataFrame(presentations_data)
                        st.dataframe(df, use_container_width=True, hide_index=True)
                    else:
                        st.info("No presentations found")
                else:
                    st.info("No presentations index found")

            with col2:
                st.subheader("Transcripts")
                transcripts_index_path = ticker_dir / "transcripts_index.json"

                if transcripts_index_path.exists():
                    transcripts_data = load_json(transcripts_index_path)
                    if transcripts_data:
                        df = pd.DataFrame(transcripts_data)
                        st.dataframe(df, use_container_width=True, hide_index=True)
                    else:
                        st.info("No transcripts found")
                else:
                    st.info("No transcripts index found")

        # Tab 3: Market Data
        with tabs[2]:
            st.subheader("Market Data & Estimates")

            # Price chart
            price_path = ticker_dir / "market_data" / "price_history.csv"
            if price_path.exists():
                try:
                    price_df = pd.read_csv(price_path, index_col=0, parse_dates=True)

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=price_df.index,
                        y=price_df['Close'],
                        mode='lines',
                        name='Close Price'
                    ))
                    fig.update_layout(
                        title=f"{ticker_upper} Price History",
                        xaxis_title="Date",
                        yaxis_title="Price (USD)",
                        hovermode='x'
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # Derived metrics
                    metrics_path = ticker_dir / "market_data" / "derived_metrics.json"
                    if metrics_path.exists():
                        metrics = load_json(metrics_path)
                        st.subheader("Key Metrics")

                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Current Price", f"${metrics.get('current_price', 0):.2f}")
                        with col2:
                            st.metric("52W High", f"${metrics.get('52w_high', 0):.2f}")
                        with col3:
                            st.metric("52W Low", f"${metrics.get('52w_low', 0):.2f}")
                        with col4:
                            vol_30d = metrics.get('volatility_30d')
                            st.metric("30D Volatility", f"{vol_30d*100:.1f}%" if vol_30d else "N/A")

                except Exception as e:
                    st.error(f"Error loading price data: {e}")
            else:
                st.info("No price history available")

            # Earnings estimates
            st.divider()
            st.subheader("Earnings Estimates")
            estimates_path = ticker_dir / "estimates" / "earnings_estimates.json"

            if estimates_path.exists():
                estimates_data = load_json(estimates_path)
                if estimates_data:
                    df = pd.DataFrame(estimates_data)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info("No earnings estimates available")
            else:
                st.info("No estimates index found")

        # Tab 4: News
        with tabs[3]:
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Press Releases")
                pr_path = ticker_dir / "news" / "press_releases.json"

                if pr_path.exists():
                    pr_data = load_json(pr_path)
                    if pr_data:
                        df = pd.DataFrame(pr_data)
                        st.dataframe(df, use_container_width=True, hide_index=True)
                    else:
                        st.info("No press releases found")
                else:
                    st.info("No press releases index found")

            with col2:
                st.subheader("External News")
                news_path = ticker_dir / "news" / "external_news.json"

                if news_path.exists():
                    news_data = load_json(news_path)
                    if news_data:
                        df = pd.DataFrame(news_data)
                        st.dataframe(df, use_container_width=True, hide_index=True)
                    else:
                        st.info("No news articles found")
                else:
                    st.info("No news index found")

        # Tab 5: Website & Management
        with tabs[4]:
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Business Segments")
                segments_path = ticker_dir / "website" / "segments.json"

                if segments_path.exists():
                    segments_data = load_json(segments_path)
                    if segments_data:
                        for segment in segments_data[:10]:  # Show first 10
                            with st.expander(segment.get('name', 'Unknown')):
                                st.write(segment.get('description', 'No description'))
                                if segment.get('source_url'):
                                    st.caption(f"Source: {segment['source_url']}")
                    else:
                        st.info("No segments found")
                else:
                    st.info("No segments index found")

            with col2:
                st.subheader("Management Team")
                mgmt_path = ticker_dir / "website" / "management_team.json"

                if mgmt_path.exists():
                    mgmt_data = load_json(mgmt_path)
                    if mgmt_data:
                        for person in mgmt_data[:15]:  # Show first 15
                            with st.expander(f"{person.get('name', 'Unknown')} - {person.get('title', '')}"):
                                st.caption(f"Category: {person.get('category', 'unknown')}")
                                if person.get('bio'):
                                    st.write(person['bio'][:500])
                    else:
                        st.info("No management profiles found")
                else:
                    st.info("No management index found")


if __name__ == "__main__":
    main()
