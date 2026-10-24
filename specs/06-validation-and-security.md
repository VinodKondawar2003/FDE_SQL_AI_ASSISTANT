# SQL validation and operational constraints

Status: APPROVED. The model is an untrusted candidate generator. No SQL is displayed, copied, exported, planned, or executed as accepted SQL until it passes deterministic checks.

## Validation sequence

1. Enforce input and candidate size limits; parse all statements with the SQLite dialect. Require exactly one nonempty statement; never split on semicolons with string operations.
2. Traverse the entire AST. Allow a SELECT query, nonrecursive WITH queries, and validated set operations. Reject writes, DDL, administrative commands, PRAGMA, ATTACH/DETACH, transactions, EXPLAIN supplied by a user, SELECT INTO, recursive CTEs, external sources, and unsupported AST nodes. Server-created EXPLAIN is internal only.
3. Resolve identifiers against the complete trusted schema with SQLGlot qualification/scope analysis. Disable schema inference and partial qualification. Account for aliases, CTE outputs, subqueries, correlated references, wildcards, and quoted names. Reject unknown tables/columns and ambiguous column references.
4. Validate relational predicates against declared foreign keys and compatible types. Check explicit JOIN, comma joins, implicit WHERE joins, and correlated subqueries. Reject cartesian, NATURAL, and unproven relationships in v1; allow a self-join on employees.manager_id=employees.employee_id. WHERE filters cannot be treated as proof of a relationship.
5. Allow only approved scalar/aggregate/window functions; initial catalog: COUNT, SUM, AVG, MIN, MAX, COALESCE, IFNULL, NULLIF, ROUND, ABS, LOWER, UPPER, LENGTH, TRIM, SUBSTR, DATE, DATETIME, STRFTIME, JULIANDAY, ROW_NUMBER, RANK, DENSE_RANK, LAG, LEAD. CAST, CASE, and ordinary arithmetic are allowed AST constructs in an in-scope query. Unknown functions fail closed. Forbid load_extension, file I/O, pragma table functions, and system catalogs.
6. Prepare the exact candidate using server-created EXPLAIN QUERY PLAN against the real read-only sample connection with the authorizer active. Syntax or semantic engine errors fail validation.
7. Apply only approved formatting/optimization, then repeat validation on the final SQL. Persist exact text/hash, schema version, and validator version.
8. Validate output prose against allowed identifiers and prohibited SQL emission. Keep candidate SQL out of explanation, refusal, diagnostic, and model-error text. Only the dedicated validated SQL field can emit SQL.

Parsing alone does not establish semantic correctness or read-only behavior. SQLGlot's schema qualification assists identifier resolution, while execution-time controls remain independent: [SQLGlot documentation](https://sqlglot.com/).

Quoted literals containing words such as “drop” must not trigger a destructive-operation rejection by substring matching. Conversely, comments, case changes, nested queries, or a read-only first statement do not excuse an unsafe AST.

## Read-only execution boundary

The runtime opens only a fixed server-owned sample path with mode=ro, sets query_only, disables extension loading, and installs an authorizer that denies every unapproved action. Allow reads only from catalog tables/columns and approved functions; allow COUNT(*)'s empty-column authorizer case deliberately. Do not register user-defined functions.

Never rely on query_only alone: SQLite documents that it is not a complete read-only boundary. The authorizer can reject operations during compilation: [query_only](https://www.sqlite.org/pragma.html#pragma_query_only), [authorizer](https://www.sqlite.org/c3ref/set_authorizer.html).

Revalidate ownership, SQL hash, schema version, and SQL before every execution/plan. There is no API that accepts arbitrary SQL for direct execution or arbitrary database paths. If schema/validator versions change, reject stale artifacts and ask the user to regenerate.

Run on a dedicated connection with a SQLite progress handler enforcing a monotonic two-second deadline, plus connection interrupt on cancellation. Fetch at most 201 rows, return the first 200, and use the extra row to mark truncation. Cap serialized results at 1 MB; terminate and return a controlled limit error if that cap is exceeded. Fetch limits do not bound aggregation/sort work; the progress handler is mandatory.

Use SQLite connection limits for expression depth, columns, compound selects, and SQL length. Close cursors/connections on success, error, cancellation, and timeout. A process may need a bounded worker thread for synchronous SQLite; HTTP timeout alone is not query cancellation.

## Safe optimization proof rules

- Formatting and identifier qualification may preserve semantics after revalidation.
- A LEFT JOIN to a unique parent may be removed only if no projected expression, WHERE, HAVING, grouping, ordering, window, or subsequent join references that parent, and uniqueness proves no row multiplication.
- An INNER JOIN may be removed under the above conditions only when a NOT NULL enforced foreign key also proves exactly one matching parent for each source row.
- Preserve one-to-many joins, nullable inner joins, filter-bearing joins, and anything not covered by a proof.
- Verify seed foreign-key integrity and uniqueness before using those proofs. Fixture result equality is useful regression evidence, not a general mathematical proof.
- Index advice names existing table/column references and explains the relevant filter/order/join; it never emits CREATE INDEX or modifies the database.

## Scope, injection, and resource controls

User text, SQL comments, model output, and persisted history are untrusted data. Prompts must not let them replace policy/schema or request secrets/tools. Avoid returning raw database values to the LLM. A model scope classifier is not an absolute guarantee; adversarial evaluations verify its behavior, while AST and database controls independently enforce the SQL boundary.

Defaults: 10 message requests per session per minute; 30 execution requests per session per minute; 30 model requests per IP per minute; 4 concurrent model turns globally; one active turn per conversation. Trust proxy IP headers only from the configured hosting proxy. Add a persisted global daily ceiling of 500 model calls, including retries, so anonymous-session rotation cannot bypass the demo budget. Limits are configurable and displayed through clear retryable errors.

Log correlation IDs, durations, status codes, and usage; omit cookie tokens, API keys, raw prompts, and result data. The model receives user questions and schema metadata; document that flow in the README/UI help. Use synthetic data only. Seven-day history cleanup and one-hour result expiry apply to storage and checkpoints.

## Targets and limits

Targets to measure after implementation: warm non-model API p95 < 500 ms on the demo dataset; typical AI-turn p95 < 20 seconds over a documented 30-turn run. Hard deadlines remain 45 seconds per turn and 2 seconds per query. External model latency prevents an unconditional latency guarantee.

Public deployment must use HTTPS, server-side secrets, exact-origin controls, security headers including a restrictive CSP, and readiness checks. Single-instance SQLite persistence is a deliberate constraint, not a claim of enterprise scale.
