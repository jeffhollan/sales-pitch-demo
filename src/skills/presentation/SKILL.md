| name | description |
|------|-------------|
| presentation | Use this skill when the user asks to create a slide deck, presentation, or PowerPoint for a customer meeting. Triggers on phrases like "create a deck", "build a presentation", "make slides", "PowerPoint for [customer]", or any reference to .pptx output. |

# Presentation Generation

## Overview

Generate branded, customer-facing PowerPoint decks using the Microsoft Brand Template.
The `generate_presentation` tool handles all slide creation — your job is to ensure it
receives complete, accurate data.

## Prerequisites

Before calling `generate_presentation`, you MUST have all three IQ datasets:
- **work_iq** — call `get_work_iq_data` for relationship context
- **fabric_iq** — call `get_fabric_iq_data` for business metrics
- **foundry_iq** — call `get_foundry_iq_data` for sales plays and competitive intel

All three are required parameters. Do not call `generate_presentation` without them.

## Workflow

1. Ask or infer the customer name from the user's request
2. Call all three IQ tools for that customer (these can run in parallel)
3. Call `generate_presentation` with the customer name and all three IQ result dicts
4. Report the output file path to the user

## Design Notes

- The deck is **customer-facing** — no internal data (ticket IDs, team names, revenue targets)
- Customer references are anonymized (e.g., "PepsiCo" → "A leading CPG company")
- Slides use the customer's brand color as an accent bar
- The template produces 6 slides: Title, Partnership Overview, AI Success, Data Platform, Opportunities, Next Steps

## QA

After generation, confirm:
- The output path ends in `.pptx`
- You mention the file path so the user can find it
