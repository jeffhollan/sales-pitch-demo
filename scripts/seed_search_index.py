#!/usr/bin/env python3
"""One-time script: create the Azure AI Search index and upload sales-play documents.

Usage:
    python -m scripts.seed_search_index

Requires AZURE_SEARCH_ENDPOINT and an *admin* key (not query key) in env vars:
    AZURE_SEARCH_ENDPOINT=https://sales-pres-demo-search.search.windows.net
    AZURE_SEARCH_ADMIN_KEY=<admin-key>
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load env from project root
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
ADMIN_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX", "sales-enablement")
API_VERSION = "2024-07-01"
MOCK_DATA = _ROOT / "src" / "mock_data" / "foundry_iq_data.json"

HEADERS = {
    "Content-Type": "application/json",
    "api-key": ADMIN_KEY or "",
}


# ── Index schema ─────────────────────────────────────────────────────────
INDEX_SCHEMA = {
    "name": INDEX_NAME,
    "fields": [
        {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
        {"name": "customer_key", "type": "Edm.String", "filterable": True},
        {"name": "customer_name", "type": "Edm.String", "searchable": True},
        {"name": "industry", "type": "Edm.String", "searchable": True},
        {"name": "play_name", "type": "Edm.String", "searchable": True},
        {"name": "relevance_score", "type": "Edm.Double", "sortable": True, "filterable": True},
        {"name": "summary", "type": "Edm.String", "searchable": True},
        {
            "name": "key_talking_points",
            "type": "Collection(Edm.String)",
            "searchable": True,
        },
        {"name": "customer_references", "type": "Edm.String"},  # JSON string
        {"name": "resources", "type": "Edm.String"},  # JSON string
        {
            "name": "competitors",
            "type": "Collection(Edm.String)",
            "filterable": True,
            "searchable": True,
        },
        {
            "name": "microsoft_strengths",
            "type": "Collection(Edm.String)",
            "searchable": True,
        },
        {
            "name": "competitive_risks",
            "type": "Collection(Edm.String)",
            "searchable": True,
        },
    ],
}


def _url(path: str) -> str:
    return f"{ENDPOINT}{path}?api-version={API_VERSION}"


def create_index() -> None:
    """Create (or update) the search index."""
    url = _url(f"/indexes/{INDEX_NAME}")
    # Use PUT to create-or-update
    resp = httpx.put(url, headers=HEADERS, json=INDEX_SCHEMA, timeout=30)
    if resp.status_code in (200, 201, 204):
        print(f"Index '{INDEX_NAME}' created/updated.")
    else:
        print(f"Failed to create index: {resp.status_code} {resp.text}")
        sys.exit(1)


def build_documents() -> list[dict]:
    """Read mock data and produce denormalized search documents."""
    with open(MOCK_DATA) as f:
        raw = json.load(f)

    docs: list[dict] = []
    for customer_key, entry in raw.items():
        ci = entry.get("competitive_intelligence", {})
        competitors = ci.get("primary_competitors_in_account", [])
        strengths = ci.get("microsoft_strengths", [])
        risks = ci.get("risks", [])

        for idx, play in enumerate(entry.get("sales_plays", [])):
            doc = {
                "@search.action": "mergeOrUpload",
                "id": f"{customer_key}-{idx}",
                "customer_key": customer_key,
                "customer_name": entry["customer_name"],
                "industry": entry["industry"],
                "play_name": play["play_name"],
                "relevance_score": play["relevance_score"],
                "summary": play["summary"],
                "key_talking_points": play.get("key_talking_points", []),
                "customer_references": json.dumps(play.get("customer_references", [])),
                "resources": json.dumps(play.get("resources", [])),
                "competitors": competitors,
                "microsoft_strengths": strengths,
                "competitive_risks": risks,
            }
            docs.append(doc)

    return docs


def upload_documents(docs: list[dict]) -> None:
    """Upload documents to the search index."""
    url = _url(f"/indexes/{INDEX_NAME}/docs/index")
    resp = httpx.post(url, headers=HEADERS, json={"value": docs}, timeout=30)
    if resp.status_code in (200, 207):
        results = resp.json().get("value", [])
        ok = sum(1 for r in results if r.get("statusCode") in (200, 201))
        failed = [r for r in results if r.get("statusCode") not in (200, 201)]
        print(f"Uploaded {ok}/{len(docs)} documents.")
        for f in failed:
            print(f"  Failed doc '{f.get('key')}': {f.get('statusCode')} {f.get('errorMessage')}")
    else:
        print(f"Failed to upload documents: {resp.status_code} {resp.text}")
        sys.exit(1)


def main() -> None:
    if not ENDPOINT or not ADMIN_KEY:
        print("Error: AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_ADMIN_KEY must be set.")
        sys.exit(1)

    create_index()
    docs = build_documents()
    upload_documents(docs)
    print("Done — index seeded successfully.")


if __name__ == "__main__":
    main()
