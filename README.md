# 📊 Deep Fundamental Equity Research Application

A comprehensive Streamlit-based application for aggregating equity research data to support initiating coverage reports. This tool automates the collection of SEC filings, investor relations materials, market data, analyst estimates, news, and company information.

## 🎯 Overview

This application helps analysts quickly gather and organize relevant company information into a structured folder hierarchy, making it easy to write initiating coverage reports. All data is downloaded locally and can be exported as a ZIP bundle.

### Key Features

- **Modular Data Layers**: Three independent layers (Base, Market Context, Extra Data) that can be toggled on/off
- **Granular Controls**: 20+ individual settings for fine-tuned data collection (see [SETTINGS_GUIDE.md](SETTINGS_GUIDE.md))
- **Extended History**: Up to 20 years of historical data (previously 10 years)
- **SEC Filings**: Automated download of 10-K, 10-Q, DEF 14A, and 8-K filings (individually selectable)
- **IR Materials**: Investor relations presentations and transcripts
- **Market Data**: Price history, fundamentals, and derived metrics
- **Analyst Estimates**: Earnings estimates, surprises, and consensus data
- **News Aggregation**: Press releases and external news articles
- **Website Intelligence**: Business segments, products, and management profiles (configurable crawl depth and page limits)
- **ZIP Download**: One-click export of all collected data
- **Compliance First**: Respects robots.txt, rate limits, and site terms of service
- **🤖 AI Report Generation**: Automated initiating coverage reports using local LLMs (new!)
- **💬 Interactive Chat Q&A**: Ask questions about collected documents with RAG-powered responses (new!)

### New AI Features

This application now includes powerful local AI capabilities powered by Ollama:

- **Automated Report Generation**: Generate comprehensive initiating coverage reports with executive summary, business analysis, financials, investment thesis, and risks
- **Interactive Document Q&A**: Chat interface to ask questions about any collected document with source citations
- **100% Local & Private**: All AI processing runs on your machine - no data sent to external APIs
- **Multiple Model Support**: Choose from various open-source LLMs (Llama, Mistral, Phi-3, etc.)

For detailed AI feature documentation, see [LLM_FEATURES.md](LLM_FEATURES.md)

## 📋 Prerequisites

- Python 3.11 or higher
- Internet connection for data retrieval
- Valid email address for SEC EDGAR access (required by SEC)

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd initiatingcoverage
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Optional: PDF Conversion (Local Only)

By default, SEC filings are saved as HTML/TXT files. For PDF conversion:

**Linux/Ubuntu:**
```bash
sudo apt-get install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0
pip install -r requirements-local.txt
```

**macOS:**
```bash
brew install pango gdk-pixbuf libffi
pip install -r requirements-local.txt
```

**Windows:** See [WeasyPrint installation guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows)

**Note:** PDF conversion is not available on Streamlit Cloud due to missing system libraries. The app works perfectly fine without it - filings are simply saved in their original HTML/TXT format which is actually better for text extraction and analysis.

## ⚙️ Configuration

### Required Configuration

Before running the application, you **must** provide:

1. **SEC User Agent**: Your name and email address (SEC requirement)
   - Format: `"YourName your.email@example.com"`
   - This is entered in the Streamlit sidebar

### Optional API Keys

For enhanced data collection, you can obtain free API keys from:

1. **Alpha Vantage** (for market data and earnings)
   - Get free key at: https://www.alphavantage.co/support/#api-key
   - 5 API calls per minute, 500 per day (free tier)

2. **Financial Modeling Prep** (for additional fundamentals)
   - Get free key at: https://financialmodelingprep.com/developer/docs/
   - 250 API calls per day (free tier)

API keys can be entered in the Streamlit sidebar or configured via environment variables:

```bash
export ALPHA_VANTAGE_KEY="your_key_here"
export FMP_KEY="your_key_here"
```

## 🎮 Usage

### Start the Application

```bash
streamlit run app.py
```

The application will open in your default web browser at `http://localhost:8501`

### Using the Application

#### 1. Configure Your Research Job

In the sidebar, enter:

- **Ticker Symbol** (required): e.g., `AAPL`, `MSFT`, `KLAC`
- **CIK** (optional): SEC Central Index Key
- **Company Website**: For IR materials and website crawling
- **Years of History**: 1-20 years (default: 10)

#### 2. Select Data Layers & Granular Settings

Toggle which data layers to collect:

- ✅ **Base Layer**: SEC filings, IR presentations, transcripts
  - Click **"⚙️ Base Layer Settings"** to select specific filing types (10-K, 10-Q, DEF 14A, 8-K)
  - Toggle IR presentations and transcripts individually

- ✅ **Market Context**: Market data, estimates, news
  - Click **"⚙️ Market Layer Settings"** to select specific data types
  - Individually control price history, fundamentals, estimates, ratings, news

- ⬜ **Extra Data**: Website crawl, segments, management
  - Click **"⚙️ Extra Layer Settings"** to configure crawl parameters
  - Set max pages (10-500) and crawl depth (1-5)
  - Toggle segments and management profiles separately

**💡 See [SETTINGS_GUIDE.md](SETTINGS_GUIDE.md) for detailed configuration options and preset recommendations.**

#### 3. Provide API Keys (Optional)

Enter your API keys in the sidebar if you have them.

#### 4. Set SEC User Agent (Required)

Enter your name and email in the format: `Research your.email@example.com`

#### 5. Run Pipeline

Click **"▶️ Run Pipeline"** to start data collection.

#### 6. Monitor Progress

Watch the progress log to see what data is being collected.

#### 7. Review Results

Browse the collected data in the tabs:

- **📄 SEC Filings**: View all downloaded filings
- **📊 IR Decks & Transcripts**: Browse presentations and call transcripts
- **📈 Market Data**: Interactive price charts and fundamentals
- **📰 News**: Press releases and news articles
- **🌐 Website & Management**: Segments and leadership profiles

#### 8. Download ZIP Bundle

Click **"📥 Download Full ZIP Bundle"** to download all collected data as a ZIP file.

## 📁 Output Structure

Data is organized in the following structure:

```
data/
└── {TICKER}/
    ├── metadata.json                    # Overall metadata and counts
    ├── sec_filings/
    │   ├── filings_index.json          # Index of all filings
    │   ├── 10-K/
    │   │   ├── YYYY-MM-DD_accession_10-K.html
    │   │   └── YYYY-MM-DD_accession_10-K.txt
    │   ├── 10-Q/
    │   ├── DEF_14A/
    │   ├── DEFA14A/
    │   └── 8-K/
    ├── ir/
    │   ├── presentations_index.json
    │   ├── presentations/
    │   │   ├── YYYY-MM-DD_title.pdf
    │   │   └── YYYY-MM-DD_title.txt
    │   └── transcripts/
    ├── transcripts/
    │   └── transcripts_index.json
    ├── estimates/
    │   ├── earnings_estimates.json
    │   └── earnings_calendar.json
    ├── market_data/
    │   ├── price_history.csv
    │   ├── basic_fundamentals.json
    │   ├── derived_metrics.json
    │   ├── income_statement.csv
    │   ├── balance_sheet.csv
    │   └── cashflow.csv
    ├── news/
    │   ├── press_releases.json
    │   └── external_news.json
    └── website/
        ├── segments.json
        ├── management_team.json
        ├── raw_html/
        └── cleaned_text/
```

## 🔧 Technical Architecture

### Layers

1. **Base Layer** (`src/layers/base_layer.py`)
   - SEC filings using `sec-edgar-downloader`
   - IR presentations crawler
   - Earnings transcripts handler

2. **Market Layer** (`src/layers/market_layer.py`)
   - Market data using `yfinance`
   - Analyst estimates (Alpha Vantage integration)
   - News aggregation

3. **Extra Layer** (`src/layers/extra_layer.py`)
   - Website crawler with robots.txt compliance
   - Business segment parser
   - Management team extractor

### Key Libraries

- **Streamlit**: Web interface
- **sec-edgar-downloader**: SEC filings
- **yfinance**: Market data and fundamentals
- **BeautifulSoup4**: HTML parsing
- **pdfplumber / PyMuPDF**: PDF text extraction
- **pandas**: Data manipulation
- **plotly**: Interactive charts

## 🤖 Rate Limits and Compliance

The application is designed to respect all rate limits and terms of service:

### SEC EDGAR
- Maximum 10 requests per second
- Requires user agent with email
- Implements automatic rate limiting

### Website Crawling
- Respects `robots.txt`
- 2-second delay between requests
- Same-domain only
- Limited to 100 pages max

### APIs
- yfinance: Free, no key required
- Alpha Vantage: 5 calls/minute (free tier)
- Respect for all provider rate limits

## ⚠️ Important Notes

### What This App Does NOT Do

- ❌ Scrape paywalled content
- ❌ Access login-protected data
- ❌ Violate any site's terms of service
- ❌ Perform unauthorized data collection

### Data Sources

All data comes from:
- ✅ Public SEC filings
- ✅ Public company IR websites
- ✅ Free market data APIs
- ✅ Public news sources

### Legal Compliance

- Always provide a valid email in your SEC user agent
- Only crawl websites that allow it in their robots.txt
- Respect all rate limits
- Use only for legitimate research purposes

## 🐛 Troubleshooting

### Common Issues

**"Could not read robots.txt"**
- This is a warning, not an error
- The crawler defaults to allowing access if robots.txt is unavailable

**"Error downloading filings"**
- Check your SEC user agent format
- Verify the ticker symbol is valid
- Check internet connection

**"No data available to download"**
- Ensure at least one data layer completed successfully
- Check the progress log for errors
- Verify the ticker exists and has available data

**Rate limit errors**
- Wait a few minutes before retrying
- Check API key validity
- Verify you haven't exceeded free tier limits

## 📈 Performance Tips

1. **Start Small**: Test with 1-2 years first
2. **Layer by Layer**: Enable one layer at a time for testing
3. **Be Patient**: Full 10-year collection can take 10-30 minutes
4. **Check Logs**: Monitor progress log for issues
5. **API Keys**: Provide API keys for better data coverage

## 🔄 Future Enhancements

Potential improvements:

- [ ] Incremental updates (only fetch new data)
- [ ] More sophisticated segment extraction using NLP
- [ ] Support for international companies
- [ ] Additional data providers
- [ ] Automated report generation
- [ ] Database backend for faster queries
- [ ] Concurrent downloads for better performance
- [ ] More robust date extraction
- [ ] Support for more file types (Excel, Word)

## 📝 Contributing

Contributions are welcome! Please ensure:

- Code follows existing patterns
- Respect all compliance requirements
- Add tests for new features
- Update documentation

## 📄 License

This project is for educational and research purposes. Users are responsible for ensuring compliance with all applicable laws, regulations, and terms of service.

## 🆘 Support

For issues, questions, or suggestions:

1. Check the troubleshooting section
2. Review the progress log for specific errors
3. Open an issue on GitHub

## 👏 Acknowledgments

This application leverages excellent open-source libraries:

- `sec-edgar-downloader` for SEC filings
- `yfinance` for market data
- `streamlit` for the web interface
- And many other fantastic Python libraries

---

**Happy Researching! 📊✨**
