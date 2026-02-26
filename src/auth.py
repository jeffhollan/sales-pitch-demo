"""Shared token helpers for Microsoft Graph.

Supports two auth modes (auto-detected from env vars):
1. Agent ID app-only — two-step client_credentials via Entra Agent Identity Blueprint
2. Legacy — single-step client_credentials (existing app registration)

When Agent ID is configured:
- Mail.Read uses the Agent ID app-only token.
- Calendars.Read uses a cached delegated agent token (acquired via
  scripts/auth_server.py). Falls back to legacy if no token is cached.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from src.config import (
    AUTH_REDIRECT_BASE_URL,
    GRAPH_AGENT_CLIENT_ID,
    GRAPH_BLUEPRINT_CLIENT_ID,
    GRAPH_BLUEPRINT_SECRET,
    GRAPH_CLIENT_ID,
    GRAPH_CLIENT_SECRET,
    GRAPH_TENANT_ID,
    TOKEN_STORAGE_URL,
)


class DelegatedAuthRequired(Exception):
    """Raised when delegated auth is needed and no valid token exists."""

    def __init__(self, auth_url: str):
        self.auth_url = auth_url
        super().__init__(f"Delegated auth required. Visit: {auth_url}")

_TOKEN_URL = f"https://login.microsoftonline.com/{GRAPH_TENANT_ID}/oauth2/v2.0/token"

# ── In-memory caches ─────────────────────────────────────────────────
_agent_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}
_legacy_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}
_delegated_token_cache: dict[str, Any] = {"access_token": None, "refresh_token": None, "expires_at": 0.0}
_DELEGATED_TOKEN_CACHE_PATH = Path.home() / ".sales-prep-demo-token.json"


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

    When Agent ID is configured, uses a cached delegated agent token
    obtained via the interactive OBO flow (scripts/auth_server.py).
    Falls back to the legacy app registration if no delegated token
    is available.
    """
    if not _use_agent_id():
        return _get_legacy_token()

    _load_delegated_cache()

    # Return cached token if still valid
    if _delegated_token_cache["access_token"] and time.time() < _delegated_token_cache["expires_at"] - 60:
        return _delegated_token_cache["access_token"]

    # Try refresh via OBO with cached refresh token
    if _refresh_delegated_token():
        return _delegated_token_cache["access_token"]

    # No valid token — raise so callers can surface the auth URL
    raise DelegatedAuthRequired(f"{AUTH_REDIRECT_BASE_URL}/login")


# ── Delegated token cache helpers ────────────────────────────────────

def _load_from_blob() -> None:
    """Load delegated token from Azure Blob Storage."""
    try:
        from azure.storage.blob import BlobClient

        blob_client = BlobClient.from_blob_url(TOKEN_STORAGE_URL)
        blob_data = blob_client.download_blob().readall()
        data = json.loads(blob_data)
        _delegated_token_cache["access_token"] = data.get("access_token")
        _delegated_token_cache["refresh_token"] = data.get("refresh_token")
        _delegated_token_cache["expires_at"] = data.get("expires_at", 0.0)
        expired = time.time() >= _delegated_token_cache["expires_at"] - 60
        has_refresh = bool(_delegated_token_cache["refresh_token"])
        print(f"[Auth] Loaded token from blob (expired={expired}, has_refresh={has_refresh})", flush=True)
    except Exception as exc:
        print(f"[Auth] Failed to load token from blob: {exc}", flush=True)


def _load_from_file() -> None:
    """Load delegated token from the local file cache."""
    try:
        data = json.loads(_DELEGATED_TOKEN_CACHE_PATH.read_text())
        _delegated_token_cache["access_token"] = data.get("access_token")
        _delegated_token_cache["refresh_token"] = data.get("refresh_token")
        _delegated_token_cache["expires_at"] = data.get("expires_at", 0.0)
    except (json.JSONDecodeError, OSError):
        pass


def _load_delegated_cache() -> None:
    """Load delegated token into the in-memory cache.

    Reads from Azure Blob Storage when TOKEN_STORAGE_URL is set,
    otherwise falls back to the local file.  Always reloads if the
    current token is expired (so a freshly-saved token from the
    OAuth callback is picked up).
    """
    # Only skip reload if the cached token is still valid
    if (_delegated_token_cache["access_token"]
            and time.time() < _delegated_token_cache["expires_at"] - 60):
        return

    if TOKEN_STORAGE_URL:
        _load_from_blob()
    elif _DELEGATED_TOKEN_CACHE_PATH.exists():
        _load_from_file()


def _save_delegated_cache() -> None:
    """Persist the in-memory delegated token cache.

    Writes to Azure Blob Storage when TOKEN_STORAGE_URL is set,
    otherwise writes to the local file.
    """
    payload = json.dumps({
        "access_token": _delegated_token_cache["access_token"],
        "refresh_token": _delegated_token_cache["refresh_token"],
        "expires_at": _delegated_token_cache["expires_at"],
    }, indent=2)

    if TOKEN_STORAGE_URL:
        try:
            from azure.storage.blob import BlobClient, ContentSettings

            blob_client = BlobClient.from_blob_url(TOKEN_STORAGE_URL)
            blob_client.upload_blob(
                payload,
                overwrite=True,
                content_settings=ContentSettings(content_type="application/json"),
            )
        except Exception:
            pass  # best-effort
    else:
        _DELEGATED_TOKEN_CACHE_PATH.write_text(payload)


def clear_delegated_cache() -> None:
    """Reset the in-memory delegated token cache so the next call reloads from disk."""
    _delegated_token_cache["access_token"] = None
    _delegated_token_cache["refresh_token"] = None
    _delegated_token_cache["expires_at"] = 0.0


def _refresh_delegated_token() -> bool:
    """Attempt to refresh the delegated token using the cached refresh token.

    Uses the OBO flow: bootstrap token (T1) as client_assertion, refresh
    token as the grant.  Returns True on success.
    """
    refresh_token = _delegated_token_cache.get("refresh_token")
    if not refresh_token:
        return False

    try:
        # Get bootstrap token (T1)
        resp1 = httpx.post(_TOKEN_URL, data={
            "grant_type": "client_credentials",
            "client_id": GRAPH_BLUEPRINT_CLIENT_ID,
            "client_secret": GRAPH_BLUEPRINT_SECRET,
            "scope": "api://AzureADTokenExchange/.default",
            "fmi_path": GRAPH_AGENT_CLIENT_ID,
        }, timeout=15)
        resp1.raise_for_status()
        t1 = resp1.json()["access_token"]

        # Refresh using T1 as client_assertion
        resp2 = httpx.post(_TOKEN_URL, data={
            "grant_type": "refresh_token",
            "client_id": GRAPH_AGENT_CLIENT_ID,
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": t1,
            "refresh_token": refresh_token,
            "scope": "https://graph.microsoft.com/Calendars.Read offline_access",
        }, timeout=15)

        if resp2.status_code >= 400:
            # Try simpler refresh with blueprint credentials
            resp2 = httpx.post(_TOKEN_URL, data={
                "grant_type": "refresh_token",
                "client_id": GRAPH_BLUEPRINT_CLIENT_ID,
                "client_secret": GRAPH_BLUEPRINT_SECRET,
                "refresh_token": refresh_token,
                "scope": "https://graph.microsoft.com/Calendars.Read offline_access",
            }, timeout=15)
            if resp2.status_code >= 400:
                return False

        body = resp2.json()
        _delegated_token_cache["access_token"] = body["access_token"]
        _delegated_token_cache["refresh_token"] = body.get("refresh_token", refresh_token)
        _delegated_token_cache["expires_at"] = time.time() + body.get("expires_in", 3600)
        _save_delegated_cache()
        return True
    except (httpx.HTTPError, KeyError):
        return False
