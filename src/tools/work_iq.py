"""Work IQ tool — relationship context from Microsoft Graph (email, Teams, calendar).

In mock mode, returns data from mock_data/work_iq_data.json.
In live mode, delegates to the @microsoft/workiq MCP server.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import MOCK_DATA_DIR, USE_MOCK_DATA

_MOCK_FILE = MOCK_DATA_DIR / "work_iq_data.json"


def _normalize_key(customer_name: str) -> str:
    """Normalize customer name to a lookup key."""
    return customer_name.lower().replace("the ", "").replace(" company", "").replace(" ", "-").strip()


def _load_mock() -> dict[str, Any]:
    with open(_MOCK_FILE) as f:
        return json.load(f)


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

    # Live mode: MCP server handles this via GitHubCopilotAgent session config.
    # This function becomes a passthrough — the agent calls MCP tools directly.
    return {"error": "Live Work IQ requires MCP server configuration. Set USE_MOCK_DATA=true for demo."}
