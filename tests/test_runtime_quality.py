"""Behavioral runtime regressions; network/provider calls are mocked."""
import sys
import unittest
from io import BytesIO
from unittest.mock import AsyncMock, patch
sys.path.insert(0,'backend')
import httpx
from pypdf import PdfWriter
from pypdf.generic import NameObject, DictionaryObject, DecodedStreamObject
from spieljobs.agent import prepare, search_jobs
from spieljobs.core import needs_interpretation
from spieljobs.server import app


def make_pdf(text=None):
    writer=PdfWriter()
    page=writer.add_blank_page(width=300,height=200)
    if text:
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 40 120 Td ('+text.encode('ascii')+b') Tj ET')
        page[NameObject('/Contents')]=writer._add_object(stream)
    output=BytesIO();writer.write(output);return output.getvalue()

class InterpretationRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_short_keywords_do_not_call_model(self):
        with patch('spieljobs.agent.extract_profile') as model:
            result=await prepare({'query':'Python developer'})
        self.assertEqual(result['profile']['interpretation'],'deterministic')
        model.assert_not_called()

    async def test_ambiguous_prompt_calls_model_and_searches_inferred_roles(self):
        query="I know Python, analytics and team leadership, but I don't know what job I should apply for"
        model=AsyncMock(return_value=(['data analyst','analytics manager'],'mistral'))
        with patch('spieljobs.agent.extract_profile',model):
            result=await prepare({'query':query})
        model.assert_awaited_once()
        self.assertEqual(result['profile']['interpretation'],'complex_prompt')
        self.assertEqual(result['profile']['search_terms'][:2],['data analyst','analytics manager'])

    async def test_long_prompt_provider_failure_reports_degraded_mode(self):
        query='I have experience with product, analytics, leadership and operations. '*4
        with patch('spieljobs.agent.extract_profile',AsyncMock(return_value=([],None))):
            result=await prepare({'query':query})
        self.assertTrue(result['warnings'])
        self.assertEqual(result['profile']['interpretation'],'complex_prompt')

    def test_resume_always_routes_to_interpreter(self):
        self.assertTrue(needs_interpretation('Python', 'Python developer'))
        self.assertFalse(needs_interpretation('Python', ''))

class PdfHandlingTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_text_pdf_extracts_text(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            response=await client.post('/resume',files={'file':('resume.pdf',make_pdf('Python Developer'),'application/pdf')})
        self.assertEqual(response.status_code,200)
        self.assertIn('Python Developer',response.json()['text'])

    async def test_image_only_or_blank_pdf_is_not_treated_as_resume(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            response=await client.post('/resume',files={'file':('scan.pdf',make_pdf(),'application/pdf')})
        self.assertEqual(response.status_code,400)
        self.assertIn('No text found',response.json()['detail'])

    async def test_non_pdf_is_rejected(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            response=await client.post('/resume',files={'file':('resume.pdf',b'not a pdf','application/pdf')})
        self.assertEqual(response.status_code,400)

class FailureHandlingTests(unittest.IsolatedAsyncioTestCase):
    async def test_source_outage_is_not_a_success_or_fake_zero(self):
        report={'id':'jobinja','name':'Jobinja','state':'unavailable','message':'request failed','checked_at':'2026-11-16T12:00:00Z'}
        with patch('spieljobs.agent.collect',AsyncMock(return_value=([],[report]))):
            result=await search_jobs('Python developer')
        self.assertEqual(result['jobs'],[])
        self.assertEqual(result['sources'][0]['state'],'unavailable')

    async def test_unsupported_remote_constraint_never_silently_returns_jobs(self):
        with patch('spieljobs.agent.collect') as collect:
            result=await search_jobs('Python developer remote only')
        collect.assert_not_called()
        self.assertEqual(result['jobs'],[])
        self.assertTrue(result['warnings'])

    async def test_excluded_tehran_is_not_treated_as_required_tehran(self):
        with patch('spieljobs.agent.collect') as collect:
            result=await search_jobs('Python jobs except Tehran')
        collect.assert_not_called()
        self.assertIsNone(result['profile']['location'])
        self.assertTrue(result['warnings'])

    @unittest.skip('Not yet verified: compare all results with the live Jobinja listing and closed job details.')
    def test_live_jobinja_coverage_and_status(self):
        pass

    @unittest.skip('Browser interaction tests require an accessible browser and running UI.')
    def test_browser_keyboard_rtl_mobile_and_cancellation(self):
        pass

class TraceContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_runtime_stages_are_nested_and_redacted(self):
        import contextvars
        import json
        current=contextvars.ContextVar('test_trace_parent',default=None)
        entries=[]
        class Span:
            def __init__(self,name,kwargs):
                self.data={'name':name,'arguments':kwargs,'parent':current.get(),'updates':[]};entries.append(self.data)
            def __enter__(self):
                self.token=current.set(self.data['name']);return self
            def __exit__(self,*args):current.reset(self.token)
            def update(self,**kwargs):self.data['updates'].append(kwargs)
        class FakeClient:
            def start_as_current_observation(self,*,name,as_type,**kwargs):
                return Span(name,{'as_type':as_type,**kwargs})
        source={'id':'test','name':'Test','state':'partial','checked_at':'2026-11-16'}
        async def collect(_):return ([{'title':'Python Developer','source':'test'}],[source])
        async def model(*args,**kwargs):return ['python'], 'fake'
        with patch('spieljobs.tracing.get_trace_client',return_value=FakeClient()), patch('spieljobs.agent.collect',side_effect=collect), patch('spieljobs.agent.extract_profile',side_effect=model):
            await search_jobs('Python private-user@example.com','Personal confidential resume Python')
        names={entry['name'] for entry in entries}
        self.assertTrue({'spieljobs.search','spieljobs.prepare','spieljobs.search_sources','spieljobs.rank'} <= names)
        for entry in entries:
            if entry['name']!='spieljobs.search':self.assertEqual(entry['parent'],'spieljobs.search')
        serialized=json.dumps(entries)
        self.assertNotIn('private-user@example.com',serialized)
        self.assertNotIn('Personal confidential resume',serialized)

    async def test_trace_failure_never_breaks_search(self):
        class BrokenClient:
            def start_as_current_observation(self,**kwargs):raise RuntimeError('telemetry unavailable')
        with patch('spieljobs.tracing.get_trace_client',return_value=BrokenClient()), patch('spieljobs.agent.collect',AsyncMock(return_value=([],[]))):
            result=await search_jobs('Python developer')
        self.assertEqual(result['jobs'],[])
