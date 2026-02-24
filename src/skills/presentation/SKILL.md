| name | description |
|------|-------------|
| presentation | Use this skill when the user asks to create a slide deck, presentation, or PowerPoint for a customer meeting. Triggers on phrases like "create a deck", "build a presentation", "make slides", "PowerPoint for [customer]", or any reference to .pptx output. |

# Presentation Generation

## Overview

Generate branded, customer-facing PowerPoint decks using the Microsoft Brand Template.
The `generate_presentation` tool handles all slide creation — your job is to ensure it
receives complete, accurate data.

---

## Design System

### Brand Colors

| Token | Hex | RGB | Usage |
|-------|-----|-----|-------|
| `MS_BLUE` | `#0078D4` | (0, 120, 212) | Primary Microsoft accent — stat numbers, headings, subheads |
| `MS_DARK` | `#242424` | (36, 36, 36) | Body text on light backgrounds |
| `MS_GRAY` | `#606060` | (96, 96, 96) | Secondary text — dates, captions, descriptions |
| `MS_LIGHT_GRAY` | `#C8C8C8` | (200, 200, 200) | Dividers, subtle borders |
| White | `#FFFFFF` | (255, 255, 255) | Text on colored cards/bars |
| Dark body | `#333333` | (51, 51, 51) | Info card body text, peer reference descriptions |

**Customer brand color** — loaded from `mock_data/brands.json` via `_load_brand()`. The customer's `primary_color` is used as the accent bar color on every slide and as the third stat card color on Slide 2. If no brand match is found, falls back to `#0078D4`.

### Typography

| Element | Font Size (pt) | Bold | Color |
|---------|---------------|------|-------|
| Slide title (placeholder) | 28–36 | Yes | Template default |
| Subtitle / date | 14–20 | No | `#606060` |
| Stat card number | 44 | Yes | `#FFFFFF` |
| Stat card label | 12 | No | `#FFFFFF` |
| Section heading (right half) | 14 | Yes | `#333333` |
| Body text | 11–13 | No | `#333333` or `#606060` |
| Opportunity subhead | 14 | Yes | `MS_BLUE` |
| Opportunity body | 11 | No | Template default |
| Closing bar text | 14 | Yes | `#FFFFFF` |

### Spacing Conventions

- **Slide width**: 13.333 inches (standard widescreen)
- **Accent bar**: full-width (`0, 0, 13.333, 0.04`) — a thin colored strip at the very top of every slide
- **Content margins**: left content starts at ~0.8 in, right content at ~7.0 in
- **Left/right split**: left half 0.8–6.2 in, right half 7.0–12.5 in
- **Stat cards**: 2.8 × 1.5 in with 0.3 in gaps, centered horizontally
- **Info cards**: internal padding of 0.15 in on all sides
- **Vertical rhythm**: ~0.85 in between stacked callout rows, ~1.1 in between info cards

---

## Component Library

Five reusable building blocks used across all slides:

### `_add_accent_bar(slide, left, top, width, height, color_hex)`

Colored rectangle (MSO_SHAPE.RECTANGLE) with no border. Used at the top of every slide and as the closing bar on Slide 6.

- **Typical top-of-slide call**: `_add_accent_bar(slide, 0, 0, 13.333, 0.04, primary)`
- **Closing bar (Slide 6)**: `_add_accent_bar(slide, 0, 6.8, 13.333, 0.5, primary)`

### `_add_text_box(slide, left, top, width, height, text, font_size=14, bold=False, color=None, alignment=LEFT)`

Positioned text box with word wrap enabled. Returns the text frame for further manipulation. Color accepts hex string or RGB tuple.

### `_add_stat_card(slide, left, top, width, height, stat_text, label_text, color_hex)`

A colored rectangle card with two overlaid text boxes:
- **Big number**: positioned at `(left+0.15, top+0.2)`, size `(width-0.3, 0.65)`, 44pt bold white, center-aligned
- **Label**: positioned at `(left+0.15, top+0.85)`, size `(width-0.3, 0.55)`, 12pt white, center-aligned

### `_add_info_card(slide, left, top, width, height, text, font_size=11, bg_color=None)`

A light-gray (default `(235, 235, 235)`) rectangle card with a body text box inset by 0.15 in on all sides. Text color is `#333333`. The `bg_color` parameter accepts an RGB tuple — used for the light-blue "Our Commitment" card `(220, 235, 250)`.

### `_set_placeholder_text(slide, idx, text, font_size=None, bold=None, color=None)`

Writes text into a template placeholder by its index. Clears existing content first. Used for titles, subtitles, and column content on template-defined layouts.

---

## Template & Layout Reference

**Template file**: `Microsoft_Brand_Template_May2023.potx`

The template is loaded via `_load_template()` which patches the .potx → .pptx content types and strips sample slides, keeping only layouts and masters.

### Layout Indices

| Index | Internal Name | Used For | Key Placeholder IDs |
|-------|--------------|----------|-------------------|
| 0 | `1_Title_Gradient_Warm Gray` | Slide 1 — Title | 0 (title), 12 (subtitle), 13 (date), 14 (prepared-for) |
| 29 | `Blank_with Head` | Slides 2, 3, 4 — custom content | 0 (title only) |
| 23 | `3-column_Text_with Subheads` | Slide 5 — Opportunities | 0 (title), 16/15 (col1 sub/body), 22/23 (col2 sub/body), 24/25 (col3 sub/body) |
| 19 | `1_1-column_Text` | Slide 6 — Next Steps | 0 (title), 16 (subhead, optional), 15 (body) |

---

## Slide-by-Slide Blueprint

### Slide 1 — Title

**Layout**: `_LAYOUT_TITLE` (index 0)

| Element | Position | Details |
|---------|----------|---------|
| Accent bar | `(0, 0, 13.333, 0.04)` | Customer `primary_color` |
| Title (ph 0) | Template-positioned | `"Powering {display_name}'s Digital Transformation"` — 36pt bold |
| Subtitle (ph 12) | Template-positioned | `"Microsoft + {display_name} Partnership Review"` — 20pt |
| Date (ph 13) | Template-positioned | `"February 2026"` format — 14pt `#606060` |
| Prepared for (ph 14) | Template-positioned | `"Prepared for {name}, {title}"` — 12pt `#606060` |

**Data sources**: `work_iq.primary_contact.name`, `work_iq.primary_contact.title`, brand `display_name`

### Slide 2 — Our Partnership at a Glance

**Layout**: `_LAYOUT_BLANK_HEAD` (index 29)

| Element | Position | Details |
|---------|----------|---------|
| Accent bar | `(0, 0, 13.333, 0.04)` | Customer `primary_color` |
| Title (ph 0) | Template-positioned | `"Our Partnership at a Glance"` — 28pt bold |
| 4 stat cards | Centered row at y=2.0 | Each 2.8 × 1.5 in, 0.3 in gaps |
| Summary text | `(1.0, card_top + 1.9, 11.333, 0.6)` | 13pt `#606060`, center-aligned |

**Stat cards** (left to right):

| # | Stat | Label | Color |
|---|------|-------|-------|
| 1 | Tenure (e.g., "5 Years") | "Strategic Partnership" | `MS_BLUE` |
| 2 | M365 user count | "Users on Microsoft 365" | `MS_BLUE` |
| 3 | Product count | "Microsoft Products" | Customer `primary_color` |
| 4 | Copilot user count | "Users with AI Copilot" | `MS_BLUE` |

**Card centering formula**: `start_left = (13.333 - (4 × 2.8 + 3 × 0.3)) / 2`

**Data source**: `_get_partnership_stats(work_iq, fabric_iq)` — extracts tenure from `relationship_summary` regex, seat counts from `fabric_iq.contract.products`

### Slide 3 — Your Success with AI

**Layout**: `_LAYOUT_BLANK_HEAD` (index 29)

**Left half** — 3 stacked stat callouts starting at y=1.8, spaced 0.85 in apart:

| Stat | Font Size | Description |
|------|-----------|-------------|
| Adoption % (e.g., "72%") | 44pt bold `MS_BLUE` | "Copilot adoption across your organization" |
| Actions/user (e.g., "142") | 36pt bold `MS_BLUE` | "AI-assisted actions per user, per month" |
| Satisfaction (e.g., "4.3 / 5.0") | 36pt bold `MS_BLUE` | "User satisfaction score" |

Stat at `(0.8, y, 2.0, 0.55)`, description at `(2.9, y+0.05, 3.3, 0.5)` — 12pt `#333333`

**Right half** — Peer reference section:

| Element | Position | Details |
|---------|----------|---------|
| Section heading | `(7.0, 1.8, 5.5, 0.35)` | `"What Your Peers Are Seeing"` — 14pt bold `#333333` |
| Peer cards (up to 2) | `(7.0, 2.3, 5.5, 0.9)` | Info cards spaced 1.1 in apart, 11pt `#333333` on light-gray |

**Data source**: `_get_copilot_highlights(fabric_iq, foundry_iq)` — adoption %, actions/user, satisfaction from `fabric_iq.usage_trends.m365_copilot`, peer references from `foundry_iq.sales_plays[0].customer_references` (anonymized)

### Slide 4 — Your Data Platform in Action

**Layout**: `_LAYOUT_BLANK_HEAD` (index 29)

**Left half** — hero stat and workload list:

| Element | Position | Details |
|---------|----------|---------|
| Big stat | `(0.8, 1.9, 3.5, 0.7)` | Monthly queries — 44pt bold `MS_BLUE` |
| Stat label | `(0.8, 2.55, 3.5, 0.4)` | `"queries per month"` — 14pt `#333333` |
| Workload list | `(0.8, 3.2, 5.0, 1.2)` | Bullet list of top workloads — 12pt `#606060` |

**Right half** — growth narrative:

| Element | Position | Details |
|---------|----------|---------|
| Section heading | `(7.0, 1.9, 5.5, 0.35)` | `"Scaling for Growth"` — 14pt bold `#333333` |
| Growth paragraph | `(7.0, 2.35, 5.5, 0.7)` | Utilization narrative — 11pt `#606060` |
| Commitment card | `(7.0, 3.2, 5.5, 1.1)` | Info card with light-blue bg `(220, 235, 250)`, `"Our Commitment\n\n{commitment}"` — 11pt |

**Data source**: `_get_fabric_highlights(fabric_iq, foundry_iq)` — queries, workloads, utilization from `fabric_iq.usage_trends.fabric`, commitment from Fabric-related sales play talking points

### Slide 5 — Opportunities Ahead

**Layout**: `_LAYOUT_3COL_SUBHEADS` (index 23)

| Element | Placeholder IDs | Details |
|---------|----------------|---------|
| Accent bar | `(0, 0, 13.333, 0.04)` | Customer `primary_color` |
| Title (ph 0) | 0 | `"Opportunities Ahead"` — 28pt bold |
| Column 1 subhead / body | 16 / 15 | "AI Copilot for All" — 14pt bold `MS_BLUE` / body 11pt |
| Column 2 subhead / body | 22 / 23 | "Intelligent Data Platform" — 14pt bold `MS_BLUE` / body 11pt |
| Column 3 subhead / body | 24 / 25 | "AI for Operations" — 14pt bold `MS_BLUE` / body 11pt |

**Data source**: `_get_opportunities(fabric_iq, foundry_iq)` — builds 3 opportunity columns with:
- Copilot expansion savings projection (regex-extracted from talking points, default `$3.2M`)
- Data platform scaling with anonymized peer reference
- AI operations with anonymized peer reference

### Slide 6 — Recommended Next Steps

**Layout**: `_LAYOUT_1COL_TEXT` (index 19)

| Element | Position / Placeholder | Details |
|---------|----------------------|---------|
| Accent bar | `(0, 0, 13.333, 0.04)` | Customer `primary_color` |
| Title (ph 0) | 0 | `"Recommended Next Steps"` — 28pt bold |
| Subhead (ph 16) | 16 (optional, try/except) | `"How we move forward together"` — 16pt `#606060` |
| Steps body (ph 15) | 15 | 4 numbered steps joined with `\n\n` — 13pt |
| Closing bar | `(0, 6.8, 13.333, 0.5)` | Customer `primary_color` |
| Closing text | `(0.5, 6.85, 12.333, 0.4)` | `"Thank you for your continued partnership, {display_name}."` — 14pt bold white, centered |

**Data source**: `_get_next_steps()` — 4 static action items:
1. Copilot Expansion Business Case — ROI analysis
2. Data Platform Performance Optimization — engineering improvements
3. AI Strategy Workshop — half-day AI briefing
4. Follow-Up — summary within 48 hours

---

## Data Extraction Patterns

The tool transforms raw IQ data into customer-facing content through these helpers:

### `_get_partnership_stats(work_iq, fabric_iq)`

| Output Key | Source | Extraction |
|-----------|--------|------------|
| `tenure` | `work_iq.relationship_summary` | Regex `(\d+)-year` → `"{n} Years"`, fallback `"Partners"` |
| `m365_users` | `fabric_iq.contract.products` | First product matching `"365 E5"` or `"365 E3"` → formatted seat count |
| `product_count` | `fabric_iq.contract.products` | `len(products)` |
| `copilot_users` | `fabric_iq.contract.products` | First product matching `"Copilot"` → formatted seat count |
| `summary` | Computed | Template string referencing product count |

### `_get_copilot_highlights(fabric_iq, foundry_iq)`

| Output Key | Source | Extraction |
|-----------|--------|------------|
| `adoption_pct` | `fabric_iq.usage_trends.m365_copilot.active_users_pct` | Formatted as `"{n}%"` |
| `actions_per_user` | `fabric_iq.usage_trends.m365_copilot.monthly_actions_per_user` | String |
| `satisfaction` | `fabric_iq.usage_trends.m365_copilot.satisfaction_score` | Formatted as `"{n} / 5.0"` |
| `peers` | `foundry_iq.sales_plays[0].customer_references[:2]` | Anonymized via `_anonymize_reference()` |

### `_get_fabric_highlights(fabric_iq, foundry_iq)`

| Output Key | Source | Extraction |
|-----------|--------|------------|
| `monthly_queries` | `fabric_iq.usage_trends.fabric.monthly_queries` | Formatted with commas |
| `workloads` | `fabric_iq.usage_trends.fabric.top_workloads` | List of strings |
| `utilization_pct` | `fabric_iq.usage_trends.fabric.capacity_utilization_pct` | Integer |
| `commitment` | `foundry_iq.sales_plays` | First Fabric play's talking point containing "optimization" or "Delta Lake"; fallback text provided |

### `_get_opportunities(fabric_iq, foundry_iq)`

Returns a list of 3 opportunity dicts (`subhead` + `body`):

1. **AI Copilot for All** — references M365 seat count, adoption %, projected savings (regex `\$[\d.]+M` from talking points, default `$3.2M`)
2. **Intelligent Data Platform** — burst capacity, Real-Time Intelligence, anonymized peer reference
3. **AI for Operations** — quality inspection, demand forecasting, supply chain, anonymized peer reference

### `_get_next_steps()`

Returns 4 static formatted strings — no data dependencies.

---

## Anonymization Rules

All customer references in peer comparisons are anonymized via `_anonymize_reference()`:

| Real Company | Anonymized Label |
|-------------|-----------------|
| PepsiCo | "A leading CPG company" |
| Nestlé | "Another global CPG leader" |
| AB InBev | "A global brewer" |
| Danone | "A global food & beverage company" |
| Procter & Gamble | "A leading consumer goods company" |
| *(unknown)* | "A leading enterprise" |

**What is always omitted from the deck** (internal-only data):
- Support ticket IDs and details
- Internal team names and account team members
- Confidence scores on expansion opportunities
- Revenue targets and financial summaries
- Renewal risk assessments
- Incremental dollar values for opportunities

---

## Orchestration Workflow

### Prerequisites

Before calling `generate_presentation`, you MUST have all three IQ datasets:
- **work_iq** — call `get_work_iq_data` for relationship context
- **fabric_iq** — call `get_fabric_iq_data` for business metrics
- **foundry_iq** — call `get_foundry_iq_data` for sales plays and competitive intel

All three are required parameters. Do not call `generate_presentation` without them.

### Workflow

1. Ask or infer the customer name from the user's request
2. Call all three IQ tools for that customer (these can run in parallel)
3. Call `generate_presentation` with the customer name and all three IQ result dicts
4. Report the output file path to the user

### QA

After generation, confirm:
- The output path ends in `.pptx`
- You mention the file path so the user can find it
