from __future__ import annotations

import subprocess
from pathlib import Path

from tools.council_bridge.codex_dispatch_runner import build_dispatch_receipt


def _dispatch_ready_ok() -> dict:
    return {
        "request_id": "exec-req-001",
        "brief_id": "council-poc-brief-001",
        "handoff_id": "handoff-20260315-100",
        "dispatch_ready": True,
        "gate_results": [
            {"gate": "handoff_executable", "passed": True, "detail": "passed"},
            {"gate": "prompt_exists", "passed": True, "detail": "passed"},
            {"gate": "prompt_non_empty", "passed": True, "detail": "passed"},
        ],
        "prompt_artifact_path": "artifacts/council_codex_prompt.txt",
    }


def test_dispatch_blocked_when_not_ready(tmp_path: Path) -> None:
    artifact = _dispatch_ready_ok()
    artifact["dispatch_ready"] = False
    artifact["blocking_reason"] = "gate failed"
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("prompt", encoding="utf-8")

    receipt = build_dispatch_receipt(artifact, prompt_path, "codex.cmd")
    assert receipt["dispatch_attempted"] is False
    assert receipt["dispatch_status"] == "blocked"


def test_dispatch_blocked_when_prompt_missing(tmp_path: Path) -> None:
    artifact = _dispatch_ready_ok()
    receipt = build_dispatch_receipt(artifact, tmp_path / "missing.txt", "codex.cmd")
    assert receipt["dispatch_attempted"] is False
    assert receipt["dispatch_status"] == "blocked"
    assert "prompt file not found" in receipt["blocking_reason"]


def test_dispatch_success_path_with_mock(monkeypatch, tmp_path: Path) -> None:
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("prompt text", encoding="utf-8")

    def _mock_run(*args, **kwargs):
        class R:
            returncode = 0
            stderr = ""
            stdout = "ok"

        return R()

    monkeypatch.setattr(subprocess, "run", _mock_run)
    receipt = build_dispatch_receipt(_dispatch_ready_ok(), prompt_path, "codex.cmd", dispatch_mode="run")
    assert receipt["dispatch_attempted"] is True
    assert receipt["dispatch_status"] == "dispatched"


def test_dispatch_failed_when_command_returns_nonzero(monkeypatch, tmp_path: Path) -> None:
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("prompt text", encoding="utf-8")

    def _mock_run(*args, **kwargs):
        class R:
            returncode = 2
            stderr = "bad"
            stdout = ""

        return R()

    monkeypatch.setattr(subprocess, "run", _mock_run)
    receipt = build_dispatch_receipt(_dispatch_ready_ok(), prompt_path, "codex.cmd", dispatch_mode="run")
    assert receipt["dispatch_attempted"] is True
    assert receipt["dispatch_status"] == "failed"
    assert "code 2" in receipt["error"]


def test_dispatch_spawn_mode_marks_dispatched_when_process_alive(monkeypatch, tmp_path: Path) -> None:
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("prompt text", encoding="utf-8")

    class _Stdin:
        def write(self, _text: str) -> None:
            return None

        def close(self) -> None:
            return None

    class _P:
        pid = 12345
        stdin = _Stdin()
        stderr = None

        def poll(self):
            return None

    def _mock_popen(*args, **kwargs):
        return _P()

    monkeypatch.setattr(subprocess, "Popen", _mock_popen)
    receipt = build_dispatch_receipt(_dispatch_ready_ok(), prompt_path, "codex.cmd", dispatch_mode="spawn")
    assert receipt["dispatch_attempted"] is True
    assert receipt["dispatch_status"] == "dispatched"
