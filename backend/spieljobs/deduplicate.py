"""Conservative cross-source grouping with preserved listing provenance."""
from datetime import date
from urllib.parse import urlsplit, urlunsplit
import re
from .core import normalize

from .urls import canonical_public_url as canonical_url

def name_parts(value):
    return {key for part in (value or '').split('|') if (key:=re.sub(r'[^\w]','',normalize(part)))}

def same_city(a,b):
    def city(value): return {'تهران' if normalize(x)=='tehran' else normalize(x) for x in re.split(r'[,،/]',value or '') if normalize(x)}
    x,y=city(a),city(b)
    return bool(x and y and x&y)

def same_job(a,b):
    if canonical_url(a.get('url')) and canonical_url(a.get('url'))==canonical_url(b.get('url')): return True
    if a.get('source')==b.get('source'): return False
    if not (normalize(a.get('title')) and normalize(a.get('title'))==normalize(b.get('title'))): return False
    if not (name_parts(a.get('company')) & name_parts(b.get('company'))): return False
    if not same_city(a.get('location'),b.get('location')): return False
    try:
        return abs((date.fromisoformat(a['posted_date'])-date.fromisoformat(b['posted_date'])).days)<=1
    except (ValueError,KeyError,TypeError):
        # Exact role, employer and city across different sources are a cautious
        # match when a source does not provide a date; a dated conflict blocks it.
        return True

def deduplicate(jobs):
    output=[]
    for item in jobs:
        job=dict(item)
        provenance={key:job.get(key) for key in ('url','status','posted_date','salary','contract','experience')}
        provenance['id']=job.get('source')
        def compatible(existing):
            incoming=canonical_url(provenance['url'])
            conflict=any(x.get('id')==provenance['id'] and canonical_url(x.get('url'))!=incoming for x in existing['sources'])
            return not conflict and same_job(existing,job)
        match=next((existing for existing in output if compatible(existing)),None)
        if match is None:
            job['sources']=[provenance]; output.append(job); continue
        if not any(canonical_url(x.get('url'))==canonical_url(provenance['url']) for x in match['sources']): match['sources'].append(provenance)
        for field in ('company_logo_url','description','salary','contract','experience','education','skills','website','linkedin','instagram'):
            if not match.get(field) and job.get(field): match[field]=job[field]
    return output
