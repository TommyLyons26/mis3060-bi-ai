# HW03 Specifications

Specification A and Specification B are two separate specifications for two separate scripts. Do not combine them.

## Specification A — Earnings Pipeline (Item 2.02)

Write the script `hw03/hw03_earnings.py` for these five companies:

| Company | Ticker | SEC CIK |
|---|---|---|
| Apple Inc. | AAPL | 0000320193 |
| Microsoft Corporation | MSFT | 0000789019 |
| NVIDIA Corporation | NVDA | 0001045810 |
| JPMorgan Chase & Co. | JPM | 0000019617 |
| Walmart Inc. | WMT | 0000104169 |

The script must:

1. Set the SEC EDGAR `User-Agent` header to `"MIS3060 Villanova tlyons01@villanova.edu"` on all HTTP requests.
2. For each of the five companies, query the EDGAR submissions API at `https://data.sec.gov/submissions/CIK{cik}.json` and filter for 8-K filings where the `items` field contains `"2.02"` (Results of Operations).
3. Select the most recent **four** such filings per company (one per quarter).
4. For each filing, construct the filing index URL, identify the earnings press release exhibit (`.htm` file), download it, and strip HTML to plain text.
5. Extract from the plain text: quarterly revenue (as a number in millions or billions), diluted EPS, net income, and the reporting period (e.g., "fourth quarter fiscal 2024").
6. Print the extracted row for each filing as it is processed, in the format: `[Ticker] | [Period] | Revenue: $X | EPS: $X | Net Income: $X`
7. Save all rows to `hw03/earnings_history.csv` with columns: `company`, `ticker`, `cik`, `filing_date`, `period`, `revenue_reported`, `eps_diluted`, `net_income`
8. Where a field cannot be extracted (regex returns no match), store the string `"NOT_FOUND"` rather than leaving the cell blank — blank cells and missing data are two different things.

---

## Specification B — Executive Events Pipeline (Item 5.02)

Write the script `hw03/hw03_executives.py` for these five companies:

| Company | Ticker | SEC CIK |
|---|---|---|
| Apple Inc. | AAPL | 0000320193 |
| Microsoft Corporation | MSFT | 0000789019 |
| NVIDIA Corporation | NVDA | 0001045810 |
| JPMorgan Chase & Co. | JPM | 0000019617 |
| Walmart Inc. | WMT | 0000104169 |

The script must:

1. Set the SEC EDGAR `User-Agent` header to `"MIS3060 Villanova tlyons01@villanova.edu"` on all HTTP requests.
2. For each of the five companies, query the EDGAR submissions API at `https://data.sec.gov/submissions/CIK{cik}.json` and filter for 8-K filings where the `items` field contains `"5.02"` (Departure of Directors or Officers) and the `filingDate` is within the past 12 months.
3. For each matching filing, download the full 8-K text, strip HTML, and extract: event type (`"departure"` or `"appointment"` or `"both"`), the person's full name, their title, and the effective date of the change.
4. If a filing reports multiple events (e.g., one departure and one appointment), create a separate row for each event.
5. Print each extracted event as it is processed: `[Ticker] | [Date] | [Event Type] | [Name] | [Title]`
6. If no Item 5.02 filings are found for a company in the past 12 months, print `[Ticker]: No executive events in past 12 months` — this is valid data, not an error.
7. Save all events to `hw03/executive_events.csv` with columns: `company`, `ticker`, `cik`, `filing_date`, `event_type`, `person_name`, `title`, `effective_date`
