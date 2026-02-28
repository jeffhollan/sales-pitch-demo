"""Workflow — parallel fan-out/fan-in data gathering for IQ sources.

Uses Agent Framework's WorkflowBuilder to run all 3 data sources in parallel,
then aggregates results for the Copilot-powered agent.

Why "better together": With the Copilot SDK alone, the LLM must sequentially
decide to call each tool. The Agent Framework's workflow graph gives you
deterministic parallel fan-out, then hands control back to the Copilot SDK's
LLM for the reasoning phase.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Annotated, Any, Never

from agent_framework import WorkflowBuilder, WorkflowContext, executor

from src.tools import get_fabric_iq_data, get_foundry_iq_data, get_work_iq_data

logger = logging.getLogger(__name__)


@dataclass
class CustomerRequest:
    customer_name: str
    request_text: str


@dataclass
class GatheredIntel:
    customer_name: str
    request_text: str
    work_iq: dict[str, Any] = field(default_factory=dict)
    fabric_iq: dict[str, Any] = field(default_factory=dict)
    foundry_iq: dict[str, Any] = field(default_factory=dict)


# ── Workflow executors ─────────────────────────────────────────────────


@executor
async def start_node(req: CustomerRequest, ctx: WorkflowContext[CustomerRequest]) -> None:
    """Entry point — stores request context in state and fans out."""
    ctx.set_state("customer_name", req.customer_name)
    ctx.set_state("request_text", req.request_text)
    await ctx.send_message(req)


@executor
async def gather_work_iq(req: CustomerRequest, ctx: WorkflowContext[dict]) -> None:
    """Fetch relationship context from Microsoft Graph."""
    logger.info("[Workflow] Gathering Work IQ for %s", req.customer_name)
    result = await asyncio.to_thread(get_work_iq_data, req.customer_name)
    await ctx.send_message({"source": "work_iq", "data": result})


@executor
async def gather_fabric_iq(req: CustomerRequest, ctx: WorkflowContext[dict]) -> None:
    """Fetch business metrics from Fabric."""
    logger.info("[Workflow] Gathering Fabric IQ for %s", req.customer_name)
    result = await asyncio.to_thread(get_fabric_iq_data, req.customer_name)
    await ctx.send_message({"source": "fabric_iq", "data": result})


@executor
async def gather_foundry_iq(req: CustomerRequest, ctx: WorkflowContext[dict]) -> None:
    """Fetch sales enablement materials from Foundry."""
    logger.info("[Workflow] Gathering Foundry IQ for %s", req.customer_name)
    result = await asyncio.to_thread(get_foundry_iq_data, req.customer_name)
    await ctx.send_message({"source": "foundry_iq", "data": result})


@executor
async def aggregate(messages: list[dict], ctx: WorkflowContext[Never, GatheredIntel]) -> None:
    """Fan-in aggregator — collects all IQ results into a single GatheredIntel."""
    intel = GatheredIntel(
        customer_name=ctx.get_state("customer_name", ""),
        request_text=ctx.get_state("request_text", ""),
    )

    for msg in messages:
        source = msg["source"]
        data = msg["data"]
        if source == "work_iq":
            intel.work_iq = data
        elif source == "fabric_iq":
            intel.fabric_iq = data
        elif source == "foundry_iq":
            intel.foundry_iq = data

    logger.info(
        "[Workflow] Aggregated — work_iq: %d chars, fabric_iq: %d chars, foundry_iq: %d chars",
        len(json.dumps(intel.work_iq, default=str)),
        len(json.dumps(intel.fabric_iq, default=str)),
        len(json.dumps(intel.foundry_iq, default=str)),
    )
    await ctx.yield_output(intel)


# ── Builder ────────────────────────────────────────────────────────────


def create_data_workflow():
    """Build the fan-out/fan-in workflow for parallel data gathering.

    Graph:
        start_node ──fan-out──> gather_work_iq   ─┐
                   ──fan-out──> gather_fabric_iq  ─┤──fan-in──> aggregate ──> GatheredIntel
                   ──fan-out──> gather_foundry_iq ─┘
    """
    return (
        WorkflowBuilder(start_executor=start_node, name="sales-prep-data-gather")
        .add_fan_out_edges(
            start_node,
            [gather_work_iq, gather_fabric_iq, gather_foundry_iq],
        )
        .add_fan_in_edges(
            [gather_work_iq, gather_fabric_iq, gather_foundry_iq],
            aggregate,
        )
        .build()
    )


# ── Tool wrapper ──────────────────────────────────────────────────────


async def run_meeting_prep_workflow(
    customer_name: Annotated[str, "Customer company name to research for meeting prep"],
) -> dict[str, Any]:
    """Run the parallel data-gathering workflow — fetches Work IQ, Fabric IQ,
    and Foundry IQ simultaneously, then returns the aggregated intelligence.
    Use this when preparing for a customer meeting to get all data at once."""
    workflow = create_data_workflow()
    result = await workflow.run(CustomerRequest(customer_name=customer_name, request_text=""))
    outputs = result.get_outputs()
    if not outputs:
        return {"error": "Workflow returned no outputs"}
    intel: GatheredIntel = outputs[0]
    return {
        "work_iq": intel.work_iq,
        "fabric_iq": intel.fabric_iq,
        "foundry_iq": intel.foundry_iq,
    }
