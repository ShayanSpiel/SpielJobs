"""Platform parsers and bounded readers; employer configuration is separate."""
import json
import re
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from .source_registry import JOBVISION
from .discovery import fetch_career_page

def _title(value):
    if isinstance(value,dict): return value.get('titleFa') or value.get('title') or value.get('titleEn')
    return value if isinstance(value,str) else None

def _date(value):
    if isinstance(value,dict): value=value.get('date')
    return value[:10] if isinstance(value,str) and re.match(r'^\d{4}-\d{2}-\d{2}',value) else None

def _text(value):
    return BeautifulSoup(value,'html.parser').get_text('\n',strip=True)[:12000] if isinstance(value,str) else None

def _job(source,title,url,company,location=None,**fields):
    if not isinstance(title,str) or not title.strip() or not isinstance(url,str): return None
    parsed=urlparse(url)
    if parsed.scheme not in ('http','https') or not parsed.netloc: return None
    return {'title':title.strip(),'url':url,'company':company,'location':location,'source':source['id'],
            'posted_date':fields.pop('posted_date',None),'description':fields.pop('description',None),
            'status':'listed','status_evidence':'Observed in the current public source listing; application availability is not independently verified.',**fields}

def parse_jobvision(data):
    posts=data.get('jobPosts') if isinstance(data,dict) else None
    if not isinstance(posts,list): raise ValueError('Missing Jobvision jobPosts')
    jobs=[]
    for item in posts:
        if not isinstance(item,dict) or not str(item.get('id','')).isdigit(): continue
        company=item.get('company') if isinstance(item.get('company'),dict) else {}
        location=item.get('location') if isinstance(item.get('location'),dict) else {}
        pay=item.get('salary') or {}
        salary=None; compensation=None
        if isinstance(pay,dict):
            explicit = pay.get('title') or pay.get('text')
            if isinstance(explicit, str) and explicit.strip():
                salary = explicit.strip()
            if isinstance(pay.get('min'), (int,float)):
                lower=pay['min']; upper=pay.get('max')
                unit = pay.get('unit') if isinstance(pay.get('unit'),str) else None
                currency = pay.get('currency') if isinstance(pay.get('currency'),str) else None
                compensation={'minimum':lower,'maximum':upper if isinstance(upper,(int,float)) else None,'currency':currency,'unit':unit,'raw_text':salary}
                if not salary:
                    amount=f'{lower} تا {upper}' if isinstance(upper,(int,float)) and upper!=lower else str(lower)
                    salary=' '.join(part for part in (amount, unit, currency) if part) if unit or currency else amount+' (واحد پول اعلام نشده)'
        logo=company.get('logoUrl') or company.get('logo')
        if isinstance(logo,dict): logo=logo.get('url')
        if not isinstance(logo,str) or urlparse(logo).scheme not in ('http','https'): logo=None
        job=_job(JOBVISION,item.get('title'),f"https://jobvision.ir/jobs/{item['id']}",company.get('nameFa') or company.get('nameEn'),_title(location.get('city')) or _title(location.get('province')),
                 company_logo_url=logo, posted_date=_date(item.get('activationTime')), salary=salary,compensation=compensation,contract=_title(item.get('workType')))
        if job: jobs.append(job)
    return jobs

def parse_hrcando(source, data):
    """Parse the public listing response used by Tapsi's own jobs page."""
    if not isinstance(data,dict) or data.get('succeed') is False:
        raise ValueError('Career API rejected request')
    content=data.get('data')
    rows=content.get('jobs') if isinstance(content,dict) else None
    if not isinstance(rows,list): raise ValueError('Missing career API jobs')
    jobs=[]
    for row in rows:
        if not isinstance(row,dict) or not str(row.get('id','')).isdigit(): continue
        city=row.get('city') if isinstance(row.get('city'),dict) else {}
        job_path=source.get('job_path','/jobs/')
        title = row.get('title')
        if isinstance(title,str) and source.get('strip_opening_count'):
            title=re.sub(r'\(\s*[\d,]+\s*\)', '', title).strip()
        department=row.get('department') if isinstance(row.get('department'),dict) else {}
        identity=(row.get('jobGuid') or row['id']) if source.get('guid_routes') else row['id']
        redirect=row.get('redirectUrl')
        target=redirect if isinstance(redirect,str) and urlparse(redirect).scheme in ('https','http') else urljoin(source['url'],job_path+str(identity))
        job=_job(source,title,target,source['name'],
                 city.get('cityTitleFa') or city.get('cityTitleEn'),posted_date=_date(row.get('submitTime')),
                 contract=row.get('workType') or row.get('workTypeEn'), category=department.get('departmentTitle'), workplace_type='remote' if row.get('isRemote') is True else None)
        if job: jobs.append(job)
    return jobs[:100]

async def fetch_hrcando(client, source, stats=None, page=None):
    """Discover the published tenant identifier from first-party JS, then query its API."""
    stats=stats if stats is not None else {}
    def request_started(): stats['requests']=stats.get('requests',0)+1
    if page is None:
        request_started()
        page=await client.get(source['url']); page.raise_for_status()
    soup=BeautifulSoup(page.text,'html.parser'); host=urlparse(str(page.url)).hostname
    scripts=[]
    base=soup.select_one('base[href]')
    script_base=urljoin(str(page.url),base['href']) if base else str(page.url)
    for tag in soup.select('script[src]'):
        url=urljoin(script_base,tag['src'])
        if urlparse(url).hostname==host and url not in scripts: scripts.append(url)
    # The page publishes this configuration in the shared jobs bundle.
    scripts.sort(key=lambda url: ('job-description~jobs-list' not in url and '/main.' not in url, len(url)))
    # Some employers publish the tenant identifier inline; others bundle it.
    pattern=r'companyApiKey(?:\s*:\s*|["\']\s*,\s*)["\']([a-fA-F0-9-]{36})["\']'
    found=re.search(pattern,page.text,re.I)
    key=found.group(1) if found else None
    address_key_pattern=r'CareerAuthKey:[\"\']([^\"\']+)[\"\']'
    address_key=None
    for url in scripts[:8] if not key else []:
        request_started()
        response=await client.get(url)
        if response.status_code in (404,410): continue
        response.raise_for_status()
        match=re.search(pattern,response.text,re.I)
        if match:
            key=match.group(1); break
        address_match=re.search(address_key_pattern,response.text)
        if address_match:
            address_key=address_match.group(1); break
    if not key and not address_key: raise ValueError('Career API configuration missing')
    origin=urlparse(str(page.url)); origin=f'{origin.scheme}://{origin.netloc}'
    jobs=[]
    api_path='CareerPage/GetCareerPageJobList' if address_key else 'CareerPageCompany/GetCompanyCareerPageJobList'
    address=str(page.url) if urlparse(str(page.url)).hostname=='career.hrcando.ir' else urlparse(str(page.url)).netloc
    headers={'address':address,'CareerAuthKey':address_key} if address_key else {'companyApiKey':key}
    path=urlparse(str(page.url)).path.rstrip('/')+'/job-detail/' if urlparse(str(page.url)).hostname=='career.hrcando.ir' else '/job-detail/'
    effective={**source,'job_path':path,'guid_routes':True} if address_key else source
    for number in range(1,4):
        request_started()
        payload={'PageNumber':number,'Take':100}
        if source.get('filters'): payload.update(CityId='',DepartmentId='',Title='')
        response=await client.post('https://careerapi.hrcando.ir/api/v1/'+api_path,
            headers={**headers,'Origin':origin,'Referer':str(page.url)},json=payload)
        response.raise_for_status(); data=response.json()
        batch=parse_hrcando(effective,data); jobs.extend(batch)
        stats['schema_verified'] = True
        content=data.get('data') or {}; pages=content.get('totalPages')
        if not batch or (isinstance(pages,int) and number>=pages) or (not isinstance(pages,int) and len(batch)<100): break
    return jobs

def parse_career(source,body):
    kind=source['kind']; jobs=[]
    if kind in ('recruitee','workable'):
        rows=body.get('offers' if kind=='recruitee' else 'jobs') if isinstance(body,dict) else None
        if not isinstance(rows,list): raise ValueError('Unexpected jobs response')
        for row in rows:
            if not isinstance(row,dict): continue
            loc=row.get('location') or {}; city=loc.get('city') if isinstance(loc,dict) else loc if isinstance(loc,str) else None
            url=row.get('careers_url') or row.get('url') or row.get('shortlink')
            job=_job(source,row.get('title'),url,source['name'],city,posted_date=_date(row.get('published_at') or row.get('created_at')),description=_text(row.get('description')))
            if job: jobs.append(job)
        return jobs[:80]
    soup=BeautifulSoup(body,'html.parser'); origin=urlparse(source['url']).hostname
    for script in soup.select('script[type="application/ld+json"]'):
        try: pending=[json.loads(script.string or script.get_text())]
        except (ValueError,TypeError): continue
        while pending:
            node=pending.pop()
            if isinstance(node,list): pending.extend(node); continue
            if not isinstance(node,dict): continue
            pending.extend(node.values())
            kind=node.get('@type'); kinds=[kind] if isinstance(kind,str) else kind if isinstance(kind,list) else []
            if 'JobPosting' not in kinds: continue
            raw=node.get('url') or node.get('@id'); url=urljoin(source['url'],raw) if isinstance(raw,str) else None
            if not url or urlparse(url).hostname!=origin: continue
            location_data=node.get('jobLocation') or {}
            if isinstance(location_data,list): location_data=location_data[0] if location_data else {}
            address=location_data.get('address',{}) if isinstance(location_data,dict) else {}
            city=address.get('addressLocality') if isinstance(address,dict) else address if isinstance(address,str) else None
            job=_job(source,node.get('title'),url,source['name'],city,posted_date=_date(node.get('datePosted')),description=_text(node.get('description')))
            if job: jobs.append(job)
    if not jobs:
        for anchor in soup.select('a[href]'):
            url=urljoin(source['url'],anchor['href']); path=urlparse(url).path.rstrip('/')
            if urlparse(url).hostname!=origin or not re.search(r'/(?:jobs?|job-detail|careers?|positions?|opportunities)/[^/]+',path,re.I): continue
            heading=anchor.select_one(source.get('title_selector') or 'h1,h2,h3,h4')
            title=(heading or anchor).get_text(' ',strip=True)
            if len(title)<5 or len(title)>160: continue
            if any(part in path.lower() for part in source.get('exclude_paths', [])): continue
            location = None; category = None
            if source.get('location_before_separator'):
                separator = anchor.find('hr')
                if separator:
                    before = separator.find_previous_sibling('span'); after = separator.find_next_sibling('span')
                    location = before.get_text(' ', strip=True) if before else None
                    category = after.get_text(' ', strip=True) if after else None
            fields={}
            for field,selector in source.get('card_fields',{}).items():
                element=anchor.select_one(selector)
                if element: fields[field]=element.get_text(' ',strip=True)
            company=fields.pop('company',None) or source['name']
            location=fields.pop('location',None) or location
            fields.setdefault('category',category)
            job=_job(source,title,url,company,location,**fields)
            if job: jobs.append(job)
    return jobs[:80]


async def fetch_html_jobs(client, source, stats):
    response = await fetch_career_page(client, source, stats)
    effective = {**source, 'url': str(response.url)}
    challenge = source.get('access_challenge_marker')
    if challenge and challenge in response.text:
        from .contracts import SourceAccessRestricted
        raise SourceAccessRestricted('Employer requires browser verification')
    if source.get('unavailable_marker') and source['unavailable_marker'] in BeautifulSoup(response.text,'html.parser').get_text(' ',strip=True):
        from .contracts import SourceMaintenance
        raise SourceMaintenance('Employer reports careers maintenance')
    jobs = parse_career(effective, response.text)
    if jobs:
        return jobs
    # Homepages often link to a separate listings route. Follow at most two
    # visible first-party links instead of declaring the whole source empty.
    soup = BeautifulSoup(response.text, 'html.parser')
    # Several employers use the same Angular/HRCando shell. A generic HTML
    # selector cannot see its API-fed vacancies. Reuse the published platform
    # configuration instead of pretending that an empty shell is an empty board.
    html=response.text.lower()
    if '<app-root' in html or 'hrcando' in html or 'companyapikey' in html:
        try:
            return await fetch_hrcando(client,effective,stats,page=response)
        except ValueError:
            pass
    host = urlparse(str(response.url)).hostname
    candidates=[]
    for anchor in soup.select('a[href]'):
        url=urljoin(str(response.url),anchor['href']); parsed=urlparse(url)
        if parsed.scheme not in ('http','https') or parsed.hostname != host or url.rstrip('/') == str(response.url).rstrip('/'):
            continue
        path=parsed.path.lower().rstrip('/')
        if re.search(r'/(?:jobs|positions|opportunities|open-positions|careers)(?:/list)?$', path) and url not in candidates:
            candidates.append(url)
    for url in candidates[:2]:
        stats['requests'] += 1
        page=await client.get(url);page.raise_for_status()
        jobs=parse_career({**effective,'url':str(page.url)},page.text)
        if jobs:return jobs
    return []


def parse_recrupen(source, body):
    """Public Cafe Bazaar listing schema, inspected on 17 November 2026."""
    if not isinstance(body,list): raise ValueError('Missing Recrupen job list')
    jobs=[]
    for row in body:
        if not isinstance(row,dict) or row.get('state')!='Published': continue
        code=row.get('shortcode')
        if not isinstance(code,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',code): continue
        location=row.get('location') if isinstance(row.get('location'),dict) else {}
        job=_job(source,row.get('title'),urljoin(source['url'],'/jobs/'+code),source['name'],location.get('city'),
                 category=row.get('department'),posted_date=_date(row.get('created_at')),
                 workplace_type='remote' if location.get('telecommuting') is True else None)
        if job: jobs.append(job)
    return jobs[:100]
