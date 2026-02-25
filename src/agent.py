"""Agent setup — configures a single GitHubCopilotAgent orchestrator with all tools.

The orchestrator receives the user's natural language request and autonomously
decides which tools to call. If the Copilot SDK is not installed, falls back
to the legacy mock agent pipeline.
"""

from __future__ import annotations

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
    from src.tools import (
        get_work_iq_data,
        get_fabric_iq_data,
        get_foundry_iq_data,
        generate_prep_doc,
        generate_presentation,
    )

    SalesAgent = _make_sales_agent_class()
    return SalesAgent(
        instructions=SYSTEM_INSTRUCTIONS,
        tools=[
            get_work_iq_data,
            get_fabric_iq_data,
            get_foundry_iq_data,
            generate_prep_doc,
            generate_presentation,
        ],
        skill_directories=[SKILLS_DIR],
    )


def _make_sales_agent_class():
    """Build a SalesAgent class that subclasses GitHubCopilotAgent.

    Deferred into a factory so the SDK import only happens when called.
    """
    from agent_framework.github import GitHubCopilotAgent

    class SalesAgent(GitHubCopilotAgent):
        """GitHubCopilotAgent subclass that forwards skill_directories."""

        def __init__(self, *, skill_directories: list[str] | None = None,
                     disabled_skills: list[str] | None = None, **kwargs):
            super().__init__(**kwargs)
            self._skill_directories = skill_directories or []
            self._disabled_skills = disabled_skills or []

        async def _create_session(self, streaming, runtime_options=None):
            """Override to inject skill_directories and disabled_skills."""
            if not self._client:
                raise RuntimeError(
                    "GitHub Copilot client not initialized. Call start() first."
                )

            opts = runtime_options or {}
            config: dict[str, Any] = {"streaming": streaming}

            model = opts.get("model") or self._settings["model"]
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

            return await self._client.create_session(config)

    return SalesAgent
