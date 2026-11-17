"""Run real synthetic searches against the running API; print results for review."""
import json
import sys
import urllib.error
import urllib.request

import os
BASE=os.getenv('SPIELJOBS_API_URL','http://127.0.0.1:8000').rstrip('/')
QUERIES=['کارشناس پشتیبانی', 'کارشناس حسابداری و مالی', 'مدیر محصول هوش مصنوعی']

def request(path, data=None):
    body=json.dumps(data,ensure_ascii=False).encode() if data else None
    req=urllib.request.Request(BASE+path,data=body,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=90) as response: return json.load(response)

try:
    health=request('/health')
    print('Backend:',health.get('runtime_revision','OLD VERSION'), 'Langfuse configured:',health.get('langfuse_configured','unknown'))
    if not str(health.get('runtime_revision','')).startswith('iran-mvp-'):
        sys.exit('The backend is an older process. Restart it before testing.')
    for query in QUERIES:
        result=request('/search',{'query':query})
        print('\nQUERY:',query,'| terms:',result.get('profile',{}).get('search_terms'),'| trace:',result.get('trace_id'))
        for source in result.get('sources',[]): print('SOURCE:',source.get('name'),source.get('state'),source.get('message'))
        jobs=result.get('jobs',[])
        print('RESULTS:',len(jobs))
        for job in jobs[:10]: print('-',job.get('title'),'|',job.get('company'),'|',job.get('url'))
        if not jobs: print('No results to assess; inspect source state and warnings.')
        for warning in result.get('warnings',[]): print('WARNING:',warning)
    print('\nReview the titles and source pages; this script does not automatically certify relevance.')
except (OSError,ValueError,urllib.error.URLError) as exc:
    sys.exit(f'Live check could not finish: {type(exc).__name__}: {exc}')
