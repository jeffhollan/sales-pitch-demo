#!/usr/bin/env python3
"""Provision an Entra Agent Identity Blueprint and Agent Identity.

Uses MSAL device code flow with Microsoft Graph PowerShell's well-known
client ID to avoid the Directory.AccessAsUser.All scope that the Azure CLI
app includes (which the Agent ID APIs reject).

Usage:
    python scripts/provision_agent_id.py
"""

from __future__ import annotations

import json
import sys
import uuid

import httpx
import msal

TENANT_ID = "dd17a423-b664-4794-9fdc-54d8e4854425"

# Dedicated public client app for Agent ID provisioning — no
# Directory.AccessAsUser.All (which the Agent ID APIs reject).
PUBLIC_CLIENT_ID = "9cb06675-3d57-4ec6-b5de-79e42d4b5986"

GRAPH_BETA = "https://graph.microsoft.com/beta"
GRAPH_V1 = "https://graph.microsoft.com/v1.0"

SCOPES = ["User.Read", "Application.ReadWrite.All", "AppRoleAssignment.ReadWrite.All", "DelegatedPermissionGrant.ReadWrite.All"]


def get_token() -> str:
    """Acquire a Graph token via device code flow."""
    app = msal.PublicClientApplication(
        PUBLIC_CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    )
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        print(f"Failed to create device flow: {flow}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  {flow['message']}")
    print(f"{'='*60}\n")

    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        print(f"Auth failed: {result.get('error_description', result)}")
        sys.exit(1)

    return result["access_token"]


def graph_post(token: str, url: str, body: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "OData-Version": "4.0",
    }
    resp = httpx.post(url, headers=headers, json=body, timeout=30)
    if resp.status_code >= 400:
        print(f"  ERROR {resp.status_code}: {resp.text[:500]}")
        sys.exit(1)
    return resp.json()


def graph_patch(token: str, url: str, body: dict) -> None:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "OData-Version": "4.0",
    }
    resp = httpx.patch(url, headers=headers, json=body, timeout=30)
    if resp.status_code >= 400:
        print(f"  ERROR {resp.status_code}: {resp.text[:500]}")
        sys.exit(1)


def graph_get(token: str, url: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    resp = httpx.get(url, headers=headers, timeout=30)
    if resp.status_code >= 400:
        print(f"  ERROR {resp.status_code}: {resp.text[:500]}")
        sys.exit(1)
    return resp.json()


def main() -> None:
    print("Step 0: Authenticate to Microsoft Graph...")
    token = get_token()

    # 1.1 — Get current user's object ID
    print("Step 1.1: Getting user object ID...")
    me = graph_get(token, f"{GRAPH_V1}/me?$select=id,userPrincipalName")
    user_oid = me["id"]
    print(f"  User: {me['userPrincipalName']} ({user_oid})")

    # 1.2 — Create blueprint
    print("Step 1.2: Creating Agent Identity Blueprint...")
    blueprint = graph_post(token, f"{GRAPH_BETA}/applications/", {
        "@odata.type": "Microsoft.Graph.AgentIdentityBlueprint",
        "displayName": "sales-pres-demo-blueprint",
        "sponsors@odata.bind": [f"{GRAPH_V1}/users/{user_oid}"],
        "owners@odata.bind": [f"{GRAPH_V1}/users/{user_oid}"],
    })
    blueprint_id = blueprint["id"]
    blueprint_app_id = blueprint["appId"]
    print(f"  Blueprint ID: {blueprint_id}")
    print(f"  Blueprint App ID: {blueprint_app_id}")

    # 1.3 — Add client secret
    print("Step 1.3: Adding client secret to blueprint...")
    secret_resp = graph_post(token, f"{GRAPH_BETA}/applications/{blueprint_id}/addPassword", {
        "passwordCredential": {
            "displayName": "demo-secret",
            "endDateTime": "2027-02-24T00:00:00Z",
        }
    })
    blueprint_secret = secret_resp["secretText"]
    print(f"  Secret: {blueprint_secret[:8]}... (saved)")

    # 1.4 — Configure identifier URI, OAuth scope, redirect URI
    print("Step 1.4: Configuring identifier URI, OAuth scope, redirect URI...")
    scope_id = str(uuid.uuid4())
    graph_patch(token, f"{GRAPH_BETA}/applications/{blueprint_id}", {
        "identifierUris": [f"api://{blueprint_app_id}"],
        "api": {
            "oauth2PermissionScopes": [{
                "adminConsentDescription": "Access the sales prep agent",
                "adminConsentDisplayName": "Access agent",
                "id": scope_id,
                "isEnabled": True,
                "type": "User",
                "value": "access_agent",
            }]
        },
        "publicClient": {
            "redirectUris": ["https://login.microsoftonline.com/common/oauth2/nativeclient"]
        },
    })
    print("  Done.")

    # 1.5 — Create blueprint principal
    print("Step 1.5: Creating blueprint principal (service principal)...")
    bp_sp = graph_post(token, f"{GRAPH_BETA}/serviceprincipals/graph.agentIdentityBlueprintPrincipal", {
        "appId": blueprint_app_id,
    })
    print(f"  Blueprint SP ID: {bp_sp['id']}")

    # 1.6 — Create agent identity
    print("Step 1.6: Creating agent identity from blueprint...")
    agent = graph_post(token, f"{GRAPH_BETA}/serviceprincipals/Microsoft.Graph.AgentIdentity", {
        "agentIdentityBlueprintId": blueprint_id,
        "displayName": "sales-pres-demo-agent",
        "sponsors@odata.bind": [f"{GRAPH_V1}/users/{user_oid}"],
    })
    agent_sp_id = agent["id"]
    agent_client_id = agent["appId"]
    print(f"  Agent SP ID: {agent_sp_id}")
    print(f"  Agent Client ID: {agent_client_id}")

    # 1.7 — Grant Mail.Read app role to agent identity
    print("Step 1.7: Granting Mail.Read app role...")
    graph_sp = graph_get(token, f"{GRAPH_V1}/servicePrincipals?$filter=appId eq '00000003-0000-0000-c000-000000000000'&$select=id")
    graph_sp_id = graph_sp["value"][0]["id"]
    print(f"  Microsoft Graph SP ID: {graph_sp_id}")

    graph_post(token, f"{GRAPH_V1}/servicePrincipals/{agent_sp_id}/appRoleAssignments", {
        "principalId": agent_sp_id,
        "resourceId": graph_sp_id,
        "appRoleId": "810c84a8-4a9e-49e6-bf7d-12d183f40d01",  # Mail.Read
    })
    print("  Mail.Read granted.")

    # 1.8 — Pre-consent Calendars.Read delegated permission
    print("Step 1.8: Pre-consenting Calendars.Read delegated permission...")
    graph_post(token, f"{GRAPH_V1}/oauth2PermissionGrants", {
        "clientId": agent_sp_id,
        "consentType": "AllPrincipals",
        "resourceId": graph_sp_id,
        "scope": "Calendars.Read",
    })
    print("  Calendars.Read pre-consented.")

    # Summary
    print(f"\n{'='*60}")
    print("  PROVISIONING COMPLETE")
    print(f"{'='*60}")
    print(f"\n  Add these to your .env file:\n")
    print(f"  GRAPH_BLUEPRINT_CLIENT_ID={blueprint_app_id}")
    print(f"  GRAPH_BLUEPRINT_SECRET={blueprint_secret}")
    print(f"  GRAPH_AGENT_CLIENT_ID={agent_client_id}")
    print(f"\n  Blueprint ID (for reference): {blueprint_id}")
    print(f"  Agent SP ID (for reference):   {agent_sp_id}")
    print()

    # Write to a temp file for easy copy
    output = {
        "blueprint_id": blueprint_id,
        "blueprint_app_id": blueprint_app_id,
        "blueprint_secret": blueprint_secret,
        "agent_sp_id": agent_sp_id,
        "agent_client_id": agent_client_id,
        "graph_sp_id": graph_sp_id,
    }
    out_path = "/tmp/agent_id_provisioning.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"  Full output saved to {out_path}")


if __name__ == "__main__":
    main()
