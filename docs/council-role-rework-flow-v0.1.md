# Phase 6.2 Role Rework Flow v0.1

Flow:

Feishu owner feedback
-> router
-> role rework hint parse
-> role-targeted mapping
-> observe-only result
-> owner confirm
-> apply role rework transition
-> Council re-enter target role node
-> new advisory artifact

## Implemented Components
- `tools/council_bridge/council_role_rework_adapter.py`
- `tools/council_bridge/owner_confirmed_role_rework_apply.py`
- router integration in `tools/council_bridge/feishu_message_router.py`

## Governance Rules
- observe-only stage never applies transition
- only owner/bridge protocol can confirm role rework apply
- chat text cannot confirm apply
- apply still goes through state-machine validation
- generated advisory artifact has no execution authority

## Artifacts
- `artifacts/council_role_rework_mapping_result.json`
- `artifacts/council_role_rework_transition_result.json`
- `artifacts/council_owner_confirmed_role_rework_apply_result.json`
- `artifacts/council_role_rework_advisory_artifact.json`
