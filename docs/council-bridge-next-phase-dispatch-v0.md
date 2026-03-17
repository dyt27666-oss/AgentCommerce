# Council Bridge Next Phase: Dispatch Prep v0

This document defines the next smallest practical phase after current semi-manual bridge v0.9.

This is design-only.  
No runtime integration is implemented here.

## 1. What Current Bridge Already Does

Current v0.9 can already:

1. generate dry-run artifact
2. prepare approved handoff artifact
3. convert approved handoff into Codex-ready prompt text
4. prepare execution receipt artifact
5. prepare final owner review summary artifact

So the bridge already standardizes artifacts and review format.

## 2. Remaining Gap

The main gap is still manual carry:

1. owner must manually take prompt artifact and dispatch it to Codex
2. owner must manually confirm dispatch readiness each round

In short: “prompt exists” but “dispatch-ready package” is not formally produced yet.

## 3. Next Minimal Component (Dispatch Prep)

Next-phase minimal component should be a tiny **dispatch-prep adapter**.

Its purpose:

1. take approved handoff + generated prompt
2. run final pre-dispatch checks
3. output one dispatch-ready package object (or file)

It does **not** execute Codex.

## 4. Inputs and Outputs

### Inputs

1. `artifacts/council_bridge_handoff.json`
2. `artifacts/council_codex_prompt.txt`
3. optional owner dispatch note

### Output

1. `artifacts/council_codex_dispatch_package.json` (proposed)

Minimum output fields:

1. `request_id`
2. `brief_id`
3. `handoff_id`
4. `dispatch_ready` (true/false)
5. `prompt_artifact_path`
6. `dispatch_checks` (list of pass/fail notes)
7. `owner_dispatch_note` (optional)

## 5. Required Gates Before Dispatch-Ready

Dispatch-prep must enforce at least:

1. handoff status is `approved`
2. handoff payload is executable under intake rules
3. prompt artifact exists and is non-empty
4. identity fields are present and non-empty

If any check fails:

1. `dispatch_ready = false`
2. include clear failure reasons
3. stop before any dispatch action

## 6. What Remains Manual Even In Next Phase

Even after dispatch-prep component exists:

1. owner still decides whether to dispatch now
2. owner still triggers Codex manually
3. owner still reviews receipt and final summary manually

So next phase reduces manual packaging, not manual governance.

## 7. Explicitly Out Of Scope

Still out of scope in that phase:

1. auto Codex execution
2. MCP runtime bridge
3. orchestration/scheduler/retry
4. workflow backbone redesign
5. multi-agent runtime expansion

## 8. Why This Is The Smallest Next Step

This phase is minimal because it only adds one missing bridge artifact:

1. from “approved + prompt exists”
2. to “dispatch-ready package with explicit gates”

It improves handoff quality without changing current manual control model.
