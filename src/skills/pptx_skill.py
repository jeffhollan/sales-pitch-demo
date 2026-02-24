"""Standalone MCP server exposing PowerPoint generation as a skill.

Run as:
    python -m src.skills.pptx_skill

Connect from any MCP client via:
    {"command": "python", "args": ["-m", "src.skills.pptx_skill"]}

This is the key demo pattern: a capability (PowerPoint generation) packaged as
a portable skill that the Copilot SDK, VS Code Copilot, or any MCP client can
consume.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Import the actual generation logic
from src.tools.doc_generator import generate_presentation as _generate_presentation
from src.config import PPTX_TEMPLATE

mcp = FastMCP(
    "pptx-skill",
    description="Generate branded PowerPoint presentations using the Microsoft Brand Template",
)


@mcp.tool()
def generate_presentation(
    customer_name: str,
    work_iq_json: str,
    fabric_iq_json: str,
    foundry_iq_json: str,
) -> str:
    """Generate a branded PowerPoint presentation for a customer meeting.

    Args:
        customer_name: Customer company name (e.g. "Coca-Cola")
        work_iq_json: Work IQ data as a JSON string (emails, meetings, contacts)
        fabric_iq_json: Fabric IQ data as a JSON string (spend, usage, tickets)
        foundry_iq_json: Foundry IQ data as a JSON string (sales plays, references)

    Returns:
        Path to the generated .pptx file
    """
    work_iq = json.loads(work_iq_json)
    fabric_iq = json.loads(fabric_iq_json)
    foundry_iq = json.loads(foundry_iq_json)
    path = _generate_presentation(customer_name, work_iq, fabric_iq, foundry_iq)
    return f"Presentation saved to {path}"


@mcp.tool()
def list_templates() -> str:
    """List available PowerPoint templates.

    Returns:
        JSON array of template info objects.
    """
    templates = []
    template_dir = PPTX_TEMPLATE.parent
    for p in sorted(template_dir.glob("*.potx")):
        templates.append({
            "name": p.stem,
            "path": str(p),
            "size_bytes": p.stat().st_size,
        })
    return json.dumps(templates, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
