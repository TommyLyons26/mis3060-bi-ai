"""
01_profile.py — Raw data profiling and data-quality checks.

Reads every CSV as TEXT (dtype=str, keep_default_na=False) so nothing is
silently converted, then:

  Part A  Generic column profile (works on any table)
          -> reports/profile_raw.csv
  Part B  Data-quality checks in four groups, each finding tagged
          ERROR / WARN / INFO
            1 Column level       type, allowed values, ranges, key uniqueness
            2 Single-table       duplicates, near-duplicates, row contradictions
            3 Referential        every FK points to an existing PK
            4 Cross-table        facts vs dimensions, facts vs facts
          -> reports/dq_summary_raw.csv

The profiler and the generic checks (types, whitespace, null tokens, PK/FK
inference, duplicates, near-duplicates) need no configuration. The
Wildcat Capital business rules live in the CONFIG section; any rule whose
tables or columns are absent is skipped, so the script runs on any folder
of CSVs.

Usage
  python scripts/01_profile.py                      # hw04/Wildcat Capital
  python scripts/01_profile.py --data some/folder   # any folder of CSVs
  python scripts/01_profile.py a.csv b.csv          # specific files
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HW_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA = HW_DIR / "Wildcat Capital"
DEFAULT_OUT = HW_DIR / "reports"

# ════════════════════════════════════════════════════════════════════
# Loading — the assignment rule: everything is text until converted on purpose
# ════════════════════════════════════════════════════════════════════


def table_name(path: Path) -> str:
    """'dim_client (1).csv' -> 'dim_client' (strips browser download suffixes)."""
    return re.sub(r"\s*\(\d+\)$", "", path.stem).strip()


def load_tables(paths: list[Path]) -> dict[str, pd.DataFrame]:
    tables = {}
    for p in sorted(paths):
        df = pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        tables[table_name(p)] = df
    return tables


# ════════════════════════════════════════════════════════════════════
# Value classification (applied to unique values only, for speed)
# ════════════════════════════════════════════════════════════════════

NULL_TOKENS = {"none", "null", "nan", "na", "n/a", "nil", "#n/a", "-", "--", "?",
               "missing", "undefined", "unknown"}
BOOL_WORDS = {"true", "false", "yes", "no", "t", "f", "y", "n"}

# Order = priority (first match wins).
FORMAT_PATTERNS = [
    ("int",          r"[+-]?\d+"),
    ("int_float",    r"[+-]?\d+\.0+"),
    ("decimal",      r"[+-]?(\d+\.\d*|\.\d+)"),
    ("sci",          r"[+-]?(\d+\.?\d*|\.\d+)[eE][+-]?\d+"),
    ("thousands",    r"[+-]?\d{1,3}(,\d{3})+(\.\d+)?"),
    ("percent",      r"[+-]?(\d+\.?\d*|\.\d+)\s*%"),
    ("currency",     r"[+-]?\$\s?[\d,]*\.?\d+|\(\$?[\d,]*\.?\d+\)"),
    ("date_iso",     r"\d{4}-\d{2}-\d{2}"),
    ("datetime_iso", r"\d{4}-\d{2}-\d{2}[ T]\d{1,2}:\d{2}(:\d{2})?(\.\d+)?Z?"),
    ("date_us",      r"\d{1,2}/\d{1,2}/\d{2,4}"),
    ("date_dmy_txt", r"\d{1,2}[- ][A-Za-z]{3}[- ]\d{2,4}"),
    ("date_compact", r"(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])"),
]
NUMBER_PLAIN = {"int", "int_float", "decimal", "sci"}
NUMBER_FMT = {"thousands", "percent", "currency"}
DATE_FMTS = {"date_iso", "datetime_iso", "date_us", "date_dmy_txt"}
DATE_PARSE_FMT = {"date_iso": "%Y-%m-%d", "date_us": "%m/%d/%Y", "date_dmy_txt": "%d-%b-%Y"}


def classify(u: pd.Series) -> pd.Series:
    """Format class for each (stripped) unique value."""
    out = pd.Series("text", index=u.index, dtype=object)
    lower = u.str.lower()
    done = pd.Series(False, index=u.index)
    for name, mask in [("blank", u == ""), ("null_token", lower.isin(NULL_TOKENS)),
                       ("bool", lower.isin(BOOL_WORDS))]:
        m = mask & ~done
        out[m] = name
        done |= m
    for name, pat in FORMAT_PATTERNS:
        m = u.str.fullmatch(pat) & ~done
        out[m] = name
        done |= m
    # 8-digit compact dates only count as dates if nothing else claimed them;
    # plain 8-digit ints were already classed "int", which is the safer default.
    return out


def shape_of(u: pd.Series) -> pd.Series:
    """Value shape: A=upper word, Aa=Capitalised word, a=lower word, 9=digit."""
    s = u.str.replace(r"[A-Z][a-z]+", "Aa", regex=True)
    s = s.str.replace(r"[A-Z]+", "A", regex=True)
    s = s.str.replace(r"[a-z]+", "a", regex=True)
    s = s.str.replace(r"\d", "9", regex=True)
    s = s.str.replace(r"9{7,}", lambda m: f"9{{{len(m.group())}}}", regex=True)
    return s.where(u != "", "<blank>")


# ════════════════════════════════════════════════════════════════════
# Explicit converters (used by profile min/max and by the business rules)
# ════════════════════════════════════════════════════════════════════


def to_num(s: pd.Series) -> pd.Series:
    """Numeric value of each cell; '9.28%' -> 0.0928, '$1,200' -> 1200, else NaN."""
    t = s.str.strip()
    neg_paren = t.str.fullmatch(r"\(.*\)")
    t = t.str.replace(r"[\$,()\s]", "", regex=True)
    pct = t.str.endswith("%")
    v = pd.to_numeric(t.str.rstrip("%"), errors="coerce")
    v = v.where(~pct, v / 100)
    return v.where(~neg_paren, -v)


def to_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.str.strip(), format="%Y-%m-%d", errors="coerce")


def canon_key(s: pd.Series) -> pd.Series:
    """Key as it would join after a deliberate cleanup: trimmed, '45.0' -> '45'."""
    t = s.str.strip()
    return t.str.replace(r"^([+-]?\d+)\.0+$", r"\1", regex=True)


def to_bool(s: pd.Series) -> pd.Series:
    m = {"true": True, "1": True, "yes": True, "y": True, "t": True,
         "false": False, "0": False, "no": False, "n": False, "f": False}
    return s.str.strip().str.lower().map(m)


# ════════════════════════════════════════════════════════════════════
# Part A — generic column profile
# ════════════════════════════════════════════════════════════════════


def infer_type(col: str, cls_counts: pd.Series, uniq: pd.DataFrame) -> str:
    present = cls_counts.drop(["blank", "null_token"], errors="ignore")
    n = present.sum()
    if n == 0:
        return "empty"
    share = lambda keys: present[present.index.isin(keys)].sum() / n
    vals = set(uniq.loc[uniq.cls.isin(["int"]), "v"])
    flag_name = re.match(r"^(is|has|flag)_", col.lower()) is not None
    if share({"bool"}) >= 0.9 or (flag_name and share({"int", "bool"}) == 1 and vals <= {"0", "1"}):
        return "boolean"
    if share(DATE_FMTS) >= 0.9:
        return "date"
    if share(NUMBER_PLAIN | NUMBER_FMT) >= 0.9:
        ints = uniq[uniq.cls == "int"].v
        if ints.str.match(r"^0\d").any():
            return "code"                       # numeric-looking but leading zeros matter
        if share({"int", "int_float"}) == 1:
            return "identifier" if re.search(r"(^|_)id$", col.lower()) else "integer"
        return "decimal"
    n_distinct = uniq.loc[~uniq.cls.isin(["blank", "null_token"])].shape[0]
    return "categorical" if n_distinct <= 50 else "text"


OK_CLASSES = {
    "identifier": {"int"},          # '45.0' is a mixed format that breaks string joins
    "integer": {"int", "int_float"},
    "decimal": NUMBER_PLAIN,
    "code": {"int"},
    "boolean": {"bool", "int"},
}


def profile_column(table: str, col: str, ordinal: int, s: pd.Series) -> tuple[dict, pd.DataFrame]:
    vc = s.value_counts(sort=False)
    uniq = pd.DataFrame({"raw": vc.index.astype(str), "n": vc.values})
    uniq["v"] = uniq.raw.str.strip()
    uniq["cls"] = classify(uniq.v)
    n_rows = len(s)
    cls_counts = uniq.groupby("cls").n.sum()
    typ = infer_type(col, cls_counts, uniq)

    blank = uniq.cls == "blank"
    nulltok = uniq.cls == "null_token"
    present = ~blank & ~nulltok
    pres = uniq[present]
    n_present = int(pres.n.sum())

    # parse failures against the inferred type
    if typ in OK_CLASSES:
        ok = pres.cls.isin(OK_CLASSES[typ])
        if typ == "boolean":
            ok &= pres.v.str.lower().isin(BOOL_WORDS | {"0", "1"})
    elif typ == "date":
        dom = pres[pres.cls.isin(DATE_FMTS)].groupby("cls").n.sum().idxmax()
        fmt = DATE_PARSE_FMT.get(dom)
        parsed = pd.to_datetime(pres.v, format=fmt, errors="coerce") if fmt else \
            pd.to_datetime(pres.v, errors="coerce")
        ok = (pres.cls == dom) & parsed.notna()
    else:
        ok = pd.Series(True, index=pres.index)
    fails = pres[~ok]
    n_fail = int(fails.n.sum())

    # mixed formats (number formats collapse to 'number' for decimal columns)
    fam = pres.cls.copy()
    if typ == "decimal":
        fam = fam.replace({c: "number" for c in NUMBER_PLAIN})
    fmt_counts = pres.groupby(fam).n.sum().sort_values(ascending=False)
    formats = "; ".join(f"{k}={v}" for k, v in fmt_counts.items())

    # whitespace
    lead_trail = uniq.raw != uniq.raw.str.strip()
    ws_only = lead_trail & (uniq.v == "")
    internal = uniq.v.str.contains(r"\S\s{2,}\S", regex=True)
    odd_ws = uniq.raw.str.contains(r"[\t\r\n ​]", regex=True)

    # shapes
    uniq["shape"] = shape_of(uniq.v)
    shp = uniq.groupby("shape").n.sum().sort_values(ascending=False)
    top_shapes = "; ".join(f"{k} ({v / n_rows:.1%})" for k, v in shp.head(3).items())
    top_vals = pres.sort_values("n", ascending=False).head(3)
    top_values = "; ".join(f"{r.v} ({r.n})" for r in top_vals.itertuples())

    # numeric / date ranges (explicit conversion of the values that can be read)
    num_min = num_max = num_mean = date_min = date_max = ""
    if typ in {"integer", "decimal", "identifier"}:
        nums = to_num(pres.v)
        w = pres.n[nums.notna()]
        if len(w):
            num_min, num_max = nums.min(), nums.max()
            num_mean = round(float(np.average(nums.dropna(), weights=w)), 6)
    if typ == "date":
        d = pd.to_datetime(pres.v, format=DATE_PARSE_FMT.get(dom), errors="coerce")
        if d.notna().any():
            date_min, date_max = d.min().date().isoformat(), d.max().date().isoformat()

    lens = pres.v.str.len()
    row = dict(
        table=table, column=col, ordinal=ordinal, n_rows=n_rows, inferred_type=typ,
        n_blank=int(uniq.n[blank].sum()),
        n_null_token=int(uniq.n[nulltok].sum()),
        null_tokens_found="; ".join(sorted(set(uniq.v[nulltok]))),
        pct_missing=round((uniq.n[blank | nulltok].sum()) / n_rows, 6) if n_rows else 0,
        n_distinct=int(present.sum()),
        pct_distinct=round(present.sum() / n_present, 6) if n_present else 0,
        is_unique=bool(n_present == n_rows and uniq.n.max() == 1),
        top_shapes=top_shapes,
        top_values=top_values,
        n_fail_parse=n_fail,
        pct_fail_parse=round(n_fail / n_present, 6) if n_present else 0,
        fail_examples="; ".join(fails.sort_values("n", ascending=False).v.head(5)),
        formats_found=formats,
        is_mixed_format=len(fmt_counts) > 1,
        n_ws_leading_trailing=int(uniq.n[lead_trail].sum()),
        n_ws_only=int(uniq.n[ws_only].sum()),
        n_ws_internal_multi=int(uniq.n[internal].sum()),
        n_ws_tab_nbsp=int(uniq.n[odd_ws].sum()),
        n_case_variants=int(pres.assign(k=pres.v.str.lower()).groupby("k").v.nunique().gt(1).sum())
        if typ in {"categorical", "text"} else 0,
        n_leading_zero=int(pres.n[pres.v.str.match(r"^[+-]?0\d")].sum()),
        min_len=int(lens.min()) if len(lens) else "",
        max_len=int(lens.max()) if len(lens) else "",
        num_min=num_min, num_max=num_max, num_mean=num_mean,
        date_min=date_min, date_max=date_max,
    )
    return row, uniq


def profile_all(tables):
    rows, details = [], {}
    for t, df in tables.items():
        for i, c in enumerate(df.columns, 1):
            row, uniq = profile_column(t, c, i, df[c])
            rows.append(row)
            details[(t, c)] = uniq
    return pd.DataFrame(rows), details


# ════════════════════════════════════════════════════════════════════
# CONFIG — Wildcat Capital expectations (skipped automatically if absent)
# ════════════════════════════════════════════════════════════════════

DATA_START, DATA_END = "2020-01-01", "2024-12-31"
US_STATES = set("""AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO
MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC""".split())
RISK_PROFILES = ["Conservative", "Moderately Conservative", "Balanced",
                 "Moderately Aggressive", "Aggressive"]
ACCOUNT_TYPES = {"Taxable", "IRA", "Roth IRA", "Trust", "529"}
TF = {"True", "False"}
FLAG01 = {"0", "1"}

TABLE_SPECS = {
    "dim_advisor":   dict(pk="advisor_id"),
    "dim_benchmark": dict(pk="benchmark_id", natural_keys=[["name"], ["ticker_proxy"]]),
    "dim_client":    dict(pk="client_id"),
    "dim_date":      dict(pk="date_id", natural_keys=[["date"]]),
    "dim_security":  dict(pk="security_id", natural_keys=[["ticker"]]),
    "fact_fees":     dict(pk="fee_id", natural_keys=[["client_id", "fee_date"]]),
    "fact_portfolio_snapshot": dict(pk="snapshot_id", natural_keys=[["client_id", "snapshot_date"]]),
    "fact_transactions": dict(pk="txn_id"),
}

# type: expected type (compared with the inferred one); required: severity if blank;
# allowed / allowed_tokens / regex / min / max: domain checks (ERROR unless sev given)
C = dict
COLUMN_SPECS = {
    "dim_advisor": {
        "first_name": C(required="ERROR"), "last_name": C(required="ERROR"),
        "region": C(allowed={"Northeast", "Mid-Atlantic", "Southeast", "Midwest", "Southwest", "West"}),
        "years_experience": C(type="integer", min=0, max=60),
        "aum_target_mm": C(type="integer", min=1, max=10_000),
        "certifications": C(allowed_tokens={"CFA", "CFP", "CIMA", "ChFC", "CPA", "CPWA", "None"}),
    },
    "dim_benchmark": {
        "name": C(required="ERROR"),
        "asset_class": C(allowed={"Equity", "Fixed Income", "Multi-Asset", "International",
                                  "Small Cap", "Emerging", "Cash"}),
        "ticker_proxy": C(regex=r"[A-Z0-9_]{2,12}"),
    },
    "dim_client": {
        "first_name": C(required="ERROR"), "last_name": C(required="ERROR"),
        "age": C(type="integer", min=18, max=110),
        "state": C(allowed=US_STATES),
        "zip_code": C(type="code", regex=r"\d{5}"),
        "risk_profile": C(allowed=set(RISK_PROFILES), required="WARN"),
        "client_tier": C(allowed={"Retail", "HNW", "UHNW"}),
        "primary_account_type": C(allowed=ACCOUNT_TYPES),
        "initial_aum": C(type="decimal", min=0.01),
        "client_since": C(type="date", min="1950-01-01", max=DATA_END),
        "advisor_id": C(type="identifier", required="ERROR"),
        "is_active": C(allowed=TF),
    },
    "dim_date": {
        "date": C(type="date", required="ERROR"),
        "year": C(type="integer", min=1900, max=2100),
        "quarter": C(type="integer", min=1, max=4),
        "month": C(type="integer", min=1, max=12),
        "month_name": C(allowed={"January", "February", "March", "April", "May", "June", "July",
                                 "August", "September", "October", "November", "December"}),
        "week_of_year": C(type="integer", min=1, max=53),
        "day_of_week": C(allowed={"Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                                  "Saturday", "Sunday"}),
        "is_month_end": C(allowed=FLAG01), "is_quarter_end": C(allowed=FLAG01),
        "is_year_end": C(allowed=FLAG01), "is_trading_day": C(allowed=FLAG01),
    },
    "dim_security": {
        "ticker": C(regex=r"[A-Z]{1,5}", required="ERROR"),
        "name": C(required="ERROR"),
        "asset_class": C(allowed={"Equity", "Fixed Income", "Alternative", "Cash Equivalent"}),
        "sector": C(allowed={"Communication Services", "Consumer Discretionary", "Consumer Staples",
                             "Energy", "Financials", "Healthcare", "Industrials", "Materials",
                             "Real Estate", "Technology", "Utilities"}),
        "benchmark_id": C(type="identifier", required="ERROR"),
        "is_etf": C(allowed=TF),
        "expense_ratio_bps": C(type="decimal", min=0, max=300),
    },
    "fact_fees": {
        "client_id": C(required="ERROR"), "advisor_id": C(required="ERROR"),
        "fee_date": C(type="date", min=DATA_START, max=DATA_END, required="ERROR"),
        "fee_type": C(allowed={"Advisory", "Management", "Custodial", "Performance"}),
        "aum_basis": C(type="decimal", min=0),
        "bps_charged": C(type="decimal", min=0, max=300),
        "amount": C(type="decimal", min=0, required="ERROR"),
    },
    "fact_portfolio_snapshot": {
        "client_id": C(required="ERROR"), "advisor_id": C(required="ERROR"),
        "benchmark_id": C(required="ERROR"),
        "snapshot_date": C(type="date", min=DATA_START, max=DATA_END, required="ERROR"),
        "year": C(type="integer", min=2020, max=2024),
        "month": C(type="integer", min=1, max=12),
        "aum": C(type="decimal", min=0, required="ERROR"),
        "return_ytd": C(type="decimal", min=-1.0),
        "benchmark_return_ytd": C(type="decimal", min=-1.0, max=2.0),
        "active_alpha_ytd": C(type="decimal"),
        "cash_pct": C(type="decimal", min=0, max=1),
        "account_type": C(allowed=ACCOUNT_TYPES),
    },
    "fact_transactions": {
        "client_id": C(required="ERROR"), "advisor_id": C(required="ERROR"),
        "security_id": C(type="identifier"),
        "txn_date": C(type="date", min=DATA_START, max=DATA_END, required="ERROR"),
        "txn_type": C(allowed={"Buy", "Sell", "Dividend", "Deposit", "Withdrawal", "Advisory Fee"}),
        "shares": C(type="decimal"),
        "price": C(type="decimal", min=0.01),
        "amount": C(type="decimal", min=0.01, required="ERROR"),
    },
}

# FK pairs beyond the automatic "<pk name> in another table" inference
EXTRA_FKS = [
    ("fact_fees", "fee_date", "dim_date", "date"),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date"),
    ("fact_transactions", "txn_date", "dim_date", "date"),
]
# FKs that may legitimately be blank (row rules check *when* blank is allowed)
NULLABLE_FKS = {("fact_transactions", "security_id")}

# ════════════════════════════════════════════════════════════════════
# Findings engine
# ════════════════════════════════════════════════════════════════════

GROUPS = {1: "1-Column", 2: "2-Single-table", 3: "3-Referential", 4: "4-Cross-table"}
SEV_ORDER = {"ERROR": 0, "WARN": 1, "INFO": 2}


class Findings:
    def __init__(self, tables):
        self.T = tables
        self.rows = []

    def pk(self, t):
        return pk_of(t, self.T[t])

    def add(self, group, sev, table, column, rule, n_failed, n_checked,
            examples="", detail="", status=None):
        if status is None:
            status = "FINDING" if n_failed else "PASS"
        self.rows.append(dict(
            group=GROUPS[group], severity=sev, status=status, table=table, column=column,
            rule=rule, n_failed=int(n_failed), n_checked=int(n_checked),
            pct_failed=round(n_failed / n_checked, 6) if n_checked else 0.0,
            examples=examples, detail=detail))

    def mask(self, group, sev, table, column, rule, df, fail, checked=None,
             show=None, detail=""):
        """Record a row-level check: `fail` is a boolean mask over df."""
        fail = pd.Series(fail, index=df.index).fillna(False).astype(bool)
        checked = pd.Series(True, index=df.index) if checked is None else \
            pd.Series(checked, index=df.index).fillna(False).astype(bool)
        fail &= checked
        self.add(group, sev, table, column, rule, fail.sum(), checked.sum(),
                 examples_of(df[fail], self.pk(table) if table in self.T else None, show),
                 detail)

    def frame(self):
        df = pd.DataFrame(self.rows)
        df.insert(0, "check_id", [f"DQ{i:03d}" for i in range(1, len(df) + 1)])
        df["_s"] = df.status.map({"FINDING": 0, "SKIPPED": 1, "PASS": 2})
        df["_v"] = df.severity.map(SEV_ORDER)
        df = df.sort_values(["_s", "_v", "group", "table", "check_id"]).drop(columns=["_s", "_v"])
        return df


def examples_of(df, pk=None, show=None, k=5):
    if df.empty:
        return ""
    cols = [c for c in (show or []) if c in df.columns]
    out = []
    for _, r in df.head(k).iterrows():
        key = f"{pk}={r[pk]}" if pk and pk in df.columns else f"row {r.name}"
        vals = ", ".join(f"{c}={r[c]!r}" for c in cols)
        out.append(f"{key}" + (f" [{vals}]" if vals else ""))
    return " | ".join(out)


def pk_of(t, df):
    spec = TABLE_SPECS.get(t, {})
    if spec.get("pk") in df.columns:
        return spec["pk"]
    first = df.columns[0]
    if re.search(r"id$", first.lower()) and df[first].is_unique:
        return first
    return None


# ════════════════════════════════════════════════════════════════════
# Group 1 — column level
# ════════════════════════════════════════════════════════════════════


def column_checks(F: Findings, prof: pd.DataFrame, details):
    for p in prof.itertuples():
        t, c, df = p.table, p.column, F.T[p.table]
        spec = COLUMN_SPECS.get(t, {}).get(c, {})
        s = df[c]
        stripped = s.str.strip()
        present = (stripped != "") & ~stripped.str.lower().isin(NULL_TOKENS)
        pk = F.pk(t)
        is_key = c == pk or c.lower().endswith("_id")

        # type: inferred vs expected
        exp = spec.get("type")
        compatible = {("decimal", "integer"), ("integer", "identifier"), ("identifier", "integer")}
        if exp and exp != p.inferred_type and (exp, p.inferred_type) not in compatible:
            sev = "ERROR" if exp in {"integer", "decimal", "date", "identifier"} else "WARN"
            F.add(1, sev, t, c, f"Inferred type '{p.inferred_type}' differs from expected '{exp}'",
                  1, 1, detail=f"formats: {p.formats_found}")
        typ = exp or p.inferred_type

        # parse failures as the expected type
        if typ in OK_CLASSES or typ == "date":
            uniq = details[(t, c)]
            pres = uniq[~uniq.cls.isin(["blank", "null_token"])]
            if typ == "date":
                ok = (pres.cls == "date_iso") & to_date(pres.v).notna()
            else:
                ok = pres.cls.isin(OK_CLASSES[typ])
            bad = set(pres.v[~ok])
            fail = present & stripped.isin(bad)
            classes = pres[~ok].groupby("cls").n.sum()
            mix = ", ".join(f"{k}={v}" for k, v in classes.items())
            int_float_only = set(classes.index) == {"int_float"}
            if int_float_only and typ == "identifier":
                sev, why = "ERROR", "IDs stored as '45.0': text join to '45' fails until cast to int"
            elif int_float_only:
                sev, why = "WARN", "integers written with '.0'"
            elif {"percent", "currency", "thousands"} & set(classes.index):
                sev, why = "ERROR", "formatted strings (%/$/,) mixed into a numeric column; pd.to_numeric fails"
            else:
                sev, why = "ERROR", "values do not parse as the expected type"
            F.mask(1, sev, t, c, f"Values parse as {typ}", df, fail, present, [c],
                   detail=f"{why}. Failing formats: {mix}" if mix else why)

        # whitespace
        ws = (s != stripped) | stripped.str.contains(r"\s{2,}|[\t ]", regex=True)
        F.mask(1, "WARN", t, c, "No leading/trailing/double/odd whitespace", df, ws, show=[c])

        # literal null tokens
        tok = stripped.str.lower().isin(NULL_TOKENS) & (stripped != "")
        if tok.any() or spec:
            F.mask(1, "WARN", t, c, "No literal null tokens (None/NULL/NA/...)", df, tok, show=[c],
                   detail="Decide on purpose whether the token means 'missing' or is a real value "
                          f"(found: {p.null_tokens_found})" if tok.any() else "")

        # required / blanks
        blank = stripped == ""
        if "required" in spec or c == pk:
            F.mask(1, "ERROR" if c == pk else spec["required"], t, c, "Not blank", df, blank)
        elif blank.any():
            F.add(1, "INFO", t, c, "Blank cells present (optional column)", int(blank.sum()), len(df),
                  detail="Blank is kept as '' when read as text; check in group 2 whether blanks are expected")

        # leading zeros
        if p.n_leading_zero and typ in {"code", "categorical", "text"}:
            F.add(1, "INFO", t, c, "Leading zeros present: keep as text", p.n_leading_zero,
                  len(df), detail="Default parsing would turn '03897' into 3897",
                  status="FINDING")

        # case variants in categoricals
        if p.n_case_variants:
            F.add(1, "WARN", t, c, "Same category spelled with different case", p.n_case_variants,
                  p.n_distinct)

        # allowed values
        if "allowed" in spec:
            bad = present & ~stripped.isin(spec["allowed"])
            top_bad = stripped[bad].value_counts().head(8)
            F.mask(1, spec.get("sev", "ERROR"), t, c, "Value in allowed set", df, bad, present, [c],
                   detail=("not allowed: " + "; ".join(f"{k} ({v})" for k, v in top_bad.items()))
                   if bad.any() else "allowed: " + ", ".join(sorted(spec["allowed"]))[:300])
        if "allowed_tokens" in spec:
            toks = stripped.str.split(r"\s*,\s*")
            bad = present & toks.apply(lambda x: not set(x) <= spec["allowed_tokens"])
            F.mask(1, "ERROR", t, c, "Every comma-separated token in allowed set", df, bad, present, [c])
        if "regex" in spec:
            bad = present & ~stripped.str.fullmatch(spec["regex"])
            F.mask(1, "ERROR", t, c, f"Matches pattern {spec['regex']}", df, bad, present, [c])

        # ranges
        if "min" in spec or "max" in spec:
            if typ == "date":
                v = to_date(s)
                lo = pd.Timestamp(spec["min"]) if "min" in spec else None
                hi = pd.Timestamp(spec["max"]) if "max" in spec else None
            else:
                v = to_num(s)
                lo, hi = spec.get("min"), spec.get("max")
            bad = pd.Series(False, index=df.index)
            if lo is not None:
                bad |= v < lo
            if hi is not None:
                bad |= v > hi
            F.mask(1, "ERROR", t, c, f"Within range [{spec.get('min', '-inf')}, {spec.get('max', 'inf')}]",
                   df, bad, v.notna(), [c])

        # key uniqueness
        if c == pk:
            dup = stripped.duplicated(keep=False) & present
            F.mask(1, "ERROR", t, c, "Primary key unique", df, dup, show=[c])

    # tables with no detectable PK
    for t, df in F.T.items():
        if F.pk(t) is None:
            F.add(1, "WARN", t, "", "Table has an identifiable primary key", 1, 1,
                  detail="No configured PK and first column is not a unique *id column")
        for keys in TABLE_SPECS.get(t, {}).get("natural_keys", []):
            if all(k in df.columns for k in keys):
                dup = df.duplicated(keys, keep=False)
                F.mask(1, "ERROR", t, "+".join(keys), "Natural/business key unique", df, dup, show=keys)


# ════════════════════════════════════════════════════════════════════
# Group 2 — single-table rules
# ════════════════════════════════════════════════════════════════════


def norm(df):
    return df.apply(lambda s: s.str.strip().str.lower())


def generic_single_table(F: Findings):
    for t, df in F.T.items():
        pk = F.pk(t)
        F.mask(2, "ERROR", t, "*", "No exact duplicate rows (all columns)", df,
               df.duplicated(keep=False))
        rest = [c for c in df.columns if c != pk]
        if pk and rest:
            n = norm(df[rest])
            dup = n.duplicated(keep=False)
            F.mask(2, "WARN", t, "*", f"No duplicate rows ignoring {pk} (trim/case-insensitive)",
                   df, dup, show=rest[:4])
            # near-duplicates: identical on every non-key column except exactly one
            if len(rest) >= 4:
                hits, why = pd.Series(False, index=df.index), {}
                for c in rest:
                    others = [x for x in rest if x != c]
                    m = n.duplicated(others, keep=False) & ~dup
                    if m.any():
                        # only count groups where the differing column really differs
                        g = n[m].groupby(others, dropna=False)[c].transform("nunique") > 1
                        m.loc[m] = g.values
                        why[c] = int(m.sum())
                        hits |= m
                F.mask(2, "WARN", t, "*", "No near-duplicate rows (same on all but one column)", df,
                       hits, show=list(why)[:3],
                       detail="differing column -> rows: " + ", ".join(f"{k}={v}" for k, v in why.items()))


ROW_RULES = []


def rule(group, sev, table, column, desc, needs=()):
    def deco(fn):
        ROW_RULES.append(dict(group=group, sev=sev, table=table, column=column, desc=desc,
                              needs=(table, *needs), fn=fn))
        return fn
    return deco


# ---- dim_advisor -----------------------------------------------------------
@rule(2, "INFO", "dim_advisor", "certifications", "'None' means no certification (not missing)")
def _(T):
    a = T["dim_advisor"]
    return a, a.certifications.str.strip() == "None", None, ["certifications"]


# ---- dim_client ------------------------------------------------------------
@rule(2, "WARN", "dim_client", "client_tier+initial_aum",
      "Tier agrees with initial AUM (Retail <$500k, HNW $500k–$5M, UHNW ≥$5M)")
def _(T):
    c = T["dim_client"]
    v = to_num(c.initial_aum)
    exp = pd.cut(v, [-np.inf, 500_000, 5_000_000, np.inf], right=False,
                 labels=["Retail", "HNW", "UHNW"]).astype(str)
    return c, exp != c.client_tier.str.strip(), v.notna(), ["client_tier", "initial_aum"]


@rule(2, "WARN", "dim_client", "age+client_since", "Client was ≥18 when the relationship started")
def _(T):
    c = T["dim_client"]
    start_age = to_num(c.age) - (pd.Timestamp(DATA_END).year - to_date(c.client_since).dt.year)
    return c, start_age < 18, start_age.notna(), ["age", "client_since"]


@rule(2, "WARN", "dim_client", "client_id",
      "No duplicate client records (same person, last name spelled differently)")
def _(T):
    c = T["dim_client"].copy()
    k = ["first_name", "age", "city", "zip_code", "initial_aum", "client_since"]
    g = c.groupby(k)
    c["_n_names"] = g.last_name.transform("nunique")
    c["_rank"] = g.client_id.transform(lambda x: canon_key(x).astype(int).rank(method="first"))
    c["kept_client_id"] = g.client_id.transform("first")
    # flag the later copy of each pair; the lowest client_id is treated as the original
    return c, (c._n_names > 1) & (c._rank > 1), None, ["first_name", "last_name", "kept_client_id"], \
        "Matching on first_name, age, city, zip, initial_aum and client_since; flagged row = higher client_id"


# ---- dim_date --------------------------------------------------------------
@rule(2, "ERROR", "dim_date", "year/quarter/month/month_name/day_of_week/week_of_year",
      "Calendar attributes agree with the date")
def _(T):
    d = T["dim_date"]
    dt = to_date(d.date)
    bad = ((dt.dt.year.astype("Int64").astype(str) != d.year)
           | (dt.dt.quarter.astype("Int64").astype(str) != d.quarter)
           | (dt.dt.month.astype("Int64").astype(str) != d.month)
           | (dt.dt.month_name() != d.month_name)
           | (dt.dt.day_name() != d.day_of_week)
           | (dt.dt.isocalendar().week.astype("Int64").astype(str) != d.week_of_year))
    return d, bad, dt.notna(), ["date", "year", "month", "day_of_week", "week_of_year"]


@rule(2, "ERROR", "dim_date", "is_month_end/is_quarter_end/is_year_end", "Period-end flags agree with the date")
def _(T):
    d = T["dim_date"]
    dt = to_date(d.date)
    f = lambda x: x.astype(int).astype(str)
    bad = ((f(dt.dt.is_month_end) != d.is_month_end) | (f(dt.dt.is_quarter_end) != d.is_quarter_end)
           | (f(dt.dt.is_year_end) != d.is_year_end))
    return d, bad, dt.notna(), ["date", "is_month_end", "is_quarter_end", "is_year_end"]


@rule(2, "ERROR", "dim_date", "is_trading_day", "Weekends are not trading days")
def _(T):
    d = T["dim_date"]
    dt = to_date(d.date)
    return d, (dt.dt.dayofweek >= 5) & (d.is_trading_day == "1"), dt.notna(), ["date", "day_of_week"]


@rule(2, "ERROR", "dim_date", "date", "Calendar is continuous (no missing days)")
def _(T):
    d = T["dim_date"].copy()
    dt = to_date(d.date).sort_values()
    gap = dt.diff().dt.days.reindex(d.index) > 1
    return d, gap, None, ["date"]


# ---- dim_security ----------------------------------------------------------
@rule(2, "ERROR", "dim_security", "is_etf+expense_ratio_bps", "ETFs have an expense ratio; single stocks do not")
def _(T):
    s = T["dim_security"]
    has = s.expense_ratio_bps.str.strip() != ""
    etf = to_bool(s.is_etf)
    return s, (etf & ~has) | (~etf.astype(bool) & has), etf.notna(), ["is_etf", "expense_ratio_bps"]


@rule(2, "ERROR", "dim_security", "asset_class+sector", "Equities have a sector; other asset classes do not")
def _(T):
    s = T["dim_security"]
    has = s.sector.str.strip() != ""
    eq = s.asset_class.str.strip() == "Equity"
    return s, (eq & ~has) | (~eq & has), None, ["asset_class", "sector"]


@rule(2, "WARN", "dim_security", "name", "Security name has no doubled suffix (e.g. 'Inc Inc.')")
def _(T):
    s = T["dim_security"]
    doubled = s.name.str.extract(r"\b(Inc|PLC|LLC|Ltd|Group)\b\.?\s+\1\b", expand=False).notna()
    return s, doubled, None, ["ticker", "name"]


@rule(2, "INFO", "dim_security", "name", "Security names are unique (different tickers may share a name)")
def _(T):
    s = T["dim_security"]
    return s, s.name.str.strip().duplicated(keep=False), None, ["ticker", "name", "asset_class"]


# ---- fact_fees -------------------------------------------------------------
@rule(2, "ERROR", "fact_fees", "amount", "amount = aum_basis × bps_charged / 10,000 / 12 (±$0.01)")
def _(T):
    f = T["fact_fees"]
    calc = to_num(f.aum_basis) * to_num(f.bps_charged) / 10_000 / 12
    a = to_num(f.amount)
    return f, (calc - a).abs() > 0.0101, calc.notna() & a.notna(), ["aum_basis", "bps_charged", "amount"]


@rule(2, "WARN", "fact_fees", "fee_date", "Fees are charged on the 1st of the month")
def _(T):
    f = T["fact_fees"]
    d = to_date(f.fee_date)
    return f, d.dt.day != 1, d.notna(), ["fee_date"]


@rule(2, "WARN", "fact_fees", "aum_basis", "AUM basis is not the $1,000 floor value")
def _(T):
    f = T["fact_fees"]
    return f, to_num(f.aum_basis) == 1000, None, ["client_id", "fee_date", "aum_basis", "amount"]


# ---- fact_portfolio_snapshot -----------------------------------------------
@rule(2, "ERROR", "fact_portfolio_snapshot", "year+month", "year and month agree with snapshot_date")
def _(T):
    p = T["fact_portfolio_snapshot"]
    d = to_date(p.snapshot_date)
    bad = (d.dt.year != to_num(p.year)) | (d.dt.month != to_num(p.month))
    return p, bad, d.notna(), ["snapshot_date", "year", "month"]


@rule(2, "ERROR", "fact_portfolio_snapshot", "active_alpha_ytd",
      "active_alpha_ytd = return_ytd − benchmark_return_ytd (±0.0001)")
def _(T):
    p = T["fact_portfolio_snapshot"]
    r, b, a = to_num(p.return_ytd), to_num(p.benchmark_return_ytd), to_num(p.active_alpha_ytd)
    return p, (r - b - a).abs() > 1e-4, r.notna() & b.notna() & a.notna(), \
        ["return_ytd", "benchmark_return_ytd", "active_alpha_ytd"]


@rule(2, "WARN", "fact_portfolio_snapshot", "return_ytd", "YTD return is plausible (between −90% and +100%)")
def _(T):
    p = T["fact_portfolio_snapshot"]
    r = to_num(p.return_ytd)
    return p, (r < -0.9) | (r > 1.0), r.notna(), ["client_id", "snapshot_date", "aum", "return_ytd"]


@rule(2, "WARN", "fact_portfolio_snapshot", "aum", "AUM is not the $1,000 floor value")
def _(T):
    p = T["fact_portfolio_snapshot"]
    return p, to_num(p.aum) == 1000, None, ["client_id", "snapshot_date", "aum", "return_ytd"]


@rule(2, "WARN", "fact_portfolio_snapshot", "snapshot_date", "Snapshots are dated the 1st of the month")
def _(T):
    p = T["fact_portfolio_snapshot"]
    d = to_date(p.snapshot_date)
    return p, d.dt.day != 1, d.notna(), ["snapshot_date"]


@rule(2, "ERROR", "fact_portfolio_snapshot", "client_id+snapshot_date",
      "Each client has an unbroken monthly series (no missing months)")
def _(T):
    p = T["fact_portfolio_snapshot"].copy()
    d = to_date(p.snapshot_date)
    p["_m"] = d.dt.year * 12 + d.dt.month
    g = p.groupby("client_id")["_m"]
    gaps = (g.transform("max") - g.transform("min") + 1) != g.transform("count")
    return p, gaps, d.notna(), ["client_id", "snapshot_date"]


# ---- fact_transactions -----------------------------------------------------
TRADE = {"Buy", "Sell", "Dividend"}
CASH = {"Deposit", "Withdrawal", "Advisory Fee"}


@rule(2, "ERROR", "fact_transactions", "security_id/shares/price",
      "Buy/Sell/Dividend rows have security, shares and price")
def _(T):
    t = T["fact_transactions"]
    trade = t.txn_type.isin(TRADE)
    miss = (t.security_id.str.strip() == "") | (t.shares.str.strip() == "") | (t.price.str.strip() == "")
    return t, miss, trade, ["txn_type", "security_id", "shares", "price"]


@rule(2, "ERROR", "fact_transactions", "security_id/shares/price",
      "Deposit/Withdrawal/Advisory Fee rows have no security, shares or price")
def _(T):
    t = T["fact_transactions"]
    cash = t.txn_type.isin(CASH)
    has = (t.security_id.str.strip() != "") | (t.shares.str.strip() != "") | (t.price.str.strip() != "")
    return t, has, cash, ["txn_type", "security_id", "shares", "price"]


@rule(2, "ERROR", "fact_transactions", "shares", "Shares are positive (direction comes from txn_type)")
def _(T):
    t = T["fact_transactions"]
    sh = to_num(t.shares)
    return t, sh <= 0, sh.notna(), ["txn_type", "shares", "price", "amount"]


@rule(2, "ERROR", "fact_transactions", "amount", "amount = |shares| × price (±$0.01) for trades")
def _(T):
    t = T["fact_transactions"]
    sh, pr, am = to_num(t.shares), to_num(t.price), to_num(t.amount)
    return t, (sh.abs() * pr - am).abs() > 0.0101, sh.notna() & pr.notna() & am.notna(), \
        ["txn_type", "shares", "price", "amount"]


@rule(2, "INFO", "fact_transactions", "amount",
      "Dividend amount = shares × price (looks like position value, not cash paid)")
def _(T):
    t = T["fact_transactions"]
    sh, pr, am = to_num(t.shares), to_num(t.price), to_num(t.amount)
    div = t.txn_type == "Dividend"
    return t, (sh * pr - am).abs() <= 0.0101, div & sh.notna(), ["shares", "price", "amount"]


@rule(2, "WARN", "fact_transactions", "client_id",
      "No transaction is a copy of another client's transaction (identical except client_id)")
def _(T):
    t = T["fact_transactions"]
    others = [c for c in t.columns if c not in ("txn_id", "client_id")]
    dup = t.duplicated(others, keep=False) & (t.groupby(others).client_id.transform("nunique") > 1)
    return t, dup, None, ["client_id", "txn_date", "txn_type", "amount"], \
        "Both rows of each pair are flagged; compare with the orphan client_id check in group 3"


@rule(2, "INFO", "fact_transactions", "txn_id+client_id+txn_date+txn_type+amount",
      "No two transactions share client, date, type and amount")
def _(T):
    t = T["fact_transactions"]
    return t, t.duplicated(["client_id", "txn_date", "txn_type", "amount"], keep=False), None, \
        ["client_id", "txn_date", "txn_type", "amount"]


# ════════════════════════════════════════════════════════════════════
# Group 3 — referential integrity
# ════════════════════════════════════════════════════════════════════


def fk_pairs(T):
    pks = {pk_of(t, df): t for t, df in T.items() if pk_of(t, df)}
    pairs = []
    for t, df in T.items():
        own = pk_of(t, df)
        for c in df.columns:
            if c != own and c in pks and pks[c] != t:
                pairs.append((t, c, pks[c], c))
    for p in EXTRA_FKS:
        if p[0] in T and p[2] in T and p[1] in T[p[0]] and p[3] in T[p[2]]:
            pairs.append(p)
    return pairs


def referential_checks(F: Findings):
    T = F.T
    for t, c, pt, pc in fk_pairs(T):
        df = T[t]
        raw = df[c].str.strip()
        blank = raw == ""
        parent_raw = set(T[pt][pc].str.strip())
        parent = set(canon_key(T[pt][pc]))
        key = canon_key(df[c])
        orphan = ~blank & ~key.isin(parent)
        F.mask(3, "ERROR", t, c, f"{t}.{c} → {pt}.{pc} exists", df, orphan, ~blank, [c],
               detail=f"{df.loc[orphan, c].nunique()} distinct orphan keys" if orphan.any() else
               "compared after trimming and '45.0'→'45'")
        raw_miss = ~blank & ~raw.isin(parent_raw) & ~orphan
        if raw_miss.any():
            F.mask(3, "ERROR", t, c, f"{t}.{c} joins to {pt}.{pc} as raw text", df, raw_miss, ~blank, [c],
                   detail="Key format differs from the parent (e.g. '45.0' vs '45'); cast both to int before joining")
        if blank.any():
            sev = "INFO" if (t, c) in NULLABLE_FKS else "ERROR"
            F.add(3, sev, t, c, f"FK {c} populated", int(blank.sum()), len(df),
                  detail="Allowed only for cash-flow rows (see group 2)" if sev == "INFO" else "")
    # dimension members never used by any fact
    for pt, pdf in T.items():
        pk = pk_of(pt, pdf)
        if not pk or not pt.startswith("dim"):
            continue
        users = [(t, c) for t, c, p2, pc in fk_pairs(T) if p2 == pt and pc == pk and t.startswith("fact")]
        if not users:
            continue
        used = set().union(*[set(canon_key(T[t][c])) for t, c in users])
        unused = ~canon_key(pdf[pk]).isin(used)
        F.mask(3, "INFO", pt, pk, f"Every {pt} row is used by a fact table", pdf, unused, show=[pk],
               detail="referenced from " + ", ".join(f"{t}.{c}" for t, c in users))


# ════════════════════════════════════════════════════════════════════
# Group 4 — cross-table business rules
# ════════════════════════════════════════════════════════════════════

RISK_TO_BENCH = {"Aggressive": "S&P 500", "Moderately Aggressive": "S&P 500",
                 "Balanced": "60/40 Blend",
                 "Moderately Conservative": "Conservative Blend", "Conservative": "Conservative Blend"}


def client_attr(T, df, cols):
    c = T["dim_client"][["client_id", *cols]].copy()
    c["client_id"] = canon_key(c.client_id)
    left = df.assign(_cid=canon_key(df.client_id))
    return left.merge(c.add_suffix("_dim").rename(columns={"client_id_dim": "_cid"}), on="_cid", how="left")


for _fact, _date in [("fact_portfolio_snapshot", "snapshot_date"), ("fact_fees", "fee_date"),
                     ("fact_transactions", "txn_date")]:
    def _make(fact=_fact):
        @rule(4, "ERROR", fact, "advisor_id", "advisor_id agrees with dim_client.advisor_id", needs=("dim_client",))
        def _(T):
            m = client_attr(T, T[fact], ["advisor_id"])
            return m, canon_key(m.advisor_id) != canon_key(m.advisor_id_dim.fillna("")), \
                m.advisor_id_dim.notna(), ["client_id", "advisor_id", "advisor_id_dim"]

    _make()

for _fact, _date, _sev in [("fact_portfolio_snapshot", "snapshot_date", "WARN"),
                           ("fact_fees", "fee_date", "WARN"),
                           ("fact_transactions", "txn_date", "WARN")]:
    def _make(fact=_fact, dcol=_date, sev=_sev):
        @rule(4, sev, fact, dcol, "Activity is not dated before dim_client.client_since (same month allowed)",
              needs=("dim_client",))
        def _(T):
            m = client_attr(T, T[fact], ["client_since"])
            d, since = to_date(m[dcol]), to_date(m.client_since_dim.fillna(""))
            bad = d < since.dt.to_period("M").dt.to_timestamp()
            return m, bad, d.notna() & since.notna(), ["client_id", dcol, "client_since_dim"]

    _make()


@rule(4, "ERROR", "fact_portfolio_snapshot", "account_type",
      "account_type agrees with dim_client.primary_account_type", needs=("dim_client",))
def _(T):
    m = client_attr(T, T["fact_portfolio_snapshot"], ["primary_account_type"])
    return m, m.account_type != m.primary_account_type_dim, m.primary_account_type_dim.notna(), \
        ["client_id", "account_type", "primary_account_type_dim"]


@rule(4, "WARN", "fact_portfolio_snapshot", "benchmark_id",
      "Benchmark matches the client's risk profile (Aggr→S&P 500, Bal→60/40, Cons→Conservative Blend)",
      needs=("dim_client", "dim_benchmark"))
def _(T):
    m = client_attr(T, T["fact_portfolio_snapshot"], ["risk_profile"])
    b = T["dim_benchmark"].assign(benchmark_id=lambda x: canon_key(x.benchmark_id)).set_index("benchmark_id").name
    m["bench_name"] = canon_key(m.benchmark_id).map(b)
    exp = m.risk_profile_dim.map(RISK_TO_BENCH)
    return m, m.bench_name != exp, exp.notna(), ["client_id", "risk_profile_dim", "bench_name"]


@rule(4, "WARN", "fact_portfolio_snapshot", "benchmark_id",
      "Clients with blank risk_profile are not silently assigned a benchmark", needs=("dim_client",))
def _(T):
    m = client_attr(T, T["fact_portfolio_snapshot"], ["risk_profile"])
    blank = m.risk_profile_dim.fillna("").str.strip() == ""
    return m, blank & m.risk_profile_dim.notna(), None, ["client_id", "risk_profile_dim", "benchmark_id"]


@rule(4, "ERROR", "fact_portfolio_snapshot", "benchmark_id", "One benchmark and one advisor per client over time")
def _(T):
    p = T["fact_portfolio_snapshot"]
    g = p.groupby("client_id")
    bad = (g.benchmark_id.transform("nunique") > 1) | (g.advisor_id.transform("nunique") > 1)
    return p, bad, None, ["client_id", "benchmark_id", "advisor_id"]


@rule(4, "ERROR", "fact_portfolio_snapshot", "benchmark_return_ytd",
      "Same benchmark + date ⇒ same benchmark_return_ytd for every client")
def _(T):
    p = T["fact_portfolio_snapshot"]
    bad = p.groupby(["benchmark_id", "snapshot_date"]).benchmark_return_ytd.transform("nunique") > 1
    return p, bad, None, ["benchmark_id", "snapshot_date", "benchmark_return_ytd"]


@rule(4, "ERROR", "fact_fees", "aum_basis", "aum_basis equals snapshot AUM for the same client-month",
      needs=("fact_portfolio_snapshot",))
def _(T):
    f, p = T["fact_fees"], T["fact_portfolio_snapshot"]
    s = p.assign(_k=canon_key(p.client_id) + "|" + p.snapshot_date.str[:7]).drop_duplicates("_k") \
        .set_index("_k").aum
    m = f.assign(snap_aum=(canon_key(f.client_id) + "|" + f.fee_date.str[:7]).map(s))
    return m, (to_num(m.aum_basis) - to_num(m.snap_aum.fillna(""))).abs() > 0.0101, m.snap_aum.notna(), \
        ["client_id", "fee_date", "aum_basis", "snap_aum"]


@rule(4, "ERROR", "fact_fees", "client_id+fee_date", "Every fee has a portfolio snapshot for that client-month",
      needs=("fact_portfolio_snapshot",))
def _(T):
    f, p = T["fact_fees"], T["fact_portfolio_snapshot"]
    keys = set(canon_key(p.client_id) + "|" + p.snapshot_date.str[:7])
    return f, ~(canon_key(f.client_id) + "|" + f.fee_date.str[:7]).isin(keys), None, ["client_id", "fee_date"]


@rule(4, "WARN", "fact_portfolio_snapshot", "client_id+snapshot_date",
      "Every snapshot month has a fee charge", needs=("fact_fees",))
def _(T):
    f, p = T["fact_fees"], T["fact_portfolio_snapshot"]
    keys = set(canon_key(f.client_id) + "|" + f.fee_date.str[:7])
    return p, ~(canon_key(p.client_id) + "|" + p.snapshot_date.str[:7]).isin(keys), None, \
        ["client_id", "snapshot_date", "aum"]


@rule(4, "WARN", "fact_transactions", "amount",
      "Advisory Fee transactions reconcile to fact_fees (same client-month total, ±$0.01)",
      needs=("fact_fees",))
def _(T):
    t, f = T["fact_transactions"], T["fact_fees"]
    fees = to_num(f.amount).groupby(canon_key(f.client_id) + "|" + f.fee_date.str[:7]).sum()
    af = t[t.txn_type == "Advisory Fee"].copy()
    af["_k"] = canon_key(af.client_id) + "|" + af.txn_date.str[:7]
    tot = to_num(af.amount).groupby(af._k).transform("sum")
    af["fact_fees_month_total"] = af._k.map(fees).round(2)
    af["txn_month_total"] = tot.round(2)
    bad = af.fact_fees_month_total.isna() | ((af.txn_month_total - af.fact_fees_month_total).abs() > 0.0101)
    yt = pd.DataFrame({"fact_fees": to_num(f.amount).groupby(f.fee_date.str[:4]).sum(),
                       "advisory_fee_txns": to_num(af.amount).groupby(af.txn_date.str[:4]).sum()}).round(0)
    detail = "Yearly totals ($): " + "; ".join(f"{y}: fees {r.fact_fees:,.0f} vs txns {r.advisory_fee_txns:,.0f}"
                                               for y, r in yt.iterrows())
    return af, bad, None, ["client_id", "txn_date", "amount", "fact_fees_month_total"], detail


@rule(4, "WARN", "fact_transactions", "txn_date", "Buy/Sell happen on trading days (dim_date.is_trading_day)",
      needs=("dim_date",))
def _(T):
    t, d = T["fact_transactions"], T["dim_date"]
    trd = t.txn_date.str.strip().map(d.set_index(d.date.str.strip()).is_trading_day)
    return t, trd == "0", t.txn_type.isin({"Buy", "Sell"}) & trd.notna(), ["txn_type", "txn_date"]


@rule(4, "INFO", "fact_transactions", "txn_date",
      "Cash flows / dividends / fees on non-trading days", needs=("dim_date",))
def _(T):
    t, d = T["fact_transactions"], T["dim_date"]
    trd = t.txn_date.str.strip().map(d.set_index(d.date.str.strip()).is_trading_day)
    return t, trd == "0", ~t.txn_type.isin({"Buy", "Sell"}) & trd.notna(), ["txn_type", "txn_date"]


@rule(4, "WARN", "fact_transactions", "shares",
      "Running share position never goes negative (no selling more than was bought)")
def _(T):
    t = T["fact_transactions"].copy()
    tr = t[t.txn_type.isin({"Buy", "Sell"})].copy()
    tr["q"] = to_num(tr.shares).abs() * np.where(tr.txn_type == "Buy", 1, -1)
    tr = tr.sort_values(["txn_date", "txn_id"])
    tr["pos"] = tr.groupby(["client_id", canon_key(tr.security_id)]).q.cumsum()
    bad = (tr.pos < -1e-6) & (tr.txn_type == "Sell")
    return tr, bad, tr.txn_type == "Sell", ["client_id", "security_id", "txn_date", "shares", "pos"], \
        "No opening positions exist before 2020, so early sells may be legitimate; confirm with the business"


@rule(4, "WARN", "fact_transactions", "txn_date",
      "Inactive clients have no transactions after their last snapshot month",
      needs=("dim_client", "fact_portfolio_snapshot"))
def _(T):
    t, c, p = T["fact_transactions"], T["dim_client"], T["fact_portfolio_snapshot"]
    last = p.groupby(canon_key(p.client_id)).snapshot_date.max().str[:7]
    inactive = set(canon_key(c.client_id[c.is_active.str.strip() == "False"]))
    k = canon_key(t.client_id)
    m = t.assign(last_snapshot_month=k.map(last))
    return m, m.txn_date.str[:7] > m.last_snapshot_month, k.isin(inactive) & m.last_snapshot_month.notna(), \
        ["client_id", "txn_date", "txn_type", "last_snapshot_month"]


@rule(4, "WARN", "dim_client", "is_active",
      "Active clients have a snapshot in the latest month", needs=("fact_portfolio_snapshot",))
def _(T):
    c, p = T["dim_client"], T["fact_portfolio_snapshot"]
    last = p.groupby(canon_key(p.client_id)).snapshot_date.max()
    m = c.assign(last_snapshot=canon_key(c.client_id).map(last))
    bad = m.last_snapshot < p.snapshot_date.max()
    return m, bad, (m.is_active == "True") & m.last_snapshot.notna(), ["client_id", "is_active", "last_snapshot"]


@rule(4, "INFO", "dim_client", "initial_aum",
      "First snapshot AUM is within 0.5×–2× of initial_aum", needs=("fact_portfolio_snapshot",))
def _(T):
    c, p = T["dim_client"], T["fact_portfolio_snapshot"]
    first = p.sort_values("snapshot_date").drop_duplicates("client_id")
    fa = to_num(first.aum).groupby(canon_key(first.client_id)).first()
    m = c.assign(first_aum=canon_key(c.client_id).map(fa))
    r = m.first_aum / to_num(m.initial_aum)
    return m, (r < 0.5) | (r > 2), r.notna(), ["client_id", "client_since", "initial_aum", "first_aum"]


@rule(4, "INFO", "dim_advisor", "aum_target_mm",
      "Advisor book (latest-month AUM) is within 0.5×–2× of aum_target_mm",
      needs=("fact_portfolio_snapshot",))
def _(T):
    a, p = T["dim_advisor"], T["fact_portfolio_snapshot"]
    last = p[p.snapshot_date == p.snapshot_date.max()]
    book = (to_num(last.aum).groupby(canon_key(last.advisor_id)).sum() / 1e6).round(1)
    m = a.assign(book_mm=canon_key(a.advisor_id).map(book))
    r = m.book_mm / to_num(m.aum_target_mm)
    return m, (r < 0.5) | (r > 2), r.notna(), ["advisor_id", "aum_target_mm", "book_mm"]


def run_row_rules(F: Findings):
    for r in ROW_RULES:
        missing = [t for t in r["needs"] if t not in F.T]
        if missing:
            F.add(r["group"], r["sev"], r["table"], r["column"], r["desc"], 0, 0,
                  detail=f"skipped: table(s) not present: {', '.join(missing)}", status="SKIPPED")
            continue
        try:
            out = r["fn"](F.T)
        except KeyError as e:
            F.add(r["group"], r["sev"], r["table"], r["column"], r["desc"], 0, 0,
                  detail=f"skipped: column not present: {e}", status="SKIPPED")
            continue
        df, fail, checked, show = out[:4]
        detail = out[4] if len(out) > 4 else ""
        F.mask(r["group"], r["sev"], r["table"], r["column"], r["desc"], df, fail, checked, show, detail)


# ════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", type=Path, help="CSV files (default: every CSV in --data)")
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA, help="folder of CSVs")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output folder for reports")
    args = ap.parse_args(argv)

    paths = args.files or sorted(args.data.glob("*.csv"))
    if not paths:
        sys.exit(f"No CSV files found in {args.data}")
    tables = load_tables(paths)
    print(f"Loaded {len(tables)} tables as text:")
    for t, df in tables.items():
        print(f"  {t:<28} {len(df):>9,} rows × {df.shape[1]:>2} cols")

    prof, details = profile_all(tables)
    F = Findings(tables)
    column_checks(F, prof, details)
    generic_single_table(F)
    run_row_rules(F)
    referential_checks(F)
    dq = F.frame()

    args.out.mkdir(parents=True, exist_ok=True)
    prof.to_csv(args.out / "profile_raw.csv", index=False)
    dq.to_csv(args.out / "dq_summary_raw.csv", index=False)

    found = dq[dq.status == "FINDING"]
    print(f"\n{len(dq)} checks run: {len(found)} findings, "
          f"{(dq.status == 'PASS').sum()} passed, {(dq.status == 'SKIPPED').sum()} skipped")
    print(found.groupby(["group", "severity"]).size().unstack(fill_value=0).to_string())
    print("\nTop ERROR findings:")
    for r in found[found.severity == "ERROR"].head(15).itertuples():
        print(f"  [{r.check_id}] {r.table}.{r.column}: {r.rule} — {r.n_failed:,} of {r.n_checked:,}")
    print(f"\nWrote {args.out / 'profile_raw.csv'}\nWrote {args.out / 'dq_summary_raw.csv'}")


if __name__ == "__main__":
    main()
