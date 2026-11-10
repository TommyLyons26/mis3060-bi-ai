# Verification: Claude's Top 10 Client Share measure

**Did it run as written?**

Yes. The measure in `claude/dax_session.md` (lines 36–57) was added to the Power BI model as `TOP 10 CLIENT SHARE 2`, exactly as written, and ran without errors. Its test query also ran as written in DAX query view.

**What did the test query return?**

| Test | What it checks | Result |
|---|---|---|
| 1. Grand total check | With no filters, the measure is compared with an independent calculation that ranks clients with RANKX instead of TOPN. If the two agree, the measure picks the right 10 clients and divides by the right total. | 2,325 clients at the 2024-12-01 snapshot. RANKX check = 0.061589267465792824, Measure = 0.06158926746579283. They match. |
| 2. Top 10 client list | Lists the 10 clients the measure treats as the largest, so you can see who they are and that their AUM adds up to the Top 10 AUM in test 1. | Clients 1001 (Sanchez, $82.4M) to 796 (Ward, $74.4M), totalling $784,005,019.49, the same as test 1. |
| 3. By advisor | Puts each advisor in the filter context. The measure should rank only that advisor's own clients and divide by that advisor's own Ending AUM. This tests that "within the current filter" works on a filter from `dim_advisor`. | 25 advisors, each between 0.5989 (advisor 9) and 0.8108 (advisor 5). Each shows its own concentration rather than repeating the firm total. |
| 4. By month | Puts each month in the filter context. The measure should use only that month's snapshot and not add up balances across months. This tests that `aum` is treated as a balance. | 60 months from January 2020 to December 2024. Each uses that month's snapshot date (the 1st), with values between 0.0553 and 0.0809. December 2024 = 0.061589, the same as test 1. |

All four results were recalculated in pandas from the Wildcat CSVs and matched.

**Which rows of `measure_reconciliation.csv` prove it?**

| Row | Slice | Pandas value | Claude's measure | Match |
|---|---|---|---|---|
| 88 | Total | 0.06158926746579307 | 0.06158926746579283 | ✓ |
| 85 | Tier=HNW, 2024 | 0.03139674749179621 | 0.03139674749179624 | ✓ |
| 86 | Tier=Retail, 2024 | 0.018348218311311205 | 0.018348218311311223 | ✓ |
| 87 | Tier=UHNW, 2024 | 0.08126426752227994 | 0.08126426752227998 | ✓ |

All four are within the 0.0001 tolerance.

**Edge cases checked**

**1. Grand total.** With no filters, the measure must read only the latest snapshot (December 2024) and not add up 60 months of balances. This is checked by test 1 of Claude's test query.

Result: **0.06158926746579283**, which matches row 88 (pandas 0.06158926746579307).

**2. `dim_date[Year] = 2022`.** For a past year, the measure must use the last snapshot in that year (December 2022), not the latest snapshot in the data and not a sum of 12 months.

```dax
EVALUATE
CALCULATETABLE (
    ROW ( "Top 10 Client Share 2022", [TOP 10 CLIENT SHARE 2] ),
    dim_date[Year] = 2022
)
```

Result:

| Top 10 Client Share 2022 |
|---|
| 0.05530865047453662 |

This matches pandas (0.055309) and the December 2022 value in test 4.

**3. 2024 tier table.** The measure must rank clients only within each tier and divide by that tier's own Ending AUM.

```dax
EVALUATE
CALCULATETABLE (
    SUMMARIZECOLUMNS ( dim_client[client_tier], "Top 10 Client Share", [TOP 10 CLIENT SHARE 2] ),
    dim_date[Year] = 2024
)
```

Result:

| client_tier | Top 10 Client Share |
|---|---|
| HNW | 0.03139674749179624 |
| Retail | 0.018348218311311223 |
| UHNW | 0.08126426752227998 |

These match rows 85, 86 and 87 of `measure_reconciliation.csv`.

**What I changed and why**:

Nothing. The measure was added and used exactly as Claude wrote it, and every test passed against pandas, so no changes were needed.

**A claim confirmed in Power BI and pandas**:

Claude claimed that its measure sets one as-of date for everyone before ranking, so a client who left mid-period counts as zero rather than as their last known balance. Comparing it with my original measure by advisor confirmed this and showed that my original gets it wrong. The two agree for 17 advisors, but my original is lower for 8 (advisors 1, 5, 10, 14, 17, 18, 21 and 23). For advisor 1, my original's top 10 included client 1052 (`is_active = false`), ranked on a September 2023 balance of $32,590,287.84. That client then added $0 at December 2024, which pushed out the real 10th client (client 1704, $5,526,001.20), so only 9 real clients were counted (0.7474 instead of 0.7656). Pandas reproduced all 8 wrong values exactly. The reconciliation did not catch this because it only checks the grand total and the 2024 tiers. At the grand total, no departed client was big enough to make the top 10. In the 2024 tiers, departed clients have no 2024 data, so they could not be ranked at all.

Based on this finding, my original Top 10 Client Share measure should be changed to Claude's Top 10 Client Share measure, as it takes into account clients who have left the firm: it only ranks clients who still hold money on the last snapshot date, so a departed client can never take a place in the top 10.
