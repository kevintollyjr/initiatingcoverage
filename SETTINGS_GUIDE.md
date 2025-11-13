# Settings Guide

Complete reference for all configuration options in the Equity Research Application.

## 📅 Historical Data Range

**Years of History**: 1-20 years (default: 10)
- Extended from the original 10-year maximum
- Ideal for mature companies with long operating histories
- Note: Older data may be less available from some sources

## 📁 Base Layer Settings

Control SEC filings and investor relations materials.

### SEC Filing Types

Toggle individual filing types:

| Setting | Description | Typical Count (10yr) |
|---------|-------------|---------------------|
| **10-K** | Annual reports | 10 filings |
| **10-Q** | Quarterly reports | 30-40 filings |
| **DEF 14A** | Proxy statements | 10 filings |
| **8-K** | Current events | 20-50 filings |

**Use Cases:**
- **Annual only**: Enable just 10-K for high-level analysis
- **No 8-Ks**: Disable 8-K to reduce noise from minor events
- **Governance focus**: Enable only DEF 14A for proxy analysis

### Investor Relations

| Setting | Description |
|---------|-------------|
| **IR Presentations** | Earnings decks, investor days, conference presentations |
| **Earnings Transcripts** | Call transcripts (if available) |

**Note**: Requires company website URL to be provided.

## 📈 Market Layer Settings

Control market data, estimates, and news collection.

### Market Data

| Setting | Description |
|---------|-------------|
| **Price History** | Daily OHLCV data, derived metrics (volatility, returns) |
| **Fundamentals** | Company info, financial statements, ratios |

### Estimates & Ratings

| Setting | Description | Data Source |
|---------|-------------|------------|
| **Earnings Estimates** | EPS actuals vs. estimates, surprises | yfinance, Alpha Vantage |
| **Analyst Ratings** | Buy/Hold/Sell ratings, price targets | API-dependent |

**Note**: Better coverage with Alpha Vantage API key.

### News

| Setting | Description |
|---------|-------------|
| **Press Releases** | Official company announcements from IR website |
| **External News** | Third-party news articles about the company |

## 🌐 Extra Layer Settings

Control website crawling and management profile extraction.

### Website Analysis

| Setting | Description |
|---------|-------------|
| **Business Segments** | Extract product lines, services, industries |
| **Management Profiles** | Extract executive and board member bios |

### Crawl Parameters

**Max Pages to Crawl**: 10-500 pages (default: 100)
- Lower values (10-50): Quick scans, major sections only
- Medium values (100-200): Balanced coverage
- Higher values (300-500): Comprehensive crawls

**Crawl Depth**: 1-5 levels (default: 2)
- Depth 1: Homepage and direct links only
- Depth 2: Two clicks from homepage (recommended)
- Depth 3-5: Deep exploration (slower, more data)

**Performance Impact:**
- 100 pages, depth 2: ~5-10 minutes
- 500 pages, depth 5: ~30-60 minutes

## 🎯 Common Configuration Presets

### Quick Scan (Fast, Essential Data Only)

```
Years: 3
Base Layer:
  ✅ 10-K only
  ❌ 10-Q, DEF 14A, 8-K
  ❌ IR Presentations
  ❌ Transcripts
Market Layer:
  ✅ Price History
  ✅ Fundamentals
  ❌ All others
Extra Layer:
  ❌ Disabled
```
**Time**: ~5-10 minutes

### Standard Analysis (Balanced)

```
Years: 10
Base Layer:
  ✅ 10-K, 10-Q, DEF 14A
  ❌ 8-K
  ✅ IR Presentations
  ❌ Transcripts
Market Layer:
  ✅ All enabled
Extra Layer:
  ❌ Disabled
```
**Time**: ~15-20 minutes

### Deep Research (Comprehensive)

```
Years: 20
Base Layer:
  ✅ All enabled
Market Layer:
  ✅ All enabled
Extra Layer:
  ✅ All enabled
  Max Pages: 200
  Depth: 3
```
**Time**: ~45-90 minutes

### Governance Focus

```
Years: 5
Base Layer:
  ❌ 10-K, 10-Q, 8-K
  ✅ DEF 14A only
  ❌ IR materials
Market Layer:
  ❌ Disabled
Extra Layer:
  ✅ Management Profiles only
  ❌ Website Segments
```
**Time**: ~5 minutes

### Market Data Only

```
Years: 10
Base Layer:
  ❌ Disabled
Market Layer:
  ✅ Price History
  ✅ Fundamentals
  ✅ Earnings Estimates
  ✅ External News
  ❌ Press Releases
Extra Layer:
  ❌ Disabled
```
**Time**: ~2-3 minutes

## 💡 Tips & Best Practices

### For Initial Testing
1. Start with 1-2 years
2. Enable only Base Layer → 10-K
3. Verify everything works
4. Gradually expand scope

### For Production Use
1. **Know your goal**: Different analyses need different data
2. **API keys matter**: Add Alpha Vantage for better earnings data
3. **Website crawls are slow**: Only enable Extra Layer when needed
4. **Storage adds up**: 20 years of data can be several GB per ticker

### Performance Optimization
1. **Disable 8-K**: Often the most numerous and least useful
2. **Skip transcripts**: Often unavailable or paywalled anyway
3. **Limit crawl depth**: Depth 1-2 captures most relevant content
4. **Use presets**: Save time with the common configurations above

### When to Use 20 Years
- **Historical analysis**: Long-term trends, cycles
- **Mature companies**: Established firms with consistent filings
- **Academic research**: Comprehensive datasets
- **Comparative studies**: Multiple companies over time

### When NOT to Use 20 Years
- **New companies**: IPOs, SPACs (data won't exist)
- **Quick checks**: Use 1-3 years for initial assessment
- **Storage constrained**: 20 years = ~10x more data
- **Time sensitive**: Longer periods = longer processing

## 🔧 Advanced Customization

### Combining Settings for Specific Workflows

**M&A Due Diligence:**
- 10-K, 10-Q, DEF 14A (5 years)
- All market data
- Management profiles
- Website segments

**Valuation Model Building:**
- 10-K, 10-Q (10 years)
- Price history + fundamentals
- Earnings estimates
- Skip everything else

**Competitive Intelligence:**
- IR presentations (3 years)
- Press releases
- External news
- Website segments (500 pages, depth 3)

**ESG/Governance Analysis:**
- DEF 14A only (10 years)
- Management profiles
- Press releases
- Skip all market data

## ⚠️ Important Notes

1. **SEC Rate Limits**: Always respected, regardless of settings
2. **Robots.txt**: Always honored for website crawling
3. **API Limits**: Free tiers have daily caps
4. **Storage**: More settings = more disk space needed
5. **Time**: More data = longer processing time

## 🆘 Troubleshooting

**"No filings collected"**
→ Check that at least one filing type is enabled

**"IR materials skipped"**
→ Ensure website URL is provided

**"Crawl seems slow"**
→ Reduce max pages or depth

**"Missing data"**
→ Company may not have data for full lookback period

---

**Pro Tip**: Start narrow and expand as needed. It's easier to collect more data later than to process unnecessary data upfront!
