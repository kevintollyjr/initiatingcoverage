# Transcript Fetching System

Robust, multi-source transcript fetcher with EdmundSEC primary + Google fallback.

## Features

- **EdmundSEC Integration**: Authenticated access to bulk transcript downloads
- **Google Fallback**: Automatic fallback when EdmundSEC doesn't have high-confidence results
- **Comprehensive Scoring**:
  - Transcript shape (0-1): Does it look like a real call transcript?
  - Date match (0-1): How close to the event date?
  - Company match (0-1): Ticker/company name present?
  - Overall confidence: Weighted combination
- **Robust Error Handling**: Never crashes, always returns structured results
- **Detailed Diagnostics**: Full logs of what was tried and why

## Installation

```bash
pip install requests beautifulsoup4 pdfplumber
```

## Configuration

Set EdmundSEC credentials in environment variables:

```bash
export EDMUNDSEC_USERNAME="your_username"
export EDMUNDSEC_PASSWORD="your_password"
```

## Usage

### Basic Example

```python
from transcripts import get_transcript, TranscriptQuery
from datetime import date

query = TranscriptQuery(
    ticker="FI",
    company_name="Fiserv, Inc.",
    event_date=date(2025, 11, 12),
    event_hint="KBW Fintech Payments Conference",
    event_type="conference",
)

result = get_transcript(query)

if result.success:
    print("Success!")
    print(f"Provider: {result.best_candidate.provider}")
    print(f"Confidence: {result.best_candidate.overall_confidence:.2f}")
    print(f"URL: {result.best_candidate.source_url}")
    print(f"Text length: {len(result.best_candidate.text)} chars")
    print("\nTranscript preview:")
    print(result.best_candidate.text[:500])
else:
    print(f"Failed: {result.error}")
    print("\nLogs:")
    for log in result.logs:
        print(f"  - {log}")
```

### Detailed Diagnostics

```python
# Access all candidates considered
for i, candidate in enumerate(result.all_candidates, 1):
    print(f"\nCandidate {i}:")
    print(f"  Provider: {candidate.provider}")
    print(f"  URL: {candidate.source_url}")
    print(f"  Confidence: {candidate.overall_confidence:.2f}")
    print(f"  Shape: {candidate.score_transcript_shape:.2f}")
    print(f"  Date: {candidate.score_date_match:.2f}")
    print(f"  Company: {candidate.score_company_match:.2f}")
    print(f"  Notes:")
    for note in candidate.notes:
        print(f"    - {note}")
```

## Scoring Metrics

### Transcript Shape Score (Weight: 0.5)

Checks if text looks like a real earnings call transcript:

- +0.3 if contains "Operator"
- +0.2 if contains Q&A section markers
- +0.2 if contains forward-looking statement warnings
- +0.2 if substantial length (>5000 chars)
- +0.1 if multiple speaker labels (CEO:, CFO:, etc.)

### Date Match Score (Weight: 0.25)

How close the transcript date is to the event date:

- 1.0: Exact match (same day)
- 0.8: Within 1 day
- 0.5: Within 3 days
- 0.2: Within 1 week
- 0.0: More than 1 week off

### Company Match Score (Weight: 0.25)

How well ticker/company name match:

- +0.4 if ticker found in header (NYSE: TICK)
- +0.3 if company name found in header
- +0.2 if parsed ticker matches
- +0.1 if parsed company name matches

### Overall Confidence

```
overall = 0.5 * shape + 0.25 * date + 0.25 * company
```

### Thresholds

- **EdmundSEC high-confidence**: ≥ 0.7
- **Fallback acceptable**: ≥ 0.6
- **Minimum acceptable**: ≥ 0.4

## Architecture

### Data Flow

```
Query → EdmundSEC → Score → High confidence? → Return
   ↓                             ↓ No
   ↓                      Google Fallback
   ↓                             ↓
   ↓                        Score All
   ↓                             ↓
   └────────────────→ Select Best → Return
```

### Modules

- **models.py**: Data structures (TranscriptQuery, TranscriptCandidate, TranscriptResult)
- **edmundsec_client.py**: EdmundSEC authentication, listing, downloading
- **google_fallback.py**: Google search-based fallback
- **scoring.py**: Scoring functions for candidates
- **orchestrator.py**: Main orchestration logic (`get_transcript()`)

## Error Handling

The system is designed to **never crash**:

- All network operations wrapped in try/except
- Errors logged and added to diagnostics
- Always returns structured `TranscriptResult`
- `success=False` with clear error message when no transcript found

## Testing

```bash
cd transcripts
pytest tests/
```

## Customization

### Adjust Scoring Weights

Edit `transcripts/scoring.py`:

```python
WEIGHT_SHAPE = 0.5    # Importance of transcript shape
WEIGHT_DATE = 0.25    # Importance of date match
WEIGHT_COMPANY = 0.25 # Importance of company match
```

### Adjust Confidence Thresholds

Edit `transcripts/orchestrator.py`:

```python
EDMUNDSEC_CONFIDENCE_THRESHOLD = 0.7  # Required confidence from EdmundSEC
FALLBACK_CONFIDENCE_THRESHOLD = 0.6   # Required confidence from Google
MIN_ACCEPTABLE_CONFIDENCE = 0.4       # Minimum to return success
```

## Troubleshooting

### No transcripts found

Check the logs in `result.logs` to see what was tried:

```python
if not result.success:
    print("Troubleshooting info:")
    for log in result.logs:
        print(log)
```

### Low confidence scores

Inspect individual score components:

```python
candidate = result.best_candidate
print(f"Shape: {candidate.score_transcript_shape:.2f}")
print(f"Date: {candidate.score_date_match:.2f}")
print(f"Company: {candidate.score_company_match:.2f}")

print("\nDetailed notes:")
for note in candidate.notes:
    print(note)
```

### EdmundSEC authentication issues

1. Verify credentials are set:
   ```bash
   echo $EDMUNDSEC_USERNAME
   echo $EDMUNDSEC_PASSWORD
   ```

2. Check logs for specific error:
   ```python
   result = get_transcript(query)
   auth_logs = [log for log in result.logs if 'EdmundSEC' in log]
   for log in auth_logs:
       print(log)
   ```

## License

Proprietary - Internal use only.
