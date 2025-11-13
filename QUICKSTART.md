# 🚀 Quick Start Guide

Get up and running with the Equity Research Application in 5 minutes!

## Step 1: Installation

```bash
# Clone the repository
git clone <repository-url>
cd initiatingcoverage

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Start the Application

```bash
# Using the provided script (macOS/Linux)
./run.sh

# Or manually
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## Step 3: Configure Your First Research Job

### In the Streamlit Sidebar:

1. **Enter Ticker**: `AAPL` (or any US equity ticker)
2. **Company Website**: `https://www.apple.com`
3. **Years of History**: `10` (or less for faster testing)
4. **Enable Layers**:
   - ✅ Base Layer (SEC + IR)
   - ✅ Market Context
   - ⬜ Extra Data (optional - can be slow)
5. **SEC User Agent**: `Research your.email@example.com` ⚠️ **REQUIRED**

### Optional but Recommended:

Get a free Alpha Vantage API key for better market data:
- Visit: https://www.alphavantage.co/support/#api-key
- Enter the key in the sidebar under "API Keys"

## Step 4: Run the Pipeline

Click **"▶️ Run Pipeline"** and watch the magic happen!

The progress log will show:
- SEC filings being downloaded
- IR presentations being collected
- Market data being fetched
- News articles being aggregated

⏱️ **Time estimate**: 5-15 minutes for 10 years of data

## Step 5: Explore the Results

Browse the tabs to see collected data:

- **📄 SEC Filings**: All 10-K, 10-Q, DEF 14A, 8-K filings
- **📊 IR Decks**: Investor presentations and transcripts
- **📈 Market Data**: Interactive price charts and fundamentals
- **📰 News**: Press releases and news articles
- **🌐 Website**: Business segments and management profiles (if Extra Data enabled)

## Step 6: Download Your Data

Click **"📥 Download Full ZIP Bundle"** to get all collected data as a ZIP file.

Your data is organized in:
```
data/AAPL/
├── sec_filings/
├── ir/
├── market_data/
├── news/
└── metadata.json
```

## 🎯 What You'll Get

For a typical S&P 500 company with 10 years of history:

- **40-50 SEC filings** (10-Ks, 10-Qs, DEF 14As, 8-Ks)
- **10-20 IR presentations** (earnings decks, investor days)
- **2,500+ days** of price history
- **40+ earnings records** with estimates
- **50+ news articles**
- Text-extracted versions of all PDFs/HTML for easy searching

## 💡 Pro Tips

1. **Start with 2-3 years** to test the setup
2. **Provide API keys** for richer data (all free tier)
3. **Check the progress log** if something seems wrong
4. **Enable Extra Data** only when needed (it's slower)
5. **Be patient** - respect for rate limits means it takes time

## 🆘 Quick Troubleshooting

**"Error downloading filings"**
→ Check SEC user agent format (must include email)

**"No data in ZIP"**
→ Check progress log for errors, verify ticker is valid

**"Rate limit error"**
→ Wait a few minutes, then try again

## 📚 Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check [CONTRIBUTING.md](CONTRIBUTING.md) to add new features
- Try different tickers and compare results

## 🎉 You're Ready!

Start gathering research data and writing those initiating coverage reports! 📊✨

---

**Need help?** Check the README.md or open an issue on GitHub.
