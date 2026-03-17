# Phase 6.3 Owner Intent Normalization v0.1

## Objective
Build a unified owner intent normalization layer so section feedback and role rework do not grow as disconnected alias systems.

## Architecture
Feishu message text
-> owner intent normalization
-> normalized intent object
-> adapter-specific mapping (feedback / role-rework)
-> state-machine validation (observe/apply flow unchanged)

Normalization is translation-only.
It does not authorize, apply, or dispatch.

## Normalized Output
`NormalizedOwnerIntent` fields:
- intent_type
- target_role
- target_section
- requested_action
- requested_change
- severity
- confidence
- ambiguity_flags
- ignored_reason
- source_text

## Configurable Alias Dictionary
Config file:
- `config/owner_intent_aliases.v0.1.json`

Contains:
- `section_aliases`
- `role_aliases`
- `action_aliases`
- `severity_markers`

## Integration
Reused by:
- `tools/council_bridge/feishu_feedback_mapping_adapter.py`
- `tools/council_bridge/council_role_rework_adapter.py`

Both adapters now consume normalized intent first, then build their own artifact-oriented outputs.

## Governance Constraints Preserved
- normalization does not bypass validation
- normalization does not apply transitions
- ambiguous messages are conservative (`intent_type=unknown` + ambiguity flags)
- HITL / artifact-first / governance over automation unchanged

## Sample
- `docs/owner_intent_normalization_samples_v0.1.json`

## Why this helps Phase 6.4
This creates a reusable semantic contract that can be shared across:
- router policy plugins
- platform-level intent analytics
- configurable org dictionaries
- multi-workspace governance without forking adapter logic
