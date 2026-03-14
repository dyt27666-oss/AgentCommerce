# EcomScout-AI

EcomScout-AI is a LangGraph-based multi-agent market intelligence workflow for e-commerce research.

The current system turns:

`user_query -> planner -> research -> crawler -> data_processing -> analysis -> strategy -> report`

into a Markdown market analysis report.

## Current Scope / Development Principles

The project follows a phased development model.

Current in-scope work is limited to:

- workflow stability
- crawler robustness
- analytics enhancement
- report quality
- documentation clarity

Current out-of-scope work is explicitly deferred:

- LLM integration
- multi-LLM debate
- Feishu approval
- API orchestration
- task orchestration
- checkpoint resume

The core workflow graph is treated as stable and should not be changed casually.

## Current Workflow

```text
planner
-> research
-> crawler
-> data_processing
-> analysis
-> strategy
-> report
```

## Agent Roles

- `planner`: keeps the workflow entry stable
- `research`: converts the query into deterministic crawl parameters
- `crawler`: fetches data from providers and handles fallback behavior
- `data_processing`: normalizes and cleans product records
- `analysis`: orchestrates modular market analytics
- `strategy`: derives practical market-entry guidance
- `report`: renders the final Markdown report

## Current Architecture Shape

The current implementation is a deterministic workflow with modular analytics.

Key structure:

```text
ecomscout_ai/
├── analysis/
├── agents/
├── crawlers/
├── graph/
└── state/
```

- `agents/` contains workflow nodes
- `crawlers/` contains provider-facing crawl logic
- `analysis/` contains analytics modules
- `graph/` contains LangGraph assembly
- `state/` contains the shared workflow state

## Shared State

The current workflow state is:

```python
{
    "user_query": str,
    "crawl_keyword": str,
    "crawl_fields": list,
    "crawl_depth": int,
    "crawl_limit": int,
    "crawl_status": str,
    "products": list,
    "clean_data": list,
    "analysis_result": dict,
    "strategy": str,
    "report": str,
}
```

## Current Analytics Modules

The analysis layer is modular and currently includes:

- `price_analysis`
- `review_analysis`
- `brand_analysis`
- `quality_metrics`

`analysis_agent` orchestrates these modules and returns structured outputs instead of embedding all logic into a single function.

## Running The Project

Install dependencies:

```powershell
py -m pip install -r requirements.txt
```

Run the workflow:

```powershell
py main.py
```

### Optional Strategy LLM Configuration

By default, the project runs in `rule_based` strategy mode and does not require any API key.

Only when you explicitly enable `llm_assisted` strategy mode do you need to configure environment variables.

## Strategy Modes

The current `strategy_agent` supports:

- `rule_based`
- `llm_assisted`

It also returns a structured `Decision Brief` and tracks the actual execution path through `strategy_execution_mode`:

- `rule_based`
- `llm_assisted`
- `rule_based_fallback`

Default behavior does not require any API key because the workflow starts in `rule_based` mode.

If `llm_assisted` is enabled and the model output cannot be parsed or validated, the system automatically falls back to `rule_based_fallback`.

The current minimum `.env` shape is:

```env
OPENAI_API_KEY=
```

You can copy from `.env.example` when testing the LLM-assisted strategy path.

Run tests:

```powershell
py -m pytest -q
```

## Current Limitations

- Amazon crawling is still best-effort rather than production-grade
- fallback mode may use normalized mock data when live crawl is unavailable
- no orchestration layer exists yet
- no human approval loop exists yet
- no LLM-driven reasoning exists yet

## Project Governance

The repository-level development rules are defined in:

- `docs/development-charter.md`
- `docs/architecture.md`
- `docs/roadmap.md`
