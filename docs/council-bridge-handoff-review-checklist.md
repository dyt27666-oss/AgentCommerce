# Council Bridge Handoff Review Checklist (Owner)

Use this checklist before confirming a handoff artifact.
If you need full step-by-step flow, start with:
- `docs/council-bridge-handoff-pack-v0.md`

Current stage is still manual.  
This checklist does not imply automatic bridge execution.

## 1. Minimum checks before marking `approved`

1. `approval_status` is set to `approved`.
2. `request_id` and `brief_id` are present and non-empty.
3. `approved_by` is present and uses stable id format:
   - lowercase letters/numbers/`_`/`-`
   - example: `owner_manual`
4. `approved_at` is present (timestamp string).
5. `codex_ready_payload` is present and non-null.
6. `codex_ready_payload.allowed_files` is bounded and expected.
7. `codex_ready_payload.constraints` is present and clear.
8. `validation_snapshot` includes both keys:
   - `dry_run_status`
   - `dry_run_errors`
9. `validation_snapshot.dry_run_status` is `valid`.
10. `validation_snapshot.dry_run_errors` is an empty list.
11. `notes` has a short approval reason.

## 2. Quick checks for `needs_fix`

1. `approval_status` is `needs_fix`.
2. `codex_ready_payload` is `null`.
3. `validation_snapshot` has `dry_run_status` and `dry_run_errors`.
4. either:
   - `dry_run_errors` is non-empty and points to a fixable issue, or
   - `notes` clearly states the manual fix reason (for scope/constraint correction).
5. `notes` clearly says what to fix next.

## 3. Quick checks for `rejected`

1. `approval_status` is `rejected`.
2. `codex_ready_payload` is `null`.
3. `validation_snapshot` minimum keys are present.
4. `notes` clearly says why this round is rejected.
5. no further handoff to Codex in this round.

## 4. Presence/Nullability quick rule

1. `approved` -> `codex_ready_payload` must exist.
2. `needs_fix` -> `codex_ready_payload` must be `null`.
3. `rejected` -> `codex_ready_payload` must be `null`.

## 5. Final owner decision

1. If all `approved` checks pass, artifact is ready for next manual bridge step.
2. If `needs_fix` checks pass, return for input correction and regenerate dry-run.
3. If `rejected`, stop this round and redefine scope before retrying.
