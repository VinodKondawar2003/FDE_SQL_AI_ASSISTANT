# Deployment runbook

The current target is Vercel + Neon. Follow the [Vercel deployment walkthrough](deployment-vercel.md). PostgreSQL persistence is locally verified; no public Vercel deployment has been verified yet. Docker and the original Render alternative are documented below.

## Local

Use scripts/start.ps1 on Windows or the README uvicorn command. The application is at http://localhost:8000. Use exactly that browser origin with the default PUBLIC_ORIGIN; 127.0.0.1 is a different origin. The Vite development origin is an alternative configuration, not an additional trusted origin.

## Docker

Create the excluded .env file, configure the model, and run docker compose up --build. The service exposes port 8000. Application/checkpoint state is in the querycraft-state named volume. Do not remove that volume unless intentionally resetting all conversation history.

The image is single-worker, non-root, and seeds its immutable sample database at build time. It does not copy .env or credentials. Docker execution remains an environment-dependent check when Docker is unavailable locally.

## Render after account connection

1. Publish the source to the chosen GitHub repository.
2. Create a Render Blueprint from render.yaml. The starter service plus persistent disk incurs hosting charges; review current costs before creation.
3. Set GOOGLE_API_KEY, verify MODEL_NAME is accessible, and set PUBLIC_ORIGIN to the exact generated HTTPS app origin without a trailing slash.
4. Keep SECURE_COOKIES=true, /var/data persistent, and the single-worker Docker command.
5. Confirm /api/v1/health/live and /api/v1/health/ready, then exercise a real query in an incognito browser.
6. Confirm two browsers cannot read each other's conversation IDs. Restart the service and confirm owned history persists.
7. Record the actual URL in the README and delivery status. Do not substitute a build dashboard link.

Health readiness checks configuration and storage; it does not spend tokens. A real post-deployment model query is required because a configured model may be inaccessible for an account.

## Rollback and operations

Redeploy the previously verified image while retaining /var/data. Back up application and checkpoint files together using a coordinated SQLite backup/maintenance window. Do not copy active SQLite files without accounting for WAL state.

Quotas are persisted. Rate errors should be retried after the indicated delay. The default daily model ceiling is 500 calls, including retries. The evaluation runner uses its own temporary state and paced calls; evaluations still incur provider usage.

The model may be changed only after compatibility and live evaluation. Never silently replace production provider failures with test responses.
