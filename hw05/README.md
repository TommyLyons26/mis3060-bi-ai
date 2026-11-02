# HW05 — Wildcat Capital Star Schema

MIS 3060 · Business Intelligence & AI

This assignment designs and builds a star schema in Power BI using the cleaned Wildcat Capital data from HW04. It covers the tables and keys, the grain of each fact table, which measures can be summed, the relationships built in Power BI, and the design decisions behind them.

## Folder structure

```
hw05/
├── README.md                    This file
├── star_design.md               Written answers for Parts A, B, C, E and F
├── powerbi/
│   ├── hw05.pbix                Power BI model (Part D)
│   └── model_view.png           Screenshot of the model diagram
└── Wildcat Capital Clean/       Cleaned source data (8 CSVs)
    ├── dim_advisor.csv
    ├── dim_benchmark.csv
    ├── dim_client.csv
    ├── dim_date.csv
    ├── dim_security.csv
    ├── fact_fees.csv
    ├── fact_portfolio_snapshot.csv
    └── fact_transactions.csv
```

## What's in star_design.md

| Part | Content |
|---|---|
| A — Keys | Each table's type (fact or dimension), primary key and foreign keys, with notes on the date join and blank `security_id` values |
| B — Grain | What one row represents in each fact table |
| C — Measures | Each numeric fact column classed as additive, semi-additive or non-additive, plus numeric columns that are not measures |
| E — Relationships and design questions | Blank security IDs, the active advisor relationship, the date join, and star vs snowflake |
| F — Reflection | Three manager questions, which can be answered in one visual, and the schema changes that would fix the others |

## The data

| Table | Type | Rows |
|---|---|---|
| dim_advisor | Dimension | 25 |
| dim_benchmark | Dimension | 8 |
| dim_client | Dimension | 2,500 |
| dim_date | Dimension | 1,827 |
| dim_security | Dimension | 500 |
| fact_fees | Fact | 122,197 |
| fact_portfolio_snapshot | Fact | 129,547 |
| fact_transactions | Fact | 298,572 |

## Power BI model (Part D)

- Built in Power BI Desktop on Apporto. The CSVs were loaded with Get Data → Text/CSV, and the column types were set in Power Query.
- The model has 13 relationships. All are many-to-one with single-direction filtering.
- The fact date columns join to `dim_date[date]`.
- `dim_client[advisor_id]` → `dim_advisor` is kept inactive to avoid a second filter path to advisors.
- The model was checked with row-count cards, a (Blank) security check and an advisor slicer.
