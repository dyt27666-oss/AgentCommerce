# Council → Codex Readonly Bridge Stub v0

## 1. Purpose

This document defines a tiny, **readonly** bridge stub for Council Layer v0.

The stub only validates and maps input from:

- `docs/council-mcp-input-sample.json`

into a normalized Codex-ready payload.

This is a design artifact, not an implementation of automated execution.

## 2. Why Readonly First

Starting with readonly mapping is the safest first landing point because it:

1. verifies input contract stability before execution complexity
2. exposes field and boundary problems early
3. avoids accidental scope expansion into orchestration/runtime automation
4. keeps changes auditable and reversible

## 3. Alignment With Existing Assets

This stub is intentionally scoped to current docs:

1. `docs/council-layer-v0.md`: role and layer boundaries
2. `docs/council-mcp-poc-plan.md`: tiny bridge route and JSON draft contract
3. `docs/council-poc-brief-example.md`: Council handoff example
4. `docs/council-mcp-input-sample.json`: concrete input sample

## 4. Stub Goal

The readonly stub should answer one question:

Can we deterministically transform Council PoC input into one normalized execution request payload that Codex can consume?

No execution should happen in this step.

## 5. Minimal Responsibilities

The stub should do only these things:

1. load and parse a Council MCP input JSON document
2. verify required fields are present and type-valid
3. normalize into a stable `codex_ready_payload` shape
4. return structured validation errors if input is invalid
5. output a readonly artifact (print or file) for human review

## 6. Explicit Non-Goals

The stub must not do:

1. no Codex invocation
2. no repo edits
3. no test execution
4. no queue/scheduler/orchestration behavior
5. no HITL/Feishu integration
6. no multi-LLM debate routing

## 7. Input And Output

### Input source

- `docs/council-mcp-input-sample.json`

### Input object coverage

1. `council_brief`
2. `codex_execution_request`

### Output target

A normalized readonly payload for Codex consumption:

- `codex_ready_payload`

## 8. Minimal Processing Flow

```text
read input json
-> structural validation
-> required field validation
-> normalize and sanitize selected fields
-> build codex_ready_payload
-> emit payload + validation report (readonly)
```

## 9. Required vs Optional Fields

### Required fields (tiny PoC)

From `council_brief`:

1. `brief_id`
2. `owner_intent`
3. `scope`
4. `non_goals`
5. `touched_files`
6. `acceptance_criteria`
7. `validation_steps`
8. `delivery_format`

From `codex_execution_request`:

1. `request_id`
2. `brief_id`
3. `execution_brief`
4. `repo_context`
5. `constraints`

### Optional fields (tiny PoC)

For this readonly stub, optional means “ignore if missing”:

1. extra metadata fields not used by the mapping
2. comments/notes fields if later added in docs

## 10. Validation Boundaries

Minimum validation rules:

1. required keys must exist
2. `brief_id` in both objects should match
3. list fields must be arrays of non-empty strings
4. `owner_intent` must be a non-empty string
5. `touched_files` must be a non-empty array
6. `repo_context.repo` and `repo_context.branch` must be non-empty strings

On validation failure:

1. return `status = invalid_input`
2. return `errors` as a list of explicit field-level messages
3. do not produce an executable payload

## 11. Suggested Normalized Payload (Readonly)

```json
{
  "status": "valid",
  "request_id": "exec-req-001",
  "brief_id": "council-poc-brief-001",
  "codex_ready_payload": {
    "goal": "Clarify llm_assisted usage instructions without changing runtime behavior.",
    "scope": [
      "docs-only wording update"
    ],
    "non_goals": [
      "no code edits"
    ],
    "allowed_files": [
      "docs/llm-assisted.md",
      "README.md"
    ],
    "acceptance_criteria": [
      "instructions are step-ordered and concise",
      "success/fallback check fields are explicit"
    ],
    "validation_steps": [
      "git status --short --branch",
      "confirm only scoped docs files changed"
    ],
    "constraints": [
      "do not change workflow graph",
      "do not edit strategy_agent/crawler/graph/tests",
      "do not add new runtime features"
    ],
    "delivery_format": [
      "change summary",
      "changed files",
      "git status",
      "next-step recommendation"
    ],
    "repo_context": {
      "repo": "AgentCommerce",
      "branch": "main"
    }
  },
  "errors": []
}
```

## 12. Suggested Tiny Skeleton (Design Only)

This is a proposal only, not implemented behavior.

### Suggested file path

- `tools/council_bridge/readonly_stub.py`

### Suggested function signatures

```python
def load_input(path: str) -> dict: ...
def validate_contract(payload: dict) -> tuple[bool, list[str]]: ...
def build_codex_ready_payload(payload: dict) -> dict: ...
```

### Suggested output contract

```python
{
  "status": "valid" | "invalid_input",
  "request_id": str | None,
  "brief_id": str | None,
  "codex_ready_payload": dict | None,
  "errors": list[str]
}
```

## 13. Boundary To Future MCP Bridge

Readonly stub boundary:

1. validates and maps input
2. produces a normalized payload
3. stops before execution

Future real bridge boundary (not in this round):

1. pass payload to Codex runtime interface
2. run bounded execution
3. collect `CodexExecutionResult`
4. handle retries or operational concerns

## 14. Why This Is Enough For Tiny Bridge v0

This step is sufficient because it validates the highest-risk early dependency:

1. contract clarity
2. handoff consistency
3. boundary discipline

If the mapping contract is unstable, execution automation should not start yet.

So readonly stub is the correct first code-facing checkpoint.
