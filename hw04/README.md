# HW04 — Wildcat Capital Data Quality

## Structure

```
hw04/
├── Wildcat Capital/          # the 8 raw CSV files (never modified)
│   ├── dim_advisor.csv
│   ├── dim_benchmark.csv
│   ├── dim_client.csv
│   ├── dim_date.csv
│   ├── dim_security.csv
│   ├── fact_fees.csv
│   ├── fact_portfolio_snapshot.csv
│   └── fact_transactions.csv
├── scripts/
│   ├── 01_profile.py         # profiles every column and runs the data-quality checks
│   ├── 02_clean.py           # applies the decisions in decision_log.md
│   └── 03_validate.py        # validates raw and clean tables and builds the scorecard
├── reports/
│   ├── profile_raw.csv              # one row per column: what the data looks like
│   ├── dq_summary_raw.csv           # one row per check: PASS or FINDING, tagged ERROR / WARN / INFO
│   ├── data_quality_scorecard.csv   # one row per table per stage (raw / clean): five quality scores
│   └── validation_details.csv       # every individual check behind the scorecard
├── decision_log.md           # one entry per issue: evidence, decision, justification, risk
└── data/
    ├── clean/                # the 8 cleaned tables (same names and columns, plus 0/1 flag columns)
    │   └── README_clean.md   # table relationships, BI column types, flags, known limitations
    └── audit/
        ├── cleaning_log.csv                          # table, issue, action, rows affected, note
        ├── value_changes.csv                         # every value changed: old → new
        ├── quarantine_dim_client_duplicates.csv      # 25 duplicate clients removed
        └── quarantine_fact_transactions_orphans.csv  # 200 copied transactions removed
```

**What `01_profile.py` does**

1. Reads every file as text (`dtype=str`, `keep_default_na=False`), so nothing is changed on the way in.
2. Profiles every column: blanks, distinct values, value shapes, values that fail to parse as the expected type, whitespace problems, mixed formats, and numeric min/max.
3. Runs data-quality checks in four groups:
   - **Column level**: type, allowed values, ranges, key uniqueness
   - **Single-table**: duplicates, near-duplicates, values that contradict other columns in the same row
   - **Referential integrity**: every foreign key points to an existing primary key
   - **Cross-table**: facts that disagree with dimensions, or with each other
4. Tags each finding **ERROR** (wrong, or will break a join or calculation), **WARN** (probably wrong; investigate) or **INFO** (worth knowing).

The profiling and generic checks work on any folder of CSVs. The Wildcat Capital business rules are kept in a config section and are skipped automatically if their tables or columns aren't present.

**What `02_clean.py` does**

1. Reads the 8 raw files as text and works on a copy; the raw files are never modified.
2. Applies the decisions in `decision_log.md` one transformation at a time. After each one it prints the rows affected and a before/after check, and uses `assert` to confirm the result. If a check fails, the script stops before saving anything.
3. Confirms each repair against another column or table instead of guessing (e.g. return − benchmark = alpha, amount = shares × price).
4. Moves removed rows to quarantine files and proves raw rows = clean rows + quarantined rows for every table.
5. Saves the clean tables, the audit trail and `README_clean.md`.

**What `03_validate.py` does**

1. Reads the raw and the clean tables as text and runs the same checks on both.
2. **Referential integrity:** a reusable function, `check_referential_integrity(fact_df, fact_key, dim_df, dim_key)`, returns the match rate, orphan rows, distinct orphan keys and null-key rate. It is applied to all 13 relationships: 10 ID-based ones and 3 date joins to `dim_date`.
3. **Business rules:** 48 checks on columns with a natural limit: ranges (e.g. age 18–110), allowed code lists (e.g. state codes, account types) and sign rules (e.g. shares > 0).
4. **Reconciliations:** recomputes values and compares them with what is stored, e.g. fee amount = AUM × rate ÷ 12, alpha = return − benchmark, trade amount = shares × price, fee AUM = snapshot AUM. One reconciliation (Advisory Fee transactions vs `fact_fees`) is expected to fail: it is the known limitation in decision #15.
5. **IQR outliers** on snapshot AUM, trade amount and initial AUM. Flagged does not mean wrong: almost every flagged AUM belongs to a UHNW client whose account is legitimately large.
6. Saves `data_quality_scorecard.csv`: one row per table per stage, with % completeness, % key uniqueness, % type validity, % rule pass and % referential match.

## How to run

From the repository root (`mis3060-bi-ai`), in the VS Code terminal:

```bash
python3 hw04/scripts/01_profile.py
```



Requires `pandas` and `numpy` (see `requirements.txt`). It takes about 40 seconds and writes both reports to `hw04/reports/`. On the raw data it runs 384 checks: 38 findings (6 ERROR, 17 WARN, 15 INFO) and 346 passes.

Then run the cleaning script:

```bash
python3 hw04/scripts/02_clean.py
```

It takes about 15 seconds and writes to `hw04/data/clean/` and `hw04/data/audit/`. It is safe to run again: it always starts from the raw files and overwrites its own outputs. It ends with `Done: 28 log entries, 198,345 value changes, 225 rows quarantined.`

Then run the validation script:

```bash
python3 hw04/scripts/03_validate.py
```

It takes about 20 seconds and writes both reports to `hw04/reports/`. It reads the clean files, so run `02_clean.py` first. On the clean data every table scores 100% on every scorecard measure that applies (referential match is n/a for the advisor, benchmark and calendar tables, which don't link to other tables).

## Claude Code findings

### `01_profile.py`

**Result: no issues flagged.**

Claude Code suggested one improvement:

- **What it noticed:** when a business rule fails, the script only handles one kind of error (a missing column, `KeyError`). Some rules do maths, convert values to whole numbers, or work with dates. If future data contained unexpected values, such as a blank or non-numeric ID, those rules could raise a different error (`ValueError` or `TypeError`). The script would then crash instead of marking that rule as `SKIPPED` and carrying on.
- **Suggested fix:** also catch `ValueError` and `TypeError` in `run_row_rules()`, so the script keeps running with messier data.
- **What I did:** no change. None of these errors happened on this dataset, and the script ran correctly on all eight files, so the change wasn't needed for this assignment.

### `02_clean.py`

**Result: no issues flagged.**

Claude Code pointed out some hidden assumptions. They are true for this dataset, but the script doesn't re-check them:

- **What it noticed:**
  - Some steps (`step_duplicate_clients`, `step_floor`, `step_extreme_returns`) assume there are no duplicate client-months and that every client ID is a number. That's true here, but it isn't checked again right before those steps. If future data broke one of these assumptions, the script could crash with an unclear error instead of a clear message.
  - In `step_risk_profile`, the check that blank-profile clients only use the default benchmark only looks at clients who have snapshots. A blank-profile client with no snapshots would pass the check without actually being examined.
- **Suggested fix:** add explicit checks for these assumptions before the steps that rely on them, so problems in future data stop the script with a clear message.
- **What I did:** no change. These assumptions all hold for this dataset, every check passed, and the script performed as intended on all eight files, so the change wasn't needed for this assignment.

### `03_validate.py`

**Result: no blocking issues flagged.**

Claude Code pointed out two minor points:

- **What it noticed:**
  - `pct_referential_match` in the scorecard is an average across all of a table's relationships, not shown separately for each one. That fits the "one row per table" format, but the score for each relationship is only visible in `validation_details.csv`.
  - Two parts of the code (the note calculation in `iqr_flags` and the type handling in `check_referential_integrity`) work correctly but are written in a slightly roundabout way. They're worth a second look if they are extended in Assignment 5.
- **Suggested fix:** none required; just be aware of these if more detail is needed or the function is reused.
- **What I did:** no change. The script ran correctly on both the raw and clean data and produced the scorecard as intended, so the change wasn't needed for this assignment.
