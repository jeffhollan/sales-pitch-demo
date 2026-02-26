"""Agent setup — configures a single GitHubCopilotAgent orchestrator with all tools.

The orchestrator receives the user's natural language request and autonomously
decides which tools to call. If the Copilot SDK is not installed, falls back
to the legacy mock agent pipeline.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


SKILLS_DIR = str(Path(__file__).resolve().parent / "skills")


# ── Agent instructions ─────────────────────────────────────────────────

SYSTEM_INSTRUCTIONS = """\
You are a Microsoft sales preparation assistant. You have access to tools
that help salespeople prepare for customer meetings.

Available tools:
- get_work_iq_data: Get relationship context (emails, calendar, Teams) from Microsoft Graph
- get_fabric_iq_data: Get business metrics (contract, spend, usage, support tickets)
- get_foundry_iq_data: Get sales enablement materials (sales plays, competitive intel)
- generate_prep_doc: Generate a Word meeting prep document
- generate_presentation: Generate a branded PowerPoint deck

Based on the user's request, decide which tools to call. For a full meeting
prep, research across all three data sources, synthesize your findings, then
generate the requested documents. For simpler requests, use only what's needed.

When presenting findings, be concise and focus on actionable insights.
Highlight risks (open tickets, competitive threats) and opportunities (expansion, upsell).

IMPORTANT — AUTHENTICATION FLOW:
If a tool returns a result containing "auth_required": true, you MUST stop immediately.
Do NOT continue with partial data. Do NOT present other findings or summarize what you have so far.
Your ONLY response should be to tell the user they need to sign in and provide the auth_url link.
Example: "I need you to sign in so I can access your calendar data. Please click here: <auth_url>"
Then WAIT. Do not call any other tools or generate any other output until the user confirms
they have signed in. Once they confirm, retry the SAME tool call to get the complete data."""


def create_orchestrator():
    """Create a SalesAgent orchestrator with all 5 tools and skill directories."""
    from agent_framework.github import GitHubCopilotAgent

    from src.tools import (
        get_work_iq_data,
        get_fabric_iq_data,
        get_foundry_iq_data,
        generate_prep_doc,
        generate_presentation,
    )

    tools = [
        get_work_iq_data,
        get_fabric_iq_data,
        get_foundry_iq_data,
        generate_prep_doc,
        generate_presentation,
    ]

    class SalesAgent(GitHubCopilotAgent):
        """GitHubCopilotAgent subclass that forwards skill_directories."""

        def __init__(self, *, skill_directories: list[str] | None = None,
                     disabled_skills: list[str] | None = None, **kwargs):
            super().__init__(**kwargs)
            self._skill_directories = skill_directories or []
            self._disabled_skills = disabled_skills or []

        async def start(self) -> None:
            """Override to configure CopilotClient auth.

            When AZURE_AI_FOUNDRY_RESOURCE_URL is set, start the CLI without
            GitHub auth (like Tony's adapter) — the ProviderConfig in
            _create_session handles LLM routing. Otherwise, pass GITHUB_TOKEN
            if available.
            """
            if self._started:
                return

            if self._client is None:
                from copilot import CopilotClient
                from copilot.types import CopilotClientOptions

                client_options: CopilotClientOptions = {}
                if self._settings["cli_path"]:
                    client_options["cli_path"] = self._settings["cli_path"]
                if self._settings["log_level"]:
                    client_options["log_level"] = self._settings["log_level"]  # type: ignore[typeddict-item]

                # Always pass GitHub token if available — the CLI needs it
                # for its startup auth handshake regardless of LLM routing.
                github_token = os.environ.get("GITHUB_TOKEN")
                if github_token:
                    client_options["github_token"] = github_token
                    print("[SalesAgent] CopilotClient using GITHUB_TOKEN", flush=True)
                else:
                    print("[SalesAgent] CopilotClient: no GITHUB_TOKEN found", flush=True)

                self._client = CopilotClient(client_options if client_options else None)

            try:
                await self._client.start()
                self._started = True
                print("[SalesAgent] CopilotClient started successfully", flush=True)
            except Exception as ex:
                print(f"[SalesAgent] CopilotClient failed to start: {ex}", flush=True)
                from agent_framework.exceptions import AgentException
                raise AgentException(f"Failed to start GitHub Copilot client: {ex}") from ex

        async def _create_session(self, streaming, runtime_options=None):
            """Override to inject skill_directories, disabled_skills, and provider."""
            if not self._client:
                raise RuntimeError(
                    "GitHub Copilot client not initialized. Call start() first."
                )

            opts = runtime_options or {}
            config: dict[str, Any] = {"streaming": streaming}

            model = (opts.get("model")
                     or self._settings["model"]
                     or os.environ.get("COPILOT_MODEL"))
            if model:
                config["model"] = model

            system_message = (
                opts.get("system_message")
                or self._default_options.get("system_message")
            )
            if system_message:
                config["system_message"] = system_message

            if self._tools:
                config["tools"] = self._prepare_tools(self._tools)

            permission_handler = (
                opts.get("on_permission_request") or self._permission_handler
            )
            if permission_handler:
                config["on_permission_request"] = permission_handler

            mcp_servers = opts.get("mcp_servers") or self._mcp_servers
            if mcp_servers:
                config["mcp_servers"] = mcp_servers

            # ── Skills (not forwarded by the base class) ──
            if self._skill_directories:
                config["skill_directories"] = self._skill_directories
            if self._disabled_skills:
                config["disabled_skills"] = self._disabled_skills

            print(f"[SalesAgent] Using GitHub Copilot provider", flush=True)
            print(f"[SalesAgent] Session config keys: {list(config.keys())}", flush=True)
            return await self._client.create_session(config)

    return SalesAgent(
        instructions=SYSTEM_INSTRUCTIONS,
        tools=tools,
        skill_directories=[SKILLS_DIR],
    )
