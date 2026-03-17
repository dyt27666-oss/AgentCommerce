# Phase 6.1 Council Role Formalization v0.1

## Scope
Phase 6.1 formalizes Council as a governed multi-role collaboration layer on top of existing:
- unified council artifact schema v0.1
- council state machine v0.1
- feishu feedback mapping + observe/apply gates
- execution handoff gate

Out of scope in this phase:
- debate engine
- execution permission expansion
- UI expansion
- automatic role autonomy bypassing owner approval

## Official Council Roles
1. planner
2. researcher
3. critic
4. strategist
5. reviewer
6. reporter

## Role Contract (v0.1)
Each role has:
- responsibilities
- inputs
- outputs
- dependency roles
- allowed artifact types
- owner-reviewable sections

Role contracts are implemented in:
- `tools/council_bridge/council_role_contract.py`

## Minimal Collaboration Sequence
Default sequence:
`planner -> researcher -> critic -> strategist -> reviewer -> reporter`

This is not a black-box fixed pipeline.
Owner can re-route by explicit feedback, e.g.:
- "让 critic 重看"
- "让 strategist 重写"

Re-route is represented as a role transition hint and fed into Council round logic.

## Role-Level Artifact Structure
Role-level artifacts continue to use `council.artifact.v0.1` and add optional:

```json
{
  "role_metadata": {
    "role": "critic",
    "role_round": 1,
    "role_run_id": "critic-r1",
    "depends_on_roles": ["planner", "researcher"],
    "upstream_artifact_ids": ["plan-001", "risk-001"],
    "owner_feedback_ids": ["fb-001"],
    "rerun_of_role_run_id": null,
    "execution_authority": false,
    "generated_at": "2026-03-16T20:00:00+08:00"
  }
}
```

Constraints:
- role metadata must stay advisory
- `execution_authority` must remain `false`
- role artifacts cannot directly enter execution lane
- owner approval gate remains mandatory for downstream execution

## Integration With Existing Council Schema
No breaking change to current parser:
- base schema fields remain unchanged
- `role_metadata` is additive and optional
- state machine keeps governing status transitions
- role outputs aggregate into decision/handoff only after owner-governed review

## Audit and Lineage
Role metadata supports:
- role run trace (`role_run_id`)
- upstream linkage (`upstream_artifact_ids`)
- rerun linkage (`rerun_of_role_run_id`)
- owner feedback back-link (`owner_feedback_ids`)

## Sample
Generated sample file:
- `docs/council_role_samples_v0.1/minimal_role_collaboration_sample.json`

Generation command:
```bash
py -m tools.council_bridge.council_role_collaboration_demo
```

## Tests
- `tests/test_council_role_contract.py`

Coverage includes:
- role contract completeness
- minimal chain order
- owner reroute hint parsing
- role metadata no-execution constraint
- advisory packet generation
- sample generation
