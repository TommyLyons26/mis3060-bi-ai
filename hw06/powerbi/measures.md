# HW6 — DAX Measure Library (Part A)

All measures live in the `_Measures` table of `powerbi/hw06.pbix`.

**Additivity patterns used**
- **SUM** — the value adds up across every dimension, including time (flows such as fees and transactions).
- **Last balance** — the value is a balance, so only the last snapshot in the filter is used (never summed across dates).
- **Recompute-and-weight** — the numerator and denominator are aggregated separately and then combined into a ratio or weighted average (never an average of ratios).

| # | Measure | Pattern | Format |
|---|---|---|---|
| – | Total Fees | SUM | Currency, 0 dp |
| – | Net Flows | SUM | Currency, 0 dp |
| 0 | AUM (naive SUM) | SUM (**wrong** for a balance) | Currency, 0 dp |
| 1 | Ending AUM | Last balance | Currency, 0 dp |
| 2 | Ending Clients | Last balance | Whole number |
| 3 | Avg AUM per Client | Recompute-and-weight | Currency, 0 dp |
| 4 | Ending AUM LY | Last balance | Currency, 0 dp |
| 4 | AUM YoY % | Recompute-and-weight | %, 1 dp |
| 5 | Ending AUM PM | Last balance | Currency, 0 dp |
| 5 | AUM MoM % | Recompute-and-weight | %, 1 dp |
| 6 | Avg Monthly AUM | Recompute-and-weight | Currency, 0 dp |
| 7 | Fee Yield (bps) | Recompute-and-weight | Decimal, 1 dp |
| 8 | Organic Growth Rate | Recompute-and-weight | %, 1 dp |
| 9 | AUM-Weighted Alpha | Recompute-and-weight | %, 2 dp |
| 10 | Alpha Signal | Recompute-and-weight (relabels #9) | Text |
| 11 | Top 10 Client Share | Recompute-and-weight | %, 1 dp |

---

## Base measures

### Total Fees
```DAX
Total Fees = SUM ( fact_fees[amount] )
```
**Pattern:** SUM — fees are a flow, so they add up across clients and over time.
**Meaning:** The total fee revenue Wildcat earned in the selected period.

### Net Flows
```DAX
Net Flows =
    CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Deposit" )
  - CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Withdrawal" )
```
**Pattern:** SUM — deposits and withdrawals are flows, so each side is summed and then netted.
**Meaning:** How much new money clients put in, minus what they took out, in the selected period.

---

## 0. AUM (naive SUM) — deliberately wrong, never used on a report
```DAX
AUM (naive SUM) = SUM ( fact_portfolio_snapshot[aum] )
```
**Pattern:** SUM — the wrong pattern for a balance. AUM is semi-additive: it adds up across clients but not across dates.
**Meaning:** Not valid as a balance once the filter covers more than one snapshot. Over a year it adds 12 month-end balances, overstating AUM about 12×. For a single snapshot date it equals Ending AUM, which is why a month-level view can hide the bug. The same sum is a valid ingredient in measures 6 and 7, where it is divided back down by the number of months.

## 1. Ending AUM
```DAX
Ending AUM =
CALCULATE (
    SUM ( fact_portfolio_snapshot[aum] ),
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
)
```
**Pattern:** Last balance — finds the latest snapshot date in the filter and sums AUM on that date only.
**Meaning:** How much money Wildcat manages at the end of the selected period.

## 2. Ending Clients
```DAX
Ending Clients =
CALCULATE (
    DISTINCTCOUNT ( fact_portfolio_snapshot[client_id] ),
    LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) )
)
```
**Pattern:** Last balance — counts distinct clients in the last snapshot only, so clients who left during the period are not included.
**Meaning:** How many clients Wildcat has at the end of the selected period.

## 3. Avg AUM per Client
```DAX
Avg AUM per Client = DIVIDE ( [Ending AUM], [Ending Clients] )
```
**Pattern:** Recompute-and-weight — both parts are recomputed at the last snapshot, then divided.
**Meaning:** The typical account size at period end, which shows whether Wildcat is serving larger or smaller clients.

## 4. Ending AUM LY and AUM YoY %
```DAX
Ending AUM LY = CALCULATE ( [Ending AUM], SAMEPERIODLASTYEAR ( dim_date[date] ) )
```
**Pattern:** Last balance — Ending AUM re-evaluated with the date filter shifted back one year.
**Meaning:** What Wildcat managed at the same point last year.

```DAX
AUM YoY % = DIVIDE ( [Ending AUM] - [Ending AUM LY], [Ending AUM LY] )
```
**Pattern:** Recompute-and-weight — the growth ratio is calculated from two last balances.
**Meaning:** How much assets under management grew over the year, from new money and market returns combined.

## 5. Ending AUM PM and AUM MoM %
```DAX
Ending AUM PM = CALCULATE ( [Ending AUM], DATEADD ( dim_date[date], -1, MONTH ) )
```
**Pattern:** Last balance — Ending AUM re-evaluated with the date filter shifted back one month.
**Meaning:** What Wildcat managed at the end of the previous month.

```DAX
AUM MoM % = DIVIDE ( [Ending AUM] - [Ending AUM PM], [Ending AUM PM] )
```
**Pattern:** Recompute-and-weight — the growth ratio is calculated from two last balances.
**Meaning:** Month-on-month change in assets, an early signal of momentum or outflows. It is meaningful at month level only.

## 6. Avg Monthly AUM
```DAX
Avg Monthly AUM =
DIVIDE (
    SUM ( fact_portfolio_snapshot[aum] ),
    DISTINCTCOUNT ( fact_portfolio_snapshot[snapshot_date] )
)
```
**Pattern:** Recompute-and-weight — the sum of balances is divided by the number of snapshot dates, which cancels the over-counting.
**Meaning:** The average amount Wildcat managed across the period, the fair base for anything earned over time, such as fees.

## 7. Fee Yield (bps)
```DAX
Fee Yield (bps) = DIVIDE ( [Total Fees] * 12 * 10000, SUM ( fact_portfolio_snapshot[aum] ) )
```
**Pattern:** Recompute-and-weight — fees (`fact_fees`) and AUM (`fact_portfolio_snapshot`) are summed separately through the shared dimensions, then combined. ×12 annualises the monthly rate and ×10,000 converts it to basis points.
**Meaning:** How many basis points of fee revenue Wildcat earns each year per dollar it manages.

## 8. Organic Growth Rate
```DAX
Organic Growth Rate = DIVIDE ( [Net Flows], [Ending AUM LY] )
```
**Pattern:** Recompute-and-weight — net flows (SUM) divided by last year's closing balance (last balance).
**Meaning:** How much Wildcat grew from new client money alone, separate from market performance.

## 9. AUM-Weighted Alpha
```DAX
AUM-Weighted Alpha =
VAR LastRows =
    CALCULATETABLE (
        fact_portfolio_snapshot,
        LASTNONBLANK ( dim_date[date], CALCULATE ( COUNTROWS ( fact_portfolio_snapshot ) ) ),
        fact_portfolio_snapshot[is_return_suspect] <> 1,
        NOT ISBLANK ( fact_portfolio_snapshot[active_alpha_ytd] )
    )
RETURN
    DIVIDE (
        SUMX ( LastRows, fact_portfolio_snapshot[aum] * fact_portfolio_snapshot[active_alpha_ytd] ),
        SUMX ( LastRows, fact_portfolio_snapshot[aum] )
    )
```
**Pattern:** Recompute-and-weight — the alpha × AUM total and the AUM total are computed separately at the last snapshot, excluding suspect and blank returns, then divided.
**Meaning:** How far clients beat or trailed their benchmarks year-to-date, with each client weighted by the money they hold.

## 10. Alpha Signal
```DAX
Alpha Signal =
VAR a = [AUM-Weighted Alpha]
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( a ), BLANK (),
        a >= 0.02, "Outperforming",
        a <= -0.02, "Lagging",
        "In line"
    )
```
**Pattern:** Recompute-and-weight — inherited from measure 9, which it relabels as text.
**Meaning:** A quick verdict on whether a segment is beating its benchmark (≥ +2%), lagging it (≤ −2%), or in line.

## 11. Top 10 Client Share
```DAX
Top 10 Client Share =
VAR Top10 = TOPN ( 10, VALUES ( dim_client[client_id] ), [Ending AUM] )
RETURN DIVIDE ( CALCULATE ( [Ending AUM], Top10 ), [Ending AUM] )
```
**Pattern:** Recompute-and-weight — Ending AUM of the 10 largest clients in the current filter divided by Ending AUM of all clients in that filter.
**Meaning:** How dependent Wildcat (or a tier) is on its biggest clients, a measure of concentration risk.


