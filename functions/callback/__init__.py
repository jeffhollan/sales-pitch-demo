"""Azure Function: GET /api/callback

Handles the OAuth redirect from Entra. Exchanges the auth code for a
delegated agent token and saves it. For cloud deployments, writes the
token to Azure Blob Storage. Equivalent to the /callback handler in
scripts/auth_server.py.
"""

from __future__ import annotations

import json
import logging
import time

import azure.functions as func

from shared.auth_exchange import (
    TOKEN_STORAGE_URL,
    TOKEN_URL,
    get_bootstrap_token,
    obo_exchange,
    try_obo_exchange,
)

logger = logging.getLogger(__name__)

_SUCCESS_HTML = """<html>
<body style="font-family:sans-serif;padding:2em;text-align:center;">
<h2>Authorization successful!</h2>
<p>You can close this tab and return to the agent.</p>
</body></html>"""

_ERROR_HTML = """<html>
<body style="font-family:sans-serif;padding:2em;text-align:center;">
<h2>Authorization failed</h2>
<p>{error}</p>
</body></html>"""


def _save_token_to_blob(token_data: dict) -> None:
    """Write token JSON to Azure Blob Storage."""
    from azure.storage.blob import BlobClient, ContentSettings

    blob_client = BlobClient.from_blob_url(TOKEN_STORAGE_URL)
    blob_client.upload_blob(
        json.dumps(token_data, indent=2),
        overwrite=True,
        content_settings=ContentSettings(content_type="application/json"),
    )
    logger.info("Token saved to blob storage")


def main(req: func.HttpRequest) -> func.HttpResponse:
    error = req.params.get("error")
    if error:
        desc = req.params.get("error_description", "")
        logger.error("Auth error: %s - %s", error, desc)
        return func.HttpResponse(
            _ERROR_HTML.format(error=f"{error}: {desc}"),
            status_code=400,
            mimetype="text/html",
        )

    code = req.params.get("code")
    if not code:
        # No code returned (consent-only) -- try autonomous flow
        try:
            import httpx

            t1 = get_bootstrap_token()
            from shared.auth_exchange import AGENT_CLIENT_ID

            resp = httpx.post(TOKEN_URL, data={
                "grant_type": "client_credentials",
                "client_id": AGENT_CLIENT_ID,
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": t1,
                "scope": "https://graph.microsoft.com/.default",
            }, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            token_data = {
                "access_token": data["access_token"],
                "refresh_token": "",
                "expires_at": time.time() + data.get("expires_in", 3600),
            }
            _save_token_to_blob(token_data)
            return func.HttpResponse(_SUCCESS_HTML, mimetype="text/html")
        except Exception as e:
            logger.exception("Autonomous flow failed")
            return func.HttpResponse(
                _ERROR_HTML.format(error=str(e)),
                status_code=500,
                mimetype="text/html",
            )

    # Exchange auth code for token
    try:
        token_data = obo_exchange(code)

        # Try OBO exchange if we got a user token
        obo_result = try_obo_exchange(token_data["access_token"])
        if obo_result:
            logger.info("OBO exchange succeeded")
            final_token = obo_result
        else:
            logger.info("OBO exchange failed; using direct token")
            final_token = token_data

        _save_token_to_blob(final_token)
        return func.HttpResponse(_SUCCESS_HTML, mimetype="text/html")

    except Exception as e:
        logger.exception("Token exchange failed")
        return func.HttpResponse(
            _ERROR_HTML.format(error=str(e)),
            status_code=500,
            mimetype="text/html",
        )
