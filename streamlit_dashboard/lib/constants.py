from __future__ import annotations


OPEN_STATE_TYPES = ("triage", "backlog", "unstarted", "started")
DONE_STATE_TYPES = ("completed", "canceled")
HIGH_PRIORITY_LABELS = ("urgent", "high")

WORKFLOW_STATE_BUCKETS = {
    "backlog": ("backlog",),
    "todo": ("todo", "to do"),
    "in_process": ("in process", "in progress"),
    "review": ("review",),
    "done": ("done",),
}

WORKFLOW_STATE_LABELS = {
    "backlog": "Backlog",
    "todo": "Todo",
    "in_process": "In Process",
    "review": "Review",
    "done": "Done",
}

WORKFLOW_STATE_ORDER = [
    "Backlog",
    "Todo",
    "To Do",
    "In Process",
    "In Progress",
    "Review",
    "Done",
    "Canceled",
    "(blank)",
]
