"""Council role formalization v0.1 for Phase 6.1.

This module defines role contracts and a minimal orchestrated collaboration sequence.
It preserves the existing artifact schema and adds role-level metadata conventions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


ROLE_PLANNER = "planner"
ROLE_RESEARCHER = "researcher"
ROLE_CRITIC = "critic"
ROLE_STRATEGIST = "strategist"
ROLE_REVIEWER = "reviewer"
ROLE_REPORTER = "reporter"

COUNCIL_ROLES = [
    ROLE_PLANNER,
    ROLE_RESEARCHER,
    ROLE_CRITIC,
    ROLE_STRATEGIST,
    ROLE_REVIEWER,
    ROLE_REPORTER,
]

MINIMAL_ROLE_CHAIN = [
    ROLE_PLANNER,
    ROLE_RESEARCHER,
    ROLE_CRITIC,
    ROLE_STRATEGIST,
    ROLE_REVIEWER,
    ROLE_REPORTER,
]

ROLE_ARTIFACT_TYPES = {"plan", "risk", "review", "decision", "handoff"}

ROLE_CONTRACTS: dict[str, dict[str, Any]] = {
    ROLE_PLANNER: {
        "responsibilities": [
            "拆解目标与阶段计划",
            "定义范围与成功标准",
            "识别执行前置依赖",
        ],
        "inputs": ["owner_brief", "request_context", "previous_round_artifacts"],
        "outputs": ["plan_objective", "scope", "steps", "acceptance_criteria"],
        "depends_on_roles": [],
        "artifact_types": ["plan"],
        "reviewable_sections": ["objective", "scope", "steps", "acceptance_criteria"],
    },
    ROLE_RESEARCHER: {
        "responsibilities": [
            "补充事实依据与假设校验",
            "形成风险输入与依赖说明",
            "标注数据缺口与证据等级",
        ],
        "inputs": ["plan_artifact", "owner_feedback", "reference_materials"],
        "outputs": ["risk_items", "dependencies", "assumptions", "open_questions"],
        "depends_on_roles": [ROLE_PLANNER],
        "artifact_types": ["risk"],
        "reviewable_sections": ["risk_items", "mitigation", "assumptions", "dependencies"],
    },
    ROLE_CRITIC: {
        "responsibilities": [
            "识别方案矛盾和缺失项",
            "提出可执行修订建议",
            "形成阻断条件与升级条件",
        ],
        "inputs": ["plan_artifact", "risk_artifact", "owner_feedback"],
        "outputs": ["review_findings", "missing_items", "recommended_revisions"],
        "depends_on_roles": [ROLE_PLANNER, ROLE_RESEARCHER],
        "artifact_types": ["review"],
        "reviewable_sections": ["review_findings", "contradictions", "recommended_revisions"],
    },
    ROLE_STRATEGIST: {
        "responsibilities": [
            "收敛备选路径并做权衡",
            "形成 Council 推荐路径",
            "输出可交接的决策草案",
        ],
        "inputs": ["plan_artifact", "risk_artifact", "review_artifact"],
        "outputs": ["recommended_path", "tradeoffs", "decision_rationale", "confidence"],
        "depends_on_roles": [ROLE_CRITIC],
        "artifact_types": ["decision", "handoff"],
        "reviewable_sections": ["recommended_path", "decision_rationale", "tradeoffs", "execution_constraints"],
    },
    ROLE_REVIEWER: {
        "responsibilities": [
            "进行最终一致性检查",
            "确认 owner 反馈已回链",
            "判断是否可提交 owner 审核",
        ],
        "inputs": ["decision_artifact", "review_artifact", "lineage"],
        "outputs": ["review_verdict", "unresolved_questions", "submission_readiness"],
        "depends_on_roles": [ROLE_STRATEGIST],
        "artifact_types": ["review"],
        "reviewable_sections": ["review_verdict", "unresolved_questions", "missing_items"],
    },
    ROLE_REPORTER: {
        "responsibilities": [
            "生成对 owner 可读摘要",
            "输出 round 汇总与下一步建议",
            "准备 Council -> owner 的提交包",
        ],
        "inputs": ["plan_artifact", "risk_artifact", "decision_artifact", "review_artifact"],
        "outputs": ["summary", "next_action", "owner_review_packet"],
        "depends_on_roles": [ROLE_REVIEWER],
        "artifact_types": ["decision"],
        "reviewable_sections": ["summary", "next_action", "open_questions"],
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@dataclass(slots=True)
class RoleTransitionHint:
    target_role: str
    reason: str
    source: str


@dataclass(slots=True)
class RoleStep:
    role: str
    expected_artifact_types: list[str]
    depends_on_roles: list[str]


def validate_role_contracts() -> list[str]:
    errors: list[str] = []
    for role in COUNCIL_ROLES:
        contract = ROLE_CONTRACTS.get(role)
        if contract is None:
            errors.append(f"missing contract for role={role}")
            continue

        required_keys = [
            "responsibilities",
            "inputs",
            "outputs",
            "depends_on_roles",
            "artifact_types",
            "reviewable_sections",
        ]
        for key in required_keys:
            if key not in contract:
                errors.append(f"contract[{role}] missing key={key}")

        artifact_types = contract.get("artifact_types", [])
        if not isinstance(artifact_types, list) or not artifact_types:
            errors.append(f"contract[{role}] artifact_types must be non-empty list")
        else:
            for artifact_type in artifact_types:
                if artifact_type not in ROLE_ARTIFACT_TYPES:
                    errors.append(f"contract[{role}] unsupported artifact_type={artifact_type}")

    return errors


def build_minimal_role_chain() -> list[RoleStep]:
    steps: list[RoleStep] = []
    for role in MINIMAL_ROLE_CHAIN:
        contract = ROLE_CONTRACTS[role]
        steps.append(
            RoleStep(
                role=role,
                expected_artifact_types=list(contract["artifact_types"]),
                depends_on_roles=list(contract["depends_on_roles"]),
            )
        )
    return steps


def parse_owner_role_hint(text: str) -> RoleTransitionHint | None:
    normalized = (text or "").strip().lower()
    if not normalized:
        return None

    keyword_map = {
        "让 critic 重看": ROLE_CRITIC,
        "critic 重看": ROLE_CRITIC,
        "让 strategist 重写": ROLE_STRATEGIST,
        "strategist 重写": ROLE_STRATEGIST,
        "planner 重做": ROLE_PLANNER,
        "researcher 重查": ROLE_RESEARCHER,
        "reviewer 重审": ROLE_REVIEWER,
        "reporter 重写": ROLE_REPORTER,
    }
    for key, role in keyword_map.items():
        if key in normalized:
            return RoleTransitionHint(
                target_role=role,
                reason=f"owner requested rerun for {role}",
                source="owner_feedback_text",
            )
    return None


def build_role_metadata(
    *,
    role: str,
    role_round: int,
    depends_on_roles: list[str],
    upstream_artifact_ids: list[str],
    owner_feedback_ids: list[str] | None = None,
    rerun_of_role_run_id: str | None = None,
) -> dict[str, Any]:
    if role not in COUNCIL_ROLES:
        raise ValueError(f"unsupported role={role}")
    if role_round < 1:
        raise ValueError("role_round must be >= 1")

    return {
        "role": role,
        "role_round": role_round,
        "role_run_id": f"{role}-r{role_round}",
        "depends_on_roles": depends_on_roles,
        "upstream_artifact_ids": upstream_artifact_ids,
        "owner_feedback_ids": owner_feedback_ids or [],
        "rerun_of_role_run_id": rerun_of_role_run_id,
        "execution_authority": False,
        "generated_at": _now_iso(),
    }


def attach_role_metadata(artifact: dict[str, Any], role_metadata: dict[str, Any]) -> dict[str, Any]:
    updated = dict(artifact)
    updated["role_metadata"] = dict(role_metadata)
    return updated


def validate_role_metadata(artifact: dict[str, Any]) -> list[str]:
    role_metadata = artifact.get("role_metadata")
    if role_metadata is None:
        return []
    if not isinstance(role_metadata, dict):
        return ["role_metadata must be an object when present"]

    errors: list[str] = []
    role = role_metadata.get("role")
    if role not in COUNCIL_ROLES:
        errors.append("role_metadata.role is invalid")

    if role_metadata.get("execution_authority") is not False:
        errors.append("role_metadata.execution_authority must remain false")

    run_id = role_metadata.get("role_run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        errors.append("role_metadata.role_run_id must be a non-empty string")

    for key in ["depends_on_roles", "upstream_artifact_ids", "owner_feedback_ids"]:
        value = role_metadata.get(key)
        if not isinstance(value, list):
            errors.append(f"role_metadata.{key} must be a list")

    return errors


def synthesize_council_packet(role_artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize role outputs into a council packet for owner review.

    This packet is advisory and does not grant execution permissions.
    """
    by_role: dict[str, list[str]] = {}
    for item in role_artifacts:
        role = None
        role_meta = item.get("role_metadata")
        if isinstance(role_meta, dict):
            role = role_meta.get("role")
        if not isinstance(role, str) or not role:
            role = str(item.get("produced_by_role") or "unknown")

        by_role.setdefault(role, []).append(str(item.get("artifact_id") or ""))

    return {
        "packet_type": "council_role_packet.v0.1",
        "generated_at": _now_iso(),
        "roles_present": sorted(by_role.keys()),
        "artifacts_by_role": by_role,
        "can_enter_execution": False,
        "requires_owner_review": True,
    }
