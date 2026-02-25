"""Local CLI entry point for the Sales Prep Agent."""

from __future__ import annotations

import asyncio
import sys

from rich.console import Console
from rich.panel import Panel

console = Console()


def _print_banner():
    console.print(Panel(
        "[bold blue]Microsoft Sales Prep Agent[/bold blue]\n"
        "[dim]Researches across Work IQ, Fabric IQ, and Foundry IQ to prepare\n"
        "meeting documents for customer engagements.[/dim]",
        border_style="blue",
    ))


async def _run(user_input: str):
    from src.workflow import run_sales_prep

    result = await run_sales_prep(user_input)

    # Show doc paths if present
    if result.get("prep_doc_path"):
        console.print(f"\n  📄 Word prep doc:  {result['prep_doc_path']}")
    if result.get("presentation_path"):
        console.print(f"  📊 PowerPoint deck: {result['presentation_path']}")
    console.print()


def main():
    _print_banner()

    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
    else:
        user_input = console.input("\n[bold]How can I help you prepare?[/bold]\n> ")

    if not user_input.strip():
        console.print("[red]Please provide a request, e.g.:[/red] Help me prepare for my meeting with Coca-Cola")
        sys.exit(1)

    asyncio.run(_run(user_input))


if __name__ == "__main__":
    main()
