# Search quality and verification

## What runs now

Persian and Arabic letter forms, digits, diacritics, and zero-width non-joiners are normalized. General Persian stopword data is from [Hazm](https://github.com/roshan-research/hazm/blob/master/hazm/data/stopwords.dat), distributed with its MIT license; common terms relevant to jobs such as «داده» and «رشد» are protected. The application does not currently import the Hazm Python package. Its generic stopword list is not a complete domain-specific language model.

Short requests are parsed deterministically. The retriever sends phrases rather than single unrelated words, with a small number of complete bilingual alternatives for recognized concepts. For short requests with at most three meaningful concepts, all must appear in the title or description; a generic specialist title is insufficient to qualify a body-only mention. Company names do not qualify results. Title and description matches are scored and recency breaks ties. This conservative rule can miss relevant jobs, especially when title wording or descriptions differ; it does not guarantee precision or recall.

Long or ambiguous prompts and résumés attempt model-based term extraction when a provider is configured. Otherwise the bounded vocabulary and keyword extraction are a fallback, with a warning. The model does not currently perform semantic reranking, infer complete career fit or independently verify a vacancy. Empty or noisy model terms can still fail to describe the user's goal.

The source adapter searches Jobinja's first page for each phrase, then checks up to 30 ranked job details in a bounded batch for logos and status. Ranking happens before details are enriched; much of the ranking therefore uses listing titles only. This is a key current quality limitation. A vacancy not retrieved cannot be ranked, and source search syntax and coverage still need live verification.

## Research and next evaluation

- [Hazm](https://github.com/roshan-research/hazm) offers normalization, tokenization, lemmatization and optional trained models. Its general stopwords alone cannot tell whether a job is relevant; its Python package was not installed or benchmarked here.
- [rank-bm25](https://github.com/dorianbrown/rank_bm25) provides lexical retrieval but explicitly requires separate preprocessing. It is useful when enough job descriptions form a corpus; it cannot resolve a user's role by itself. It was not installed or benchmarked here.
- The [multilingual E5 model card](https://huggingface.co/intfloat/multilingual-e5-small) describes multilingual embeddings and required query/passage prefixes. An embedding or reranking layer should only be adopted after comparison against human relevance labels for Persian and mixed-language Iranian job ads, with latency, model availability, data handling and cost measured.

Measure precision at three, irrelevant results among the first three, recall of known relevant listings in a captured source set, empty-result rate, constraint violations, date and location correctness, and extraction quality. Evaluate synonyms, mixed Persian/English, suffixes, company-name collisions, unrelated departments, multiple intent concepts, long career descriptions, scanned PDFs, provider failure, and unavailable sources. Human review must label actual user goals and job evidence; synthetic tests cannot certify live relevance.

## Running checks

```bash
cd /Users/shayan/Documents/ChatGPT/spieljobs
SPIELJOBS_TRACING_ENABLED=false PYTHONPATH=backend .venv/bin/python -m unittest discover -s tests -q
bash scripts/run_backend.sh
```

In another terminal, run:

```bash
.venv/bin/python scripts/live_search_check.py
.venv/bin/python scripts/check_langfuse.py
```

The live script prints actual titles and URLs for manual review; it deliberately does not claim a precision score without labels. The Langfuse check sends a synthetic trace and reads it back, allowing time for asynchronous ingestion. The API health response includes a runtime revision and whether credentials are present, but does not assert that credentials or network access work. Search results expose the trace ID when the SDK can create one; that alone does not prove delivery.

On 2026-11-16, the automated checks used synthetic or mocked data. Three attempted live Jobinja searches returned connection errors in the restricted execution environment; no live ranking quality or cloud trace delivery was verified there.
