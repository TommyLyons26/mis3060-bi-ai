"""
01_reconcile_measures.py
MIS 3060 HW06 - reconcile Power BI DAX measures against an independent pandas recompute.

Inputs
  Wildcat Capital Clean/*.csv   - the ONLY source for the pandas calculations
  reports/powerbi_values.csv    - Power BI numbers (measure, slice, value), used only for comparison
Output
  reports/measure_reconciliation.csv
    measure, slice, powerbi_value, pandas_value, abs_diff, match

Tolerance: 0.01 for currency, 0.0001 for ratios (and bps); text and counts must match exactly.
Run from anywhere:  python scripts/01_reconcile_measures.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "Wildcat Capital Clean"
PBI_FILE = ROOT / "reports" / "powerbi_values.csv"
OUT_FILE = ROOT / "reports" / "measure_reconciliation.csv"

# ---------------------------------------------------------------- load data (CSV only)
snap = pd.read_csv(DATA / "fact_portfolio_snapshot.csv", parse_dates=["snapshot_date"])
fees = pd.read_csv(DATA / "fact_fees.csv", parse_dates=["fee_date"])
txns = pd.read_csv(DATA / "fact_transactions.csv", parse_dates=["txn_date"])
clients = pd.read_csv(DATA / "dim_client.csv", usecols=["client_id", "client_tier"])

# attach client tier to every fact table (same relationship as dim_client in the model)
snap = snap.merge(clients, on="client_id", how="left")
fees = fees.merge(clients, on="client_id", how="left")
txns = txns.merge(clients, on="client_id", how="left")

CURRENCY = {
    "AUM (naive SUM)", "Ending AUM", "Avg AUM per Client", "Ending AUM LY",
    "Ending AUM PM", "Avg Monthly AUM", "Total Fees", "Net Flows",
}
COUNT = {"Ending Clients"}
TEXT = {"Alpha Signal"}
# everything else is a ratio (YoY %, MoM %, Organic Growth, Alpha, Top 10 Share, Fee Yield bps)


def balance_at(date, tier=None):
    """Total AUM at one snapshot date (optionally for one tier). None if no snapshot exists."""
    rows = snap[snap.snapshot_date == date]
    if tier is not None:
        rows = rows[rows.client_tier == tier]
    return rows.aum.sum() if len(rows) else None


def safe_div(a, b):
    return None if a is None or b is None or b == 0 else a / b


def alpha_signal(alpha):
    if alpha is None:
        return None
    if alpha >= 0.02:
        return "Outperforming"
    if alpha <= -0.02:
        return "Lagging"
    return "In Line"


def measures(start=None, end=None, tier=None):
    """Compute every measure for a filter context: date range [start, end] and optional tier."""
    s, f, t = snap, fees, txns
    if start is not None:
        s = s[(s.snapshot_date >= start) & (s.snapshot_date <= end)]
        f = f[(f.fee_date >= start) & (f.fee_date <= end)]
        t = t[(t.txn_date >= start) & (t.txn_date <= end)]
    if tier is not None:
        s, f, t = s[s.client_tier == tier], f[f.client_tier == tier], t[t.client_tier == tier]

    last_date = s.snapshot_date.max()
    last = s[s.snapshot_date == last_date]
    monthly = s.groupby("snapshot_date").aum.sum()

    ending = last.aum.sum()
    clients_n = last.client_id.nunique()
    ly = balance_at(last_date - pd.DateOffset(years=1), tier)     # balance one year earlier
    pm = balance_at(last_date - pd.DateOffset(months=1), tier)    # balance one month earlier
    avg_monthly = monthly.mean()

    total_fees = f.amount.sum()
    # annualized fees per dollar of average AUM, in basis points (1 bp = 0.0001)
    fee_yield = total_fees / avg_monthly * 12 / len(monthly) * 10_000

    net_flows = (t.loc[t.txn_type == "Deposit", "amount"].sum()
                 - t.loc[t.txn_type == "Withdrawal", "amount"].sum())

    clean = last[last.is_return_suspect != 1]
    alpha = safe_div((clean.active_alpha_ytd * clean.aum).sum(), clean.aum.sum())

    top10 = last.groupby("client_id").aum.sum().nlargest(10).sum()

    return {
        "AUM (naive SUM)": s.aum.sum(),
        "Ending AUM": ending,
        "Ending Clients": clients_n,
        "Avg AUM per Client": safe_div(ending, clients_n),
        "Ending AUM LY": ly,
        "AUM YoY %": safe_div(None if ly is None else ending - ly, ly),
        "Ending AUM PM": pm,
        "AUM MoM %": safe_div(None if pm is None else ending - pm, pm),
        "Avg Monthly AUM": avg_monthly,
        "Fee Yield (bps)": fee_yield,
        "Organic Growth Rate": safe_div(net_flows, ly),
        "AUM-Weighted Alpha": alpha,
        "Alpha Signal": alpha_signal(alpha),
        "Top 10 Client Share": safe_div(top10, ending),
        "Total Fees": total_fees,
        "Net Flows": net_flows,
    }


# ---------------------------------------------------------------- required coverage
ALL = list(measures().keys())
YEAR_MEASURES = ["AUM (naive SUM)", "Ending AUM", "Ending AUM LY", "AUM YoY %", "Avg Monthly AUM",
                 "Fee Yield (bps)", "Organic Growth Rate", "AUM-Weighted Alpha", "Alpha Signal"]
TIER_MEASURES = ["Ending AUM", "Avg AUM per Client", "Ending AUM LY", "AUM YoY %", "Fee Yield (bps)",
                 "Organic Growth Rate", "AUM-Weighted Alpha", "Alpha Signal", "Top 10 Client Share"]
MONTH_MEASURES = ["Ending AUM", "Ending AUM PM", "AUM MoM %"]

pandas_rows = []
for m, v in measures().items():
    pandas_rows.append((m, "Total", v))
for y in sorted(snap.year.unique()):
    vals = measures(pd.Timestamp(y, 1, 1), pd.Timestamp(y, 12, 31))
    pandas_rows += [(m, f"Year={y}", vals[m]) for m in YEAR_MEASURES]
for tier in sorted(clients.client_tier.dropna().unique()):
    vals = measures(pd.Timestamp(2024, 1, 1), pd.Timestamp(2024, 12, 31), tier)
    pandas_rows += [(m, f"Tier={tier} | Year=2024", vals[m]) for m in TIER_MEASURES]
vals = measures(pd.Timestamp(2024, 12, 1), pd.Timestamp(2024, 12, 31))
pandas_rows += [(m, "Month=2024-12", vals[m]) for m in MONTH_MEASURES]

pd_df = pd.DataFrame(pandas_rows, columns=["measure", "slice", "pandas_value"])
# a blank in pandas (e.g. 2020 has no prior year) corresponds to a blank cell in Power BI
pd_df = pd_df[pd_df.pandas_value.notna()]

# ---------------------------------------------------------------- compare with Power BI
pbi = pd.read_csv(PBI_FILE, dtype=str).rename(columns={"value": "powerbi_value"})
rec = pd_df.merge(pbi, on=["measure", "slice"], how="outer")


def compare(row):
    p, q, m = row.powerbi_value, row.pandas_value, row.measure
    if pd.isna(p) or pd.isna(q):
        return pd.Series({"abs_diff": None, "match": False})
    if m in TEXT:
        return pd.Series({"abs_diff": None, "match": str(p).strip().lower() == str(q).strip().lower()})
    diff = abs(float(p) - float(q))
    tol = 0.01 if m in CURRENCY else 0 if m in COUNT else 0.0001
    return pd.Series({"abs_diff": diff, "match": diff <= tol})


rec[["abs_diff", "match"]] = rec.apply(compare, axis=1)
rec = rec[["measure", "slice", "powerbi_value", "pandas_value", "abs_diff", "match"]]
rec.to_csv(OUT_FILE, index=False)

print(f"{rec.match.sum()} / {len(rec)} rows match  ->  {OUT_FILE.relative_to(ROOT)}")
bad = rec[~rec.match]
if len(bad):
    print("\nMISMATCHES:")
    print(bad.to_string(index=False))
