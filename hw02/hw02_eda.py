"""
Script:      hw02_eda.py
Dataset:     data/raw/fact_transactions.csv
Author:      Tommy Lyons
Generated:   2026-09-17

Performs a complete exploratory data analysis (EDA) of the financial
transactions dataset in a single run: loads the data, prints summary
statistics, checks data quality, generates charts, and writes a
plain-text profile summary.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import datetime

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
DATA_PATH = "data/raw/fact_transactions.csv"
CHARTS_DIR = "hw02/charts"
PROFILE_PATH = "hw02/hw02_profile.txt"
EXPECTED_SHAPE = (298772, 9)

os.makedirs(CHARTS_DIR, exist_ok=True)

# Collect everything that should also go into the plain-text profile
summary_lines = []


def log(text=""):
    """Print to console and also collect for the plain-text profile."""
    print(text)
    summary_lines.append(str(text))


# ---------------------------------------------------------------------------
# 1. Load the data
# ---------------------------------------------------------------------------
df = pd.read_csv(DATA_PATH)

# ---------------------------------------------------------------------------
# 2. Shape
# ---------------------------------------------------------------------------
log("=" * 70)
log("1. SHAPE")
log("=" * 70)
log(f"Rows: {df.shape[0]}, Columns: {df.shape[1]}")
log("")

# ---------------------------------------------------------------------------
# 3. Column names and data types
# ---------------------------------------------------------------------------
log("=" * 70)
log("2. COLUMN NAMES AND DATA TYPES")
log("=" * 70)
log(df.dtypes.to_string())
log("")

# ---------------------------------------------------------------------------
# 4. Missing values per column
# ---------------------------------------------------------------------------
log("=" * 70)
log("3. MISSING VALUES PER COLUMN")
log("=" * 70)
log(df.isnull().sum().to_string())
log("")

# ---------------------------------------------------------------------------
# 5. Descriptive statistics for numeric columns
# ---------------------------------------------------------------------------
log("=" * 70)
log("4. DESCRIPTIVE STATISTICS (NUMERIC COLUMNS)")
log("=" * 70)
log(df.describe().to_string())
log("")

# ---------------------------------------------------------------------------
# 6. Value counts and percentages for txn_type
# ---------------------------------------------------------------------------
log("=" * 70)
log("5. TXN_TYPE VALUE COUNTS AND PERCENTAGES")
log("=" * 70)
txn_type_counts = df["txn_type"].value_counts().sort_values(ascending=False)
txn_type_pct = (txn_type_counts / txn_type_counts.sum() * 100).round(2)
txn_type_summary = pd.DataFrame({
    "count": txn_type_counts,
    "percentage": txn_type_pct
})
log(txn_type_summary.to_string())
log("")

# ---------------------------------------------------------------------------
# 7. Unique counts: clients, advisors, securities
# ---------------------------------------------------------------------------
log("=" * 70)
log("6. UNIQUE COUNTS")
log("=" * 70)
n_clients = df["client_id"].nunique()
n_advisors = df["advisor_id"].nunique()
n_securities = df["security_id"].nunique()
log(f"Unique clients:    {n_clients}")
log(f"Unique advisors:   {n_advisors}")
log(f"Unique securities: {n_securities}")
log("")

# ---------------------------------------------------------------------------
# 8. Date range of txn_date
# ---------------------------------------------------------------------------
log("=" * 70)
log("7. DATE RANGE (txn_date)")
log("=" * 70)
earliest_date = df["txn_date"].min()
latest_date = df["txn_date"].max()
log(f"Earliest date: {earliest_date}")
log(f"Latest date:   {latest_date}")
log("")

# ---------------------------------------------------------------------------
# 9. Duplicate rows by txn_id
# ---------------------------------------------------------------------------
log("=" * 70)
log("8. DUPLICATE CHECK (txn_id)")
log("=" * 70)
n_duplicates = df["txn_id"].duplicated().sum()
log(f"Duplicate txn_id count: {n_duplicates}")
log("")

# ---------------------------------------------------------------------------
# 10. Mean, median, skewness of amount
# ---------------------------------------------------------------------------
log("=" * 70)
log("9. AMOUNT: MEAN, MEDIAN, SKEWNESS")
log("=" * 70)
amount_mean = df["amount"].mean()
amount_median = df["amount"].median()
amount_skew = df["amount"].skew()
log(f"Mean amount:     {amount_mean:.2f}")
log(f"Median amount:   {amount_median:.2f}")
log(f"Skewness amount: {amount_skew:.4f}")
log("")

# ---------------------------------------------------------------------------
# 11. Group by txn_type: count, mean, median amount (sorted by mean desc)
# ---------------------------------------------------------------------------
log("=" * 70)
log("10. AMOUNT BY TXN_TYPE (count, mean, median)")
log("=" * 70)
group_by_type = df.groupby("txn_type")["amount"].agg(
    count="count", mean="mean", median="median"
)
group_by_type["mean"] = group_by_type["mean"].round(2)
group_by_type["median"] = group_by_type["median"].round(2)
group_by_type = group_by_type.sort_values("mean", ascending=False)
log(group_by_type.to_string())
log("")

# ---------------------------------------------------------------------------
# 12. Correlation matrix for shares, price, amount
# ---------------------------------------------------------------------------
log("=" * 70)
log("11. CORRELATION MATRIX (shares, price, amount)")
log("=" * 70)
corr_matrix = df[["shares", "price", "amount"]].corr().round(2)
log(corr_matrix.to_string())
log("")

# Identify the three strongest correlations, excluding self-correlation
corr_pairs = (
    corr_matrix.where(~np.eye(len(corr_matrix), dtype=bool))
    .stack()
    .reset_index()
)
corr_pairs.columns = ["var_1", "var_2", "correlation"]
# Each pair appears twice (symmetric matrix); drop the mirrored duplicates
corr_pairs["pair_key"] = corr_pairs.apply(
    lambda row: tuple(sorted([row["var_1"], row["var_2"]])), axis=1
)
corr_pairs = corr_pairs.drop_duplicates(subset="pair_key").drop(columns="pair_key")
corr_pairs["abs_correlation"] = corr_pairs["correlation"].abs()
top_corr = corr_pairs.sort_values("abs_correlation", ascending=False).head(3)

log("Top 3 strongest correlations:")
for _, row in top_corr.iterrows():
    log(f"  {row['var_1']} vs {row['var_2']}: {row['correlation']}")
log("")

# ---------------------------------------------------------------------------
# 13. Shares min/max/negative count, broken out by txn_type
# ---------------------------------------------------------------------------
log("=" * 70)
log("12. SHARES (min, max, negative count) BY TXN_TYPE")
log("=" * 70)
shares_by_type = df.groupby("txn_type")["shares"].agg(
    min="min",
    max="max",
    negative_count=lambda s: (s < 0).sum()
)
log(shares_by_type.to_string())
log("")

# ---------------------------------------------------------------------------
# 14. Shape validation warning
# ---------------------------------------------------------------------------
log("=" * 70)
log("13. SHAPE VALIDATION")
log("=" * 70)
if df.shape != EXPECTED_SHAPE:
    log(f"WARNING: DataFrame shape {df.shape} does not match expected shape {EXPECTED_SHAPE}!")
else:
    log(f"Shape matches expected shape {EXPECTED_SHAPE}.")
log("")

# ---------------------------------------------------------------------------
# 15. Charts
# ---------------------------------------------------------------------------

# --- Histogram of amount with mean/median lines ---
fig, ax = plt.subplots(figsize=(10, 6))
ax.hist(df["amount"].dropna(), bins=50, color="#4C72B0", edgecolor="white")
ax.axvline(amount_mean, color="red", linestyle="--", linewidth=2,
           label=f"Mean: {amount_mean:.2f}")
ax.axvline(amount_median, color="green", linestyle="--", linewidth=2,
           label=f"Median: {amount_median:.2f}")
ax.set_title("Distribution of Transaction Amount")
ax.set_xlabel("Amount")
ax.set_ylabel("Frequency")
ax.legend()
fig.tight_layout()
fig.savefig(os.path.join(CHARTS_DIR, "hist_amount.png"), dpi=150)
plt.close(fig)

# --- Horizontal box plot of amount by txn_type ---
fig, ax = plt.subplots(figsize=(10, 6))
types_sorted = sorted(df["txn_type"].dropna().unique())
data_by_type = [df.loc[df["txn_type"] == t, "amount"].dropna() for t in types_sorted]
ax.boxplot(data_by_type, labels=types_sorted, vert=False)
ax.set_title("Amount Distribution by Transaction Type")
ax.set_xlabel("Amount")
ax.set_ylabel("Transaction Type")
fig.tight_layout()
fig.savefig(os.path.join(CHARTS_DIR, "box_amount_by_type.png"), dpi=150)
plt.close(fig)

# --- Scatter plot: shares vs amount, colored by txn_type ---
fig, ax = plt.subplots(figsize=(10, 6))
cmap = plt.get_cmap("tab10")
for i, t in enumerate(types_sorted):
    subset = df[df["txn_type"] == t]
    ax.scatter(subset["shares"], subset["amount"], s=10, alpha=0.5,
               color=cmap(i % 10), label=t)
ax.set_title("Shares vs. Amount by Transaction Type")
ax.set_xlabel("Shares")
ax.set_ylabel("Amount")
ax.legend(title="Transaction Type", bbox_to_anchor=(1.02, 1), loc="upper left")
fig.tight_layout()
fig.savefig(os.path.join(CHARTS_DIR, "scatter_shares_amount.png"), dpi=150)
plt.close(fig)

print(f"\nCharts saved to '{CHARTS_DIR}/'")

# ---------------------------------------------------------------------------
# 16. Save plain-text summary (items 2-13) to hw02_profile.txt
# ---------------------------------------------------------------------------
with open(PROFILE_PATH, "w") as f:
    f.write(f"EDA Profile Summary - Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"Dataset: {DATA_PATH}\n\n")
    f.write("\n".join(summary_lines))

print(f"Profile summary saved to '{PROFILE_PATH}'")
