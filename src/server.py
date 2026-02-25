"""Hosted Agent Adapter server entry point.

Wraps the SalesAgent orchestrator in a Starlette server exposing:
- POST /responses  — OpenAI Responses API format
- GET  /liveness   — health check
- GET  /readiness  — readiness check
"""

from azure.ai.agentserver.agentframework import from_agent_framework

from src.agent import create_orchestrator

app = from_agent_framework(create_orchestrator())


def main():
    app.run()


if __name__ == "__main__":
    main()
