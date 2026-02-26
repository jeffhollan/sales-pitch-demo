#!/usr/bin/env python3
"""One-time script: seed the M365 dev tenant mailbox with demo emails and calendar events.

Usage:
    python -m scripts.seed_graph_data

Requires Graph auth env vars in .env (Agent ID or legacy app registration).
The identity must have Mail.ReadWrite application permission with admin consent.
Calendar seeding uses the same token — works with the legacy app registration;
with Agent ID it requires Calendars.ReadWrite (which may need delegated flow).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

from src.auth import _get_legacy_token, get_graph_token  # noqa: E402
from src.config import GRAPH_USER_ID  # noqa: E402

USER_ID = GRAPH_USER_ID

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ── Timestamp helpers ────────────────────────────────────────────────────
now = datetime.now(timezone.utc)


def _received(days_ago: int) -> str:
    return (now - timedelta(days=days_ago)).isoformat()


def _event_start(days_ago: int, hour: int = 10) -> dict[str, str]:
    return {
        "dateTime": (now - timedelta(days=days_ago)).strftime(f"%Y-%m-%dT{hour:02d}:00:00"),
        "timeZone": "UTC",
    }


def _event_end(days_ago: int, hour: int = 11) -> dict[str, str]:
    return {
        "dateTime": (now - timedelta(days=days_ago)).strftime(f"%Y-%m-%dT{hour:02d}:00:00"),
        "timeZone": "UTC",
    }


def _email(subject: str, content: str, from_name: str, from_addr: str, days_ago: int) -> dict:
    return {
        "subject": subject,
        "body": {"contentType": "Text", "content": content},
        "from": {"emailAddress": {"name": from_name, "address": from_addr}},
        "toRecipients": [{"emailAddress": {"name": "Demo User", "address": USER_ID or ""}}],
        "receivedDateTime": _received(days_ago),
    }


def _event(subject: str, content: str, days_ago: int, attendees: list[dict],
           start_hour: int = 10, end_hour: int = 11) -> dict:
    return {
        "subject": subject,
        "body": {"contentType": "Text", "content": content},
        "start": _event_start(days_ago, start_hour),
        "end": _event_end(days_ago, end_hour),
        "attendees": attendees,
    }


def _attendee(name: str, address: str) -> dict:
    return {"emailAddress": {"name": name, "address": address}, "type": "required"}


# ── Customer data ────────────────────────────────────────────────────────
CUSTOMERS = [
    # ── 1. Coca-Cola ─────────────────────────────────────────────────────
    {
        "name": "Coca-Cola",
        "emails": [
            _email(
                "RE: Enterprise Agreement Renewal — Timeline",
                "Marcus, we need to finalize the renewal terms by March 15. "
                "Our CFO wants to see a clear ROI summary before approving the "
                "expanded scope. Can we schedule a call next week?",
                "Sarah Chen", "sarah.chen@coca-cola.com", 4,
            ),
            _email(
                "Fabric Workspace Performance Concerns",
                "Hi Priya, we've been experiencing latency issues in our supply chain "
                "analytics pipeline on Fabric. Query times have increased 3x over the "
                "past month. This is affecting our daily reporting.",
                "David Park", "david.park@coca-cola.com", 6,
            ),
            _email(
                "AI Strategy Briefing Request",
                "We're putting together our AI roadmap for the next fiscal year "
                "and would love to get Microsoft's perspective on Copilot and "
                "Foundry for our bottling operations.",
                "Sarah Chen", "sarah.chen@coca-cola.com", 10,
            ),
        ],
        "events": [
            _event(
                "Coca-Cola QBR — Q4 Review",
                "Reviewed Q4 usage metrics. Coca-Cola expressed strong interest "
                "in expanding Copilot from 5,000 to 15,000 seats. Fabric adoption "
                "growing in supply chain team. Action: send AI strategy proposal by Feb 28.",
                14,
                [
                    _attendee("Sarah Chen", "sarah.chen@coca-cola.com"),
                    _attendee("David Park", "david.park@coca-cola.com"),
                ],
            ),
            _event(
                "Technical Deep Dive — Fabric Performance",
                "Investigated Fabric query latency. Root cause: unoptimized Delta Lake "
                "partitioning on supply chain datasets. Priya to provide optimization guide.",
                33,
                [_attendee("David Park", "david.park@coca-cola.com")],
                start_hour=14, end_hour=15,
            ),
        ],
    },
    # ── 2. Contoso ───────────────────────────────────────────────────────
    {
        "name": "Contoso",
        "emails": [
            _email(
                "AI Foundry Integration — Updated Timeline",
                "Hi team, we've completed the initial API integration with AI Foundry "
                "and are targeting March 1 for the first production workload. Need to "
                "align on the data pipeline architecture before we can proceed to phase 2.",
                "Kevin Liu", "kevin.liu@contoso.com", 3,
            ),
            _email(
                "Copilot Adoption Metrics — February Update",
                "Our Copilot rollout hit 8,200 active users this month, up from 5,400 "
                "in January. The engineering teams are seeing a measurable productivity "
                "lift. We'd like to discuss expanding to the remaining 12,000 employees.",
                "Amy Zhang", "amy.zhang@contoso.com", 5,
            ),
            _email(
                "Platform Architecture Review — Action Items",
                "Following our architecture review last week, we need Microsoft's guidance "
                "on the best approach for integrating AI Foundry models into our existing "
                "microservices platform. Can Priya's team provide a reference architecture?",
                "Kevin Liu", "kevin.liu@contoso.com", 8,
            ),
        ],
        "events": [
            _event(
                "Contoso QBR — AI Foundry & Copilot Progress",
                "Reviewed AI Foundry integration milestones and Copilot adoption curve. "
                "Contoso wants to be a launch partner for Foundry GA. Discussed scaling "
                "Copilot to all 20K employees by Q3. Action: send Foundry GA timeline.",
                12,
                [
                    _attendee("Kevin Liu", "kevin.liu@contoso.com"),
                    _attendee("Amy Zhang", "amy.zhang@contoso.com"),
                ],
            ),
            _event(
                "AI Foundry Technical Design Session",
                "Deep dive on Foundry model deployment patterns for Contoso's platform. "
                "Agreed on a hybrid approach: managed endpoints for standard models, "
                "custom containers for their fine-tuned models. Follow-up on pricing.",
                28,
                [_attendee("Kevin Liu", "kevin.liu@contoso.com")],
                start_hour=13, end_hour=15,
            ),
        ],
    },
    # ── 3. Fabrikam ──────────────────────────────────────────────────────
    {
        "name": "Fabrikam",
        "emails": [
            _email(
                "Azure Migration Timeline — Phase 3 Update",
                "Hans here. Phase 2 of our Azure migration is wrapping up next week. "
                "We're moving 140 workloads in phase 3 and need to finalize the landing "
                "zone design. Can we get a dedicated CSA for the next 6 weeks?",
                "Hans Mueller", "hans.mueller@fabrikam.com", 4,
            ),
            _email(
                "Fabric Pilot Results — Supply Chain Analytics",
                "The Fabric pilot for our supply chain team exceeded expectations. "
                "Query performance is 4x faster than our on-prem solution and the "
                "real-time dashboards have reduced decision latency from hours to minutes.",
                "Lisa Andersen", "lisa.andersen@fabrikam.com", 7,
            ),
            _email(
                "FYI: AWS Competitive Proposal Received",
                "Wanted to flag that our procurement team received a competitive proposal "
                "from AWS for our remaining on-prem workloads. Their pricing is aggressive. "
                "I think we should discuss how to position Azure's advantages in our next call.",
                "Hans Mueller", "hans.mueller@fabrikam.com", 9,
            ),
        ],
        "events": [
            _event(
                "Fabrikam Migration Review — Phase 2 Closeout",
                "Phase 2 migration complete: 95 workloads moved to Azure. Performance "
                "within SLA targets. Discussed phase 3 scope and timeline. Key risk: AWS "
                "competitive pressure on pricing. Action: prepare TCO comparison.",
                15,
                [
                    _attendee("Hans Mueller", "hans.mueller@fabrikam.com"),
                    _attendee("Lisa Andersen", "lisa.andersen@fabrikam.com"),
                ],
            ),
            _event(
                "Supply Chain Analytics Workshop — Fabric",
                "Hands-on workshop with Fabrikam's supply chain data team. Demonstrated "
                "Fabric lakehouse patterns for inventory optimization. Team impressed "
                "with real-time streaming capabilities. Next: production pilot plan.",
                30,
                [_attendee("Lisa Andersen", "lisa.andersen@fabrikam.com")],
                start_hour=9, end_hour=12,
            ),
        ],
    },
    # ── 4. Northwind Traders ─────────────────────────────────────────────
    {
        "name": "Northwind Traders",
        "emails": [
            _email(
                "Copilot Store Ops Pilot — Early Results",
                "Tom here. The Copilot pilot across our 50 flagship stores is showing "
                "promising results. Store managers are saving 2+ hours per week on "
                "reporting. We'd like to discuss expanding to all 1,200 locations.",
                "Tom Richards", "tom.richards@northwindtraders.com", 3,
            ),
            _email(
                "Dynamics 365 Expansion — Retail Module",
                "Maria here. We're evaluating the Dynamics 365 Commerce module for our "
                "omnichannel strategy. Our current POS system contract expires in August "
                "and we want to have a migration plan ready by June.",
                "Maria Santos", "maria.santos@northwindtraders.com", 6,
            ),
            _email(
                "Holiday Season Analytics — Lessons Learned",
                "Wanted to share our post-holiday analysis. The Azure-powered demand "
                "forecasting model reduced stockouts by 18% vs. last year. However, "
                "we need better real-time inventory visibility across our DC network.",
                "Tom Richards", "tom.richards@northwindtraders.com", 9,
            ),
        ],
        "events": [
            _event(
                "Northwind Digital Transformation QBR",
                "Reviewed digital transformation roadmap. Copilot pilot exceeding targets "
                "in store ops. Dynamics 365 Commerce evaluation underway. Key opportunity: "
                "expand Copilot to all stores and integrate with D365 for unified analytics.",
                18,
                [
                    _attendee("Maria Santos", "maria.santos@northwindtraders.com"),
                    _attendee("Tom Richards", "tom.richards@northwindtraders.com"),
                ],
            ),
            _event(
                "Copilot Store Ops Pilot Kickoff",
                "Launched Copilot pilot in 50 flagship stores. Defined success metrics: "
                "manager time savings, report accuracy, employee satisfaction. Weekly "
                "check-ins scheduled. Pilot duration: 8 weeks.",
                35,
                [_attendee("Tom Richards", "tom.richards@northwindtraders.com")],
            ),
        ],
    },
    # ── 5. Woodgrove Bank ────────────────────────────────────────────────
    {
        "name": "Woodgrove Bank",
        "emails": [
            _email(
                "EA Renewal Concerns — Need to Discuss",
                "Our finance team has flagged several concerns with the proposed EA "
                "renewal pricing. With our Google Cloud evaluation underway, we need "
                "to see a more competitive offer before April 1. Can we set up a "
                "meeting with your pricing team?",
                "Richard Zhao", "richard.zhao@woodgrovebank.com", 3,
            ),
            _email(
                "Compliance Audit — Azure Configuration Review",
                "Our internal audit team has completed their review of our Azure "
                "environment. There are 14 findings related to data residency and "
                "encryption-at-rest configurations that need remediation within 30 days.",
                "Diana Patel", "diana.patel@woodgrovebank.com", 5,
            ),
            _email(
                "Google Cloud Evaluation — Status Update",
                "FYI — our Google Cloud POC for the data analytics workloads is "
                "progressing. BigQuery performance is competitive but their security "
                "model is less mature than Azure's for our regulated environment. "
                "This is still an active evaluation.",
                "Richard Zhao", "richard.zhao@woodgrovebank.com", 8,
            ),
        ],
        "events": [
            _event(
                "Woodgrove EA Renewal Discussion",
                "Discussed EA renewal timeline and pricing concerns. Woodgrove evaluating "
                "Google Cloud for analytics workloads. Key risk: churn on data platform. "
                "Need to demonstrate Azure's compliance advantages. Action: prepare "
                "competitive response and updated pricing by March 5.",
                16,
                [
                    _attendee("Richard Zhao", "richard.zhao@woodgrovebank.com"),
                    _attendee("Diana Patel", "diana.patel@woodgrovebank.com"),
                ],
            ),
            _event(
                "Compliance Architecture Review — Azure Security",
                "Reviewed Woodgrove's Azure security posture against banking regulations. "
                "Identified gaps in data residency controls and key management. Diana's "
                "team to prioritize remediation. Microsoft to provide best practice guide.",
                32,
                [_attendee("Diana Patel", "diana.patel@woodgrovebank.com")],
                start_hour=14, end_hour=16,
            ),
        ],
    },
    # ── 6. Adatum ────────────────────────────────────────────────────────
    {
        "name": "Adatum",
        "emails": [
            _email(
                "Mainframe Migration Phase 2 — Planning",
                "Frank here. Phase 1 of the mainframe migration is complete but phase 2 "
                "keeps getting pushed back due to budget constraints. We need a revised "
                "cost estimate that accounts for the parallel-run period our compliance "
                "team is requiring.",
                "Frank Morrison", "frank.morrison@adatum.com", 5,
            ),
            _email(
                "Azure Arc Hybrid Strategy — Questions",
                "We're interested in Azure Arc for managing our remaining on-prem "
                "workloads alongside the migrated ones. Can you provide a demo "
                "of Arc's policy enforcement capabilities? Our security team has "
                "specific requirements around configuration drift detection.",
                "Janet Kim", "janet.kim@adatum.com", 7,
            ),
            _email(
                "Budget Approval Timeline — FY27 Planning",
                "Quick update: our FY27 budget planning cycle starts in April. If we "
                "want phase 2 funding approved, we need to have the business case "
                "finalized by March 20. The CIO is supportive but needs hard numbers.",
                "Frank Morrison", "frank.morrison@adatum.com", 10,
            ),
        ],
        "events": [
            _event(
                "Adatum Modernization Steering Committee",
                "Quarterly steering committee meeting. Phase 1 mainframe migration "
                "complete. Phase 2 delayed due to budget. Discussed Azure Arc for "
                "hybrid management. Need to build FY27 business case with clear ROI. "
                "Action: deliver updated cost model by March 15.",
                20,
                [
                    _attendee("Frank Morrison", "frank.morrison@adatum.com"),
                    _attendee("Janet Kim", "janet.kim@adatum.com"),
                ],
            ),
            _event(
                "Azure Arc Workshop — Hybrid Management",
                "Technical workshop on Azure Arc capabilities for Adatum's hybrid "
                "environment. Demonstrated policy enforcement, configuration management, "
                "and monitoring. Janet's team to evaluate for 60 days. Follow-up on "
                "licensing costs.",
                34,
                [_attendee("Janet Kim", "janet.kim@adatum.com")],
                start_hour=13, end_hour=15,
            ),
        ],
    },
    # ── 7. Tailwind Toys ────────────────────────────────────────────────
    {
        "name": "Tailwind Toys",
        "emails": [
            _email(
                "Copilot Rollout Update — All Hands Feedback",
                "Zara here. Our company-wide Copilot rollout is going amazingly well. "
                "92% of employees are active users after just 6 weeks. The product team "
                "is especially excited about Copilot in Power BI for customer analytics.",
                "Zara Patel", "zara.patel@tailwindtoys.com", 3,
            ),
            _email(
                "D2C Platform Scaling — Azure Capacity Planning",
                "We're projecting 3x traffic for our summer product launch and need to "
                "ensure our Azure infrastructure can handle the spike. Can we schedule "
                "a capacity planning session with your solutions architect?",
                "Mike Chen", "mike.chen@tailwindtoys.com", 6,
            ),
            _email(
                "AI Customer Insights POC — Proposal",
                "We'd like to explore using Azure AI services to build a real-time "
                "customer insights engine for our D2C platform. Think personalized "
                "recommendations, churn prediction, and lifetime value scoring. "
                "Can you put together a POC proposal?",
                "Zara Patel", "zara.patel@tailwindtoys.com", 8,
            ),
        ],
        "events": [
            _event(
                "Tailwind Growth Planning Session",
                "Reviewed Tailwind's rapid growth trajectory and Azure consumption "
                "forecast. D2C platform scaling for summer launch. Copilot adoption "
                "at 92% — potential case study. AI customer insights POC proposed. "
                "Action: capacity plan and POC proposal by March 1.",
                13,
                [
                    _attendee("Zara Patel", "zara.patel@tailwindtoys.com"),
                    _attendee("Mike Chen", "mike.chen@tailwindtoys.com"),
                ],
            ),
            _event(
                "Copilot Success Review — Tailwind Toys",
                "Reviewed Copilot adoption metrics post-rollout. 92% adoption in 6 "
                "weeks is exceptional. Product team using Copilot in Power BI daily. "
                "Discussed potential for Tailwind to be a Copilot reference customer.",
                25,
                [_attendee("Zara Patel", "zara.patel@tailwindtoys.com")],
            ),
        ],
    },
    # ── 8. Alpine Ski House ──────────────────────────────────────────────
    {
        "name": "Alpine Ski House",
        "emails": [
            _email(
                "Seasonal Scaling Plan — Winter 2026-27",
                "Erik here. We need to start planning our Azure scale-up for next "
                "winter season. Last year we hit capacity limits during the holiday "
                "booking rush. Can we design an auto-scaling architecture that handles "
                "10x traffic spikes without manual intervention?",
                "Erik Johansson", "erik.johansson@alpineskihouse.com", 4,
            ),
            _email(
                "AI Personalization Demo Request",
                "Sophie here. I attended the Microsoft AI Tour event and was impressed "
                "by the personalization demos. We'd love to explore AI-driven guest "
                "experience personalization — think custom ski recommendations, "
                "dynamic pricing, and concierge chatbot.",
                "Sophie Martin", "sophie.martin@alpineskihouse.com", 6,
            ),
            _email(
                "RE: Azure Spend — Budget Constraints",
                "Our board is concerned about cloud costs trending upward. We need "
                "to bring our monthly Azure spend down by 20% without sacrificing "
                "performance during peak season. Can your team do a cost optimization "
                "review?",
                "Erik Johansson", "erik.johansson@alpineskihouse.com", 9,
            ),
        ],
        "events": [
            _event(
                "Alpine IT Strategy Review",
                "Discussed seasonal infrastructure challenges and cost optimization. "
                "Erik's team needs auto-scaling for 10x traffic spikes. Board concerned "
                "about cloud spend. Action: cost optimization review and auto-scaling "
                "architecture proposal.",
                17,
                [
                    _attendee("Erik Johansson", "erik.johansson@alpineskihouse.com"),
                    _attendee("Sophie Martin", "sophie.martin@alpineskihouse.com"),
                ],
            ),
            _event(
                "AI Guest Experience Demo — Alpine Ski House",
                "Demonstrated Azure AI capabilities for guest personalization. Showed "
                "recommendation engine, dynamic pricing model, and Copilot-powered "
                "concierge chatbot. Sophie enthusiastic. Next: build business case "
                "for summer implementation.",
                29,
                [_attendee("Sophie Martin", "sophie.martin@alpineskihouse.com")],
                start_hour=11, end_hour=12,
            ),
        ],
    },
    # ── 9. Bellows College ───────────────────────────────────────────────
    {
        "name": "Bellows College",
        "emails": [
            _email(
                "Copilot Faculty Pilot Proposal",
                "Dr. Walsh here. Our faculty senate approved a Copilot pilot for 200 "
                "professors across three departments. We need help designing the "
                "rollout plan and training curriculum. Academic licensing terms are "
                "a key factor in our budget approval.",
                "Dr. Patricia Walsh", "patricia.walsh@bellowscollege.edu", 4,
            ),
            _email(
                "Teams Rooms Expansion — Campus Modernization",
                "We're expanding Teams Rooms to 45 additional classrooms and conference "
                "rooms this summer. The hybrid learning model is here to stay. Need "
                "to coordinate with your education solutions team on hardware specs "
                "and deployment timeline.",
                "James Hartwell", "james.hartwell@bellowscollege.edu", 7,
            ),
            _email(
                "Research Computing Needs — HPC on Azure",
                "Our physics and bioinformatics departments are outgrowing our on-prem "
                "HPC cluster. We're evaluating Azure HPC for burst computing. Can you "
                "connect us with your research computing specialists? Budget is tight "
                "but the research grants may cover cloud costs.",
                "Dr. Patricia Walsh", "patricia.walsh@bellowscollege.edu", 9,
            ),
        ],
        "events": [
            _event(
                "Bellows Digital Strategy Committee",
                "Met with Bellows College IT leadership. Copilot faculty pilot approved "
                "for 200 professors. Teams Rooms expansion planned for summer. Research "
                "computing moving to Azure HPC. Key: academic licensing and grant funding. "
                "Action: prepare A5 licensing proposal and HPC POC.",
                19,
                [
                    _attendee("Dr. Patricia Walsh", "patricia.walsh@bellowscollege.edu"),
                    _attendee("James Hartwell", "james.hartwell@bellowscollege.edu"),
                ],
            ),
            _event(
                "Copilot for Education Demo — Bellows College",
                "Demonstrated Copilot capabilities in academic context: research "
                "assistance, curriculum development, student engagement analytics. "
                "Faculty feedback positive. Dr. Walsh to present to department heads. "
                "Next: finalize pilot scope and training plan.",
                31,
                [_attendee("Dr. Patricia Walsh", "patricia.walsh@bellowscollege.edu")],
            ),
        ],
    },
    # ── 10. Relecloud ────────────────────────────────────────────────────
    {
        "name": "Relecloud",
        "emails": [
            _email(
                "CDN Performance Issue — Urgent",
                "Aisha here. We're seeing elevated latency on Azure CDN across the "
                "EU region. P95 latency has gone from 45ms to 180ms since Thursday. "
                "This is affecting 2M+ streaming users. We need an escalation path "
                "and root cause analysis ASAP.",
                "Aisha Johnson", "aisha.johnson@relecloud.com", 3,
            ),
            _email(
                "AI Recommendation Engine — Architecture Proposal",
                "Carlos here. We've been prototyping our next-gen recommendation "
                "engine using Azure OpenAI and Cognitive Search. The initial results "
                "are promising — 23% improvement in content engagement. Want to discuss "
                "scaling this to production with your AI team.",
                "Carlos Rivera", "carlos.rivera@relecloud.com", 6,
            ),
            _email(
                "Content Analytics — Fabric Evaluation",
                "We're evaluating Microsoft Fabric for our content analytics platform. "
                "Currently using a mix of Databricks and custom pipelines. If Fabric "
                "can consolidate our stack and reduce costs, we're interested in a "
                "migration. Can you arrange a technical deep dive?",
                "Aisha Johnson", "aisha.johnson@relecloud.com", 8,
            ),
        ],
        "events": [
            _event(
                "Relecloud Platform Review",
                "Reviewed Relecloud's Azure platform health and roadmap. CDN latency "
                "issue escalated to engineering. AI recommendation engine POC showing "
                "strong results. Fabric evaluation for content analytics underway. "
                "Action: resolve CDN issue, schedule Fabric deep dive.",
                14,
                [
                    _attendee("Aisha Johnson", "aisha.johnson@relecloud.com"),
                    _attendee("Carlos Rivera", "carlos.rivera@relecloud.com"),
                ],
            ),
            _event(
                "AI Content Recommendations — Design Sprint",
                "Two-day design sprint for Relecloud's AI recommendation engine. "
                "Defined architecture: Azure OpenAI + Cognitive Search + Cosmos DB. "
                "Carlos's team to build production prototype. Target: 30% engagement "
                "lift. Follow-up on Azure OpenAI throughput provisioning.",
                26,
                [_attendee("Carlos Rivera", "carlos.rivera@relecloud.com")],
                start_hour=9, end_hour=16,
            ),
        ],
    },
    # ── 11. Lamna Healthcare ─────────────────────────────────────────────
    {
        "name": "Lamna Healthcare",
        "emails": [
            _email(
                "P1 Security Incident — Update Required",
                "Dr. Kim here. Following the security incident last week, our board "
                "is requesting a full incident report and remediation timeline from "
                "Microsoft. We need to understand the root cause and what additional "
                "controls are being put in place. This is top priority.",
                "Dr. Robert Kim", "robert.kim@lamnahealthcare.com", 3,
            ),
            _email(
                "HIPAA Compliance Remediation — Action Plan",
                "Sarah here. Based on the post-incident review, we've identified 8 "
                "HIPAA-related configuration gaps in our Azure environment. We need "
                "Microsoft's help prioritizing and remediating these within 45 days "
                "to satisfy our compliance officer.",
                "Sarah Thompson", "sarah.thompson@lamnahealthcare.com", 5,
            ),
            _email(
                "Clinical Analytics Roadmap — Fabric Interest",
                "Despite the security concerns, our clinical team is still very "
                "interested in Fabric for clinical analytics. De-identified patient "
                "data analysis could transform our care quality metrics. Can we "
                "discuss a HIPAA-compliant Fabric architecture?",
                "Sarah Thompson", "sarah.thompson@lamnahealthcare.com", 8,
            ),
        ],
        "events": [
            _event(
                "Lamna Security Incident War Room",
                "Emergency review of the security incident. Root cause: misconfigured "
                "network security group allowed unauthorized access to a staging environment. "
                "No PHI exposed. Remediation plan: 8 items, 45-day timeline. Microsoft "
                "to provide dedicated security architect for 30 days.",
                10,
                [
                    _attendee("Dr. Robert Kim", "robert.kim@lamnahealthcare.com"),
                    _attendee("Sarah Thompson", "sarah.thompson@lamnahealthcare.com"),
                ],
            ),
            _event(
                "Clinical Analytics — Fabric Workshop",
                "Technical workshop on HIPAA-compliant Fabric architecture for clinical "
                "analytics. Demonstrated de-identification pipelines and row-level security. "
                "Sarah's team excited about care quality dashboards. Blocked pending security "
                "remediation completion. Revisit in 60 days.",
                22,
                [_attendee("Sarah Thompson", "sarah.thompson@lamnahealthcare.com")],
                start_hour=13, end_hour=15,
            ),
        ],
    },
]


# ── Seeding functions ────────────────────────────────────────────────────

def seed_emails(token: str) -> None:
    """Create draft messages in the user's mailbox (visible as received mail)."""
    url = f"{GRAPH_BASE}/users/{USER_ID}/messages"
    for customer in CUSTOMERS:
        print(f"\n  [{customer['name']}]")
        for email in customer["emails"]:
            resp = httpx.post(url, headers=_headers(token), json=email, timeout=15)
            if resp.status_code in (200, 201):
                print(f"    \u2713 {email['subject']}")
            else:
                print(f"    \u2717 ({resp.status_code}): {email['subject']}")


def seed_events(token: str) -> None:
    """Create calendar events."""
    url = f"{GRAPH_BASE}/users/{USER_ID}/events"
    for customer in CUSTOMERS:
        print(f"\n  [{customer['name']}]")
        for event in customer["events"]:
            resp = httpx.post(url, headers=_headers(token), json=event, timeout=15)
            if resp.status_code in (200, 201):
                print(f"    \u2713 {event['subject']}")
            else:
                print(f"    \u2717 ({resp.status_code}): {event['subject']}")


def main() -> None:
    if not USER_ID:
        print("Error: GRAPH_USER_ID must be set in .env")
        sys.exit(1)

    print("Acquiring token\u2026")
    token = _get_legacy_token()

    print(f"Seeding emails for {len(CUSTOMERS)} customers\u2026")
    seed_emails(token)

    print(f"\nSeeding calendar events for {len(CUSTOMERS)} customers\u2026")
    seed_events(token)

    print("\nDone.")


if __name__ == "__main__":
    main()
