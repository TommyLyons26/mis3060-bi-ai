# Wildcat Capital — Clean Data

Produced by `scripts/02_clean.py` from the raw files in `Wildcat Capital/` (never modified).
Every change is explained in `decision_log.md` and recorded in `data/audit/`.

## Files

| File | Raw rows | Clean rows | Quarantined |
|---|---|---|---|
| `dim_advisor.csv` | 25 | 25 | 0 |
| `dim_benchmark.csv` | 8 | 8 | 0 |
| `dim_client.csv` | 2,525 | 2,500 | 25 |
| `dim_date.csv` | 1,827 | 1,827 | 0 |
| `dim_security.csv` | 500 | 500 | 0 |
| `fact_fees.csv` | 122,197 | 122,197 | 0 |
| `fact_portfolio_snapshot.csv` | 129,547 | 129,547 | 0 |
| `fact_transactions.csv` | 298,772 | 298,572 | 200 |

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
| `dim_client` | `risk_profile_missing` | 75 | Risk profile was blank and is now "Unknown". Treat their alpha with caution (benchmark is a default). |
| `fact_portfolio_snapshot` | `aum_at_floor` | 420 | AUM is exactly $1,000 (an artificial floor). Exclude from return and fee-rate analysis. |
| `fact_portfolio_snapshot` | `return_extreme` | 1,475 | YTD return < −90% or > +100%. Exclude from return, alpha and advisor-performance averages. |
| `fact_portfolio_snapshot` | `fee_missing` | 7,350 | No fee recorded in `fact_fees` for this client-month. Revenue for these months is unknown. |
| `fact_fees` | `aum_at_floor` | 386 | Fee calculated on the $1,000 floor AUM. Exclude from fee-rate analysis. |
| `fact_transactions` | `shares_sign_fixed` | 835 | Buy had negative shares; the minus sign was removed (amount confirmed = shares × price). |
| `fact_transactions` | `non_trading_day` | 40,630 | Buy/Sell dated on a weekend. Exclude from daily analysis; fine for monthly totals. |
| `fact_transactions` | `after_account_closed` | 2,410 | Inactive client's transaction after their last snapshot month. Exclude from activity / active-client counts. |

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
