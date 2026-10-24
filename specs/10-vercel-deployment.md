# Vercel deployment adaptation

Authorized by the user's request to move to Vercel after Render/Railway sign-in failures, 2026-10-24.

The read-only SQL query database remains the same build-time SQLite sample. Application sessions, conversations, artifacts, result snapshots, quotas, and LangGraph checkpoints use hosted PostgreSQL (Neon). Local SQLite persistence remains supported when DATABASE_URL is unset.

DATABASE_URL is the pooled application connection. DATABASE_URL_UNPOOLED is the direct connection for checkpoint setup/runtime and session advisory locks. Credentials stay in excluded .env and Vercel environment settings. No database URLs are logged.

Multiple function instances coordinate conversation mutations, explicit execution, and the global model concurrency limit with PostgreSQL advisory locks. Recovery happens only while holding a conversation lock; a cold start must never mark another instance's active turn interrupted. Quotas remain atomic across instances. Cleanup is performed on incoming session requests with database locking, rather than depending on a background timer continuing after a serverless request ends.

The app and compiled React UI share one Vercel origin. A trusted Vercel deployment hostname is accepted alongside an explicit PUBLIC_ORIGIN; arbitrary Host headers are not trusted. Cookies use Secure on Vercel. The function budget is 60 seconds and the model turn budget remains 45 seconds.

Acceptance: existing deterministic tests; real PostgreSQL storage/checkpoint round trip; independent app instances reading the same history; overlapping requests rejected; atomic quotas; cold-start recovery; ownership/exports; actual Gemini smoke through the PostgreSQL-backed API; Vercel build configuration; final public health, UI, and AI request after deployment.

This amendment changes persistence/hosting, not the assistant's SQL dialect, supported schema, model prompts, or SQL validation boundary.
