# Sources and decision register

Status: APPROVED. Technical references reviewed on 2026-10-23. Documentation can change; implementation will pin and verify concrete versions.

## Primary assignment

Local source: C:/Users/konda/Downloads/FD Engineer Hiring Assignment.pdf.
Six pages, all extracted and reviewed; page 3 was also checked with layout-preserving extraction to distinguish required and optional UI columns.

PDF objectives and functional requirements: pp1–3.
Backend/workflow/guardrails/deliverables: pp3–4.
Evaluation/bonuses/submission: p5.
Hiring priorities: p6.

The PDF is project evidence. Its request to build/submit is subject to the user's explicit instruction to stop after specifications.

## Official technical references

| Reference | Design use |
| --- | --- |
| [FastAPI features](https://fastapi.tiangolo.com/features/) | Typed validation and API documentation |
| [React app from scratch](https://react.dev/learn/build-a-react-app-from-scratch) | Vite option and framework tradeoffs |
| [Vite guide](https://vite.dev/guide/) | Frontend build/runtime compatibility to verify at implementation |
| [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | Thread-scoped checkpoint state |
| [LangGraph memory](https://docs.langchain.com/oss/python/langgraph/add-memory) | Persistent conversation design |
| [LangChain models](https://docs.langchain.com/oss/python/langchain/models) | Model interface and structured output |
| [Google model integration](https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai) | Proposed provider adapter |
| [SQLGlot](https://sqlglot.com/) | Parsing and schema-aware analysis; not a security boundary by itself |
| [SQLite query_only](https://www.sqlite.org/pragma.html#pragma_query_only) | Read-only configuration limitations |
| [SQLite authorizer](https://www.sqlite.org/c3ref/set_authorizer.html) | Compile-time action authorization |
| [Python sqlite3](https://docs.python.org/3/library/sqlite3.html) | Runtime connection, cancellation, and callback APIs |
| [Render persistent disks](https://render.com/docs/disks) | Proposed storage/deployment constraints |

The stack selection, limits, API shape, and test thresholds are proposed engineering decisions, not requirements quoted from these sources.

## Decision register

| ID | Decision | Basis/status |
| --- | --- | --- |
| D01 | Specifications first; coding waits | Explicit user instruction; binding |
| D02 | Proposed commerce/employee schema | User selected option 1; confirmed |
| D03 | LangGraph instead of plain model chain | User request and PDF preference |
| D04 | FastAPI/Python and React/TypeScript | Proposed for approval |
| D05 | SQLite demo plus separate persisted state | Proposed; single-instance constraint explicit |
| D06 | Google Gemini adapter, configurable verified model | Proposed; credential/model availability unresolved |
| D07 | Conservative validation and explicit execution | Proposed; supports mandatory read-only guarantee |
| D08 | Follow-up treated as mandatory | PDF §3.6 overrides bonus classification |
| D09 | Clarify ambiguous January boundary | PDF prose/example conflict |
| D10 | Index recommendations are prose | Reconciles optimization requirement with no DDL generation |
| D11 | Included bonuses and deferrals as listed | Proposed scope; not all bonus features are mandatory |
| D12 | Render with persistence | Proposed, account/budget unresolved; no purchase authorized |

## Change control

After approval, record date, affected requirement IDs, rationale, and user-approved scope changes here. Update acceptance cases with behavior changes. Do not weaken SQL safety to accommodate a model failure.

Approval history: user approved all specifications on 2026-10-23 and authorized development. On 2026-10-24, the user requested completion/verification of the local project and deferred external publication/deployment.

Implementation compatibility decisions: local verification uses Python 3.13 (the installed interpreter), Docker targets Python 3.13, and the code remains Python 3.12-compatible. The available, generation-tested provider model is gemini-3.5-flash-lite; the initially configured 1.5 Flash was unavailable and 2.5 Flash rejected generation for this account. Provider-reported request limits require paced evaluation. Session cookies are opaque random tokens; CSRF uses random per-session tokens, so no unused SESSION_SECRET is required.

See docs/validation.md for actual results rather than treating acceptance criteria as completed tests.
