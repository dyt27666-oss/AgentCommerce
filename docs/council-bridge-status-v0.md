# Council -> Codex Bridge Status v0

This document is a plain status snapshot of the current bridge v0.

It reflects current repository state only.

## 1. What v0 Already Does

### Implemented helper tools

1. readonly dry-run exporter:
   - `tools/council_bridge/readonly_stub.py`
2. semi-manual handoff writer:
   - `tools/council_bridge/manual_handoff_writer.py`

### Implemented test coverage

1. readonly stub tests:
   - `tests/test_council_readonly_stub.py`
2. handoff writer tests:
   - `tests/test_manual_handoff_writer.py`

### Implemented artifact flow (manual + helper-supported)

1. dry-run artifact can be generated:
   - `artifacts/council_bridge_dry_run.json`
2. handoff artifact can be prepared:
   - `artifacts/council_bridge_handoff.json`
3. contract nullability and status behavior are enforced by writer/tests.

## 2. What Is Documented But Not Automated

The following are defined by docs, but not runtime-automated:

1. Codex intake policy:
   - `docs/council-codex-intake-v0.md`
2. execution receipt contract:
   - `docs/council-codex-execution-receipt-v0.md`
3. lifecycle stages and gates:
   - `docs/council-bridge-lifecycle-v0.md`
4. owner pack/checklist/contract:
   - handoff pack + checklist + contract docs

## 3. What Is Still Manual

1. owner still decides `approval_status`
2. owner still provides `approved_by` and `notes`
3. owner still reviews checklist/contract before moving forward
4. owner still reviews execution receipt content
5. loop-back decisions (`needs_fix` routing) remain human decisions

## 4. What Is Intentionally Out Of Scope In v0

1. no Codex auto-trigger
2. no MCP runtime bridge
3. no orchestration/scheduler/retry
4. no workflow backbone redesign
5. no multi-agent runtime/debate/HITL integration

## 5. Current Minimal Successful v0 Loop

1. generate valid dry-run artifact
2. prepare approved handoff artifact with required fields
3. intake checks pass for approved status
4. produce execution receipt with required summary/compliance fields
5. owner reviews receipt and closes round

## 6. Next Smallest Reasonable Phase

Keep the same bridge boundaries and add only one minimal improvement:

1. a tiny, local receipt writer helper (similar to handoff writer) to reduce manual formatting drift

Why this is the next smallest step:

1. no architecture change
2. no automation expansion
3. improves audit consistency with low risk

## 7. Round audit pack (review/report/archive)

For one-round replay and owner reporting, use:

1. `tools/council_bridge/round_audit_pack_writer.py`

Outputs:

1. machine-readable:
   - `artifacts/council_round_audit_pack.json`
2. owner-readable:
   - `artifacts/council_round_audit_summary.md`

Purpose:

1. replay what happened in this round
2. support phase reporting / README snapshot
3. support new-chat continuation with compact evidence
4. support archive handoff

This tool is summary-only:

1. no dispatch
2. no completion capture
3. no review execution
