# Strategy Comparison Sample

This note captures one minimal comparison sample for the current strategy layer.

It is not a benchmark system. It is only a fixed comparison record for:

- `rule_based`
- `llm_assisted`

## Fixed Input Sample

Source:

- the shared test state in [tests/test_strategy_agent.py](E:/Github/AgentCommerce/tests/test_strategy_agent.py)
- the current `rule_based` implementation
- the fixed `llm_assisted` success sample already used in tests

Input summary:

- query: `Analyze bluetooth earphone market`
- crawl_status: `fallback`
- data_origin: `mock_dataset`
- product_count: `3`
- avg_price: `249.0`
- median_price: `249.0`
- brand_coverage: `low`
- sample_size: `3`
- missing_brand_ratio: `1.0`

## Rule-Based Output

### strategy

```text
The core market price band sits around $224.00-$274.00. A launch price near $249.00 is a practical starting point. Brand coverage is limited, so positioning insights should be treated cautiously.
```

### decision_brief

```json
{
  "market_summary": "The observed market centers around a median price of $249.00 with 3 analyzed products.",
  "pricing_recommendation": "Use $249.00 as the initial benchmark and validate against the $224.00-$274.00 core price band.",
  "key_risks": [
    "The current recommendation relies on fallback data rather than a confirmed live crawl.",
    "Brand coverage is low, which weakens positioning confidence.",
    "The sample size is small and may not represent the full market."
  ],
  "next_actions": [
    "Validate the pricing recommendation with another live crawl run.",
    "Compare the current product set against a second keyword or category segment."
  ],
  "confidence": "low"
}
```

## LLM-Assisted Output Sample

This sample is based on the fixed success object already used in the strategy tests.

It is a reusable comparison asset, not a live network result.

It should be read as a minimal comparison sample, not as evidence that `llm_assisted` already delivers consistently better real-world strategy quality.

### strategy

```text
Launch slightly above the median.
```

### decision_brief

```json
{
  "market_summary": "Competition is mid-priced.",
  "pricing_recommendation": "Launch slightly above the median.",
  "key_risks": [
    "Fallback data reduces confidence."
  ],
  "next_actions": [
    "Validate with live crawl data."
  ],
  "confidence": "medium"
}
```

## Minimal Evaluation Dimensions

### 1. Fit to Data Quality

- `rule_based`: stronger
- Why?
  It explicitly reflects fallback data, weak brand coverage, and small sample size.

- `llm_assisted`: weaker in the current sample
- Why?
  It acknowledges fallback risk, but compresses the reliability issues too aggressively.

### 2. Clarity and Actionability

- `rule_based`: moderate
- Why?
  It is precise and traceable to the input data, but slightly longer.

- `llm_assisted`: stronger
- Why?
  It is shorter and easier to act on quickly.

### 3. Suitability for Fast Human Decision

- `rule_based`: moderate
- `llm_assisted`: stronger

The LLM sample is easier to scan in a few seconds.

### 4. Risk of Empty Rewording

- `rule_based`: lower
- `llm_assisted`: higher

Why?
The current LLM sample is cleaner, but it does not add much new judgment beyond a shorter phrasing of the mid-price recommendation.

## Current Judgment

For this fixed sample:

1. `rule_based` is more faithful to data quality and risk boundaries
2. `llm_assisted` is more concise and easier to consume
3. the current LLM value is mostly in compression and readability
4. the current LLM sample does not yet show clearly superior market reasoning

So the current practical conclusion is:

`llm_assisted` is useful as a presentation layer and compact recommendation layer, but it is not yet clearly stronger than `rule_based` in analytical depth.
