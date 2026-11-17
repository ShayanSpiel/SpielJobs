import unittest
from spieljobs.contracts import normalize_jobs, source_failure
from spieljobs.extra_sources import parse_career, CAREERS, parse_hrcando
from spieljobs.core import needs_interpretation, parse_query, rank_and_filter


class ContractTests(unittest.TestCase):
    def test_bad_rows_do_not_poison_source_and_ids_are_stable(self):
        source={'id':'sample'}
        rows=[{'title':'Python Developer','url':'https://example.org/jobs/1','source':'wrong','posted_date':'bad'},
              {'title':'Bad URL','url':'javascript:alert(1)'}, {'url':'https://example.org/2'}]
        jobs,rejected=normalize_jobs(rows,source,'2026-11-17T00:00:00Z')
        self.assertEqual((len(jobs),rejected),(1,2))
        self.assertEqual(jobs[0]['source'],'sample')
        self.assertIsNone(jobs[0]['posted_date'])
        again,_=normalize_jobs(rows,source,'2026-11-18T00:00:00Z')
        self.assertEqual(jobs[0]['id'],again[0]['id'])

    def test_divar_markup_keeps_employer_title_location_department(self):
        # Markup shape inspected on Divar's public /positions page, 17 Nov 2026.
        source=next(s for s in CAREERS if s['id']=='divar')
        html='<a title="Senior Software Engineer" href="/positions/Senior-Software-Engineer-C7E4CB97D3"><div><div><h2>Senior Software Engineer</h2><span>Position Detail</span></div><div><span>Tehran</span><hr role="separator"><span>AI &amp; Software Engineering</span></div></div></a><a href="/positions/Talent-Pool-Future-Opportunities-5C0530D034"><h2>Talent Pool - Future Opportunities</h2></a>'
        jobs=parse_career(source,html)
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]['location'],'Tehran')
        self.assertEqual(jobs[0]['category'],'AI & Software Engineering')
        self.assertEqual(jobs[0]['url'],'https://careers.divar.ir/positions/Senior-Software-Engineer-C7E4CB97D3')

    def test_snappfood_evidence_fields_and_title_count(self):
        source=next(s for s in CAREERS if s['id']=='snappfood')
        data={'data':{'jobs':[{'id':4803,'title':'Marketing Campaign Management Senior Specialist (1)','isRemote':True,'city':{'cityTitleFa':'تهران'},'department':{'departmentTitle':'Marketing'}}]}}
        job=parse_hrcando(source,data)[0]
        self.assertEqual(job['title'],'Marketing Campaign Management Senior Specialist')
        self.assertEqual(job['workplace_type'],'remote')
        self.assertEqual(job['category'],'Marketing')

    def test_short_contextual_request_uses_model_and_preserves_exclusions(self):
        self.assertTrue(needs_interpretation('مدیر محصول ولی نه برنامه نویسی'))
        profile=parse_query('مدیر محصول ولی نه برنامه نویسی')
        jobs=[{'title':'Product Developer'}, {'title':'Product Manager'}]
        self.assertEqual([j['title'] for j in rank_and_filter(jobs,profile)],['Product Manager'])

class ListingIdentityTests(unittest.TestCase):
    def test_tracking_is_removed_without_merging_functional_job_ids(self):
        from spieljobs.urls import canonical_public_url
        from spieljobs.deduplicate import deduplicate
        self.assertEqual(canonical_public_url('https://example.com/job?id=1&utm_source=google&_t=tracking#top'),'https://example.com/job?id=1')
        rows=[{'title':'Accountant','source':'sample','url':'https://example.com/job?id=1'}, {'title':'Accountant','source':'sample','url':'https://example.com/job?id=2'}]
        self.assertEqual(len(deduplicate(rows)),2)

class SharedPlatformTests(unittest.IsolatedAsyncioTestCase):
    async def test_generic_angular_career_shell_discovers_hrcando_feed(self):
        import httpx
        from spieljobs.adapters import fetch_html_jobs
        source={'id':'employer','name':'Employer','url':'https://careers.example.org/','site_url':'https://example.org','kind':'html'}
        paths=[]
        def handler(request):
            paths.append(request.url.path)
            if request.method=='GET' and request.url.path=='/':
                return httpx.Response(200,text='<app-root></app-root><script src="/main.js"></script>')
            if request.url.path=='/main.js':
                return httpx.Response(200,text='companyApiKey:"11111111-1111-1111-1111-111111111111"')
            return httpx.Response(200,json={'succeed':True,'data':{'jobs':[{'id':1,'title':'Accounting Specialist','city':{'cityTitleFa':'تهران'}}]}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            jobs=await fetch_html_jobs(client,source,{'requests':0})
        self.assertEqual(jobs[0]['title'],'Accounting Specialist')
        self.assertEqual(paths.count('/'),1)
        self.assertEqual(jobs[0]['url'],'https://careers.example.org/jobs/1')

class SourceAvailabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_empty_api_is_available_but_unrecognized_html_is_not(self):
        import httpx
        from unittest.mock import patch
        from spieljobs.extra_sources import collect_extra, _career_cache
        _career_cache.clear()
        original=httpx.AsyncClient
        def handler(request):
            if request.url.host=='candidateapi.jobvision.ir':
                return httpx.Response(200,json={'isSuccess':True,'data':{'jobPosts':[]}})
            if request.url.host=='snapp.recruitee.com':
                return httpx.Response(200,json={'offers':[]})
            return httpx.Response(200,text='<html><body>Unrecognized page</body></html>')
        def client(*args,**kwargs):
            return original(*args,**kwargs,transport=httpx.MockTransport(handler))
        with patch('spieljobs.extra_sources.httpx.AsyncClient',side_effect=client):
            jobs,reports=await collect_extra(['accountant'])
        self.assertEqual(jobs,[])
        states={r['id']:r['state'] for r in reports}
        self.assertEqual(states['snapp'],'unverified')
        self.assertEqual(states['jobvision'],'success')
        self.assertEqual(states['torob'],'unverified')
        _career_cache.clear()

    async def test_jobinja_aggregate_preserves_connection_failure(self):
        from unittest.mock import patch, AsyncMock
        from spieljobs.sources import collect
        report={'state':'unavailable','checked_at':'2026-11-17','icon_url':None,'message':'Connection failed','failure_kind':'connection_failed','http_status':None}
        with patch('spieljobs.sources.jobinja',new=AsyncMock(return_value=([],report))), patch('spieljobs.sources.collect_extra',new=AsyncMock(return_value=([],[]))):
            _,reports=await collect(['accountant'])
        self.assertEqual(reports[0]['failure_kind'],'connection_failed')


class PublishedPlatformSchemaTests(unittest.IsolatedAsyncioTestCase):
    async def test_address_based_hrcando_uses_published_protocol(self):
        import json
        from pathlib import Path
        import httpx
        from spieljobs.adapters import fetch_hrcando
        source={'id':'jabama','name':'Jabama','url':'https://careers.jabama.com/','kind':'hrcando'}
        fixture=json.loads((Path(__file__).parent/'fixtures/hrcando-address-list.json').read_text())
        def handler(request):
            if request.url.path=='/': return httpx.Response(200,text='<app-root></app-root><script src="/main.js"></script>')
            if request.url.path=='/main.js': return httpx.Response(200,text='CareerAuthKey:"public-browser-configuration"')
            self.assertEqual(request.url.path,'/api/v1/CareerPage/GetCareerPageJobList')
            self.assertEqual(request.headers['address'],'careers.jabama.com')
            self.assertEqual(request.headers['CareerAuthKey'],'public-browser-configuration')
            return httpx.Response(200,json=fixture)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            jobs=await fetch_hrcando(client,source)
        self.assertEqual(jobs[0]['title'],'سرپرست پشتیبانی مشتریان')
        self.assertEqual(jobs[0]['location'],'تهران')
        self.assertEqual(jobs[0]['posted_date'],'2026-11-15')
        self.assertIn('/job-detail/',jobs[0]['url'])

    async def test_recrupen_preserves_source_date_and_uses_public_job_route(self):
        import json
        from pathlib import Path
        from spieljobs.adapters import parse_recrupen
        source=next(s for s in CAREERS if s['id']=='cafebazaar')
        rows=json.loads((Path(__file__).parent/'fixtures/recrupen-list.json').read_text())
        jobs=parse_recrupen(source,rows)
        self.assertEqual(len(jobs),2)
        self.assertEqual(jobs[0]['posted_date'],'2019-11-03')
        self.assertEqual(jobs[0]['url'],'https://careers.cafebazaar.ir/jobs/ADA37C8C43')
        self.assertEqual(jobs[0]['status'],'listed')


class SourceCardRegressionTests(unittest.TestCase):
    def test_captured_digiexpress_card_keeps_location_out_of_title(self):
        from pathlib import Path
        source=next(s for s in CAREERS if s['id']=='digiexpress')
        job=parse_career(source,(Path(__file__).parent/'fixtures/digiexpress-card.html').read_text())[0]
        self.assertEqual(job['title'],'Senior Last Mile Excellency Specialist')
        self.assertEqual(job['location'],'Tehran')
        self.assertEqual(job['contract'],'Full-time')
        self.assertEqual(job['category'],'Operations')

    def test_captured_torob_card_preserves_subsidiary_and_workplace(self):
        from pathlib import Path
        source=next(s for s in CAREERS if s['id']=='torob')
        job=parse_career(source,(Path(__file__).parent/'fixtures/torob-card.html').read_text())[0]
        self.assertEqual(job['company'],'ترب‌پی')
        self.assertEqual(job['location'],'دورکاری')
        self.assertEqual(job['title'],'کارشناس‌ارشد جذب فروشگاه‌ها')

    def test_role_plus_skill_retrieves_role_then_checks_skill_evidence(self):
        profile=parse_query('حسابدار مسلط به اکسل در تهران')
        self.assertEqual(profile['search_terms'][0],'حسابدار')
        rows=[{'title':'حسابدار','location':'تهران','description':'مسلط به Excel'}, {'title':'حسابدار','location':'تهران','description':'حقوق و دستمزد'}]
        self.assertEqual(len(rank_and_filter(rows,profile)),1)

    def test_skill_only_query_does_not_require_both_skills_in_source_title(self):
        profile=parse_query('مسلط به Python و SQL در مشهد')
        self.assertTrue(profile['skill_query'])
        self.assertIn('python',profile['search_terms'])
        self.assertIn('sql',profile['search_terms'])


class SourceGeographyTests(unittest.IsolatedAsyncioTestCase):
    async def test_jobinja_native_province_filter_is_sent_before_ranking(self):
        import httpx
        from unittest.mock import patch
        from spieljobs.sources import _jobinja
        original=httpx.AsyncClient
        def handler(request):
            self.assertEqual(request.url.params['filters[locations][0]'],'اصفهان')
            self.assertEqual(request.url.params['filters[keywords][]'],'سرپرست فروش')
            return httpx.Response(200,text='<html><body>No fixture vacancies</body></html>')
        def client(*args,**kwargs):return original(*args,**kwargs,transport=httpx.MockTransport(handler))
        with patch('spieljobs.sources.httpx.AsyncClient',side_effect=client):
            _,report=await _jobinja('سرپرست فروش',province='اصفهان')
        self.assertEqual(report['location_filter'],'اصفهان')


class RoleFamilyRegressionTests(unittest.TestCase):
    def test_support_department_does_not_make_a_product_manager_a_support_specialist(self):
        profile=parse_query('کارشناس پشتیبانی در تهران')
        rows=[{'title':'Senior Product Manager | Support','location':'تهران'}, {'title':'Technical Support Specialist','location':'تهران'}]
        self.assertEqual([x['title'] for x in rank_and_filter(rows,profile)],['Technical Support Specialist'])
