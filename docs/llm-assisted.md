# LLM Assisted Quick Start

This note is only for validating the current `llm_assisted` path.

## Before You Start

- Default mode is `rule_based`
- Default mode does not require any API key
- Only `llm_assisted` requires environment variables

## Minimal Environment Setup

1. Copy the example file:

```powershell
Copy-Item .env.example .env
```

2. Fill in the minimum required value in `.env`:

```env
OPENAI_API_KEY=your_real_key
```

Optional:

```env
OPENAI_MODEL=gpt-4o-mini
```

If you do not enable `llm_assisted`, you can leave `.env` unused.

## Enable `llm_assisted`

The workflow still defaults to `rule_based`.

For a real validation run, temporarily change the initial state in [ecomscout_ai/main.py](E:/Github/AgentCommerce/ecomscout_ai/main.py):

```python
"strategy_mode": STRATEGY_MODE_LLM_ASSISTED,
```

Keep the rest of the workflow unchanged.

This temporary `main.py` change is only the smallest validation path for the current phase. It is not the intended long-term configuration mechanism.

## Run The Workflow

```powershell
py main.py
```

## How To Tell Whether LLM Was Actually Used

Check the `## Strategy Suggestion` section in the final report.

If the run really used the LLM path, you should see:

```text
strategy_execution_mode: llm_assisted
llm_parse_status: parsed
llm_fallback_reason: None
```

## How To Recognize Fallback

If the LLM path fails and the system falls back to deterministic strategy generation, the same report section will show:

```text
strategy_execution_mode: rule_based_fallback
llm_parse_status: fallback
llm_fallback_reason: ...
```

Typical fallback reasons:

- `llm_runtime_error`
  LLM call failed, API key missing, or runtime invocation failed

- `llm_output_parse_failed`
  Model output could not be parsed into a JSON object

- `schema_validation_failed`
  Model returned JSON-like content, but required fields or types were invalid

## Minimal Validation Path

1. Confirm default mode still works without any API key:

```powershell
py main.py
```

Expected signal:

- `strategy_execution_mode: rule_based`
- `llm_parse_status: not_attempted`

2. Add `.env` with a real API key
3. Switch `strategy_mode` to `STRATEGY_MODE_LLM_ASSISTED`
4. Run again:

```powershell
py main.py
```

5. Read the report fields:

- `strategy_execution_mode`
- `llm_parse_status`
- `llm_fallback_reason`
- `Decision Brief`

If the run did not end in `llm_assisted`, ask:

- Was the API key actually loaded?
- Did the model return valid JSON?
- Did the JSON pass strict schema validation?
