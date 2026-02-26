"""Quick test script for the deployed agent in Azure AI Foundry (streaming)."""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

myEndpoint = os.getenv(
    "AZURE_AI_PROJECT_ENDPOINT",
    "https://sales-presentation-project-resource.services.ai.azure.com/api/projects/sales-presentation-project",
)

myAgent = "sales-pres-agent"
myVersion = "20"


def stream_container_logs():
    """Stream container logs from the Azure AI Foundry logstream endpoint."""
    import httpx

    credential = DefaultAzureCredential()
    token = credential.get_token("https://ai.azure.com/.default")

    url = f"{myEndpoint}/agents/{myAgent}/versions/{myVersion}/containers/default:logstream"
    headers = {"Authorization": f"Bearer {token.token}"}

    print(f"Connecting to logstream: {url}\n")

    timeout = httpx.Timeout(connect=30.0, read=600.0, write=30.0, pool=30.0)
    try:
        with httpx.stream("GET", url, headers=headers, timeout=timeout) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                print(line, flush=True)
    except httpx.ReadTimeout:
        print("\n[logstream] Read timeout (server max connection time reached).")
    except httpx.RemoteProtocolError:
        print("\n[logstream] Connection closed (idle timeout — no new logs).")
    except httpx.HTTPStatusError as e:
        print(f"\n[logstream] HTTP error: {e.response.status_code} {e.response.text}")

    print("\n--- logstream ended ---")


def run_agent_test(prompt: str):
    """Run the streaming + non-streaming agent tests."""
    project_client = AIProjectClient(
        endpoint=myEndpoint,
        credential=DefaultAzureCredential(),
    )
    openai_client = project_client.get_openai_client()

    print(f"Sending: {prompt!r}\n")

    stream = openai_client.responses.create(
        input=[{"role": "user", "content": prompt}],
        extra_body={
            "agent_reference": {
                "name": myAgent,
                "version": myVersion,
                "type": "agent_reference",
            }
        },
        stream=True,
    )

    event_count = 0
    for event in stream:
        event_count += 1
        etype = getattr(event, "type", "N/A")
        if etype == "response.output_text.delta":
            print(event.delta, end="", flush=True)
        elif etype == "response.completed":
            print(f"\n[completed] output_text={event.response.output_text!r}")
        elif etype == "error":
            print(
                f"\nERROR: code={getattr(event, 'code', '?')} message={getattr(event, 'message', '?')}"
            )
        else:
            # Show all envelope events for debugging
            print(f"  [{event_count}] {etype}", flush=True)
            # Print raw event data for debugging
            if hasattr(event, "model_dump"):
                import json
                print(f"       {json.dumps(event.model_dump(), default=str)[:200]}", flush=True)

    print(f"\n--- stream ended after {event_count} event(s) ---")

    # Also try non-streaming to verify the agent works at all
    print("\n=== Non-streaming test ===")
    try:
        result = openai_client.responses.create(
            input=[{"role": "user", "content": "Hello"}],
            extra_body={
                "agent_reference": {
                    "name": myAgent,
                    "version": myVersion,
                    "type": "agent_reference",
                }
            },
            stream=False,
        )
        print(f"output_text: {result.output_text!r}")
    except Exception as e:
        print(f"Non-streaming error: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test deployed agent in Azure AI Foundry")
    parser.add_argument("--logs", action="store_true", help="Stream container logs instead of running agent test")
    parser.add_argument("prompt", nargs="?", default="Tell me what you can help with.", help="Prompt to send to the agent")
    args = parser.parse_args()

    if args.logs:
        stream_container_logs()
    else:
        run_agent_test(args.prompt)
