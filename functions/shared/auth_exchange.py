"""Shared OAuth exchange logic for Azure Functions.

Extracted from scripts/auth_server.py so both the login and callback
functions can reuse the same token exchange logic.
"""

from __future__ import annotations

import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

TENANT_ID = os.getenv("GRAPH_TENANT_ID", "")
BLUEPRINT_CLIENT_ID = os.getenv("GRAPH_BLUEPRINT_CLIENT_ID", "")
BLUEPRINT_SECRET = os.getenv("GRAPH_BLUEPRINT_SECRET", "")
AGENT_CLIENT_ID = os.getenv("GRAPH_AGENT_CLIENT_ID", "")
AUTH_REDIRECT_BASE_URL = os.getenv("AUTH_REDIRECT_BASE_URL", "http://localhost:5050")
TOKEN_STORAGE_URL = os.getenv("TOKEN_STORAGE_URL", "")

REDIRECT_URI = f"{AUTH_REDIRECT_BASE_URL}/callback"
TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
AUTHORIZE_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize"


def get_bootstrap_token() -> str:
    """Blueprint credentials -> bootstrap token (T1)."""
    resp = httpx.post(TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": BLUEPRINT_CLIENT_ID,
        "client_secret": BLUEPRINT_SECRET,
        "scope": "api://AzureADTokenExchange/.default",
        "fmi_path": AGENT_CLIENT_ID,
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()["access_token"]


def obo_exchange(auth_code: str) -> dict:
    """Exchange auth code for a delegated agent token via OBO.

    Step 1: Code -> user token (Tc) using standard auth code redemption
    Step 2: Blueprint credentials -> bootstrap token (T1)
    Step 3: OBO exchange -- T1 + Tc -> delegated agent token
    """
    # Step 1 -- Redeem auth code for user token
    resp1 = httpx.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "client_id": BLUEPRINT_CLIENT_ID,
        "client_secret": BLUEPRINT_SECRET,
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "scope": "https://graph.microsoft.com/Calendars.Read offline_access",
    }, timeout=15)
    if resp1.status_code >= 400:
        # Try redeeming with agent client ID instead
        resp1 = httpx.post(TOKEN_URL, data={
            "grant_type": "authorization_code",
            "client_id": AGENT_CLIENT_ID,
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": get_bootstrap_token(),
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
            "scope": "https://graph.microsoft.com/Calendars.Read offline_access",
        }, timeout=15)
        if resp1.status_code >= 400:
            raise RuntimeError(f"Code redemption failed: {resp1.status_code} {resp1.text[:500]}")

    user_token_data = resp1.json()

    access_token = user_token_data.get("access_token", "")
    refresh_token = user_token_data.get("refresh_token", "")
    expires_in = user_token_data.get("expires_in", 3600)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": time.time() + expires_in,
    }


def try_obo_exchange(user_token: str) -> dict | None:
    """Try full OBO: bootstrap token + user token -> delegated agent token."""
    t1 = get_bootstrap_token()
    resp = httpx.post(TOKEN_URL, data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "client_id": AGENT_CLIENT_ID,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": t1,
        "assertion": user_token,
        "scope": "https://graph.microsoft.com/Calendars.Read",
        "requested_token_use": "on_behalf_of",
    }, timeout=15)
    if resp.status_code >= 400:
        return None
    data = resp.json()
    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "expires_at": time.time() + data.get("expires_in", 3600),
    }
