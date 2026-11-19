"""Offline integration checks for the real API, graph and MCP tool."""
import os
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,'backend')
import httpx
from spieljobs.server import app
from spieljobs.mcp_server import search_live_jobs

async def stub_collect(terms):
    return ([{'title':'AI Engineer','url':'https://example.com/job/1','company':'Example','location':'Tehran','posted_date':'2026-11-15','description':None,'source':'Test','status':'unknown'}],
            [{'name':'Test','state':'partial','checked_at':None,'message':'Fixture only'}])

class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_api_graph_results_and_no_model_for_keywords(self):
        with patch('spieljobs.agent.collect',side_effect=stub_collect), patch('spieljobs.agent.extract_profile') as model:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                response=await client.post('/search',json={'query':'AI engineer'})
        self.assertEqual(response.status_code,200)
        body=response.json()
        self.assertEqual(body['jobs'][0]['title'],'AI Engineer')
        self.assertEqual(body['sources'][0]['state'],'partial')
        self.assertNotIn('resume',body)
        model.assert_not_called()

    async def test_resume_failure_is_visible_and_private(self):
        with patch('spieljobs.agent.collect',side_effect=stub_collect), patch('spieljobs.agent.extract_profile',return_value=([],None)):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                response=await client.post('/search',json={'query':'AI engineer','resume':'sensitive résumé text'})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['warnings'])
        self.assertNotIn('sensitive résumé text',response.text)

    async def test_mcp_calls_same_graph(self):
        with patch('spieljobs.agent.collect',side_effect=stub_collect):
            result=await search_live_jobs('AI engineer')
        self.assertEqual(result['jobs'][0]['url'],'https://example.com/job/1')

    async def test_api_validates_empty_query(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            response=await client.post('/search',json={'query':''})
        self.assertEqual(response.status_code,422)

class ModelFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_mistral_failure_then_gemini(self):
        from spieljobs.models import extract_profile
        calls=[]
        def handler(request):
            calls.append(request.url.host)
            if request.url.host == 'api.mistral.ai':
                return httpx.Response(503,json={'error':'unavailable'})
            return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':'{"terms":["AI engineer"]}'}]}}]})
        original_client=httpx.AsyncClient
        def mock_client(*args,**kwargs):
            kwargs['transport']=httpx.MockTransport(handler)
            return original_client(*args,**kwargs)
        diagnostics={}
        with patch.dict(os.environ,{'MISTRAL_API_KEY':'test','GEMINI_API_KEY':'test'}), patch('spieljobs.models.httpx.AsyncClient',side_effect=mock_client):
            terms,provider=await extract_profile('Engineer','AI engineering experience',diagnostics)
        self.assertEqual(provider,'gemini')
        self.assertEqual(terms,['AI engineer'])
        self.assertEqual(calls,['api.mistral.ai','generativelanguage.googleapis.com'])
        self.assertEqual(diagnostics['attempts'][0]['http_status'],503)

    async def test_mistral_success_skips_fallback(self):
        from spieljobs.models import extract_profile
        calls=[]
        def handler(request):
            calls.append(request.url.host)
            return httpx.Response(200,json={'choices':[{'message':{'content':'{"terms":["product manager"]}'}}]})
        original=httpx.AsyncClient
        def client(*args,**kwargs):
            kwargs['transport']=httpx.MockTransport(handler)
            return original(*args,**kwargs)
        with patch.dict(os.environ,{'MISTRAL_API_KEY':'test','GEMINI_API_KEY':'test'}), patch('spieljobs.models.httpx.AsyncClient',side_effect=client):
            terms,provider=await extract_profile('Product manager','')
        self.assertEqual((terms,provider),(['product manager'],'mistral'))
        self.assertEqual(calls,['api.mistral.ai'])

class StreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_reports_graph_phases_and_result(self):
        with patch('spieljobs.agent.collect',side_effect=stub_collect):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                response=await client.post('/search/stream',json={'query':'AI engineer'})
        self.assertEqual(response.status_code,200)
        self.assertIn('text/event-stream',response.headers['content-type'])
        self.assertIn('"phase": "prepare"',response.text)
        self.assertIn('"phase": "search"',response.text)
        self.assertIn('"phase": "rank"',response.text)
        self.assertIn('event: result',response.text)
        self.assertNotIn('"resume"',response.text)

class ResumeSearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_resume_terms_are_sent_to_source_without_model(self):
        from spieljobs.agent import search_jobs
        with patch('spieljobs.agent.collect',side_effect=stub_collect) as collect, patch('spieljobs.agent.extract_profile',return_value=([],None)):
            result=await search_jobs('فرصت مناسب رزومه من','Python developer with data analyst experience')
        self.assertIn('python',collect.call_args.args[0])
        self.assertTrue(result['warnings'])

class SourceContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_search_returns_enriched_source_details(self):
        import json
        listing='''<html><body><ul><li><h2><a href="/companies/acme/jobs/a">Python Developer</a></h2><ul><li>Acme</li><li>تهران</li></ul></li></ul></body></html>'''
        detail='''<script type="application/ld+json">{"@type":"JobPosting","description":"<p>Build Python services</p>","hiringOrganization":{"sameAs":"https://acme.example"}}</script><ul class="c-infoBox"><li class="c-infoBox__item"><span class="c-infoBox__itemTitle">حقوق</span> توافقی</li></ul>'''
        original=httpx.AsyncClient; requests=[]
        def handler(request):
            requests.append(request)
            return httpx.Response(200,text=listing if request.url.path=='/jobs' else detail,request=request)
        def source_client(*args,**kwargs):
            kwargs['transport']=httpx.MockTransport(handler)
            return original(*args,**kwargs)
        async with original(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            with patch('spieljobs.sources.httpx.AsyncClient',side_effect=source_client), patch('spieljobs.sources.collect_extra',return_value=([],[])):
                response=await client.post('/search/stream',json={'query':'Python developer'})
        result_frame=next(frame for frame in response.text.split('\n\n') if frame.startswith('event: result'))
        result=json.loads(next(line[6:] for line in result_frame.splitlines() if line.startswith('data: ')))
        job=result['jobs'][0]
        self.assertEqual(job['description'],'Build Python services')
        self.assertEqual(job['salary'],'توافقی')
        self.assertEqual(job['website'],'https://acme.example')
        self.assertEqual(requests[0].url.params.get_list('filters[keywords][]'),['python'])

    async def test_detail_enrichment_uses_company_profile_and_real_status(self):
        from spieljobs.sources import enrich_jobs
        detail='<button>ارسال رزومه</button>'
        profile='<script type="application/ld+json">{"@type":"Organization","logo":"https://cdn.example.org/employer.png"}</script>'
        original=httpx.AsyncClient
        def handler(request):
            return httpx.Response(200, text=detail if '/jobs/' in request.url.path else profile, request=request)
        def client(*args,**kwargs):
            kwargs['transport']=httpx.MockTransport(handler)
            return original(*args,**kwargs)
        job={'source':'jobinja','url':'https://jobinja.ir/companies/acme/jobs/1','status':'unknown','company_logo_url':None}
        with patch('spieljobs.sources.httpx.AsyncClient',side_effect=client):
            await enrich_jobs([job])
        self.assertEqual(job['status'],'open')
        self.assertEqual(job['company_logo_url'],'https://cdn.example.org/employer.png')

    async def test_only_attempted_source_and_provenance_are_reported(self):
        from spieljobs.sources import collect
        html='''<html><head><link rel="icon" sizes="16x16" href="/tiny.png"><link rel="icon" sizes="192x192" href="/large.png"></head><body><ul><li><img class="company-logo" src="/org.png"><h2><a href="/companies/example/jobs/abc/test">Python engineer</a></h2><ul><li>Example Co</li><li>Tehran</li></ul></li></ul></body></html>'''
        seen=[]
        def handler(request):
            seen.append(str(request.url)); return httpx.Response(200,text=html,request=request)
        original=httpx.AsyncClient
        def client(*args,**kwargs):
            kwargs['transport']=httpx.MockTransport(handler)
            return original(*args,**kwargs)
        with patch('spieljobs.sources.httpx.AsyncClient',side_effect=client), patch('spieljobs.sources.collect_extra',return_value=([],[])):
            jobs,reports=await collect(['python','engineer'])
        self.assertEqual(len(seen),2)
        self.assertEqual([r['id'] for r in reports],['jobinja'])
        self.assertEqual(reports[0]['requests'],2)
        self.assertEqual(reports[0]['icon_url'],'https://jobinja.ir/large.png')
        self.assertEqual(jobs[0]['company_logo_url'],'https://jobinja.ir/org.png')
        self.assertEqual(jobs[0]['source'],'jobinja')
    async def test_no_terms_performs_no_requests(self):
        from spieljobs.sources import collect
        with patch('spieljobs.sources.jobinja') as source:
            self.assertEqual(await collect([]),([],[]))
        source.assert_not_called()
    async def test_stream_sources_come_from_adapter_registry(self):
        async def collect_with_progress(terms):
            from langgraph.config import get_stream_writer
            get_stream_writer()({'group':'job_boards','sources':[{'id':'other','name':'Other','state':'searching','site_url':'https://example.test'}]})
            return await stub_collect(terms)
        with patch('spieljobs.agent.collect',side_effect=collect_with_progress):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                response=await client.post('/search/stream',json={'query':'AI engineer'})
        self.assertIn('"id": "other"',response.text)
        self.assertIn('event: source_progress',response.text)
        self.assertNotIn('"Azki"',response.text)

class ImageProvenanceTests(unittest.TestCase):
    def test_job_details_extracts_actual_salary_description_and_company_links(self):
        from spieljobs.sources import job_details
        html='''<script type="application/ld+json">{"@type":"JobPosting","description":"<p>Build useful products</p>","datePosted":"2026-11-15","hiringOrganization":{"sameAs":["https://example.org","https://www.linkedin.com/company/example"]}}</script><ul class="c-infoBox"><li class="c-infoBox__item"><span class="c-infoBox__itemTitle">حقوق</span> ۳۰ تا ۴۰ میلیون تومان</li><li class="c-infoBox__item"><span class="c-infoBox__itemTitle">نوع همکاری</span> تمام وقت</li><li class="c-infoBox__item"><span class="c-infoBox__itemTitle">مهارت‌های مورد نیاز</span><div class="tags"><span>Python</span><span>SQL</span></div></li></ul>'''
        info=job_details(html,'https://jobinja.ir/companies/example/jobs/123')
        self.assertEqual(info['salary'],'۳۰ تا ۴۰ میلیون تومان')
        self.assertEqual(info['description'],'Build useful products')
        self.assertEqual(info['contract'],'تمام وقت')
        self.assertEqual(info['skills'],['Python','SQL'])
        self.assertEqual(info['website'],'https://example.org')
        self.assertEqual(info['linkedin'],'https://www.linkedin.com/company/example')
        self.assertNotIn('instagram',info)

    def test_no_fabricated_salary_or_company_links(self):
        from spieljobs.sources import job_details
        info=job_details('<p>Nothing published</p>','https://jobinja.ir/jobs/1')
        self.assertNotIn('salary',info)
        self.assertNotIn('website',info)

    def test_detail_reads_hiring_organization_logo_and_explicit_dates(self):
        from spieljobs.sources import detail_metadata
        html='''<script type="application/ld+json">{"@type":"JobPosting","hiringOrganization":{"logo":"https://img.example.org/company.png"},"validThrough":"2099-12-31"}</script>'''
        logo,status,evidence=detail_metadata(html,'https://jobinja.ir/jobs/1')
        self.assertEqual(logo,'https://img.example.org/company.png')
        self.assertEqual(status,'open')
        self.assertIn('validThrough',evidence)

    def test_detail_recognizes_closed_and_does_not_assume_active(self):
        from spieljobs.sources import detail_metadata
        self.assertEqual(detail_metadata('<p>مهلت ارسال رزومه به پایان رسیده</p>','https://jobinja.ir')[1],'closed')
        self.assertEqual(detail_metadata('<h1>Example job</h1>','https://jobinja.ir')[1],'unknown')
        self.assertEqual(detail_metadata('<button disabled>ارسال رزومه</button>','https://jobinja.ir')[1],'unknown')
        self.assertEqual(detail_metadata('<button>ارسال رزومه</button>','https://jobinja.ir')[1],'open')

    def test_largest_company_srcset_is_selected(self):
        from bs4 import BeautifulSoup
        from spieljobs.sources import company_logo
        card=BeautifulSoup('<a href="/companies/acme"><img src="/small.png" srcset="/small.png 32w, /large.png 256w"></a>','html.parser')
        self.assertEqual(company_logo(card,'https://jobinja.ir/jobs'),'https://jobinja.ir/large.png')
    def test_background_logo_and_absent_logo(self):
        from bs4 import BeautifulSoup
        from spieljobs.sources import company_logo
        card=BeautifulSoup('<div class="company-logo" style="background-image:url(https://images.test/logo.png)"></div>','html.parser')
        self.assertEqual(company_logo(card,'https://jobinja.ir/jobs'),'https://images.test/logo.png')
        self.assertIsNone(company_logo(BeautifulSoup('<p>No image</p>','html.parser'),'https://jobinja.ir/jobs'))

class ProviderDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_absent_credentials_report_unconfigured_without_network(self):
        from spieljobs.models import extract_profile
        diagnostics={}
        with patch.dict(os.environ,{},clear=True), patch('spieljobs.models.httpx.AsyncClient') as client:
            terms,provider=await extract_profile('job','some text', diagnostics)
        self.assertEqual((terms,provider),([],None))
        self.assertEqual(diagnostics['reason'],'not_configured')
        client.assert_not_called()
    async def test_provider_failure_is_not_misreported_as_no_skills(self):
        from spieljobs.agent import prepare
        async def unavailable(query,resume,diagnostics):
            diagnostics['reason']='provider_unavailable'
            return [],None
        with patch('spieljobs.agent.extract_profile',side_effect=unavailable):
            result=await prepare({'query':'کار','resume':'experience in an unfamiliar specialty'})
        self.assertIn('اسم شغلی که دنبالش هستی رو توی کادر جست‌وجو بنویس',result['warnings'][0])
        self.assertNotIn('مهارت قابل تشخیصی',result['warnings'][0])

class ResumeRoleFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_query_overrides_resume_role_gate(self):
        from spieljobs.agent import prepare
        with patch('spieljobs.agent.extract_profile',return_value=([],None)):
            implicit=await prepare({'query':'فرصت مناسب رزومه','resume':'Senior product manager Python SQL 5 years'})
            explicit=await prepare({'query':'Python developer مناسب رزومه','resume':'Senior product manager Python SQL 5 years'})
        self.assertTrue(implicit['profile'].get('fallback_resume_role'))
        self.assertFalse(explicit['profile'].get('fallback_resume_role'))
