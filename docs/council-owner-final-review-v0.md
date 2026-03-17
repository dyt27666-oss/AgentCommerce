# Council Owner Final Review v0

This document defines the final owner review pack for one semi-manual bridge round.

It is docs-only guidance for v0.  
No automatic review workflow is implemented.

## 1. Final Review Pack (What to Open Together)

At round end, open these artifacts together:

1. handoff artifact:
   - `artifacts/council_bridge_handoff.json`
2. dispatch receipt:
   - `artifacts/council_codex_dispatch_receipt.json`
3. Codex-ready prompt (if used):
   - `artifacts/council_codex_prompt.txt`
4. execution receipt:
   - `artifacts/council_codex_execution_receipt.json`
5. changed files / diff evidence:
   - local diff output (for files listed in receipt)

Optional references:

1. `docs/council-codex-intake-v0.md`
2. `docs/council-codex-execution-receipt-v0.md`

## 2. Recommended Review Order

Review in this order:

1. `execution_status` from execution receipt
2. `constraints_compliance` from execution receipt
3. `changed_files` list and actual diff
4. linkage fields match across artifacts:
   - `request_id`
   - `brief_id`
   - `handoff_id`
5. handoff scope boundaries:
   - `allowed_files`
   - `constraints`
6. summary and next-step suggestion

## 3. What To Confirm First

Before reading details, confirm:

1. receipt exists and has required fields
2. identity linkage matches handoff artifact
3. constraints are marked compliant
4. changed files are inside `allowed_files`

If these fail, stop and request correction first.

## 4. Decision Rules (Go / No-Go)

### Approve (Go)

Use when all are true:

1. receipt status is `completed` (or acceptable `partial` with explicit approval)
2. constraints are compliant
3. changed files are in allowed scope
4. summary is clear and matches goal
5. next step is reasonable

### Revision Request

Use when work is mostly correct but needs small correction:

1. constraints are still compliant
2. scope is mostly correct
3. minor content/issues need one more pass

### needs_fix

Use when bridge artifacts are usable but correction is required before acceptance:

1. status is `partial` or `blocked` with fixable cause
2. receipt or handoff has missing/unclear required details
3. scope/constraint wording needs tightening

### Rejection

Use when round output is not acceptable for current scope:

1. constraint violation
2. out-of-scope file edits
3. identity linkage mismatch
4. summary/receipt quality too poor to audit reliably

## 5. Decision Boundary Rule (Source-Of-Issue First)

Use this single principle first:

1. If the main issue is **execution result quality**, prefer `revision_request`.
2. If the main issue is **handoff/contract/input quality**, prefer `needs_fix`.
3. If the main issue is **scope/constraint violation**, prefer `rejected` (or `needs_fix` only when clearly recoverable and no boundary breach occurred).
4. If the main issue is **identity mismatch or invalid artifact**, use `rejected` directly.

Quick mapping by issue source:

1. execution/result problem -> `revision_request`
2. handoff/contract/input problem -> `needs_fix`
3. scope/constraint violation -> `rejected`
4. identity mismatch/invalid artifact -> `rejected`

## 6. Borderline Case Examples

### Case A: Output text quality is weak, but scope/compliance is correct

Decision: `revision_request`

Why: this is an execution/result refinement, not a handoff artifact defect.

### Case B: Receipt missing required field (`next_step_suggestion`) but work seems done

Decision: `needs_fix`

Why: artifact/contract completeness issue; fix artifact first.

### Case C: changed_files includes file outside allowed_files

Decision: `rejected`

Why: scope boundary breach, not a minor revision.

### Case D: `request_id` in receipt does not match handoff artifact

Decision: `rejected`

Why: identity linkage invalidates audit reliability.

### Case E: blocked with clear blocker and no boundary breach

Decision: `needs_fix`

Why: recoverable process/input correction is needed before next round.

## 7. How Artifacts Fit Together

1. handoff artifact defines approved scope and boundaries
2. prompt artifact (optional) shows what was sent for execution guidance
3. execution receipt records what was actually done
4. changed files/diff provides evidence for receipt claims

Owner decision should be based on all four, not on summary text alone.

## 8. Minimum Final Review Summary (Owner Output)

At final decision, write a short review summary with:

1. decision (`approved` / `revision_request` / `needs_fix` / `rejected`)
2. identity tuple (`request_id`, `brief_id`, `handoff_id`)
3. status check (`execution_status`, constraint compliance)
4. scope check result (changed files in/out of scope)
5. key reason for decision (1-2 lines)
6. next action

Template (recommended):

- `docs/council-owner-final-review-summary-template.json`

Suggested saved output path per round:

- `artifacts/council_owner_final_review_summary.json`

Practical use:

1. copy the template file
2. fill identity fields from handoff/receipt (`request_id`, `brief_id`, `handoff_id`)
3. fill decision fields (`final_owner_decision`, `execution_status`)
4. fill compliance check + reason + next action
5. save into `artifacts/council_owner_final_review_summary.json`

Semi-manual helper command (optional):

```bash
py tools/council_bridge/final_review_summary_writer.py --final-decision approved --key-reason "Output meets scope and constraints." --next-action "Close round."
```

This helper:

1. reads handoff + execution receipt
2. carries identity linkage automatically
3. derives scope/compliance check fields
4. writes `artifacts/council_owner_final_review_summary.json`
5. does not auto-make owner decisions

## 10. Final review once (single close entrypoint)

For owner final decision close-out in one local command:

```bash
py tools/council_bridge/final_review_once.py --final-decision approved --key-reason "Execution matches scope and constraints." --next-action "Close this round."
```

This entrypoint:

1. reuses final review summary generation
2. writes `artifacts/council_owner_final_review_summary.json`
3. writes `artifacts/council_final_review_once_result.json` with inherited identity/source trace

Still not included:

1. no auto-decision
2. no callback trigger
3. no auto-approval or archive workflow

## 9. Practical Note

This v0 final review is still semi-manual.

It reduces owner stitching work, but does not replace owner judgment.
