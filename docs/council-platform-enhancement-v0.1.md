# Phase 6.4 Platform Enhancement v0.1

## Scope
This phase adds a minimal platform layer for configuration, dictionary versioning, and governance observability without changing execution authority boundaries.

## 1) Strategy Configuration Center v0.1
Unified entrypoint:
- `tools/council_bridge/policy_config_center.py`

Config files:
- `config/policy_center/default.json`
- `config/policy_center/owner_overrides.json`
- `config/policy_center/group_overrides.json`
- `config/policy_center/workspace_overrides.json`
- `config/policy_center/project_overrides.json`

Override order:
`default -> owner -> group -> workspace -> project`

Covered config domains:
- lane switches (`chat_lane_enabled`, mention policy, allow/block groups)
- alias registry (`active_version`, `versions`)
- policy/alias scope metadata

Compatibility:
- existing adapter APIs remain unchanged
- `bridge_config.resolve_runtime_config` now adapts from policy center

## 2) Dictionary Version + Publish/Rollback v0.1
Version data lives in:
- `default.json -> alias_registry`

Runtime records include:
- `dictionary_version`
- `policy_version`
- `policy_scope`
- `alias_scope`

Publish/rollback helpers:
- `list_alias_versions(...)`
- `set_active_alias_version(...)`

Activation mechanism:
- switch `alias_registry.active_version`
- no UI required

Rollback reserve:
- keep multiple version entries under `alias_registry.versions`
- set previous version as `active_version`

## 3) Governance Metrics Summary v0.1
Module:
- `tools/council_bridge/platform_governance_metrics.py`

Output artifact:
- `artifacts/council_governance_metrics_summary.json`

Metrics included:
- normalization hit / ambiguity / ignored
- feedback mapping hit / miss
- role rework detect rate
- state validation pass / block
- apply success / blocked
- execution dispatch success / blocked

Aggregation scopes:
- workspace_id
- project_id
- owner

No dashboard introduced; JSON summary only.

## 4) Workspace/Project Scope Enhancement v0.1
Scope fields now propagated in routing/mapping context:
- `workspace_id`
- `project_id`
- `policy_scope`
- `alias_scope`

Where used:
- route result artifact
- feedback mapping result
- role rework mapping result
- governance metrics aggregation

## Guardrails Preserved
- no new execution permissions
- no bypass of apply/dispatch gates
- normalization/config/metrics layers are governance-only
- HITL / artifact-first / governance over automation unchanged

## How this supports Phase 6.5+
This adds a reusable control plane for:
- org/workspace policy rollout
- dictionary release management
- scoped governance analytics
- future pluginized policy/routing without rewriting adapters
