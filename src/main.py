"""Local CLI entry point for the Sales Prep Agent."""

from __future__ import annotations

import asyncio
import sys

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

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

    console.print("\n")
    console.print(Panel(
        Markdown(result["synthesis"]),
        title="[bold]Meeting Prep Synthesis[/bold]",
        border_style="green",
    ))

    console.print("\n[bold green]✓ Documents generated:[/bold green]")
    console.print(f"  📄 Word prep doc:  {result['prep_doc_path']}")
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
