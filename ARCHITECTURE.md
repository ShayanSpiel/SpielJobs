# SpielJobs runtime architecture

SpielJobs is a Persian-first runtime job search engine. The MVP retrieves public vacancies on demand, interprets natural language when needed, ranks deterministically, and returns source evidence. The same bounded workflow serves web requests and MCP. It is not yet an exhaustive index, autonomous application agent, or social feed.

## Current boundaries

| Layer | Responsibility | Files |
| --- | --- | --- |
| Browser | RTL search, streaming, card presentation, seven-day device history | `frontend/app`, `frontend/lib/history.ts`, `frontend/lib/search-client.ts` |
| Transport | Input validation, request/body limits, CORS, SSE, PDF/DOCX extraction | `server.py`, `guards.py`, `resumes.py`, `mcp_server.py` |
| Orchestration | One prepare → retrieve → rank execution shared by HTTP/SSE/MCP | `agent.py` |
| Interpretation | Normalization, concepts, constraints, typo correction; optional bounded Mistral → Gemini call | `core.py`, `models.py` |
| Sources | Employer registry, platform parsers, first-party endpoint discovery, bounded requests, failure reports | `source_registry.py`, `sources.py`, `extra_sources.py`, `discovery.py` |
| Data boundary | Stable source record IDs, safe links, ISO dates, explicit nulls, invalid-row quarantine | `contracts.py` |
| Quality | Conservative grouping, post-enrichment filtering, trace-linked request-scoped evaluation | `deduplicate.py`, `evaluation.py`, `tracing.py` |

Keep this a modular application. Adding employers should usually add configuration and a captured fixture, not orchestration branches or a new agent. A new platform needs its own parser and contract tests. Browser rendering belongs in a separate controlled worker if a source cannot expose an accessible public API or server-rendered page; it does not belong inside every Vercel search request.

## Data contract

Every retrieved vacancy has a stable ID derived from source + URL, source identity, original URL, employer, title, optional location/date, checked time, and evidence-backed status. Unknown data stays null/unknown. Native IDs can be introduced by an adapter without changing the public response. A grouped job retains every constituent offer and its salary/date/status. Cross-source grouping is conservative and can still be uncertain when dates are missing.

`salary` preserves displayable source text. `compensation` provides optional minimum, maximum, currency, period and unit. Do not infer millions, toman, monthly pay, or net/gross pay from bare numbers. Persian digit presentation happens in one frontend formatter, not separately inside cards. Source dates are ISO Gregorian calendar dates; relative display uses Iran time and the Persian calendar.

A source report records checked time, request count, state, matched count and optional `failure_kind`/HTTP status. Blocked, rate-limited, timeout, connection failure, missing endpoint and schema change are distinct failures. An unparsed page is not evidence of zero jobs. Cached reports retain their original checked time and report zero new requests. Public employer snapshots have a 60-second warm-instance cache; failures have a 15-second cooldown. This cache is an optimization, not persistent ingestion or a cross-instance consistency guarantee.

## Query quality and AI

Simple recognizable searches use deterministic code. Ambiguous, contextual, résumé-based and longer requests use bounded model interpretation with provider fallback. The interpreter proposes role phrases; it does not invent jobs, decide source availability or override hard filters. Explicit exclusion terms are applied to titles. Date filters exclude unknown dates; Tehran filters exclude unknown locations. Recognized senior/junior requests require matching title evidence. Some constraints, including strict remote-only requests, remain explicitly unsupported rather than silently ignored.

Retrieval uses bounded complete phrases and bilingual concept alternatives. Ranking is explainable lexical matching, not semantic career-fit scoring. Enrichment is bounded, then results are filtered again to exclude newly identified closed vacancies. At most 50 results are returned. These choices trade recall for bounded latency and conservative matching; the product must not claim world-class relevance or full coverage without independent reviewed labels.

## Persistence and the next stages

Device history is a capped local cache of 20 conversations and 30 messages per conversation, expiring after seven days. It stores queries and returned public job evidence, not résumé contents or filenames. It offers reopen/delete; storage failures are visible. There is no cross-device account sync today.

`backend/migrations/001_search_engine.sql` is an additive persistence foundation, not an applied migration. It separates employers, canonical jobs, source offers, sources, private search runs and saved jobs. Stable offer identities and content hashes support idempotent upserts. Source offers retain freshness and provenance; deduplication does not destroy postings. Public listing reads and private owner-scoped tables use RLS. Apply it only to the confirmed project and verify advisors/policies before connecting it. The available Supabase connection currently exposes no projects.

For an indexed feed, introduce scheduled source ingestion, durable jobs, source health history, canonical offer upserts and cursor pagination on `(first_seen_at,id)`. Add authenticated saved jobs and search sync after consent/retention UX. For agent actions, use the current search tool as a read capability; add separate action permissions, approval boundaries, idempotency keys and audit records for applying or messaging. Do not make a search request an unbounded autonomous loop.

## Reliability and deployment

Deploy the FastAPI service and Next.js frontend as separate Vercel projects in Frankfurt. The frontend uses a same-origin external rewrite to the backend; Python/MCP remain independently deployable. The search budget is 105 seconds inside a 120-second function. Each employer retrieval has a 10-second budget; concurrent source calls and detail enrichments are bounded. Browser cancellation cancels graph work. Shared Redis limits are supported and fail closed if the configured limiter fails. Without Redis, only per-process controls exist; shared quotas must be configured before public release.

Evaluation is awaited and bounded within the request lifecycle, including trace flush. There are no detached evaluation tasks relying on a warm process or shutdown hooks. This improves serverless delivery but does not provide durable retries. Add a durable queue before requiring guaranteed evaluation delivery at scale.

## Release gate

Passing offline tests is necessary but insufficient. Release requires source/model connectivity from the hosting region, live API/SSE/MCP checks, reviewed Persian/English relevance cases, résumé checks, mobile journey checks, shared quotas, real Langfuse trace retrieval and a verified production URL. `scripts/audit_sources.py` records real adapter failures without pretending to measure recall. See `docs/DEPLOYMENT.md` and `HANDOFF.md` for current evidence and blockers.
