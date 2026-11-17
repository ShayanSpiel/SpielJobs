import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,'backend')
from spieljobs.extra_sources import JOBVISION, CAREERS, parse_jobvision, parse_career, parse_hrcando, fetch_hrcando, collect_extra, enrich_extra
from spieljobs.deduplicate import deduplicate

class SourceParsingTests(unittest.TestCase):
    def test_jobvision_maps_real_response_fields(self):
        data={'jobPosts':[{'id':42,'title':'Python Developer','company':{'nameFa':'نمونه'},'location':{'city':{'titleFa':'تهران'}},'salary':{'min':30,'max':40},'activationTime':{'date':'2026-11-16T10:00:00'}}]}
        job=parse_jobvision(data)[0]
        self.assertEqual(job['url'],'https://jobvision.ir/jobs/42')
        self.assertEqual(job['salary'],'30 تا 40 (واحد پول اعلام نشده)')
        self.assertEqual(job['source'],'jobvision')
        self.assertEqual(job['status'],'listed')

    def test_company_json_and_markup_are_actual_links(self):
        source={**CAREERS[0],'kind':'recruitee'}
        jobs=parse_career(source,{'offers':[{'title':'Product Manager','careers_url':'https://snapp.recruitee.com/o/product-manager','location':{'city':'Tehran'}}]})
        self.assertEqual(jobs[0]['company'],'Snapp')
        self.assertEqual(jobs[0]['url'],'https://snapp.recruitee.com/o/product-manager')
        generic={**next(s for s in CAREERS if s['id']=='tapsi'),'kind':'html','url':'https://careers.tapsi.ir/'}
        html='<a href="/jobs/123"><h3>Product Manager</h3></a><a href="/jobs/">همه آگهی‌ها</a>'
        self.assertEqual([x['url'] for x in parse_career(generic,html)],['https://careers.tapsi.ir/jobs/123'])

    def test_changed_api_schema_is_not_treated_as_empty_success(self):
        with self.assertRaises(ValueError): parse_jobvision({'other':[]})

    def test_tapsi_job_data_maps_to_actual_job_page(self):
        source=next(s for s in CAREERS if s['id']=='tapsi')
        body={'succeed':True,'data':{'totalJobCount':1,'jobs':[{'id':1913,'title':'Tapsi Box - Head of Operations','submitTime':'2026-11-14T10:47:11.643','workType':'تمام وقت','city':{'cityTitleFa':'تهران'}}]}}
        job=parse_hrcando(source,body)[0]
        self.assertEqual(job['url'],'https://careers.tapsi.ir/jobs/1913')
        self.assertEqual((job['title'],job['location'],job['posted_date']),('Tapsi Box - Head of Operations','تهران','2026-11-14'))
        with self.assertRaises(ValueError): parse_hrcando(source,{'succeed':True,'data':{}})

class DedupTests(unittest.TestCase):
    def test_merges_strong_cross_source_match_without_losing_links(self):
        jobs=[{'title':'Python Developer','company':'نمونه | Example','location':'تهران، تهران','posted_date':'2026-11-16','source':'jobinja','url':'https://jobinja.ir/jobs/1'},
              {'title':'Python Developer','company':'Example','location':'تهران','posted_date':'2026-11-16','source':'jobvision','url':'https://jobvision.ir/jobs/2'}]
        result=deduplicate(jobs)
        self.assertEqual(len(result),1)
        self.assertEqual([s['id'] for s in result[0]['sources']],['jobinja','jobvision'])
        self.assertEqual(result[0]['sources'][1]['url'],'https://jobvision.ir/jobs/2')

    def test_similar_but_unverified_or_old_roles_remain_separate(self):
        base={'title':'Engineer','company':'Example','location':'Tehran','posted_date':'2026-11-16','source':'jobinja','url':'https://jobinja.ir/jobs/1'}
        different={**base,'source':'jobvision','url':'https://jobvision.ir/jobs/2','posted_date':'2026-10-01'}
        unknown={**base,'source':'snapp','url':'https://snapp.ir/jobs/3','posted_date':None,'location':'Shiraz'}
        self.assertEqual(len(deduplicate([base,different,unknown])),3)

    def test_matching_cross_source_role_without_date_is_grouped(self):
        a={'title':'Product Manager','company':'Example','location':'Tehran','source':'jobinja','url':'https://jobinja.ir/jobs/1'}
        b={**a,'source':'jobvision','location':'تهران','url':'https://jobvision.ir/jobs/2'}
        self.assertEqual(len(deduplicate([a,b])[0]['sources']),2)

    def test_distinct_same_provider_offers_remain_separate(self):
        a={'title':'Product Manager','company':'Example','location':'Tehran','source':'jobinja','url':'https://jobinja.ir/jobs/1'}
        b={**a,'source':'jobvision','url':'https://jobvision.ir/jobs/2','salary':'30 میلیون'}
        c={**b,'url':'https://jobvision.ir/jobs/3'}
        groups=deduplicate([a,b,c])
        self.assertEqual(len(groups),2)
        self.assertEqual(groups[0]['sources'][1]['salary'],'30 میلیون')

class SourceRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_tapsi_discovers_its_configuration_and_requests_listings(self):
        import httpx
        source=next(s for s in CAREERS if s['id']=='tapsi')
        observed=[]
        def handler(request):
            observed.append((request.method,request.url.path))
            if request.url.path=='/jobs': return httpx.Response(200,text='<script src="/assets/job-description~jobs-list.js"></script>')
            if request.url.path.endswith('.js'): return httpx.Response(200,text='companyApiKey:"11111111-1111-1111-1111-111111111111"')
            self.assertEqual(request.headers['companyapikey'],'11111111-1111-1111-1111-111111111111')
            return httpx.Response(200,json={'succeed':True,'data':{'jobs':[{'id':1910,'title':'Marketing Project Management Expert','city':{'cityTitleFa':'تهران'}}]}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            jobs=await fetch_hrcando(client,source)
        self.assertEqual(jobs[0]['url'],'https://careers.tapsi.ir/jobs/1910')
        self.assertEqual([method for method,_ in observed],['GET','GET','POST'])
    async def test_actual_adapter_marks_blocked_careers_and_returns_jobvision_result(self):
        import httpx
        original=httpx.AsyncClient
        def handler(request):
            if request.url.host=='candidateapi.jobvision.ir':
                return httpx.Response(200,json={'isSuccess':True,'data':{'jobPosts':[{'id':42,'title':'Python Developer','company':{'nameFa':'نمونه'}}]}},request=request)
            return httpx.Response(403,request=request)
        def client(*args,**kwargs):
            kwargs['transport']=httpx.MockTransport(handler)
            return original(*args,**kwargs)
        progress=[]
        with patch('spieljobs.extra_sources.httpx.AsyncClient',side_effect=client):
            jobs,reports=await collect_extra(['python'],progress=progress.append)
        self.assertEqual([j['source'] for j in jobs],['jobvision'])
        self.assertEqual(next(r['state'] for r in reports if r['id']=='jobvision'),'partial')
        self.assertEqual(next(r['state'] for r in reports if r['id']=='snapp'),'unavailable')
        self.assertEqual(len(reports),len(CAREERS)+1)
        self.assertEqual(progress[0]['sources'][0]['id'],'jobvision')
        self.assertTrue(any(p['group']=='career_pages' for p in progress))
        self.assertTrue(any(s.get('id')=='jobvision' and s.get('state')=='partial' for p in progress for s in p['sources']))

    async def test_jobvision_details_enrich_merged_result_without_overwriting_primary_status(self):
        import httpx
        original=httpx.AsyncClient
        def handler(request):
            return httpx.Response(200,json={'data':{'description':'<p>Python and SQL</p>','isExpired':False,'company':{'website':'https://example.org'}}},request=request)
        def client(*args,**kwargs):
            kwargs['transport']=httpx.MockTransport(handler)
            return original(*args,**kwargs)
        job={'title':'Python Developer','url':'https://jobinja.ir/jobs/1','source':'jobinja','status':'unknown','sources':[{'id':'jobvision','url':'https://jobvision.ir/jobs/42','status':'unknown'}]}
        with patch('spieljobs.extra_sources.httpx.AsyncClient',side_effect=client): await enrich_extra([job])
        self.assertEqual(job['description'],'Python and SQL')
        self.assertEqual(job['website'],'https://example.org')
        self.assertEqual(job['status'],'unknown')
        self.assertEqual(job['sources'][0]['status'],'open')
