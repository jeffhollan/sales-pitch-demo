"""Hosted Agent Server — wraps GitHubCopilotAgent in a FoundryCBAgent.

Subclasses FoundryCBAgent from azure-ai-agentserver-core to expose:
- POST /responses  — OpenAI Responses API format (SSE streaming)
- GET  /liveness   — health check
- GET  /readiness  — readiness check

The agent_run method delegates to GitHubCopilotAgent internally, then
converts the agent-framework streaming output into RAPI SSE events.
"""

from __future__ import annotations

import datetime
from typing import AsyncGenerator

from azure.ai.agentserver.core import FoundryCBAgent, AgentRunContext
from azure.ai.agentserver.core.models import Response as OpenAIResponse
from azure.ai.agentserver.core.models.projects import (
    ItemContentOutputText,
    ResponseCompletedEvent,
    ResponseContentPartAddedEvent,
    ResponseContentPartDoneEvent,
    ResponseCreatedEvent,
    ResponseInProgressEvent,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponsesAssistantMessageItemResource,
    ResponseStreamEvent,
    ResponseTextDeltaEvent,
    ResponseTextDoneEvent,
)

from agent_framework import AgentSession

from src.agent import create_orchestrator


class SalesAgentServer(FoundryCBAgent):
    """FoundryCBAgent adapter that runs GitHubCopilotAgent internally."""

    def __init__(self):
        super().__init__()
        self._orchestrator = create_orchestrator()
        self._started = False
        self._seq = 0

    def _next_seq(self) -> int:
        val = self._seq
        self._seq += 1
        return val

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
    ) -> AsyncGenerator[ResponseStreamEvent, None]:
        """Yield RAPI SSE events following the standard envelope sequence."""
        self._seq = 0
        item_id = context.id_generator.generate_message_id()
        now = datetime.datetime.now()
        accumulated_text = ""

        # --- Opening envelope ---
        yield ResponseCreatedEvent(
            sequence_number=self._next_seq(),
            response=self._build_response(context, "in_progress", now),
        )

        yield ResponseInProgressEvent(
            sequence_number=self._next_seq(),
            response=self._build_response(context, "in_progress", now),
        )

        # Output item (assistant message)
        item = ResponsesAssistantMessageItemResource(
            id=item_id,
            status="in_progress",
            content=[],
        )
        yield ResponseOutputItemAddedEvent(
            sequence_number=self._next_seq(),
            output_index=0,
            item=item,
        )

        # Content part (text)
        yield ResponseContentPartAddedEvent(
            sequence_number=self._next_seq(),
            item_id=item_id,
            output_index=0,
            content_index=0,
            part=ItemContentOutputText(text="", annotations=[]),
        )

        # --- Stream agent output ---
        print(f"[SalesAgent] Starting agent stream for prompt: {prompt[:80]!r}", flush=True)
        session = AgentSession()
        update_count = 0
        try:
            stream = self._orchestrator.run(prompt, stream=True, session=session)
            async for update in stream:
                update_count += 1
                text = update.text
                if text:
                    accumulated_text += text
                    yield ResponseTextDeltaEvent(
                        sequence_number=self._next_seq(),
                        item_id=item_id,
                        output_index=0,
                        content_index=0,
                        delta=text,
                    )
        except Exception as exc:
            print(f"[SalesAgent] Stream ERROR after {update_count} updates: {exc!r}", flush=True)
            raise

        print(f"[SalesAgent] Stream ended after {update_count} updates, accumulated {len(accumulated_text)} chars", flush=True)

        # --- Closing envelope ---
        yield ResponseTextDoneEvent(
            sequence_number=self._next_seq(),
            item_id=item_id,
            output_index=0,
            content_index=0,
            text=accumulated_text,
        )

        yield ResponseContentPartDoneEvent(
            sequence_number=self._next_seq(),
            item_id=item_id,
            output_index=0,
            content_index=0,
            part=ItemContentOutputText(text=accumulated_text, annotations=[]),
        )

        done_item = ResponsesAssistantMessageItemResource(
            id=item_id,
            status="completed",
            content=[ItemContentOutputText(text=accumulated_text, annotations=[])],
        )
        yield ResponseOutputItemDoneEvent(
            sequence_number=self._next_seq(),
            output_index=0,
            item=done_item,
        )

        yield ResponseCompletedEvent(
            sequence_number=self._next_seq(),
            response=self._build_response(
                context, "completed", now, output=[done_item]
            ),
        )

    # ── Non-streaming path ────────────────────────────────────────────

    async def _non_stream_response(
        self, prompt: str, context: AgentRunContext
    ) -> OpenAIResponse:
        """Run the agent and return a complete Response object."""
        session = AgentSession()
        result = await self._orchestrator.run(prompt, session=session)
        text = result.text or "(No response text was produced by the agent.)"
        item_id = context.id_generator.generate_message_id()
        return OpenAIResponse(
            id=context.response_id,
            created_at=datetime.datetime.now(),
            output=[
                ResponsesAssistantMessageItemResource(
                    id=item_id,
                    status="completed",
                    content=[
                        ItemContentOutputText(text=text, annotations=[]),
                    ],
                )
            ],
        )

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _build_response(
        context: AgentRunContext,
        status: str,
        created_at: datetime.datetime,
        output: list | None = None,
    ) -> OpenAIResponse:
        return OpenAIResponse({
            "object": "response",
            "id": context.response_id,
            "status": status,
            "created_at": created_at,
            "output": output or [],
        })

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
