# Wildcat Capital — Data Cleaning Report

**For:** Portfolio Committee · **Scope:** 8 tables, 2020–2024 (clients, advisors, securities, benchmarks, calendar, monthly snapshots, fees, transactions)
**Sources:** `decision_log.md` (19 decisions) and `reports/data_quality_scorecard.csv`

## Executive summary

The data is in good shape overall: the advisor, benchmark and calendar tables needed no changes, and most problems affected only a small share of rows. We found **5 clear errors** and **14 warnings**. Every error has been fixed or removed. Warnings were either fixed, flagged for analysts, or documented as limitations. Nothing was deleted without a record: the **225 rows removed** (25 duplicate clients and 200 copied transactions) are kept in quarantine files and can be restored.

After cleaning, **all eight tables score 100%** on completeness, key uniqueness, type validity and business rules, and the five tables that link to others score 100% on referential integrity. Before cleaning, the transactions table could not be linked to securities at all.

**Three points the committee should keep in mind when using the figures:**

1. **Fee revenue has two versions.** The fee table shows **$204.7M** over five years; the fee transactions show **$263.7M**. They never agree. We use the fee table, which follows an exact formula. In addition, it is missing a fee in 5.7% of months (7,350 client-months), so revenue from it is understated.
2. **AUM excludes deposits and withdrawals.** Account values move only with investment returns. Net client deposits of **$327.4M** over five years are not reflected in AUM.
3. **Performance figures should exclude flagged rows.** 1,475 snapshots show unrealistic returns (up to +9,467%) and 420 show an artificial $1,000 balance. All of them are small Retail accounts. They are kept but flagged, so averages aren't distorted.

## Cleaning summary

| Issue | Rows affected | Action |
|---|---|---|
| Duplicate clients (surname typo, e.g. "Taylo" = "Taylor") | 25 | Quarantined; original kept |
| Transactions for non-existent clients (copies of real ones) | 200 | Quarantined; $10.9M of double-counted activity removed |
| Security IDs stored as "45.0", so no trade linked to a security | 197,044 | Converted to whole numbers |
| Returns stored as text ("9.28%") | 300 | Converted to decimals (0.0928) |
| State names written in full ("Pennsylvania") | 77 | Standardized to 2-letter codes |
| Negative shares on Buy transactions | 835 | Sign removed and flagged |
| Blank client risk profile | 75 | Filled "Unknown" and flagged |
| Doubled "Inc Inc." in security names | 14 | Corrected |
| $1,000 AUM floor / extreme returns | 420 / 1,475 | Flagged, values kept |
| Months with no fee / weekend trades / activity after account closed | 7,350 / 40,630 / 2,410 | Flagged, values kept |
| Fee sources disagree, AUM excludes cash flows, holdings don't add up, and 3 minor items | — | Left as is; usage rules documented |

**Scorecard: the tables that changed** (all other tables scored 100% before and after)

| Table | Stage | Completeness | Key uniqueness | Type validity | Rule pass | Referential match |
|---|---|---|---|---|---|---|
| Transactions | Raw → Clean | 100 → 100 | 99.87 → 100 | **90.54 → 100** | 99.95 → 100 | **81.95 → 100** |
| Clients | Raw → Clean | 99.79 → 100 | 98.02 → 100 | 100 → 100 | 99.69 → 100 | 100 → 100 |
| Portfolio snapshots | Raw → Clean | 100 → 100 | 100 → 100 | 99.98 → 100 | 99.97 → 100 | 100 → 100 |

## Key judgment calls

**1. Use the fee table, not fee transactions, for revenue** (decision #15)
- *Decision:* Keep both tables, report revenue from `fact_fees`, and treat Advisory Fee transactions only as cash leaving client accounts.
- *Justification:* The fee table matches account values to the cent (AUM × rate ÷ 12), with one fee per client per month. The transactions follow no formula, fall on random days, and are not linked to trading.
- *Risk:* If the transactions are the true fees, revenue is understated by about $59M (22%).

**2. Flag unrealistic balances and returns instead of correcting them** (decisions #11, #12)
- *Decision:* Keep the $1,000-floor balances and extreme returns, but flag them and exclude them from performance averages.
- *Justification:* The true values cannot be recovered, and any replacement would be invented. Most affected clients are Conservative or Balanced, while larger clients stay within about ±14% of their benchmark.
- *Risk:* If some of these moves were genuine, those clients' performance is understated. Only 1.1% of snapshots are affected.

**3. Quarantine duplicates and copied transactions instead of deleting them** (decisions #5, #8)
- *Decision:* Move the 25 duplicate clients and 200 orphan transactions to quarantine files, each linked to the original row it copies.
- *Justification:* Every duplicate matches its original on 12 details, including the starting balance to the cent. Every orphan is an exact copy of a real transaction. Keeping them would double-count clients and $10.9M of activity.
- *Risk:* Very low. If any were genuine, they can be restored from the quarantine files.

**4. Correct negative Buy shares** (decision #4)
- *Decision:* Remove the minus sign on 835 Buys and flag them.
- *Justification:* The amount on each of these rows already equals shares × price without the minus sign, so the sign is the only inconsistent value.
- *Risk:* **Medium.** If these were Sells recorded as Buys, about $52M of trades would be recorded in the wrong direction. The flag allows them to be reviewed and reversed.

## Limitations

- **Fee revenue is uncertain:** two sources disagree ($204.7M vs $263.7M), and the chosen source is missing about 5.7% of months.
- **AUM excludes cash flows:** do not combine AUM with deposits or withdrawals ($327.4M net), or try to explain AUM changes with them.
- **Holdings cannot be rebuilt from trades:** 72% of sells exceed the shares bought in the data, so use AUM for portfolio value.
- **Trade dates look randomly generated:** 28% of trades fall on weekends (flagged). The calendar has no public holidays, so holiday trades are not flagged.
- **Some accounts closed too early or too late:** 2,410 transactions from inactive clients occur after their account history ends (flagged).
- **Unknown risk profiles:** 75 clients are compared against the default 60/40 benchmark, so their relative performance should be read with caution.
- **Small precision loss:** the 300 converted returns were truncated at 2 decimal places of a percent (within 0.0001).

---

`AI-assisted report — reviewed for factual accuracy on [26th of October 2026] by [Tommy Lyons]`
