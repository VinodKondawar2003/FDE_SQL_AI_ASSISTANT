# Implementation and delivery plan

Status: APPROVED. M0 is approved; M1?M5 are implemented; M6 verification is in progress. Local M7 packaging is prepared. The user deferred repository publication and public deployment.

## Spec-driven development process

1. Obtain the user's explicit approval of this package or incorporate requested revisions.
2. Establish a traceable backlog using R/B requirement IDs and A acceptance IDs.
3. Implement one vertical slice at a time; update contracts before making incompatible changes.
4. Keep real-model evaluation separate from deterministic tests.
5. Complete release acceptance and collect concrete submission artifacts.
6. Report remaining external dependencies honestly; do not label a local demo as publicly deployed.

## Milestones and exit criteria

| Milestone | Work | Depends on | Exit |
| --- | --- | --- | --- |
| M0: approval | Review specs and resolve requested changes | Current phase | Explicit user approval |
| M1: foundation | Repository layout, dependency locks, typed settings, synthetic schema/seed, app storage | M0 | Clean local setup and fixture checks |
| M2: SQL boundary | AST qualification, join checks, engine validation, read-only executor, budgets | M1 | A05–A11 and execution guard tests pass |
| M3: agent | LangGraph routes, prompts, repair, clarification, explanations, safe optimization, checkpoints | M2 | Generation/debug/follow-up vertical slice |
| M4: API/UI | Sessions, ownership, contracts, responsive chat, history, output panels, errors/copy | M3 | Required end-to-end flows work |
| M5: included bonuses | Run/results, plan, SQL/CSV exports, dark mode, syntax highlighting | M4 | Included B requirements pass |
| M6: evaluation/hardening | Live benchmark, isolation/concurrency, accessibility, failure recovery | M4/M5 | Release gates pass with recorded evidence |
| M7: delivery | Docker, public hosting, README/diagrams/prompts, demo recording and submission links | M6 | Public incognito verification and full deliverable checklist |

Mandatory work takes priority if the assignment's 6–8-hour time box is imposed. Do not silently remove mandatory behavior to meet it. Discuss reducing included bonuses if necessary; do not claim optional work is complete when deferred.

## Proposed repository layout after approval

backend/app/api — routes, schemas, dependencies
backend/app/agent — graph, state, nodes, model adapter
backend/app/prompts — versioned prompt templates
backend/app/sql — catalog, validation, optimization, execution
backend/app/storage — sessions, turns, artifacts, persistence
backend/tests — unit and integration cases
frontend/src — workspace components, API client, styles
frontend/tests — components and browser scenarios
data — schema, deterministic seed source, semantic dictionary
evals — corpus, oracle fixtures, runner, reports
docs — architecture, workflow, demo script and deployment runbook
specs — this approved source of requirements
Dockerfile / compose.yaml / lockfiles / .env.example / README.md — delivery files

The implemented API and persistence use backend/app/main.py and backend/app/storage.py; the remaining layout follows this plan.

## Deployment and secrets checklist

Required after implementation: model credential and verified model ID; hosting account with persistent storage; public origin; repository destination. Store secrets in host environment settings and excluded local env files. .env.example uses placeholders.

Build a multi-stage image, run as a non-root user, serve same-origin UI/API, mount persistent state, and configure the immutable sample database. Startup checks schema integrity and storage permissions; deployment performs a genuine model smoke test. Use HTTPS, health probes, quotas, and a documented rollback to the prior image without destroying state.

Record exact runtime/dependency/model versions and the dataset revision. Freeze package versions only after checking compatibility; do not install unbounded latest dependencies on deployment. CI runs lint/type checks, deterministic tests, browser smoke tests, and image build. Live-model evaluations use secrets only in a controlled manual release job.

## Submission artifacts

- GitHub repository URL containing complete source and no secrets.
- Public deployed app URL, verified from an unauthenticated/incognito browser.
- README: prerequisites, local/Docker setup, environment variables, seed/reset procedure, testing, model configuration, demo access, limitations, assumptions, and links.
- Architecture diagram and LangGraph route/state explanation.
- Actual versioned prompts used, schema, seed instructions, semantic dictionary.
- Evaluation report with real results, not planned test names.
- Accessible 3–5-minute demo recording.

Suggested four-minute demo: scope/schema (0:00–0:30); generate/explain/run (0:30–1:20); follow-up (1:20–1:50); debug and optimize (1:50–2:40); destructive/out-of-scope refusal and clarification (2:40–3:20); architecture and deployment evidence (3:20–4:00).

## Risks and completion conditions

Provider access, model availability, hosting cost/access, repository destination, and video recording capability remain external dependencies. They must be resolved before the corresponding deliverable is claimed complete. A paid host is a proposal, not an authorized purchase.

The model can produce semantically wrong SQL even when it is safe and syntactically valid; explicit business definitions and oracle-based evaluation reduce this risk. Conservative join validation intentionally rejects unsupported relationships instead of guessing.

Completion requires the mandatory PDF requirements, agreed included bonuses, verified tests, public link, repository, documentation, and demo video. The approval gate has been satisfied. See docs/delivery-status.md for measured completion evidence.
