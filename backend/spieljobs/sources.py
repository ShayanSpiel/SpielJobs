"""Live source adapters. Each report describes a source actually requested."""
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urlencode
import asyncio
import json
import re
import httpx
from bs4 import BeautifulSoup
from .core import relative_date
from .tracing import observation, safe_text, summarize_jobs
from .extra_sources import configured, collect_extra
from .source_registry import JOBINJA_PROVINCES
from .deduplicate import deduplicate
from .contracts import normalize_jobs, source_failure, normalized_location

# Source-specific configuration lives with its adapter, rather than in the UI.
JOBINJA = {'id':'jobinja', 'name':'Jobinja', 'label':'جابینجا', 'url':'https://jobinja.ir/jobs', 'site_url':'https://jobinja.ir', 'fallback_logo_url':'https://iranian-alternatives.ir/logo/jobinja.png'}

def active_sources():
    """Configured adapters that will be invoked by collect, in execution order."""
    return [dict(source) for source in [JOBINJA,*configured()]]

def safe_http_url(value, base):
    if not value or value.startswith('data:'):
        return None
    url = urljoin(base, value)
    return url if urlparse(url).scheme in ('http', 'https') else None

def page_icon(soup, base):
    """Use the best icon explicitly declared by the source, preferring SVG or large icons."""
    icons = []
    for tag in soup.find_all('link', href=True):
        rel = ' '.join(tag.get('rel', [])).lower()
        if 'icon' not in rel:
            continue
        url = safe_http_url(tag['href'], base)
        if not url:
            continue
        size = tag.get('sizes', '')
        if isinstance(size, list): size = ' '.join(size)
        try: pixels = max((int(s.split('x')[0]) for s in size.lower().split() if 'x' in s), default=0)
        except ValueError: pixels = 0
        preference = 10000 if urlparse(url).path.lower().endswith('.svg') else pixels
        icons.append((preference, url))
    return max(icons, default=(0, None), key=lambda x:x[0])[1]

def company_logo(card, base):
    """Extract the employer logo from the listing, including lazy images and srcset."""
    image = card.select_one('img[class*="logo" i], [class*="logo" i] img, a[href*="/companies/"]:not([href*="/jobs/"]) img, img[alt*="logo" i], img[alt*="لوگو"]')
    if image:
        candidates=[]
        srcset=image.get('data-srcset') or image.get('srcset') or ''
        for candidate in srcset.split(','):
            parts=candidate.strip().split()
            if not parts: continue
            try: size=float(parts[1].rstrip('wx')) if len(parts)>1 else 1
            except ValueError: size=1
            url=safe_http_url(parts[0],base)
            if url: candidates.append((size,url))
        if candidates:
            return max(candidates,key=lambda item:item[0])[1]
        for attr in ('data-original','data-lazy-src','data-src','src'):
            url=safe_http_url(image.get(attr),base)
            if url: return url
    # Some listing templates put the original image on a logo element's inline background.
    for element in card.select('[class*="logo" i][style]'):
        match=re.search(r'url\(\s*["\']?([^"\')]+)', element.get('style',''), re.I)
        if match:
            url=safe_http_url(match.group(1).strip(),base)
            if url:return url
    return None

def detail_metadata(html, base):
    """Use only employer artwork and explicit vacancy signals from the source page."""
    soup = BeautifulSoup(html, 'html.parser')
    company_header = soup.select_one('[class*="companyHeader" i], [class*="company-header" i], [class*="companyInfo" i], [class*="company-info" i]')
    logo = company_logo(company_header, base) if company_header else None
    parts = urlparse(base).path.strip('/').split('/')
    if not logo and len(parts) >= 2 and parts[0] == 'companies':
        company_path = '/companies/' + parts[1]
        for link in soup.find_all('a', href=True):
            if urlparse(urljoin(base, link['href'])).path.rstrip('/') != company_path: continue
            logo = company_logo(link, base)
            if not logo and link.parent and len(link.parent.select('a[href*="/companies/"]')) == 1:
                logo = company_logo(link.parent, base)
            if logo: break
    status, evidence = 'unknown', 'The detail page did not provide a recognizable status.'
    text = soup.get_text(' ', strip=True)
    if re.search(r'آگهی (?:منقضی|بسته) شده|مهلت (?:ارسال رزومه|درخواست) (?:به پایان رسیده|پایان یافته)', text):
        status, evidence = 'closed', 'Source detail page explicitly says the listing is closed.'
    for script in soup.select('script[type="application/ld+json"]'):
        try: data = json.loads(script.string or script.get_text())
        except (ValueError, TypeError): continue
        pending = [data]
        while pending:
            node = pending.pop()
            if isinstance(node, list): pending.extend(node); continue
            if not isinstance(node, dict): continue
            pending.extend(node.values())
            kind = node.get('@type', '')
            if 'JobPosting' not in ([kind] if isinstance(kind, str) else kind if isinstance(kind, list) else []): continue
            employer = node.get('hiringOrganization')
            if isinstance(employer, dict):
                image = employer.get('logo')
                if isinstance(image, dict): image = image.get('url') or image.get('contentUrl')
                if isinstance(image, str): logo = safe_http_url(image, base) or logo
            valid = node.get('validThrough')
            if status != 'closed' and isinstance(valid, str):
                try:
                    expires = datetime.fromisoformat(valid.replace('Z', '+00:00'))
                    if expires.tzinfo is None: expires = expires.replace(tzinfo=timezone.utc)
                    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', valid):
                        status = 'open' if expires.date() >= datetime.now(timezone.utc).date() else 'closed'
                    else:
                        status = 'open' if expires >= datetime.now(timezone.utc) else 'closed'
                    evidence = 'Status derived from source JobPosting validThrough.'
                except ValueError: pass
    if status == 'unknown':
        for action in soup.select('button, a, input[type="submit"]'):
            label = action.get_text(' ', strip=True) or action.get('value', '')
            disabled = action.has_attr('disabled') or action.get('aria-disabled') == 'true'
            if not disabled and re.search(r'^(?:ارسال رزومه|ارسال درخواست|درخواست استخدام)$', label.strip()):
                status, evidence = 'open', 'Source detail page shows an enabled application action.'
                break
    return logo, status, evidence

def profile_logo(html, base):
    soup = BeautifulSoup(html, 'html.parser')
    for script in soup.select('script[type="application/ld+json"]'):
        try: data = json.loads(script.string or script.get_text())
        except (ValueError, TypeError): continue
        pending = [data]
        while pending:
            node = pending.pop()
            if isinstance(node, list): pending.extend(node); continue
            if not isinstance(node, dict): continue
            pending.extend(node.values())
            kinds = node.get('@type', '')
            if 'Organization' not in ([kinds] if isinstance(kinds, str) else kinds if isinstance(kinds, list) else []): continue
            logo = node.get('logo')
            if isinstance(logo, dict): logo = logo.get('url') or logo.get('contentUrl')
            if isinstance(logo, str) and safe_http_url(logo, base): return safe_http_url(logo, base)
    header = soup.select_one('[class*="companyHeader" i], [class*="company-header" i], [class*="companyInfo" i], [class*="company-info" i]')
    return company_logo(header, base) if header else None

def _links(values, base):
    links={}
    for value in values:
        url=safe_http_url(value,base)
        if not url: continue
        host=(urlparse(url).hostname or '').lower()
        if host=='linkedin.com' or host.endswith('.linkedin.com'): links.setdefault('linkedin',url)
        elif host=='instagram.com' or host.endswith('.instagram.com'): links.setdefault('instagram',url)
        elif host!='jobinja.ir' and not host.endswith('.jobinja.ir'): links.setdefault('website',url)
    return links

def job_details(html, base):
    """Read displayed job fields and employer links; absent source data stays absent."""
    soup=BeautifulSoup(html,'html.parser'); details={}; links=[]
    labels={'حقوق':'salary','حقوق و مزایا':'salary','نوع همکاری':'contract','حداقل سابقه کار':'experience',
            'موقعیت مکانی':'location','دسته بندی شغلی':'category','حداقل مدرک تحصیلی':'education',
            'مهارت های مورد نیاز':'skills'}
    for item in soup.select('ul.c-infoBox li.c-infoBox__item'):
        title=item.select_one('.c-infoBox__itemTitle')
        if not title: continue
        field=labels.get(normalize_label(title.get_text(' ',strip=True)))
        if not field: continue
        value=item.get_text(' ',strip=True).removeprefix(title.get_text(' ',strip=True)).strip(' :：')
        if field=='skills':
            values=[tag.get_text(' ',strip=True) for tag in item.select('.tags span') if tag.get_text(' ',strip=True)]
            if values: details[field]=values[:20]
        elif value and 'برای مشاهده حقوق وارد شوید' not in value:
            details[field]=value[:300]
    for script in soup.select('script[type="application/ld+json"]'):
        try: data=json.loads(script.string or script.get_text())
        except (ValueError,TypeError): continue
        pending=[data]
        while pending:
            node=pending.pop()
            if isinstance(node,list): pending.extend(reversed(node)); continue
            if not isinstance(node,dict): continue
            kind=node.get('@type','')
            if 'JobPosting' not in ([kind] if isinstance(kind,str) else kind if isinstance(kind,list) else []):
                graph=node.get('@graph'); pending.extend(reversed(graph) if isinstance(graph,list) else []); continue
            desc=node.get('description')
            if isinstance(desc,str):
                value=BeautifulSoup(desc,'html.parser').get_text('\n',strip=True)
                if value: details['description']=value[:12000]
            org=node.get('hiringOrganization')
            if isinstance(org,dict):
                same=org.get('sameAs')
                if isinstance(same,str): links.append(same)
                elif isinstance(same,list): links.extend(v for v in same if isinstance(v,str))
            salary=node.get('baseSalary')
            if 'salary' not in details and isinstance(salary,dict):
                currency=salary.get('currency'); val=salary.get('value'); unit=None
                if isinstance(val,dict):
                    unit=val.get('unitText'); lower=val.get('minValue'); upper=val.get('maxValue'); exact=val.get('value')
                    val=(f'{lower} – {upper}' if lower is not None and upper is not None else exact if exact is not None else lower if lower is not None else upper)
                if val is not None and isinstance(val,(int,float,str)):
                    details['salary']=' '.join(str(x) for x in (val,currency,unit) if x is not None)
            date=node.get('datePosted')
            if isinstance(date,str) and re.match(r'^\d{4}-\d{2}-\d{2}',date): details['posted_date']=date[:10]
            break
    header=soup.select_one('.c-companyHeader')
    if header: links.extend(a.get('href') for a in header.select('a[href]'))
    details.update(_links(links,base))
    return details

def normalize_label(value):
    return re.sub(r'\s+',' ',value.replace('\u200c',' ').replace('ي','ی').replace('ك','ک')).strip(' :：')

def profile_links(html,base):
    soup=BeautifulSoup(html,'html.parser')
    header=soup.select_one('.c-companyHeader')
    return _links([a.get('href') for a in header.select('a[href]')] if header else [],base)

async def enrich_jobs(jobs):
    """Fetch ranked Jobinja details in a bounded batch; preserve unknowns on failure."""
    candidates = [job for job in jobs if job.get('source', '').lower() == 'jobinja'
                  and urlparse(job.get('url', '')).hostname == 'jobinja.ir'
                  and urlparse(job.get('url', '')).scheme == 'https'][:30]
    if not candidates: return jobs
    semaphore = asyncio.Semaphore(4)
    async with httpx.AsyncClient(timeout=5, follow_redirects=False, headers={'User-Agent':'SpielJobs prototype contact: local user'}) as client:
        async def inspect(index,job):
            async with semaphore:
                try:
                    response = await client.get(job['url'])
                    if response.status_code != 200: return
                    logo, status, evidence = detail_metadata(response.text, str(response.url))
                    details=job_details(response.text,str(response.url))
                    if isinstance(details.get('location'),str):
                        details['location_text']=details['location']
                        details['location']=normalized_location(details['location'])
                    job.update(details)
                    if status != 'unknown': job.update(status=status, status_evidence=evidence)
                    parts = urlparse(job['url']).path.strip('/').split('/')
                    if (index<3 or (not logo and not job.get('company_logo_url'))) and len(parts) >= 3 and parts[0] == 'companies' and parts[2] == 'jobs':
                        profile = await client.get('https://jobinja.ir/companies/' + parts[1])
                        if profile.status_code == 200:
                            logo = logo or profile_logo(profile.text, str(profile.url))
                            for key,value in profile_links(profile.text,str(profile.url)).items(): job.setdefault(key,value)
                    if logo: job['company_logo_url'] = logo
                except (httpx.HTTPError, ValueError): return
        with observation('spieljobs.jobinja.details', 'tool', input={'candidate_count':len(candidates)}) as span:
            try: await asyncio.wait_for(asyncio.gather(*(inspect(i,job) for i,job in enumerate(candidates))), timeout=10)
            except asyncio.TimeoutError: pass
            span.update(output={'logo_count':sum(bool(job.get('company_logo_url')) for job in candidates), 'verified_status_count':sum(job.get('status') != 'unknown' for job in candidates)})
    return jobs

async def _jobinja(query, province=None):
    checked = datetime.now(timezone.utc).isoformat()
    report = {**JOBINJA,'checked_at':checked,'state':'unavailable','icon_url':None,'message':'Source could not be checked.'}
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers={'User-Agent':'SpielJobs prototype contact: local user'}) as client:
            params={'filters[keywords][]':query} if query else {}
            if province: params['filters[locations][0]']=province
            response = await client.get(JOBINJA['url'],params=params)
            report['location_filter']=province
            response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        report['icon_url'] = page_icon(soup, str(response.url))
        jobs = []
        for heading in soup.select('h2'):
            link = heading.find('a', href=True)
            if not link or '/jobs/' not in link['href']:
                continue
            card = heading.find_parent('li') or heading.parent
            raw = card.get_text(' ', strip=True)
            fields = [x.get_text(' ', strip=True) for x in card.select('li')]
            date_node=card.select_one('.c-jobListView__passedDays, time, [class*="passedDays"]')
            posted=relative_date(date_node.get_text(' ',strip=True)) if date_node else None
            jobs.append({'title':link.get_text(' ',strip=True), 'url':urljoin(str(response.url),link['href']), 'company':fields[0] if fields else None,'company_logo_url':company_logo(card, str(response.url)), 'location':fields[1] if len(fields)>1 else None,'posted_date':posted,'posted_text':raw[:300], 'description':None,'source':JOBINJA['id'],'checked_at':checked,'status':'listed','status_evidence':'Observed in the current Jobinja listing; open status is not independently verified.'})
        jobs, rejected = normalize_jobs(jobs, JOBINJA, checked)
        report['rejected_rows'] = rejected
        if not jobs:
            report.update(state='unverified', message='No parsable listings. This may be an empty result or a changed page; the adapter has not been verified.')
        else:
            report.update(state='partial', message=f'{len(jobs)} listings parsed from one page; search, pagination and open status are not verified.')
        return jobs, report
    except (httpx.HTTPError, ValueError) as exc:
        report['failure_kind'], report['http_status'] = source_failure(exc)
        report['message'] = f'Request failed: {report["failure_kind"]}.'
        return [], report

async def jobinja(query, province=None):
    with observation('spieljobs.jobinja.request', 'tool', input={'search_query':safe_text(query,200)}) as span:
        jobs, report=await _jobinja(query,province=province) if province else await _jobinja(query)
        span.update(
            output={'result_count': len(jobs), 'source_state': report['state'],
                    'failure_kind': report.get('failure_kind'),
                    'http_status': report.get('http_status'),
                    'jobs': summarize_jobs(jobs, 30)},
            level='ERROR' if report['state'] == 'unavailable' else 'DEFAULT',
        )
        return jobs, report

async def collect(terms, progress=None, location=None):
    if progress is None:
        try:
            from langgraph.config import get_stream_writer
            progress=get_stream_writer()
        except (KeyError,RuntimeError):
            pass
    selected = [term for term in terms if len(term) >= 2][:4]
    if not selected:
        return [], []
    if progress: progress({'group':'job_boards','sources':[dict(JOBINJA,state='searching',checked_at=None)]})
    async def board():
        province=JOBINJA_PROVINCES.get(location)
        searches = await asyncio.gather(*(jobinja(term,province=province) if province else jobinja(term) for term in selected))
        jobs, seen = [], set()
        for batch, _ in searches:
            for item in batch:
                if item['url'] not in seen:
                    seen.add(item['url']); jobs.append(item)
        states = [report['state'] for _, report in searches]
        state = 'partial' if 'partial' in states else ('unverified' if 'unverified' in states else 'unavailable')
        reports = [report for _, report in searches]
        report = {**JOBINJA, 'checked_at': max(r['checked_at'] for r in reports), 'state': state,
            'icon_url': next((r['icon_url'] for r in reports if r['icon_url']), None),
            'requests': len(selected), 'terms': selected, 'location_filter':province,
            'searches': [{'term': term, 'url': JOBINJA['url']+'?'+urlencode({'filters[keywords][]':term,**({'filters[locations][0]':province} if province else {})})} for term in selected],
            'message': f'{len(selected)} bounded live search request(s), first page only; pagination and status need verification. ' + ' '.join(dict.fromkeys(r['message'] for r in reports))}
        if state=='unavailable':
            report.update(failure_kind=reports[0].get('failure_kind'),http_status=reports[0].get('http_status'))
        if progress:
            progress({'group': 'job_boards', 'sources': [report]})
        return jobs, [report]
    # Independent sources start together; a slow board cannot hold up careers.
    board_result, extras = await asyncio.gather(board(), collect_extra(selected, progress=progress) if progress else collect_extra(selected))
    jobs, reports = board_result
    extra_jobs, extra_reports = extras
    return deduplicate(jobs + extra_jobs), reports + extra_reports
