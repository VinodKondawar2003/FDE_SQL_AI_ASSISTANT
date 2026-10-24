# API contracts and frontend behavior

Status: APPROVED. API prefix /api/v1; JSON UTF-8. UUIDs are server-generated except client request_id UUIDs for retry deduplication.

## Session and ownership

POST /session creates an anonymous session if none exists, sets an opaque HttpOnly SameSite=Lax cookie (Secure in deployment), and returns session expiry and a session-bound CSRF token. Store only the cookie-token hash server-side. Validate Origin and the CSRF header for state-changing requests. GET /session returns the current session metadata and CSRF token. No endpoint accepts a model credential from the browser.

Every conversation, turn, artifact, execution, and export requires ownership checks. Return 404 for inaccessible IDs. The browser cannot choose the LangGraph thread ID. The public demo requires no signup, but visitors have separate histories.

## Endpoints

| Method/path | Request or purpose | Success |
| --- | --- | --- |
| GET /health/live | Process is running; no secrets | 200 status |
| GET /health/ready | Schema, state storage, provider configuration ready | 200 or 503; no paid provider call per probe |
| GET /schema | Allowed tables, columns, relationships, dictionary, version | 200 catalog |
| POST /conversations | Optional title | 201 conversation |
| GET /conversations | Cursor, limit <= 50 | 200 owned conversation page |
| GET /conversations/{id} | Cursor, limit <= 50 for turns | 200 conversation and turn page |
| DELETE /conversations/{id} | Delete owned history, artifacts, results, checkpoints | 204 |
| POST /conversations/{id}/messages | request_id, message, mode | 200 completed turn |
| POST /queries/{artifact_id}/execute | request_id | 200 execution result |
| GET /queries/{artifact_id}/plan | Validated query plan | 200 plan and observations |
| GET /queries/{artifact_id}/download | Exact validated SQL, no user-derived filename | 200 application/sql |
| GET /executions/{id}/download | Stored bounded result snapshot | 200 text/csv |

Deletion is an application-history operation, not permission for assistant-generated DELETE SQL. Block deletion during an active turn or execution with 409, then allow retry.

Message mode: auto (default), generate, optimize, debug, explain. A mode hint never bypasses safety or scope. Message length: 1–8,000 characters; total request body <= 32 KB. Candidate SQL <= 16,000 characters. Empty messages are invalid.

Response shape:
- request_id, conversation_id, turn_id, status.
- status: completed | clarification_required | refused | failed.
- intent and a short user-facing message.
- sql: null or {artifact_id, text, dialect: "sqlite", schema_version, validation: "passed"}.
- explanation: null or {summary, steps, assumptions}.
- diagnostics: [{code, message, location?}]; no stack traces or secrets.
- optimization: null or {changes, suggestions, index_recommendations, rewrite_applied}.
- clarification: null or {question, choices}; free text is always accepted.
- error: null or {code, message, retryable}.
- meta: total_duration_ms, execution_available.

Refusal/clarification/failed responses have sql=null. A successful schema/concept explanation can have sql=null. No execution is implied by successful generation.

Execution returns execution_id, artifact_id, columns [{name, type}], rows as arrays, returned_row_count, truncated, limit=200, duration_ms, expires_at. Arrays preserve duplicate SQL column names; metadata uses column positions. Null is JSON null; integers outside JavaScript's safe range serialize as strings with integer type metadata. Reject unsupported binary results.

## Error handling and retries

400 invalid business request; 401 expired/missing session; 404 missing/inaccessible object; 409 turn in progress, request_id conflict, or schema mismatch; 413 body too large; 422 typed field validation; 429 quota exceeded with Retry-After; 502 provider failure; 503 unavailable configuration/storage; 504 turn/execution deadline.

A semantically understood refusal or clarification is HTTP 200. Infrastructure failures use the HTTP error code and the same safe error envelope, including a turn_id when one was persisted. Validation failure after bounded repair is status=failed with a controlled diagnostic.

For a completed identical (conversation_id, request_id, payload), replay the stored result without a model call. A duplicate in progress returns 409; a reused ID with different content returns 409. Execution deduplication is keyed by artifact_id and request_id. Mark abandoned in-progress turns as interrupted on restart and reconcile persisted final checkpoints before permitting retry.

## UI contract

Desktop: left history rail; central chat/composer; right SQL and explanation area with results and plan tabs. Small screens: history drawer and stacked/tabbed output; no page overflow at 360 px. Tables and SQL blocks may scroll within their containers.

Empty state explains SQL-only scope, SQLite dialect, and synthetic data; offers example prompts and a schema drawer. Each assistant response can show validated SQL, explanation, assumptions, debugging issues, and optimization advice. Selecting a historical turn restores its artifact. A new refusal must not display the previous turn's SQL as the new answer.

Copy and Download SQL are enabled only for validated artifacts. A read-only SQL display prevents accidental edits from inheriting validation; user SQL is supplied in the composer with Debug/Optimize mode. Run is explicit. Show running, rows/empty result, truncation, timeout, and execution-error states. Disable duplicate sends/runs while pending.

Show honest loading text such as “Preparing your SQL response”; do not simulate node progress. On uncertain network failure, offer retry with the same request_id. Restore history after refresh; New conversation clears contextual carryover.

Keyboard: Enter sends, Shift+Enter inserts newline, visible focus, labeled icon buttons, accessible status announcements, keyboard-operable tabs, adequate contrast in both themes. Render messages as escaped text or restricted sanitized Markdown with raw HTML disabled. No executable HTML from SQL or model output.

CSV downloads contain only the shown stored snapshot, with truncation disclosed. Downloads expire after one hour and return 410 after expiry. Escape CSV quotes/newlines and neutralize formula-leading text cells (=, +, -, @, tab, CR); preserve typed numeric values. Do not run a new unbounded query to export.
