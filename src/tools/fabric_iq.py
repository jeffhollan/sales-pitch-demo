"""Fabric IQ tool — business metrics from Microsoft Fabric (spend, usage, tickets).

In mock mode, returns data from mock_data/fabric_iq_data.json.
In live mode, delegates to @microsoft/fabric-mcp.
"""

from __future__ import annotations

import json
from typing import Any

from src.config import MOCK_DATA_DIR, USE_MOCK_DATA

_MOCK_FILE = MOCK_DATA_DIR / "fabric_iq_data.json"


def _normalize_key(customer_name: str) -> str:
    return customer_name.lower().replace("the ", "").replace(" company", "").replace(" ", "-").strip()


def _load_mock() -> dict[str, Any]:
    with open(_MOCK_FILE) as f:
        return json.load(f)


def get_fabric_iq_data(customer_name: str) -> dict[str, Any]:
    """Retrieve Fabric IQ data (contract, usage, support tickets, expansion opps) for a customer.

    Returns a dict with keys: customer_name, contract, usage_trends,
    support_tickets, expansion_opportunities, financial_summary.
    """
    if USE_MOCK_DATA:
        data = _load_mock()
        key = _normalize_key(customer_name)
        if key in data:
            return data[key]
        for k, v in data.items():
            if k in key or key in k:
                return v
        return {"error": f"No Fabric IQ mock data found for '{customer_name}'"}

    # No free tier for Fabric — fall back to mock data with a warning.
    import warnings
    warnings.warn(
        "Fabric IQ has no free-tier live backend; falling back to mock data.",
        stacklevel=2,
    )
    data = _load_mock()
    key = _normalize_key(customer_name)
    if key in data:
        return data[key]
    for k, v in data.items():
        if k in key or key in k:
            return v
    return {"error": f"No Fabric IQ mock data found for '{customer_name}'"}
