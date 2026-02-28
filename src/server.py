"""Hosted Agent Server — wraps GitHubCopilotAgent in a FoundryCBAgent.

Subclasses FoundryCBAgent from azure-ai-agentserver-core to expose:
- POST /responses  — OpenAI Responses API format (SSE streaming)
- GET  /liveness   — health check
- GET  /readiness  — readiness check

The server is a thin adapter — the agent handles tool selection,
workflow invocation, and document generation autonomously.
"""

from __future__ import annotations

import datetime
import logging
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

# ── Enhancement 3: OpenTelemetry Observability ─────────────────────────
# One call enables distributed tracing across the entire stack — every
# workflow step, every tool call, every agent invocation.
try:
    from agent_framework.observability import configure_otel_providers
    configure_otel_providers(enable_sensitive_data=False)
    print("[SalesAgent] OpenTelemetry configured successfully", flush=True)
except Exception as exc:
    print(f"[SalesAgent] OpenTelemetry initialization skipped: {exc}", flush=True)

logger = logging.getLogger(__name__)


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

        # --- Diagnostic logging ---
        payload = context.raw_payload
        input_raw = payload.get("input", "")
        conv_id = getattr(context, "conversation_id", None)
        prev_resp_id = payload.get("previous_response_id", None)

        print(f"[SalesAgent] === Incoming Request ===", flush=True)
        print(f"[SalesAgent]   conversation_id: {conv_id}", flush=True)
        print(f"[SalesAgent]   response_id: {context.response_id}", flush=True)
        print(f"[SalesAgent]   previous_response_id: {prev_resp_id}", flush=True)
        print(f"[SalesAgent]   input type: {type(input_raw).__name__}", flush=True)

        if isinstance(input_raw, list):
            print(f"[SalesAgent]   input message count: {len(input_raw)}", flush=True)
            for i, m in enumerate(input_raw):
                if isinstance(m, dict):
                    role = m.get("role", "?")
                    mtype = m.get("type", "?")
                    content = m.get("content", "")
                    content_preview = str(content)[:100]
                    print(f"[SalesAgent]   input[{i}]: role={role} type={mtype} content_preview={content_preview!r}", flush=True)
        elif isinstance(input_raw, str):
            print(f"[SalesAgent]   input preview: {input_raw[:120]!r}", flush=True)
        print(f"[SalesAgent] === End Request Info ===", flush=True)
        # --- End diagnostic logging ---

        prompt = self._extract_prompt(payload)
        session = AgentSession()

        if context.stream:
            return self._stream_response(prompt, session, context)
        else:
            return await self._non_stream_response(prompt, session, context)

    # ── Streaming path ────────────────────────────────────────────────

    async def _stream_response(
        self, prompt: str, session: AgentSession, context: AgentRunContext
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
            error_text = f"\n\n[Error: {exc}]"
            accumulated_text += error_text
            yield ResponseTextDeltaEvent(
                sequence_number=self._next_seq(),
                item_id=item_id,
                output_index=0,
                content_index=0,
                delta=error_text,
            )

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
        self, prompt: str, session: AgentSession, context: AgentRunContext
    ) -> OpenAIResponse:
        """Run the agent and return a complete Response object."""
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
            messages = []
            for m in raw:
                if not isinstance(m, dict):
                    continue
                role = m.get("role", "user")
                content = m.get("content", "")
                if isinstance(content, list):
                    text = " ".join(
                        p.get("text", "") for p in content
                        if isinstance(p, dict) and p.get("type") in ("input_text", "output_text")
                    )
                elif isinstance(content, str):
                    text = content
                else:
                    text = str(content)
                if text.strip():
                    messages.append((role, text.strip()))
            if len(messages) <= 1:
                return messages[0][1] if messages else ""
            # Multiple messages — format with role labels for context
            parts = []
            for role, text in messages[:-1]:
                label = "User" if role == "user" else "Assistant"
                parts.append(f"[{label}]: {text}")
            parts.append(f"\nCurrent request:\n{messages[-1][1]}")
            return "Previous conversation:\n" + "\n".join(parts)
        return str(raw)


app = SalesAgentServer()


def main():
    app.run()


if __name__ == "__main__":
    main()
