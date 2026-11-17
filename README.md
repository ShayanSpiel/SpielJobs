# SpielJobs

Persian-first runtime job search for an Iran pilot. A Next.js UI and a stateless FastAPI/MCP service share one bounded prepare → retrieve → enrich → rank workflow.

## Local development

Requires Node 22+ and Python 3.12+. Install frontend dependencies with `npm ci --prefix frontend`, create `.venv`, then install `backend/requirements.txt`. Copy `.env.example` to the ignored `.env` and configure the relevant services. Run `npm run dev` from the root. The UI uses port 3000 and the backend uses port 8000.

`npm run check` runs isolated offline API, ranking, upload, MCP, tracing, user-intent and frontend tests. `npm run build` builds the frontend. Development output uses `.next-dev`, independently of production `.next`.

Simple queries use deterministic code. Contextual queries and resumes can use Mistral with Gemini fallback. PDF/DOCX extraction is bounded. Search history stays on the device for seven days; resume contents and filenames are excluded.

## Deploy from this repository to Vercel

Create **two projects** from the same repository:

| Project | Root directory | Framework | Required configuration |
| --- | --- | --- | --- |
| `spieljobs-api` | `backend` | FastAPI | Server-side model/tracing keys, shared Redis quota credentials, allowed origins |
| `spieljobs` | `frontend` | Next.js | `SPIELJOBS_API_URL` set to the deployed HTTPS API origin |

Deploy the backend first, then the frontend. Set the intended frontend domain to `job.spielos.xyz` only after Vercel supplies the correct DNS record. Production search fails closed without shared quota configuration. See [deployment details](docs/DEPLOYMENT.md), [architecture](ARCHITECTURE.md), and [current release evidence](docs/RELEASE-REVIEW.md).

## MCP

Local stdio: `scripts/run-mcp.sh`. Remote HTTP: the backend's `/mcp`, or the frontend's `/api/runtime/mcp` once its external rewrite is configured. The tool is `search_live_jobs(query, resume_text='')`. Configure `NEXT_PUBLIC_MCP_URL` only after verifying the public endpoint; the landing page otherwise shows local connection instructions.

## Current limits

Source coverage is partial. Some employer sites require adapter repair or browser rendering. Unknown dates, locations, salaries and vacancy states are not fabricated. Ranking is lexical with controlled bilingual concepts and explicit constraints, not a guarantee of career fit. No reviewed paired benchmark proves an advantage over Jobinja or Google. The additive database migration is prepared but not applied.
