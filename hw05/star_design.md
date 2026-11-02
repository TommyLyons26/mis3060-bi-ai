# Wildcat Capital — Star Schema Design

## Part A — Keys

| Table | Type | Primary key | Foreign keys (column → table[column]) |
|---|---|---|---|
| dim_advisor | Dimension | advisor_id | — |
| dim_benchmark | Dimension | benchmark_id | — |
| dim_client | Dimension | client_id | advisor_id → dim_advisor[advisor_id] |
| dim_date | Dimension | date_id | — |
| dim_security | Dimension | security_id | benchmark_id → dim_benchmark[benchmark_id] |
| fact_fees | Fact | fee_id | client_id → dim_client[client_id]<br>advisor_id → dim_advisor[advisor_id]<br>fee_date → dim_date[date] |
| fact_portfolio_snapshot | Fact | snapshot_id | client_id → dim_client[client_id]<br>advisor_id → dim_advisor[advisor_id]<br>benchmark_id → dim_benchmark[benchmark_id]<br>snapshot_date → dim_date[date] |
| fact_transactions | Fact | txn_id | client_id → dim_client[client_id]<br>advisor_id → dim_advisor[advisor_id]<br>security_id → dim_security[security_id] *(can be blank — see note)*<br>txn_date → dim_date[date] |

### Notes

- **Date keys match `dim_date[date]`, not `dim_date[date_id]`.** The fact date columns (`fee_date`, `snapshot_date`, `txn_date`) hold calendar dates such as `2020-01-01`. Every value matches a row in `dim_date[date]`, and none matches `dim_date[date_id]`, which is a sequential number (1, 2, 3…).
- **`fact_transactions.security_id` can legitimately be blank.** It is blank in 101,528 of 298,572 rows. All of those rows are cash movements (Deposit, Withdrawal, Advisory Fee), which involve no security. Every Buy, Sell and Dividend row has a valid `security_id`.


## Part B — Grain

- **fact_fees:** One row represents one fee charged to one client for one month.
- **fact_portfolio_snapshot:** One row represents one client's portfolio position (AUM and returns) as of one month-start date.
- **fact_transactions:** One row represents one individual transaction (buy, sell, dividend, deposit, withdrawal or advisory fee) made in one client's account on one date.

## Part C — Measures

| Table | Column | Type | What it means for summing/averaging (with a simple example) |
|---|---|---|---|
| fact_fees | amount | Additive | A fee in dollars, like a bill, so it can be summed across clients, months or both. $100 in January plus $100 in February means $200 was really paid. |
| fact_fees | aum_basis | Semi-additive | A balance at one moment, like a bank balance, so it can be summed across clients for one month but never across months. $1,000 in January and $1,000 in February is still only $1,000. |
| fact_fees | bps_charged | Non-additive | A fee rate, like an interest rate, so it must be averaged (weighted by aum_basis) rather than summed. A 1% rate plus another 1% rate isn't a 2% rate on anything. |
| fact_portfolio_snapshot | aum | Semi-additive | A balance at one moment, so it can be summed across clients for one month but never across months, because that counts the same money twice. |
| fact_portfolio_snapshot | return_ytd | Non-additive | Year-to-date growth that is already a running total, so never sum it; use the latest month or an AUM-weighted average. December's figure already includes January to November. |
| fact_portfolio_snapshot | benchmark_return_ytd | Non-additive | The same as return_ytd but for the market index, so it's never summed, for the same reason. |
| fact_portfolio_snapshot | active_alpha_ytd | Non-additive | Return minus benchmark return (how much the client beat or trailed the market), so it's never summed. It's the difference between two percentages. |
| fact_portfolio_snapshot | cash_pct | Non-additive | The share of the portfolio held in cash, so it must be averaged (weighted by AUM), not summed. One client at 2% and another at 3% doesn't make 5% in cash. |
| fact_transactions | amount | Additive* | Dollars moved in each transaction, which can be summed across clients and months, but only within one txn_type because every value is positive. A $500 deposit plus a $500 withdrawal would show $1,000 when the net change is $0. |
| fact_transactions | shares | Additive* | The number of shares traded, which can be summed only within one security and one type. 100 Apple plus 100 Apple is 200 Apple, but 100 Apple plus 100 Tesla means nothing. |
| fact_transactions | price | Non-additive | The price of one share, so it's averaged (weighted by shares) or the latest price is used, never summed. A $10 stock plus a $50 stock isn't "$60" of anything. |

\* Additive with a condition: filter by txn_type first, and also by security for shares.

**Simple rule:** money that flowed is additive. A balance at a moment is semi-additive: add across people, not across time. A rate, percentage or price is non-additive: average it, never add it.

### Numeric columns that are not measures

- **Keys:**
  - fee_id, snapshot_id, txn_id (the fact tables' own keys).
  - client_id, advisor_id, benchmark_id, security_id (foreign keys).
  - These are labels, so adding or averaging them means nothing.
- **Date parts:** year and month in fact_portfolio_snapshot. Use them for grouping, not adding.
- **Flags (0/1):** is_return_suspect and is_post_departure_txn. Summing them only counts how many rows are flagged.

### Numeric attributes in dimension tables that should never be summed

- **dim_advisor:**
  - years_experience: average it. Total years across advisors means nothing.
  - aum_target_mm: a goal, not real money.
- **dim_client:**
  - age: average it, don't add it.
  - zip_code: a code, not a quantity.
  - initial_aum: each client's starting balance on a different date, so a total mixes points in time.
- **dim_date:** year, quarter, month, week_of_year, is_month_end, is_quarter_end, is_year_end and is_trading_day. These are for grouping and filtering only.
- **dim_security:** expense_ratio_bps, a rate. Average it, don't add it. It's blank for 281 securities.

## Part E — Relationships and design questions

dim_client, dim_advisor and dim_date are conformed dimensions: each one is shared by all three fact tables (fact_fees, fact_portfolio_snapshot and fact_transactions), so the same client, advisor or date filter works consistently across fees, snapshots and transactions.

**(a) Why do some transaction rows have no security_id, and is that a defect?**

101,528 of the 298,572 rows in fact_transactions have a blank security_id. Every one of them is a Deposit, Withdrawal or Advisory Fee: cash moving into or out of an account, or a fee being paid, with no stock or fund bought or sold. Every Buy, Sell and Dividend row has a valid security_id, and every filled-in value exists in dim_security. So the blanks are expected and not a defect. In Power BI they show as one (Blank) row of $3,573,887,227.67 when transactions are grouped by security, which is the total value of the cash rows.

**(b) advisor_id appears in dim_client and on all three fact tables. Which relationship(s) did you keep active, and why?**

I kept the three direct relationships active: fact_fees, fact_portfolio_snapshot and fact_transactions each connect to dim_advisor[advisor_id]. I set dim_client[advisor_id] → dim_advisor to inactive. Without this, there would be two routes from dim_advisor to each fact table: one direct, and one through dim_client. Power BI allows only one active route between two tables. I kept the direct route for two reasons. First, the advisor_id on a fact row records the advisor linked to that fee, snapshot or transaction when it happened, while dim_client.advisor_id only holds the client's current advisor. If a client were reassigned, the direct route would still credit past activity to the right advisor. Second, it keeps every fact table one step from dim_advisor, rather than going through dim_client. In this data, the advisor on every fact row matches the client's advisor in dim_client, so the choice changes no numbers today, and an advisor slicer correctly filters all three fact tables.

**(c) The date dimension has its own date_id, but the facts store calendar dates. Which column did you join on, and why?**

I joined fee_date, snapshot_date and txn_date to dim_date[date], not dim_date[date_id]. The fact tables store real calendar dates such as 2020-01-01, while date_id is just a counter (1, 2, 3…). Every fact date appears in dim_date[date], and none of them matches a date_id, so joining on date_id would link nothing. dim_date[date] is also unique (1,827 dates for 1,827 rows), so it works as the "one" side of a many-to-one relationship.

**(d) Star or snowflake: does anything in the eight tables connect one dimension to another? Did you keep it?**

Two links connect one dimension to another. dim_security[benchmark_id] → dim_benchmark is the first. I kept it active because fact_transactions has no benchmark_id, so this is the only way to analyse transactions by benchmark (for example, total buys of securities measured against the S&P 500). It doesn't conflict with the snapshot's own direct link to dim_benchmark, because each fact table has only one route there. dim_client[advisor_id] → dim_advisor is the second. I kept it in the model but inactive, for the reasons in (b). Because of these links, the model is mostly a star with one small snowflake branch (fact_transactions → dim_security → dim_benchmark). Three fact tables share the same client, advisor and date dimensions, so overall it's a fact constellation (also called a galaxy schema).

## Part F — Reflection

**Q1 (fact_fees): How much fee revenue did each advisor earn per year?**

This can be answered in a single visual with no DAX: a bar chart with dim_advisor[last_name] and dim_date[year], plus Sum of fact_fees[amount]. Fee amount is additive (a dollar charge), so summing it across clients, months and years always gives a correct total, and both advisor and date link directly to fact_fees.

**Q2 (fact_transactions): What was the net new money (deposits minus withdrawals) by client tier each year?**

This cannot be answered in a single visual without DAX. Every amount in fact_transactions is stored as a positive number, including withdrawals, and only txn_type shows the direction. Summing amount for deposits and withdrawals together gives $3,310.2M, but the true net (deposits of $1,818.8M minus withdrawals of $1,491.4M) is $327.4M. A visual cannot subtract one transaction type from another without a DAX measure. **Schema fix:** add a signed column to fact_transactions, such as net_flow_amount, with deposits stored as positive, withdrawals as negative and trades as 0. Then Sum of net_flow_amount by dim_client[client_tier] and dim_date[year] answers the question in one visual.

**Q3 (fact_portfolio_snapshot): What was total client AUM at the end of each year, by client tier?**

This can only be answered approximately in a single visual. AUM is semi-additive (a balance at a point in time), and each client has 12 monthly snapshots per year, so by default Power BI adds all 12 balances together. For 2024 this gives $135.5bn, while the December balance is $12.7bn. Adding a visual filter of dim_date[month] = 12 fixes the double counting without DAX, but it returns the 1 December balance, so it misses any changes during December. It also relies on whoever builds the visual remembering to add the filter. The dim_date[is_year_end] flag cannot help, because snapshots are dated on the 1st of each month and never fall on 31 December. **Schema fix:** store snapshots on month-end dates (e.g. 31 December, not 1 December), so the existing is_month_end and is_year_end flags can filter to the true closing balance.
