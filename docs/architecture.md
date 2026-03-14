# EcomScout-AI Architecture

## Purpose

The current system is a deterministic multi-agent workflow for e-commerce market research.

Its Phase 1–2 goal is simple:

`user_query -> markdown report`

The architecture is intentionally kept narrow so the core workflow becomes stable before adding orchestration, approvals, or LLM layers.

## Workflow

The current graph order is fixed:

```text
planner
-> research
-> crawler
-> data_processing
-> analysis
-> strategy
-> report
```

This workflow should remain unchanged during the current stage.

## Agent Roles

### Planner Agent

Role: workflow entry coordinator

Current responsibility:

- preserve the stable multi-agent pipeline entrypoint

### Research Agent

Role: market researcher

Current responsibility:

- convert `user_query` into deterministic crawl parameters

Outputs:

- `crawl_keyword`
- `crawl_fields`
- `crawl_depth`
- `crawl_limit`

### Crawler Agent

Role: data collection engineer

Current responsibility:

- consume research output
- route to the correct provider
- return normalized products plus crawl status

The crawler must not guess crawl parameters on its own.

### Data Processing Agent

Role: data engineer

Current responsibility:

- clean invalid records
- normalize numeric fields
- preserve optional fields such as brand / BSR / category

### Analysis Agent

Role: data analyst

Current responsibility:

- orchestrate analytics modules
- return structured analysis output

### Strategy Agent

Role: business strategist

Current responsibility:

- derive a practical market suggestion from the analysis output

### Report Agent

Role: technical writer

Current responsibility:

- produce the final Markdown market report
- surface crawl configuration and data source explicitly

## Module Responsibilities

### `ecomscout_ai/agents/`

Contains the LangGraph node implementations.

Each file corresponds to one workflow role.

### `ecomscout_ai/crawlers/`

Contains the crawler subsystem.

Current structure:

- `base.py`
- `factory.py`
- `models.py`
- `playwright_client.py`
- `providers/amazon_provider.py`

Current provider chain:

```text
crawler_agent
-> provider factory
-> amazon_provider
```

The provider layer is where future site expansion should happen.

### `ecomscout_ai/analysis/`

Contains modular analytics.

Current modules:

- `price_analysis.py`
- `review_analysis.py`
- `brand_analysis.py`
- `quality_metrics.py`
- `common.py`

This keeps analytics extensible without turning `analysis_agent` into a monolith.

### `ecomscout_ai/graph/`

Contains LangGraph workflow assembly.

Current expectation:

- the graph is stable
- future work should improve node internals, not graph shape

### `ecomscout_ai/state/`

Contains the shared `AgentState`.

## Current Shared State

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

## Crawler / Provider Structure

The crawler architecture is provider-based.

Current example:

```text
crawler_agent
      ↓
provider_factory
      ↓
amazon_provider
```

Current Amazon provider behavior:

1. attempt live Amazon crawl
2. parse search result cards
3. optionally enrich detail fields for deeper crawl depth
4. if live crawl fails, return normalized fallback data

Current `crawl_status` values:

- `success`
- `partial_success`
- `fallback`
- `failed`

The report uses this status to distinguish live data from fallback output.

## Analytics Structure

The analytics layer is deterministic and modular.

### Price Analytics

Current outputs include:

- `avg_price`
- `median_price`
- `price_percentiles`
- `price_bands`

### Review Analytics

Current outputs include:

- `review_avg`
- `review_median`
- `review_distribution`

### Brand Analytics

Current outputs include:

- `brand_counts`
- `brand_share`
- `brand_coverage`

### Dataset Quality

Current outputs include:

- `sample_size`
- `missing_price_ratio`
- `missing_rating_ratio`
- `missing_brand_ratio`

## Report Generation Flow

The report generation is still deterministic.

Current report sections include:

- `Query`
- `Crawl Configuration`
- `Data Source`
- `Dataset Summary`
- `Dataset Quality`
- `Sample Products`
- `Price Analysis`
- `Price Distribution`
- `Review Statistics`
- `Brand Overview`
- `Strategy Suggestion`

This stage prioritizes reliability and traceability over stylistic polish.

## Current Architectural Constraint

This repository is currently in the deterministic workflow + modular analytics stage.

That means:

- improve crawler stability
- improve analytics quality
- improve report quality
- improve documentation

And explicitly do not add:

- API orchestration systems
- human approval logic
- Feishu integration
- LLM integration
- multi-LLM debate

Those belong to later phases after the current workflow is stable.
