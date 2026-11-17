from typing import TypedDict, Any
import asyncio
from time import perf_counter
from uuid import uuid4
from .revision import RUNTIME_REVISION
from langgraph.graph import StateGraph, START, END
from .core import extract_resume_terms, fallback_resume_role, needs_interpretation, parse_query, rank_and_filter, STOP, normalize, GENERIC_QUALIFIERS, contains_term, CITIES
from .sources import collect, enrich_jobs
from .models import extract_profile
from .tracing import observation, traced_node, current_trace_id, trace_input, flush_trace_client, trace_scope
from .evaluation import make_record, stage_snapshot, complete_evaluation
from .extra_sources import enrich_extra

class State(TypedDict, total=False):
    query: str
    resume: str
    profile: dict[str, Any]
    jobs: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    model_used: str | None
    warnings: list[str]

@traced_node('spieljobs.prepare', 'chain')
async def prepare(state):
    profile = parse_query(state['query'])
    warnings=[]; provider=None
    if profile['corrections']:
        changes='، '.join(f"{item['original']} ← {item['corrected']}" for item in profile['corrections'])
        warnings.append(f'جست‌وجو با اصلاح املایی انجام شد: {changes}')
    query_terms = profile['terms']
    cv_terms = []
    resume = state.get('resume', '')
    interpret = needs_interpretation(state['query'], resume) and not profile.get('unsupported_constraints')
    model_terms = []
    if interpret:
        cv_terms = extract_resume_terms(resume) if resume else []
        diagnostics = {}
        model_terms,provider = await extract_profile(state['query'],resume, diagnostics=diagnostics)
        model_terms = [term for term in model_terms if normalize(term) not in STOP and normalize(term) not in GENERIC_QUALIFIERS and len(normalize(term)) > 1]
        if model_terms:
            cv_terms = list(dict.fromkeys(model_terms + cv_terms))[:12]
        elif resume and cv_terms:
            warnings.append('تحلیل هوشمند رزومه در دسترس نبود؛ عبارت‌های شناخته‌شده به‌صورت محلی استخراج شدند.')
        elif resume:
            reason = diagnostics.get('reason')
            if reason == 'not_configured':
                warnings.append('کلید مدل برای تحلیل رزومه تنظیم نشده است و واژه‌نامهٔ محلی هم موردی پیدا نکرد. این به معنی نداشتن مهارت در رزومه نیست.')
            else:
                warnings.append('تحلیل هوشمند رزومه پاسخ قابل استفاده نداد و واژه‌نامهٔ محدود محلی هم موردی پیدا نکرد. این به معنی نداشتن مهارت در رزومه نیست.')
        else:
            warnings.append('تحلیل هوشمند درخواست در دسترس نبود؛ جست‌وجو با تطبیق محدود واژه‌ها انجام شد.')
    profile['terms'] = list(dict.fromkeys((cv_terms + query_terms) if interpret else query_terms))[:30]
    # Resume/model expansion must preserve explicit query concept constraints.
    # A complex prompt's inferred search phrases need to reach the source.
    if model_terms and not resume:
        profile['search_terms'] = list(dict.fromkeys(model_terms[:4]))
    elif cv_terms:
        profile['search_terms'] = list(dict.fromkeys(profile['search_terms'][:1] + cv_terms[:3]))[:4]
    else:
        profile['search_terms'] = profile['search_terms'][:4]
    profile['interpretation'] = 'blocked' if profile.get('unsupported_constraints') else ('resume' if resume else ('complex_prompt' if interpret else 'deterministic'))
    if resume and not provider and not query_terms and any(word in normalize(state['query']) for word in ('رزومه','resume')):
        profile['fallback_resume_role']=fallback_resume_role(resume)
        if profile['fallback_resume_role']:
            profile['terms']=list(dict.fromkeys(profile['fallback_resume_role']+profile['terms']))[:30]
    if profile.get('unsupported_constraints'):
        warnings.append('این نسخه هنوز نمی‌تواند محدودیت درخواستی دورکاری یا استثنا کردن تهران را با اطمینان بررسی کند؛ برای جلوگیری از نتیجهٔ گمراه‌کننده جست‌وجو انجام نشد.')
    return {'profile':profile,'model_used':provider,'warnings':warnings}

@traced_node('spieljobs.search_sources', 'retriever')
async def search(state):
    if not state['profile']['search_terms'] or state['profile'].get('unsupported_constraints'):
        return {'jobs': [], 'sources': []}
    jobs, sources = await collect(state['profile']['search_terms'],location=state['profile']['location']) if state['profile'].get('location') else await collect(state['profile']['search_terms'])
    return {'jobs':jobs, 'sources':sources}

@traced_node('spieljobs.rank', 'chain')
async def rank(state):
    # Enrich candidates before strict filtering: a skill such as SQL may be in
    # an accountant's description rather than its title. Title-only prefiltering
    # previously discarded exactly the evidence needed to answer those users.
    profile=state['profile']
    terms=profile.get('terms',[])
    def affinity(job):
        title=job.get('title') or ''; body=job.get('description') or ''
        return sum(10 for term in terms if contains_term(title,term)) + sum(2 for term in terms if contains_term(body,term)) + (1 if job.get('source') in ('jobinja','jobvision') else 0)
    eligible=[job for job in state['jobs'] if job.get('status')!='closed' and (not profile.get('location') or any(contains_term(job.get('location') or '',name) for name in CITIES.get(profile['location'],[profile['location']])))]
    candidates=sorted(eligible,key=affinity,reverse=True)[:50]
    await asyncio.gather(enrich_jobs(candidates),enrich_extra(candidates))
    jobs = rank_and_filter(state['jobs'], profile)
    warnings=list(state.get('warnings', []))
    if any(source.get('state') == 'stale' for source in state.get('sources', [])):
        warnings.append('بعضی منابع اکنون پاسخ ندادند؛ نتایج آن‌ها از آخرین بررسی موفق است و ممکن است تغییر کرده باشد. زمان بررسی در وضعیت منابع مشخص است.')
    if state.get('jobs') and not jobs:
        warnings.append('آگهی‌هایی پیدا شد، اما شواهد کافی برای معیارهای درخواستت نداشتند. عنوان کوتاه‌تر یا یک معیار کمتر را امتحان کن.')
    if len(jobs)>50:
        warnings.append('۵۰ نتیجهٔ اول نمایش داده می‌شود. برای محدود کردن نتایج، مهارت یا بازهٔ زمانی را اضافه کن.')
    jobs=jobs[:50]
    sources=[dict(source,matched_count=sum(1 for job in jobs if any((entry.get('id') or '').lower()==(source.get('id') or '').lower() for entry in job.get('sources',[])) or (job.get('source') or '').lower()==(source.get('id') or '').lower())) for source in state.get('sources',[])]
    return {'jobs':jobs, 'sources':sources, 'warnings':warnings}

builder = StateGraph(State)
builder.add_node('prepare',prepare)
builder.add_node('search',search)
builder.add_node('rank',rank)
builder.add_edge(START,'prepare')
builder.add_edge('prepare','search')
builder.add_edge('search','rank')
builder.add_edge('rank',END)
graph = builder.compile()

async def search_events(query: str, resume: str = '', channel: str = 'api_or_mcp', session_id: str | None = None):
    """One orchestration path for HTTP, SSE and MCP; no detached work."""
    if not query.strip() or len(query) > 2000 or len(resume) > 30000:
        raise ValueError('Invalid search input')
    started=perf_counter(); run_id=uuid4().hex; stage_started=started
    with trace_scope(session_id=session_id,channel=channel,run_id=run_id), observation('spieljobs.search', 'agent', input=trace_input(query,resume)) as span:
        async with asyncio.timeout(105):
            state = {'query': query, 'resume': resume}; stages = []
            blocked = bool(parse_query(query).get('unsupported_constraints'))
            interpret = needs_interpretation(query, resume) and not blocked
            yield 'status', {'phase': 'prepare', 'uses_model': interpret,
                'interpretation': 'blocked' if blocked else 'resume' if resume else 'complex_prompt' if interpret else 'deterministic'}
            async for mode, update in graph.astream(state, stream_mode=['updates', 'custom']):
                if mode == 'custom':
                    yield 'source_progress', update
                    continue
                for node, values in update.items():
                    state.update(values)
                    snapshot=stage_snapshot(node, values)
                    snapshot['duration_ms']=round((perf_counter()-stage_started)*1000)
                    stage_started=perf_counter()
                    stages.append(snapshot)
                    if node == 'prepare':
                        yield 'status', {'phase': 'search', 'model_used': values.get('model_used'), 'terms': values['profile']['search_terms'], 'sources': []}
                    elif node == 'search':
                        yield 'status', {'phase': 'rank', 'sources': values['sources'], 'found': len(values['jobs'])}
            state.pop('resume', None)
            trace_id = current_trace_id() if span.active else None
            state['trace_id'] = trace_id
            state['run_id'] = run_id
            state['session_id'] = session_id
            state['observation_id'] = span.id
            state['runtime'] = {'revision':RUNTIME_REVISION,'retrieval_ms':round((perf_counter()-started)*1000),'stages':[{k:v for k,v in step.items() if k in ('step','duration_ms')} for step in stages]}
            record = make_record(query, resume, state, stages, channel)
            # An observation evaluator cannot read a sibling or child. Keep
            # its complete end-to-end contract on this one root observation.
            span.update(input={**record['input'],'profile':{
                'extracted_keywords':record['process']['extracted_keywords'],
                'constraints':record['process']['constraints']}},
                output={**record['output'],'sources':record['process']['sources'],'runtime':state['runtime']},
                metadata={'evaluation_contract':'spieljobs-observation/1'})
            # Request-scoped evaluation finishes before the response closes.
            # This avoids relying on a warm instance or shutdown hooks.
            await complete_evaluation(trace_id, record)
    # Close the root observation before flushing it. Flushing inside the span
    # exported children but could lose the root on a frozen serverless instance.
    if trace_id:
        try:
            async with asyncio.timeout(3):
                await asyncio.to_thread(flush_trace_client)
        except TimeoutError:
            pass
    state['runtime']['duration_ms']=round((perf_counter()-started)*1000)
    from .analytics import record_search
    await record_search(state,channel)
    yield 'result', state


async def search_jobs(query: str, resume: str = '', *,channel: str = 'api_or_mcp',session_id: str | None = None):
    async for kind, payload in search_events(query, resume,channel,session_id):
        if kind == 'result':
            return payload
