# 5A — Known-Answer Check: Earnings

Look up the officially reported quarterly revenue for **one** company for **one** specific quarter using the company's investor relations website or a financial news source.

| Check | Official Source | Your CSV | Match? |
|---|---|---|---|
| [Apple] [3rd Quarter 2026] Revenue | 109.4 billion | 109.4 billion | Yes |
| [Apple] [3rd Quarter 2026 ] EPS Diluted | 2.02 | 2.02 | Yes |


# 5B — Known-Answer Check: Executive Events

Pick **one** executive event from your `executive_events.csv`. Verify it against a public news source (Google News, LinkedIn, or the company's own press releases).

| Check | News Source Confirms? | Notes |
|---|---|---|
| Person name and title | John Ternus - CEO | Apple Press Release confirms|
| Event type (departure/appointment) | Appointment | Apple Press Release confirms |
| Effective date | 1st September 2026 | Apple Press Release confirms|

# 5C — Cross-Validation: Earnings via Yahoo Finance

For the same company and quarter you checked in 5A, use `yfinance` (from ICE 5.1) to retrieve quarterly revenue and net income as a second independent source:

> *"Write Python using yfinance to get the most recent quarterly revenue and net income for [ticker]."*

| Metric | From 8-K text extraction | From yfinance | Match? |
|---|---|---|---|
| Revenue | 109.4 billion | 109.4 billion | Yes |
| Net Income | 29,789 million | 29,789 million | Yes |

If the two sources disagree, explain the most likely reason (period mismatch, metric definition difference, or extraction error).

# 5D — Pipeline Integrity Checks

Complete this table:

| Check | Expected | Actual | Pass/Fail |
|---|---|---|---|
| `earnings_history.csv` row count | Up to 20 (5 companies × 4 quarters) | 20 | Pass |
| `executive_events.csv` row count | At least 0 (document actual) | 32 | Pass |
| `corporate_events_timeline.csv` created | Yes | Yes | Pass |
| Rows with all three fields `"NOT_FOUND"` | 0 (investigate if > 0) | 3 | Fail |

In executive_events_csv there were 3 rows who do have event_type, name, and title all set to NOT_FOUND. After investigating with Claude, it was discovered each row is a "compensation-only Item 5.02 filing", whereby no one departed or were appointed. 