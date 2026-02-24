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


def test_orchestrator_has_all_tools():
    """Verify the orchestrator (or fallback) is created with all expected tools."""
    from src.agent import create_orchestrator

    result = create_orchestrator()

    # If SDK is installed, we get a GitHubCopilotAgent with 5 tools
    if isinstance(result, dict):
        # Fallback mock agents — should have the 3 IQ agents
        assert "work_iq" in result
        assert "fabric_iq" in result
        assert "foundry_iq" in result
    else:
        # SDK agent — verify all 5 tools are registered
        tool_names = {t.to_dict()["name"] for t in result._tools}
        assert "get_work_iq_data" in tool_names
        assert "get_fabric_iq_data" in tool_names
        assert "get_foundry_iq_data" in tool_names
        assert "generate_prep_doc" in tool_names
        assert "generate_presentation" in tool_names


@pytest.mark.asyncio
async def test_run_sales_prep_legacy():
    """Test the legacy fallback pipeline (mock agents, no SDK)."""
    from unittest.mock import patch

    from src.workflow import run_sales_prep

    # Force the legacy path by making create_orchestrator return mock agents
    from src.agent import _create_mock_agents

    with patch("src.workflow.create_orchestrator", return_value=_create_mock_agents()):
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
async def test_run_sales_prep_streaming():
    """Test the SDK streaming path with a mock orchestrator."""
    from unittest.mock import MagicMock, patch

    from agent_framework import Content
    from src.workflow import run_sales_prep

    # Build mock Content objects using the real Content factory methods
    text_content = Content.from_text("Here is the synthesis.")
    call_content = Content.from_function_call(
        call_id="call_1", name="get_work_iq_data", arguments='{"customer_name": "Test"}'
    )
    result_content = Content.from_function_result(
        call_id="call_1", result="/tmp/test.docx"
    )
    pptx_content = Content.from_function_result(
        call_id="call_2", result="/tmp/test.pptx"
    )

    # Create mock updates
    update1 = MagicMock()
    update1.contents = [text_content]
    update2 = MagicMock()
    update2.contents = [call_content]
    update3 = MagicMock()
    update3.contents = [result_content]
    update4 = MagicMock()
    update4.contents = [pptx_content]

    # Create a mock agent that is NOT a dict (so it takes the SDK path)
    class MockCopilotAgent:
        def run(self, user_input, stream=False):
            async def _gen():
                for u in [update1, update2, update3, update4]:
                    yield u

            # Return an async iterable
            return _gen()

    with patch("src.workflow.create_orchestrator", return_value=MockCopilotAgent()):
        result = await run_sales_prep("meeting with Test Corp")

    assert result["synthesis"] == "Here is the synthesis."
    assert result["prep_doc_path"] == "/tmp/test.docx"
    assert result["presentation_path"] == "/tmp/test.pptx"
