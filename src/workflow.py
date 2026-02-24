"""Workflow orchestration — parallel IQ fan-out → synthesis → doc generation.

This module defines the end-to-end sales prep workflow:
1. Parse customer name from user input
2. Fan out to three IQ agents in parallel (Work IQ, Fabric IQ, Foundry IQ)
3. Synthesize findings into a meeting plan
4. Generate Word prep doc + PowerPoint presentation
5. Return file paths

In mock mode, this runs without the Agent Framework or Copilot SDK — just
async Python with concurrent tasks. In live mode, it uses ConcurrentBuilder.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from rich.console import Console

from src.agent import create_agents
from src.tools.doc_generator import generate_prep_doc, generate_presentation

console = Console()


def _extract_customer_name(user_input: str) -> str:
    """Extract customer name from natural language input."""
    patterns = [
        r"(?:meeting|call|session|prep)\s+(?:with|for)\s+(.+?)(?:\s*$|\s*\.|\s*\?)",
        r"(?:prepare|prep)\s+(?:for|with)\s+(.+?)(?:\s*$|\s*\.|\s*\?)",
        r"(?:with|for)\s+(.+?)(?:\s*$|\s*\.|\s*\?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, user_input, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    # Fallback: return the input as-is
    return user_input.strip()


async def _run_iq_agent(agent, customer_name: str, iq_name: str) -> dict[str, Any]:
    """Run a single IQ agent and return results."""
    console.print(f"  [dim]Querying {iq_name}...[/dim]")
    result = await agent.run(customer_name)
    console.print(f"  [green]✓[/green] {iq_name} complete")
    return result


async def run_sales_prep(user_input: str) -> dict[str, Any]:
    """Execute the full sales prep workflow.

    Args:
        user_input: Natural language request (e.g., "Help me prepare for my meeting with Coca-Cola")

    Returns:
        dict with keys: customer_name, work_iq, fabric_iq, foundry_iq,
                        prep_doc_path, presentation_path
    """
    customer_name = _extract_customer_name(user_input)
    console.print(f"\n[bold blue]Sales Prep Agent[/bold blue] — Preparing for: [bold]{customer_name}[/bold]\n")

    # ── Step 1: Fan out to IQ agents in parallel ──
    console.print("[bold]Step 1/3[/bold] — Researching across Microsoft IQs...")
    agents = create_agents()

    work_iq_task = asyncio.create_task(
        _run_iq_agent(agents["work_iq"], customer_name, "Work IQ (email/Teams/calendar)")
    )
    fabric_iq_task = asyncio.create_task(
        _run_iq_agent(agents["fabric_iq"], customer_name, "Fabric IQ (spend/usage/tickets)")
    )
    foundry_iq_task = asyncio.create_task(
        _run_iq_agent(agents["foundry_iq"], customer_name, "Foundry IQ (sales plays/KB)")
    )

    work_iq, fabric_iq, foundry_iq = await asyncio.gather(
        work_iq_task, fabric_iq_task, foundry_iq_task
    )

    # ── Step 2: Synthesize ──
    console.print("\n[bold]Step 2/3[/bold] — Synthesizing findings...")
    synthesis = _synthesize(customer_name, work_iq, fabric_iq, foundry_iq)
    console.print("  [green]✓[/green] Synthesis complete")

    # ── Step 3: Generate documents ──
    console.print("\n[bold]Step 3/3[/bold] — Generating documents...")

    prep_doc_path = generate_prep_doc(customer_name, work_iq, fabric_iq, foundry_iq)
    console.print(f"  [green]✓[/green] Word prep doc: [link=file://{prep_doc_path}]{prep_doc_path}[/link]")

    presentation_path = generate_presentation(customer_name, work_iq, fabric_iq, foundry_iq)
    console.print(f"  [green]✓[/green] PowerPoint deck: [link=file://{presentation_path}]{presentation_path}[/link]")

    return {
        "customer_name": customer_name,
        "synthesis": synthesis,
        "work_iq": work_iq,
        "fabric_iq": fabric_iq,
        "foundry_iq": foundry_iq,
        "prep_doc_path": prep_doc_path,
        "presentation_path": presentation_path,
    }


def _synthesize(
    customer_name: str,
    work_iq: dict[str, Any],
    fabric_iq: dict[str, Any],
    foundry_iq: dict[str, Any],
) -> str:
    """Build a text synthesis from the three IQ results.

    In mock mode, this is template-driven. In live mode, the LLM synthesizer
    agent would handle this via the Copilot SDK.
    """
    lines = []

    # Executive summary
    fin = fabric_iq.get("financial_summary", {})
    rel = work_iq.get("relationship_summary", "")
    lines.append("## Executive Summary")
    lines.append(rel)
    if fin:
        lines.append(
            f"Current annual spend: ${fin.get('current_annual_spend', 0):,.0f}. "
            f"Growth potential: +{fin.get('growth_potential_pct', 0)}% "
            f"(${fin.get('proposed_annual_spend', 0):,.0f}). "
            f"Renewal risk: {fin.get('renewal_risk', 'Unknown')}."
        )

    # Key risks
    lines.append("\n## Key Risks")
    open_tickets = [t for t in fabric_iq.get("support_tickets", []) if t.get("status") == "Open"]
    for t in open_tickets:
        lines.append(f"- [{t['severity']}] {t['title']} — open since {t['opened']}")
    ci = foundry_iq.get("competitive_intelligence", {})
    for risk in ci.get("risks", []):
        lines.append(f"- {risk}")

    # Opportunities
    lines.append("\n## Opportunities")
    for opp in fabric_iq.get("expansion_opportunities", []):
        lines.append(f"- {opp['product']}: ${opp['incremental_value']:,.0f} ({opp['stage']}, {opp['confidence']} confidence)")

    # Recommended agenda
    lines.append("\n## Recommended Agenda")
    lines.append("1. Address open support issues (demonstrate responsiveness)")
    lines.append("2. Review Copilot adoption success and expansion business case")
    lines.append("3. Present Fabric optimization plan and capacity roadmap")
    lines.append("4. Introduce AI Foundry vision for bottling operations")
    lines.append("5. Align on renewal timeline and expanded scope")

    # Materials
    lines.append("\n## Materials to Share")
    for play in foundry_iq.get("sales_plays", []):
        lines.append(f"- {play['play_name']}")
        for res in play.get("resources", []):
            lines.append(f"  - {res['title']} ({res['type']})")

    return "\n".join(lines)
