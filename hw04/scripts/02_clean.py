"""
02_clean.py — Apply the decisions in decision_log.md to the Wildcat Capital data.

Reads the eight raw CSVs (as text: dtype=str, keep_default_na=False) and writes
a new, cleaned set. The raw files are never modified.

Rules this script follows
  * Same file names, same columns. Flag columns (0/1) are added only where a
    value is suspicious but cannot be corrected without inventing data.
  * One transformation at a time. Each step prints rows affected and a
    before/after check, then `assert`s the after-state. Any failed check stops
    the script before anything is written.
  * Reconcile instead of guessing: repairs are confirmed against a column or
    table that describes the same fact (e.g. alpha = return − benchmark).
  * Nothing is deleted silently: removed rows go to data/audit/quarantine_*.csv
    and raw rows = clean rows + quarantined rows is proven for every table.

Outputs (relative to hw04/)
  data/clean/<table>.csv            eight cleaned tables
  data/clean/README_clean.md        relationships, BI column types, flags, limitations
  data/audit/cleaning_log.csv       table, issue, action, rows_affected, note
  data/audit/value_changes.csv      table, key_column, key, column, old_value, new_value
  data/audit/quarantine_*.csv       one file per quarantined set

Usage
  python scripts/02_clean.py
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

HW_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = HW_DIR / "Wildcat Capital"
CLEAN_DIR = HW_DIR / "data" / "clean"
AUDIT_DIR = HW_DIR / "data" / "audit"

TABLES = ["dim_advisor", "dim_benchmark", "dim_client", "dim_date", "dim_security",
          "fact_fees", "fact_portfolio_snapshot", "fact_transactions"]
PK = {"dim_advisor": "advisor_id", "dim_benchmark": "benchmark_id", "dim_client": "client_id",
      "dim_date": "date_id", "dim_security": "security_id", "fact_fees": "fee_id",
      "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id"}

STATE_NAMES = {  # full name -> USPS code (only names that appear are needed, but the map is complete)
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA",
    "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT",
    "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM",
    "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
    "Virginia": "VA", "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
    "District of Columbia": "DC",
}
US_CODES = set(STATE_NAMES.values())


# ════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════

def num(s: pd.Series) -> pd.Series:
    """Plain numeric conversion of text; anything else becomes NaN (never silently 0)."""
    return pd.to_numeric(s.str.strip(), errors="coerce")


def fmt(x: float, dp: int = 6) -> str:
    """Write a float back as text without float noise, e.g. 0.0928 -> '0.0928'."""
    return f"{round(float(x), dp):.{dp}f}".rstrip("0").rstrip(".")


_STEP = [0]


def banner(title: str):
    _STEP[0] += 1
    print(f"\n{'─' * 78}\nStep {_STEP[0]}: {title}\n{'─' * 78}")


class Audit:
    def __init__(self):
        self.log, self.changes, self.quarantine = [], [], {}

    def note(self, table, issue, action, rows, note=""):
        self.log.append(dict(table=table, issue=issue, action=action, rows_affected=int(rows), note=note))
        print(f"  → logged: {action} | {rows:,} rows | {note}" if note else f"  → logged: {action} | {rows:,} rows")

    def change(self, df, table, mask, col, new):
        """Apply new values to df.loc[mask, col] and record every old → new pair."""
        key = PK[table]
        old = df.loc[mask, col]
        new = pd.Series(new, index=old.index) if not isinstance(new, pd.Series) else new.loc[old.index]
        changed = old != new
        self.changes.append(pd.DataFrame({
            "table": table, "key_column": key, "key": df.loc[old.index[changed], key].values,
            "column": col, "old_value": old[changed].values, "new_value": new[changed].values}))
        df.loc[old.index, col] = new
        return int(changed.sum())

    def changes_for(self, table, col):
        """Keys of rows changed so far in table.col."""
        ch = [c for c in self.changes if len(c) and c.table.iat[0] == table and c.column.iat[0] == col]
        return pd.concat(ch).key if ch else pd.Series(dtype=str)

    def move(self, df, table, mask, name, reason, extra: pd.DataFrame | None = None):
        """Remove rows from df into a named quarantine set; returns the remaining frame."""
        q = df[mask].copy()
        if extra is not None:
            q = q.join(extra)
        q.insert(0, "quarantine_reason", reason)
        q.insert(0, "source_table", table)
        self.quarantine[name] = (table, q)
        return df[~mask].copy()


def show(df, cols, mask=None, k=3):
    d = df[mask] if mask is not None else df
    print("   " + d[cols].head(k).to_string(index=False).replace("\n", "\n   "))


# ════════════════════════════════════════════════════════════════════
# Load
# ════════════════════════════════════════════════════════════════════

def load():
    raw = {}
    for t in TABLES:
        p = RAW_DIR / f"{t}.csv"
        raw[t] = pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    return raw


# ════════════════════════════════════════════════════════════════════
# Transformations (numbers refer to decision_log.md)
# ════════════════════════════════════════════════════════════════════

def step_state(T, A):
    banner("dim_client.state — full state names → 2-letter codes  [decision #1]")
    c = T["dim_client"]
    s = c.state.str.strip()
    bad = ~s.isin(US_CODES)
    print(f"  before: {bad.sum()} non-code values: {s[bad].value_counts().to_dict()}")
    unknown = set(s[bad]) - set(STATE_NAMES)
    assert not unknown, f"Unmapped state names, refusing to guess: {unknown}"
    before_counts = s.map(lambda v: STATE_NAMES.get(v, v)).value_counts()
    n = A.change(c, "dim_client", bad, "state", s[bad].map(STATE_NAMES))
    after = c.state.str.strip()
    print(f"  after : {(~after.isin(US_CODES)).sum()} non-code values; PA now {int((after == 'PA').sum())} clients")
    assert after.isin(US_CODES).all(), "state still contains non-code values"
    assert after.value_counts().sort_index().equals(before_counts.sort_index()), "per-state totals changed unexpectedly"
    A.note("dim_client", "Full state names instead of 2-letter codes", "standardize", n,
           "lookup table; per-state totals reconcile to the name+code counts before the fix")


def step_return_pct(T, A):
    banner("fact_portfolio_snapshot.return_ytd — '9.28%' text → 0.0928  [decision #2]")
    p = T["fact_portfolio_snapshot"]
    r = p.return_ytd.str.strip()
    pct = r.str.endswith("%")
    print(f"  before: {pct.sum()} values end in '%'; pd.to_numeric fails on {num(r).isna().sum()} rows")
    show(p, ["snapshot_id", "return_ytd", "benchmark_return_ytd", "active_alpha_ytd"], pct)
    new = (pd.to_numeric(r[pct].str.rstrip("%")) / 100).map(lambda v: fmt(v, 6))
    n = A.change(p, "fact_portfolio_snapshot", pct, "return_ytd", new)
    rv, b, al = num(p.return_ytd), num(p.benchmark_return_ytd), num(p.active_alpha_ytd)
    gap = (rv - b - al).abs()
    print(f"  after : {p.return_ytd.str.endswith('%').sum()} '%' values, {rv.isna().sum()} unparseable")
    print(f"  reconcile: |return − benchmark − alpha| max on fixed rows = {gap[pct].max():.6f} "
          f"(values were cut off at 2 dp of a percent, so up to 0.0001 is allowed); max on all other rows = {gap[~pct].max():.7f}")
    show(p, ["snapshot_id", "return_ytd", "benchmark_return_ytd", "active_alpha_ytd"], pct)
    assert rv.notna().all(), "return_ytd still has unparseable values"
    assert gap[pct].max() <= 0.0001, "fixed returns do not reconcile with benchmark and alpha"
    assert gap[~pct].max() <= 0.000002, "unexpected alpha mismatch in untouched rows"
    A.note("fact_portfolio_snapshot", "return_ytd stored as text percentages", "convert", n,
           "÷100; confirmed by return − benchmark = alpha (within 0.0001: % values were truncated at 2 dp)")


def step_security_id(T, A):
    banner("fact_transactions.security_id — '45.0' → '45'  [decision #3]")
    t, sec = T["fact_transactions"], T["dim_security"]
    sid = t.security_id.str.strip()
    filled = sid != ""
    keys = set(sec.security_id.str.strip())
    n_dot0 = sid[filled].str.fullmatch(r"\d+\.0+").sum()
    print(f"  before: {filled.sum():,} filled, {n_dot0:,} end in '.0'; "
          f"text join matches {sid[filled].isin(keys).sum():,}")
    assert sid[filled].str.fullmatch(r"\d+(\.0+)?").all(), "a security_id has a real fractional part"
    new = sid[filled].str.replace(r"\.0+$", "", regex=True)
    n = A.change(t, "fact_transactions", filled, "security_id", new)
    after = t.security_id[filled]
    n_whole = after.str.fullmatch(r"\d+").sum()
    print(f"  after : {n_whole:,} whole numbers; text join matches {after.isin(keys).sum():,}")
    assert after.str.fullmatch(r"\d+").all()
    assert after.isin(keys).all(), "a converted security_id has no match in dim_security"
    assert (t.security_id == "").sum() == (~filled).sum(), "blank security_ids changed"
    A.note("fact_transactions", "security_id stored as '45.0'", "convert", n,
           "every converted ID joins to dim_security; blanks (cash-flow rows) untouched")


def step_negative_shares(T, A):
    banner("fact_transactions.shares — negative shares on Buys  [decision #4]")
    t = T["fact_transactions"]
    sh, pr, am = num(t.shares), num(t.price), num(t.amount)
    neg = (t.txn_type == "Buy") & (sh < 0)
    print(f"  before: {neg.sum()} Buys with negative shares; negative Sells: {((t.txn_type == 'Sell') & (sh < 0)).sum()}")
    show(t, ["txn_id", "txn_type", "shares", "price", "amount"], neg)
    # reconcile first: the positive amount must equal |shares| × price, otherwise the sign is not the error
    assert ((sh[neg].abs() * pr[neg] - am[neg]).abs() <= 0.0101).all(), \
        "amount ≠ |shares| × price on a negative Buy; the sign may not be the error"
    t["shares_sign_fixed"] = neg.astype(int)
    n = A.change(t, "fact_transactions", neg, "shares", t.shares[neg].str.strip().str.lstrip("-"))
    sh2 = num(t.shares)
    trade = sh2.notna()
    print(f"  after : negative shares = {(sh2 < 0).sum()}; shares_sign_fixed = 1 on {t.shares_sign_fixed.sum()} rows")
    show(t, ["txn_id", "txn_type", "shares", "price", "amount", "shares_sign_fixed"], neg)
    assert (sh2[trade] > 0).all()
    assert ((sh2[trade] * pr[trade] - am[trade]).abs() <= 0.0101).all(), "amount ≠ shares × price after fix"
    A.note("fact_transactions", "Negative shares on Buy transactions", "standardize + flag", n,
           "sign removed; amount = shares × price now holds for every trade; flag shares_sign_fixed")


def step_duplicate_clients(T, A):
    banner("dim_client — duplicate clients with a misspelled last name  [decision #8]")
    c = T["dim_client"]
    other = [x for x in c.columns if x not in ("client_id", "last_name")]
    c["_cid"] = c.client_id.astype(int)
    first = c.sort_values("_cid").groupby(other, sort=False).client_id.transform("first")
    first = first.reindex(c.index)
    dup = first != c.client_id
    orig = c.set_index("client_id").last_name
    print(f"  before: {len(c):,} clients; {dup.sum()} match an earlier client on all {len(other)} other columns")
    pairs = pd.DataFrame({"client_id": c.client_id[dup], "last_name": c.last_name[dup],
                          "original_client_id": first[dup], "original_last_name": first[dup].map(orig)})
    print("   " + pairs.head(4).to_string(index=False).replace("\n", "\n   "))

    def one_letter(a, b):  # b == a minus/plus one trailing letter (or vice versa)
        a, b = a.lower(), b.lower()
        return a != b and (a.startswith(b) or b.startswith(a)) and abs(len(a) - len(b)) == 1
    assert all(one_letter(a, b) for a, b in zip(pairs.last_name, pairs.original_last_name)), \
        "a 'duplicate' differs by more than a one-letter typo"
    # reconcile: the copies must have no activity, so removing them breaks no joins
    used = set(T["fact_portfolio_snapshot"].client_id) | set(T["fact_fees"].client_id) | \
        set(T["fact_transactions"].client_id)
    assert not set(pairs.client_id) & used, "a duplicate client has fact rows; cannot quarantine"
    raw_n = len(c)
    extra = pairs.set_index(c.index[dup])[["original_client_id", "original_last_name"]]
    T["dim_client"] = A.move(c.drop(columns="_cid"), "dim_client", dup, "dim_client_duplicates",
                             "Duplicate of original_client_id; last name differs by one letter", extra)
    c2 = T["dim_client"]
    print(f"  after : {len(c2):,} clients; duplicates on the {len(other)} columns = "
          f"{c2.duplicated(other).sum()}; quarantined {dup.sum()}")
    assert len(c2) + dup.sum() == raw_n
    assert not c2.duplicated(other).any()
    A.note("dim_client", "Duplicate clients (2501–2525)", "quarantine", int(dup.sum()),
           "quarantine_dim_client_duplicates.csv; copies had 0 snapshots, fees and transactions")


def step_orphan_txns(T, A):
    banner("fact_transactions — client_ids not in dim_client (copied rows)  [decision #5]")
    t, c = T["fact_transactions"], T["dim_client"]
    orphan = ~t.client_id.isin(set(c.client_id))
    print(f"  before: {len(t):,} rows; {orphan.sum()} orphan rows, {t.client_id[orphan].nunique()} distinct fake IDs "
          f"({t.client_id[orphan].astype(int).min()}–{t.client_id[orphan].astype(int).max()})")
    same = [x for x in t.columns if x not in ("txn_id", "client_id")]
    real = t[~orphan].drop_duplicates(same)[same + ["txn_id", "client_id"]] \
        .rename(columns={"txn_id": "original_txn_id", "client_id": "original_client_id"})
    m = t[orphan].reset_index().merge(real, on=same, how="left").set_index("index")
    print(f"  reconcile: {m.original_txn_id.notna().sum()} of {orphan.sum()} orphans are exact copies of a real "
          "client's transaction (all columns except client_id)")
    assert m.original_txn_id.notna().all(), "an orphan transaction is not a copy; cannot assume it is fake"
    raw_n = len(t)
    T["fact_transactions"] = A.move(t, "fact_transactions", orphan, "fact_transactions_orphans",
                                    "client_id not in dim_client; exact copy of original_txn_id",
                                    m[["original_txn_id", "original_client_id"]])
    t2 = T["fact_transactions"]
    print(f"  after : {len(t2):,} rows; orphans remaining = {(~t2.client_id.isin(set(c.client_id))).sum()}")
    assert len(t2) + orphan.sum() == raw_n
    assert t2.client_id.isin(set(c.client_id)).all()
    assert t2.txn_id.isin(m.original_txn_id).sum() == orphan.sum(), "an original transaction went missing"
    A.note("fact_transactions", "Transactions for clients that don't exist", "quarantine", int(orphan.sum()),
           "quarantine_fact_transactions_orphans.csv with original_txn_id of the row each one copies")


def step_risk_profile(T, A):
    banner("dim_client.risk_profile — blank → 'Unknown' + flag  [decision #7]")
    c, p = T["dim_client"], T["fact_portfolio_snapshot"]
    blank = c.risk_profile.str.strip() == ""
    print(f"  before: {blank.sum()} blank risk profiles (after removing duplicates)")
    snaps = p[p.client_id.isin(set(c.client_id[blank]))]
    print(f"  reconcile: their {len(snaps):,} snapshots use benchmark(s) {sorted(snaps.benchmark_id.unique())} "
          "— the 60/40 default, so the benchmark cannot reveal the true profile")
    assert set(snaps.benchmark_id) <= {"3"}, "a blank-profile client uses a non-default benchmark; could infer instead"
    c["risk_profile_missing"] = blank.astype(int)
    n = A.change(c, "dim_client", blank, "risk_profile", "Unknown")
    print(f"  after : blanks = {(c.risk_profile.str.strip() == '').sum()}; 'Unknown' = {(c.risk_profile == 'Unknown').sum()}; "
          f"flag = {c.risk_profile_missing.sum()}")
    assert (c.risk_profile.str.strip() != "").all()
    assert (c.risk_profile == "Unknown").sum() == c.risk_profile_missing.sum() == blank.sum()
    A.note("dim_client", "Blank risk profile", "fill + flag", n,
           "filled 'Unknown' (not guessed); flag risk_profile_missing; benchmark 3 kept")


def step_security_name(T, A):
    banner("dim_security.name — 'Inc Inc.' → 'Inc.'  [decision #9]")
    s = T["dim_security"]
    pat = r"\bInc\s+Inc\.?$"
    bad = s.name.str.contains(pat, regex=True)
    print(f"  before: {bad.sum()} names with a doubled suffix")
    show(s, ["security_id", "ticker", "name"], bad)
    new = s.name[bad].str.replace(pat, "Inc.", regex=True)
    clash = new.isin(set(s.name[~bad]))
    assert not clash.any(), f"fixed name would clash with an existing security: {list(new[clash])}"
    n = A.change(s, "dim_security", bad, "name", new)
    print(f"  after : {s.name.str.contains(pat, regex=True).sum()} doubled suffixes")
    show(s, ["security_id", "ticker", "name"], bad)
    assert not s.name.str.contains(pat, regex=True).any()
    A.note("dim_security", "Doubled 'Inc Inc.' in security names", "standardize", n,
           "display label only; no fixed name clashes with another security")


def step_floor(T, A):
    banner("AUM at the $1,000 floor — flag snapshots and fees  [decision #11]")
    p, f = T["fact_portfolio_snapshot"], T["fact_fees"]
    aum = num(p.aum)
    print(f"  before: {int((aum == 1000).sum())} snapshots at exactly 1000.0; lowest AUM = {aum.min():,.2f}; "
          f"fees with aum_basis 1000.0 = {int((num(f.aum_basis) == 1000).sum())}")
    assert aum.min() >= 1000, "AUM below the floor exists; the floor assumption is wrong"
    p["aum_at_floor"] = (aum == 1000).astype(int)
    # reconcile: fee aum_basis must equal the same client-month snapshot AUM, so the fee flag follows the snapshot
    k = lambda df, d: df.client_id + "|" + df[d].str[:7]
    snap_aum = pd.Series(p.aum.values, index=k(p, "snapshot_date"))
    snap_flag = pd.Series(p.aum_at_floor.values, index=k(p, "snapshot_date"))
    fk = k(f, "fee_date")
    assert fk.isin(snap_aum.index).all(), "a fee has no snapshot for its client-month"
    assert (num(f.aum_basis).values == num(fk.map(snap_aum)).values).all(), "fee aum_basis ≠ snapshot AUM"
    f["aum_at_floor"] = fk.map(snap_flag).astype(int).values
    print(f"  reconcile: fee aum_basis equals snapshot AUM for all {len(f):,} fees")
    print(f"  after : aum_at_floor = 1 on {p.aum_at_floor.sum()} snapshots ({p.client_id[p.aum_at_floor == 1].nunique()} clients) "
          f"and {f.aum_at_floor.sum()} fees")
    assert p.aum_at_floor.sum() == (aum == 1000).sum()
    assert f.aum_at_floor.sum() == (num(f.aum_basis) == 1000).sum()
    A.note("fact_portfolio_snapshot", "AUM stuck at the $1,000 floor", "flag", int(p.aum_at_floor.sum()),
           "aum_at_floor; true balance cannot be recovered (return was computed from the floor)")
    A.note("fact_fees", "Fee charged on the $1,000 floor AUM", "flag", int(f.aum_at_floor.sum()),
           "aum_at_floor, matched to the snapshot of the same client-month")


def step_extreme_returns(T, A):
    banner("Extreme YTD returns (< −90% or > +100%) — flag  [decision #12]")
    p = T["fact_portfolio_snapshot"]
    r = num(p.return_ytd)
    ext = (r < -0.9) | (r > 1.0)
    print(f"  before: {ext.sum():,} extreme returns; range {r.min():.4f} to {r.max():.4f}")
    # reconcile: AUM = last December's AUM × (1 + return_ytd). If it holds, the jump is real in both
    # columns (not a typo in one), so it must be flagged, not corrected.
    q = p.assign(_aum=num(p.aum), _y=p.snapshot_date.str[:4].astype(int))
    dec = q[q.snapshot_date.str[5:7] == "12"].set_index(["client_id", "_y"])._aum
    base = pd.Series([dec.get((cid, y - 1), np.nan) for cid, y in zip(q.client_id, q._y)], index=q.index)
    ok = base.notna()
    # tolerance = the precision the data is stored at: AUM to the cent (on both AUM and the December base,
    # magnified by 1 + return), return to 6 dp, and 0.0001 for the rows converted in the % step (those
    # values were cut off, not rounded, at 2 dp of a percent: e.g. a true −0.0750% is stored as "−0.07%")
    was_pct = p.snapshot_id.isin(set(A.changes_for("fact_portfolio_snapshot", "return_ytd")))
    tol = 0.005 + 0.005 * (1 + r).abs() + base * np.where(was_pct, 1e-4, 5e-7) + 1e-6
    gap = (base * (1 + r) - q._aum).abs()
    worst = (gap / tol)[ok].max()
    print(f"  reconcile: AUM = Dec AUM × (1 + return) on {ok.sum():,} testable rows; "
          f"largest gap = {worst:.4f}× the storage-rounding tolerance (must be ≤ 1)")
    assert worst <= 1, "AUM and return disagree beyond rounding; a jump could be a typo rather than a real value"
    p["return_extreme"] = ext.astype(int)
    print(f"  after : return_extreme = 1 on {p.return_extreme.sum():,} rows "
          f"({p.client_id[ext].nunique()} clients); overlap with aum_at_floor = {(ext & (p.aum_at_floor == 1)).sum()}")
    assert p.return_extreme.sum() == ext.sum()
    A.note("fact_portfolio_snapshot", "Extreme YTD returns", "flag", int(ext.sum()),
           "return_extreme; values kept (AUM and return agree, so nothing to correct)")


def step_fee_missing(T, A):
    banner("Snapshot months with no fee — flag  [decision #14]")
    p, f = T["fact_portfolio_snapshot"], T["fact_fees"]
    fk = set(f.client_id + "|" + f.fee_date.str[:7])
    pk = p.client_id + "|" + p.snapshot_date.str[:7]
    missing = ~pk.isin(fk)
    print(f"  before: {len(p):,} snapshots, {len(f):,} fees; {missing.sum():,} snapshots without a fee")
    assert f.duplicated(["client_id", "fee_date"]).sum() == 0, "a client has two fees in one month"
    assert len(p) - len(f) == missing.sum(), "snapshot − fee counts do not reconcile"
    p["fee_missing"] = missing.astype(int)
    print(f"  reconcile: {len(p):,} snapshots − {len(f):,} fees = {missing.sum():,} missing (one fee per client-month)")
    print(f"  after : fee_missing = 1 on {p.fee_missing.sum():,} snapshots ({p.client_id[missing].nunique():,} clients)")
    A.note("fact_portfolio_snapshot", "Months with no fee", "flag", int(missing.sum()),
           "fee_missing; fact_fees left as is (no fees invented)")


def step_non_trading(T, A):
    banner("Buys/Sells on non-trading days — flag  [decision #16]")
    t, d = T["fact_transactions"], T["dim_date"]
    assert t.txn_date.isin(set(d.date)).all(), "a txn_date is missing from dim_date"
    trd = t.txn_date.map(d.set_index("date").is_trading_day)
    trade = t.txn_type.isin(["Buy", "Sell"])
    flag = trade & (trd == "0")
    print(f"  before: {trade.sum():,} Buys/Sells, {flag.sum():,} on non-trading days")
    t["non_trading_day"] = flag.astype(int)
    print(f"  after : non_trading_day = 1 on {t.non_trading_day.sum():,} rows; on non-Buy/Sell rows = "
          f"{t.non_trading_day[~trade].sum()}")
    assert t.non_trading_day.sum() == flag.sum() and t.non_trading_day[~trade].sum() == 0
    A.note("fact_transactions", "Buys/Sells on weekends", "flag", int(flag.sum()),
           "non_trading_day; dates kept (moving them would invent dates)")


def step_after_closed(T, A):
    banner("Inactive clients transacting after their last snapshot — flag  [decision #18]")
    t, c, p = T["fact_transactions"], T["dim_client"], T["fact_portfolio_snapshot"]
    inactive = set(c.client_id[c.is_active == "False"])
    last = p.groupby("client_id").snapshot_date.max().str[:7]
    lm = t.client_id.map(last)
    flag = t.client_id.isin(inactive) & lm.notna() & (t.txn_date.str[:7] > lm)
    print(f"  before: {len(inactive)} inactive clients; {flag.sum():,} transactions after their last snapshot month")
    # reconcile: fees (the other monthly fact) must stop with the snapshots for these clients
    f = T["fact_fees"]
    fl = f.client_id.map(last)
    assert not (f.client_id.isin(inactive) & (f.fee_date.str[:7] > fl)).any(), "fees continue after the last snapshot"
    print("  reconcile: no inactive client has a fee after their last snapshot, so the snapshot end date is consistent")
    t["after_account_closed"] = flag.astype(int)
    print(f"  after : after_account_closed = 1 on {t.after_account_closed.sum():,} rows "
          f"({t.client_id[flag].nunique()} clients); by type {t.txn_type[flag].value_counts().to_dict()}")
    assert t.after_account_closed.sum() == flag.sum()
    assert not (t.after_account_closed.astype(bool) & ~t.client_id.isin(inactive)).any()
    A.note("fact_transactions", "Inactive clients still transacting", "flag", int(flag.sum()),
           "after_account_closed; rows kept (some may be genuine closing transactions)")


def step_leave_as_is(T, A):
    banner("Decisions with no data change — recorded for the audit trail")
    items = [
        ("dim_advisor", "'None' in certifications (#6)", "means no certification; must stay text"),
        ("fact_fees", "Two near-identical fees (#10)", "different months; values match because of the floor"),
        ("fact_transactions", "Same-day deposit/withdrawal pairs (#13)", "separate transactions with different amounts"),
        ("fact_transactions", "Advisory Fee transactions vs fact_fees (#15)", "use fact_fees for revenue"),
        ("fact_transactions", "Sells exceed shares bought (#17)", "do not calculate holdings from transactions"),
        ("fact_portfolio_snapshot", "AUM excludes deposits/withdrawals (#19)", "do not combine AUM with cash flows"),
    ]
    for t, issue, note in items:
        print(f"  {t:<26} {issue} — {note}")
        A.note(t, issue, "leave as is", 0, note)


# ════════════════════════════════════════════════════════════════════
# Final checks, outputs
# ════════════════════════════════════════════════════════════════════

FLAGS = {
    "dim_client": ["risk_profile_missing"],
    "fact_fees": ["aum_at_floor"],
    "fact_portfolio_snapshot": ["aum_at_floor", "return_extreme", "fee_missing"],
    "fact_transactions": ["shares_sign_fixed", "non_trading_day", "after_account_closed"],
}


def final_checks(raw, T, A):
    banner("Final checks on the clean tables")
    # 1. row reconciliation
    print("  Rows: raw = clean + quarantined")
    for t in TABLES:
        q = sum(len(df) for (tab, df) in A.quarantine.values() if tab == t)
        print(f"    {t:<26} {len(raw[t]):>9,} = {len(T[t]):>9,} + {q:>4}")
        assert len(raw[t]) == len(T[t]) + q, f"row counts do not reconcile for {t}"
        A.note(t, "Row reconciliation", "check", 0, f"raw {len(raw[t])} = clean {len(T[t])} + quarantined {q}")
    # 2. same columns, plus only the declared flags
    for t in TABLES:
        added = [c for c in T[t].columns if c not in raw[t].columns]
        assert list(T[t].columns[:raw[t].shape[1]]) == list(raw[t].columns), f"column order changed in {t}"
        assert added == FLAGS.get(t, []), f"unexpected columns in {t}: {added}"
        for fcol in added:
            assert set(T[t][fcol].unique()) <= {0, 1}, f"{t}.{fcol} is not 0/1"
    # 3. primary keys unique, every FK resolves
    for t in TABLES:
        assert T[t][PK[t]].is_unique and (T[t][PK[t]] != "").all(), f"PK problem in {t}"
    fks = [("dim_client", "advisor_id", "dim_advisor"), ("dim_security", "benchmark_id", "dim_benchmark"),
           ("fact_fees", "client_id", "dim_client"), ("fact_fees", "advisor_id", "dim_advisor"),
           ("fact_portfolio_snapshot", "client_id", "dim_client"), ("fact_portfolio_snapshot", "advisor_id", "dim_advisor"),
           ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark"), ("fact_transactions", "client_id", "dim_client"),
           ("fact_transactions", "advisor_id", "dim_advisor"), ("fact_transactions", "security_id", "dim_security")]
    for t, col, parent in fks:
        v = T[t][col][T[t][col] != ""]
        assert v.isin(set(T[parent][PK[parent]])).all(), f"{t}.{col} has keys missing from {parent}"
    for t, col in [("fact_fees", "fee_date"), ("fact_portfolio_snapshot", "snapshot_date"),
                   ("fact_transactions", "txn_date")]:
        assert T[t][col].isin(set(T["dim_date"].date)).all(), f"{t}.{col} not in dim_date"
    print("  Primary keys unique; all 13 foreign keys resolve (incl. dates → dim_date)")
    # 4. numeric columns parse cleanly
    numeric = {"fact_portfolio_snapshot": ["aum", "return_ytd", "benchmark_return_ytd", "active_alpha_ytd", "cash_pct"],
               "fact_fees": ["aum_basis", "bps_charged", "amount"], "fact_transactions": ["amount"],
               "dim_client": ["age", "initial_aum"]}
    for t, cols in numeric.items():
        for col in cols:
            assert num(T[t][col]).notna().all(), f"{t}.{col} does not parse as a number"
    assert (num(T["fact_transactions"].shares.replace("", np.nan).dropna()) > 0).all()
    print("  All numeric columns parse; no negative shares")


def write_outputs(raw, T, A):
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    for t in TABLES:
        T[t].to_csv(CLEAN_DIR / f"{t}.csv", index=False)
    pd.DataFrame(A.log).to_csv(AUDIT_DIR / "cleaning_log.csv", index=False)
    pd.concat(A.changes, ignore_index=True).to_csv(AUDIT_DIR / "value_changes.csv", index=False)
    for name, (_, q) in A.quarantine.items():
        q.to_csv(AUDIT_DIR / f"quarantine_{name}.csv", index=False)
    (CLEAN_DIR / "README_clean.md").write_text(readme(raw, T, A), encoding="utf-8")
    # raw files untouched
    for t in TABLES:
        again = pd.read_csv(RAW_DIR / f"{t}.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
        assert again.equals(raw[t]), f"raw file {t}.csv changed"
    print(f"\nWrote {len(TABLES)} clean tables + README to {CLEAN_DIR.relative_to(HW_DIR)}/")
    print(f"Wrote audit files to {AUDIT_DIR.relative_to(HW_DIR)}/: cleaning_log.csv, value_changes.csv, "
          + ", ".join(f"quarantine_{n}.csv" for n in A.quarantine))
    print("Raw files re-read and confirmed unchanged.")


def readme(raw, T, A):
    p, t, c, f = T["fact_portfolio_snapshot"], T["fact_transactions"], T["dim_client"], T["fact_fees"]
    rows = "\n".join(f"| `{n}.csv` | {len(raw[n]):,} | {len(T[n]):,} | "
                     f"{sum(len(q) for (tb, q) in A.quarantine.values() if tb == n):,} |" for n in TABLES)
    return f"""# Wildcat Capital — Clean Data

Produced by `scripts/02_clean.py` from the raw files in `Wildcat Capital/` (never modified).
Every change is explained in `decision_log.md` and recorded in `data/audit/`.

## Files

| File | Raw rows | Clean rows | Quarantined |
|---|---|---|---|
{rows}

Quarantined rows are in `data/audit/quarantine_dim_client_duplicates.csv` and
`data/audit/quarantine_fact_transactions_orphans.csv`, each with the ID of the original row it copies.

## Relationships (star schema)

| From (many) | To (one) | Key |
|---|---|---|
| `fact_portfolio_snapshot`, `fact_fees`, `fact_transactions` | `dim_client` | `client_id` |
| `fact_portfolio_snapshot`, `fact_fees`, `fact_transactions`, `dim_client` | `dim_advisor` | `advisor_id` |
| `fact_portfolio_snapshot`, `dim_security` | `dim_benchmark` | `benchmark_id` |
| `fact_transactions` | `dim_security` | `security_id` (blank on Deposit / Withdrawal / Advisory Fee rows) |
| `fact_portfolio_snapshot.snapshot_date`, `fact_fees.fee_date`, `fact_transactions.txn_date` | `dim_date` | `date` |

`fact_fees` and `fact_portfolio_snapshot` are both one row per client per month (dated the 1st) and
can be matched on `client_id` + month. All keys resolve in the clean data (checked by the script).

## Column types for a BI tool

Set these explicitly; do not let the tool auto-detect.

| Type | Columns |
|---|---|
| **Text** (keep leading zeros / literal values) | `dim_client.zip_code`, `dim_advisor.certifications` ("None" is a real value, not null), all names, `state`, `ticker`, `ticker_proxy`, all category columns (`risk_profile`, `client_tier`, `primary_account_type`, `account_type`, `txn_type`, `fee_type`, `asset_class`, `sector`, `region`, `month_name`, `day_of_week`) |
| **Whole number** | all `*_id` columns (`security_id` must allow blanks), `age`, `years_experience`, `aum_target_mm`, `year`, `quarter`, `month`, `week_of_year` |
| **Decimal** | `initial_aum`, `aum`, `aum_basis`, `amount`, `price`, `shares`, `bps_charged`, `expense_ratio_bps` (blank for non-ETFs), `return_ytd`, `benchmark_return_ytd`, `active_alpha_ytd`, `cash_pct` (returns and cash are fractions: 0.0928 = 9.28%) |
| **Date** (YYYY-MM-DD) | `dim_date.date`, `client_since`, `snapshot_date`, `fee_date`, `txn_date` |
| **True/False text** | `dim_client.is_active`, `dim_security.is_etf` |
| **0/1 flags** | `is_month_end`, `is_quarter_end`, `is_year_end`, `is_trading_day`, and every flag column below |

Blanks are real: `sector` (non-equities), `expense_ratio_bps` (non-ETFs) and `security_id` / `shares` /
`price` (cash-flow rows) are blank by design. Treat them as null, never as 0.

## Flag columns added (0/1)

| Table | Flag | Rows = 1 | Meaning / how to use |
|---|---|---|---|
| `dim_client` | `risk_profile_missing` | {c.risk_profile_missing.sum():,} | Risk profile was blank and is now "Unknown". Treat their alpha with caution (benchmark is a default). |
| `fact_portfolio_snapshot` | `aum_at_floor` | {p.aum_at_floor.sum():,} | AUM is exactly $1,000 (an artificial floor). Exclude from return and fee-rate analysis. |
| `fact_portfolio_snapshot` | `return_extreme` | {p.return_extreme.sum():,} | YTD return < −90% or > +100%. Exclude from return, alpha and advisor-performance averages. |
| `fact_portfolio_snapshot` | `fee_missing` | {p.fee_missing.sum():,} | No fee recorded in `fact_fees` for this client-month. Revenue for these months is unknown. |
| `fact_fees` | `aum_at_floor` | {f.aum_at_floor.sum():,} | Fee calculated on the $1,000 floor AUM. Exclude from fee-rate analysis. |
| `fact_transactions` | `shares_sign_fixed` | {t.shares_sign_fixed.sum():,} | Buy had negative shares; the minus sign was removed (amount confirmed = shares × price). |
| `fact_transactions` | `non_trading_day` | {t.non_trading_day.sum():,} | Buy/Sell dated on a weekend. Exclude from daily analysis; fine for monthly totals. |
| `fact_transactions` | `after_account_closed` | {t.after_account_closed.sum():,} | Inactive client's transaction after their last snapshot month. Exclude from activity / active-client counts. |

## Known limitations (not fixed, with reasons)

| Limitation | Why it was not fixed | How to work with it |
|---|---|---|
| Advisory Fee transactions never match `fact_fees` ($263.7M vs $204.7M over five years) | No rule links the two; picking or rebuilding one would be a guess | Use `fact_fees` for revenue; treat fee transactions as cash leaving accounts only |
| AUM does not include deposits or withdrawals (AUM = last December AUM × (1 + YTD return)) | Changing AUM would break its agreement with returns, alpha and fees | Use AUM for balances, returns and fees; report deposits/withdrawals separately; never combine them |
| Sells often exceed shares bought (72% of sells take a holding below zero) | Each trade is valid on its own; the problem only appears when trades are added up | Don't calculate holdings or position P&L from transactions; use AUM |
| Dividend `amount` equals shares × price (the holding value), not the cash paid | No dividend rate exists to recompute it | Don't sum dividend amounts as income |
| `fact_fees` is missing ~5.7% of client-months (flagged `fee_missing`) | Inventing fees would mean guessing rate and fee type | State that revenue from `fact_fees` is understated |
| `dim_date` has no public holidays (`is_trading_day` = weekdays only) | No holiday list in the data | Some holiday trades are not flagged `non_trading_day` |
| Benchmark for "Unknown" risk-profile clients is the 60/40 Blend default | The true profile is unknown | Filter `risk_profile_missing = 1` when ranking performance vs benchmark |
| `dim_advisor.aum_target_mm` is far from actual books for 24 of 25 advisors | Targets are business inputs, not data errors | Don't use targets to judge advisors |
| Same-day deposits/withdrawals and repeated fee amounts on different dates | Different amounts or dates mean separate, plausible transactions | None needed |
"""


def main():
    raw = load()
    print("Loaded raw tables (as text):")
    for t in TABLES:
        print(f"  {t:<26} {len(raw[t]):>9,} rows × {raw[t].shape[1]} cols")
    T = {t: df.copy() for t, df in raw.items()}
    A = Audit()
    # remove copied rows first, so no fix is applied to a row that is then quarantined
    step_duplicate_clients(T, A)
    step_orphan_txns(T, A)
    step_state(T, A)
    step_return_pct(T, A)
    step_security_id(T, A)
    step_negative_shares(T, A)
    step_risk_profile(T, A)
    step_security_name(T, A)
    step_floor(T, A)
    step_extreme_returns(T, A)
    step_fee_missing(T, A)
    step_non_trading(T, A)
    step_after_closed(T, A)
    step_leave_as_is(T, A)
    final_checks(raw, T, A)
    write_outputs(raw, T, A)
    print(f"\nDone: {len(A.log)} log entries, {sum(len(c) for c in A.changes):,} value changes, "
          f"{sum(len(q) for _, q in A.quarantine.values())} rows quarantined.")


if __name__ == "__main__":
    main()
