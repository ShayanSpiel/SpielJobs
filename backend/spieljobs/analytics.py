"""Optional aggregate product events: no query, resume, job text or contact data."""
import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
import logging
import os
import re

logger=logging.getLogger(__name__)
_client=None
_identity=ContextVar('analytics_identity',default=None)

@contextmanager
def analytics_context(headers):
    distinct=headers.get('x-posthog-distinct-id','')
    session=headers.get('x-posthog-session-id','')
    clean=lambda value: value if re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',value) else None
    token=_identity.set((clean(distinct),clean(session)))
    try:yield
    finally:_identity.reset(token)

async def record_search(state,channel):
    global _client
    key=os.getenv('POSTHOG_PROJECT_TOKEN'); host=os.getenv('POSTHOG_HOST')
    if not key or not host:return
    try:
        if _client is None:
            from posthog import AsyncPosthog
            _client=AsyncPosthog(key,host=host,capture_exception_code_variables=False,timeout=1,max_retries=0)
        distinct,session=_identity.get() or (None,None)
        properties={'app':'spieljobs','channel':channel,'run_id':state['run_id'],
            'result_count':len(state.get('jobs',[])),
            'available_sources':sum(s.get('state') in ('success','partial') for s in state.get('sources',[])),
            'source_count':len(state.get('sources',[])),
            'duration_ms':state.get('runtime',{}).get('duration_ms'),
            '$process_person_profile':False,'$geoip_disable':True}
        if session:properties['$session_id']=session
        async with asyncio.timeout(2):
            await _client.capture_immediate('search_runtime_completed',distinct_id=distinct or state['run_id'],properties=properties)
    except Exception as exc:
        logger.warning('PostHog delivery unavailable: %s',type(exc).__name__)
