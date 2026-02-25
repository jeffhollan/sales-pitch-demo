"""Configuration — loads env vars and provides project-wide settings."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# ── Paths ──────────────────────────────────────────────────────────────
PROJECT_ROOT = _PROJECT_ROOT
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
MOCK_DATA_DIR = Path(__file__).resolve().parent / "mock_data"
OUTPUT_DIR = _PROJECT_ROOT / os.getenv("OUTPUT_DIR", "output")
PPTX_TEMPLATE = _PROJECT_ROOT / "templates" / "Microsoft_Brand_Template_May2023.potx"

# ── Feature flags ──────────────────────────────────────────────────────
USE_MOCK_DATA: bool = os.getenv("USE_MOCK_DATA", "true").lower() == "true"

# ── Work IQ (Microsoft Graph) ─────────────────────────────────────────
WORKIQ_TENANT_ID: str | None = os.getenv("WORKIQ_TENANT_ID")
GRAPH_TENANT_ID: str | None = os.getenv("GRAPH_TENANT_ID")
GRAPH_CLIENT_ID: str | None = os.getenv("GRAPH_CLIENT_ID")
GRAPH_CLIENT_SECRET: str | None = os.getenv("GRAPH_CLIENT_SECRET")
GRAPH_USER_ID: str | None = os.getenv("GRAPH_USER_ID")

# ── Agent Identity Blueprint (Entra Agent ID preview) ────────────────
GRAPH_BLUEPRINT_CLIENT_ID: str | None = os.getenv("GRAPH_BLUEPRINT_CLIENT_ID")
GRAPH_BLUEPRINT_SECRET: str | None = os.getenv("GRAPH_BLUEPRINT_SECRET")
GRAPH_AGENT_CLIENT_ID: str | None = os.getenv("GRAPH_AGENT_CLIENT_ID")
GRAPH_DELEGATED_CLIENT_ID: str | None = os.getenv("GRAPH_DELEGATED_CLIENT_ID")
GRAPH_DELEGATED_CLIENT_SECRET: str | None = os.getenv("GRAPH_DELEGATED_CLIENT_SECRET")

# ── OAuth callback ────────────────────────────────────────────────────
AUTH_REDIRECT_BASE_URL: str = os.getenv("AUTH_REDIRECT_BASE_URL", "http://localhost:5050")

# ── Cloud token storage (Azure Blob SAS URL) ─────────────────────────
TOKEN_STORAGE_URL: str | None = os.getenv("TOKEN_STORAGE_URL")

# ── Fabric IQ ─────────────────────────────────────────────────────────
FABRIC_WORKSPACE_ID: str | None = os.getenv("FABRIC_WORKSPACE_ID")

# ── Foundry IQ (Azure AI Search) ──────────────────────────────────────
AZURE_SEARCH_ENDPOINT: str | None = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY: str | None = os.getenv("AZURE_SEARCH_KEY")
AZURE_SEARCH_INDEX: str = os.getenv("AZURE_SEARCH_INDEX", "sales-enablement")


def ensure_output_dir() -> Path:
    """Create and return the output directory."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR
