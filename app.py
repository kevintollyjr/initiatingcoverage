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

    # Deployment info
    import os
    if os.getenv('STREAMLIT_SHARING_MODE') or os.getenv('STREAMLIT_CLOUD'):
        st.info("""
        **☁️ Running on Streamlit Cloud**
        - ✅ All data collection features available
        - ❌ AI features (report generation, chat) require local deployment
        - ℹ️ PDF conversion unavailable (SEC filings saved as HTML/TXT)

        To use AI features, [run locally](https://github.com/yourusername/initiatingcoverage#installation) and install Ollama.
        """)

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
            max_value=20,
            value=10,
            help="Number of years to look back for data (1-20 years)"
        )

        st.divider()

        # Layer toggles
        st.subheader("📁 Data Layers")

        enable_base = st.checkbox(
            "Base Layer",
            value=True,
            help="SEC filings, IR presentations, transcripts"
        )

        # Base Layer granular controls
        if enable_base:
            with st.expander("⚙️ Base Layer Settings"):
                st.caption("SEC Filings")
                col1, col2 = st.columns(2)
                with col1:
                    collect_10k = st.checkbox("10-K", value=True, key="10k")
                    collect_10q = st.checkbox("10-Q", value=True, key="10q")
                with col2:
                    collect_def14a = st.checkbox("DEF 14A", value=True, key="def14a")
                    collect_8k = st.checkbox("8-K", value=True, key="8k")

                st.caption("Filing Format")
                sec_filing_format = st.radio(
                    "Preferred Format",
                    options=["html", "pdf", "both"],
                    index=0,
                    horizontal=True,
                    help="HTML is faster, PDF is more readable, Both downloads everything"
                )

                # Check if PDF conversion is available
                try:
                    from src.layers.base_layer import WEASYPRINT_AVAILABLE
                    if not WEASYPRINT_AVAILABLE and sec_filing_format in ["pdf", "both"]:
                        st.info("ℹ️ PDF conversion not available (expected on Streamlit Cloud). SEC filings will be saved as HTML/TXT, which works great for analysis!")
                except ImportError:
                    pass

                st.caption("Investor Relations")
                collect_ir_presentations = st.checkbox("IR Presentations", value=True, key="ir_pres")
                collect_transcripts = st.checkbox("Earnings Transcripts", value=True, key="transcripts")
        else:
            collect_10k = collect_10q = collect_def14a = collect_8k = False
            collect_ir_presentations = collect_transcripts = False
            sec_filing_format = "html"

        enable_market = st.checkbox(
            "Market Context",
            value=True,
            help="Market data, estimates, news"
        )

        # Market Layer granular controls
        if enable_market:
            with st.expander("⚙️ Market Layer Settings"):
                st.caption("Market Data")
                collect_price_history = st.checkbox("Price History", value=True, key="price")
                collect_fundamentals = st.checkbox("Fundamentals", value=True, key="fundamentals")

                st.caption("Estimates & Ratings")
                collect_earnings_estimates = st.checkbox("Earnings Estimates", value=True, key="estimates")
                collect_analyst_ratings = st.checkbox("Analyst Ratings", value=True, key="ratings")

                st.caption("News")
                collect_press_releases = st.checkbox("Press Releases", value=True, key="pr")
                collect_external_news = st.checkbox("External News", value=True, key="news")
        else:
            collect_price_history = collect_fundamentals = False
            collect_earnings_estimates = collect_analyst_ratings = False
            collect_press_releases = collect_external_news = False

        enable_extra = st.checkbox(
            "Extra Data",
            value=False,
            help="Website crawl, segments, management"
        )

        # Extra Layer granular controls
        if enable_extra:
            with st.expander("⚙️ Extra Layer Settings"):
                st.caption("Website Analysis")
                collect_website_segments = st.checkbox("Business Segments", value=True, key="segments")
                collect_management_profiles = st.checkbox("Management Profiles", value=True, key="mgmt")
                collect_comprehensive_website = st.checkbox(
                    "Comprehensive Website Crawl",
                    value=True,
                    key="comprehensive_web",
                    help="Deep crawl of entire website for business info (products, tech, strategy, etc.)"
                )

                st.caption("Crawl Parameters")
                max_website_pages = st.number_input(
                    "Max Pages to Crawl",
                    min_value=10,
                    max_value=500,
                    value=100,
                    step=10,
                    help="Maximum number of website pages to crawl"
                )
                website_crawl_depth = st.slider(
                    "Crawl Depth",
                    min_value=1,
                    max_value=5,
                    value=2,
                    help="How many levels deep to crawl from main page"
                )
        else:
            collect_website_segments = collect_management_profiles = False
            collect_comprehensive_website = False
            max_website_pages = 100
            website_crawl_depth = 2

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
            # Base layer granular settings
            collect_10k=collect_10k,
            collect_10q=collect_10q,
            collect_def14a=collect_def14a,
            collect_8k=collect_8k,
            collect_ir_presentations=collect_ir_presentations,
            collect_transcripts=collect_transcripts,
            sec_filing_format=sec_filing_format,
            # Market layer granular settings
            collect_price_history=collect_price_history,
            collect_fundamentals=collect_fundamentals,
            collect_earnings_estimates=collect_earnings_estimates,
            collect_analyst_ratings=collect_analyst_ratings,
            collect_press_releases=collect_press_releases,
            collect_external_news=collect_external_news,
            # Extra layer granular settings
            collect_website_segments=collect_website_segments,
            collect_management_profiles=collect_management_profiles,
            collect_comprehensive_website=collect_comprehensive_website,
            max_website_pages=max_website_pages,
            website_crawl_depth=website_crawl_depth,
            # API keys
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
            "🌐 Website & Management",
            "🤖 AI Report",
            "💬 Chat Q&A"
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

        # Tab 6: AI Report Generation
        with tabs[5]:
            st.subheader("🤖 AI-Generated Initiating Coverage Report")

            # Cloud deployment notice
            st.info("""
            **💡 Local Feature Only**
            AI features require Ollama running on your local machine. They are **not available on Streamlit Cloud**
            due to resource limitations. To use AI features, run this app locally and install Ollama.
            """)

            # Check if Ollama is available
            try:
                from src.llm import (
                    check_ollama_installation,
                    get_available_models,
                    ReportGenerator
                )

                ollama_available, ollama_status = check_ollama_installation()

                if not ollama_available:
                    st.warning("⚠️ Ollama not available")
                    st.info(ollama_status)
                    st.markdown("""
                    **To use AI features:**
                    1. Install Ollama: [https://ollama.ai](https://ollama.ai)
                    2. Install Python package: `pip install ollama`
                    3. Download a model: `ollama pull llama3.1:8b`
                    4. Restart the app
                    """)
                else:
                    st.success(f"✓ {ollama_status}")

                    # Model selection
                    available_models = get_available_models()
                    if available_models:
                        selected_model = st.selectbox(
                            "Select Model",
                            options=available_models,
                            help="Choose the LLM model for report generation"
                        )

                        # Generate report button
                        if st.button("📝 Generate Report", type="primary"):
                            ticker_dir = APP_CONFIG.data_dir / ticker_upper

                            # Initialize report generator
                            generator = ReportGenerator(
                                data_dir=ticker_dir,
                                ticker=ticker_upper,
                                model_name=selected_model
                            )

                            if generator.available:
                                # Index documents first
                                with st.spinner("Indexing documents..."):
                                    num_chunks = generator.rag.index_all_documents(
                                        progress_callback=lambda msg: st.info(msg)
                                    )

                                # Generate report
                                with st.spinner("Generating report (this may take several minutes)..."):
                                    report = generator.generate_initiating_coverage_report(
                                        progress_callback=lambda msg: st.info(msg)
                                    )

                                if report:
                                    # Save report
                                    report_path = generator.save_report(report)

                                    # Display report
                                    st.success(f"✓ Report generated! ({num_chunks} document chunks indexed)")
                                    st.markdown(report)

                                    # Download button
                                    st.download_button(
                                        "📥 Download Report",
                                        data=report,
                                        file_name=f"{ticker_upper}_initiating_coverage.md",
                                        mime="text/markdown"
                                    )
                                else:
                                    st.error("Failed to generate report")
                            else:
                                st.error("Report generator not available. Check dependencies.")

                        # Show existing report if available
                        existing_report = ticker_dir / f"{ticker_upper}_initiating_coverage_report.md"
                        if existing_report.exists():
                            st.divider()
                            st.subheader("📄 Previously Generated Report")
                            with open(existing_report, 'r') as f:
                                existing_content = f.read()
                            with st.expander("View Report", expanded=False):
                                st.markdown(existing_content)
                    else:
                        st.warning("No models available. Download a model first:")
                        st.code("ollama pull llama3.1:8b", language="bash")

            except ImportError as e:
                st.error("LLM dependencies not installed")
                st.info("Install with: `pip install ollama chromadb sentence-transformers langchain`")

        # Tab 7: Chat Q&A
        with tabs[6]:
            st.subheader("💬 Chat with Your Documents")

            # Cloud deployment notice
            st.info("""
            **💡 Local Feature Only**
            AI features require Ollama running on your local machine. They are **not available on Streamlit Cloud**
            due to resource limitations. To use AI features, run this app locally and install Ollama.
            """)

            try:
                from src.llm import (
                    check_ollama_installation,
                    get_available_models,
                    ChatInterface
                )

                ollama_available, ollama_status = check_ollama_installation()

                if not ollama_available:
                    st.warning("⚠️ Ollama not available")
                    st.info(ollama_status)
                    st.markdown("""
                    **To use chat features:**
                    1. Install Ollama: [https://ollama.ai](https://ollama.ai)
                    2. Install Python package: `pip install ollama`
                    3. Download a model: `ollama pull llama3.1:8b`
                    4. Restart the app
                    """)
                else:
                    st.success(f"✓ {ollama_status}")

                    # Model selection
                    available_models = get_available_models()
                    if available_models:
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            selected_model = st.selectbox(
                                "Model",
                                options=available_models,
                                help="Choose the LLM model for chat",
                                key="chat_model"
                            )
                        with col2:
                            if st.button("🔄 Clear History"):
                                if 'chat_interface' in st.session_state:
                                    st.session_state.chat_interface.clear_history()
                                    st.success("History cleared!")

                        # Initialize chat interface
                        ticker_dir = APP_CONFIG.data_dir / ticker_upper

                        if 'chat_interface' not in st.session_state:
                            chat = ChatInterface(
                                data_dir=ticker_dir,
                                ticker=ticker_upper,
                                model_name=selected_model
                            )

                            if chat.available:
                                # Index documents
                                with st.spinner("Indexing documents for chat..."):
                                    chat.rag.index_all_documents()
                                st.session_state.chat_interface = chat
                                st.session_state.chat_messages = []
                            else:
                                st.error("Chat system not available")

                        # Chat interface
                        if 'chat_interface' in st.session_state:
                            chat = st.session_state.chat_interface

                            # Display chat history
                            for msg in st.session_state.get('chat_messages', []):
                                with st.chat_message(msg['role']):
                                    st.write(msg['content'])
                                    if msg.get('sources'):
                                        with st.expander("📚 Sources"):
                                            for source in msg['sources'][:3]:
                                                st.caption(f"**{source['metadata'].get('source', 'unknown')}**")
                                                st.text(source['text'][:200] + "...")

                            # Chat input
                            if prompt := st.chat_input("Ask a question about the company..."):
                                # Add user message
                                st.session_state.chat_messages.append({
                                    'role': 'user',
                                    'content': prompt
                                })

                                with st.chat_message("user"):
                                    st.write(prompt)

                                # Get response
                                with st.chat_message("assistant"):
                                    with st.spinner("Thinking..."):
                                        answer, sources = chat.ask(prompt)

                                    st.write(answer)

                                    if sources:
                                        with st.expander("📚 Sources"):
                                            for source in sources[:3]:
                                                st.caption(f"**{source['metadata'].get('source', 'unknown')}**")
                                                st.text(source['text'][:200] + "...")

                                # Add assistant message
                                st.session_state.chat_messages.append({
                                    'role': 'assistant',
                                    'content': answer,
                                    'sources': sources
                                })

                            # Export conversation
                            if len(st.session_state.get('chat_messages', [])) > 0:
                                if st.button("📥 Export Conversation"):
                                    export_path = ticker_dir / f"{ticker_upper}_chat_conversation.md"
                                    chat.export_conversation(export_path)
                                    st.success(f"Conversation exported to {export_path}")

                    else:
                        st.warning("No models available. Download a model first:")
                        st.code("ollama pull llama3.1:8b", language="bash")

            except ImportError:
                st.error("LLM dependencies not installed")
                st.info("Install with: `pip install ollama chromadb sentence-transformers langchain`")


if __name__ == "__main__":
    main()
