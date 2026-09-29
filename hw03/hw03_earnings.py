"""
Script:      hw03_earnings.py
Source:      SEC EDGAR (submissions API + 8-K Item 2.02 filings)
Author:      Tommy Lyons
Generated:   2026-09-27

Earnings pipeline (Specification A). For five large-cap companies, pulls the
four most recent 8-K filings that report Item 2.02 (Results of Operations),
finds the earnings press release exhibit in each filing, strips it to plain
text, and extracts quarterly revenue, diluted EPS, net income and the
reporting period. Results are printed as they are processed and saved to
hw03/earnings_history.csv. Fields that cannot be extracted are stored as
"NOT_FOUND" (never left blank).

Run from the repo root:   python hw03/hw03_earnings.py
"""

import csv
import os
import re
import time

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
USER_AGENT = "MIS3060 Villanova tlyons01@villanova.edu"
HEADERS = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}

COMPANIES = [
    {"company": "Apple Inc.", "ticker": "AAPL", "cik": "0000320193"},
    {"company": "Microsoft Corporation", "ticker": "MSFT", "cik": "0000789019"},
    {"company": "NVIDIA Corporation", "ticker": "NVDA", "cik": "0001045810"},
    {"company": "JPMorgan Chase & Co.", "ticker": "JPM", "cik": "0000019617"},
    {"company": "Walmart Inc.", "ticker": "WMT", "cik": "0000104169"},
]

FILINGS_PER_COMPANY = 4
NOT_FOUND = "NOT_FOUND"
REQUEST_PAUSE = 0.2  # SEC allows max 10 requests/second; stay well under it

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "earnings_history.csv")
CSV_COLUMNS = ["company", "ticker", "cik", "filing_date", "period",
               "revenue_reported", "eps_diluted", "net_income"]

# One shared session so the User-Agent header is sent on EVERY request
session = requests.Session()
session.headers.update(HEADERS)


def get(url):
    """GET a URL with the SEC User-Agent, pausing to respect rate limits."""
    time.sleep(REQUEST_PAUSE)
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response


# ---------------------------------------------------------------------------
# Step 2-3: find the four most recent Item 2.02 8-K filings
# ---------------------------------------------------------------------------
def quarter_key(date_str):
    """'2024-10-31' -> (2024, 4). Used to keep one filing per quarter."""
    year, month = int(date_str[:4]), int(date_str[5:7])
    return (year, (month - 1) // 3 + 1)


def get_earnings_filings(cik):
    """Return the most recent FILINGS_PER_COMPANY 8-K Item 2.02 filings."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    recent = get(url).json()["filings"]["recent"]

    filings, quarters_seen = [], set()
    # The "recent" arrays are parallel lists, newest filing first
    for i, form in enumerate(recent["form"]):
        if form != "8-K" or "2.02" not in recent["items"][i]:
            continue
        # One per quarter: key on the period the filing reports on
        # (reportDate), falling back to the filing date if it is missing
        ref_date = recent["reportDate"][i] or recent["filingDate"][i]
        q = quarter_key(ref_date)
        if q in quarters_seen:
            continue
        quarters_seen.add(q)
        filings.append({
            "accession": recent["accessionNumber"][i],
            "filing_date": recent["filingDate"][i],
            "primary_doc": recent["primaryDocument"][i],
        })
        if len(filings) == FILINGS_PER_COMPANY:
            break
    return filings


# ---------------------------------------------------------------------------
# Step 4: filing index -> press release exhibit -> plain text
# ---------------------------------------------------------------------------
def filing_index_url(cik, accession):
    """Build the EDGAR filing index URL for an accession number."""
    folder = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}"
    return f"{folder}/{accession}-index.htm", folder


def find_press_release_url(cik, filing):
    """Read the filing index and return the URL of the earnings press
    release exhibit (.htm). Prefers EX-99.1, then any other EX-99.x."""
    index_url, folder = filing_index_url(cik, filing["accession"])
    soup = BeautifulSoup(get(index_url).text, "html.parser")

    exhibits = []  # (doc_type, url)
    for row in soup.select("table.tableFile tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        link = cells[2].find("a")
        doc_type = cells[3].get_text(strip=True).upper()
        if not link or not link.get("href", "").lower().endswith((".htm", ".html")):
            continue
        href = link["href"].replace("/ix?doc=", "")  # inline-XBRL viewer links
        exhibits.append((doc_type, "https://www.sec.gov" + href))

    for doc_type, url in exhibits:
        if doc_type == "EX-99.1":
            return url
    for doc_type, url in exhibits:
        if doc_type.startswith("EX-99"):
            return url
    # Last resort: the 8-K body itself
    return f"{folder}/{filing['primary_doc']}"


def html_to_text(html):
    """Strip HTML tags and normalise whitespace to one-line plain text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(" ")
    text = text.replace("\xa0", " ").replace("’", "'")
    text = text.replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Step 5: regex extraction
# ---------------------------------------------------------------------------
MONEY = r"\$\s?([\d,]+(?:\.\d+)?)\s*(billion|million)"
# Up to N characters that do NOT contain a "$" or words that signal we have
# drifted onto a different metric
def gap(n, stop_words):
    return rf"(?:(?!\$|{'|'.join(stop_words)}).){{0,{n}}}?"

REVENUE_PATTERNS = [
    # Sentence form, e.g. "quarterly revenue of $94.9 billion" (AAPL),
    # "Revenue was $65.6 billion" (MSFT), "revenue for the third quarter
    # ended October 27, 2024, of $35.1 billion" (NVDA), "on revenue of
    # $43.3 billion" (JPM), "Consolidated revenue of $169.6 billion" (WMT)
    (rf"\b(?:net )?revenues?\b{gap(100, ['income', 'earnings', 'margin', 'expense'])}{MONEY}", None),
    (rf"\bnet sales\b{gap(80, ['income', 'earnings', 'margin'])}{MONEY}", None),
    # Financial-statement tables (figures are in millions)
    (r"\bTotal net sales\s+\$?\s?([\d,]{4,})", "million"),
    (r"\bTotal net revenues?(?:, managed)?\s+\$?\s?([\d,]{4,})", "million"),
    (r"\bTotal revenues?\s+\$?\s?([\d,]{4,})", "million"),
    (r"\bRevenue\s+\$\s?([\d,]{4,})", "million"),
]

EPS_PATTERNS = [
    r"diluted earnings per share\b[^$]{0,40}?\$\s?(\d+\.\d{2})",      # AAPL, MSFT
    r"earnings per diluted share\b[^$]{0,60}?\$\s?(\d+\.\d{2})",      # NVDA
    r"\bGAAP EPS\b[^$]{0,30}?\$\s?(\d+\.\d{2})",                      # WMT
    r"\bdiluted EPS\b[^$]{0,30}?\$\s?(\d+\.\d{2})",
    r"\$\s?(\d+\.\d{2}) per (?:diluted )?share",                       # JPM
    r"\bDiluted(?: earnings per share)?\s*\$\s?(\d+\.\d{2})",          # tables
]

NET_INCOME_PATTERNS = [
    # "Net income was $24.7 billion" (MSFT), "net income of $12.9 billion" (JPM)
    (rf"(?<!non-)(?<!adjusted )\bnet income\b{gap(60, ['revenue', 'per share', 'margin'])}{MONEY}", None),
    # Tables, in millions: "Net income $ 14,736" (AAPL, NVDA),
    # "Consolidated net income attributable to Walmart $ 4,579" (WMT)
    (r"\bConsolidated net income attributable to Walmart\s+\$?\s?([\d,]{3,})", "million"),
    (r"\bNet income\s+\$\s?([\d,]{3,})", "million"),
]

QUARTER_WORDS = {"1": "first", "2": "second", "3": "third", "4": "fourth"}
ORDINAL = r"(first|second|third|fourth)"


def normalise_year(year):
    return year if len(year) == 4 else "20" + year


def extract_period(text):
    """Return the reporting period, e.g. 'fourth quarter fiscal 2024'.
    All year-bearing patterns are tried; the earliest match in the
    document (usually the headline/opening line) wins."""
    candidates = []  # (position, period string)

    # "third quarter of fiscal 2025" / "third-quarter 2024" / "third quarter fiscal year 2025"
    for m in re.finditer(rf"\b{ORDINAL}[\s-]quarter(?: of)?( fiscal(?: year)?)? (\d{{4}})\b", text, re.I):
        fiscal = " fiscal" if m.group(2) else ""
        candidates.append((m.start(), f"{m.group(1).lower()} quarter{fiscal} {m.group(3)}"))
    # "fiscal 2024 fourth quarter" (AAPL)
    for m in re.finditer(rf"\bfiscal(?: year)? (\d{{4}}) {ORDINAL} quarter\b", text, re.I):
        candidates.append((m.start(), f"{m.group(2).lower()} quarter fiscal {m.group(1)}"))
    # "Q3 FY25" (WMT) / "FY25 Q1"
    for m in re.finditer(r"\bQ([1-4])\s?(?:FY|fiscal )\s?'?(\d{2,4})\b", text, re.I):
        candidates.append((m.start(), f"{QUARTER_WORDS[m.group(1)]} quarter fiscal {normalise_year(m.group(2))}"))
    for m in re.finditer(r"\bFY\s?'?(\d{2,4}) Q([1-4])\b", text, re.I):
        candidates.append((m.start(), f"{QUARTER_WORDS[m.group(2)]} quarter fiscal {normalise_year(m.group(1))}"))
    # "4Q24" / "3Q 2024" (JPM shorthand)
    for m in re.finditer(r"\b([1-4])Q\s?(\d{2}|\d{4})\b", text):
        candidates.append((m.start(), f"{QUARTER_WORDS[m.group(1)]} quarter {normalise_year(m.group(2))}"))

    if candidates:
        return min(candidates)[1]

    # Fallback (e.g. MSFT): "first quarter results ... quarter ended September 30, 2024"
    ended = re.search(r"\bquarter ended ([A-Z][a-z]+ \d{1,2}, \d{4})", text)
    ordinal = re.search(rf"\b{ORDINAL}[\s-]quarter\b", text, re.I)
    if ordinal and ended:
        return f"{ordinal.group(1).lower()} quarter (ended {ended.group(1)})"
    if ended:
        return f"quarter ended {ended.group(1)}"
    return NOT_FOUND


def extract_money(text, patterns):
    """Try each (pattern, default_unit) in order; return e.g. '94.9 billion'."""
    for pattern, default_unit in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            amount = m.group(1).rstrip(".,")
            unit = default_unit or m.group(2).lower()
            return f"{amount} {unit}"
    return NOT_FOUND


def extract_eps(text):
    for pattern in EPS_PATTERNS:
        m = re.search(pattern, text, re.I)
        if m:
            return m.group(1)
    return NOT_FOUND


def extract_fields(text):
    return {
        "period": extract_period(text),
        "revenue_reported": extract_money(text, REVENUE_PATTERNS),
        "eps_diluted": extract_eps(text),
        "net_income": extract_money(text, NET_INCOME_PATTERNS),
    }


# ---------------------------------------------------------------------------
# Step 6: printing
# ---------------------------------------------------------------------------
def dollars(value):
    return value if value == NOT_FOUND else f"${value}"


def print_row(row):
    print(f"{row['ticker']} | {row['period']} | Revenue: {dollars(row['revenue_reported'])} | "
          f"EPS: {dollars(row['eps_diluted'])} | Net Income: {dollars(row['net_income'])}")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def main():
    rows = []
    for co in COMPANIES:
        try:
            filings = get_earnings_filings(co["cik"])
        except requests.RequestException as err:
            print(f"{co['ticker']}: could not load submissions ({err})")
            continue

        if not filings:
            print(f"{co['ticker']}: no 8-K Item 2.02 filings found")

        for filing in filings:
            fields = {"period": NOT_FOUND, "revenue_reported": NOT_FOUND,
                      "eps_diluted": NOT_FOUND, "net_income": NOT_FOUND}
            try:
                exhibit_url = find_press_release_url(co["cik"], filing)
                text = html_to_text(get(exhibit_url).text)
                fields = extract_fields(text)
            except requests.RequestException as err:
                print(f"{co['ticker']}: failed to download filing "
                      f"{filing['accession']} ({err})")

            row = {
                "company": co["company"],
                "ticker": co["ticker"],
                "cik": co["cik"],
                "filing_date": filing["filing_date"],
                **fields,
            }
            print_row(row)
            rows.append(row)

    # Step 7-8: save (every missing field is already the string NOT_FOUND)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows to {os.path.relpath(OUTPUT_CSV)}")


if __name__ == "__main__":
    main()
