from __future__ import annotations


OPEN_STATE_TYPES = ("triage", "backlog", "unstarted", "started")
DONE_STATE_TYPES = ("completed", "canceled")
HIGH_PRIORITY_LABELS = ("urgent", "high")

STATE_ORDER = ["triage", "backlog", "unstarted", "started", "completed", "canceled", "(blank)"]
