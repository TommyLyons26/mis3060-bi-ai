# EDA Script Specification

## Overview

Write a single Python script that performs a complete exploratory data analysis (EDA) of a financial transactions dataset. The script must run all of the steps described below together, in one execution, from start to finish. Do not split this into multiple scripts or separate runs, everything happens in one file, one pass, from loading the data at the start to saving the final outputs at the end.

## Dataset

The script should load the dataset located at `data/raw/fact_transactions.csv` into a pandas DataFrame. This is the only input file needed.

## What the script must do, in order

1. Load `data/raw/fact_transactions.csv` into a pandas DataFrame.

2. Print the shape of the DataFrame, showing the number of rows and the number of columns.

3. Print every column name along with its data type.

4. Print the number of missing values for every column in the dataset.

5. Print descriptive statistics for all numeric columns - count, mean, standard deviation, minimum, 25th percentile, median, 75th percentile, and maximum.

6. Print the value counts and percentages for the `txn_type` column, sorted from the most frequent type to the least frequent.

7. Print the number of unique clients, the number of unique advisors, and the number of unique securities referenced anywhere in the file.

8. Print the earliest and latest dates found in the `txn_date` column, so the overall date range of the dataset is clear.

9. Check whether there are any duplicate rows based on the `txn_id` column, and print how many duplicates were found.

10. Print the mean, median, and skewness of the `amount` column.

11. Group the data by `txn_type`, and for each type print the count of transactions along with the mean and median `amount`, each rounded to 2 decimal places. Sort these results from the highest mean amount to the lowest.

12. Compute the correlation matrix for the `shares`, `price`, and `amount` columns, rounded to 2 decimal places, print the full matrix, and then identify and print the three strongest correlations found (not counting a variable's correlation with itself).

13. For the `shares` column, broken out separately by each `txn_type`, print the minimum value, the maximum value, and the count of negative values.

14. Compare the DataFrame's shape against the expected shape of 298,772 rows and 9 columns, and print a clear warning message if the actual shape does not match this.

15. Create and save three charts, all placed in a folder called `hw02/charts/`:
    - A histogram of the `amount` column, with vertical lines marking the mean and the median, both clearly labeled. Save this as `hw02/charts/hist_amount.png`.
    - A horizontal box plot of `amount` broken out by `txn_type`. Save this as `hw02/charts/box_amount_by_type.png`.
    - A scatter plot with `shares` on the x-axis and `amount` on the y-axis, with points colored by `txn_type`. Save this as `hw02/charts/scatter_shares_amount.png`.

16. Save a plain-text summary covering the results of items 2 through 13 to `hw02/hw02_profile.txt`.

17. At the very top of the script, include a comment block that identifies: the name of the script, the dataset it analyzes, the author, and the date the script was generated.

## Important reminder

- This is one script, not seventeen separate scripts. All 17 items above must be part of the same file and must all execute together in a single run.

