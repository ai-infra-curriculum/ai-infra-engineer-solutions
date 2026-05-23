"""Slack webhook integration."""
from __future__ import annotations

import requests


def post(webhook_url: str, markdown: str) -> None:
    payload = {"text": markdown, "mrkdwn": True}
    r = requests.post(webhook_url, json=payload, timeout=10)
    r.raise_for_status()
