"""Workflow orchestration — Copilot SDK-driven agent with streaming output.

The orchestrator agent receives the user's natural language request and
autonomously decides which tools to call. Output streams to the console via
run(stream=True), showing the agent's reasoning and tool invocations in real time.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from typing import Any

from rich.console import Console

from src.agent import create_orchestrator
from src.config import PROJECT_ROOT, TOKEN_STORAGE_URL

console = Console()

_AUTH_SERVER_SCRIPT = str(PROJECT_ROOT / "scripts" / "auth_server.py")


async def _poll_for_token(timeout: int = 120) -> bool:
    """Poll Azure Blob Storage for a fresh token write.

    Records the blob's last_modified timestamp before polling starts, then
    waits for it to change (or for the blob to appear if none existed). This
    ensures we only return True after the auth callback writes a new token,
    rather than picking up a stale token from a previous run.
    """
    from azure.storage.blob import BlobClient

    blob_client = BlobClient.from_blob_url(TOKEN_STORAGE_URL)
    deadline = asyncio.get_event_loop().time() + timeout

    # Snapshot the current last_modified time (if blob exists)
    initial_modified = None
    try:
        props = blob_client.get_blob_properties()
        initial_modified = props.last_modified
    except Exception:
        pass  # blob doesn't exist yet

    while asyncio.get_event_loop().time() < deadline:
        try:
            props = blob_client.get_blob_properties()
            # Wait for a NEW write (different last_modified than before polling)
            if props.last_modified != initial_modified:
                return True
        except Exception:
            pass
        await asyncio.sleep(3)

    return False


async def run_sales_prep(user_input: str) -> dict[str, Any]:
    """Execute the sales prep workflow.

    Args:
        user_input: Natural language request (e.g., "Help me prepare for my meeting with Coca-Cola")

    Returns:
        dict with keys: synthesis, and optionally prep_doc_path, presentation_path
    """
    from agent_framework import AgentSession

    orchestrator = create_orchestrator()
    session = AgentSession()

    console.print(f"\n[bold blue]Sales Prep Agent[/bold blue]\n")

    while True:
        collected_text: list[str] = []
        doc_paths: dict[str, str] = {}
        auth_required = False

        stream = orchestrator.run(user_input, stream=True, session=session)
        async for update in stream:
            for content in update.contents:
                if content.type == "text":
                    console.print(content.text, end="")
                    collected_text.append(content.text)

                elif content.type == "function_call":
                    console.print(f"\n  [dim]Calling {content.name}...[/dim]")

                elif content.type == "function_result":
                    console.print(f"  [green]\u2713[/green] [dim]{content.call_id} complete[/dim]")
                    result = content.result
                    if isinstance(result, str):
                        if result.endswith(".docx"):
                            doc_paths["prep_doc_path"] = result
                        elif result.endswith(".pptx"):
                            doc_paths["presentation_path"] = result
                        # Check if this function result contains auth_required
                        try:
                            parsed = json.loads(result)
                            if isinstance(parsed, dict) and parsed.get("auth_required"):
                                auth_required = True
                        except (json.JSONDecodeError, TypeError):
                            pass
                    elif isinstance(result, dict) and result.get("auth_required"):
                        auth_required = True

        console.print()  # newline after streaming

        if not auth_required:
            break

        from src.auth import clear_delegated_cache

        if TOKEN_STORAGE_URL:
            # Cloud: the agent's response already contains the auth URL.
            # Poll blob storage until the token appears.
            console.print("\n[dim]Waiting for authentication via browser...[/dim]")
            success = await _poll_for_token(timeout=120)
            if not success:
                console.print("[red]Authentication timed out.[/red]")
                break
        else:
            # Local: launch the auth server as a subprocess.
            # It opens the browser, handles the OAuth callback, saves the token, then exits.
            console.print("\n[bold yellow]Launching authentication server...[/bold yellow]")
            auth_proc = subprocess.Popen([sys.executable, _AUTH_SERVER_SCRIPT])
            try:
                auth_proc.wait(timeout=120)
            except subprocess.TimeoutExpired:
                auth_proc.kill()
                console.print("[red]Authentication timed out.[/red]")
                break

        # Clear in-memory cache so the retry picks up the fresh token.
        clear_delegated_cache()
        console.print("[green]Authentication successful — retrying...[/green]\n")
        user_input = "I've signed in. Please retry fetching my calendar data."

    return {
        "synthesis": "".join(collected_text),
        **doc_paths,
    }
