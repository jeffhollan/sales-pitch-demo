"""Hosted Agent Adapter server entry point.

Wraps the SalesAgent orchestrator in a Starlette server exposing:
- POST /responses  — OpenAI Responses API format
- GET  /liveness   — health check
- GET  /readiness  — readiness check
"""

# Shim: azure-ai-agentserver-agentframework <=1.0.0b14 imports
# AgentProtocol, which was renamed to Agent in agent-framework-core RC1.
import agent_framework as _af
if not hasattr(_af, "AgentProtocol"):
    _af.AgentProtocol = _af.Agent

from azure.ai.agentserver.agentframework import from_agent_framework

from src.agent import create_orchestrator

app = from_agent_framework(create_orchestrator())


def main():
    app.run()


if __name__ == "__main__":
    main()
