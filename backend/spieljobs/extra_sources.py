"""Read-only source adapters; unavailable and unparsable pages stay explicit."""
import asyncio
import re
import time
import weakref
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from .tracing import observation, safe_text, summarize_jobs

from .source_registry import JOBVISION, CAREERS, configured
from .contracts import normalize_jobs, source_failure
from .discovery import fetch_career_page
from .source_snapshots import load_snapshot, save_snapshot

# Process-local, bounded to the registered employers. Never cache failures over
# successful snapshots. A warm worker can survive a transient upstream outage;
# cold/serverless workers still need a shared snapshot store in production.
_career_cache = {}
_refresh_locks = weakref.WeakKeyDictionary()
CAREER_FRESH_SECONDS = 300
CAREER_MAX_AGE_SECONDS = 1800
SOURCE_BUDGET_SECONDS = 18


def _refresh_lock(source, term):
    if source['id'] == 'jobvision':
        return nullcontext()
    locks = _refresh_locks.setdefault(asyncio.get_running_loop(), {})
    return locks.setdefault(source['id'], asyncio.Lock())


def _snapshot(source, *, stale=False, failure=None):
    cached = _career_cache.get(source['id'])
    if not cached:
        return None
    age = max(0, time.monotonic() - cached[0])
    if age >= (CAREER_MAX_AGE_SECONDS if stale else CAREER_FRESH_SECONDS):
        return None
    jobs, report = deepcopy(cached[1])
    report.update(cache_hit=True, cache_age_seconds=round(age),
                  last_fetch_requests=report['requests'], requests=0)
    if stale:
        report.update(state='stale', refresh_failure_kind=failure['failure_kind'],
                      refresh_checked_at=failure['checked_at'],
                      requests=failure['requests'],
                      message='Live refresh failed; showing a previous successful snapshot. See checked_at for its original retrieval time.')
    return jobs, report


# Re-export parsers for compatibility; transport-independent platform code lives
# in adapters.py and employer-specific settings live in source_registry.py.
from .adapters import _text, _title, parse_jobvision, parse_hrcando, fetch_hrcando, parse_career, fetch_html_jobs, parse_recrupen

async def collect_extra(terms, progress=None):
    if not terms: return [],[]
    checked=datetime.now(timezone.utc).isoformat(); limit=asyncio.Semaphore(8)
    async with httpx.AsyncClient(timeout=httpx.Timeout(8,connect=4),follow_redirects=True,headers={'User-Agent':'SpielJobs prototype contact: local user'}) as client:
        async def one(source,term=None):
            async with _refresh_lock(source, term), limit:
                stats={'requests':0}
                if progress and source['id'] != 'jobvision':
                    progress({'group':'career_pages','sources':[dict(source,state='searching',checked_at=None)]})
                if source['id'] != 'jobvision' and source['id'] not in _career_cache:
                    shared = await load_snapshot(client, source)
                    if shared is not None:
                        _career_cache[source['id']] = shared
                cached = _snapshot(source) if source['id'] != 'jobvision' else None
                if cached:
                    with observation('spieljobs.source.'+source['id'], 'retriever', input={'cache':True}) as span:
                        span.update(output={'state':cached[1]['state'], 'count':len(cached[0]),
                            'cache_hit':True, 'cache_age_seconds':cached[1]['cache_age_seconds'],
                            'checked_at':cached[1]['checked_at'], 'requests':0})
                    return cached
                started = time.monotonic()
                with observation('spieljobs.source.'+source['id'],'retriever',input={'query':safe_text(term,150) if term else None}) as span:
                    try:
                        async with asyncio.timeout(SOURCE_BUDGET_SECONDS):
                            async def fetch():
                                if source['id'] == 'jobvision' or source['kind'] in ('jobvision_company', 'recrupen'):
                                    stats['requests'] += 1
                                if source['id']=='jobvision':
                                    response=await client.post('https://candidateapi.jobvision.ir/api/v1/JobPost/List',headers={'Origin':'https://jobvision.ir','Referer':'https://jobvision.ir/','Accept':'application/json'},json={'keyword':term,'sortBy':1,'searchId':None,'pageSize':100,'requestedPage':1})
                                    response.raise_for_status(); envelope=response.json()
                                    if not isinstance(envelope,dict) or envelope.get('isSuccess') is False: raise ValueError('Jobvision rejected query')
                                    jobs=parse_jobvision(envelope.get('data'))
                                elif source['kind']=='jobvision_company':
                                    response=await client.post('https://candidateapi.jobvision.ir/api/v1/JobPost/List',headers={'Origin':'https://jobvision.ir','Referer':'https://jobvision.ir/'},json={'companyId':source['company_id'],'sortBy':1,'pageSize':100,'requestedPage':1})
                                    response.raise_for_status()
                                    envelope=response.json()
                                    data=envelope.get('data') if isinstance(envelope,dict) and envelope.get('isSuccess',True) else None
                                    jobs=parse_jobvision(data)
                                    if any(str((row.get('company') or {}).get('id'))!=str(source['company_id']) for row in data['jobPosts']):
                                        raise ValueError('Jobvision company filter was not honored')
                                    stats['schema_verified']=True
                                elif source['kind']=='recrupen':
                                    response=await client.get(source['api_url'],headers={'x-company-id':str(source['company_id'])})
                                    response.raise_for_status()
                                    jobs=parse_recrupen(source,response.json())
                                    stats['schema_verified']=True
                                elif source['kind']=='hrcando':
                                    jobs=await fetch_hrcando(client,source,stats)
                                else:
                                    if source['kind']=='html':
                                        jobs=await fetch_html_jobs(client,source,stats)
                                    else:
                                        response=await fetch_career_page(client,source,stats)
                                        jobs=parse_career({**source,'url':str(response.url)},response.json())
                                return jobs
                            for attempt in range(2):
                                try:
                                    jobs = await fetch()
                                    break
                                except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as exc:
                                    retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code in (502, 503, 504)
                                    if attempt or not retryable:
                                        raise
                                    stats['retry_count'] = 1
                                    await asyncio.sleep(0.2)
                        jobs, rejected = normalize_jobs(jobs, source, checked)
                        # A validated API response with zero jobs is distinct
                        # from HTML that our parser failed to recognize.
                        recognized = stats.get('schema_verified') or source.get('kind') in ('hrcando','recruitee','workable') or source['id']=='jobvision'
                        state='partial' if jobs else ('success' if recognized and not rejected else 'unverified')
                        report={**source,'state':state,'checked_at':checked,'requests':stats['requests'],'rejected_rows':rejected,'retry_count':stats.get('retry_count',0),'message':'Validated listing response returned no vacancies for this request.' if state=='success' else 'Bounded listing retrieval; source coverage and status require verification.'}
                        if state=='unverified': report['failure_kind']='schema_changed'
                        span.update(level='WARNING' if state=='unverified' else 'DEFAULT',
                            status_message='Unrecognized listing structure' if state=='unverified' else None,
                            output={'state':state,'count':len(jobs),'failure_kind':report.get('failure_kind'),'jobs':summarize_jobs(jobs,30)})
                        if source['id'] != 'jobvision' and state in ('partial', 'success'):
                            _career_cache[source['id']] = (time.monotonic(), deepcopy((jobs, report)))
                            await save_snapshot(client, source, jobs, report)
                        return jobs,report
                    except (httpx.HTTPError,ValueError,TypeError,KeyError,TimeoutError) as exc:
                        failure, status = source_failure(exc)
                        report={**source,'failure_kind':failure,'http_status':status,'state':'unavailable','checked_at':checked,'requests':stats['requests'],'message':f'Source request or parsing failed: {type(exc).__name__}.'}
                        span.update(level='WARNING',status_message=failure+(f' HTTP {status}' if status else ''),output={'state':'unavailable','failure_kind':failure,'http_status':status,'elapsed_ms':round((time.monotonic()-started)*1000),'requests':stats['requests'],'budget_seconds':SOURCE_BUDGET_SECONDS})
                        # Only transient transport/server failures may use dated
                        # evidence. Maintenance, blocks, removed pages and schema
                        # changes must remain explicit failures.
                        if source['id'] != 'jobvision' and (failure in ('timeout', 'connection_failed') or (status is not None and status >= 500)):
                            cached = _snapshot(source, stale=True, failure=report)
                            if cached:
                                span.update(output={'state':'stale', 'failure_kind':failure,
                                    'count':len(cached[0]), 'cache_age_seconds':cached[1]['cache_age_seconds']})
                                return cached
                        return [],report
        if progress: progress({'group':'job_boards','sources':[dict(JOBVISION,state='searching',checked_at=None)]})
        # Public employer snapshots are independent of keyword boards.
        async def boards():
            board_results=await asyncio.gather(*(one(JOBVISION,term) for term in terms[:2]))
            if progress:
                states=[report for _,report in board_results]
                progress({'group':'job_boards','sources':[next((r for r in states if r['state']=='partial'),states[0])]})
            return board_results
        board_task = asyncio.create_task(boards())
        async def career(source):
            result=await one(source)
            if progress: progress({'group':'career_pages','sources':[result[1]]})
            return result
        try:
            career_results = await asyncio.gather(*(career(source) for source in CAREERS))
            results = (await board_task) + career_results
        finally:
            if not board_task.done():
                board_task.cancel()
                await asyncio.gather(board_task, return_exceptions=True)
    jobs=[]; reports=[]
    for batch,report in results:
        jobs.extend(batch)
        existing=next((r for r in reports if r['id']==report['id']),None)
        if existing:
            requests=existing['requests']+report['requests']
            priority={'unavailable':0,'unverified':1,'success':2,'partial':3}
            if priority[report['state']]>priority[existing['state']]:
                existing.clear(); existing.update(report)
            existing['requests']=requests
        else: reports.append(report)
    return jobs,reports

async def enrich_extra(jobs):
    """Read Jobvision's own detail endpoint for the first ranked listings."""
    candidates=[]
    for job in jobs:
        evidence=next((item for item in job.get('sources',[]) if item.get('id')=='jobvision'),None)
        if job.get('source')=='jobvision' or evidence:
            candidates.append((job,evidence))
    candidates=candidates[:10]
    if not candidates: return
    semaphore=asyncio.Semaphore(4)
    async with httpx.AsyncClient(timeout=httpx.Timeout(5,connect=3),headers={'Origin':'https://jobvision.ir','Referer':'https://jobvision.ir/','Accept':'application/json'}) as client:
        async def one(job,evidence):
            match=re.fullmatch(r'/jobs/(\d+)',urlparse((evidence or {}).get('url') or job.get('url','')).path.rstrip('/'))
            if not match:return
            async with semaphore:
                try:
                    response=await client.get('https://candidateapi.jobvision.ir/api/v1/JobPost/Detail',params={'jobPostId':match.group(1)})
                    response.raise_for_status(); body=response.json()
                    data=body.get('data') if isinstance(body,dict) and body.get('isSuccess',True) else None
                    if not isinstance(data,dict):return
                    description=_text(data.get('description'))
                    if description and not job.get('description'):job['description']=description
                    if _title(data.get('workType')) and not job.get('contract'):job['contract']=_title(data['workType'])
                    years=data.get('requiredRelatedExperienceYears')
                    if isinstance(years,(int,float)) and years>=0:job['experience']=f'{years} سال'
                    if isinstance(data.get('isExpired'),bool):
                        state='closed' if data['isExpired'] else 'open'
                        if evidence is not None:evidence['status']=state
                        if job.get('source')=='jobvision':job.update(status=state,status_evidence='Jobvision detail reports expired status.')
                    company=data.get('company') or {}
                    logo=(company.get('logoUrl') or company.get('logo')) if isinstance(company,dict) else None
                    if isinstance(logo,dict):logo=logo.get('url')
                    if isinstance(logo,str) and urlparse(logo).scheme in ('http','https') and not job.get('company_logo_url'):job['company_logo_url']=logo
                    website=company.get('website') if isinstance(company,dict) else None
                    if isinstance(website,str) and urlparse(website).scheme in ('http','https') and not job.get('website'):job['website']=website
                except (httpx.HTTPError,ValueError,TypeError,KeyError):return
        with observation('spieljobs.jobvision.details','tool',input={'candidate_count':len(candidates)}) as span:
            try: await asyncio.wait_for(asyncio.gather(*(one(job,evidence) for job,evidence in candidates)),timeout=8)
            except asyncio.TimeoutError: pass
            span.update(output={'with_description':sum(bool(job.get('description')) for job,_ in candidates)})
