# Council MCP PoC Plan v0

## 1. Purpose

This document fills one specific gap:

- [council-layer-v0.md](E:/Github/AgentCommerce/docs/council-layer-v0.md) explains the overall design direction
- this document explains the **smallest bridge PoC** for handing a Council-produced task to Codex through an MCP / Agents SDK path

It is not an implementation report.  
It is not proof that the bridge already exists.  
It is only a minimal plan for testing the bridge idea.

## 2. Current Reality

### Already implemented

The repository already has:

1. a stable execution workflow
2. deterministic workflow nodes
3. strategy output with `rule_based`, `llm_assisted`, and `rule_based_fallback`
4. tests and regression coverage for strategy output
5. project-level collaboration constraints in `AGENTS.md`

### Not yet implemented

The repository does **not** yet have:

1. a real Council orchestration layer
2. a Codex execution bridge via MCP
3. an Agents SDK-based Council runner
4. an automated handoff from Council output into Codex execution

So the current status is:

- **Execution Layer exists**
- **Council bridge exists only at design level**

## 3. PoC Goal

The v0 MCP bridge PoC should answer one narrow question:

**Can a Council-produced execution brief be passed to Codex through a thin bridge, so Codex can execute a bounded repository task with less manual prompt rewriting?**

That is the only target for this PoC.

## 4. Success Standard

The PoC is successful if all of the following are true:

1. a small Council process produces one bounded execution brief
2. that brief can be handed to Codex through one explicit bridge layer
3. Codex executes one small repository task from that brief
4. Codex returns a bounded result package:
   - change summary
   - test result
   - git status
   - next-step recommendation
5. the bridge path is simpler than manually rewriting the brief every time

## 5. Minimal Scope

This PoC should stay very small.

It should include only:

1. one Council-produced brief
2. one executor bridge concept
3. one Codex execution run
4. one narrow repository task

It should not include:

1. autonomous multi-round debate
2. multiple executor routing
3. memory or task resume
4. HITL / Feishu
5. background job orchestration
6. production security hardening

## 6. What This PoC Explicitly Does Not Do

This PoC must not be mistaken for:

1. a full multi-agent system
2. a production orchestrator
3. a replacement for the current workflow
4. a live deployment design
5. a proof that Council quality is already better than direct prompting

It is only a bridge experiment.

## 7. Required Components

### 1. Codex CLI

Needed because Codex is the intended Executor Agent.

In the PoC, Codex remains the system that:

1. reads the repository
2. edits files
3. runs tests
4. reports results

### 2. Codex MCP server

Needed if the PoC is meant to validate a real bridge rather than a purely manual handoff.

Why?

Because the bridge question is specifically:

**Can Council output be handed to Codex through an explicit execution interface?**

If Codex is still invoked manually without an explicit bridge, the PoC only validates prompt formatting, not the bridge idea.

### 3. Agents SDK

Recommended for the Council side, but not required for the very first bridge check.

Why recommended?

1. it is designed for role-oriented agent orchestration
2. it provides a cleaner home for PM / Architect / Critic / QA coordination
3. it avoids forcing LangGraph to host two different concerns

Why not mandatory for day one?

Because a manual or mocked Council output is enough to test whether the Codex bridge is even worth building.

## 8. Smallest Call Chain

The minimum bridge path should look like this:

```text
Council brief
-> Executor bridge
-> Codex execution
-> Result return
```

Or more explicitly:

```text
PM / Architect / Critic / QA
-> final execution brief
-> bridge adapter
-> Codex
-> test + status + summary
-> owner
```

This is enough for a v0 bridge PoC.

## 9. Recommended First PoC Task

The first PoC task should be:

**update a small repository-facing document without changing workflow or business logic**

Recommended example:

- improve the `llm_assisted` usage entry in README or docs

Why this task fits:

1. it is small and bounded
2. it touches real repository files
3. it requires Codex to read current project context
4. it can be verified easily
5. it avoids the risk of testing bridge behavior and business logic changes at the same time

## 10. Why This Task Is Good For The Bridge PoC

This task is useful because it isolates the bridge question from product complexity.

It helps test:

1. whether Council can produce a brief with clear scope
2. whether Codex can follow that brief through the bridge
3. whether the returned result package is audit-friendly

It avoids mixing in:

1. crawler flakiness
2. LLM runtime variability
3. workflow graph changes
4. complex validation logic

## 11. Main Risks And Watchpoints

### Risk 1: fake automation

The biggest risk is pretending a manual handoff is already an MCP bridge.

This PoC should be honest about whether the handoff is:

1. manual
2. mocked
3. real MCP-mediated execution

### Risk 2: too much scope

If the first PoC includes:

1. debate
2. approvals
3. live memory
4. multiple tools

then it is no longer a minimal bridge PoC.

### Risk 3: wrong comparison

If the chosen task is too large, it becomes impossible to tell whether failure came from:

1. the bridge
2. Codex execution
3. task complexity

### Risk 4: unclear ownership

The Council must define:

1. scope
2. constraints
3. acceptance criteria

Codex must only execute.

If those responsibilities blur, the PoC becomes hard to evaluate.

## 12. PoC Ready / Not Ready Check

### Ready now

The repository is ready for a **design-level bridge PoC** because:

1. the execution layer is stable enough
2. repository constraints are documented
3. `AGENTS.md` exists
4. strategy output hardening is already in place
5. there are small repository tasks suitable for a controlled bridge test

### Not ready yet

The repository is **not yet ready** for a production-style Council automation layer because it still lacks:

1. an implemented Council runner
2. a real bridge adapter inside the repo
3. stable operational monitoring
4. approval and recovery systems

So the readiness judgment is:

- **Ready for a tiny bridge PoC**
- **Not ready for autonomous multi-agent operations**

## 13. Suggested Next-Step If Ready

If proceeding, the smallest next implementation should be:

1. create one static Council execution brief payload
2. create one tiny bridge adapter stub or script
3. use that stub to invoke Codex on one documentation-only task
4. compare the result with direct manual prompting

This should still avoid:

1. workflow edits
2. business logic changes
3. long-running agent loops

## 14. If Not Ready, What Is Missing

If the team chooses not to implement the bridge PoC yet, the missing prerequisites are:

1. a confirmed choice between manual bridge vs MCP-mediated bridge
2. one approved first task for the bridge test
3. one agreed result format for Codex output

These are planning gaps, not architectural blockers.

## 15. Practical Conclusion

The repository is ready for a **small, documentation-first Council → Codex bridge PoC**, but not for a full autonomous Council system.

The correct next move is not "build the whole council."

The correct next move is:

1. keep Council logic thin
2. test one explicit handoff
3. keep Codex as executor
4. measure whether the bridge adds clarity over direct prompting
