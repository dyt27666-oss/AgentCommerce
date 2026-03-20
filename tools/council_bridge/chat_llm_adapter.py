"""Minimal chat LLM adapter for Feishu chat lane."""

from __future__ import annotations

import os
import re
from typing import Any

DEFAULT_SILRA_MODEL = "glm-4.7"
DEFAULT_SILRA_BASE_URLS = [
    "https://api.silra.cn",
    "https://api.silra.cn/v1",
    "https://api.silra.cn/v1/chat/completions",
]


def _enabled() -> bool:
    raw = str(os.getenv("AGENTCOMMERCE_CHAT_LLM_ENABLED", "")).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    # Auto-enable only if API key is present.
    return bool((os.getenv("SILRA_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip())


def _api_key() -> str:
    key = (os.getenv("SILRA_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("chat llm api key missing (SILRA_API_KEY / OPENAI_API_KEY)")
    return key


def _model_name() -> str:
    return (
        os.getenv("AGENTCOMMERCE_CHAT_MODEL")
        or os.getenv("SILRA_MODEL")
        or os.getenv("OPENAI_MODEL")
        or DEFAULT_SILRA_MODEL
    )


def _base_urls() -> list[str]:
    custom = (os.getenv("SILRA_BASE_URL") or "").strip()
    if custom:
        return [custom]
    return DEFAULT_SILRA_BASE_URLS.copy()


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def generate_chat_reply(
    *,
    user_text: str,
    correlated: dict[str, Any],
    permission_context: dict[str, Any],
) -> dict[str, Any]:
    if not _enabled():
        raise RuntimeError("chat llm disabled by policy")

    from langchain_openai import ChatOpenAI

    api_key = _api_key()
    model_name = _model_name()
    request_id = str(correlated.get("request_id") or "")
    granted_level = str(permission_context.get("granted_permission_level") or "read_only")
    confirmation_required = bool(permission_context.get("confirmation_required"))

    system_prompt = (
        "你是 AgentCommerce 的聊天助手，目标是自然、简洁、可执行。"
        "当前是聊天模式，不要伪装执行已经发生。"
        "如果用户请求执行/修改/本地命令且权限不足，要明确提示需授权。"
        "不要输出 JSON、不要输出模板标题、不要复读系统字段。"
    )
    user_prompt = (
        f"用户消息：{_clean_text(user_text)}\n"
        f"上下文request_id：{request_id or 'n/a'}\n"
        f"当前授权级别：{granted_level}\n"
        f"是否需要二次确认：{confirmation_required}\n"
        "请直接给出中文回复。"
    )

    last_error: Exception | None = None
    for base_url in _base_urls():
        try:
            model = ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=base_url,
                temperature=0.3,
            )
            response = model.invoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )
            content = getattr(response, "content", "")
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            reply = _clean_text(str(content))
            if not reply:
                raise RuntimeError("empty llm reply")
            return {
                "reply_text": reply,
                "response_source": "llm",
                "llm_provider": "silra_compatible",
                "llm_model": model_name,
                "llm_base_url": base_url,
                "llm_error": "",
            }
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"chat llm invocation failed: {last_error}")

