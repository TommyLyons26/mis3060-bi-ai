Pasted text.txt
TXT

Here is my model metadata attached. The grain of fact_portfolio_snapshot is the following: One row per client per month: each row is that client’s portfolio balance and performance as of that month’s snapshot date. Aum is a balance and active_alpha_ytd is year to date. I need you to give me a measure for the Top 10 Client Share. The business definition is as follows: Share of Ending AUM held by the 10 largest clients within the current filter. I need a measure, an explanation of its filter context, and a DAX test query. Ensure you dont use memory for this.

 [ID]    [Name]    [Relationship]    [Model]    [IsActive]    [CrossFilteringBehavior]    [RelyOnReferentialIntegrity]    [FromTable]    [FromColumn]    [FromCardinality]    [ToTable]    [ToColumn]    [ToCardinality]    [State]    [SecurityFilteringBehavior]
2450    AutoDetected_47d2c78f-3915-4351-b30d-fc5f654a65f4    'fact_transactions'[advisor_id] *[<-]1 'dim_advisor'[advisor_id]    a739e509-7b5a-4006-9e2f-cb2abe0c65f5    true    OneDirection    false    fact_transactions    advisor_id    Many    dim_advisor    advisor_id    One    Ready    Single
3424    AutoDetected_080dc0c9-a847-4102-8fe6-5527ad4e80b2    'fact_transactions'[client_id] *[<-]1 'dim_client'[client_id]    a739e509-7b5a-4006-9e2f-cb2abe0c65f5    true    OneDirection    false    fact_transactions    client_id    Many    dim_client    client_id    One    Ready    Single
4453    AutoDetected_2f815d05-ddf4-42b9-bf11-303f56a168d6    'fact_transactions'[security_id] *[<-]1 'dim_security'[security_id]    a739e509-7b5a-4006-9e2f-cb2abe0c65f5    true    OneDirection    false    fact_transactions    security_id    Many    dim_security    security_id    One    Ready    Single
4712    6deec966-5197-f019-8717-87cd3326e62d    'fact_transactions'[txn_date] *[<-]1 'dim_date'[date]    a739e509-7b5a-4006-9e2f-cb2abe0c65f5    true    OneDirection    false    fact_transactions    txn_date    Many    dim_date    date    One    Ready    Single
2451    AutoDetected_515f758c-a4c4-4e3e-8414-fe1239270ac5    'fact_portfolio_snapshot'[advisor_id] *[<-]1 'dim_advisor'[advisor_id]    a739e509-7b5a-4006-9e2f-cb2abe0c65f5    true    OneDirection    false    fact_portfolio_snapshot    advisor_id    Many    dim_advisor    advisor_id    One    Ready    Single
2639    AutoDetected_27290db9-48a2-4230-a18e-ac5fca16ab64    'fact_portfolio_snapshot'[benchmark_id] *[<-]1 'dim_benchmark'[benchmark_id]    a739e509-7b5a-4006-9e2f-cb2abe0c65f5    true    OneDirection    false    fact_portfolio_snapshot    benchmark_id    Many    dim_benchmark    benchmark_id    One    Ready    Single
3425    AutoDetected_8da07bbb-379a-44b4-8620-2cb9df480b79    'fact_portfolio_snapshot'[client_id] *[<-]1 'dim_client'[client_id]    a739e509-7b5a-4006-9e2f-cb2abe0c65f5    true    OneDirection    false    fact_portfolio_snapshot    client_id    Many    dim_client    client_id    One    Ready    Single
4695    aa81e5e4-13d7-2473-c80b-1050d4fb268e    'fact_portfolio_snapshot'[snapshot_date] *[<-]1 'dim_date'[date]    a739e509-7b5a-4006-9e2f-cb2abe0c65f5    true    OneDirection    false    fact_portfolio_snapshot    snapshot_date    Many    dim_date    date    One    Ready    Single
2452    AutoDetected_13cb45f8-9f1d-42c6-9326-a4402ef86ceb    'fact_fees'[advisor_id] *[<-]1 'dim_advisor'[advisor_id]    a739e509-7b5a-4006-9e2f-cb2abe0c65f5    true    OneDirection    false    fact_fees    advisor_id    Many    dim_advisor    advisor_id    One    Ready    Single
3426    AutoDetected_6b7ee019-ebcc-4ab0-a5f6-23016186f549    'fact_fees'[client_id] *[<-]1 'dim_client'[client_id]    a739e509-7b5a-4006-9e2f-cb2abe0c65f5    true    OneDirection    false    fact_fees    client_id    Many    dim_client    client_id    One    Ready    Single
4678    fbd94a81-c893-0c31-c79a-9a0f84f664a0    'fact_fees'[fee_date] *[<-]1 'dim_date'[date]    a739e509-7b5a-4006-9e2f-cb2abe0c65f5    true    OneDirection    false    fact_fees    fee_date    Many    dim_date    date    One    Ready    Single
2662    371030ed-f05a-47f6-a233-06998810b983    'dim_client'[client_since] *[<-]1 'LocalDateTable_976ce71a-eea0-49bb-b089-dd421adaa4b8'[Date]    a739e509-7b5a-4006-9e2f-cb2abe0c65f5    true    OneDirection    false    dim_client    client_since    Many    LocalDateTable_976ce71a-eea0-49bb-b089-dd421adaa4b8    date    One    Ready    Single
3498    4ef23535-e977-479b-98bc-f80d9c25c9a5    'dim_date'[date] *[<-]1 'LocalDateTable_30b0d5f8-768e-4d2a-9562-888fa2f9b2e7'[Date]    a739e509-7b5a-4006-9e2f-cb2abe0c65f5    true    OneDirection    false    dim_date    date    Many    LocalDateTable_30b0d5f8-768e-4d2a-9562-888fa2f9b2e7    date    One    Ready    Single
4454    AutoDetected_031cb484-3962-4004-9c23-08d705a8563e    'dim_security'[benchmark_id] *[<-]1 'dim_benchmark'[benchmark_id]    a739e509-7b5a-4006-9e2f-cb2abe0c65f5    true    OneDirection    false    dim_security    benchmark_id    Many    dim_benchmark    benchmark_id    One    Ready    Single

I worked only from the metadata and relationships you attached. I haven’t run this against your model, so the test query below is how to confirm the numbers.

Measure
dax
Top 10 Client Share =
VAR LastSnapshotDate =
    MAX ( fact_portfolio_snapshot[snapshot_date] )
VAR ClientEndingAUM =
    CALCULATETABLE (
        ADDCOLUMNS (
            VALUES ( fact_portfolio_snapshot[client_id] ),
            "@EndingAUM", CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ) )
        ),
        fact_portfolio_snapshot[snapshot_date] = LastSnapshotDate
    )
VAR Top10Clients =
    TOPN (
        10,
        ClientEndingAUM,
        [@EndingAUM], DESC,
        fact_portfolio_snapshot[client_id], ASC    -- tie-breaker: exactly 10 rows
    )
VAR Top10AUM = SUMX ( Top10Clients, [@EndingAUM] )
VAR TotalAUM = SUMX ( ClientEndingAUM, [@EndingAUM] )
RETURN
    DIVIDE ( Top10AUM, TotalAUM )

Format it as a percentage.

How the filter context works
AUM is a balance, so it can’t be summed across months. LastSnapshotDate takes the latest snapshot_date that still has rows after every filter is applied (dates, advisor, benchmark, client attributes). Both the top 10 and the total use only that one snapshot. Without this, a full year would add up 12 monthly balances.
There is one “as-of” date for everyone, not one per client. The date is set once, before looping over clients. A client who left mid-period has no row on the last date, so their ending AUM is zero, not their last known balance. That’s the right reading of “ending AUM held”.
Clients come from the fact table, not dim_client. Your relationships are all single-direction, dimension to fact, and dim_advisor doesn’t link to dim_client. So VALUES(dim_client[client_id]) would ignore an advisor or benchmark slicer. VALUES(fact_portfolio_snapshot[client_id]) respects every filter on the fact table. That makes “the top 10 within the current filter” mean the top 10 among clients who actually appear in the filtered snapshot.
Context transition. Inside ADDCOLUMNS, CALCULATE(SUM(aum)) turns each client_id into a filter. Together with the date filter from CALCULATETABLE, that gives one client’s balance on the last snapshot date.
Ties. TOPN returns more than N rows when values tie. The client_id tie-breaker makes it return exactly 10.

How it behaves in visuals:

Visual	Result
Card, no slicers	Share of firm AUM held by the 10 largest clients on the latest snapshot
Rows = advisor	Top 10 within each advisor’s book. Advisors with 10 or fewer clients show 100%
Axis = Year/Month (dim_date)	Concentration at each period’s last snapshot, so you get a trend
Rows = client	Always 100%, because the context holds one client. Don’t use it at client grain
Date filter with no snapshot rows (e.g. mid-month only)	Blank

fact_portfolio_snapshot[Year] and [Month] sit on the fact table. If someone slices on those instead of dim_date, the result is the same, because they filter the same rows.

Test query (DAX Studio)
dax
DEFINE
    VAR __LastDate =
        MAX ( fact_portfolio_snapshot[snapshot_date] )
    VAR __ClientAUM =
        CALCULATETABLE (
            ADDCOLUMNS (
                VALUES ( fact_portfolio_snapshot[client_id] ),
                "Ending AUM", CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ) )
            ),
            fact_portfolio_snapshot[snapshot_date] = __LastDate
        )
    -- Independent check: rank with RANKX instead of TOPN
    VAR __Ranked =
        ADDCOLUMNS (
            __ClientAUM,
            "Rank", RANKX ( __ClientAUM, [Ending AUM], , DESC, SKIP )
        )

-- 1) Measure vs. an independent calculation at grand total
EVALUATE
ROW (
    "Last Snapshot", __LastDate,
    "Clients at Last Snapshot", COUNTROWS ( __ClientAUM ),
    "Total Ending AUM", SUMX ( __ClientAUM, [Ending AUM] ),
    "Top 10 AUM (RANKX)", SUMX ( FILTER ( __Ranked, [Rank] <= 10 ), [Ending AUM] ),
    "Share (RANKX check)",
        DIVIDE (
            SUMX ( FILTER ( __Ranked, [Rank] <= 10 ), [Ending AUM] ),
            SUMX ( __ClientAUM, [Ending AUM] )
        ),
    "Share (Measure)", [Top 10 Client Share]
)

-- 2) The top 10 clients, so you can eyeball them
EVALUATE
ADDCOLUMNS (
    FILTER ( __Ranked, [Rank] <= 10 ),
    "Client",
        LOOKUPVALUE ( dim_client[last_name], dim_client[client_id], fact_portfolio_snapshot[client_id] )
)
ORDER BY [Rank] ASC

-- 3) Filter-context behavior by advisor (small books should show 100%)
EVALUATE
SUMMARIZECOLUMNS (
    dim_advisor[advisor_id],
    dim_advisor[last_name],
    "Top 10 Client Share", [Top 10 Client Share]
)
ORDER BY dim_advisor[advisor_id]

-- 4) Trend by month (one as-of balance per month, not summed)
EVALUATE
SUMMARIZECOLUMNS (
    dim_date[Year],
    dim_date[Month],
    "Last Snapshot In Period", MAX ( fact_portfolio_snapshot[snapshot_date] ),
    "Top 10 Client Share", [Top 10 Client Share]
)
ORDER BY dim_date[Year], dim_date[Month]

What passing looks like:

In query 1, Share (RANKX check) equals Share (Measure). The only exception is a tie at 10th place, where RANKX can include an 11th client.
In query 2, the AUM of the 10 clients adds up to Top 10 AUM.
In query 3, advisors with 10 or fewer clients show 100%.
In query 4, each month shows that month’s last snapshot date, and every value is between 0 and 1.

Before running, add the measure to the model, or paste it into the DEFINE block as MEASURE fact_portfolio_snapshot[Top 10 Client Share] = ….