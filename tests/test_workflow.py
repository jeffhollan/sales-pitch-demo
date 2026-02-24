"""Tests for the sales prep workflow."""

import asyncio
import os

import pytest


@pytest.fixture(autouse=True)
def _mock_mode(monkeypatch):
    """Ensure tests run in mock mode."""
    monkeypatch.setenv("USE_MOCK_DATA", "true")
    # Patch the already-imported config constant so modules that read it
    # at import time (work_iq, fabric_iq, foundry_iq) see the override.
    import src.config
    monkeypatch.setattr(src.config, "USE_MOCK_DATA", True)
    import src.tools.work_iq
    monkeypatch.setattr(src.tools.work_iq, "USE_MOCK_DATA", True)
    import src.tools.fabric_iq
    monkeypatch.setattr(src.tools.fabric_iq, "USE_MOCK_DATA", True)
    import src.tools.foundry_iq
    monkeypatch.setattr(src.tools.foundry_iq, "USE_MOCK_DATA", True)


def test_extract_customer_name():
    from src.workflow import _extract_customer_name

    assert "Coca-Cola" in _extract_customer_name("Help me prepare for my meeting with Coca-Cola")
    assert "PepsiCo" in _extract_customer_name("Prep for PepsiCo")
    assert "Contoso" in _extract_customer_name("Prepare for my call with Contoso")


@pytest.mark.asyncio
async def test_run_sales_prep():
    from src.workflow import run_sales_prep

    result = await run_sales_prep("Help me prepare for my meeting with Coca-Cola")

    assert "coca-cola" in result["customer_name"].lower() or "coca" in result["customer_name"].lower()
    assert result["work_iq"].get("customer_name") == "The Coca-Cola Company"
    assert result["fabric_iq"].get("customer_name") == "The Coca-Cola Company"
    assert result["foundry_iq"].get("customer_name") == "The Coca-Cola Company"
    assert result["prep_doc_path"].endswith(".docx")
    assert result["presentation_path"].endswith(".pptx")
    assert os.path.exists(result["prep_doc_path"])
    assert os.path.exists(result["presentation_path"])


@pytest.mark.asyncio
async def test_parallel_execution():
    """Verify all three IQ queries run concurrently."""
    import time
    from unittest.mock import AsyncMock, patch

    from src.workflow import run_sales_prep

    # Track call times to verify concurrency
    call_times = []

    original_create = None

    async def slow_run(customer_name):
        call_times.append(time.monotonic())
        await asyncio.sleep(0.1)
        return {"customer_name": customer_name, "mock": True}

    with patch("src.workflow.create_agents") as mock_create:
        class SlowAgent:
            def __init__(self, name):
                self.name = name
            async def run(self, customer_name):
                return await slow_run(customer_name)

        mock_create.return_value = {
            "work_iq": SlowAgent("work-iq"),
            "fabric_iq": SlowAgent("fabric-iq"),
            "foundry_iq": SlowAgent("foundry-iq"),
        }

        start = time.monotonic()
        # This will fail on doc generation since we return minimal data,
        # but the parallel part is what we're testing
        try:
            await run_sales_prep("meeting with Test Corp")
        except Exception:
            pass
        elapsed = time.monotonic() - start

    # If queries ran in parallel, total should be ~0.1s not ~0.3s
    assert len(call_times) == 3
    # All three should have started within 50ms of each other
    assert max(call_times) - min(call_times) < 0.05
