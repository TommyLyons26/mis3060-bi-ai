# hw01/prompt_comparison.md
## My Analytical Question


## Strategy 1 — Zero-shot: Ask the question exactly as written, with no additional context.
  ### The prompt I sent
What are the most important metrics for measuring credit risk in a consumer loan portfolio?
  ### The first 150 words of Claude's response
The core metrics fall into a few natural groups, and I'll flag which ones your Wildcat loan file (2,341 loans, with credit_score, DTI, interest_rate, loan_status, loan_purpose, and income) can actually support.

Delinquency and default rates are the front line — the share of loans that are 30/60/90+ days past due, and the default rate itself. Your data already has this baked into loan_status: right now it's 62% Current, 23% Paid Off, 11% Delinquent, and 5% Default, so a straightforward first cut is default rate and delinquent rate overall and by segment (loan_purpose, state, credit score band). Related to this is the roll rate — how loans migrate from current to delinquent to default over time — but that needs a payment-history or snapshot-over-time view, which this single cross-sectional file doesn't give you unless origination_date lets you build vintage cohorts.

Loss metrics go a level deeper than "did it default" to "how much did.....
  ### My evaluation
Claude grounded the answer in the actual wildcat data and organised metrics into groups. However, the reponse was very broad and generic serving no real purpose.

## Strategy 2 — Role-assigned (role + audience): Assign Claude a role and specify an audience before asking the question.
  ### The prompt I sent
  You are a senior credit risk analyst presenting to a portfolio committee of three senior executives. Explain to them what the most important metrics for measuring credit risk in a consumer loan portfolio?

  ### The first 150 words of Claude's response
  Looking at your Wildcat loan data (credit score, DTI, loan amount, term, status, purpose, state, origination date), here's how I'd frame this for a portfolio committee — grouped by what each metric actually tells the room, since executives care less about the formula and more about "what decision does this drive."

  Portfolio quality at origination. This is your leading indicator — it tells the committee what risk you're taking on before any loans go bad. The two workhorses are weighted-average credit score (FICO) across the book and debt-to-income ratio distribution. A committee wants to see these trending over time by vintage (origination cohort), because a portfolio can look fine in aggregate while quietly drifting toward riskier borrowers quarter over quarter. Loan-to-value matters too for anything secured.

  Delinquency and default rates. This is the core lagging indicator of realized risk. You'd present 30/60/90+ day delinquency rates and the overall default rate .........

  ### My evaluation

  Assigning a role and audience effectively shaped the response. Claude organised metrics based on what the committee needs to hear. However, although the role changed the framing and emphasis, the actual contenet was still very similar to strategy one.

 ## Strategy 3 — Few-shot: Provide one example of the output format you want before asking the question.
  ### The prompt I sent
  I am going to send you a question. I need the answer in a format such as this: 1) The Metric 2) The reasoning 3) Give me an analogy to describe it. This is the question: "What are the most important metrics for measuring credit risk in a consumer loan portfolio?"

  ### The first 150 words of Claude's response
  Here are the core metrics used to gauge credit risk in a consumer loan portfolio, each broken into the three parts you asked for.
  Probability of Default (PD)
  1.	The Metric: The likelihood that a borrower will fail to make payments (typically defined as 90+ days past due) within a given time horizon, usually expressed as a percentage.
  2.	The Reasoning: PD is the foundation of credit risk modeling — everything else (pricing, reserves, capital requirements) is built on top of an estimate of how many borrowers will actually default. It's usually modeled using credit scores, income, past behavior, and macroeconomic variables.
  3.	Analogy: It's like a weather forecast's "70% chance of rain" — you can't say which specific day it'll rain, but you can say how often it will across many days (or in this case, many borrowers).
  Loss Given Default (LGD) and Exposure at Default (EAD)
  1.	The Metric: LGD .........

  ### My evaluation
  The few shot prompting format worked exactly as intended. Every metric followed: Metric, Reason, and Analogy, which made it very easy to understand. However the few shot prompting did not limit the scope, with the answer being the longest out of all three strategies.

  ## Conclusion 
  Each strategy improved the response along a different dimension rather than making it uniformly better. Zero shot gave a broad coverage, role assignment improved relevance to a specific audience, and few shot improved structural consistencty and readability. For a BI analyst, the role assigned strategy produced the most useful output. This strategy made claude think about its output in a way that would most align with what the audiences needs. You can see this in Claudes output as he tailored answer more to how the metric drives the decision and less on the formulaltion of the metric.