"""Foundry IQ tool — sales plays and enablement materials from knowledge base.

In mock mode, returns data from mock_data/foundry_iq_data.json.
In live mode, delegates to Azure AI Search MCP endpoint.
"""

from __future__ import annotations

import json
from typing import Any

from src.config import MOCK_DATA_DIR, USE_MOCK_DATA

_MOCK_FILE = MOCK_DATA_DIR / "foundry_iq_data.json"


def _normalize_key(customer_name: str) -> str:
    return customer_name.lower().replace("the ", "").replace(" company", "").replace(" ", "-").strip()


def _load_mock() -> dict[str, Any]:
    with open(_MOCK_FILE) as f:
        return json.load(f)


def get_foundry_iq_data(customer_name: str) -> dict[str, Any]:
    """Retrieve Foundry IQ data (sales plays, competitive intel, references) for a customer.

    Returns a dict with keys: customer_name, industry, sales_plays,
    competitive_intelligence.
    """
    if USE_MOCK_DATA:
        data = _load_mock()
        key = _normalize_key(customer_name)
        if key in data:
            return data[key]
        for k, v in data.items():
            if k in key or key in k:
                return v
        return {"error": f"No Foundry IQ mock data found for '{customer_name}'"}

    return {"error": "Live Foundry IQ requires MCP server configuration. Set USE_MOCK_DATA=true for demo."}
