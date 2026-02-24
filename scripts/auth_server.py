#!/usr/bin/env python3
"""Local OAuth callback server for delegated Agent Identity auth.

Starts an HTTP server on localhost:5050 that drives the interactive
authorization flow for Entra Agent Identity OBO (on-behalf-of):

  1. GET /login  — redirects the user's browser to Entra /authorize
  2. GET /callback — catches the redirect, exchanges the auth code for
     a delegated agent token via the two-step OBO flow, caches it, and exits.

Usage:
    python scripts/auth_server.py
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from dotenv import load_dotenv

# Load env from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

TENANT_ID = os.getenv("GRAPH_TENANT_ID", "")
BLUEPRINT_CLIENT_ID = os.getenv("GRAPH_BLUEPRINT_CLIENT_ID", "")
BLUEPRINT_SECRET = os.getenv("GRAPH_BLUEPRINT_SECRET", "")
AGENT_CLIENT_ID = os.getenv("GRAPH_AGENT_CLIENT_ID", "")

PORT = 5050
REDIRECT_URI = f"http://localhost:{PORT}/callback"
TOKEN_CACHE_PATH = Path.home() / ".sales-prep-demo-token.json"
TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
AUTHORIZE_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize"

_state = secrets.token_urlsafe(16)


def _obo_exchange(auth_code: str) -> dict:
    """Exchange auth code for a delegated agent token via OBO.

    Step 1: Code → user token (Tc) using standard auth code redemption
    Step 2: Blueprint credentials → bootstrap token (T1)
    Step 3: OBO exchange — T1 + Tc → delegated agent token
    """
    # Step 1 — Redeem auth code for user token
    # The code was issued with client_id=AGENT_CLIENT_ID, so we redeem
    # using the blueprint credentials (which own the agent).
    resp1 = httpx.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "client_id": BLUEPRINT_CLIENT_ID,
        "client_secret": BLUEPRINT_SECRET,
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "scope": "https://graph.microsoft.com/Calendars.Read offline_access",
    }, timeout=15)
    if resp1.status_code >= 400:
        print(f"  Step 1 (code redemption) failed: {resp1.status_code} {resp1.text[:500]}", file=sys.stderr)
        # Try redeeming with agent client ID instead
        resp1 = httpx.post(TOKEN_URL, data={
            "grant_type": "authorization_code",
            "client_id": AGENT_CLIENT_ID,
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": _get_bootstrap_token(),
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
            "scope": "https://graph.microsoft.com/Calendars.Read offline_access",
        }, timeout=15)
        if resp1.status_code >= 400:
            raise RuntimeError(f"Code redemption failed: {resp1.status_code} {resp1.text[:500]}")

    user_token_data = resp1.json()

    # If we got a Graph token directly (aud=graph), just use it
    access_token = user_token_data.get("access_token", "")
    refresh_token = user_token_data.get("refresh_token", "")
    expires_in = user_token_data.get("expires_in", 3600)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": time.time() + expires_in,
    }


def _get_bootstrap_token() -> str:
    """Step 1 of Agent ID flow: blueprint credentials → bootstrap token."""
    resp = httpx.post(TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": BLUEPRINT_CLIENT_ID,
        "client_secret": BLUEPRINT_SECRET,
        "scope": "api://AzureADTokenExchange/.default",
        "fmi_path": AGENT_CLIENT_ID,
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()["access_token"]


def _try_obo_exchange(user_token: str) -> dict | None:
    """Try full OBO: bootstrap token + user token → delegated agent token."""
    t1 = _get_bootstrap_token()
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
        print(f"  OBO exchange failed: {resp.status_code} {resp.text[:300]}", file=sys.stderr)
        return None
    data = resp.json()
    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "expires_at": time.time() + data.get("expires_in", 3600),
    }


def _save_token(token_data: dict) -> None:
    TOKEN_CACHE_PATH.write_text(json.dumps(token_data, indent=2))
    print(f"  Token cached to {TOKEN_CACHE_PATH}")


class CallbackHandler(BaseHTTPRequestHandler):
    server: HTTPServer

    def log_message(self, format: str, *args: object) -> None:
        pass  # suppress default logging

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/login":
            params = urlencode({
                "client_id": AGENT_CLIENT_ID,
                "response_type": "code",
                "redirect_uri": REDIRECT_URI,
                "scope": f"api://{BLUEPRINT_CLIENT_ID}/access_agent offline_access",
                "state": _state,
                "response_mode": "query",
            })
            self.send_response(302)
            self.send_header("Location", f"{AUTHORIZE_URL}?{params}")
            self.end_headers()
            return

        if parsed.path == "/callback":
            qs = parse_qs(parsed.query)

            # Verify state
            if qs.get("state", [None])[0] != _state:
                self._respond(400, "State mismatch — possible CSRF. Try again.")
                return

            error = qs.get("error", [None])[0]
            if error:
                desc = qs.get("error_description", [""])[0]
                print(f"  Auth error: {error} — {desc}", file=sys.stderr)
                self._respond(400, f"Authorization error: {error}\n{desc}")
                return

            code = qs.get("code", [None])[0]
            if code:
                print("  Received auth code, exchanging for token...")
                try:
                    token_data = _obo_exchange(code)

                    # Try OBO exchange if we got a user token
                    obo_result = _try_obo_exchange(token_data["access_token"])
                    if obo_result:
                        print("  OBO exchange succeeded!")
                        _save_token(obo_result)
                    else:
                        print("  OBO exchange failed; saving direct token instead.")
                        _save_token(token_data)

                    self._respond(200, "Authorization successful! You can close this tab.")
                except Exception as e:
                    print(f"  Token exchange error: {e}", file=sys.stderr)
                    self._respond(500, f"Token exchange failed: {e}")
                    return
            else:
                # response_type=none (consent-only) — no code returned
                print("  No code returned (consent-only). Trying autonomous flow...")
                try:
                    t1 = _get_bootstrap_token()
                    # Try getting a Graph token with delegated scope via client_credentials
                    resp = httpx.post(TOKEN_URL, data={
                        "grant_type": "client_credentials",
                        "client_id": AGENT_CLIENT_ID,
                        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                        "client_assertion": t1,
                        "scope": "https://graph.microsoft.com/.default",
                    }, timeout=15)
                    resp.raise_for_status()
                    data = resp.json()
                    _save_token({
                        "access_token": data["access_token"],
                        "refresh_token": "",
                        "expires_at": time.time() + data.get("expires_in", 3600),
                    })
                    self._respond(200, "Consent recorded. Token acquired via autonomous flow. You can close this tab.")
                except Exception as e:
                    print(f"  Autonomous flow after consent failed: {e}", file=sys.stderr)
                    self._respond(500, f"Failed to acquire token after consent: {e}")
                    return

            # Shut down the server after handling the callback
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        self._respond(404, "Not found. Go to /login to start.")

    def _respond(self, status: int, body: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html = f"<html><body style='font-family:sans-serif;padding:2em;'><h2>{body}</h2></body></html>"
        self.wfile.write(html.encode())


def main() -> None:
    missing = []
    if not TENANT_ID:
        missing.append("GRAPH_TENANT_ID")
    if not BLUEPRINT_CLIENT_ID:
        missing.append("GRAPH_BLUEPRINT_CLIENT_ID")
    if not BLUEPRINT_SECRET:
        missing.append("GRAPH_BLUEPRINT_SECRET")
    if not AGENT_CLIENT_ID:
        missing.append("GRAPH_AGENT_CLIENT_ID")
    if missing:
        print(f"Missing env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    server = HTTPServer(("127.0.0.1", PORT), CallbackHandler)
    url = f"http://localhost:{PORT}/login"
    print(f"Starting auth server on {url}")
    print("Opening browser...")
    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("Auth server stopped.")


if __name__ == "__main__":
    main()
