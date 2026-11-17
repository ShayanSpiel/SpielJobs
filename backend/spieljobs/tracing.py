"""Privacy-conscious Langfuse instrumentation. Observability must not block a search."""
import functools
import logging
import os
import re
from contextlib import contextmanager
from pathlib import Path
from dotenv import load_dotenv
from .urls import canonical_public_url
from .revision import RUNTIME_REVISION

load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=False)
logger=logging.getLogger(__name__)
_client=None

def safe_text(value, limit=2000):
    """Remove common contact details and credential shapes from observed text."""
    text=str(value or '')[:limit]
    text=re.sub(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b','[email]',text)
    text=re.sub(r'(?<!\w)(?:\+?[0-9۰-۹٠-٩][\s().-]*){10,15}(?!\w)','[phone]',text)
    return re.sub(r'(?i)\b(?:sk|pk|api[_-]?key)[-_][a-z0-9_-]{12,}\b','[credential]',text)

def trace_input(query, resume):
    return {'request':safe_text(query), 'context':{'resume_attached':bool(resume),'resume_characters':len(resume),'resume_text_recorded':False}}

def summarize_jobs(jobs, limit=100):
    return [{'title':safe_text(job.get('title'),200), 'company':safe_text(job.get('company'),200),
             'url':canonical_public_url(job.get('url')), 'source':job.get('source'),
             'location':safe_text(job.get('location'),200), 'description':safe_text(job.get('description'),1000),
             'salary':safe_text(job.get('salary'),200), 'contract':safe_text(job.get('contract'),200),
             'experience':safe_text(job.get('experience'),200), 'skills':[safe_text(s,100) for s in (job.get('skills') or [])],
             'posted_date':job.get('posted_date'), 'status':job.get('status'), 'status_evidence':safe_text(job.get('status_evidence'),300),
             'sources':[{'id':s.get('id'),'url':canonical_public_url(s.get('url'))} for s in (job.get('sources') or [])],
             'match_terms':[safe_text(t,100) for t in job.get('match_terms',[])], 'score':job.get('score')}
            for job in jobs[:limit]]

class NoopObservation:
    active=False
    id=None
    def update(self, **kwargs): pass

class SafeObservation:
    active=True
    def __init__(self, inner): self.inner=inner
    @property
    def id(self): return getattr(self.inner,'id',None)
    def update(self, **kwargs):
        try: self.inner.update(**kwargs)
        except Exception: logger.warning('Langfuse observation update failed')

def get_trace_client():
    global _client
    if os.getenv('SPIELJOBS_TRACING_ENABLED','true').lower() in ('false','0','no'):
        return None
    if not os.getenv('LANGFUSE_PUBLIC_KEY') or not os.getenv('LANGFUSE_SECRET_KEY'):
        return None
    if _client is None:
        try:
            from langfuse import Langfuse
            os.environ.setdefault('LANGFUSE_RELEASE',os.getenv('VERCEL_GIT_COMMIT_SHA') or RUNTIME_REVISION)
            _client=Langfuse(base_url=os.getenv('LANGFUSE_BASE_URL','https://cloud.langfuse.com'),
                environment=os.getenv('LANGFUSE_TRACING_ENVIRONMENT') or os.getenv('VERCEL_ENV','development'),
                flush_interval=2.0, timeout=3)
        except Exception:
            logger.warning('Langfuse initialization failed; search continues')
            return None
    return _client

@contextmanager
def trace_scope(*,session_id=None,channel='api_or_mcp',run_id=None,trace_name='spieljobs.search'):
    """v4 correlation belongs to each observation, including model children."""
    if get_trace_client() is None:
        yield
        return
    try:
        from langfuse import propagate_attributes
        metadata={'app':'spieljobs','channel':channel,'runtime_revision':RUNTIME_REVISION}
        if run_id: metadata['run_id']=run_id
        manager=propagate_attributes(session_id=session_id,trace_name=trace_name,
            version=RUNTIME_REVISION,tags=['spieljobs',channel],metadata=metadata)
        manager.__enter__()
    except Exception:
        logger.warning('Langfuse correlation scope unavailable; search continues')
        yield
        return
    try:
        yield
    finally:
        try: manager.__exit__(None,None,None)
        except Exception: logger.warning('Langfuse correlation scope close failed')

@contextmanager
def observation(name, as_type='span', **kwargs):
    client=get_trace_client()
    if client is None:
        yield NoopObservation()
        return
    try:
        manager=client.start_as_current_observation(name=name, as_type=as_type, **kwargs)
        span=manager.__enter__()
    except Exception:
        logger.warning('Langfuse observation start failed; search continues')
        yield NoopObservation()
        return
    try:
        yield SafeObservation(span)
    except BaseException as exc:
        try:
            SafeObservation(span).update(level='ERROR', status_message=type(exc).__name__)
            manager.__exit__(None,None,None)
        except Exception: logger.warning('Langfuse observation close failed')
        raise
    else:
        try: manager.__exit__(None,None,None)
        except Exception: logger.warning('Langfuse observation close failed')

def traced_node(name, as_type='span'):
    def decorate(function):
        @functools.wraps(function)
        async def wrapper(state):
            profile=state.get('profile') or {}
            with observation(name,as_type,input={'request':safe_text(state.get('query','')), 'has_resume':bool(state.get('resume')), 'search_terms':[safe_text(t,100) for t in profile.get('search_terms',[])], 'candidate_count':len(state.get('jobs',[]))}) as span:
                result=await function(state)
                out_profile=result.get('profile') or {}
                sources=result.get('sources') or []
                span.update(output={'interpretation':out_profile.get('interpretation'), 'extracted_keywords':[safe_text(t,100) for t in out_profile.get('terms',[])], 'source_queries':[safe_text(t,100) for t in out_profile.get('search_terms',[])], 'model_used':result.get('model_used'), 'jobs':summarize_jobs(result.get('jobs',[])), 'job_count':len(result.get('jobs',[])), 'sources':[{'id':s.get('id'), 'state':s.get('state'), 'requests':s.get('requests'),'terms':[safe_text(t,100) for t in s.get('terms',[])]} for s in sources], 'warnings':[safe_text(w,300) for w in result.get('warnings',[])]})
                return result
        return wrapper
    return decorate

def flush_trace_client():
    """Flush buffered observations at process shutdown without creating a new client."""
    if _client is not None:
        try: _client.flush()
        except Exception: logger.warning('Langfuse flush failed')

def current_trace_id():
    client = get_trace_client()
    if client is None: return None
    try: return client.get_current_trace_id()
    except Exception: return None
