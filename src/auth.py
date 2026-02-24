"""Shared token helper — client credentials flow for Microsoft Graph."""

from __future__ import annotations

import time
from typing import Any

import httpx

from src.config import GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET

_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}


def get_graph_token() -> str:
    """Acquire a Graph API token using client credentials, with in-memory cache."""
    if _token_cache["access_token"] and time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]

    if not all([GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET]):
        raise RuntimeError(
            "GRAPH_TENANT_ID, GRAPH_CLIENT_ID, and GRAPH_CLIENT_SECRET must be set "
            "in .env when USE_MOCK_DATA=false"
        )

    url = f"https://login.microsoftonline.com/{GRAPH_TENANT_ID}/oauth2/v2.0/token"
    resp = httpx.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": GRAPH_CLIENT_ID,
            "client_secret": GRAPH_CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    _token_cache["access_token"] = body["access_token"]
    _token_cache["expires_at"] = time.time() + body.get("expires_in", 3600)
    return _token_cache["access_token"]
