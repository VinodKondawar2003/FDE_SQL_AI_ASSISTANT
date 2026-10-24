# SQL Assistant specification package

Status: APPROVED — awaiting user approval. Prepared: 2026-10-23 (Asia/Calcutta).

Start with this document, then review the requirements and architecture. These approved specifications define the acceptance criteria. Measured implementation results are recorded in docs/validation.md.

## Approval boundary

The user requested PDF analysis and specification files first, followed by a pause for approval. That original gate was satisfied by the user's explicit approval. Local implementation and verification are now authorized; the user subsequently published the repository and requested Vercel deployment. See amendment 10 for the authorized hosting change. Reading the assignment required a temporary PDF extraction utility; it is not an application dependency.

Approval of this package authorized implementation against its requirements. Paid hosting/provider accounts and credentials remain deployment inputs, not assumptions that they already exist. Implementation must preserve a clear record of any subsequently approved scope changes.

## Recommended solution

- Frontend: React, TypeScript, Vite, Tailwind CSS; a responsive chat workspace.
- Backend: Python 3.12-compatible code, verified with Python 3.13, FastAPI, Pydantic; typed API and service boundaries.
- AI: LangGraph StateGraph with explicit routing, checkpointed conversation state, bounded repair, and structured model responses.
- Model integration: LangChain model interface; initially Google Gemini through langchain-google-genai. Model ID is a required server setting and will be selected from available structured-output-capable models using the acceptance benchmark. No unverified model name, availability, or price is assumed.
- Query database: SQLite with synthetic sample data, opened read-only at runtime.
- Validation: SQLGlot AST/schema checks followed by SQLite prepare/EXPLAIN checks and execution authorization.
- Persistence: PostgreSQL application storage and LangGraph checkpoints for Vercel; separate SQLite files remain supported locally.
- Delivery: Vercel FastAPI function serving the compiled frontend and API, with Neon persistence (amendment 10). Local Docker remains supported.
- Testing: pytest, frontend component tests, Playwright, and a reproducible live-model evaluation set.

This stack is an engineering recommendation for this assignment's scope. See the architecture for alternatives and constraints, and the references for official documentation.

## Scope decision

All mandatory PDF requirements are included. Included enhancements: safe sample execution, syntax highlighting, CSV and SQL downloads, dark mode, prompt-injection defenses, Docker, automated tests, and a query-plan panel. Raw model-token streaming and multiple SQL dialects are deferred. SQLite plan output is not a numeric cost estimate.

The user selected a proposed demo schema: customers, orders, products, employees, plus departments and order_items to support useful relationships. No separate source schema was supplied.

## Read in this order

1. [Requirements and source interpretation](01-requirements.md)
2. [Architecture and stack decisions](02-architecture.md)
3. [Sample schema and business semantics](03-data-model.md)
4. [LangGraph workflow and prompt contracts](04-agent-workflow.md)
5. [API and frontend behavior](05-api-and-ui.md)
6. [Validation and operational constraints](06-validation-and-security.md)
7. [Acceptance and evaluation](07-acceptance-tests.md)
8. [Implementation and delivery plan](08-delivery-plan.md)
9. [Sources and decision register](09-sources-and-decisions.md)
10. [Vercel and PostgreSQL deployment amendment](10-vercel-deployment.md)

## Approval checklist

- Accept the recommended stack and the single-instance SQLite deployment boundary.
- Accept the synthetic commerce/employee schema and business definitions.
- Accept the mandatory scope and the explicit included/deferred bonuses.
- Accept the safety rules, acceptance gates, and implementation sequence.

The provider credential and model are configured locally. The repository is on GitHub and Neon is configured. Vercel dashboard deployment and public verification are pending.

Implementation approval: **APPROVED**. Development authorized by the user. Current implementation and verification status: [delivery status](../docs/delivery-status.md).
