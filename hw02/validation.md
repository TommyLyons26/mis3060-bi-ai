# 2A — Known-Answer Benchmarks (8 points)
| Check | Expected | Your Script Produced | Match? | Notes |
|---|---|---|---|---|
| Dataset shape | (298772, 9) | (298772, 9) | Yes | Match successful |
| Null count — `security_id` | 101,597 | 101,597 | Yes | Match successful |
| Null count — `amount` | 0 | 0 | Yes | Match successful |
| Unique `txn_type` values | 6 | 6 | Yes | Section 5 of output gave 6 values: Buy, Sell, Dividend, Deposit, Advisory Fee, Withdrawal |
| Count of `Buy` transactions | 83,556 | 83,556 | Yes | Match Successful |
| `txn_date` data type | object | datetime64(ns) | No | Please see Claude cowork section for explanation |
| Earliest `txn_date` | 2020-01-01 | 2020-01-01 | Yes | Match successful |
| Latest `txn_date` | 2024-12-30 | 2024-12-30 | Yes | Match successful |
| Duplicate `txn_id` count | 0 | 0 | Yes | Match successful |
| Mean `amount` | $54,075.17 | 54,075.17 | Yes | Match successful |
| Median `amount` | $41,220.48 | 41,220.49 | No | Please see Claude cowork section for explanation |
| Skewness of `amount` | 1.15 | 1.1463 | No | Please see Claude cowork section for explanation |
| Correlation `shares`–`amount` | 0.65 | 0.65 | Yes | Match successful |
| Correlation `price`–`amount` | 0.64 | 0.64 | Yes | Match successful |
| Correlation `shares`–`price` | 0.00 | 0.00 | Yes | Match successful |
| Negative `shares` count (Buy only) | 836 | 836 | Yes | Match successful |
| Profile file created | Yes | Yes | Yes | Match Successful |
| Chart files created (3) | Yes | 3 | Yes |Match successful |


## Claude Cowork Conversations

### Claude conversation for txt_type:

#### Prompt:
 One of the expected outputs here is txn date being an object, however the script output seems to be datetime64(ns). why is there a difference here

#### Output: 
That's expected, and it comes down to one line in the script.

In hw02_eda.py, the data is loaded with:

python
df = pd.read_csv(DATA_PATH, parse_dates=["txn_date"])

The parse_dates=["txn_date"] argument tells pandas to convert that column from text into an actual datetime type as it loads the file. That's why your script's output shows datetime64[ns] for txn_date — pandas already parsed it.

The homework's "Expected" answer of object implies a script that loads the CSV in its most basic form — pd.read_csv(DATA_PATH) with no parse_dates argument. In that case, pandas just reads every column as plain text unless told otherwise, so txn_date stays as object (a string), even though it looks like a date.

Neither version is "wrong" technically — parsing dates properly is generally better practice, since it's what lets .min() and .max() work correctly for the date range calculation later on. But since your rubric expects object, it sounds like the assignment wants you to see the raw, unparsed dtype at this step.

Want me to update the script to drop parse_dates at load time (and instead convert txn_date to datetime only where it's needed, like the date range and duplicate checks), so the dtype check matches what's expected?

follow up prompt: but is parsing eeven needed here and why

Output: It depends on what you're using it for, but for this specific script — not strictly required, and here's why.

Parsing (parse_dates=["txn_date"]) converts the column from plain text into a real datetime type, which matters when you need to do date arithmetic — things like calculating the number of days between two dates, extracting the year or month, or resampling by week/quarter. Without parsing, pandas just treats the values as strings, and string comparison doesn't understand calendar logic (e.g., it wouldn't correctly compare "2024-1-5" vs "2024-10-1" if the format weren't zero-padded).

That said, for the specific things this script does with txn_date — finding the min and max (item 8, the date range) — it actually works correctly either way, because your dates are in ISO format (YYYY-MM-DD), and that format happens to sort correctly as plain strings too. Alphabetical/lexicographic order and chronological order line up for zero-padded ISO dates. So .min() and .max() would return the right answers whether txn_date is object or datetime64[ns].

So in this case, parsing isn't needed for correctness — it was really just a "best practice" habit on my part. Since your homework's expected dtype is object, it sounds like the assignment intentionally wants you to skip that conversion and work with the raw string column as-is.

Want me to remove parse_dates=["txn_date"] from the script so it matches the expected object dtype?

#### Conclusion:
Script was refined and updated to match intended value

### Claude conversation for Median Amount:

#### Prompt:
For median amount the expecteed value is $41,220.48 but im getting 41,220.49 from my script. Why is there a difference in values here.

#### Output: 
I checked the actual numbers on your machine to be sure, and the answer is a floating-point rounding edge case, not a bug in the script.

The true median value is exactly 41220.485 — right on the halfway point between two cents. Here's the problem: the number 0.485 can't be represented exactly in binary floating point (the format all computers use for decimals). The closest representable value is a tiny fraction above or below the "true" 0.485, so when Python rounds it to 2 decimal places, it rounds up to .49 because the stored value is microscopically greater than .485.

Whatever tool produced the "expected" answer of $41,220.48 likely computed or rounded that median using a different method — Excel, a calculator, or decimal-based arithmetic — which resolved that exact tie differently and rounded down instead.

So this isn't really "wrong" on either side — it's a well-known quirk of floating-point rounding right at a midpoint like .485. The underlying median is the same value; it's just a one-cent difference in how the halfway point got rounded.

If you want, I can note this in your validation.md as an explanation for that row rather than leaving it as an unresolved mismatch — just say the word.

#### Conclusion: 
The true median is 41,220.485, a tie between two cents. The script rounded up to 49 cents. The expected value of 41,220.48 seemed to have rounded down instead. It comes down to floating-point representation, not a mistake anywhere in the logic.

### Claude conversation for Skewness amount: 

#### Prompt:
 In my script im getting : Skewness amount: 1.1463. But for the expected output in my homework it is expecting 1.15. Why is there a difference

#### Output: 
That's not actually a discrepancy — it's the same number at different precision. Your script prints 1.1463 (4 decimal places), and if you round that to 2 decimal places, you get 1.15 (since the third decimal digit is 6, which rounds the .14 up to .15).

So the expected output in your homework just rounded to 2 decimal places, while the script's .4f formatting shows more precision. Both represent the same underlying skewness value — nothing to troubleshoot here, it's just a display/rounding difference.

#### Conclusion: 
The expected value and my scripts value are the same but the expected value rounded to 2 decimal places while my script shows more precision.

# 2B — Explain the Code and Output (16 points)


## 1. Did Claude's predicted outputs (from Prompt 1) match what you actually saw in the terminal? List any discrepancies.

Most of claudes expected output was the same as the actual scripts output, but there was a few discrepancies:
Claude guessed security_id to be a object or int64, but it was float64. This is because claude did no take into account missing values, which are present. 
Claude guessed that sell shares would be negative and that buy shares would not be negative. In the script output the shares are all positive and there are negatives in buy shares.

## 2. What did Claude flag as potentially unexpected or worth investigating (from Prompt 2)?

Claude flagged the following as unexpected or worth investigating: 

The 836 Buy rows with negative shares. Claude says buying minus shares does not make much sense. Claude says this could be a reversal, a correction or it just could be an error. This breaks the pattern of the other data, as Sell and Dividend are never negative.

Claude mentions some Client ID gaps. Claude states the highest ID is 3,192 but there are 2,700 distinct clients, meaning 492 numbers never appear. 

Claude also comemnted on the missing values, which I will discuss further in question 3.


## 3. Did Claude mention the 101,597 null values in `security_id`? What explanation did it give?

Yes, Claude mentioned the 101,597 null values in security_id, shares and prices. Claude says these blanks are to be expected and are not errors. Those three column types describe either buying or selling a security, and three out of the six transaction types (Deposit, Withdrawal, Advisory Fee) have no security involved. Claude states these blanks mean "not applicable".

## 4. Did Claude flag the `txn_date` column as a concern? Why would that matter for a time-series analysis?

Claude mentions that txn_date is object, meaning it is stored as a text, not as a real date. Claude then says the Date Range worked because the format is ISO. Claude also states if later I want to group by month or year, I would need to convert it to datetime. 

## 5. Open your three chart files. Does what you see in each image match Claude's explanation of that section of the output? Note any differences.

For the hist_amount.png, Claude says I should see a right skewed histogram, being tallets at the far left, tapering off to the right. Claude also states there should be a green and red dashed line, with the green (median) at about 41,220 and the red (mean) at about 54,074, to the right of the green line. 
This correctly matches my output here. 

For the box_amount_by_type.png, Claude says that categories are sorted alphabetically, from bottom to top. 
Claude states Advisory Fee will be a very thin box squashed against zero, with a long trail of outlier dots stretching to the right.
Buy, Dividend, Sell will have three similar boxes with medians around 48,000 and whiskers reaching far right.
Deposit, Withdrawal will have boxes centered near 50,000, with the median line in the middle of the box.
This correctly matches my output here.

For the scatter_shares_amount.png, Claude says the legend will list 6 types, but only orange (buy), red (dividend) and purple (sell) will have visible points. There will be a wedge shape. There will be heavy overplotting with purple covering the orange and red. Negative buys will appear as orange points on the left of the zero. 
This mostly matches my output here, with a small caveat being the red points are barely visible in the scatter plot.


## 6. Paste one follow-up question you asked Claude, and Claude's answer.

### Follow up Question:

There is a negative count value of 836, regarding Buys. Is this worth investigating further or is it normal to have a negative value this high?

### Claude's Reponse:

Yes, it's worth investigating, though it's a small share of the data.

How big it is: 836 out of 83,556 Buys is about 1.0%. That won't distort overall averages much, but in real transaction data a Buy with negative shares should be near zero, not 1%. Sell and Dividend have none at all, so these rows stand out against the rest of the data.

One thing that stands out: 836 is almost exactly 1% of the Buy rows (83,556 × 0.01 ≈ 836). A round percentage like that often means the anomaly was planted deliberately in a synthetic or coursework dataset, as a data quality issue for you to find. That's my inference, not something the output proves, but it's a good reason to flag it in your write-up.

Quick checks to decide what they are:

Is amount positive on those rows? If so, shares and amount contradict each other.
Does abs(shares) * price roughly equal amount? If so, only the sign is wrong.
Do they cluster on certain dates, clients, or advisors? Clustering suggests a systematic cause, while an even spread suggests random corruption.

Handling them:

Keep them if they turn out to be legitimate reversals.
Fix the sign if abs(shares) * price matches amount.
Exclude or flag them if the fields disagree and you can't explain why.

# 2C — Business Check & Cross-Validation (16 points)


### 1. `security_id`, `shares`, and `price` are all null in exactly 101,597 rows. Looking at the `txn_type` value counts, which three transaction types would you expect to have no security — and why? Do the counts add up to 101,597?

Based on the transaction types, deposits, advisory fees and withdrawals are all just cash movements and therefore have no security. The counts all up to 101,597 because every blank row belongs to one of deoposits, advisory fees or withdrawals, meaning the total missing count is the addition of these three transaction types: 35,981 + 35,766 + 29,850 = 101,597

### 2. There are 83,556 Buy transactions and 59,755 Sell transactions. What does it mean for a wealth management firm to have significantly more Buys than Sells over a five-year period?

Having more buys than sells means that there is an increase in organic growth, whereby clients are investing more in their portfolios than withdrawing from it. 

However, it might not always indicate organic growth.

If a client uses dollar cost averaging whereby they invest the same amount, at reqular intervals, regardless of market conditions, this would mean they would have more Buy transactions than Sell transactions. (https://www.finra.org/investors/insights/dollar-cost-averaging)

Also, counting transaction activity doesn't tell you exactly whether the firm has actually grown. McKinsey found that in 2022, despite ongoing buying and selling activity, US wealth management client assets fell by $6.2 trillion, whereby market losses wiped out $7.6 trillion, and net inflows only offset $1.4 trillion of that (just 2.8% organic growth). So even with more Buys than Sells, a firm's assets can still shrink if market performance is strongly negative. (https://www.mckinsey.com/industries/financial-services/our-insights/us-wealth-management-amid-market-turbulence-an-industry-converges) 

### 3. The `txn_date` column is stored as a string (type `object`) rather than a date. If Claude Cowork generated code to compute the average number of days between transactions, what would go wrong if the dates remained as strings?

If the dates remained as strings, it would raise an error as python cannot compute the average number of days between transactions because the dates are strings. The dates would have to be in datetime format, in order for this calculation to work.

### 4. Wildcat Capital has 2,700 clients served by 25 advisors. Is that ratio — roughly 108 clients per advisor — plausible for a registered investment advisory firm?

Yes this is plausible. According to reports from smartasset(https://smartasset.com/advisor-resources/how-many-clients-does-a-financial-advisor-have) the typical range is from 65-277 clients. So based on this evidence this range is plausible. 

### 5. 836 `Buy` transactions have negative `shares` values (as low as −499.63), while every other transaction type in the dataset has only positive share values. What are two plausible business explanations for a negative share count on a Buy transaction (for example, a data-entry sign error versus a legitimate correction or reversal entry), and what would you do next to determine which explanation is more likely?

Two plausible business explanations here would be a data-entry sign error and a trade reversal. In order to determine which one is more plausible I would check the timiming around the negative buys. If negative buys with the same amount are evident shortly after other buys for the same client_id/security_id then this could be evidence of a reversal entry. Also the txn_id for negatives could be the same as other positive buys indicating reversal entrys. If this was not the case than the data-entry sign error explanation would make more sense.


## **Cross-validation.** 

#### 6. What did each script return?
Prompt A returned 83,566 buy rows. Prompt B returned 298,772 total rows, 215,216 excluded rows (sell, deposit, withdrawal, dividend, advisory fee) and 83,566 remaining buy rows. 

#### 7. Do the results agree?

These results both align and therefore agree with each other. 

#### 8. Why is it useful to verify a count using subtraction rather than direct filtering?

It is useful to use substraction as it is a genuine independent check. It does not rely on the same 'Buy' string match that prompt A uses. Also prompt B assumes that the six values (Buy, Sell, Deposit, Withdrawal, Dividend and Advisory Fee) are every possible value in the txn_type column and nothing else exists. Since prompt B's value matched prompt A's we know that this assumption held and there is only six categories in the data, and substracting the five values except for Buy from the total, leaves us with an accurate Buy count. 



