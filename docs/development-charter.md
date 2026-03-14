# AgentCommerce Development Charter

## 1. Project Goal

The goal of this project is to build a multi-agent market intelligence system for e-commerce market research.

The system is intended to:

- collect product data
- analyze market structure
- generate strategy insights
- coordinate multiple AI agents
- eventually support human approval through Feishu
- eventually support multi-LLM collaboration and debate

## 2. Development Principle

The system must evolve in explicit phases.

Do not implement all future features at once.

Development priority:

1. Phase 1: stable multi-agent workflow
2. Phase 2: analytics and report quality
3. Phase 3: documentation and architecture clarity
4. Phase 4: LLM integration
5. Phase 5: multi-LLM debate
6. Phase 6: human-in-the-loop via Feishu

Only move forward when the current phase is stable enough to justify expansion.

## 3. Current System Scope

The current workflow is fixed as:

```text
planner
-> research
-> crawler
-> data_processing
-> analysis
-> strategy
-> report
```

The current stage goal is:

`user_query -> markdown report`

This pipeline must run reliably without external orchestration systems.

## 4. Agent Roles

### Planner Agent

Role: project manager

Responsibility:

- understand the workflow entrypoint
- preserve the high-level execution structure

### Research Agent

Role: market researcher

Responsibility:

- convert the query into crawl parameters
- determine:
  - `crawl_keyword`
  - `crawl_fields`
  - `crawl_depth`
  - `crawl_limit`

### Crawler Agent

Role: data collection engineer

Responsibility:

- fetch product data through providers
- handle fallback behavior
- return explicit crawl status

### Data Processing Agent

Role: data engineer

Responsibility:

- normalize fields
- clean invalid records

### Analysis Agent

Role: data analyst

Responsibility:

- compute statistics
- orchestrate analytics modules

### Strategy Agent

Role: business strategist

Responsibility:

- derive market insights

### Report Agent

Role: technical writer

Responsibility:

- generate the final Markdown report

## 5. Crawler Architecture Rule

Crawler behavior must use a provider architecture.

Current shape:

```text
crawler_agent
      ↓
provider_factory
      ↓
amazon_provider
```

Future providers may include:

- `amazon_provider`
- `jd_provider`
- `taobao_provider`
- `aliexpress_provider`

Providers must return normalized product structures.

## 6. Analytics Architecture Rule

Analytics must remain modular.

Current modules include:

- `price_analysis`
- `review_analysis`
- `brand_analysis`
- `quality_metrics`

Each module should return structured outputs.

`analysis_agent` should orchestrate these modules rather than embedding all logic in one function.

## 7. Future LLM Integration

LLM integration is a future phase, not a current requirement.

Planned order:

- first: `strategy_agent` and `report_agent`
- later: `research_agent`

Future role examples may include:

- Analyst LLM
- Strategy LLM
- Risk LLM
- Critic LLM
- Synthesis LLM

## 8. Future Multi-LLM Debate

The long-term architecture may include a debate layer such as:

```text
analysis_result
-> Analyst Agent
-> Strategy Agent
-> Risk Agent
-> Critic Agent
-> Synthesis Agent
-> final recommendation
```

This is intentionally deferred until the deterministic workflow is stable.

## 9. Future Human-in-the-Loop

Human approval through Feishu is a later-stage concern.

Expected approval points:

- before crawler execution
- before final strategy output

Feishu is intended to act as:

- notification channel
- approval channel
- task resume trigger

This must not be implemented before the core workflow is stable.

## 10. Current Development Rules

During the current stage:

Do:

- improve crawler stability
- improve analytics
- improve report quality
- write documentation

Do not:

- add orchestration systems
- add API gateways
- add human approval logic
- expand the architecture scope beyond the current phase

## 11. Expected Outcome

The project should evolve into an AI market intelligence agent with these eventual capabilities:

- multi-agent workflow
- crawler data pipeline
- market analytics
- strategy generation
- multi-LLM collaboration
- human approval loop

Until then, the repository should prioritize a stable, inspectable, and well-documented core workflow.
