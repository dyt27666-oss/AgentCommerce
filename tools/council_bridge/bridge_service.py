"""Bridge service skeleton: webhook ingress + worker + optional reconciler scheduler."""

from __future__ import annotations

import argparse
import threading
import time

from tools.council_bridge.bridge_worker import run_worker_once
from tools.council_bridge.feishu_action_reconciler import main as reconciler_main
from tools.council_bridge.feishu_event_webhook import run_server as run_webhook_server


def run_service(
    *,
    host: str,
    port: int,
    source_artifact: str,
    action_stage: str,
    check_completion_once: bool,
    build_receipt_skeleton: bool,
    verification_token: str,
    signing_secret: str,
    run_reconciler: bool,
    reconciler_interval_sec: int,
    worker_interval_sec: int,
) -> None:
    webhook_thread = threading.Thread(
        target=run_webhook_server,
        kwargs=dict(
            host=host,
            port=port,
            source_artifact=source_artifact,
            action_stage=action_stage,
            check_completion_once=check_completion_once,
            build_receipt_skeleton=build_receipt_skeleton,
            verification_token=verification_token,
            signing_secret=signing_secret,
            webhook_event_path="artifacts/council_feishu_webhook_event.json",
            dedupe_state_path="artifacts/council_feishu_message_dedupe_state.json",
            route_result_path="artifacts/council_feishu_message_route_result.json",
        ),
        daemon=True,
    )
    webhook_thread.start()

    def _worker_loop() -> None:
        while True:
            run_worker_once()
            time.sleep(max(1, worker_interval_sec))

    worker_thread = threading.Thread(target=_worker_loop, daemon=True)
    worker_thread.start()

    if run_reconciler:
        def _reconciler_loop() -> None:
            while True:
                # run one-shot reconciliation each interval
                import sys
                import os

                argv_backup = sys.argv
                try:
                    sys.argv = [
                        "feishu_action_reconciler.py",
                        "--max-polls",
                        "1",
                        "--source-artifact",
                        source_artifact,
                        "--action-stage",
                        action_stage,
                    ]
                    reconciler_main()
                finally:
                    sys.argv = argv_backup
                time.sleep(max(1, reconciler_interval_sec))

        threading.Thread(target=_reconciler_loop, daemon=True).start()

    print(
        "[bridge-service] started "
        f"| webhook=http://{host}:{port} "
        f"| worker_interval={worker_interval_sec}s "
        f"| reconciler={'on' if run_reconciler else 'off'}"
    )
    while True:
        time.sleep(3600)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bridge service skeleton (v1.2).")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--source-artifact", default="artifacts/council_codex_dispatch_ready.json")
    parser.add_argument("--action-stage", default="auto", choices=["auto", "dispatch_ready", "review_ready", "final_summary"])
    parser.add_argument("--check-completion-once", action="store_true")
    parser.add_argument("--build-receipt-skeleton", action="store_true")
    parser.add_argument("--verification-token", default="")
    parser.add_argument("--signing-secret", default="")
    parser.add_argument("--run-reconciler", action="store_true")
    parser.add_argument("--reconciler-interval-sec", type=int, default=60)
    parser.add_argument("--worker-interval-sec", type=int, default=2)
    args = parser.parse_args()

    run_service(
        host=args.host,
        port=args.port,
        source_artifact=args.source_artifact,
        action_stage=args.action_stage,
        check_completion_once=args.check_completion_once,
        build_receipt_skeleton=args.build_receipt_skeleton,
        verification_token=args.verification_token,
        signing_secret=args.signing_secret,
        run_reconciler=args.run_reconciler,
        reconciler_interval_sec=args.reconciler_interval_sec,
        worker_interval_sec=args.worker_interval_sec,
    )


if __name__ == "__main__":
    main()

