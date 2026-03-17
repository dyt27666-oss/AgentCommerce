"""Compatibility wrapper: feishu_action_listener -> feishu_action_reconciler.

Primary low-latency path is now webhook:
- tools/council_bridge/feishu_event_webhook.py

This module remains as fallback polling scanner entrypoint for compatibility.
"""

from __future__ import annotations

from tools.council_bridge.feishu_action_reconciler import *  # noqa: F401,F403


if __name__ == "__main__":
    from tools.council_bridge.feishu_action_reconciler import main

    main()

