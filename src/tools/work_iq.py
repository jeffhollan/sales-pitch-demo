"""Work IQ tool — relationship context from Microsoft Graph (email, Teams, calendar).

In mock mode, returns data from mock_data/work_iq_data.json.
In live mode, queries Microsoft Graph API directly using client credentials.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from src.auth import get_graph_delegated_token, get_graph_token
from src.config import GRAPH_USER_ID, MOCK_DATA_DIR, USE_MOCK_DATA

_MOCK_FILE = MOCK_DATA_DIR / "work_iq_data.json"

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _normalize_key(customer_name: str) -> str:
    """Normalize customer name to a lookup key."""
    return customer_name.lower().replace("the ", "").replace(" company", "").replace(" ", "-").strip()


def _load_mock() -> dict[str, Any]:
    with open(_MOCK_FILE) as f:
        return json.load(f)


def _graph_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_graph_token()}",
        "ConsistencyLevel": "eventual",
    }


def _fetch_messages(customer_name: str) -> list[dict[str, Any]]:
    """Fetch recent emails mentioning the customer from Graph."""
    if not GRAPH_USER_ID:
        raise RuntimeError("GRAPH_USER_ID must be set when USE_MOCK_DATA=false")

    url = f"{_GRAPH_BASE}/users/{GRAPH_USER_ID}/messages"
    try:
        resp = httpx.get(
            url,
            headers=_graph_headers(),
            params={
                "$search": f'"{customer_name}"',
                "$top": "10",
                "$select": "receivedDateTime,from,subject,bodyPreview",
            },
            timeout=15,
        )
        resp.raise_for_status()
    except (httpx.HTTPStatusError, RuntimeError):
        # Token not yet valid (e.g. Exchange replication delay) — return empty
        return []
    items = resp.json().get("value", [])

    emails: list[dict[str, Any]] = []
    for msg in items:
        from_addr = msg.get("from", {}).get("emailAddress", {})
        emails.append({
            "date": (msg.get("receivedDateTime") or "")[:10],
            "from": from_addr.get("address", from_addr.get("name", "unknown")),
            "subject": msg.get("subject", ""),
            "snippet": (msg.get("bodyPreview") or "")[:200],
        })
    return emails


def _delegated_graph_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_graph_delegated_token()}",
        "ConsistencyLevel": "eventual",
    }


def _fetch_events(customer_name: str) -> list[dict[str, Any]]:
    """Fetch calendar events mentioning the customer from Graph.

    Uses the delegated token (Calendars.Read) since application-mode
    calendar access is blocked for Entra Agent Identities.
    """
    if not GRAPH_USER_ID:
        raise RuntimeError("GRAPH_USER_ID must be set when USE_MOCK_DATA=false")

    url = f"{_GRAPH_BASE}/users/{GRAPH_USER_ID}/events"
    try:
        resp = httpx.get(
            url,
            headers=_delegated_graph_headers(),
            params={
                "$filter": f"contains(subject,'{customer_name}')",
                "$top": "10",
                "$select": "start,subject,attendees,bodyPreview",
            },
            timeout=15,
        )
        resp.raise_for_status()
    except (httpx.HTTPStatusError, RuntimeError):
        # Delegated token not available or 403 — return empty calendar data
        return []
    items = resp.json().get("value", [])

    meetings: list[dict[str, Any]] = []
    for evt in items:
        attendees = [
            a.get("emailAddress", {}).get("name", "")
            for a in evt.get("attendees", [])
        ]
        meetings.append({
            "date": (evt.get("start", {}).get("dateTime") or "")[:10],
            "title": evt.get("subject", ""),
            "attendees": attendees,
            "notes": (evt.get("bodyPreview") or "")[:200],
        })
    return meetings


def _query_graph(customer_name: str) -> dict[str, Any]:
    """Build Work IQ data from Microsoft Graph API."""
    emails = _fetch_messages(customer_name)
    meetings = _fetch_events(customer_name)

    return {
        "customer_name": customer_name,
        "primary_contact": {},
        "account_team": {},
        "recent_emails": emails,
        "recent_meetings": meetings,
        "teams_messages": [],
        "relationship_summary": "",
    }


def get_work_iq_data(customer_name: str) -> dict[str, Any]:
    """Retrieve Work IQ data (email, Teams, calendar) for a customer.

    Returns a dict with keys: customer_name, primary_contact, account_team,
    recent_emails, recent_meetings, teams_messages, relationship_summary.
    """
    if USE_MOCK_DATA:
        data = _load_mock()
        key = _normalize_key(customer_name)
        if key in data:
            return data[key]
        # Fuzzy match: check if any key is contained in the query
        for k, v in data.items():
            if k in key or key in k:
                return v
        return {"error": f"No Work IQ mock data found for '{customer_name}'"}

    return _query_graph(customer_name)
