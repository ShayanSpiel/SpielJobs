"""Regression examples for the actual user problem; all source data is synthetic."""
import sys
import unittest
from unittest.mock import AsyncMock, patch
import httpx
sys.path.insert(0, 'backend')
from spieljobs.core import parse_query, rank_and_filter
from spieljobs.server import app

class SearchQualityTests(unittest.TestCase):
    def test_persian_suffixes_and_filler_are_not_search_terms(self):
        p = parse_query('فرصت‌های شغلی پشتیبانی بر اساس رزومه من')
        self.assertEqual(p['search_terms'], ['پشتیبانی','support','customer service'])
        self.assertNotIn('های', p['terms'])
        self.assertNotIn('بر', p['terms'])

    def test_support_does_not_turn_finance_jobs_into_matches(self):
        p = parse_query('کارشناس پشتیبانی')
        jobs = [
            {'id':'support','title':'کارشناس پشتیبانی مشتریان'},
            {'id':'finance','title':'کارشناس حسابداری و مالی','description':'پشتیبانی از امور مالی'},
            {'id':'company','title':'حسابدار','company':'شرکت پشتیبانی'},
        ]
        self.assertEqual([x['id'] for x in rank_and_filter(jobs,p)], ['support'])

    def test_multiple_role_concepts_are_required(self):
        p = parse_query('مدیر محصول هوش مصنوعی در تهران')
        jobs = [
            {'id':'good','title':'مدیر محصول هوش مصنوعی','location':'تهران'},
            {'id':'english','title':'AI Product Manager','location':'Tehran'},
            {'id':'engineer','title':'برنامه نویس هوش مصنوعی','location':'تهران'},
            {'id':'product','title':'مدیر محصول','location':'تهران'},
        ]
        self.assertEqual({x['id'] for x in rank_and_filter(jobs,p)}, {'good','english'})
        self.assertNotIn('بر', p['search_terms'])
        self.assertIn('هوش مصنوعی', p['search_terms'][0])

    def test_empty_prompt_does_not_invent_keywords(self):
        self.assertEqual(parse_query('بر اساس رزومه من')['search_terms'], [])

    def test_typo_correction_applies_to_search_and_ranking(self):
        p=parse_query('AI product managaer')
        self.assertEqual(p['corrections'],[{'original':'managaer','corrected':'manager'}])
        self.assertIn('manager',p['terms'])
        self.assertNotIn('managaer',' '.join(p['search_terms']))
        self.assertEqual(len(rank_and_filter([{'title':'AI Product Manager'}],p)),1)

    def test_unknown_names_and_skills_are_not_guessed(self):
        p=parse_query('Kubernetes zyxwvu')
        self.assertEqual(p['corrections'],[])
        self.assertIn('kubernetes',p['terms'])

    def test_data_and_growth_are_not_dropped_by_general_stoplist(self):
        p=parse_query('مدیر رشد و تحلیل داده')
        self.assertIn('رشد',p['terms'])
        self.assertIn('داده',p['terms'])

    def test_mixed_script_and_zwnj_normalize_consistently(self):
        p=parse_query('فرصت‌های پشتيباني')
        self.assertEqual(p['search_terms'],['پشتیبانی','support','customer service'])

    def test_translated_search_keeps_all_requested_concepts(self):
        p=parse_query('مدیر محصول هوش مصنوعی')
        self.assertIn('product', ' '.join(p['search_terms']))
        self.assertNotIn('ai', p['search_terms'])
        self.assertNotIn('هوش', p['terms'])

    def test_accounting_avoids_unrelated_support_title(self):
        p=parse_query('حسابداری مالی')
        jobs=[{'id':'relevant','title':'کارشناس حسابداری مالی'},
              {'id':'support','title':'کارشناس پشتیبانی مشتریان','description':'خدمات حسابداری'},
              {'id':'sales','title':'مدیر فروش','company':'حسابداری مالی'}]
        self.assertEqual([x['id'] for x in rank_and_filter(jobs,p)],['relevant'])

    def test_user_observed_live_ai_product_titles_survive_ranking(self):
        p=parse_query('مدیر محصول هوش مصنوعی')
        jobs=[{'id':'myket','title':'مدیر محصول هوش مصنوعی (AI Product Manager)'},
              {'id':'ayan','title':'مدیر محصول (هوش مصنوعی)'},
              {'id':'baloot','title':'AI-Native Product Manager (AI-First Product Development)'},
              {'id':'unrelated','title':'برنامه نویس هوش مصنوعی'}]
        self.assertEqual({x['id'] for x in rank_and_filter(jobs,p)}, {'myket','ayan','baloot'})

class SearchRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_resume_model_expansion_preserves_explicit_skill_and_role(self):
        from spieljobs.agent import prepare
        with patch('spieljobs.agent.extract_profile',AsyncMock(return_value=(['accountant','bookkeeping'],'mistral'))):
            result=await prepare({'query':'حسابدار مسلط به اکسل در تهران','resume':'Synthetic accounting resume'})
        profile=result['profile']
        self.assertTrue(profile['strict_concepts'])
        jobs=[{'title':'حسابدار','location':'تهران','description':'Excel'},
              {'title':'حسابدار','location':'تهران','description':'bookkeeping'}]
        self.assertEqual(len(rank_and_filter(jobs,profile)),1)

    async def test_empty_after_filter_is_explained(self):
        jobs=[{'title':'حسابدار مالی','description':'پشتیبانی از امور مالی','source':'sample'}]
        source={'id':'sample','name':'sample','state':'partial'}
        with patch('spieljobs.agent.collect',AsyncMock(return_value=(jobs,[source]))):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                response=await client.post('/search',json={'query':'کارشناس پشتیبانی'})
        self.assertEqual(response.json()['jobs'],[])
        self.assertIn('شواهد کافی',response.json()['warnings'][0])

    async def test_streamed_search_filters_false_positive(self):
        jobs=[{'title':'کارشناس پشتیبانی مشتریان','source':'sample'},
              {'title':'حسابدار مالی','description':'پشتیبانی از امور مالی','source':'sample'}]
        source={'id':'sample','name':'sample','state':'success'}
        collector=AsyncMock(return_value=(jobs,[source]))
        with patch('spieljobs.agent.collect',collector):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                response=await client.post('/search/stream',json={'query':'کارشناس پشتیبانی'})
        self.assertEqual(response.status_code,200)
        self.assertIn('کارشناس پشتیبانی مشتریان',response.text)
        self.assertNotIn('حسابدار مالی',response.text)
        self.assertEqual(collector.call_args.args[0],['پشتیبانی','support','customer service'])

    async def test_real_langfuse_sdk_nests_streaming_search(self):
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
        from langfuse import Langfuse
        provider=TracerProvider()
        exporter=InMemorySpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        try:
            # The SDK is real; only its network exporter is replaced.
            with patch.dict('os.environ', {'LANGFUSE_PUBLIC_KEY':'pk-lf-quality-offline','LANGFUSE_SECRET_KEY':'sk-lf-quality-offline'}):
                client=Langfuse(public_key='pk-lf-quality-offline',secret_key='sk-lf-quality-offline',tracer_provider=provider,span_exporter=InMemorySpanExporter())
                jobs=[{'title':'Python developer','source':'offline'}]
                async def collect_with_generation(*args,**kwargs):
                    from spieljobs.tracing import observation
                    with observation('fixture.generation','generation',model='offline') as generation:
                        generation.update(output={'synthetic':True},usage_details={'input':10,'output':2})
                    return jobs,sources
                sources=[{'id':'offline','name':'Offline','state':'success'}]
                with patch.dict('os.environ', {'MISTRAL_API_KEY':'', 'GEMINI_API_KEY':''}), patch('spieljobs.evaluation.get_trace_client',return_value=client), patch('spieljobs.evaluation.persist_run'), patch('spieljobs.tracing.get_trace_client',return_value=client), patch('spieljobs.agent.collect',side_effect=collect_with_generation):
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as web:
                        response=await web.post('/search/stream',json={'query':'python developer','session_id':'quality-session-1'})
            spans=exporter.get_finished_spans()
            self.assertEqual(response.status_code,200)
            self.assertTrue({'spieljobs.search','spieljobs.prepare','spieljobs.search_sources','spieljobs.rank','spieljobs.evaluate','fixture.generation'}.issubset({s.name for s in spans}))
            self.assertEqual(len({s.context.trace_id for s in spans}),1)
            self.assertEqual(sum(s.parent is None for s in spans),1)
            self.assertTrue(all(s.attributes.get('session.id')=='quality-session-1' for s in spans))
            self.assertTrue(all(s.attributes.get('langfuse.trace.name')=='spieljobs.search' for s in spans))
            root=next(s for s in spans if s.parent is None)
            import json
            self.assertIn('profile',json.loads(root.attributes['langfuse.observation.input']))
            self.assertIn('sources',json.loads(root.attributes['langfuse.observation.output']))
            self.assertIn('"trace_id": "',response.text)
        finally:
            provider.shutdown()
