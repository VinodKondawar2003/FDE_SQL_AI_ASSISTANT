# Local verification

Verification date: 2026-10-24. Public repository publication and public hosting are deferred by the user's explicit choice.

## Deterministic checks

| Check | Measured result |
| --- | --- |
| Backend pytest | 64 passed |
| Ruff | Passed |
| Frontend component tests | 2 passed |
| TypeScript and Vite production build | Passed |
| Playwright desktop and 360 px mobile flows | 2 passed |
| npm dependency audit | 0 vulnerabilities at verification time |

These are 68 automated tests in total. Backend and browser integration tests use the real SQLite engine, API, and LangGraph, with a test-only scripted provider. They do not establish real-model accuracy.

The tests cover SQL AST and authorizer restrictions; schema and relationship resolution; date and state-code semantics; join-removal proofs; cancellation and row caps; ownership; CSRF and origin checks; idempotency; concurrent turns; restart/checkpoint recovery; expiry; CSV handling; real browser navigation, results, follow-ups, exports, refresh, refusal, dark mode, and mobile overflow. Additional regressions ensure supplied explain queries bypass generation and retain their joins.

The final build also caught and resolved a component-test typing error. Browser screenshots now use Playwright's per-test output directory, avoiding Windows locks on documentation images.

## Real Gemini verification

Configured and generation-tested model: `gemini-3.5-flash-lite`. The user supplied the credential in the excluded local .env file. Provider model availability was tested directly; unavailable earlier model IDs were not treated as successful connections.

The live smoke test passed:
- Customer projection: 80 rows.
- California follow-up: 40 rows, preserving the selected columns.
- Unrelated sports request: refused.
- Ambiguous January 2024 boundary: clarification required.

The first full live run passed all 60 cases: 20 generation, 10 conversation, 8 debug/optimization, 6 ambiguity, 6 scope, and 10 security. Additional runs with varied synthetic datasets are still in progress. The final result will be recorded below and retained in [verified.json](../evals/reports/verified.json). No claim of passing the three-run release gate is made while that evaluation is in progress.

Earlier live evaluation found provider rate limits and two semantic issues: a state-name literal that needed the stored two-letter code, and an explain request unnecessarily sent through generation. Both were fixed. Three focused live regressions (New York follow-up, explicit dangling-AND repair, supplied-query explanation) passed. The dangling-AND case was clarified to say the AND was accidental; guessing a missing business predicate would be inappropriate.

Calls in the final evaluation are spaced five seconds apart. Reported case durations include pacing and, for conversations, multiple turns. They are not an unpaced single-turn latency measurement. The aspirational 20-second AI p95 target remains separate from the enforced 45-second turn deadline.

## Evidence and limits

- [Backend tests](../backend/tests), [component tests](../frontend/src/OutputPanel.test.tsx), and [browser tests](../frontend/tests/workspace.spec.ts).
- [Live corpus](../evals/cases.json), [runner](../evals/run.py), and [smoke script](../scripts/live_smoke.py).
- Documentation screenshots were captured from browser tests using the test adapter; they are UI evidence, not live-model evidence.
- The recording script and video player are prepared, but no completed demo video exists yet. The recording command was declined during the Git handoff.
- Docker is not installed in this workspace. Dockerfile/Compose/Render configuration is supplied, but a local container build or runtime is **not verified**. CI includes an image-build step for the future connected repository.
- Public deployment, external URL verification, and hosted persistence testing are deferred.
- Finite test coverage cannot guarantee that every natural-language request has the intended business meaning. Review generated SQL and its explanation before running it.

## Reproduce

Use the README verification commands. Install the locked Python and Node dependencies first. Deterministic tests need no Gemini key; live smoke and evaluation do, and consume provider quota.

Run the live evaluator separately from demo recording and other intensive AI use to avoid sharing the same provider rate limit. The evaluator writes incremental reports and exits nonzero if any case fails. Preserve failed runs when diagnosing a regression; do not substitute a filtered rerun for the full-corpus evidence.

Warm loopback HTTP timing: 30 measured requests after 5 warmups per endpoint. Schema p95 10.31 ms; conversation list p95 12.07 ms; readiness p95 1.75 ms. See [timing evidence](local-api-timing.json).

A transient HTTP-status retry regression was added after the live evaluator started: HTTP 503 is now retried once within the same call/deadline budget. The 64-test backend suite verifies it; the running live evaluator uses its previously loaded retry behavior.
