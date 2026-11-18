# Vercel deployment

The repository contains two independently deployable services. Deployment is now user-managed; do not create or overwrite an unrelated Vercel project.

## 1. Backend

Import the repository with root directory **`backend`** and framework **FastAPI**. `pyproject.toml` selects `spieljobs.server:app`; `vercel.json` sets Frankfurt and a 120-second maximum function duration. `.python-version` selects Python 3.12.

Set server environment variables through Vercel’s encrypted environment settings. For SpielJobs production, set `SPIELJOBS_SUPABASE_QUOTA_URL` to the deployed quota function. Keep keys off the frontend. Model keys are optional for ordinary keyword searches, but required to verify intelligent interpretation. Langfuse keys enable trace export. Set `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` for shared atomic request limits and public employer snapshots. Successful employer snapshots remain fresh for five minutes and can provide a dated fallback for up to 30 minutes when a refresh fails transiently. The snapshot keys are versioned by code revision and source configuration; they contain public listings only. In production, missing or unavailable shared limits block protected requests rather than expose unbounded paid usage. Defaults: 10 requests/IP/minute, 120 requests/global/minute, 4 concurrent protected requests per process. These are pilot controls, not load-test evidence.

`/health` is liveness and configuration reporting, not a claim that sources/models/tracing work. Its revision fingerprints the loaded source. Check that value before running acceptance tests. The app exposes `/search`, `/search/stream`, `/resume`, and stateless Streamable HTTP MCP at `/mcp`.

## 2. Frontend

Import the same repository with root directory **`frontend`**, framework **Next.js**, install `npm ci`, build `npm run build`. The production build sets `SPIELJOBS_API_URL` to the FastAPI deployment in `frontend/vercel.json`. Search and résumé upload use the same-origin `/api/runtime/*` rewrite. The MCP connection instructions derive their URL from the same FastAPI origin.

Verify the FastAPI origin before changing it in the frontend build configuration. Set `NEXT_PUBLIC_PROJECT_REPOSITORY` to the published GitHub repository if the footer should link to it.

## 3. Domain

Add **`job.spielos.xyz`** to the frontend project. Use exactly the DNS target returned by Vercel, then verify HTTPS. Do not modify the root `spielos.xyz` website or point the domain at an unverified deployment.

## 4. Acceptance

Run `npm run check` and build the frontend. Run `scripts/audit_sources.py` from the hosting region. Exercise the real personas in `evals/personas.json`, including skill-only, non-Tehran, management, date-constrained and unavailable-source journeys. Check original application pages; do not infer vacancy status from HTTP 200 alone. Verify streamed progress, cancel/retry, PDF/DOCX, history reload/delete, source expansion, two-line descriptions and mobile navigation. Initialize MCP, list tools and call the live tool through the production URL. Retrieve a real Langfuse root trace and numeric/categorical scores from the matching project.

Source is published at https://github.com/ShayanSpiel/SpielJobs. Deployment and live acceptance remain separate release gates; use the checks above after creating both Vercel projects.

## Shared production quota

Apply the search quota migration and deploy `supabase/functions/spieljobs-quota` with gateway JWT checks disabled. The function verifies a signed Vercel OIDC token for the production FastAPI project before calling the service-role-only Postgres RPC. Counters use a one-minute bucket, a 10-request client limit, and a 120-request global limit. The public site and MCP use the same quota through FastAPI.

A configured `/health` response confirms that the quota URL and adapter registry loaded. Verify with a real search and an MCP call before routing traffic to the deployment.
