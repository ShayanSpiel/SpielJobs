"""Real-run record contract and evaluator behavior with isolated test doubles."""
import asyncio
import json
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0,'backend')
from spieljobs.evaluation import make_record, deterministic_checks, evaluate_and_record, judge_relevance, stage_snapshot

def example():
    profile={'interpretation':'resume','terms':['python'],'search_terms':['python'], 'unsupported_constraints':[]}
    source={'id':'jobinja','name':'Jobinja','state':'partial','terms':['python'],'requests':1}
    job={'title':'Python developer','company':'Example','source':'jobinja','url':'https://jobinja.ir/jobs/1?tracking=123','status':'unknown','match_terms':['python']}
    state={'profile':profile,'sources':[source],'jobs':[job],'warnings':[],'model_used':'gemini'}
    stages=[stage_snapshot('prepare',{'profile':profile,'model_used':'gemini'}),stage_snapshot('search',{'sources':[source],'jobs':[job]}),stage_snapshot('rank',{'jobs':[job]})]
    return make_record('Python developer, contact private@example.com','PRIVATE RESUME CONTENT',state,stages,'web_stream')

class RecordTests(unittest.TestCase):
    def test_actual_run_is_structured_and_has_no_resume_or_contact(self):
        record=example(); serialized=json.dumps(record,ensure_ascii=False)
        self.assertEqual(record['category'],'Resume')
        self.assertEqual([x['step'] for x in record['process']['stages']],['prepare','search','rank'])
        self.assertEqual(record['output']['jobs'][0]['url'],'https://jobinja.ir/jobs/1')
        self.assertNotIn('PRIVATE RESUME CONTENT',serialized)
        self.assertNotIn('private@example.com',serialized)
        self.assertEqual(record['process']['sources'][0]['state'],'partial')

    def test_partial_coverage_is_not_a_pass(self):
        checks=deterministic_checks(example())
        self.assertEqual(checks['source_evidence']['state'],'pass')
        self.assertEqual(checks['source_coverage']['state'],'partial')

class FakeClient:
    def __init__(self): self.datasets=[]; self.items=[]; self.scores=[]
    def create_dataset(self,**kw): self.datasets.append(kw)
    def create_dataset_item(self,**kw): self.items.append(kw)
    def create_score(self,**kw): self.scores.append(kw)

class EvaluationTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_awaits_actual_completed_run(self):
        import httpx
        from spieljobs.server import app
        source={'id':'jobinja','name':'Jobinja','state':'partial','requests':1}
        job={'title':'Python Developer','company':'Example','url':'https://jobinja.ir/jobs/1','source':'jobinja','status':'unknown'}
        class Span:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def update(self,**kwargs): pass
        class Tracer:
            def start_as_current_observation(self,**kwargs): return Span()
            def get_current_trace_id(self): return 'real-run-trace'
        with patch('spieljobs.tracing.get_trace_client',return_value=Tracer()), patch('spieljobs.agent.collect',AsyncMock(return_value=([job],[source]))), patch('spieljobs.agent.enrich_jobs',AsyncMock(side_effect=lambda jobs: jobs)), patch('spieljobs.agent.complete_evaluation', new_callable=AsyncMock) as schedule:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                response=await client.post('/search/stream',json={'query':'Python developer'})
        self.assertEqual(response.status_code,200)
        schedule.assert_awaited_once()
        trace_id,record=schedule.call_args.args
        self.assertEqual(trace_id,'real-run-trace')
        self.assertEqual(record['input']['request'],'Python developer')
        self.assertEqual([step['step'] for step in record['process']['stages']],['prepare','search','rank'])
        self.assertEqual(record['output']['jobs'][0]['title'],'Python Developer')

    async def test_unavailable_model_is_not_a_false_pass(self):
        with patch.dict('os.environ',{},clear=True):
            result=await judge_relevance(example())
        self.assertEqual(result['state'],'not_run')

    async def test_model_judge_evaluates_each_returned_job(self):
        import httpx
        payload={'choices':[{'message':{'content':json.dumps({'results':[{'index':1,'label':'relevant','reason':'Python role matches.'}]})}}]}
        def handler(request): return httpx.Response(200,json=payload,request=request)
        original=httpx.AsyncClient
        def client(*args,**kwargs):
            kwargs['transport']=httpx.MockTransport(handler)
            return original(*args,**kwargs)
        with patch.dict('os.environ',{'MISTRAL_API_KEY':'test-key'},clear=True), patch('spieljobs.evaluation.httpx.AsyncClient',side_effect=client):
            result=await judge_relevance(example())
        self.assertEqual(result['state'],'completed')
        self.assertEqual(result['results'][0]['label'],'relevant')

    async def test_model_judge_rejects_incomplete_results(self):
        import httpx
        def handler(request): return httpx.Response(200,json={'choices':[{'message':{'content':'{"results": []}'}}]},request=request)
        original=httpx.AsyncClient
        def client(*args,**kwargs):
            kwargs['transport']=httpx.MockTransport(handler)
            return original(*args,**kwargs)
        with patch.dict('os.environ',{'MISTRAL_API_KEY':'test-key'},clear=True), patch('spieljobs.evaluation.httpx.AsyncClient',side_effect=client):
            result=await judge_relevance(example())
        self.assertEqual(result['state'],'not_run')

    async def test_scores_and_actual_dataset_item_are_sent(self):
        client=FakeClient(); record=example()
        judged={'state':'completed','results':[{'index':1,'label':'relevant','reason':'Title matches Python.'}],'limitation':'title only'}
        with patch('spieljobs.evaluation.get_trace_client',return_value=client), patch('spieljobs.evaluation.judge_relevance',AsyncMock(return_value=judged)), patch('spieljobs.evaluation.observation') as obs:
            obs.return_value.__enter__.return_value.update=lambda **kwargs:None
            await evaluate_and_record('trace-123',record)
        self.assertEqual(client.items[0]['source_trace_id'],'trace-123')
        self.assertIsNone(client.items[0]['expected_output'])
        self.assertEqual(client.items[0]['metadata']['observed_output']['total'],1)
        self.assertEqual(client.items[0]['metadata']['evaluation']['relevance']['state'],'completed')
        self.assertTrue(any(x['name']=='SpielJobs / result 1 relevance' and x['value']=='relevant' for x in client.scores))
