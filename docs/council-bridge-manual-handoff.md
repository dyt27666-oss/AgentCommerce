# Council Bridge Manual Handoff (Phase 5 Pre-step)

## 1. Purpose

This document defines a tiny, manual handoff entry after readonly dry-run export.

It answers one question only:

How should a human confirm the dry-run JSON and convert it into a fixed handoff input for the next Codex step?

## 2. Why Manual Trigger First

At current stage, manual trigger is preferred because:

1. bridge contract is still v0 and should be audited by human eyes
2. repository policy requires explicit scope control and minimal risk
3. automatic execution would hide contract defects too early
4. this keeps rollback cost near zero

## 3. Role of Dry-Run JSON

Dry-run JSON is the contract checkpoint between:

1. Council-side planning artifacts
2. future execution handoff input

It is used to verify:

1. request identity is stable (`request_id`, `brief_id`)
2. scope and non-goals are explicit
3. allowed file boundaries are clear
4. validation steps and delivery format are executable
5. errors are empty before handoff

## 4. Manual Review Checklist

Human reviewer should inspect these fields in order:

1. `status` must be `valid`
2. `errors` must be empty
3. `request_id` and `brief_id` must exist and be non-empty
4. `codex_ready_payload.goal` must match owner intent
5. `codex_ready_payload.allowed_files` must be bounded and expected
6. `codex_ready_payload.constraints` must include no-workflow/no-business-logic boundaries when required
7. `codex_ready_payload.validation_steps` must be realistic and minimal
8. `codex_ready_payload.delivery_format` must match expected reporting

## 5. Continue vs Stop Rules

### Allow handoff only if all conditions are met

1. `status == "valid"`
2. `errors` is an empty list
3. touched scope matches current task boundary
4. constraints prevent out-of-scope execution
5. reviewer confirms payload is actionable and auditable

### Must stop and return for correction if any condition fails

1. `status != "valid"`
2. `errors` is non-empty
3. allowed files are missing or too broad
4. constraints are absent or ambiguous
5. goal/scope conflicts with current Charter phase

## 6. Minimal Handoff Input Shape

The manual handoff input should stay minimal:

```json
{
  "request_id": "exec-req-001",
  "brief_id": "council-poc-brief-001",
  "handoff_status": "approved_for_execution_prep",
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
    "constraints": [
      "do not change workflow graph",
      "do not edit strategy_agent/crawler/graph/tests",
      "do not add new runtime features"
    ],
    "validation_steps": [
      "git status --short --branch",
      "confirm only scoped docs files changed"
    ],
    "delivery_format": [
      "change summary",
      "changed files",
      "git status",
      "next-step recommendation"
    ]
  },
  "reviewer_note": "Manual review passed for tiny bridge prep."
}
```

## 7. Suggested Tiny Manual Procedure

1. run readonly exporter and generate dry-run JSON
2. open exported JSON and apply checklist from Section 4
3. if valid, copy minimal fields into handoff input shape
4. mark `handoff_status` as `approved_for_execution_prep`
5. archive review note for audit trail
6. proceed to next implementation step (still manual trigger)

## 8. Boundary to Future Real Bridge

This manual handoff step does:

1. human confirmation
2. fixed-format input preparation
3. contract quality gate before execution

This step does not do:

1. direct Codex invocation
2. automatic retries
3. task orchestration
4. HITL/Feishu integration
5. autonomous Council execution loops

So this is a preparation gate, not an execution system.
