"""
03_validate.py — Validate the Wildcat Capital tables, raw and clean.

Runs the same checks on the raw files (hw04/Wildcat Capital/) and the cleaned
files (hw04/data/clean/), read as text (dtype=str, keep_default_na=False):

  1. Referential integrity  check_referential_integrity() on all 13 relationships
                            (10 ID-based + 3 date joins to dim_date)
  2. Business rules         every column with a natural bound: ranges, allowed
                            code lists, sign rules, conditional blanks
  3. Reconciliations        recomputed values vs stored values, within and across tables
  4. IQR outliers           on numeric columns with no natural bound

Outputs (hw04/reports/)
  data_quality_scorecard.csv    one row per table per stage: % completeness, % key
                                uniqueness, % type validity, % rule pass, % referential match
  validation_details.csv        every individual check behind the scorecard

Usage
  python scripts/03_validate.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

HW_DIR = Path(__file__).resolve().parent.parent
STAGES = {"raw": HW_DIR / "Wildcat Capital", "clean": HW_DIR / "data" / "clean"}
REPORTS = HW_DIR / "reports"

TABLES = ["dim_advisor", "dim_benchmark", "dim_client", "dim_date", "dim_security",
          "fact_fees", "fact_portfolio_snapshot", "fact_transactions"]


# ════════════════════════════════════════════════════════════════════
# 1. Referential integrity — reusable (Assignment 5)
# ════════════════════════════════════════════════════════════════════

def check_referential_integrity(fact_df: pd.DataFrame, fact_key: str,
                                dim_df: pd.DataFrame, dim_key: str) -> dict:
    """
    Check that every value of fact_df[fact_key] exists in dim_df[dim_key].

    Keys are compared exactly as stored (as text, after trimming spaces), the way
    a BI tool would join them, so '45.0' does NOT match '45'. Blank / null keys are
    counted separately and are not treated as orphans.

    Returns a dict:
      rows               rows in fact_df
      null_keys          rows where the key is blank / null
      null_key_rate      null_keys / rows
      checked            rows with a non-null key
      matched            non-null keys found in dim_df[dim_key]
      match_rate         matched / checked  (1.0 when nothing to check)
      orphan_count       non-null keys not found in the dimension
      orphan_rows        DataFrame of those rows
      distinct_orphan_keys  sorted list of the distinct missing key values
    """
    key = fact_df[fact_key].astype("string").str.strip()
    null = key.isna() | (key == "")
    parent = set(dim_df[dim_key].astype("string").str.strip().dropna())
    found = key.isin(parent) & ~null
    orphan = ~null & ~found
    rows, checked = len(fact_df), int((~null).sum())
    return {
        "rows": rows,
        "null_keys": int(null.sum()),
        "null_key_rate": float(null.mean()) if rows else 0.0,
        "checked": checked,
        "matched": int(found.sum()),
        "match_rate": float(found.sum() / checked) if checked else 1.0,
        "orphan_count": int(orphan.sum()),
        "orphan_rows": fact_df[orphan],
        "distinct_orphan_keys": sorted(key[orphan].unique().tolist()),
    }


# (child table, child column, parent table, parent column)
RELATIONSHIPS = [
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id"),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_fees", "client_id", "dim_client", "client_id"),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id"),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_transactions", "client_id", "dim_client", "client_id"),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_transactions", "security_id", "dim_security", "security_id"),
    ("fact_fees", "fee_date", "dim_date", "date"),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date"),
    ("fact_transactions", "txn_date", "dim_date", "date"),
]


# ════════════════════════════════════════════════════════════════════
# Column types, keys and expected blanks (used by the scorecard)
# ════════════════════════════════════════════════════════════════════

PK = {"dim_advisor": "advisor_id", "dim_benchmark": "benchmark_id", "dim_client": "client_id",
      "dim_date": "date_id", "dim_security": "security_id", "fact_fees": "fee_id",
      "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id"}

# Business keys: a second way the same real-world row could be duplicated under a new PK
BUSINESS_KEY = {
    "dim_benchmark": ["ticker_proxy"],
    "dim_client": ["first_name", "age", "city", "zip_code", "initial_aum", "client_since"],
    "dim_date": ["date"],
    "dim_security": ["ticker"],
    "fact_fees": ["client_id", "fee_date"],
    "fact_portfolio_snapshot": ["client_id", "snapshot_date"],
    "fact_transactions": ["advisor_id", "security_id", "txn_date", "txn_type", "shares", "price", "amount"],
}

INT, DEC, DATE, BOOL, FLAG = "integer", "decimal", "date", "true/false", "0/1"
TYPES = {
    "dim_advisor": {"advisor_id": INT, "years_experience": INT, "aum_target_mm": INT},
    "dim_benchmark": {"benchmark_id": INT},
    "dim_client": {"client_id": INT, "age": INT, "initial_aum": DEC, "client_since": DATE,
                   "advisor_id": INT, "is_active": BOOL, "risk_profile_missing": FLAG},
    "dim_date": {"date_id": INT, "date": DATE, "year": INT, "quarter": INT, "month": INT,
                 "week_of_year": INT, "is_month_end": FLAG, "is_quarter_end": FLAG,
                 "is_year_end": FLAG, "is_trading_day": FLAG},
    "dim_security": {"security_id": INT, "benchmark_id": INT, "is_etf": BOOL, "expense_ratio_bps": DEC},
    "fact_fees": {"fee_id": INT, "client_id": INT, "advisor_id": INT, "fee_date": DATE,
                  "aum_basis": DEC, "bps_charged": DEC, "amount": DEC, "aum_at_floor": FLAG},
    "fact_portfolio_snapshot": {"snapshot_id": INT, "client_id": INT, "advisor_id": INT, "benchmark_id": INT,
                                "snapshot_date": DATE, "year": INT, "month": INT, "aum": DEC,
                                "return_ytd": DEC, "benchmark_return_ytd": DEC, "active_alpha_ytd": DEC,
                                "cash_pct": DEC, "aum_at_floor": FLAG, "return_extreme": FLAG,
                                "fee_missing": FLAG},
    "fact_transactions": {"txn_id": INT, "client_id": INT, "advisor_id": INT, "security_id": INT,
                          "txn_date": DATE, "shares": DEC, "price": DEC, "amount": DEC,
                          "shares_sign_fixed": FLAG, "non_trading_day": FLAG, "after_account_closed": FLAG},
}
TYPE_PATTERN = {INT: r"[+-]?\d+", DEC: r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?", DATE: r"\d{4}-\d{2}-\d{2}",
                BOOL: r"True|False", FLAG: r"0|1"}

CASH_TYPES = {"Deposit", "Withdrawal", "Advisory Fee"}


def expected_blank(t: str, df: pd.DataFrame) -> pd.DataFrame:
    """True where a blank cell is correct by design (so it doesn't count against completeness)."""
    eb = pd.DataFrame(False, index=df.index, columns=df.columns)
    if t == "dim_security":
        eb["sector"] = df.asset_class != "Equity"
        eb["expense_ratio_bps"] = df.is_etf != "True"
    if t == "fact_transactions":
        cash = df.txn_type.isin(CASH_TYPES)
        for c in ("security_id", "shares", "price"):
            eb[c] = cash
    return eb


# ════════════════════════════════════════════════════════════════════
# 2. Business rules (columns with a natural bound)
# ════════════════════════════════════════════════════════════════════

def num(s):
    return pd.to_numeric(s.str.strip(), errors="coerce")


def date(s):
    return pd.to_datetime(s.str.strip(), format="%Y-%m-%d", errors="coerce")


US = set("""AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM
NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC""".split())
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
ACCOUNT = {"Taxable", "IRA", "Roth IRA", "Trust", "529"}
RISK = {"Conservative", "Moderately Conservative", "Balanced", "Moderately Aggressive", "Aggressive", "Unknown"}
SECTORS = {"Communication Services", "Consumer Discretionary", "Consumer Staples", "Energy", "Financials",
           "Healthcare", "Industrials", "Materials", "Real Estate", "Technology", "Utilities"}


def between(lo, hi):
    return lambda s: (num(s) >= lo) & (num(s) <= hi)


def date_between(lo, hi):
    return lambda s: (date(s) >= pd.Timestamp(lo)) & (date(s) <= pd.Timestamp(hi))


def one_of(values):
    return lambda s: s.str.strip().isin(values)


def matches(pattern):
    return lambda s: s.str.strip().str.fullmatch(pattern).fillna(False)


# (table, column, rule, kind, test) — test(series) -> bool mask; applied to non-blank cells
COLUMN_RULES = [
    ("dim_advisor", "years_experience", "0–60 years", "range", between(0, 60)),
    ("dim_advisor", "aum_target_mm", "> 0", "sign", lambda s: num(s) > 0),
    ("dim_advisor", "region", "known region", "code list",
     one_of({"Northeast", "Mid-Atlantic", "Southeast", "Midwest", "Southwest", "West"})),
    ("dim_advisor", "certifications", "each token in CFA/CFP/CIMA/None", "code list",
     lambda s: s.str.split(r"\s*,\s*").apply(lambda x: set(x) <= {"CFA", "CFP", "CIMA", "None"})),
    ("dim_benchmark", "asset_class", "known asset class", "code list",
     one_of({"Equity", "Fixed Income", "Multi-Asset", "International", "Small Cap", "Emerging", "Cash"})),
    ("dim_client", "age", "18–110", "range", between(18, 110)),
    ("dim_client", "state", "2-letter US code", "code list", one_of(US)),
    ("dim_client", "zip_code", "5 digits", "format", matches(r"\d{5}")),
    ("dim_client", "risk_profile", "known risk profile (or 'Unknown')", "code list", one_of(RISK)),
    ("dim_client", "client_tier", "Retail/HNW/UHNW", "code list", one_of({"Retail", "HNW", "UHNW"})),
    ("dim_client", "primary_account_type", "known account type", "code list", one_of(ACCOUNT)),
    ("dim_client", "initial_aum", "> 0", "sign", lambda s: num(s) > 0),
    ("dim_client", "client_since", "1950-01-01 to 2024-12-31", "range", date_between("1950-01-01", "2024-12-31")),
    ("dim_client", "is_active", "True/False", "code list", one_of({"True", "False"})),
    ("dim_date", "year", "2020–2024", "range", between(2020, 2024)),
    ("dim_date", "quarter", "1–4", "range", between(1, 4)),
    ("dim_date", "month", "1–12", "range", between(1, 12)),
    ("dim_date", "week_of_year", "1–53", "range", between(1, 53)),
    ("dim_date", "month_name", "month name", "code list", one_of(MONTHS)),
    ("dim_date", "day_of_week", "day name", "code list", one_of(DAYS)),
    ("dim_security", "ticker", "1–5 capital letters", "format", matches(r"[A-Z]{1,5}")),
    ("dim_security", "asset_class", "known asset class", "code list",
     one_of({"Equity", "Fixed Income", "Alternative", "Cash Equivalent"})),
    ("dim_security", "sector", "known sector", "code list", one_of(SECTORS)),
    ("dim_security", "is_etf", "True/False", "code list", one_of({"True", "False"})),
    ("dim_security", "expense_ratio_bps", "0–300 bps", "range", between(0, 300)),
    ("fact_fees", "fee_date", "2020-01-01 to 2024-12-31", "range", date_between("2020-01-01", "2024-12-31")),
    ("fact_fees", "fee_type", "known fee type", "code list",
     one_of({"Advisory", "Management", "Custodial", "Performance"})),
    ("fact_fees", "aum_basis", ">= 0", "sign", lambda s: num(s) >= 0),
    ("fact_fees", "bps_charged", "0–300 bps", "range", between(0, 300)),
    ("fact_fees", "amount", ">= 0", "sign", lambda s: num(s) >= 0),
    ("fact_portfolio_snapshot", "snapshot_date", "2020-01-01 to 2024-12-31", "range",
     date_between("2020-01-01", "2024-12-31")),
    ("fact_portfolio_snapshot", "year", "2020–2024", "range", between(2020, 2024)),
    ("fact_portfolio_snapshot", "month", "1–12", "range", between(1, 12)),
    ("fact_portfolio_snapshot", "aum", ">= 0", "sign", lambda s: num(s) >= 0),
    ("fact_portfolio_snapshot", "return_ytd", ">= −100% (numeric)", "range", lambda s: num(s) >= -1),
    ("fact_portfolio_snapshot", "benchmark_return_ytd", "−100% to +200%", "range", between(-1, 2)),
    ("fact_portfolio_snapshot", "cash_pct", "0–1", "range", between(0, 1)),
    ("fact_portfolio_snapshot", "account_type", "known account type", "code list", one_of(ACCOUNT)),
    ("fact_transactions", "txn_date", "2020-01-01 to 2024-12-31", "range", date_between("2020-01-01", "2024-12-31")),
    ("fact_transactions", "txn_type", "known transaction type", "code list",
     one_of({"Buy", "Sell", "Dividend"} | CASH_TYPES)),
    ("fact_transactions", "shares", "> 0 (direction comes from txn_type)", "sign", lambda s: num(s) > 0),
    ("fact_transactions", "price", "> 0", "sign", lambda s: num(s) > 0),
    ("fact_transactions", "amount", "> 0", "sign", lambda s: num(s) > 0),
]

# Row rules: (table, columns, rule, kind, test(df) -> (pass mask, applies mask))
ROW_RULES = [
    ("dim_client", "client_tier+initial_aum", "tier matches initial AUM band", "consistency",
     lambda d: (pd.cut(num(d.initial_aum), [-np.inf, 5e5, 5e6, np.inf], right=False,
                       labels=["Retail", "HNW", "UHNW"]).astype(str) == d.client_tier, None)),
    ("dim_security", "sector", "only equities have a sector", "conditional blank",
     lambda d: ((d.sector != "") == (d.asset_class == "Equity"), None)),
    ("dim_security", "expense_ratio_bps", "only ETFs have an expense ratio", "conditional blank",
     lambda d: ((d.expense_ratio_bps != "") == (d.is_etf == "True"), None)),
    ("fact_transactions", "security_id/shares/price", "trades have security, shares and price", "conditional blank",
     lambda d: ((d.security_id != "") & (d.shares != "") & (d.price != ""), ~d.txn_type.isin(CASH_TYPES))),
    ("fact_transactions", "security_id/shares/price", "cash flows have no security, shares or price",
     "conditional blank",
     lambda d: ((d.security_id == "") & (d.shares == "") & (d.price == ""), d.txn_type.isin(CASH_TYPES))),
]


def run_rules(T: dict) -> pd.DataFrame:
    out = []
    for t, col, rule, kind, test in COLUMN_RULES:
        s = T[t][col]
        applies = s.str.strip() != ""
        ok = test(s[applies]).fillna(False).astype(bool)
        out.append(dict(table=t, column=col, rule=rule, kind=kind, checked=int(applies.sum()),
                        passed=int(ok.sum()), examples="; ".join(s[applies][~ok].astype(str).unique()[:5])))
    for t, col, rule, kind, test in ROW_RULES:
        d = T[t]
        ok, applies = test(d)
        applies = pd.Series(True, index=d.index) if applies is None else applies
        ok = ok[applies]
        out.append(dict(table=t, column=col, rule=rule, kind=kind, checked=int(applies.sum()),
                        passed=int(ok.sum()), examples=""))
    r = pd.DataFrame(out)
    r["failed"] = r.checked - r.passed
    r["pass_rate"] = np.where(r.checked > 0, r.passed / r.checked.where(r.checked > 0, 1), 1.0)
    return r


# ════════════════════════════════════════════════════════════════════
# 3. Reconciliations (recomputed vs stored)
# ════════════════════════════════════════════════════════════════════

def month_key(df, client_col, date_col):
    return df[client_col].str.strip() + "|" + df[date_col].str[:7]


def reconcile(T: dict) -> pd.DataFrame:
    f, p, t, c = T["fact_fees"], T["fact_portfolio_snapshot"], T["fact_transactions"], T["dim_client"]
    out = []

    def add(name, scope, ok, applies, note):
        ok = ok[applies] if applies is not None else ok
        out.append(dict(reconciliation=name, scope=scope, checked=int(len(ok)), passed=int(ok.sum()),
                        failed=int((~ok).sum()), pass_rate=float(ok.mean()) if len(ok) else 1.0, note=note))

    # R1 fee amount recomputed from its own inputs
    calc = num(f.aum_basis) * num(f.bps_charged) / 10_000 / 12
    add("fee amount = aum_basis × bps ÷ 10,000 ÷ 12", "fact_fees",
        ((calc - num(f.amount)).abs() <= 0.0101).fillna(False), None, "tolerance $0.01")

    # R2 fee aum_basis vs the snapshot AUM of the same client-month (cross-table)
    snap = pd.Series(num(p.aum).values, index=month_key(p, "client_id", "snapshot_date"))
    snap = snap[~snap.index.duplicated()]
    s_aum = month_key(f, "client_id", "fee_date").map(snap)
    add("fee aum_basis = snapshot AUM (same client-month)", "fact_fees ↔ fact_portfolio_snapshot",
        ((num(f.aum_basis) - s_aum).abs() <= 0.0101).fillna(False), None, "every fee should have a snapshot")

    # R3 alpha recomputed from return and benchmark
    gap = (num(p.return_ytd) - num(p.benchmark_return_ytd) - num(p.active_alpha_ytd)).abs()
    add("active_alpha_ytd = return_ytd − benchmark_return_ytd", "fact_portfolio_snapshot",
        (gap <= 1e-4).fillna(False), None, "tolerance 0.0001 (converted % values were truncated at 2 dp)")

    # R4 trade amount recomputed from shares × price
    trade = t.txn_type.isin({"Buy", "Sell", "Dividend"})
    add("trade amount = shares × price", "fact_transactions",
        ((num(t.shares) * num(t.price) - num(t.amount)).abs() <= 0.0101).fillna(False), trade, "tolerance $0.01")

    # R5 snapshot attributes agree with the client dimension (cross-table)
    cd = c.set_index("client_id")
    add("snapshot advisor_id and account_type = dim_client", "fact_portfolio_snapshot ↔ dim_client",
        ((p.advisor_id == p.client_id.map(cd.advisor_id)) &
         (p.account_type == p.client_id.map(cd.primary_account_type))), None, "")

    # R6 Advisory Fee transactions vs fact_fees, client-month totals (known limitation, decision #15)
    af = t[t.txn_type == "Advisory Fee"]
    fees = num(f.amount).groupby(month_key(f, "client_id", "fee_date")).sum()
    tx = num(af.amount).groupby(month_key(af, "client_id", "txn_date")).sum()
    both = tx.index.intersection(fees.index)
    ok = pd.Series((tx[both] - fees[both]).abs() <= 0.0101, index=both)
    add("Advisory Fee transactions = fact_fees (client-month totals)", "fact_transactions ↔ fact_fees",
        ok, None, f"expected to fail: known limitation (decision #15); txns ${num(af.amount).sum() / 1e6:,.1f}M "
                  f"vs fact_fees ${num(f.amount).sum() / 1e6:,.1f}M")
    return pd.DataFrame(out)


# ════════════════════════════════════════════════════════════════════
# 4. IQR outliers (numeric columns with no natural bound)
# ════════════════════════════════════════════════════════════════════

IQR_COLUMNS = [("fact_portfolio_snapshot", "aum", None),
               ("fact_transactions", "amount", ("Buy", "Sell")),
               ("dim_client", "initial_aum", None)]


def iqr_flags(T: dict) -> pd.DataFrame:
    out = []
    for t, col, types in IQR_COLUMNS:
        d = T[t] if types is None else T[t][T[t].txn_type.isin(types)]
        v = num(d[col]).dropna()
        q1, q3 = v.quantile([0.25, 0.75])
        lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
        flagged = (v < lo) | (v > hi)
        note = ""
        if "client_id" in d.columns and t != "dim_client":
            tier = d.client_id.map(T["dim_client"].set_index("client_id").client_tier)
            note = f"{(tier[flagged.index[flagged]] == 'UHNW').mean():.0%} of flagged rows are UHNW clients"
        elif t == "dim_client":
            note = f"{(d.client_tier[flagged.index[flagged]] == 'UHNW').mean():.0%} of flagged rows are UHNW clients"
        out.append(dict(table=t, column=col + (f" ({'/'.join(types)})" if types else ""), n=len(v),
                        q1=round(q1, 2), q3=round(q3, 2), lower_fence=round(lo, 2), upper_fence=round(hi, 2),
                        flagged=int(flagged.sum()), pct_flagged=round(flagged.mean() * 100, 2), note=note))
    return pd.DataFrame(out)


IQR_SENTENCE = ("Flagged does not mean wrong: an IQR outlier is only far from the middle of the distribution; "
                "here almost every flagged AUM and initial AUM belongs to a UHNW client whose account is "
                "legitimately large, and flagged trades are simply large trades, so a flag is a prompt to look, "
                "not proof of an error.")


# ════════════════════════════════════════════════════════════════════
# Scorecard
# ════════════════════════════════════════════════════════════════════

def scorecard(stage: str, T: dict, ri: pd.DataFrame, rules: pd.DataFrame) -> pd.DataFrame:
    out = []
    for t in TABLES:
        d = T[t]
        blank = d.apply(lambda s: s.str.strip() == "")
        should_fill = ~expected_blank(t, d)
        completeness = 1 - (blank & should_fill).to_numpy().sum() / should_fill.to_numpy().sum()

        pk = d[PK[t]].str.strip()
        bad = pk.duplicated(keep=False) | (pk == "")
        if t in BUSINESS_KEY:
            bad |= d.duplicated(BUSINESS_KEY[t], keep=False)
        uniqueness = 1 - bad.mean()

        valid = total = 0
        for col, typ in TYPES.get(t, {}).items():
            if col not in d.columns:
                continue
            s = d[col].str.strip()
            s = s[s != ""]
            ok = s.str.fullmatch(TYPE_PATTERN[typ])
            if typ == DATE:
                ok &= date(s).notna()
            valid += int(ok.sum())
            total += len(s)
        type_validity = valid / total if total else 1.0

        r = rules[rules.table == t]
        rule_pass = r.passed.sum() / r.checked.sum() if r.checked.sum() else 1.0

        x = ri[ri.child_table == t]
        ref = x.matched.sum() / x.checked.sum() if len(x) and x.checked.sum() else np.nan

        out.append(dict(table=t, stage=stage, rows=len(d),
                        pct_completeness=round(completeness * 100, 2),
                        pct_key_uniqueness=round(uniqueness * 100, 2),
                        pct_type_validity=round(type_validity * 100, 2),
                        pct_rule_pass=round(rule_pass * 100, 2),
                        pct_referential_match=round(ref * 100, 2) if pd.notna(ref) else np.nan))
    return pd.DataFrame(out)


# ════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════

def load(folder: Path) -> dict:
    return {t: pd.read_csv(folder / f"{t}.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
            for t in TABLES}


def section(title):
    print(f"\n{'═' * 90}\n{title}\n{'═' * 90}")


def main():
    cards, details = [], []
    for stage, folder in STAGES.items():
        if not folder.exists():
            raise SystemExit(f"Missing {folder}. Run scripts/02_clean.py first.")
        T = load(folder)
        section(f"{stage.upper()} — {folder.relative_to(HW_DIR)}/")

        # 1. referential integrity
        ri_rows = []
        for ct, ck, pt, pk in RELATIONSHIPS:
            res = check_referential_integrity(T[ct], ck, T[pt], pk)
            ri_rows.append(dict(child_table=ct, child_key=ck, parent_table=pt, parent_key=pk,
                                **{k: v for k, v in res.items() if k != "orphan_rows"}))
        ri = pd.DataFrame(ri_rows)
        print("\n1. Referential integrity (13 relationships)")
        for r in ri.itertuples():
            keys = ", ".join(map(str, r.distinct_orphan_keys[:5])) + (" …" if len(r.distinct_orphan_keys) > 5 else "")
            print(f"   {r.child_table + '.' + r.child_key:<38} → {r.parent_table + '.' + r.parent_key:<26} "
                  f"match {r.match_rate:7.2%} | orphans {r.orphan_count:>7,} ({len(r.distinct_orphan_keys):>3} keys)"
                  f" | null {r.null_key_rate:6.2%}" + (f" | e.g. {keys}" if r.orphan_count else ""))

        # 2. rules
        rules = run_rules(T)
        print(f"\n2. Business rules: {len(rules)} rules, {int((rules.failed > 0).sum())} with failures")
        for r in rules[rules.failed > 0].itertuples():
            print(f"   FAIL {r.table}.{r.column}: {r.rule} — {r.failed:,} of {r.checked:,}"
                  + (f" (e.g. {r.examples})" if r.examples else ""))

        # 3. reconciliations
        rec = reconcile(T)
        print("\n3. Reconciliations")
        for r in rec.itertuples():
            status = "PASS" if r.failed == 0 else "FAIL"
            print(f"   {status} {r.reconciliation:<58} {r.passed:>8,} / {r.checked:<8,} {r.note}")

        # 4. IQR outliers
        iqr = iqr_flags(T)
        print("\n4. IQR outliers (1.5 × IQR)")
        for r in iqr.itertuples():
            print(f"   {r.table}.{r.column:<26} fences [{r.lower_fence:>14,.2f}, {r.upper_fence:>14,.2f}] "
                  f"flagged {r.flagged:>6,} ({r.pct_flagged:5.2f}%) — {r.note}")
        print(f"   {IQR_SENTENCE}")

        card = scorecard(stage, T, ri, rules)
        cards.append(card)
        for name, df in [("referential_integrity", ri.assign(distinct_orphan_keys=ri.distinct_orphan_keys.map(
                lambda k: "; ".join(map(str, k[:20]))))), ("rule", rules), ("reconciliation", rec), ("iqr_outlier", iqr)]:
            details.append(df.assign(stage=stage, check_type=name))

    sc = pd.concat(cards).sort_values(["table", "stage"], key=lambda s: s.map({"raw": 0, "clean": 1})
                                      if s.name == "stage" else s).reset_index(drop=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    sc.to_csv(REPORTS / "data_quality_scorecard.csv", index=False)
    pd.concat(details, ignore_index=True).to_csv(REPORTS / "validation_details.csv", index=False)

    section("DATA QUALITY SCORECARD (%)")
    print(sc.to_string(index=False, na_rep="n/a"))
    print(f"\nWrote {(REPORTS / 'data_quality_scorecard.csv').relative_to(HW_DIR)}")
    print(f"Wrote {(REPORTS / 'validation_details.csv').relative_to(HW_DIR)}")


if __name__ == "__main__":
    main()
