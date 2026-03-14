# Council Layer v0 / MCP Bridge v0

## 1. Why This Document Exists

The current repository already has a stable execution workflow:

`planner -> research -> crawler -> data_processing -> analysis -> strategy -> report`

That is useful, but it is still an **execution workflow**, not yet a **collaborative multi-agent system**.

Why?

1. the current agents are workflow nodes, not role-based collaborators
2. there is no deliberation layer that compares alternative plans
3. there is no explicit separation between "decide what to do" and "execute the work"
4. there is no formal bridge from higher-level planning agents into Codex as an execution engine

So the real design gap is not "more nodes".  
The gap is: **how should a higher-level council coordinate decisions, then hand scoped execution tasks to Codex cleanly?**

## 2. Current Reality vs Target Shape

### Current Reality: Execution Layer

The current repository already provides:

1. deterministic workflow execution
2. provider-based crawl execution
3. modular analytics
4. deterministic reporting
5. bounded strategy generation with rule-based and optional `llm_assisted` modes

This layer is best understood as:

- **Execution Layer**
- narrow, inspectable, testable
- focused on turning one query into one report

### New Target: Council / Deliberation Layer

The new layer is not meant to replace the existing workflow.

Its role would be:

1. frame work as a scoped task
2. generate alternative approaches or plans
3. critique and refine the plan
4. hand a bounded implementation or execution request to Codex
5. let Codex execute as the tool-using worker

So the intended stack becomes:

```text
Owner
-> Council Layer
-> Executor Agent (Codex)
-> Execution Layer
```

## 3. Council Layer v0 Goal

Council Layer v0 should solve only one problem:

**Allow a small set of role-based agents to produce a scoped execution brief, then call Codex as the executor through an MCP / Agents SDK path.**

It should not try to solve:

1. full autonomous project management
2. unrestricted multi-agent debate
3. human approval workflows
4. background task orchestration
5. production-grade agent memory or resume logic

In other words:

**v0 is a coordination shell, not a full autonomous agent platform.**

## 4. Role Design

The minimum role set should be:

### Owner = user

Role:

- defines the task goal
- accepts or rejects high-level proposals
- stays outside the automated council loop unless explicitly asked

Input:

- product goal
- constraints
- acceptance criteria

Output:

- approved task intent

### PM Agent

Role:

- convert the owner request into a scoped work item
- define success criteria
- constrain the size of the task

Input:

- owner request
- current repository context

Output:

- task brief
- acceptance criteria
- non-goals

### Architect Agent

Role:

- map the task brief onto the current repository structure
- propose the smallest viable implementation path

Input:

- PM task brief
- current architecture constraints

Output:

- proposed implementation path
- touched modules
- risks and assumptions

### Critic Agent

Role:

- challenge weak assumptions
- identify scope creep, risk, or architecture conflicts

Input:

- PM brief
- Architect proposal

Output:

- objections
- risk notes
- scope reductions

### QA Agent

Role:

- translate the agreed plan into verification expectations

Input:

- final scoped proposal
- existing tests and repo conventions

Output:

- test checklist
- minimal validation plan

### Executor Agent = Codex

Role:

- perform concrete repository work
- edit files
- run tests
- produce implementation output or docs

Input:

- approved execution brief
- repository workspace
- verification checklist

Output:

- actual file changes
- test results
- git status
- next-step recommendation

## 5. Boundary Between Council and Codex

This boundary must stay explicit.

### Council Layer does

1. framing
2. scoping
3. critique
4. decision brief generation
5. execution request construction

### Codex does

1. read repository state
2. modify files
3. run tests
4. verify results
5. produce commit-ready output

If the Council Layer starts directly editing the repo, the design becomes muddy.

If Codex starts inventing its own task framing, the Council Layer becomes redundant.

So the separation is:

**Council decides; Codex executes.**

## 6. Minimal Collaboration Flow

One minimal round should work like this:

```text
Owner request
-> PM Agent frames task
-> Architect Agent proposes smallest implementation path
-> Critic Agent constrains risk and scope
-> QA Agent defines verification
-> Council emits one execution brief
-> Codex executes in the repository
-> Codex returns results to Owner
```

This is already enough to validate whether the collaboration model is useful.

No full debate loop is required in v0.

## 7. Codex Positioning

In this design, Codex is not the council itself.

Codex is the **Executor Agent**.

That means:

1. Codex should receive already-scoped work
2. Codex should not be forced to invent the governance layer
3. Codex is strongest when asked to execute bounded tasks against a real workspace
4. Codex output should remain auditable:
   - changed files
   - test results
   - git status
   - follow-up recommendation

This matches the current project reality better than pretending Codex is already a fully autonomous top-level project manager.

## 8. MCP / Agents SDK Role In This Design

### MCP role

MCP is the bridge that exposes capabilities and context between agents and tools.

For this v0 design, the relevant concept is:

1. Codex can be exposed as an MCP-compatible execution endpoint
2. a higher-level controller can talk to that executor through MCP
3. MCP keeps the integration surface explicit instead of embedding hidden shell calls inside a planner

OpenAI documents Codex and MCP as compatible integration directions, and OpenAI also documents a docs MCP server for pulling official documentation context.  
This document is making a design inference from those official directions: **use MCP as the explicit bridge between a deliberation layer and Codex-style execution.**

Official references:

- [Docs MCP](https://platform.openai.com/docs/docs-mcp)
- [Agents SDK](https://platform.openai.com/docs/guides/agents-sdk/)
- [OpenAI MCP guide](https://platform.openai.com/docs/mcp/)
- [Codex as MCP server discussion](https://openai.com/index/unlocking-the-codex-harness/)

### Agents SDK role

Agents SDK is the cleaner place to host the Council Layer logic.

Why?

1. it is designed for agent orchestration and handoffs
2. it can hold role definitions more naturally than the current execution graph
3. it avoids forcing LangGraph to do two jobs at once:
   - execution workflow
   - upper-level deliberation workflow

So the recommended split is:

1. **Agents SDK**: Council Layer
2. **Codex via MCP**: Executor bridge
3. **Current repository workflow**: Execution Layer

## 9. Why Only v0

Current constraints matter.

This repository is not ready for a full autonomous multi-agent debate system because:

1. the execution layer only recently stabilized
2. strategy LLM integration is still being hardened
3. evaluation baselines are minimal
4. there is no durable orchestration layer
5. there is no HITL / approval / resume mechanism yet

A full autonomous council now would add coordination complexity before the execution layer is stable enough to deserve it.

So v0 should only validate one question:

**Can a small role-based council generate a better execution brief for Codex than direct user prompting alone?**

## 10. Minimal PoC Proposal

### Minimal PoC objective

Validate that:

1. a small council can create one bounded execution brief
2. that brief can be handed to Codex through a clean bridge
3. Codex can execute against the current repository using that brief

### What the first PoC should verify

The first PoC should verify:

1. role separation works
2. the execution brief is clearer than a raw user request
3. Codex can consume the brief and complete a narrow repo task

### What the first PoC should not verify

The first PoC should not verify:

1. autonomous long-running debate
2. multiple executor routing
3. background scheduling
4. human approval
5. production-grade memory
6. multi-LLM comparison quality

## 11. Minimal PoC Shape

Recommended minimum files:

```text
docs/council-layer-v0.md
docs/council-poc-brief-example.md
scratch/council_poc.py            # optional
```

Only the first file is required now.  
The others are suggested only for a later PoC turn.

### Do we need to run Codex CLI as an MCP server?

For the first true bridge PoC:

- **probably yes**

Reason:

The whole point of the PoC is not just "role descriptions".  
It is validating the bridge between a council process and Codex execution.

If that bridge stays implicit, the PoC is too abstract.

### Do we need Agents SDK?

For the first design-complete PoC:

- **recommended, but not mandatory on day one**

Pragmatic sequence:

1. write the council role contract first
2. mock the council output if necessary
3. then use Agents SDK as the orchestration shell for the council

### Smallest PoC path

The smallest credible path is:

1. define PM / Architect / Critic / QA role prompts
2. produce one final execution brief
3. pass that brief to Codex through a bridge interface
4. let Codex run on one narrow repository task
5. compare the result against direct execution without the council brief

## 12. Suggested Directory Sketch

This is only a possible future direction, not an implementation commitment:

```text
agentcommerce_council/
  council/
    roles.py
    prompts.py
    orchestrator.py
  bridge/
    codex_mcp_client.py
  evals/
    sample_tasks/
```

This should remain separate from the current execution layer until the bridge is proven useful.

## 13. Practical Conclusion

The current repository should still be treated as the **Execution Layer**.

Council Layer v0 should be added only as a thin upper layer that:

1. frames work
2. critiques scope
3. produces one execution brief
4. hands execution to Codex

That is enough for a first PoC.

Anything beyond that would likely be premature architecture expansion.
