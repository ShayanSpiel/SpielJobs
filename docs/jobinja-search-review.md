# Jobinja search and ranking review

## Scope

Review of the current implementation on 16 November 2026. Findings are based on code inspection, existing offline tests, and a small synthetic ranking example. They are **not** a measurement of production precision, recall, freshness or actual Jobinja coverage. No new direct live comparison could be performed from this session. The current adapter has not been validated against all Jobinja pages and site behavior.

## What happens today

1. The user supplies a prompt and optionally a text-extracted PDF résumé. Python normalizes Persian/Arabic characters and extracts tokens, known synonyms, a date range and Tehran when present.
2. For a résumé only, an AI model is asked for up to 12 role and skill terms: Mistral first, then Gemini if the first provider fails. If neither returns useful terms, the code uses a small predefined vocabulary and reports a warning. Plain keyword or natural-language prompts without a résumé never call an AI model.
3. The search node sends at most three prompt-derived terms plus up to two résumé-derived terms, capped at four overall, to the Jobinja search endpoint in parallel. Each request retrieves only its first results page. It does not check every page or site.
4. The adapter parses listing HTML into title, company, location, relative posting date, source link and a logo when available. Descriptions are currently not retrieved from job details. Jobs are deduplicated by the complete URL.
5. Python filters by known Tehran locations and a recognized date limit. Where a date limit is used, jobs with unknown dates are excluded. It scores matching whole terms: 5 per title term, 2 per description term, 1 per company term; relevance comes first and date breaks ties. Results returned by this ranking are the app's recommendations, not a separate recommendation model.

## Findings and examples

### 1. Search terms lose the actual role

For `مدیر محصول هوش مصنوعی در تهران`, the source receives separate searches for `مدیر`, `محصول`, and `هوش`. Those are broad terms, rather than complete role concepts. Similarly `AI product manager in Tehran` becomes separate `ai`, `product`, and `manager` searches. Results depend heavily on the first page of each broad query. Some relevant roles may never enter the candidate pool.

### 2. One generic matching word can qualify an irrelevant role

In a deliberately small synthetic example, the Persian request above ranked `مدیر محصول هوش مصنوعی` first, `AI Product Manager` second, and the unrelated `مدیر فروش` third because it matched `مدیر`. This illustrates a concrete false-positive mechanism; it is not a measured precision score for Jobinja.

### 3. Skills in descriptions are missed

Although the scorer can read a `description`, the current Jobinja adapter sets it to `None`. A role whose relevant skills appear only in its description can be dropped by the local ranking even if the source returns it for a skill search. Company and employment details are also incomplete.

### 4. Search and recommendation are not semantic

Matching is based on terms and a small synonym dictionary. It does not understand whether a candidate has the relevant level, or that an AI transformation lead and an enablement lead may be related. Explicit request terms and résumé terms contribute to the same basic score. The recommendation does not check qualifications, salary, experience requirements or user preferences comprehensively.

### 5. Freshness and status are uncertain

The adapter converts some relative dates to calendar dates using the current UTC date; the original wording and source timezone can affect interpretation. A visible listing is returned with status `unknown`, and there is no independent check that the role is still accepting applications. One page per term makes coverage incomplete; lack of a date removes a result when a time filter is active.

### 6. Deduplication and source health need improvement

Only exact URLs are deduplicated; tracking parameters or the same posting on another source may leave duplicates. Source reports are aggregated by source, so individual keyword failures can be obscured by successful requests.

## Recommended order

1. **Measure before tuning:** collect a small, permitted, manually verified Jobinja sample for Persian/English role searches and résumé examples. Record expected results, irrelevant results, source page count, dates and open-status evidence. Include real but privacy-safe fixtures and assess precision@3 and recall against the sample.
2. **Keep intent intact:** identify job-title and skill phrases, recognized location, and time constraints separately. Use targeted role phrases and bilingual alternatives in source requests instead of simply taking the first tokens. Distinguish required constraints from optional preferences; generic words alone should not qualify a job.
3. **Retrieve detail pages in a bounded way:** retrieve descriptions and explicit status/date signals for a limited shortlist when permitted; apply sensible concurrency and source rate limits. Keep unknown status and report unavailable detail pages honestly.
4. **Improve ranking:** weight title and required skills; treat seniority, location and negative constraints explicitly. Deduplicate by source ID/canonical URL and, later, across employers and boards. Explain why a result matched and what could not be checked.
5. **Use AI selectively:** keep direct keyword searches deterministic. For a complex prompt or résumé, use one low-cost structured profile extraction only when needed; optionally re-rank a bounded shortlist when the user asks for nuanced matching. Compare AI and deterministic variants on the same evaluation set before enabling by default.
6. **Improve coverage:** implement pagination with limits, proper empty/blocked detection, per-query reporting, cancellation and timeouts. Add more sources only after inspecting and testing their retrieval paths and access conditions.

## AI and privacy

The current AI call sends up to 12,000 characters of the extracted résumé and up to 2,000 characters of the prompt to the configured provider, attempting Mistral before Gemini on failure. It extracts search terms only; it does not perform live search, rank jobs or verify open status. The response strips résumé text and the app does not intentionally persist it. Model costs, connectivity and provider data-retention behavior depend on the configured account and provider. Uploaded scanned/image-only PDFs are not supported.
