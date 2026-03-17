"""Local Codex dispatch runner for semi-manual bridge.

This tool attempts local dispatch only.
It does not orchestrate external systems and does not use MCP runtime integration.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DISPATCH_READY_PATH = Path("artifacts") / "council_codex_dispatch_ready.json"
PROMPT_PATH = Path("artifacts") / "council_codex_prompt.txt"
RECEIPT_PATH = Path("artifacts") / "council_codex_dispatch_receipt.json"
STDOUT_LOG_PATH = Path("artifacts") / "council_codex_dispatch_stdout.log"
STDERR_LOG_PATH = Path("artifacts") / "council_codex_dispatch_stderr.log"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _blocking_receipt(
    request_id: Any,
    brief_id: Any,
    handoff_id: Any,
    prompt_artifact_path: str,
    reason: str,
    started_at: str,
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "brief_id": brief_id,
        "handoff_id": handoff_id,
        "dispatch_attempted": False,
        "dispatch_status": "blocked",
        "prompt_artifact_path": prompt_artifact_path,
        "started_at": started_at,
        "blocking_reason": reason,
        "notes": "Dispatch not attempted because readiness gates failed.",
    }


def _parse_args_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def build_dispatch_receipt(
    dispatch_ready_artifact: dict[str, Any],
    prompt_path: Path,
    codex_command: str,
    codex_args: list[str] | None = None,
    dispatch_mode: str = "spawn",
    stdout_log_path: Path | None = None,
    stderr_log_path: Path | None = None,
    timeout_sec: int = 120,
) -> dict[str, Any]:
    started_at = _now_iso()
    request_id = dispatch_ready_artifact.get("request_id")
    brief_id = dispatch_ready_artifact.get("brief_id")
    handoff_id = dispatch_ready_artifact.get("handoff_id")
    prompt_artifact_path = dispatch_ready_artifact.get("prompt_artifact_path") or prompt_path.as_posix()

    if dispatch_ready_artifact.get("dispatch_ready") is not True:
        reason = dispatch_ready_artifact.get("blocking_reason") or "dispatch_ready is not true."
        return _blocking_receipt(request_id, brief_id, handoff_id, prompt_artifact_path, reason, started_at)

    if not (_non_empty(request_id) and _non_empty(brief_id) and _non_empty(handoff_id)):
        return _blocking_receipt(
            request_id, brief_id, handoff_id, prompt_artifact_path, "missing identity fields in dispatch-ready artifact.", started_at
        )

    gate_results = dispatch_ready_artifact.get("gate_results")
    if isinstance(gate_results, list):
        failed = [g for g in gate_results if isinstance(g, dict) and g.get("passed") is not True]
        if failed:
            reason = "dispatch-ready gate_results contains failed gates."
            return _blocking_receipt(request_id, brief_id, handoff_id, prompt_artifact_path, reason, started_at)

    if not prompt_path.exists():
        return _blocking_receipt(request_id, brief_id, handoff_id, prompt_artifact_path, "prompt file not found.", started_at)
    prompt_text = prompt_path.read_text(encoding="utf-8")
    if not prompt_text.strip():
        return _blocking_receipt(request_id, brief_id, handoff_id, prompt_artifact_path, "prompt file is empty.", started_at)

    # Use non-interactive exec mode to avoid TTY requirement in plain `codex`.
    args = [codex_command, "exec", "-"] + (codex_args or [])

    out_log = stdout_log_path or STDOUT_LOG_PATH
    err_log = stderr_log_path or STDERR_LOG_PATH

    if dispatch_mode == "spawn":
        try:
            out_log.parent.mkdir(parents=True, exist_ok=True)
            err_log.parent.mkdir(parents=True, exist_ok=True)
            stdout_f = out_log.open("a", encoding="utf-8")
            stderr_f = err_log.open("a", encoding="utf-8")
            proc = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=stdout_f,
                stderr=stderr_f,
                text=True,
            )
            assert proc.stdin is not None
            proc.stdin.write(prompt_text)
            proc.stdin.close()
            time.sleep(1.0)
            code = proc.poll()
            stdout_f.close()
            stderr_f.close()
            if code is None:
                return {
                    "request_id": request_id,
                    "brief_id": brief_id,
                    "handoff_id": handoff_id,
                    "dispatch_attempted": True,
                    "dispatch_status": "dispatched",
                    "prompt_artifact_path": prompt_artifact_path,
                    "started_at": started_at,
                    "dispatch_process": {
                        "pid": proc.pid,
                        "mode": "spawn",
                        "state": "running",
                    },
                    "dispatch_log_paths": {
                        "stdout": out_log.as_posix(),
                        "stderr": err_log.as_posix(),
                    },
                    "notes": f"Local Codex process started (pid={proc.pid}) via non-interactive exec mode.",
                }

            stderr = ""
            if err_log.exists():
                stderr = err_log.read_text(encoding="utf-8", errors="ignore").strip()[-500:]
            return {
                "request_id": request_id,
                "brief_id": brief_id,
                "handoff_id": handoff_id,
                "dispatch_attempted": True,
                "dispatch_status": "failed",
                "prompt_artifact_path": prompt_artifact_path,
                "started_at": started_at,
                "dispatch_process": {
                    "pid": proc.pid,
                    "mode": "spawn",
                    "state": "exited_early",
                    "return_code": code,
                },
                "dispatch_log_paths": {
                    "stdout": out_log.as_posix(),
                    "stderr": err_log.as_posix(),
                },
                "error": f"codex process exited early with code {code}",
                "notes": stderr[:500] if stderr else "Process exited before dispatch confirmation.",
            }
        except Exception as exc:
            return {
                "request_id": request_id,
                "brief_id": brief_id,
                "handoff_id": handoff_id,
                "dispatch_attempted": True,
                "dispatch_status": "failed",
                "prompt_artifact_path": prompt_artifact_path,
                "started_at": started_at,
                "error": str(exc),
                "notes": "Dispatch process failed to start.",
            }

    if dispatch_mode == "run":
        try:
            proc = subprocess.run(
                args,
                input=prompt_text,
                text=True,
                capture_output=True,
                timeout=timeout_sec,
            )
            if proc.returncode == 0:
                return {
                    "request_id": request_id,
                    "brief_id": brief_id,
                    "handoff_id": handoff_id,
                    "dispatch_attempted": True,
                    "dispatch_status": "dispatched",
                    "prompt_artifact_path": prompt_artifact_path,
                    "started_at": started_at,
                    "dispatch_process": {
                        "mode": "run",
                        "state": "completed",
                        "return_code": 0,
                    },
                    "notes": "Local Codex dispatch command completed via run mode.",
                }
            return {
                "request_id": request_id,
                "brief_id": brief_id,
                "handoff_id": handoff_id,
                "dispatch_attempted": True,
                "dispatch_status": "failed",
                "prompt_artifact_path": prompt_artifact_path,
                "started_at": started_at,
                "dispatch_process": {
                    "mode": "run",
                    "state": "completed",
                    "return_code": proc.returncode,
                },
                "error": f"codex command exited with code {proc.returncode}",
                "notes": (proc.stderr or proc.stdout or "").strip()[:500],
            }
        except subprocess.TimeoutExpired:
            return {
                "request_id": request_id,
                "brief_id": brief_id,
                "handoff_id": handoff_id,
                "dispatch_attempted": True,
                "dispatch_status": "failed",
                "prompt_artifact_path": prompt_artifact_path,
                "started_at": started_at,
                "error": f"codex dispatch timed out after {timeout_sec}s",
                "notes": "Dispatch command timed out in run mode.",
            }
        except Exception as exc:
            return {
                "request_id": request_id,
                "brief_id": brief_id,
                "handoff_id": handoff_id,
                "dispatch_attempted": True,
                "dispatch_status": "failed",
                "prompt_artifact_path": prompt_artifact_path,
                "started_at": started_at,
                "error": str(exc),
                "notes": "Dispatch command failed with runtime error in run mode.",
            }

    raise ValueError("dispatch_mode must be 'spawn' or 'run'.")


def run_dispatch(
    dispatch_ready_path: str,
    prompt_path: str,
    output_path: str,
    codex_command: str,
    codex_args: list[str] | None = None,
    dispatch_mode: str = "spawn",
    stdout_log_path: str | None = None,
    stderr_log_path: str | None = None,
    timeout_sec: int = 120,
) -> dict[str, Any]:
    artifact = _load_json(Path(dispatch_ready_path))
    receipt = build_dispatch_receipt(
        dispatch_ready_artifact=artifact,
        prompt_path=Path(prompt_path),
        codex_command=codex_command,
        codex_args=codex_args,
        dispatch_mode=dispatch_mode,
        stdout_log_path=Path(stdout_log_path) if stdout_log_path else None,
        stderr_log_path=Path(stderr_log_path) if stderr_log_path else None,
        timeout_sec=timeout_sec,
    )
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local Codex dispatch from dispatch-ready artifact.")
    parser.add_argument("--dispatch-ready", default=str(DISPATCH_READY_PATH), help="Path to dispatch-ready artifact JSON.")
    parser.add_argument("--prompt", default=str(PROMPT_PATH), help="Path to prompt artifact text.")
    parser.add_argument("--output", default=str(RECEIPT_PATH), help="Path to dispatch receipt JSON.")
    parser.add_argument("--codex-command", default="codex.cmd", help="Local Codex command.")
    parser.add_argument(
        "--codex-args",
        default="",
        help="Optional comma-separated extra args appended after `codex exec -`.",
    )
    parser.add_argument(
        "--dispatch-mode",
        default="spawn",
        choices=["spawn", "run"],
        help="spawn: start Codex process and return quickly; run: wait for command completion.",
    )
    parser.add_argument("--timeout-sec", type=int, default=120, help="Dispatch command timeout in seconds.")
    parser.add_argument("--stdout-log", default=str(STDOUT_LOG_PATH), help="Path for dispatch stdout log.")
    parser.add_argument("--stderr-log", default=str(STDERR_LOG_PATH), help="Path for dispatch stderr log.")
    args = parser.parse_args()

    receipt = run_dispatch(
        dispatch_ready_path=args.dispatch_ready,
        prompt_path=args.prompt,
        output_path=args.output,
        codex_command=args.codex_command,
        codex_args=_parse_args_list(args.codex_args),
        dispatch_mode=args.dispatch_mode,
        stdout_log_path=args.stdout_log,
        stderr_log_path=args.stderr_log,
        timeout_sec=args.timeout_sec,
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    print(f"\n[codex-dispatch-runner] saved: {args.output}")

    if receipt.get("dispatch_status") != "dispatched":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
