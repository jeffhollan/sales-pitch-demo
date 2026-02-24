"""Agent setup — configures GitHubCopilotAgent with tools and MCP servers.

This module provides the factory functions for creating agents. In mock mode,
agents use function tools backed by local JSON data. In live mode, agents
connect to MCP servers via the Copilot SDK session config.
"""

from __future__ import annotations

from typing import Any

from src.config import USE_MOCK_DATA


# ── Agent instructions ─────────────────────────────────────────────────

SYSTEM_INSTRUCTIONS = """You are a Microsoft sales preparation assistant. Your job is to help
salespeople prepare for customer meetings by researching across three data sources (Work IQ,
Fabric IQ, Foundry IQ), synthesizing findings, and generating meeting prep documents.

When a user asks to prepare for a meeting with a customer:
1. Query all three IQ sources for the customer
2. Synthesize the findings into a coherent meeting plan
3. Generate a Word prep doc and a PowerPoint presentation
4. Return the file paths to the generated documents

Be concise, professional, and focus on actionable insights. Highlight risks
(open support tickets, competitive threats) and opportunities (expansion, upsell)."""


WORK_IQ_INSTRUCTIONS = """You are the Work IQ research agent. Your job is to retrieve
relationship context from Microsoft Graph — recent emails, Teams messages, calendar events,
and people information for a given customer. Return the raw data as-is."""

FABRIC_IQ_INSTRUCTIONS = """You are the Fabric IQ research agent. Your job is to retrieve
business metrics from Microsoft Fabric — contract details, spend, usage trends, support
tickets, and expansion opportunities for a given customer. Return the raw data as-is."""

FOUNDRY_IQ_INSTRUCTIONS = """You are the Foundry IQ research agent. Your job is to retrieve
sales enablement materials from the knowledge base — relevant sales plays, competitive
intelligence, customer references, and resources for a given customer. Return the raw data as-is."""

SYNTHESIZER_INSTRUCTIONS = """You are the synthesis agent. Given research results from Work IQ
(relationship context), Fabric IQ (business metrics), and Foundry IQ (sales plays), create a
concise meeting preparation plan. Structure your output as:

1. **Executive Summary** — 2-3 sentences on the account state and meeting priorities
2. **Key Risks** — issues to address (open tickets, competitive threats, renewal timeline)
3. **Opportunities** — expansion, upsell, and strategic discussion topics
4. **Recommended Agenda** — suggested talking points in priority order
5. **Materials to Share** — relevant sales plays, references, and resources"""


def create_agents() -> dict[str, Any]:
    """Create and return all agent instances.

    Returns a dict with keys: work_iq, fabric_iq, foundry_iq.
    Uses lightweight MockAgent wrappers in both mock and live modes — the tool
    functions themselves handle the mock/live branching via REST APIs (Azure AI
    Search for Foundry IQ, Microsoft Graph for Work IQ).
    """
    return _create_mock_agents()


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


def _create_live_agents() -> dict[str, Any]:
    """Create GitHubCopilotAgent instances with MCP server connections.

    Requires: agent-framework[all], agent-framework-github-copilot, and
    GitHub Copilot CLI authenticated via `gh auth login`.

    Document generation (generate_presentation, generate_prep_doc) is
    registered as function tools on the orchestrator agent.  The same
    capabilities are also available as a standalone MCP server — see
    ``src.skills.pptx_skill`` — which can be connected instead:

        mcp_servers={
            "pptx-skill": {
                "command": "python",
                "args": ["-m", "src.skills.pptx_skill"],
            },
        }
    """
    try:
        from agent_framework.github import GitHubCopilotAgent
    except ImportError:
        raise RuntimeError(
            "Live mode requires agent-framework-github-copilot. "
            "Install with: pip install agent-framework[all] agent-framework-github-copilot --pre"
        )

    from src.tools.doc_generator import generate_prep_doc, generate_presentation

    work_iq_agent = GitHubCopilotAgent(
        default_options={"instructions": WORK_IQ_INSTRUCTIONS},
        mcp_servers={
            "work-iq": {"command": "npx", "args": ["-y", "@microsoft/workiq", "mcp"]},
        },
    )

    fabric_iq_agent = GitHubCopilotAgent(
        default_options={"instructions": FABRIC_IQ_INSTRUCTIONS},
        mcp_servers={
            "fabric-iq": {"command": "npx", "args": ["-y", "@microsoft/fabric-mcp"]},
        },
    )

    foundry_iq_agent = GitHubCopilotAgent(
        default_options={"instructions": FOUNDRY_IQ_INSTRUCTIONS},
    )

    # Orchestrator agent with doc-gen function tools registered directly.
    # These are Annotated function tools that the Copilot SDK can invoke.
    orchestrator = GitHubCopilotAgent(
        default_options={"instructions": SYSTEM_INSTRUCTIONS},
        tools=[generate_presentation, generate_prep_doc],
    )

    return {
        "work_iq": work_iq_agent,
        "fabric_iq": fabric_iq_agent,
        "foundry_iq": foundry_iq_agent,
        "orchestrator": orchestrator,
    }
