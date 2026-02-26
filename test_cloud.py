"""Quick test script for the deployed agent in Azure AI Foundry (streaming)."""

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

project_client = AIProjectClient(
    endpoint=myEndpoint,
    credential=DefaultAzureCredential(),
)

myAgent = "sales-pres-agent"
myVersion = "19"

prompt = sys.argv[1] if len(sys.argv) > 1 else "Tell me what you can help with."

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
