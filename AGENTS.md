# AgentCommerce Codex Guide

## 1. Project Goal

AgentCommerce is a multi-agent market intelligence system for e-commerce research.

The current implemented path is:

`user_query -> planner -> research -> crawler -> data_processing -> analysis -> strategy -> report -> markdown report`

The current repository is focused on stabilizing this core workflow before expanding into larger orchestration or multi-agent reasoning systems.

## 2. Current Phase

Treat the repository as being in the "stable workflow + analytics + strategy output hardening" stage.

Current priorities:

1. keep the LangGraph workflow stable
2. improve crawler robustness inside the existing node boundary
3. improve analytics quality
4. improve strategy output quality
5. improve documentation and testing

Do not treat future architecture ideas as already implemented.

## 3. Fixed Workflow

The workflow backbone is fixed:

```text
planner
-> research
-> crawler
-> data_processing
-> analysis
-> strategy
-> report
```

Rules:

1. do not change this graph casually
2. do not insert new orchestration layers into the main path
3. prefer improving node internals over changing workflow shape

## 4. Current In-Scope

Allowed work during the current stage:

1. crawler stability and diagnostics
2. analytics enhancement
3. strategy output hardening
4. deterministic report quality
5. tests, regression assets, and docs
6. minimal LLM-assisted strategy support within the current `strategy_agent`

## 5. Current Out-Of-Scope

Do not implement these unless the user explicitly reopens the scope:

1. multi-LLM debate
2. HITL / Feishu approval
3. API orchestration
4. task orchestration
5. checkpoint / resume systems
6. FastAPI task API
7. new business domains outside the current workflow
8. crawler expansion to large new site sets by default

## 6. Agent And Module Boundaries

### `planner`

- keep workflow entry stable
- do not absorb downstream logic

### `research`

- derive deterministic crawl parameters
- outputs:
  - `crawl_keyword`
  - `crawl_fields`
  - `crawl_depth`
  - `crawl_limit`

### `crawler`

- consume research outputs only
- do not guess crawl inputs on its own
- route through provider structure
- return normalized product data plus crawl diagnostics

### `data_processing`

- clean invalid records
- normalize field types
- preserve relevant structured fields for later analysis

### `analysis`

- orchestrate modular analytics only
- do not collapse all analysis into one large function

### `strategy`

- support current strategy modes:
  - `rule_based`
  - `llm_assisted`
  - `rule_based_fallback`
- output:
  - `strategy`
  - `decision_brief`
  - execution diagnostics

### `report`

- remain deterministic
- render existing state
- do not invent new strategy conclusions

### `crawlers/`

- provider-oriented structure
- current main provider path:
  - `crawler_agent -> factory -> amazon_provider`

### `analysis/`

- modular analytics structure
- current modules:
  - `price_analysis`
  - `review_analysis`
  - `brand_analysis`
  - `quality_metrics`

## 7. Strategy LLM Rules

Current `strategy_agent` behavior must stay honest and reversible:

1. default mode is `rule_based`
2. `llm_assisted` is optional
3. if LLM output fails parsing or validation, fall back to `rule_based_fallback`
4. keep `decision_brief` structured and validated
5. keep execution diagnostics visible:
   - `strategy_execution_mode`
   - `llm_parse_status`
   - `llm_fallback_reason`

Current LLM integration constraints:

1. do not turn the whole system into an LLM-first workflow
2. do not add multi-LLM routing
3. do not add debate logic
4. do not add hidden silent fallbacks that mask failure

## 8. Implementation Rules

When modifying the repository:

1. keep the implementation minimal
2. prefer local fixes over broad refactors
3. keep fallback paths explicit
4. preserve default `rule_based` usability without API keys
5. preserve testability and auditability
6. do not add external runtime complexity unless explicitly requested

## 9. Testing Rules

Before claiming completion:

1. run targeted tests for touched areas
2. run `py -m pytest -q` when the change affects runtime behavior or tests
3. do not rely on live network calls inside pytest
4. keep regression assets fixed and reusable
5. protect both success and fallback paths for `strategy_agent`

## 10. Commit Rules

Each turn should focus on one clear goal.

Rules:

1. do not mix unrelated changes into one commit
2. if unrelated local changes exist, call them out and avoid including them
3. do not silently commit `.env` or local secrets
4. prefer one accurate commit per scoped task

## 11. Standard Completion Report

After each completed task, report at least:

1. change summary
2. key constraints respected
3. test results
4. current git status
5. next-step recommendation

If a commit was made, also report:

1. file list included in the commit
2. commit hash
3. commit message
4. whether it was pushed to `origin/main`

## 12. Codex Working Agreement

When working in this repository:

1. check git status first
2. do not mix unrelated changes
3. keep scope narrow for each round
4. run tests before completion claims
5. keep outputs concise, structured, and auditable
6. if a request conflicts with this file, call out the conflict explicitly instead of silently expanding scope
