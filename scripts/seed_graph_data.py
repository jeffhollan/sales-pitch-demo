#!/usr/bin/env python3
"""One-time script: seed the M365 dev tenant mailbox with demo emails and calendar events.

Usage:
    python -m scripts.seed_graph_data

Requires GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, and GRAPH_USER_ID
in .env.  The app registration must have Mail.ReadWrite and Calendars.ReadWrite
application permissions with admin consent.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

TENANT_ID = os.getenv("GRAPH_TENANT_ID")
CLIENT_ID = os.getenv("GRAPH_CLIENT_ID")
CLIENT_SECRET = os.getenv("GRAPH_CLIENT_SECRET")
USER_ID = os.getenv("GRAPH_USER_ID")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _get_token() -> str:
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    resp = httpx.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ── Demo emails ──────────────────────────────────────────────────────────
EMAILS = [
    {
        "subject": "RE: Enterprise Agreement Renewal — Timeline",
        "body": {
            "contentType": "Text",
            "content": (
                "Marcus, we need to finalize the renewal terms by March 15. "
                "Our CFO wants to see a clear ROI summary before approving the "
                "expanded scope. Can we schedule a call next week?"
            ),
        },
        "from": {
            "emailAddress": {"name": "Sarah Chen", "address": "sarah.chen@coca-cola.com"}
        },
        "toRecipients": [
            {"emailAddress": {"name": "Demo User", "address": USER_ID or ""}}
        ],
        "receivedDateTime": (datetime.now(timezone.utc) - timedelta(days=4)).isoformat(),
    },
    {
        "subject": "Fabric Workspace Performance Concerns",
        "body": {
            "contentType": "Text",
            "content": (
                "Hi Priya, we've been experiencing latency issues in our supply chain "
                "analytics pipeline on Fabric. Query times have increased 3x over the "
                "past month. This is affecting our daily reporting."
            ),
        },
        "from": {
            "emailAddress": {"name": "David Park", "address": "david.park@coca-cola.com"}
        },
        "toRecipients": [
            {"emailAddress": {"name": "Demo User", "address": USER_ID or ""}}
        ],
        "receivedDateTime": (datetime.now(timezone.utc) - timedelta(days=6)).isoformat(),
    },
    {
        "subject": "AI Strategy Briefing Request",
        "body": {
            "contentType": "Text",
            "content": (
                "We're putting together our AI roadmap for the next fiscal year "
                "and would love to get Microsoft's perspective on Copilot and "
                "Foundry for our bottling operations."
            ),
        },
        "from": {
            "emailAddress": {"name": "Sarah Chen", "address": "sarah.chen@coca-cola.com"}
        },
        "toRecipients": [
            {"emailAddress": {"name": "Demo User", "address": USER_ID or ""}}
        ],
        "receivedDateTime": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
    },
]

# ── Demo calendar events ────────────────────────────────────────────────
now = datetime.now(timezone.utc)
EVENTS = [
    {
        "subject": "Coca-Cola QBR — Q4 Review",
        "body": {
            "contentType": "Text",
            "content": (
                "Reviewed Q4 usage metrics. Coca-Cola expressed strong interest "
                "in expanding Copilot from 5,000 to 15,000 seats. Fabric adoption "
                "growing in supply chain team. Action: send AI strategy proposal by Feb 28."
            ),
        },
        "start": {
            "dateTime": (now - timedelta(days=14)).strftime("%Y-%m-%dT10:00:00"),
            "timeZone": "UTC",
        },
        "end": {
            "dateTime": (now - timedelta(days=14)).strftime("%Y-%m-%dT11:00:00"),
            "timeZone": "UTC",
        },
        "attendees": [
            {"emailAddress": {"name": "Sarah Chen", "address": "sarah.chen@coca-cola.com"}, "type": "required"},
            {"emailAddress": {"name": "David Park", "address": "david.park@coca-cola.com"}, "type": "required"},
        ],
    },
    {
        "subject": "Technical Deep Dive — Fabric Performance",
        "body": {
            "contentType": "Text",
            "content": (
                "Investigated Fabric query latency. Root cause: unoptimized Delta Lake "
                "partitioning on supply chain datasets. Priya to provide optimization guide."
            ),
        },
        "start": {
            "dateTime": (now - timedelta(days=33)).strftime("%Y-%m-%dT14:00:00"),
            "timeZone": "UTC",
        },
        "end": {
            "dateTime": (now - timedelta(days=33)).strftime("%Y-%m-%dT15:00:00"),
            "timeZone": "UTC",
        },
        "attendees": [
            {"emailAddress": {"name": "David Park", "address": "david.park@coca-cola.com"}, "type": "required"},
        ],
    },
]


def seed_emails(token: str) -> None:
    """Create draft messages in the user's mailbox (visible as received mail)."""
    url = f"{GRAPH_BASE}/users/{USER_ID}/messages"
    for email in EMAILS:
        resp = httpx.post(url, headers=_headers(token), json=email, timeout=15)
        if resp.status_code in (200, 201):
            print(f"  Created email: {email['subject']}")
        else:
            print(f"  Failed ({resp.status_code}): {email['subject']} — {resp.text[:200]}")


def seed_events(token: str) -> None:
    """Create calendar events."""
    url = f"{GRAPH_BASE}/users/{USER_ID}/events"
    for event in EVENTS:
        resp = httpx.post(url, headers=_headers(token), json=event, timeout=15)
        if resp.status_code in (200, 201):
            print(f"  Created event: {event['subject']}")
        else:
            print(f"  Failed ({resp.status_code}): {event['subject']} — {resp.text[:200]}")


def main() -> None:
    if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET, USER_ID]):
        print(
            "Error: GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, "
            "and GRAPH_USER_ID must be set in .env"
        )
        sys.exit(1)

    print("Acquiring token…")
    token = _get_token()

    print("Seeding emails…")
    seed_emails(token)

    print("Seeding calendar events…")
    seed_events(token)

    print("Done.")


if __name__ == "__main__":
    main()
