"""
Script:      hw03_timeline.py
Source:      hw03/earnings_history.csv (Spec A) + hw03/executive_events.csv (Spec B)
Author:      Tommy Lyons
Generated:   2026-09-27

Business question: do executive changes (8-K Item 5.02) tend to be announced
before or after a company's earnings releases (8-K Item 2.02)?

For every executive event, finds the same company's earnings filing whose
filing_date is closest to the event's filing_date, then records:
  - days_to_nearest_earnings : absolute number of days between the two filings
  - event_timing             : 'same week'        if within 7 days (either side)
                               'before earnings'  if the event was filed earlier
                               'after earnings'   if the event was filed later

Output: hw03/corporate_events_timeline.csv — every column from both tables
(the earnings filing date is renamed earnings_filing_date so it does not
clash with the event's filing_date) plus the two new columns.

Rows whose event_type is "NOT_FOUND" (Item 5.02 filings where no person could
be extracted, e.g. compensation-only filings) are kept in the CSV but are not
counted as executive events in the printed summary.

Run from the repo root:   python hw03/hw03_timeline.py
"""

import os

import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EARNINGS_CSV = os.path.join(SCRIPT_DIR, "earnings_history.csv")
EVENTS_CSV = os.path.join(SCRIPT_DIR, "executive_events.csv")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "corporate_events_timeline.csv")

SAME_WEEK_DAYS = 7
NOT_FOUND = "NOT_FOUND"


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
def load_tables():
    # dtype=str keeps CIKs' leading zeros and leaves "NOT_FOUND" untouched
    earnings = pd.read_csv(EARNINGS_CSV, dtype=str, keep_default_na=False)
    events = pd.read_csv(EVENTS_CSV, dtype=str, keep_default_na=False)
    earnings["filing_date"] = pd.to_datetime(earnings["filing_date"])
    events["filing_date"] = pd.to_datetime(events["filing_date"])
    return earnings, events


# ---------------------------------------------------------------------------
# Steps 1-2: nearest earnings filing, days between, timing category
# ---------------------------------------------------------------------------
def nearest_earnings(event_row, earnings):
    """Return the same-company earnings row closest in time to the event.
    On an exact tie the earlier earnings filing is used."""
    same_co = earnings[earnings["ticker"] == event_row["ticker"]]
    if same_co.empty:
        return None
    gaps = (same_co["filing_date"] - event_row["filing_date"]).abs()
    order = pd.DataFrame({"gap": gaps, "date": same_co["filing_date"]}).sort_values(["gap", "date"])
    return same_co.loc[order.index[0]]


def classify(event_date, earnings_date):
    days = abs((event_date - earnings_date).days)
    if days <= SAME_WEEK_DAYS:
        timing = "same week"
    elif event_date < earnings_date:
        timing = "before earnings"
    else:
        timing = "after earnings"
    return days, timing


def build_timeline(earnings, events):
    earnings_cols = [c for c in earnings.columns if c not in ("company", "ticker", "cik")]
    rows = []
    for _, ev in events.iterrows():
        row = ev.to_dict()
        match = nearest_earnings(ev, earnings)
        if match is None:
            row.update({"earnings_filing_date": pd.NaT, "period": NOT_FOUND,
                        "revenue_reported": NOT_FOUND, "eps_diluted": NOT_FOUND,
                        "net_income": NOT_FOUND,
                        "days_to_nearest_earnings": NOT_FOUND, "event_timing": NOT_FOUND})
        else:
            for col in earnings_cols:
                key = "earnings_filing_date" if col == "filing_date" else col
                row[key] = match[col]
            days, timing = classify(ev["filing_date"], match["filing_date"])
            row["days_to_nearest_earnings"] = days
            row["event_timing"] = timing
        rows.append(row)

    columns = (list(events.columns)
               + ["earnings_filing_date"] + [c for c in earnings_cols if c != "filing_date"]
               + ["days_to_nearest_earnings", "event_timing"])
    timeline = pd.DataFrame(rows, columns=columns)
    for col in ("filing_date", "earnings_filing_date"):
        timeline[col] = pd.to_datetime(timeline[col]).dt.strftime("%Y-%m-%d")
    return timeline


# ---------------------------------------------------------------------------
# Steps 4-5: printed summary and final count
# ---------------------------------------------------------------------------
def print_summary(timeline, companies):
    real = timeline[timeline["event_type"] != NOT_FOUND]

    print("=" * 78)
    print("EXECUTIVE EVENTS vs. NEAREST EARNINGS ANNOUNCEMENT")
    print("=" * 78)
    for ticker, company in companies:
        co_events = real[real["ticker"] == ticker]
        print(f"\n{company} ({ticker})")
        if co_events.empty:
            print("  No executive events in past 12 months")
            continue
        for _, r in co_events.iterrows():
            print(f"  {r['filing_date']}  {r['event_type']:<11} {r['person_name']:<22} "
                  f"-> {r['event_timing']:<15} ({r['days_to_nearest_earnings']} days from "
                  f"{r['period']} earnings, filed {r['earnings_filing_date']})")

    counts = real["event_timing"].value_counts()
    before = int(counts.get("before earnings", 0))
    after = int(counts.get("after earnings", 0))
    same_week = int(counts.get("same week", 0))

    print("\n" + "=" * 78)
    print("FINAL COUNT (all five companies)")
    print("=" * 78)
    print(f"  Before earnings announcement : {before}")
    print(f"  After earnings announcement  : {after}")
    print(f"  Same week as earnings (<=7d) : {same_week}")
    print(f"  Total executive events       : {len(real)}")
    skipped = len(timeline) - len(real)
    if skipped:
        print(f"  ({skipped} Item 5.02 filing(s) with no extracted person excluded from counts)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    earnings, events = load_tables()
    timeline = build_timeline(earnings, events)

    # Step 3: save
    timeline.to_csv(OUTPUT_CSV, index=False)

    # Keep company order as it appears in the earnings table
    companies = list(dict.fromkeys(zip(earnings["ticker"], earnings["company"])))
    for pair in zip(events["ticker"], events["company"]):
        if pair not in companies:
            companies.append(pair)
    print_summary(timeline, companies)

    print(f"\nSaved {len(timeline)} rows to {os.path.relpath(OUTPUT_CSV)}")


if __name__ == "__main__":
    main()
