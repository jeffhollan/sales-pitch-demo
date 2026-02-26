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
User ──► GitHub Copilot  ──► │                  │
              — or —         │  Orchestrator    │
Client ──► /responses    ──► │  (agent.py /     │
          (server.py)        │   server.py)     │
                              │                  │
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

The orchestrator is a `GitHubCopilotAgent` (from the Copilot Agent Framework SDK) that receives the user's natural-language request and autonomously decides which tools to call and in what order. The agent runs as a Starlette server (`src/server.py`) exposing an OpenAI Responses API–compatible `/responses` endpoint, which is the same interface used when deployed to Azure AI Foundry via the Hosted Agent Adapter.

## Project layout

```
├── src/
│   ├── server.py            # Hosted Agent Adapter server (`sales-prep-server`)
│   ├── invoke.py            # Local dev helper — calls the hosted server from CLI
│   ├── agent.py             # Orchestrator setup, system prompt, tool list
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

When the agent needs calendar data and no valid delegated token exists, it returns an `auth_required` response with a sign-in URL. The user signs in via browser, and the token is stored locally (`~/.sales-prep-demo-token.json`) or in Azure Blob Storage when `TOKEN_STORAGE_URL` is set.

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

### Run the server

Start the agent server (runs on `http://0.0.0.0:8088`):

```bash
uv run python -m src.server
```

The server exposes three endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/responses` | POST | Send a prompt to the agent (OpenAI Responses API format) |
| `/liveness` | GET | Health check |
| `/readiness` | GET | Readiness check |

To invoke the agent (in a separate terminal):

```bash
# Using the included dev helper (streams output with rich formatting)
uv run python -m src.invoke "Help me prepare for my meeting with Coca-Cola"

# Or with curl
curl -N -X POST http://localhost:8088/responses \
  -H "Content-Type: application/json" \
  -d '{"input": "Help me prepare for my meeting with Coca-Cola", "stream": true}'
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

## Test Customers

The following companies are pre-populated in mock data and can be used for demos and testing:

| Company | Industry | Annual Spend | Story |
|---------|----------|-------------|-------|
| Coca-Cola | Consumer Packaged Goods / Beverages | $12.4M | 8-year strategic partnership. Copilot expansion (5K→15K seats), Fabric growth, EA renewal March 15 |
| Contoso Ltd. | Technology / SaaS | $18.5M | Flagship account, pure upsell momentum — expanding AI Foundry into their own SaaS product |
| Fabrikam | Manufacturing / Industrial | $8.2M | Supply chain modernization, migrating from on-prem to Fabric + Azure. Competitive threat from AWS |
| Northwind Traders | Retail / E-commerce | $4.5M | Retail transformation, Dynamics 365-heavy. Expanding into Copilot for store operations |
| Woodgrove Bank | Financial Services / Banking | $22M | Largest account. Regulatory compliance focus, heavy Azure. Churn risk — evaluating Google Cloud |
| Adatum | Insurance / Financial Services | $6.8M | Legacy modernization from mainframe to Azure. Slow-moving but high potential |
| Tailwind Toys | Consumer Products / Toys | $2.1M | Fast-growing D2C brand. Small but expanding rapidly. Early Copilot adopter |
| Alpine Ski House | Hospitality / Tourism | $1.2M | Seasonal business, cost-conscious. Looking at AI for guest experience personalization |
| Bellows College | Higher Education | $3.5M | Education digital transformation. M365 A5 + Teams-heavy. Exploring Copilot for faculty |
| Relecloud | Media / Entertainment / Streaming | $15M | Streaming platform, Azure-heavy (AKS, CDN, Media Services). Building AI-powered content recommendations |
| Lamna Healthcare | Healthcare / Pharmaceuticals | $9.5M | HIPAA-compliant cloud strategy. Azure + Fabric for clinical analytics. P1 security incident in progress |

To test with any company:

```bash
uv run python -m src.invoke "Help me prepare for my meeting with Northwind Traders"
```
