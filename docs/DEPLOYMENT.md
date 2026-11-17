# Vercel deployment

The repository contains two independently deployable services. Deployment is now user-managed; do not create or overwrite an unrelated Vercel project.

## 1. Backend

Import the repository with root directory **`backend`** and framework **FastAPI**. `pyproject.toml` selects `spieljobs.server:app`; `vercel.json` sets Frankfurt and a 120-second maximum function duration. `.python-version` selects Python 3.12.

Set environment variables from `.env.example` through Vercel's encrypted environment settings. Keep keys off the frontend. Model keys are optional for ordinary keyword searches, but required to verify intelligent interpretation. Langfuse keys enable trace export. Set `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` for shared atomic request limits and public employer snapshots. Successful employer snapshots remain fresh for five minutes and can provide a dated fallback for up to 30 minutes when a refresh fails transiently. The snapshot keys are versioned by code revision and source configuration; they contain public listings only. In production, missing or unavailable shared limits block protected requests rather than expose unbounded paid usage. Defaults: 10 requests/IP/minute, 120 requests/global/minute, 4 concurrent protected requests per process. These are pilot controls, not load-test evidence.

`/health` is liveness and configuration reporting, not a claim that sources/models/tracing work. Its revision fingerprints the loaded source. Check that value before running acceptance tests. The app exposes `/search`, `/search/stream`, `/resume`, and stateless Streamable HTTP MCP at `/mcp`.

## 2. Frontend

Import the same repository with root directory **`frontend`**, framework **Next.js**, install `npm ci`, build `npm run build`. Set **`SPIELJOBS_API_URL=https://<deployed-backend-host>`** with no path or credentials. Requests use the same-origin `/api/runtime/*` rewrite. A production frontend build refuses missing API configuration. A direct `NEXT_PUBLIC_API_URL` override is also supported, but requires matching backend CORS.

After API/MCP verification, set `NEXT_PUBLIC_MCP_URL` to the verified public MCP endpoint and `NEXT_PUBLIC_PROJECT_REPOSITORY` to the actual GitHub repository. These are build-time public values. The page must not advertise an unverified endpoint or a nonexistent repository.

## 3. Domain

Add **`job.spielos.xyz`** to the frontend project. Use exactly the DNS target returned by Vercel, then verify HTTPS. Do not modify the root `spielos.xyz` website or point the domain at an unverified deployment.

## 4. Acceptance

Run `npm run check` and build the frontend. Run `scripts/audit_sources.py` from the hosting region. Exercise the real personas in `evals/personas.json`, including skill-only, non-Tehran, management, date-constrained and unavailable-source journeys. Check original application pages; do not infer vacancy status from HTTP 200 alone. Verify streamed progress, cancel/retry, PDF/DOCX, history reload/delete, source expansion, two-line descriptions and mobile navigation. Initialize MCP, list tools and call the live tool through the production URL. Retrieve a real Langfuse root trace and numeric/categorical scores from the matching project.

Source is published at https://github.com/ShayanSpiel/SpielJobs. Deployment and live acceptance remain separate release gates; use the checks above after creating both Vercel projects.
