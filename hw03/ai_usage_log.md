# The three prompts you sent to Claude Cowork (Specification A, Specification B, and the timeline prompt)

## Specification A Prompt:

Look at specification A in my hw03 folder: 

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
Save the generated script as `hw03/hw03_earnings.py`.

## Specification B Prompt:


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


Save the generated script as `hw03/hw03_executives.py`.


Before running, confirm the script handles two edge cases:
- A company with **zero** Item 5.02 filings in the past 12 months (prints the no-events message, does not crash)
- A single filing that reports **both** a departure and an appointment (produces two rows in the output CSV)


## Timeline Prompt:

Generate a third script, `hw03/hw03_timeline.py`, that does the following: 
> *"Write a Python script that reads `hw03/earnings_history.csv` and `hw03/executive_events.csv`. Do the following:*
>
> *1. For each executive event in the events table, calculate the number of days between the executive event's `filing_date` and the nearest earnings filing date for the same company in the earnings table. Call this `days_to_nearest_earnings`.*
> *2. Add a column `event_timing` that categorizes each executive event as: `'before earnings'` if the event came before the nearest earnings filing, `'after earnings'` if it came after, or `'same week'` if within 7 days of an earnings filing.*
> *3. Save the combined table to `hw03/corporate_events_timeline.csv` with all columns from both source tables plus `days_to_nearest_earnings` and `event_timing`.*
> *4. Print a summary: for each company, list any executive events and whether they occurred before or after the nearest earnings announcement.*
> *5. Print a final count: how many events occurred before vs. after an earnings announcement across all five companies."*


# Which companies' extractions required iteration (follow-up regex fixes)

Nvidia, Walmart and Microsoft extractions were highlighted from working with Claude.

Claudes explanation:

1. "Worldwide Field" (NVDA):
I checked the filing: the person retiring is Ajay K. Puri, EVP of Worldwide Field Operations. The script took part of his job title ("Worldwide Field") for a name. The row is labelled as a departure, which is correct, but a real person is missing and a fake one appears in its place. If someone checked this row against the filing, it would fail.

2. Duplicates: "Di Sibio" (MSFT), "Nora Johnson" (NVDA) and "Mr. John" (WMT) are real problems.
Each is the same person counted twice:

Carmine Di Sibio also appears as "Di Sibio" (the filing refers to him as "Mr. Di Sibio").
Suzanne Nora Johnson also appears as "Nora Johnson".
John R. Furner also appears as "Mr. John".


Based on this output the problems were identified and corrected.


# One thing the generated script did that you would not have thought to specify, and whether it was correct or needed adjustment

Some companies had an item 5.02 filing in the past 12 months that was not a departure or an appointment. Specification B did not say how to handle this. The script kept these filings and marked them NOT_FOUND, like Specification A, rather than dropping them. The script found 3 NOT_FOUND rows, which was correct as they were only compensation filings, where no one had joined or left. No adjustment was needed.

