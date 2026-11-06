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

# Part C

## (a) Ending AUM vs. SUMX over clients

| Measure (no filters) | Value |
|---|---|
| `Ending AUM` | $12,729,572,078.86 |
| `SUMX ( VALUES ( dim_client[client_id] ), [Ending AUM] )` | $13,149,297,713.80 |
| **Difference** | **$419,725,634.94** |

With no filters applied, `Ending AUM` finds the latest snapshot date in the whole dataset (December 2024) and sums the AUM of the 2,325 clients in that snapshot.

The SUMX version iterates over all 2,500 clients. Context transition filters `[Ending AUM]` to one client at a time, so "latest snapshot" becomes *that client's* last snapshot rather than the firm's. Current clients still return their December 2024 balance, but clients who have left return their final balance from the month they departed, so SUMX adds money the firm no longer holds.

**Where the $419.7M comes from.** Checked against `dim_client[is_active]`:

```DAX
EVALUATE
ROW (
    "Inactive clients", CALCULATE ( COUNTROWS ( dim_client ), dim_client[is_active] = FALSE () ),
    "Their last AUM",   CALCULATE ( SUMX ( VALUES ( dim_client[client_id] ), [Ending AUM] ),
                                    dim_client[is_active] = FALSE () )
)
```

This returns 175 inactive clients with a combined last-known AUM of $419,725,634.94, exactly the gap between the two measures. These clients do not appear in the December 2024 snapshot, so `Ending AUM` excludes them while the SUMX version still counts their final balances.

**Which answers "How much do we manage today?"** `Ending AUM` ($12.73B). It counts only money the firm actually holds at the latest date. The SUMX total mixes balances from different dates and includes $419.7M from departed clients, overstating current AUM by about 3.3%.

## (b) Fee Yield vs. ICE 9 Effective Fee Rate (2024)

| 2024 | Denominator | Value |
|---|---|---|
| `Fee Yield (bps)` | `SUM(fact_portfolio_snapshot[aum])` = $135,459,843,783.73 | **43.15 bps** |
| `Effective Fee Rate (bps)` | `SUM(fact_fees[aum_basis])` = $128,385,303,527.10 | **45.53 bps** |

Both use the same numerator, 2024 `[Total Fees]` = $48,714,005.93, and the same ×12 ×10,000 scaling. Only the denominator differs.

**Cause (found in pandas).** In 2024, `fact_portfolio_snapshot` has 27,900 client-months but `fact_fees` has only 26,216. That leaves **1,684 client-months that appear in the snapshot table (with a balance) but have no row at all in `fact_fees`**. For the 26,216 client-months that appear in both tables, `aum_basis` equals the snapshot `aum` exactly, so the tables agree on balances and the fees table is simply missing rows. The 1,684 missing client-months hold **$7,074,540,256.63** of AUM, which is exactly the gap between the two denominators ($135.46B − $128.39B).

Fee Yield divides fees by all AUM, including AUM that has no fee record. Effective Fee Rate divides only by AUM that has a fee row, so its denominator is smaller and the rate is higher.

**Data limitation.** Fee records are incomplete: about 6% of 2024 client-months have a balance but no fee row. The gaps are spread across 1,082 clients. The data can't tell us whether those fees were waived (truly zero) or never recorded:
- **If waived,** Fee Yield (43.15 bps) is the true firm-wide yield and Effective Fee Rate overstates it.
- **If missing,** Fee Yield understates the real rate.

Either way, neither number can be fully trusted until the missing fee rows are explained.

## (c) AUM-Weighted Alpha: last snapshot only, suspects excluded

| Version (no filters, December 2024 snapshot) | Value |
|---|---|
| `AUM-Weighted Alpha`, suspects excluded (2,177 rows) | **1.448%** (0.014480) |
| Simple mean of `active_alpha_ytd`, same 2,177 rows | **0.879%** (0.008788) |
| AUM-weighted, suspects included (2,325 rows) | **1.668%** (0.016678) |

**Why the last snapshot only.** `active_alpha_ytd` is a year-to-date running total that resets every January. Each month's value means "how far ahead of the benchmark the client is so far this year". So only the December snapshot holds the complete full-year figure, and every earlier month is an incomplete, partial-year number. Client 1 shows this: their alpha resets to −0.15% after January 2024 and builds to +1.61% by December 2024, which is their full 2024 result. Averaging all 12 of client 1's 2024 values gives only about +0.19%, because the early months drag it down.

**Why exclude `is_return_suspect = 1`.** The 148 suspect rows in the last snapshot have impossible returns. Their alphas range from −121% to +7,134%, while every clean row falls between −50% and +50%. These are data errors, not real performance. Most are small accounts, but including them still pushes the weighted alpha from 1.45% to 1.67%, a 0.22 percentage point distortion from broken data.

**Weighted vs. simple mean.** The simple mean (0.88%) gives a $5,000 account the same say as a $40M account, so it shows how the typical client did. Weighting by AUM (1.45%) shows how the firm's money performed, which is what matters for the firm's results. Because the weighted figure is higher, larger accounts outperformed smaller ones.

## (d) Organic Growth Rate by client tier (2024)

| Tier | AUM YoY % | Organic Growth Rate | Other growth (YoY − Organic) | Net new money | Share of firm net new money |
|---|---|---|---|---|---|
| Retail | 19.13% | **9.87%** | 9.26% | $44,184,047.61 | **57.0%** |
| HNW | 19.64% | 1.18% | 18.46% | $25,227,406.26 | 32.5% |
| UHNW | 19.59% | **0.10%** | 19.49% | $8,101,601.39 | 10.5% |

**What it says.** All three tiers grew by roughly the same amount in 2024, about 19–20% YoY, but for very different reasons. UHNW's growth came almost entirely from sources other than new money: clients added only 0.10% in net flows, and the remaining 19.49 percentage points came mainly from investment returns. HNW is similar, with 1.18% organic and 18.46% other growth. Retail is the only tier bringing in substantial new money, with 9.87% organic growth and 57.0% of the firm's net new money. Outside Retail, Wildcat's growth was driven mostly by the market rather than by new money.

**What it does not tell you.**
1. **Scale.** Organic Growth is a percentage, so it hides size. Retail has the highest rate and the largest share of new money, but it is the smallest tier, so a large percentage can still be a small dollar amount.
2. **What the "other" growth is.** YoY minus Organic is a residual. It mixes market returns with fees deducted and clients joining, leaving or changing tier, and the measure cannot separate them.
3. **Where the new money came from.** Net flows don't show whether money came from new clients or existing ones topping up, or from many small deposits or a few large ones.
4. **Profitability.** Different tiers pay different fee rates, so a dollar of growth is worth more in some tiers than others. Organic Growth treats every dollar the same.
5. **Durability.** Market-driven growth can reverse in a down year. Only organic growth reflects clients choosing to give Wildcat more money.
