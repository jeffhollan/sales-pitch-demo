"""Local dev helper — invoke the hosted agent server from the command line.

Usage:
    python -m src.invoke "Help me prepare for my meeting with Coca-Cola"
"""

from __future__ import annotations

import json
import sys

import httpx
from rich.console import Console

console = Console()

SERVER_URL = "http://localhost:8088/responses"


def _stream_response(prompt: str):
    """POST to the agent server and stream SSE events to the console."""
    with httpx.Client(timeout=None) as client:
        with client.stream(
            "POST",
            SERVER_URL,
            json={"input": prompt, "stream": True},
            headers={"Accept": "text/event-stream"},
        ) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue

                payload = line.removeprefix("data: ").strip()
                if payload == "[DONE]":
                    break

                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    continue

                _handle_event(event)


def _handle_event(event: dict):
    """Pretty-print a single SSE event."""
    event_type = event.get("type", "")

    if event_type == "response.output_text.delta":
        # Streaming text chunk — print inline
        delta = event.get("delta", "")
        console.print(delta, end="", highlight=False)

    elif event_type == "response.output_text.done":
        # Text output complete
        console.print()

    elif event_type == "response.function_call_arguments.done":
        name = event.get("name", "unknown")
        console.print(f"\n[dim]  Tool call completed: {name}[/dim]")

    elif event_type == "response.completed":
        console.print("\n[green]Done.[/green]")


def main():
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        prompt = console.input("\n[bold]Enter your prompt:[/bold]\n> ")

    if not prompt.strip():
        console.print("[red]Please provide a prompt.[/red]")
        sys.exit(1)

    console.print(f"\n[dim]Sending to {SERVER_URL} …[/dim]\n")

    try:
        _stream_response(prompt)
    except httpx.ConnectError:
        console.print(
            "[red]Could not connect to the agent server.[/red]\n"
            f"[dim]Make sure it is running at {SERVER_URL}[/dim]"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
