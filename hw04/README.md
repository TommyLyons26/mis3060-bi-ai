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
│   └── 02_clean.py           # applies the decisions in decision_log.md
├── reports/
│   ├── profile_raw.csv       # one row per column: what the data looks like
│   └── dq_summary_raw.csv    # one row per check: PASS or FINDING, tagged ERROR / WARN / INFO
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

## How to run

From the repository root (`mis3060-bi-ai`), in the VS Code terminal:

```bash
python3 hw04/scripts/01_profile.py
```

Optional:

```bash
python3 hw04/scripts/01_profile.py --data path/to/folder   # profile any folder of CSVs
python3 hw04/scripts/01_profile.py a.csv b.csv             # profile specific files
```

Requires `pandas` and `numpy` (see `requirements.txt`). It takes about 40 seconds and writes both reports to `hw04/reports/`. On the raw data it runs 384 checks: 38 findings (6 ERROR, 17 WARN, 15 INFO) and 346 passes.

Then run the cleaning script:

```bash
python3 hw04/scripts/02_clean.py
```

It takes about 15 seconds and writes to `hw04/data/clean/` and `hw04/data/audit/`. It is safe to run again: it always starts from the raw files and overwrites its own outputs. It ends with `Done: 28 log entries, 198,345 value changes, 225 rows quarantined.`

## Claude Code findings

### `01_profile.py`

**Result: no issues flagged.**

Claude Code suggested one improvement:

- **What it noticed:** when a business rule fails, the script only handles one kind of error (a missing column, `KeyError`). Some rules do maths, convert values to whole numbers, or work with dates. If future data contained unexpected values, such as a blank or non-numeric ID, those rules could raise a different error (`ValueError` or `TypeError`). The script would then crash instead of marking that rule as `SKIPPED` and carrying on.
- **Suggested fix:** also catch `ValueError` and `TypeError` in `run_row_rules()`, so the script keeps running with messier data.
- **What I did:** no change. None of these errors happened on this dataset, and the script ran correctly on all eight files, so the change wasn't needed for this assignment.

### `02_clean.py`

**Result: no active bugs flagged.**

Claude Code pointed out some hidden assumptions. They are true for this dataset, but the script doesn't re-check them:

- **What it noticed:**
  - Some steps (`step_duplicate_clients`, `step_floor`, `step_extreme_returns`) assume there are no duplicate client-months and that every client ID is a number. That's true here, but it isn't checked again right before those steps. If future data broke one of these assumptions, the script could crash with an unclear error instead of a clear message.
  - In `step_risk_profile`, the check that blank-profile clients only use the default benchmark only looks at clients who have snapshots. A blank-profile client with no snapshots would pass the check without actually being examined.
- **Suggested fix:** add explicit checks for these assumptions before the steps that rely on them, so problems in future data stop the script with a clear message.
- **What I did:** no change. These assumptions all hold for this dataset, every check passed, and the script performed as intended on all eight files, so the change wasn't needed for this assignment.
