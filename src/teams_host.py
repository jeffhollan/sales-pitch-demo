"""Teams / M365 Agents SDK hosting entry point.

This module provides the Teams bot integration. It requires:
- M365 developer tenant with Teams licenses
- M365 Agents SDK configured
- Teams Toolkit or Agent 365 CLI for deployment

This is a Phase 6 placeholder — the core workflow logic is in workflow.py.
"""

from __future__ import annotations

import asyncio
from typing import Any


async def handle_teams_message(activity: dict[str, Any]) -> dict[str, Any]:
    """Handle an incoming Teams message and return a response.

    This is the main entry point for Teams integration. It:
    1. Extracts the user message from the Teams activity
    2. Runs the sales prep workflow
    3. Returns a response with document links

    Args:
        activity: Teams Bot Framework activity object

    Returns:
        Response activity with text and adaptive card attachment
    """
    from src.workflow import run_sales_prep

    user_text = activity.get("text", "").strip()
    if not user_text:
        return {"type": "message", "text": "Please tell me which customer you'd like to prepare for. For example: 'Help me prepare for my meeting with Coca-Cola'"}

    result = await run_sales_prep(user_text)

    # Build adaptive card response
    card = _build_adaptive_card(result)

    return {
        "type": "message",
        "text": f"Meeting prep complete for {result['customer_name']}! I've generated a prep doc and presentation.",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": card,
            }
        ],
    }


def _build_adaptive_card(result: dict[str, Any]) -> dict[str, Any]:
    """Build an Adaptive Card for Teams with meeting prep results."""
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": f"Meeting Prep — {result['customer_name']}",
                "size": "Large",
                "weight": "Bolder",
                "color": "Accent",
            },
            {
                "type": "TextBlock",
                "text": result.get("synthesis", "")[:500],
                "wrap": True,
                "size": "Small",
            },
            {"type": "TextBlock", "text": "Generated Documents:", "weight": "Bolder"},
            {
                "type": "ColumnSet",
                "columns": [
                    {
                        "type": "Column",
                        "items": [
                            {"type": "TextBlock", "text": "📄 Word Prep Doc", "weight": "Bolder"},
                            {"type": "TextBlock", "text": result.get("prep_doc_path", ""), "size": "Small"},
                        ],
                    },
                    {
                        "type": "Column",
                        "items": [
                            {"type": "TextBlock", "text": "📊 PowerPoint Deck", "weight": "Bolder"},
                            {"type": "TextBlock", "text": result.get("presentation_path", ""), "size": "Small"},
                        ],
                    },
                ],
            },
        ],
    }


# ── M365 Agents SDK hosting (Phase 6) ─────────────────────────────────
# To deploy on Teams:
# 1. pip install m365-agents-sdk
# 2. Configure manifest and Entra ID app registration
# 3. Use Teams Toolkit: `teamsapp provision && teamsapp deploy`
#
# Example hosting setup:
#
# from m365_agents import AgentApplication
#
# app = AgentApplication()
#
# @app.on_message()
# async def on_message(context):
#     response = await handle_teams_message(context.activity)
#     await context.send_activity(response)
#
# if __name__ == "__main__":
#     app.run()
