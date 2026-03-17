# Council -> Codex Intake v0 (Semi-Manual)

This document defines how Codex should read and consume a handoff artifact in the current semi-manual bridge phase.

This is documentation only.  
No automatic execution is implemented by this document.

## 1. Intake Entry

Default handoff artifact path:

- `artifacts/council_bridge_handoff.json`

Codex should treat this file as the intake source for one execution round.

## 2. When Artifact Is Executable

Codex may execute only when all conditions are true:

1. `approval_status == "approved"`
2. `codex_ready_payload` is present and non-null
3. `validation_snapshot.dry_run_status == "valid"`
4. `validation_snapshot.dry_run_errors` is empty
5. `request_id` and `brief_id` are present

If any condition fails, Codex should not execute.

## 3. Status Values That Must Not Be Executed

Do not execute when:

1. `approval_status == "needs_fix"`
2. `approval_status == "rejected"`

Expected behavior in those cases:

1. return a short non-execution note
2. point back to handoff correction
3. do not modify repository files

## 4. Authoritative Fields For Codex

Codex should treat these fields as authoritative:

1. `request_id`
2. `brief_id`
3. `approval_status`
4. `codex_ready_payload`
5. `validation_snapshot`
6. `notes`

Meaning:

1. use these as execution boundaries
2. do not re-interpret intent beyond this scope

## 5. Minimum Data Needed From codex_ready_payload

Minimum required fields for practical execution:

1. `goal`
2. `allowed_files`
3. `constraints`
4. `validation_steps`
5. `delivery_format`

Optional but useful:

1. `scope`
2. `non_goals`
3. `repo_context`

If minimum fields are missing, treat as non-executable and request correction.

## 6. How To Respect allowed_files And constraints

Codex should follow these rules:

1. edit only paths listed in `allowed_files`
2. if a needed file is outside `allowed_files`, stop and request updated handoff
3. follow `constraints` as hard limits
4. if a task conflicts with `constraints`, do not proceed

This keeps the semi-manual bridge auditable.

## 7. Out-of-Scope Items During Intake

Codex should treat these as out of scope in v0:

1. automatic execution triggers
2. MCP bridge runtime behavior
3. orchestration, scheduling, retries
4. multi-agent debate or role routing
5. HITL/Feishu integration logic
6. workflow backbone redesign

## 8. Minimal Execution Receipt (After Execution)

If execution is performed on an approved artifact, return a minimal receipt:

1. `request_id`
2. `brief_id`
3. `execution_status` (`completed` / `blocked`)
4. `changed_files`
5. `constraints_respected` (yes/no + short note)
6. `validation_results` (what was run and result)
7. `summary`
8. `next_step_suggestion`

This receipt is small but sufficient for owner review.

## 9. Practical Note

This intake guide is a semi-manual contract aid only.

It does not mean the repository has automatic Council -> Codex execution.
