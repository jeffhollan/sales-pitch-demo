"""Hosted Agent Server — wraps GitHubCopilotAgent in a FoundryCBAgent.

Subclasses FoundryCBAgent from azure-ai-agentserver-core to expose:
- POST /responses  — OpenAI Responses API format (SSE streaming)
- GET  /liveness   — health check
- GET  /readiness  — readiness check

The agent_run method delegates to GitHubCopilotAgent internally, then
converts the agent-framework streaming output into RAPI SSE events.
"""

from __future__ import annotations

import time
from typing import AsyncGenerator

from azure.ai.agentserver.core import FoundryCBAgent, AgentRunContext
from azure.ai.agentserver.core.models import projects as rapi

from agent_framework import AgentSession

from src.agent import create_orchestrator


class SalesAgentServer(FoundryCBAgent):
    """FoundryCBAgent adapter that runs GitHubCopilotAgent internally."""

    def __init__(self):
        super().__init__()
        self._orchestrator = create_orchestrator()
        self._started = False

    async def agent_run(self, context: AgentRunContext):
        if not self._started:
            await self._orchestrator.start()
            self._started = True

        prompt = self._extract_prompt(context.raw_payload)

        if context.stream:
            return self._stream_response(prompt, context)
        else:
            return await self._non_stream_response(prompt, context)

    # ── Streaming path ────────────────────────────────────────────────

    async def _stream_response(
        self, prompt: str, context: AgentRunContext
    ) -> AsyncGenerator[rapi.ResponseStreamEvent, None]:
        """Yield RAPI SSE events following the standard envelope sequence."""
        seq = 0
        item_id = context.id_generator.generate_message_id()
        now = int(time.time())
        accumulated_text = ""

        # --- Opening envelope ---
        response_obj = self._make_response(context, "in_progress", now)

        yield rapi.ResponseCreatedEvent(
            {"sequence_number": seq, "response": response_obj}
        )
        seq += 1

        yield rapi.ResponseInProgressEvent(
            {"sequence_number": seq, "response": response_obj}
        )
        seq += 1

        # Output item (assistant message)
        item = {
            "type": "message",
            "id": item_id,
            "role": "assistant",
            "status": "in_progress",
            "content": [],
        }
        yield rapi.ResponseOutputItemAddedEvent(
            {"sequence_number": seq, "output_index": 0, "item": item}
        )
        seq += 1

        # Content part (text)
        yield rapi.ResponseContentPartAddedEvent(
            {
                "sequence_number": seq,
                "item_id": item_id,
                "output_index": 0,
                "content_index": 0,
                "part": {"type": "output_text", "text": ""},
            }
        )
        seq += 1

        # --- Stream agent output ---
        session = AgentSession()
        stream = self._orchestrator.run(prompt, stream=True, session=session)
        async for update in stream:
            text = update.text
            if text:
                accumulated_text += text
                yield rapi.ResponseTextDeltaEvent(
                    {
                        "sequence_number": seq,
                        "item_id": item_id,
                        "output_index": 0,
                        "content_index": 0,
                        "delta": text,
                    }
                )
                seq += 1

        # --- Closing envelope ---
        yield rapi.ResponseTextDoneEvent(
            {
                "sequence_number": seq,
                "item_id": item_id,
                "output_index": 0,
                "content_index": 0,
                "text": accumulated_text,
            }
        )
        seq += 1

        yield rapi.ResponseContentPartDoneEvent(
            {
                "sequence_number": seq,
                "item_id": item_id,
                "output_index": 0,
                "content_index": 0,
                "part": {"type": "output_text", "text": accumulated_text},
            }
        )
        seq += 1

        done_item = {
            "type": "message",
            "id": item_id,
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": accumulated_text}],
        }
        yield rapi.ResponseOutputItemDoneEvent(
            {"sequence_number": seq, "output_index": 0, "item": done_item}
        )
        seq += 1

        completed_response = self._make_response(
            context, "completed", now, output=[done_item]
        )
        yield rapi.ResponseCompletedEvent(
            {"sequence_number": seq, "response": completed_response}
        )

    # ── Non-streaming path ────────────────────────────────────────────

    async def _non_stream_response(
        self, prompt: str, context: AgentRunContext
    ) -> rapi.Response:
        """Run the agent and return a complete Response object."""
        session = AgentSession()
        result = await self._orchestrator.run(prompt, session=session)
        text = result.text or ""
        now = int(time.time())
        item_id = context.id_generator.generate_message_id()
        output = [
            {
                "type": "message",
                "id": item_id,
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": text}],
            }
        ]
        return self._make_response(context, "completed", now, output=output)

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _make_response(
        context: AgentRunContext,
        status: str,
        created_at: int,
        output: list | None = None,
    ) -> dict:
        return {
            "id": context.response_id,
            "object": "response",
            "status": status,
            "created_at": created_at,
            "output": output or [],
        }

    @staticmethod
    def _extract_prompt(payload: dict) -> str:
        raw = payload.get("input", "")
        if isinstance(raw, str):
            return raw
        if isinstance(raw, list):
            parts = []
            for m in raw:
                if isinstance(m, dict):
                    content = m.get("content", "")
                    if isinstance(content, str):
                        parts.append(content)
                    elif isinstance(content, list):
                        parts.extend(
                            p.get("text", "")
                            for p in content
                            if isinstance(p, dict) and p.get("type") == "input_text"
                        )
            return "\n".join(parts)
        return str(raw)


app = SalesAgentServer()


def main():
    app.run()


if __name__ == "__main__":
    main()
