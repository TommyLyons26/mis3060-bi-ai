# MIS 3060 HW06: Measure Reconciliation

`scripts/01_reconcile_measures.py` recomputes every DAX measure independently in pandas, using only the Wildcat Capital CSVs in `Wildcat Capital Clean/`. It then compares the results with the Power BI values in `reports/powerbi_values.csv` and writes `reports/measure_reconciliation.csv` with the columns `measure, slice, powerbi_value, pandas_value, abs_diff, match`.

**Tolerances:** 0.01 for currency, 0.0001 for ratios and bps. Text and counts must match exactly.

**Coverage:**
- Every measure at the grand total.
- Measures 1, 4 and 6–10 by year.
- Measures 1, 3, 4 and 7–11 by client tier for 2024.
- Measure 5 for December 2024.
- `AUM (naive SUM)` in both tools, to show that both make the same mistake when AUM snapshots are summed across months.

## Run

```
python scripts/01_reconcile_measures.py
```

## Review findings (Claude Code)

**Bad / worth your attention:**

- **Real discrepancy found, not a script bug.** Every Fee Yield (bps) row is off by exactly 10x. For example, the "Total" slice shows about 4.33 in Power BI and about 43.34 in pandas, and the ratio is identical across all 9 rows. I re-derived the DAX formula from `measures.md` by hand, and it is algebraically identical to the Python formula: both reduce to `total_fees * 12 * 10000 / naive_AUM_sum`. Since the Python and DAX logic agree, the .pbix's computed values are 10x too small. That points to a bug in the live Power BI measure itself, or in how `powerbi_values.csv` was exported. It's worth checking the measure in the .pbix directly, for example for a stray `/100` or a percentage-formatted column being read as a decimal.
- Everything else behaved sensibly: the text, count and currency tolerances, and the blank handling for years with no prior-year data. I spot-checked the passing rows and found no false positives.
- No personal or sensitive data appeared in any of the source files, only synthetic client and portfolio figures.

## What was wrong and how I fixed it

**Which side was wrong:** Power BI. On the first run, 79 of 88 rows matched. All 9 mismatches were **Fee Yield (bps)** (Total, each year 2020–2024, and each tier for 2024), and in every one the Power BI value was exactly 10x smaller than the pandas value.

**Cause:** this was a manual input error in my Power BI measure. I multiplied by **1,000 instead of 10,000** when converting to basis points. One basis point is 0.01% (1/10,000), so the correct multiplier is 10,000. The source data confirms the pandas figure is the realistic one: `bps_charged` in `fact_fees.csv` sits around 65 bps, so an annualized fee yield of about 43 bps makes sense and 4.3 bps does not.

**Fix:**
1. In Power BI, I changed the multiplier in `Fee Yield (bps)` from `1000` to `10000`.
2. I re-ran the DAX queries and re-exported the values to `reports/powerbi_values.csv`.
3. I re-ran `scripts/01_reconcile_measures.py`. **Result: 88 of 88 rows match.**

The pandas script did not need any change. The Git history shows both versions: the commit with the bug (79/88) and the commit with the fix (88/88).
