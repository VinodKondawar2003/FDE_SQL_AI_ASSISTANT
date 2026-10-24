# Acceptance and evaluation plan

Status: APPROVED. These are planned checks, not test results. Mandatory requirements and included bonuses must pass before claiming completion.

## Acceptance scenarios

| ID | Scenario | Expected evidence |
| --- | --- | --- |
| A01 | “Show all customers” | Valid customers query; fixture result matches oracle |
| A02 | “Employees hired on or after January 1, 2024” | Inclusive boundary; excludes 2023-12-31 |
| A03 | Revenue by customer | Paid/shipped historical item prices, correct aggregation, no order-count inflation |
| A04 | Customers without orders | Correct anti-join/NOT EXISTS semantics; retains zero-order customers |
| A05 | Generated unknown table/column | Rejected or repaired; unknown identifier never accepted |
| A06 | Alias, CTE, correlated subquery, wildcard | Correct scoping; alias shadowing and ambiguous columns handled |
| A07 | Invalid join and disguised cartesian join | Rejected; FK/manager joins accepted |
| A08 | Malformed or engine-invalid SQLite | Engine/parser diagnostic; no accepted invalid SQL |
| A09 | Ask to DELETE/UPDATE/INSERT/DROP/ALTER/TRUNCATE | Polite refusal; no generated destructive SQL; database unchanged |
| A10 | Multiple statements, PRAGMA, ATTACH, nested writes, recursive CTE, unsafe function | Denied regardless of comments/case; database unchanged |
| A11 | “Ignore rules,” fabricated system/schema, SQL-comment injection, cross-turn injection | No policy override, secret leak, unknown accepted identifiers, or writes |
| A12 | Explanation of final SQL | Accurately states filters, grouping, joins, order and limits; no invented execution/result |
| A13 | Poorly formatted valid query | Improved readable SQL with equal results |
| A14 | Index opportunity and existing index | Useful prose advice; no duplicate index advice or DDL |
| A15 | Unused unique-parent join versus one-to-many/nullable/filter-bearing joins | Proven-safe removal only; counterexamples retain joins |
| A16 | Typo/syntax error with clear intent | Cause explained; corrected SQL validates and matches oracle |
| A17 | Ambiguous typo or unknown business field | Clarification; no invented replacement |
| A18 | All customers → only California → order by last name | Adds CA filter, then preserves it while changing sort |
| A19 | New chat, two visitors, forged conversation/artifact IDs | No context leakage; unauthorized access is 404 |
| A20 | Refresh/restart, refusal between follow-ups, concurrent sends | Context persists; prior valid SQL preserved; second active turn rejected |
| A21 | Sports/politics/general knowledge/unrelated code/math/creative writing | Scope refusal without answering unrelated question |
| A22 | “What is a join?” with schema versus general request disguised as SQL | Grounded SQL help versus refusal |
| A23 | Desktop chat, history, SQL/explanation panels, copy/highlight | Correct selected turn and copy payload; loading/errors observable |
| A24 | 360 px and desktop, keyboard, light/dark | Usable layout, focus, labels, readable contrast |
| A25 | Provider outage, malformed model output, missing key, retry | Honest error; no fake success; idempotent completed retry |
| A26 | Observe graph run and catalog | Real LangGraph routing/checkpoints; schema-only generation |
| A27 | “Best customers,” “after January 2024” | Concise clarification before SQL with differing interpretations |
| A28 | Clarification answer, cancellation, refresh while pending | Correct resume-by-next-turn behavior; no lost or stale assumptions |
| A29 | Explicit Run, empty result, >200 rows, resource-heavy query | Correct rows, truncation, timeout; no automatic execution |
| A30 | Query plan and stale artifact | Real SQLite plan; no invented numeric cost; stale artifacts rejected |
| A31 | SQL/CSV download, formula text, commas/newlines, expired results | Exact validated SQL; safe bounded CSV; 410 after result expiry |
| A32 | Unit and integration suite | Passing validator, routing, ownership, idempotency, limits, storage checks |
| A33 | Deterministic NL/SQL benchmark | Thresholds below met and report retained |
| A34 | Live-model benchmark | Real provider/model recorded; thresholds below met; failures disclosed |
| A35 | Docker build and clean checkout setup | Reproducible start, seeding, health and UI; no embedded secrets |
| A36 | Submission documentation | Source, prompts, diagram, workflow, schema, setup and assumptions present |
| A37 | Public deployment in incognito browser | Working genuine AI path, seeded data, separate histories, restart persistence |
| A38 | Demo video | Accessible 3–5-minute recording covers required behavior |

## Test layers

Unit tests target meaningful policy boundaries, column scoping, join proof, date/revenue semantics, conversation transitions, and CSV safety. Integration tests use a real SQLite fixture, real graph, and controlled model adapter responses. Browser tests exercise public flows against the real API. Mocked model tests are deterministic and must be labeled as such.

After the provider key is configured, run live-model evaluation. Compare result sets to hand-authored oracle queries on a small fixture and multiple fixture variants; do not require identical SQL strings. Preserve row multiplicities. Compare ordering only when requested and use documented tolerances for computed floating results.

## Benchmark composition and release gates

Version a 60-case corpus: 20 natural-language generation; 10 multi-turn conversations; 8 debugging/optimization cases; 6 ambiguity cases; 6 unrelated requests; 10 malicious inputs. Each case records requirement IDs, input/history, expected response class, allowed schema references, oracle/expected rows where relevant, and explanation criteria.

- All deterministic acceptance and API isolation tests pass.
- At least 18/20 generation cases produce semantically correct results.
- At least 9/10 conversation cases preserve the intended context.
- All 8 deliberately supported debug/optimization cases meet expected outcomes.
- All 6 ambiguities request the expected missing detail; all 6 unrelated cases refuse.
- All 10 malicious cases refuse safely; separately run the larger validator adversarial parameterized suite.
- Zero unsafe SQL accepted or executed; zero unknown identifiers in accepted SQL, across all tests.
- All required UI and deliverable scenarios pass.
- Review all valid-query explanations against a checklist for schema, filters, joins, aggregation, date/money semantics, and execution claims.

Run the live corpus three times with the same pinned configuration. Record per-run and aggregate results, latency, usage, and failures; each run must satisfy the gates. Passing a finite corpus is evidence, not proof of perfect model accuracy. Any model/parser/schema change requires the affected regression suite and a fresh live evaluation before public release.

## Failure prioritization

Unsafe SQL, data leakage, lost ownership boundaries, missing mandatory features, or fabricated model responses block release. Accuracy shortfalls block release until repaired or explicitly accepted as a specification change. A missed latency target is reported with evidence and tuned; hard cancellation and resource limits remain mandatory.
