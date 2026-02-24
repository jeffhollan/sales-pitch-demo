"""Agent setup — configures a single GitHubCopilotAgent orchestrator with all tools.

The orchestrator receives the user's natural language request and autonomously
decides which tools to call. If the Copilot SDK is not installed, falls back
to the legacy mock agent pipeline.
"""

from __future__ import annotations

from typing import Any


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
Highlight risks (open tickets, competitive threats) and opportunities (expansion, upsell)."""


def create_orchestrator():
    """Create a GitHubCopilotAgent orchestrator with all 5 tools registered.

    Falls back to the legacy mock agent dict if the Copilot SDK is not installed.
    """
    try:
        from agent_framework.github import GitHubCopilotAgent
    except ImportError:
        import warnings
        warnings.warn(
            "agent-framework-github-copilot not installed — falling back to mock agents. "
            "Install with: pip install agent-framework-github-copilot --pre",
            stacklevel=2,
        )
        return _create_mock_agents()

    from src.tools import (
        get_work_iq_data,
        get_fabric_iq_data,
        get_foundry_iq_data,
        generate_prep_doc,
        generate_presentation,
    )

    return GitHubCopilotAgent(
        instructions=SYSTEM_INSTRUCTIONS,
        tools=[
            get_work_iq_data,
            get_fabric_iq_data,
            get_foundry_iq_data,
            generate_prep_doc,
            generate_presentation,
        ],
    )


def _create_mock_agents() -> dict[str, Any]:
    """Create simple function-based agents for mock mode (no Copilot SDK needed)."""
    from src.tools.work_iq import get_work_iq_data
    from src.tools.fabric_iq import get_fabric_iq_data
    from src.tools.foundry_iq import get_foundry_iq_data

    class MockAgent:
        """Lightweight agent that wraps a function tool."""
        def __init__(self, name: str, fn):
            self.name = name
            self._fn = fn

        async def run(self, customer_name: str) -> dict[str, Any]:
            return self._fn(customer_name)

    return {
        "work_iq": MockAgent("work-iq", get_work_iq_data),
        "fabric_iq": MockAgent("fabric-iq", get_fabric_iq_data),
        "foundry_iq": MockAgent("foundry-iq", get_foundry_iq_data),
    }
