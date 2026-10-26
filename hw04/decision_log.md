# Decision Log: Wildcat Capital Data Cleaning (HW04)

Each decision is written down **before** the cleaning code. The evidence comes from `scripts/01_profile.py` and its report `reports/dq_summary_raw.csv` (check IDs in brackets). Every file was read as text (`dtype=str`, `keep_default_na=False`).

Counts in entries 1–5 are on the raw data. Later entries leave out the 200 orphan transactions quarantined in #5, which is why some totals differ slightly (e.g. 59,755 sells in #4 vs 59,720 in #17).

**Possible decisions:** convert · standardize · fill · flag · quarantine · leave as is

## Summary

| # | Issue | Type | Decision |
|---|---|---|---|
| 1 | [State names written in full](#1-state-names-written-in-full) | ERROR | Standardize |
| 2 | [Returns stored as text percentages](#2-returns-stored-as-text-percentages) | ERROR | Convert |
| 3 | [Security IDs stored as "45.0"](#3-security-ids-stored-as-450) | ERROR | Convert |
| 4 | [Negative shares on Buy transactions](#4-negative-shares-on-buy-transactions) | ERROR | Standardize + flag |
| 5 | [Transactions for clients that don't exist](#5-transactions-for-clients-that-dont-exist) | ERROR | Quarantine |
| 6 | ["None" in advisor certifications](#6-none-in-advisor-certifications) | WARN | Leave as is |
| 7 | [Blank risk profile](#7-blank-risk-profile) | WARN | Fill + flag |
| 8 | [Duplicate clients](#8-duplicate-clients) | WARN | Quarantine |
| 9 | [Doubled "Inc Inc." in security names](#9-doubled-inc-inc-in-security-names) | WARN | Standardize |
| 10 | [Two near-identical fees](#10-two-near-identical-fees) | WARN | Leave as is |
| 11 | [AUM stuck at the $1,000 floor](#11-aum-stuck-at-the-1000-floor) | WARN | Flag |
| 12 | [Extreme returns](#12-extreme-returns) | WARN | Flag |
| 13 | [Same-day transaction pairs](#13-same-day-transaction-pairs) | WARN | Leave as is |
| 14 | [Months with no fee](#14-months-with-no-fee) | WARN | Flag |
| 15 | [Fee transactions vs the fee table](#15-fee-transactions-vs-the-fee-table) | WARN | Leave as is |
| 16 | [Trades on weekends](#16-trades-on-weekends) | WARN | Flag |
| 17 | [Selling more shares than bought](#17-selling-more-shares-than-bought) | WARN | Leave as is |
| 18 | [Inactive clients still transacting](#18-inactive-clients-still-transacting) | WARN | Flag |
| 19 | [AUM does not include deposits or withdrawals](#19-aum-does-not-include-deposits-or-withdrawals) | WARN | Leave as is |

## Major issues (ERROR findings)

### 1. State names written in full

| Field | Detail |
|---|---|
| **Table / column** | `dim_client.state` |
| **Evidence** | [DQ055] 78 of 2,525 clients have the full state name instead of the 2-letter code: Pennsylvania (25), Florida (15), New York (14), New Jersey (13), California (5), Illinois (4), Texas (2). Example: client 109 = "Pennsylvania". |
| **Dimension violated** | Validity, Consistency |
| **Decision** | **Standardize**: replace the 7 full names with their 2-letter codes (Pennsylvania → PA, etc.) using a lookup table. Stop with an error if a new, unknown name appears. |
| **Justification** | Clients are grouped and reported by state. If "PA" and "Pennsylvania" stay separate, Pennsylvania is missing 25 clients and their AUM, and regional reports are wrong. Each name matches exactly one code, so the fix is safe. |
| **Risk** | Very low. None of the 7 names could mean two different states. If a new spelling shows up later, the script stops instead of guessing. |

### 2. Returns stored as text percentages

| Field | Detail |
|---|---|
| **Table / column** | `fact_portfolio_snapshot.return_ytd` |
| **Evidence** | [DQ231] 300 of 129,547 rows are stored as text percentages, e.g. snapshot 42 = "9.28%". All other rows are decimals (e.g. 0.019504). Converting the column to numbers directly turns these 300 into blanks (NaN). |
| **Dimension violated** | Validity, Consistency |
| **Decision** | **Convert**: for values ending in "%", remove the % and divide by 100 ("9.28%" → 0.0928). Leave the other rows as they are, then make the whole column numeric. |
| **Justification** | YTD return is the main performance measure for clients and advisors. Losing these 300 rows would skew averages. Removing the % without dividing by 100 would turn 9.28% into 928%. As a check: return − benchmark return = alpha holds for every row, and after the fix it holds for these 300 rows too. That confirms dividing by 100 is correct. |
| **Risk** | Low. If some "%" values were already in decimal form, they would end up 100× too small, but the alpha check shows they weren't. The percentages only have 2 decimal places, so a small amount of precision is lost. |

### 3. Security IDs stored as "45.0"

| Field | Detail |
|---|---|
| **Table / column** | `fact_transactions.security_id` (joins to `dim_security.security_id`) |
| **Evidence** | [DQ261, DQ376] All 197,175 filled values end in ".0", e.g. txn 1 = "45.0", while `dim_security` uses "45". Joined as text, **0** trades match a security. Once converted to whole numbers, all 197,175 match. |
| **Dimension violated** | Validity, Consistency, Referential Integrity |
| **Decision** | **Convert**: change `security_id` to whole numbers (`Int64`) in both tables before joining. The 101,597 blank rows (deposits, withdrawals, fees) stay blank. |
| **Justification** | Any analysis by security, asset class, sector or benchmark needs this join. Without the fix, no trade can be linked to its security. The ".0" is just a formatting leftover (the column was probably saved as decimals because of the blanks); it doesn't mean a different ID. |
| **Risk** | Very low. It would only be a problem if an ID had a real decimal part (e.g. "45.5"), and there are none. `Int64` is used because it allows blanks; plain `int` would crash or turn blanks into 0. |

### 4. Negative shares on Buy transactions

| Field | Detail |
|---|---|
| **Table / column** | `fact_transactions.shares` |
| **Evidence** | [DQ339] 836 of 83,556 Buys (1.0%) have negative shares, e.g. txn 272: Buy, shares −261.9719, price $441.71, amount $115,715.61. All 59,755 Sells and all other Buys have positive shares. In all 836 rows, amount = shares × price when the minus sign is ignored. (One of the 836 is an orphan copy removed in #5, leaving 835.) |
| **Dimension violated** | Validity, Consistency |
| **Decision** | **Standardize + flag**: remove the minus sign, and add a column `shares_sign_fixed = True` on these 836 rows so they can be traced. |
| **Justification** | In this data, `txn_type` (Buy or Sell) says which way a trade went; the shares are always positive. The amount is positive and matches the shares without the minus sign, so the minus sign is the only part of the row that doesn't fit. Fixing it keeps $52.0M of real purchases counted correctly instead of treating them as sales. |
| **Risk** | Medium. If these were actually Sells labelled as Buys, the fix records them the wrong way round, which would distort position and cash-flow figures. The flag column lets the business review them and undo the change if needed. |

### 5. Transactions for clients that don't exist

| Field | Detail |
|---|---|
| **Table / column** | `fact_transactions.client_id` |
| **Evidence** | [DQ373, DQ342] 200 of 298,772 rows (0.07%) use client IDs that don't exist in `dim_client` (IDs 2702–3192, while `dim_client` stops at 2525). Each one is an exact copy of a real client's transaction (same advisor, date, type, security, shares, price and amount); only the client ID is different. |
| **Dimension violated** | Referential Integrity, Uniqueness |
| **Decision** | **Quarantine**: move the 200 rows to `quarantine/fact_transactions_orphans.csv`, noting the reason and the txn_id of the original transaction each one copies. Remove them from the cleaned table. |
| **Justification** | They can't be linked to any client, so they break client-level reports. Because each one copies a real transaction, keeping them would count $10.9M of activity twice. Moving them to a separate file instead of deleting them keeps a record in case the business wants to investigate. |
| **Risk** | Low. If they belonged to real clients missing from `dim_client`, those clients' activity would be understated. That's very unlikely, since every row is an exact copy of another client's transaction, and the quarantine file means they can be restored. |

## WARN findings

### 6. "None" in advisor certifications

| Field | Detail |
|---|---|
| **Table / column** | `dim_advisor.certifications` |
| **Evidence** | [DQ023] 6 of 25 advisors (IDs 2, 5, 11, 12, 13, 20) have the value "None". The column has no blanks or other null values. |
| **Dimension violated** | Completeness (apparent only; not an actual gap) |
| **Decision** | **Leave as is** |
| **Justification** | "None" is a real value meaning the advisor holds no certification. It is not missing data: every advisor has a value. |
| **Risk** | If a later step uses default `pd.read_csv`, "None" turns into NaN and these 6 advisors look like missing data. This column must always be read as text. |

### 7. Blank risk profile

| Field | Detail |
|---|---|
| **Table / column** | `dim_client.risk_profile` |
| **Evidence** | [DQ063, DQ352] 76 of 2,525 clients (3.0%) have a blank risk profile; 75 of them are real clients with activity. No other column (tier, age, account type) predicts the missing value. All 75 were given benchmark 3 (60/40 Blend) across 3,942 snapshots, which looks like a system default. |
| **Dimension violated** | Completeness |
| **Decision** | **Fill + flag**: replace blank with "Unknown" and add `risk_profile_missing = True`. Keep their benchmark as is. |
| **Justification** | Risk profile decides which benchmark a client is measured against. Guessing "Balanced" would hide a real gap, and leaving blanks risks these clients dropping out of reports. "Unknown" keeps them visible and honest, and the flag shows the business which clients need a profile collected. |
| **Risk** | Reports grouped by risk profile will show an extra "Unknown" group of 75 clients. Their performance vs. benchmark (alpha) should be treated with caution, since we don't know if 60/40 Blend is the right comparison for them. |

### 8. Duplicate clients

| Field | Detail |
|---|---|
| **Table / column** | `dim_client` (client_id 2501–2525) |
| **Evidence** | [DQ300, DQ319, DQ383] 25 clients match an existing client on all 12 other columns (age, city, ZIP, initial AUM to the cent, join date, advisor, etc.). Only the last name differs, by one letter (e.g. 2501 "Taylo" = 674 "Taylor"; 2515 "Pacen" = 889 "Pace"). The copies have 0 snapshots, fees or transactions, and no two real clients share this combination of details. |
| **Dimension violated** | Uniqueness |
| **Decision** | **Quarantine**: move the 25 rows to `quarantine/dim_client_duplicates.csv`, with the client_id of the original each one copies. Keep the original (lower ID, correct spelling, has all the activity). |
| **Justification** | Duplicates inflate the client count (2,525 instead of 2,500) and put 25 people in reports twice, e.g. clients per advisor and average starting AUM. Keeping the original is safe because it holds all the activity and the correctly spelled name. Nothing in the fact tables points at the copies, so removing them breaks no joins. |
| **Risk** | Very low. If any were real, separate people, we'd lose 25 clients. But they have no activity at all, and matching on 12 details including an exact starting balance rules that out. The quarantine file means they can be restored. |

### 9. Doubled "Inc Inc." in security names

| Field | Detail |
|---|---|
| **Table / column** | `dim_security.name` |
| **Evidence** | [DQ326] 14 of 500 securities (all equities) have a doubled suffix, e.g. security 6 = "Perez Inc Inc.". The other 267 equity names end in a single "Inc.". After the fix, no name clashes with another security. |
| **Dimension violated** | Validity, Consistency |
| **Decision** | **Standardize**: replace "Inc Inc." with "Inc." on these 14 rows only |
| **Justification** | It's a clear typo that makes reports and dashboards look careless. Trades join to securities by `security_id`, not name, so no numbers change. |
| **Risk** | Very low. The worst case is that a company's legal name really contains "Inc Inc.", which is extremely unlikely. The change only touches a display label, never an ID or an amount. |

### 10. Two near-identical fees

| Field | Detail |
|---|---|
| **Table / column** | `fact_fees` (fee_id 57446, 57490) |
| **Evidence** | [DQ309] 2 fees for client 1169 are identical except the date (2020-06-01 and 2024-04-01): Management, $1,000.00 AUM, 85.65 bps, $0.71. No client has two fees in the same month. |
| **Dimension violated** | Uniqueness (suspected, not confirmed) |
| **Decision** | **Leave as is** |
| **Justification** | Fees are charged once a month, so the same client being charged in two different months is expected. The values match only because the account sat at the $1,000 floor both times (see #11) and 85.65 bps is a common rate (70 occurrences). |
| **Risk** | Very low. If one were a real duplicate we'd overstate fees by $0.71. |

### 11. AUM stuck at the $1,000 floor

| Field | Detail |
|---|---|
| **Table / column** | `fact_portfolio_snapshot.aum` and `fact_fees.aum_basis` |
| **Evidence** | [DQ334, DQ330] 420 snapshots (92 clients, all Retail) show AUM of exactly $1,000.00, and no snapshot is ever below $1,000. Accounts usually crash into it in one month (median −86%) while their benchmark moved only between −5% and +6% that month. Example: client 1026 went from $33,870.66 to $1,000.00 in July 2022. 386 fees were charged on this $1,000 ($0.65–$0.80 each). The true balance can't be worked out: the return was calculated from the $1,000, so recalculating always gives $1,000 again. |
| **Dimension violated** | Accuracy/Plausibility |
| **Decision** | **Flag**: keep the rows and add `aum_at_floor = True` to the 420 snapshots and the 386 fees. Leave flagged rows out of return and fee-rate analysis. |
| **Justification** | $1,000 looks like a minimum the data was set to, not a real balance. Deleting the rows would leave gaps in clients' monthly history, and inventing a "correct" value would be a guess. Flagging keeps the history while stopping fake values from skewing averages. |
| **Risk** | If $1,000 were a real minimum balance (e.g. a firm policy), excluding these rows would leave out genuine small accounts. They are only 0.3% of snapshots, so totals barely change either way. |

### 12. Extreme returns

| Field | Detail |
|---|---|
| **Table / column** | `fact_portfolio_snapshot.return_ytd` (and `active_alpha_ytd`) |
| **Evidence** | [DQ333] 1,475 snapshots (178 clients, all Retail) have a YTD return below −90% or above +100%, up to +9,467%. Benchmarks only ranged from −24% to +27%. There are 797 one-month moves bigger than ±50%, while the benchmark moved at most 6%. Example: client 29 went from $9,105 to $52,090 in July 2022 (+287% YTD) while the market fell. 249 of these rows are also at the $1,000 floor (#11), and recoveries from the floor create the largest values. |
| **Dimension violated** | Accuracy/Plausibility |
| **Decision** | **Flag**: add `return_extreme = True` to these 1,475 rows. Leave them out of return, alpha and advisor-performance averages. Keep their AUM for fee and balance reporting. |
| **Justification** | Returns this far from the benchmark only happen with very risky portfolios (one stock, leverage). Most of these clients (131 of 178) are Conservative, Moderately Conservative or Balanced, and HNW/UHNW clients never show it; they stay within about ±14% of their benchmark. A few of these values can make average performance meaningless. Flagging keeps the full monthly history and lets analysts choose to include or exclude them. |
| **Risk** | If some jumps were real (e.g. a small account holding one stock that soared), excluding them would understate those clients' performance. Only 1.1% of snapshots are flagged, so overall averages become more reliable, not less. |

### 13. Same-day transaction pairs

| Field | Detail |
|---|---|
| **Table / column** | `fact_transactions` (same-day pairs) |
| **Evidence** | [DQ315] 673 deposits and withdrawals have another deposit or withdrawal for the same client on the same day, with a different amount. Example: client 1 deposited $94,893.52 and $26,587.27 on 2024-09-25. Separately, 14 Advisory Fees repeat the same amount on two different dates, e.g. client 1060 was charged $306.32 in 2020-03 and 2022-11. |
| **Dimension violated** | Uniqueness (suspected, not confirmed) |
| **Decision** | **Leave as is** |
| **Justification** | Clients can deposit or withdraw more than once in a day, and different amounts mean these are separate transactions. The same fee amount on different dates is a coincidence, as in #10. 377 same-day Advisory Fees were also flagged. They don't fit the pattern in `fact_fees` (exactly one fee per client per month, on the 1st), so they're looked at under the fee reconciliation (DQ358), not here. |
| **Risk** | Low. If some same-day rows were real duplicates, those clients' deposits or withdrawals would be overstated. Because the amounts differ, a double entry is unlikely. |

### 14. Months with no fee

| Field | Detail |
|---|---|
| **Table / column** | `fact_portfolio_snapshot` ↔ `fact_fees` |
| **Evidence** | [DQ357] 7,350 of 129,547 snapshot months (5.7%) have no matching fee in `fact_fees`. 2,261 of 2,500 clients are missing at least one month, usually 1–4. The gaps are spread evenly across tiers, years and calendar months, are mostly single months, and aren't linked to new clients, departing clients or the $1,000 floor. |
| **Dimension violated** | Completeness |
| **Decision** | **Flag**: add `fee_missing = True` to these 7,350 snapshots. Leave `fact_fees` as it is. |
| **Justification** | The gaps look like fee records that were lost or never recorded, not deliberate waivers, which would cluster (e.g. new clients or one tier). Inventing fees would mean guessing the rate and fee type. Flagging keeps the fee table factual and lets revenue reports state that ~5.7% of months have no fee record. |
| **Risk** | Revenue from `fact_fees` is understated, roughly $17.9M over five years at the average rate (an estimate). If some gaps were real waivers, flagging them as "missing" overstates the problem, but nothing in the data is changed. |

### 15. Fee transactions vs the fee table

| Field | Detail |
|---|---|
| **Table / column** | `fact_transactions` (Advisory Fee) ↔ `fact_fees` |
| **Evidence** | [DQ358] The two tables give different versions of fee revenue: `fact_fees` totals **$204.7M** over five years and the Advisory Fee transactions total **$263.7M** ($59M more). None of the 35,742 fee transactions matches the fee table, whether compared by month, by quarter, by fee type or with a one-month delay. The fee table has one fee per client per month and follows an exact formula (AUM × rate ÷ 12, to the cent). The transactions appear about 14 times per client on random days, sometimes twice on the same day (377 rows, see #13), and follow no formula. Fees aren't linked to sells either: there's no difference in fee size in months with or without sells. |
| **Dimension violated** | Consistency, Accuracy |
| **Decision** | **Leave as is**: keep both tables unchanged. Use `fact_fees` as the source of truth for fee revenue. Don't add up Advisory Fee transactions as revenue. |
| **Justification** | The fee table follows a clear, checkable rule and agrees with the account values in the snapshots. The transactions only roughly follow account size, with irregular amounts and dates. The transactions stay in the data because they still show money leaving client accounts. |
| **Risk** | If the transactions were the true fees, revenue would be understated by about $59M (22%). Also, `fact_fees` is missing fees in 5.7% of months (#14), so revenue from it is somewhat understated as well. |

### 16. Trades on weekends

| Field | Detail |
|---|---|
| **Table / column** | `fact_transactions.txn_date` (Buy/Sell) ↔ `dim_date.is_trading_day` |
| **Evidence** | [DQ359] 40,630 of 143,218 Buys and Sells (28.4%) fall on a Saturday or Sunday, when markets are closed. Trades are spread evenly across all 7 days (~14.3% each), which is exactly what random dates would give, and all 2,500 clients are affected. Deposits, withdrawals, dividends and fees show the same ~28%. Note: `dim_date` has no public holidays, so it only marks weekends as non-trading days. |
| **Dimension violated** | Accuracy/Plausibility |
| **Decision** | **Flag**: add `non_trading_day = True` to these 40,630 trades. Keep the dates as they are. |
| **Justification** | The dates look randomly generated, not recorded on real trading days. Moving them to the next Monday would mean inventing dates and could push trades into the next month. Monthly and yearly figures are unaffected, and the flag lets daily analysis (e.g. trades by day of week) filter these rows out. |
| **Risk** | If kept in daily analysis, reports would show trading on days the market was closed. Because the calendar has no holidays, some trades on holidays are not flagged, so the true number of non-trading-day trades is slightly higher. |

### 17. Selling more shares than bought

| Field | Detail |
|---|---|
| **Table / column** | `fact_transactions` (Buy/Sell `shares`) |
| **Evidence** | [DQ361] Keeping a running total of shares per client and security, 42,975 of 59,720 sells (72%) take the client below zero. 24,166 of them sell a security the client never bought in the data. After five years, 39% of client–security positions end negative. Holdings from before 2020 don't explain it: clients who joined in 2020 or later show the same rate (71.5%). |
| **Dimension violated** | Consistency |
| **Decision** | **Leave as is**: keep all trades unchanged. Don't use transactions to calculate holdings or positions; use AUM from `fact_portfolio_snapshot` for portfolio value. |
| **Justification** | Each trade is valid on its own (date, client, security, shares, price and amount all agree). The problem only appears when trades are added up, so removing or flagging 72% of sells would damage the data without fixing anything. Trade counts, trade values and trading activity can still be used. |
| **Risk** | If someone calculates holdings, position values or profit/loss from transactions, the results will be wrong (negative holdings). Some sells may be genuine shares transferred in from another firm, which the data doesn't record. |

### 18. Inactive clients still transacting

| Field | Detail |
|---|---|
| **Table / column** | `fact_transactions` ↔ `dim_client.is_active` / `fact_portfolio_snapshot` |
| **Evidence** | [DQ362] 175 clients are inactive: their snapshots and fees stop between Dec 2022 and Nov 2023. Yet 2,410 of their transactions (131 clients) are dated 1–12 months after their last snapshot, including 689 Buys and 278 Deposits ($13.4M deposited, $11.8M withdrawn, $1.9M in fees). All of them stop by the end of 2023. |
| **Dimension violated** | Consistency |
| **Decision** | **Flag**: add `after_account_closed = True` to these 2,410 transactions. Keep the rows. |
| **Justification** | The snapshot table and the transactions table disagree on when these accounts closed. A few final sells and withdrawals would be normal when a client leaves, but new Buys and Deposits a year later are not. Flagging keeps the possible closing transactions while letting reports on activity or active clients leave these rows out. |
| **Risk** | If the snapshots stopped too early and these clients were really still active, excluding the flagged rows would understate their activity. If kept in, closed clients look active and activity is overstated. |

### 19. AUM does not include deposits or withdrawals

| Field | Detail |
|---|---|
| **Table / column** | `fact_portfolio_snapshot.aum` ↔ `fact_transactions` (Deposit / Withdrawal) |
| **Evidence** | Found while investigating the $1,000 floor (#11); not a profiler check. AUM follows one formula for 100% of testable rows: **AUM = last December's AUM × (1 + YTD return)**. Deposits and withdrawals are never part of it: there's no link between them and AUM changes in the same, previous or next month, and only 8 of 650 large AUM jumps line up with a deposit or withdrawal. Clients deposited $1,818.8M and withdrew $1,491.4M over five years (net +$327.4M), none of which shows up in AUM. |
| **Dimension violated** | Consistency, Completeness |
| **Decision** | **Leave as is**: don't change AUM or the transactions. Use AUM for balances, returns and fees; use deposits and withdrawals only as cash-flow figures. Don't add them to AUM or use them to explain AUM changes. |
| **Justification** | AUM agrees with the rest of the data (return, alpha and fees all match it), so changing it would break that. In a real firm, deposits and withdrawals would change AUM, so one of the two tables is probably incomplete, but the data can't tell us which. A clear usage rule avoids misleading results without changing any data. |
| **Risk** | If AUM should include cash flows, account sizes, AUM totals and the fees calculated from them are off by each client's net deposits (about $327M in total). Anyone combining the two tables will get results that don't add up. |
