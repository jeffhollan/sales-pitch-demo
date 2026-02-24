"""Shared token helpers for Microsoft Graph.

Supports two auth modes (auto-detected from env vars):
1. Agent ID app-only — two-step client_credentials via Entra Agent Identity Blueprint
2. Legacy — single-step client_credentials (existing app registration)

When Agent ID is configured, Mail.Read uses the Agent ID token.
Calendars.Read is blocked for agent identities in application mode, so
calendar access always uses the legacy app registration token.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from src.config import (
    GRAPH_AGENT_CLIENT_ID,
    GRAPH_BLUEPRINT_CLIENT_ID,
    GRAPH_BLUEPRINT_SECRET,
    GRAPH_CLIENT_ID,
    GRAPH_CLIENT_SECRET,
    GRAPH_TENANT_ID,
)

_TOKEN_URL = f"https://login.microsoftonline.com/{GRAPH_TENANT_ID}/oauth2/v2.0/token"

# ── In-memory caches ─────────────────────────────────────────────────
_agent_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}
_legacy_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}


def _use_agent_id() -> bool:
    """Return True when Agent ID env vars are configured."""
    return bool(GRAPH_BLUEPRINT_CLIENT_ID and GRAPH_BLUEPRINT_SECRET and GRAPH_AGENT_CLIENT_ID)


# ── Legacy app-only token ────────────────────────────────────────────

def _acquire_legacy_token() -> dict[str, Any]:
    """Single-step client_credentials with the old app registration."""
    resp = httpx.post(
        _TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": GRAPH_CLIENT_ID,
            "client_secret": GRAPH_CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _get_legacy_token() -> str:
    """Acquire legacy app-only token with in-memory cache."""
    if _legacy_token_cache["access_token"] and time.time() < _legacy_token_cache["expires_at"] - 60:
        return _legacy_token_cache["access_token"]

    if not (GRAPH_CLIENT_ID and GRAPH_CLIENT_SECRET):
        raise RuntimeError(
            "Legacy Graph auth not configured. Set GRAPH_CLIENT_ID and "
            "GRAPH_CLIENT_SECRET in .env"
        )

    body = _acquire_legacy_token()
    _legacy_token_cache["access_token"] = body["access_token"]
    _legacy_token_cache["expires_at"] = time.time() + body.get("expires_in", 3600)
    return _legacy_token_cache["access_token"]


# ── Agent ID app-only token ──────────────────────────────────────────

def _acquire_agent_app_token() -> dict[str, Any]:
    """Two-step Agent ID client_credentials flow.

    Step 1: Blueprint credentials → bootstrap token (T1)
    Step 2: T1 as client_assertion → Graph app-only token
    """
    # Step 1 — get bootstrap token
    resp1 = httpx.post(
        _TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": GRAPH_BLUEPRINT_CLIENT_ID,
            "client_secret": GRAPH_BLUEPRINT_SECRET,
            "scope": "api://AzureADTokenExchange/.default",
            "fmi_path": GRAPH_AGENT_CLIENT_ID,
        },
        timeout=15,
    )
    resp1.raise_for_status()
    t1 = resp1.json()["access_token"]

    # Step 2 — exchange for Graph token
    resp2 = httpx.post(
        _TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": GRAPH_AGENT_CLIENT_ID,
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": t1,
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=15,
    )
    resp2.raise_for_status()
    return resp2.json()


# ── Public API ────────────────────────────────────────────────────────

def get_graph_token() -> str:
    """Acquire a Graph API app-only token for Mail.Read.

    Uses Agent ID two-step flow when configured, otherwise legacy.
    """
    if _use_agent_id():
        if _agent_token_cache["access_token"] and time.time() < _agent_token_cache["expires_at"] - 60:
            return _agent_token_cache["access_token"]
        body = _acquire_agent_app_token()
        _agent_token_cache["access_token"] = body["access_token"]
        _agent_token_cache["expires_at"] = time.time() + body.get("expires_in", 3600)
        return _agent_token_cache["access_token"]

    return _get_legacy_token()


def get_graph_delegated_token() -> str:
    """Acquire a Graph token for Calendars.Read.

    Calendars.Read is blocked for agent identities in application mode,
    so this always uses the legacy app registration token (which has
    Calendars.Read as an app permission on a regular app registration).
    """
    return _get_legacy_token()
