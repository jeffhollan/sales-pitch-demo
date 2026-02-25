"""Quick test script for the deployed agent in Azure AI Foundry (streaming)."""

import sys

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

myEndpoint = "https://sales-presentation-project-resource.services.ai.azure.com/api/projects/sales-presentation-project"

project_client = AIProjectClient(
    endpoint=myEndpoint,
    credential=DefaultAzureCredential(),
)

myAgent = "sales-pres-agent"
myVersion = "3"

prompt = sys.argv[1] if len(sys.argv) > 1 else "Tell me what you can help with."

openai_client = project_client.get_openai_client()

print(f"Sending: {prompt!r}\n")

stream = openai_client.responses.create(
    input=[{"role": "user", "content": prompt}],
    extra_body={"agent": {"name": myAgent, "version": myVersion, "type": "agent_reference"}},
    stream=True,
)

for event in stream:
    etype = getattr(event, "type", "N/A")
    if etype == "response.output_text.delta":
        print(event.delta, end="", flush=True)
    elif etype == "response.completed":
        print()
    elif etype == "error":
        print(f"\nERROR: code={getattr(event, 'code', '?')} message={getattr(event, 'message', '?')}")
    elif etype not in (
        "response.created", "response.in_progress",
        "response.output_item.added", "response.content_part.added",
        "response.output_text.done", "response.content_part.done",
        "response.output_item.done",
    ):
        print(f"\n[{etype}] {event}")
