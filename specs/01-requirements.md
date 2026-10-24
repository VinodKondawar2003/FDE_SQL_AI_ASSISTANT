# Requirements and source interpretation

Status: APPROVED. Authority: the user's request governs this phase; the PDF is the source of project requirements, not permission to begin coding or submit anything.

Source: FD Engineer Hiring Assignment.pdf, six pages, read in full. SHA-256: b76f0c54edfc3155d8aa8455018ad8a27d532e70c3ebfe32529510205be41a76.

## Product objective

Enable a business user to ask questions about the supplied sample database, obtain accurate read-only SQL and a plain-English explanation, improve or debug SQL, and refine queries conversationally. This is a focused SQL assistant with explicit scope boundaries.

## Mandatory requirements and traceability

| ID | PDF source | Required behavior | Acceptance coverage |
| --- | --- | --- | --- |
| R01 | p1 §3.1 | Convert natural-language requests to SQL grounded in the configured schema | A01–A04 |
| R02 | p2 §3.2 | Validate syntax, tables, columns, and join relationships before returning generated SQL | A05–A08 |
| R03 | p2 §3.2; p4 §7 | Refuse destructive operations; return only read-only queries | A09–A11 |
| R04 | p2 §3.3 | Explain the final validated SQL in plain English | A12 |
| R05 | p2 §3.4 | Improve readability, suggest performance improvements and indexes, remove provably unnecessary joins | A13–A15 |
| R06 | p2 §3.5 | Identify SQL errors, explain their cause, and return validated corrections when intent is clear | A16–A17 |
| R07 | p2 §3.6 | Retain conversation context and modify the previous query for follow-ups | A18–A20 |
| R08 | p3 §3.7; p4 §7 | Refuse general knowledge, sports, politics, unrelated programming, mathematics, and creative writing | A21–A22 |
| R09 | p3 §4 | Responsive chat, SQL panel, explanation panel, history, loading, error feedback, copy SQL | A23–A25 |
| R10 | p3 §5; p4 §6 | Backend, relational database, schema grounding, LangGraph orchestration with explicit validation | A26 |
| R11 | p4 §7 | Ask for clarification for material ambiguity; handle invalid requests gracefully | A27–A28 |
| R12 | p4 §8; p5 §11 | Source repo, setup README, diagram, workflow explanation, prompts, schema, assumptions | A36 |
| R13 | p4 §8; p5 §11 | Public working application and 3–5-minute demo video, with repository and deployment links | A37–A38 |

The forbidden examples DELETE, UPDATE, INSERT, DROP, ALTER, and TRUNCATE are a minimum; all writes and administration are denied through an allowlist. Index suggestions are prose recommendations, never CREATE INDEX output from the agent.

## Included enhancements

| ID | Source | Planned behavior | Acceptance |
| --- | --- | --- | --- |
| B01 | p1 §2; p4 §6; p5 §10 | Explicit Run button executes validated SQL against sample data | A29–A30 |
| B02 | p5 §10 | SQL syntax highlighting | A23 |
| B03 | p3 §4; p5 §10 | Download validated SQL and bounded results as CSV | A31 |
| B04 | p3 §4 | Accessible dark mode | A24 |
| B05 | p5 §10 | Prompt-injection defenses at model and execution boundaries | A11 |
| B06 | p5 §10 | Docker deployment and unit/integration tests | A32–A37 |
| B07 | related to p5 §10 | EXPLAIN QUERY PLAN panel; qualitative scan/index observations | A30 |

Deferred bonus scope: raw token streaming; PostgreSQL/MySQL generation and execution; numerical query-cost estimation. An honest status indicator meets the mandatory loading requirement. No numeric optimizer cost is invented for SQLite.

## Interpretations and ambiguities

1. Follow-up support is mandatory under §3.6 even though §10 repeats it as a bonus.
2. The PDF promises a provided schema but contains none. The user selected our proposed demo schema on 2026-10-23.
3. The PDF says “after January 2024” but illustrates a January 1 inclusive boundary. Treat that wording as ambiguous and ask whether the user means on/after January 1 or after January ends. Explicit “on or after January 1, 2024” is inclusive; “after January 2024 ends” starts February 1.
4. The agent may explain SQL concepts using the approved schema. It must not become a general chatbot; a SQL wrapper around an unrelated request does not make it in scope.
5. “Never hallucinate” becomes an enforceable output contract: unknown identifiers cannot appear in accepted SQL. Internally rejected model candidates can be wrong and are never exposed as validated SQL.
6. “Remove unnecessary joins” requires proof of semantic preservation, including duplicate and NULL behavior; it does not permit deleting every join whose columns are unselected.
7. Setup scripts may create/seed the database. The prohibition on write SQL applies to the assistant and query execution surface, not trusted deployment provisioning.
8. The stated 6–8 hours is an assignment time box, not an evidence-based completion promise. Mandatory features take priority; optional enhancements follow core acceptance.

## Non-goals

User-uploaded databases, arbitrary connection strings, database writes, general programming help, enterprise SSO, cross-user analytics, autonomous schema modifications, retrieval/vector infrastructure, and multi-region scaling.

## Evaluation priorities

PDF rubric: agent design 25%, SQL accuracy 25%, validation/guardrails 20%, conversation 10%, UI/UX 10%, code quality 5%, documentation 5%. The implementation plan allocates effort to correctness and safety before optional presentation features.
