"""Azure Function: GET /api/login

Redirects the user's browser to the Entra /authorize endpoint to start
the interactive OAuth flow. Equivalent to the /login handler in
scripts/auth_server.py.
"""

from __future__ import annotations

import secrets
from urllib.parse import urlencode

import azure.functions as func

from shared.auth_exchange import AGENT_CLIENT_ID, AUTHORIZE_URL, BLUEPRINT_CLIENT_ID, REDIRECT_URI


def main(req: func.HttpRequest) -> func.HttpResponse:
    state = secrets.token_urlsafe(16)

    params = urlencode({
        "client_id": AGENT_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": f"api://{BLUEPRINT_CLIENT_ID}/access_agent offline_access",
        "state": state,
        "response_mode": "query",
    })

    return func.HttpResponse(
        status_code=302,
        headers={"Location": f"{AUTHORIZE_URL}?{params}"},
    )
