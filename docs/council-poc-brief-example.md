# Council PoC Brief Example v0

## Purpose

This file is a single, minimal handoff sample for Council Layer v0.

It shows what a Council-decided execution brief should look like before handing work to Codex.

It is not an automated council system implementation.

## Scenario / Task Goal

Improve the `llm_assisted` usage entry in documentation so a developer can run the minimal validation path with less ambiguity.

Task type:

- docs-only
- no workflow changes
- no business logic changes

## PM Agent Summary

### Objective

Make the LLM-assisted onboarding steps easier to follow in one pass.

### Scope

1. adjust wording in existing docs only
2. keep current behavior unchanged
3. keep guidance aligned with current Silra + `glm-4.7` path

### Non-goals

1. no code changes
2. no new runtime configuration system
3. no orchestration features
4. no new Council automation

## Architect Agent Proposal

### Proposed change set

Touch only:

1. `docs/llm-assisted.md`
2. optionally one short pointer line in `README.md` if needed

### Why this is the smallest valid path

1. docs are the current friction point
2. no dependency on runtime behavior changes
3. easy to review and revert
4. respects Charter boundaries

### Expected output shape

1. clearer step order
2. explicit success/fallback field checks
3. no expansion into full tutorial or architecture rewrite

## Critic Agent Concerns

1. Scope creep risk:
   Turning a docs tweak into a full "Council + MCP tutorial".

2. Hidden behavior claims risk:
   Writing as if bridge automation already exists.

3. Drift risk:
   Documentation might mention fields or commands not present in repository state.

### Critic constraints

1. keep changes to existing docs paths
2. avoid future-state language that reads as implemented capability
3. do not add claims that require live API validation in this task

## QA Agent Acceptance Criteria

1. only documentation files are changed
2. no edits to `strategy_agent`, `crawler`, `graph`, or tests
3. instructions remain consistent with current repo config keys
4. fallback/success recognition fields are explicitly named
5. git diff is small and scoped to docs intent
6. final report includes changed files + git status + next step

## Final Execution Brief For Codex

### Brief ID

`council-poc-brief-001`

### Owner Intent

Improve the clarity of LLM-assisted usage instructions without changing any runtime behavior.

### Execution Scope

Allowed:

1. edit `docs/llm-assisted.md`
2. optional one-line pointer update in `README.md`

Forbidden:

1. no workflow graph edits
2. no business logic edits
3. no prompt logic edits
4. no new docs outside current scope
5. no test changes

### Required Output

1. concise doc wording updates only
2. clear success/fallback check fields:
   - `strategy_execution_mode`
   - `llm_parse_status`
   - `llm_fallback_reason`
3. no claim that Council automation is already implemented

### Validation Steps

1. run `git status --short --branch`
2. confirm only scoped docs files changed
3. if no code changed, no mandatory test run required for this task
4. provide final summary with:
   - changed file list
   - what was clarified
   - current git status
   - next-step recommendation

### Delivery Format

Codex must return:

1. short change summary
2. scoped file list
3. git status
4. whether push is needed

## Responsibility Reminder

Council decides:

1. objective
2. scope
3. constraints
4. acceptance criteria

Codex executes:

1. file edits
2. verification
3. result reporting

This sample demonstrates handoff format only.  
It does not mean a full autonomous Council system is already running.
