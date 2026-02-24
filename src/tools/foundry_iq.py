"""Foundry IQ tool — sales plays and enablement materials from knowledge base.

In mock mode, returns data from mock_data/foundry_iq_data.json.
In live mode, queries Azure AI Search REST API.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from src.config import (
    AZURE_SEARCH_ENDPOINT,
    AZURE_SEARCH_INDEX,
    AZURE_SEARCH_KEY,
    MOCK_DATA_DIR,
    USE_MOCK_DATA,
)

_MOCK_FILE = MOCK_DATA_DIR / "foundry_iq_data.json"


def _normalize_key(customer_name: str) -> str:
    return customer_name.lower().replace("the ", "").replace(" company", "").replace(" ", "-").strip()


def _load_mock() -> dict[str, Any]:
    with open(_MOCK_FILE) as f:
        return json.load(f)


def _query_search(customer_name: str) -> dict[str, Any]:
    """Query Azure AI Search for sales plays matching a customer."""
    if not AZURE_SEARCH_ENDPOINT or not AZURE_SEARCH_KEY:
        raise RuntimeError(
            "AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_KEY must be set when USE_MOCK_DATA=false"
        )

    url = f"{AZURE_SEARCH_ENDPOINT}/indexes/{AZURE_SEARCH_INDEX}/docs/search?api-version=2024-07-01"
    customer_key = _normalize_key(customer_name)

    resp = httpx.post(
        url,
        headers={
            "Content-Type": "application/json",
            "api-key": AZURE_SEARCH_KEY,
        },
        json={
            "filter": f"customer_key eq '{customer_key}'",
            "top": 10,
        },
        timeout=30,
    )
    resp.raise_for_status()
    results = resp.json().get("value", [])

    if not results:
        return {"error": f"No Foundry IQ data found for '{customer_name}' in Azure Search"}

    # Reassemble the grouped structure from denormalized search documents.
    first = results[0]
    sales_plays = []
    all_competitors: list[str] = []
    all_strengths: list[str] = []
    all_risks: list[str] = []

    for doc in results:
        play: dict[str, Any] = {
            "play_name": doc["play_name"],
            "relevance_score": doc["relevance_score"],
            "summary": doc["summary"],
            "key_talking_points": doc.get("key_talking_points", []),
            "customer_references": json.loads(doc.get("customer_references", "[]")),
            "resources": json.loads(doc.get("resources", "[]")),
        }
        sales_plays.append(play)
        all_competitors.extend(doc.get("competitors", []))
        all_strengths.extend(doc.get("microsoft_strengths", []))
        all_risks.extend(doc.get("competitive_risks", []))

    # Deduplicate while preserving order.
    def _dedup(seq: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in seq:
            if item not in seen:
                seen.add(item)
                out.append(item)
        return out

    return {
        "customer_name": first["customer_name"],
        "industry": first["industry"],
        "sales_plays": sales_plays,
        "competitive_intelligence": {
            "primary_competitors_in_account": _dedup(all_competitors),
            "microsoft_strengths": _dedup(all_strengths),
            "risks": _dedup(all_risks),
        },
    }


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

    return _query_search(customer_name)
