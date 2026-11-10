# MIS 3060 HW06: Measure Reconciliation

`scripts/01_reconcile_measures.py` recomputes every DAX measure independently in pandas, using only the Wildcat Capital CSVs in `Wildcat Capital Clean/`. It then compares the results with the Power BI values in `reports/powerbi_values.csv` and writes `reports/measure_reconciliation.csv` with the columns `measure, slice, powerbi_value, pandas_value, abs_diff, match`.

**Tolerances:** 0.01 for currency, 0.0001 for ratios and bps. Text and counts must match exactly.

**Coverage:**
- Every measure at the grand total.
- Measures 1, 4 and 6–10 by year.
- Measures 1, 3, 4 and 7–11 by client tier for 2024.
- Measure 5 for December 2024.
- `AUM (naive SUM)` in both tools, to show that both make the same mistake when AUM snapshots are summed across months.

## Structure

```
hw06/
├── README.md                         This file
├── Wildcat Capital Clean/            Source CSVs (the only input to the pandas script)
├── powerbi/
│   ├── hw06.pbix                     Power BI model
│   └── measures.md                   DAX measure library and Part C answers
├── scripts/
│   └── 01_reconcile_measures.py      Pandas recompute and comparison
├── reports/
│   ├── powerbi/                      Raw DAX query exports (total, by year, 2024 tiers, Dec 2024)
│   ├── powerbi_values.csv            The four exports merged into measure, slice, value
│   └── measure_reconciliation.csv    Script output: Power BI vs. pandas, row by row
└── claude/
    ├── model_metadata.md             Model columns and relationships, given to Claude
    ├── dax_session.md                Claude conversation that produced the Top 10 Client Share measure
    └── verification.md               Verification of that measure
```

## Workflow

1. **Claude Desktop** drafted `scripts/01_reconcile_measures.py` from the measure definitions.
2. **I ran it in VS Code** against the CSVs and my Power BI exports.
3. **Claude Code reviewed** the script and its output before I committed. Its findings and what I did about each are below.

## How to run

Requires Python 3 and pandas (`pip install pandas`). From the `hw06` folder:

```
python scripts/01_reconcile_measures.py
```

The script prints how many rows match and lists any mismatches. The full table is written to `reports/measure_reconciliation.csv`.

To refresh the Power BI side, re-run the four DAX queries in DAX query view, copy each result straight into the matching file in `reports/powerbi/` without opening it in Excel, and rebuild `reports/powerbi_values.csv`.

## Claude Code findings and what I did

| # | What Claude Code flagged | What I did |
|---|---|---|
| 1 | **Real discrepancy, not a script bug.** Every Fee Yield (bps) row was off by exactly 10x (e.g. Total: about 4.33 in Power BI vs. about 43.34 in pandas). It re-derived the DAX from `measures.md`, found it identical to the Python formula (`total_fees * 12 * 10000 / naive_AUM_sum`), and pointed to a bug in the live Power BI measure. | Checked the measure in the .pbix and found I had typed `1000` instead of `10000`. Fixed it in Power BI, re-exported, and re-ran the script. Details below. |
| 2 | The text, count and currency tolerances, and the blank handling for 2020 (no prior year), behaved correctly. No false positives in the passing rows. | No change needed. |
| 3 | No personal or sensitive data in the source files, only synthetic client and portfolio figures. | No change needed. |

## Mismatches and fixes

**Which side was wrong:** Power BI. On the first run, 79 of 88 rows matched. All 9 mismatches were **Fee Yield (bps)** (Total, each year 2020–2024, and each tier for 2024), and in every one the Power BI value was exactly 10x smaller than the pandas value.

**Cause:** a manual input error in my Power BI measure. I multiplied by **1,000 instead of 10,000** when converting to basis points. One basis point is 0.01% (1/10,000), so the correct multiplier is 10,000. The source data confirms the pandas figure is the realistic one: `bps_charged` in `fact_fees.csv` sits around 65 bps, so an annualized fee yield of about 43 bps makes sense and 4.3 bps does not.

**Fix:**
1. In Power BI, I changed the multiplier in `Fee Yield (bps)` from `1000` to `10000`.
2. I re-ran the DAX queries and re-exported the values to `reports/powerbi_values.csv`.
3. I re-ran `scripts/01_reconcile_measures.py`. **Result: 88 of 88 rows match.**

The pandas script did not need any change. The Git history shows both versions: the commit with the bug (79/88) and the commit with the fix (88/88).

**Separate finding (Top 10 Client Share):** my original Top 10 Client Share measure passed the reconciliation, matching pandas at the grand total and for all three 2024 tiers. However, testing it by advisor showed that it gives wrong values for 8 of the 25 advisors (1, 5, 10, 14, 17, 18, 21 and 23). It ranks clients who have left the firm on their old balance, so a departed client can take a top-10 place while adding $0 to current AUM. The reconciliation did not catch this because it does not test by advisor. See `claude/verification.md`.
