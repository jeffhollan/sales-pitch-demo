"""Middleware — tool logging and doc-generation guardrails.

Demonstrates FunctionMiddleware from Agent Framework wrapping all Copilot SDK
tool calls without modifying any tool code.

Why "better together": The Copilot SDK has @define_tool and event callbacks,
but no middleware interception layer. Agent Framework's FunctionMiddleware wraps
all Copilot-invoked tools from a single file.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from agent_framework import (
    FunctionInvocationContext,
    FunctionMiddleware,
    MiddlewareTermination,
)

logger = logging.getLogger(__name__)


class ToolLoggingMiddleware(FunctionMiddleware):
    """Log every tool call: name, arguments, duration, and result size."""

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        name = context.function.name
        logger.info("[ToolLog] CALLING %s  args=%s", name, context.arguments)
        start = time.perf_counter()

        await call_next()

        elapsed = time.perf_counter() - start
        result_size = len(str(context.result)) if context.result is not None else 0
        logger.info(
            "[ToolLog] %s completed in %.2fs  result=%d chars",
            name,
            elapsed,
            result_size,
        )


class DocGenerationGuardrail(FunctionMiddleware):
    """Block generate_prep_doc / generate_presentation when IQ data is empty.

    Prevents the LLM from generating documents with hallucinated data by
    requiring all three data sources to be populated before document creation.
    """

    _GUARDED_TOOLS = frozenset({"generate_prep_doc", "generate_presentation"})
    _IQ_ARGS = ("work_iq", "fabric_iq", "foundry_iq")

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        if context.function.name not in self._GUARDED_TOOLS:
            await call_next()
            return

        # Normalize arguments to a dict regardless of Pydantic vs Mapping
        args = context.arguments
        if isinstance(args, dict):
            arg_dict = args
        elif hasattr(args, "model_dump"):
            arg_dict = args.model_dump()
        else:
            arg_dict = dict(args)

        missing = [a for a in self._IQ_ARGS if not arg_dict.get(a)]

        if missing:
            msg = (
                f"BLOCKED: {context.function.name} requires data for "
                f"{', '.join(missing)}. Gather the data first using the "
                f"corresponding IQ tools before generating documents."
            )
            logger.warning("[Guardrail] %s", msg)
            raise MiddlewareTermination(msg, result=msg)

        await call_next()
