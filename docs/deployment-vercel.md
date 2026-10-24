# Deploy Querycraft to Vercel with Neon

This deploys the React interface and FastAPI API together at one HTTPS address. Neon stores sessions, conversations, saved results, quotas, and LangGraph checkpoints. Queries still run against the bundled, read-only synthetic SQLite database.

## 1. Push the deployment changes

Commit the Vercel/PostgreSQL implementation and documentation, then push main to:
https://github.com/VinodKondawar26/FDE_SQL_AI_ASSISTANT

Do not add .env, local databases, or temporary PowerPoint files. The database passwords and Gemini key belong only in local .env and Vercel's environment settings.

## 2. Import the repository

In the Vercel dashboard, choose **Add New > Project**, find **FDE_SQL_AI_ASSISTANT**, and click **Import**.

- Framework Preset: **FastAPI**.
- Root Directory: repository root (leave the default); do not select frontend.
- Build Command: uses vercel.json, **python scripts/vercel_build.py**.
- Output Directory and Install Command: leave the framework defaults.
- Node.js version: 22.x if a version selector is available.
- Python version: .python-version selects 3.13.

The build installs Python dependencies, builds React, seeds the sample database, and creates the PostgreSQL tables. No separate frontend or backend deployment is required.

## 3. Add environment variables before deploying

Select Production for the initial deployment. Copy values into Vercel directly; never share their contents in chat or screenshots.

| Name | Value |
| --- | --- |
| GOOGLE_API_KEY | Your Gemini key from local .env |
| MODEL_NAME | The tested model ID from local .env |
| MODEL_PROVIDER | google_genai |
| DATABASE_URL | Neon pooled URL; starts with postgresql:// |
| DATABASE_URL_UNPOOLED | Neon direct URL; starts with postgresql:// |
| DAILY_MODEL_CALLS | 500, or a lower daily demo limit |

Paste only each value, without the variable name or enclosing quotes. Keep Neon's SSL parameters.

The app requires BOTH database URLs: pooled connections handle application storage; direct connections handle checkpoints and conversation locks. Do not replace the direct URL with a pooled URL.

Leave PUBLIC_ORIGIN unset initially. The app trusts Vercel's own deployment and production hostnames and enables secure cookies automatically. Do not copy the local http://localhost:8000 origin into Vercel. Keep automatically exposed system environment variables enabled in project settings. If using a custom domain, set PUBLIC_ORIGIN to its exact https:// address without a trailing slash.

You can alternatively connect neon-bole-blanket from **Storage > Connect to Project** and use the injected variables. Verify the exact names DATABASE_URL and DATABASE_URL_UNPOOLED in Project Settings > Environment Variables. If a custom prefix was used, add the two expected names explicitly.

For Preview deployments, use a separate Neon branch/database with its own credentials. Do not point untrusted preview code at the production database. A distinct DATABASE_SCHEMA can separate tables but is not an access-control boundary.

## 4. Deploy and inspect

Click **Deploy**. Build logs should show the frontend build, sample seeding, and:
PostgreSQL application and LangGraph tables are ready.

If variables are added or corrected after a failed build, select **Redeploy**. Environment changes require a new deployment.

When status is Ready, open the stable production domain from the project dashboard.

## 5. Verify before sharing

1. Open /api/v1/health/ready on the production domain; it should return HTTP 200.
2. Ask: Show customer_id and first_name for all customers. Run the query: 80 rows.
3. Ask: Only those from California. Run the query: 40 rows.
4. Refresh; verify the conversation remains. Download CSV and SQL.
5. Open an incognito window; verify it starts a separate history.
6. Ask an unrelated sports question; it should be refused.
7. Share the stable production URL, not a temporary preview URL.

Check the production URL in an incognito browser before sharing. If Vercel asks reviewers to sign in, review Project Settings > Deployment Protection and permit public access to the production deployment. Application session cookies still separate each visitor's history.

## Troubleshooting

- **Database setup failed:** verify both URLs, the Neon database status, and direct connection access. This runs before the deployment becomes active.
- **503 model unavailable:** check GOOGLE_API_KEY and MODEL_NAME, then redeploy.
- **403 origin:** check PUBLIC_ORIGIN and Vercel's automatic system environment variables; use the stable production URL.
- **Frontend missing / 404:** ensure root directory is the repository root and the build completed. Do not deploy only frontend.
- **Turn timeout:** check provider quota and function logs. Keep the Vercel function region close to Neon. The app's AI deadline is 45 seconds; the configured function limit is 60 seconds.
- **429:** the app has session, IP, concurrency, and daily model limits. Wait for the limit to reset; do not remove protections from the public demo.
- **Local Windows PostgreSQL error mentioning ProactorEventLoop:** launch with scripts/start.ps1, which selects the compatible event loop.

## Local PostgreSQL verification

With both URLs in local .env:

~~~powershell
.\.venv\Scripts\python.exe -m scripts.setup_database
$env:RUN_POSTGRES_TESTS = "1"
.\.venv\Scripts\python.exe -m pytest backend/tests/test_postgres.py -q
Remove-Item Env:RUN_POSTGRES_TESTS
.\.venv\Scripts\python.exe -m scripts.live_smoke
~~~

The integration tests create a random qc_test_* schema and delete only that schema afterward. Live smoke uses the real model and removes its own conversation. Hosted HTTP validation remains necessary after deployment.

References: [Vercel FastAPI deployment](https://vercel.com/docs/frameworks/backend/fastapi), [Python runtime](https://vercel.com/docs/functions/runtimes/python), [Neon connection strings](https://neon.com/docs/connect/connect-from-any-app).
