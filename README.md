# Sales Prep Agent

An AI agent that autonomously researches a customer and generates meeting-ready documents.

## What it does

Give the agent a customer name (e.g. *"Help me prepare for my meeting with Coca-Cola"*) and it will:

1. Research across three data sources — email/calendar, business metrics, and sales enablement materials
2. Synthesize findings into actionable insights
3. Generate a **Word prep doc** (`.docx`) and a **branded PowerPoint deck** (`.pptx`)

Output files land in `output/`.

## Architecture

```
                         ┌─────────────────┐
User ──► CLI (main.py) ──► Orchestrator    │
                         │ (agent.py /     │
                         │  workflow.py)   │
                         └───────┬─────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                   │
              ▼                  ▼                   ▼
     ┌────────────────┐ ┌───────────────┐ ┌─────────────────┐
     │  Work IQ       │ │  Fabric IQ    │ │  Foundry IQ     │
     │  (Graph API)   │ │  (Fabric)     │ │  (AI Search)    │
     │  emails,       │ │  spend,       │ │  sales plays,   │
     │  calendar,     │ │  usage,       │ │  competitive    │
     │  Teams         │ │  tickets      │ │  intel           │
     └────────────────┘ └───────────────┘ └─────────────────┘
              │                  │                   │
              └──────────────────┼──────────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                                     ▼
     ┌────────────────┐                   ┌─────────────────┐
     │ generate_prep  │                   │ generate_       │
     │ _doc (.docx)   │                   │ presentation    │
     └────────────────┘                   │ (.pptx)         │
              │                           └─────────────────┘
              ▼                                     ▼
           output/                               output/
```

The orchestrator is a `GitHubCopilotAgent` (from the Copilot Agent Framework SDK) that receives the user's natural-language request and autonomously decides which tools to call and in what order.

## Project layout

```
├── src/
│   ├── main.py              # CLI entry point (`sales-prep` command)
│   ├── agent.py             # Orchestrator setup, system prompt, tool list
│   ├── workflow.py          # Streaming loop, auth retry logic
│   ├── auth.py              # Graph token helpers (Agent ID + legacy modes)
│   ├── config.py            # Env vars, paths, feature flags
│   ├── tools/
│   │   ├── work_iq.py       # Microsoft Graph — emails, calendar
│   │   ├── fabric_iq.py     # Business metrics — spend, usage, tickets
│   │   ├── foundry_iq.py    # Azure AI Search — sales plays, competitive intel
│   │   └── doc_generator.py # Word + PowerPoint generation
│   ├── mock_data/           # JSON fixtures for offline/demo mode
│   ├── skills/              # Copilot SDK skill directories
│   └── templates/           # Document templates
├── scripts/
│   ├── auth_server.py       # Local OAuth callback server
│   ├── provision_agent_id.py
│   ├── seed_search_index.py # Seed Azure AI Search with demo data
│   └── seed_graph_data.py
├── templates/
│   └── Microsoft_Brand_Template_May2023.potx  # PowerPoint brand template
├── tests/
├── output/                  # Generated documents appear here
├── pyproject.toml
├── .env.example
└── uv.lock
```

## The 5 tools

| Tool | Source | Returns |
|------|--------|---------|
| `get_work_iq_data` | Microsoft Graph API | Recent emails, calendar events, Teams messages, primary contact, and account team for a customer |
| `get_fabric_iq_data` | Microsoft Fabric | Contract details, spend/usage trends, support tickets, and expansion opportunities |
| `get_foundry_iq_data` | Azure AI Search | Sales plays, competitive intelligence, customer references, and enablement resources |
| `generate_prep_doc` | (local) | Generates a `.docx` Word meeting prep document with relationship context, business health, and recommended topics |
| `generate_presentation` | (local) | Generates a branded `.pptx` PowerPoint deck (6 slides) using the Microsoft brand template |

## Authentication

The agent supports **two auth modes** for Microsoft Graph, auto-detected from environment variables:

### Option A: Entra Agent ID (preview) — preferred

A two-step `client_credentials` flow via the Agent Identity Blueprint:

1. Blueprint credentials acquire a bootstrap token (T1)
2. T1 is exchanged as a `client_assertion` for a Graph app-only token

This mode is used for **Mail.Read**. For **Calendars.Read** (which requires delegated permissions under Agent ID), the agent uses a cached delegated token acquired via an interactive OAuth code flow (`scripts/auth_server.py`).

### Option B: Legacy app registration

A single-step `client_credentials` flow using a standard Entra app registration. Used as fallback when Agent ID env vars are not set.

### Delegated OAuth flow (calendar access)

When the agent needs calendar data and no valid delegated token exists, it:

1. Returns an `auth_required` response with a sign-in URL
2. The workflow loop detects this, launches the local auth server (or polls Azure Blob Storage in cloud mode)
3. The user signs in via browser
4. The workflow clears the in-memory token cache and retries the tool call automatically

Token storage is local by default (`~/.sales-prep-demo-token.json`) or Azure Blob Storage when `TOKEN_STORAGE_URL` is set.

## Getting started

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Setup

```bash
# Clone the repository
git clone <repo-url> && cd sales-pres-demo

# Copy env template
cp .env.example .env

# Install dependencies (core + agent SDK)
uv sync --extra agent --extra dev
```

### Run

```bash
# Via the CLI entry point
uv run sales-prep "Help me prepare for my meeting with Coca-Cola"

# Or interactively (will prompt for input)
uv run sales-prep
```

## Mock vs Live mode

The `USE_MOCK_DATA` flag in `.env` controls data sourcing:

| Mode | `USE_MOCK_DATA` | Behavior |
|------|-----------------|----------|
| **Mock** (default) | `true` | All three IQ tools read from JSON files in `src/mock_data/`. No credentials or network access required. |
| **Live** | `false` | Work IQ calls Microsoft Graph, Foundry IQ queries Azure AI Search. Fabric IQ falls back to mock data (no free-tier backend). Requires valid credentials in `.env`. |

Mock mode is useful for demos, development, and running tests without external dependencies.

## Running tests

```bash
uv run pytest tests/
```
