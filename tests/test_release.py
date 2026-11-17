"""Release boundaries: limits, private errors, document parsing and constraints."""
import asyncio
from io import BytesIO
import json
import os
import unittest
from unittest.mock import AsyncMock, patch
from zipfile import ZipFile

import httpx
from fastapi import FastAPI
from spieljobs.guards import RequestGuards, MAX_BODY
from spieljobs.resumes import extract_resume
from spieljobs.core import parse_query, rank_and_filter
from spieljobs.server import app
from spieljobs.extra_sources import CAREERS, fetch_hrcando


def docx(xml):
    output = BytesIO()
    with ZipFile(output, 'w') as archive:
        archive.writestr('word/document.xml', xml)
    return output.getvalue()


class ResumeTests(unittest.TestCase):
    def test_docx_extracts_paragraphs_without_saving_upload(self):
        data = docx('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Python developer</w:t></w:r></w:p><w:p><w:r><w:t>تهران</w:t></w:r></w:p></w:body></w:document>')
        self.assertEqual(extract_resume(data), 'Python developer\nتهران')

    def test_docx_entities_are_rejected(self):
        with self.assertRaises(ValueError):
            extract_resume(docx('<!DOCTYPE x [<!ENTITY a "expansion">]><x>&a;</x>'))

    def test_docx_expansion_is_bounded(self):
        with self.assertRaises(ValueError):
            extract_resume(docx('x' * 8_000_001))


class ConstraintTests(unittest.TestCase):
    def test_closed_and_unknown_locations_do_not_satisfy_tehran(self):
        jobs = [{'title':'Python Developer', 'location':'Tehran', 'status':'closed'},
                {'title':'Python Developer', 'location':None, 'status':'unknown'},
                {'title':'Python Developer', 'location':'تهران', 'status':'open'}]
        self.assertEqual(rank_and_filter(jobs, parse_query('Python developer in Tehran')), [dict(jobs[2], match_terms=['python'], score=10)])

    def test_seniority_does_not_return_junior_vacancies(self):
        jobs = [{'title':'Junior Python Developer'}, {'title':'Senior Python Developer'}, {'title':'Python Developer'}]
        self.assertEqual([j['title'] for j in rank_and_filter(jobs, parse_query('senior Python developer'))], ['Senior Python Developer'])


class HttpBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_validation_does_not_echo_resume(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            response = await client.post('/search',json={'query':' ', 'resume':'PRIVATE' * 6000})
        self.assertEqual(response.status_code,422)
        self.assertNotIn('PRIVATE', response.text)
        self.assertEqual(response.headers['cache-control'],'no-store')

    async def test_oversized_chunked_request_is_rejected_before_search(self):
        async def chunks():
            yield b'x' * MAX_BODY
            yield b'x'
        with patch('spieljobs.server.search_jobs', new_callable=AsyncMock) as search:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                response = await client.post('/search',content=chunks())
        self.assertEqual(response.status_code,413)
        search.assert_not_called()

    async def test_rate_limit_covers_mcp_and_api_and_ignores_spoofed_forwarding(self):
        test_app = FastAPI()
        test_app.add_middleware(RequestGuards)
        @test_app.post('/search')
        @test_app.post('/mcp')
        async def endpoint(): return {'ok':True}
        with patch.dict(os.environ,{'SPIELJOBS_REQUESTS_PER_MINUTE':'1','VERCEL':'0','UPSTASH_REDIS_REST_URL':''}):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app),base_url='http://test') as client:
                first = await client.post('/search')
                second = await client.post('/mcp',headers={'X-Forwarded-For':'different-ip'})
        self.assertEqual((first.status_code,second.status_code),(200,429))
        self.assertIn('retry-after',second.headers)

    async def test_shared_limit_failure_closes_paid_endpoints(self):
        guard=RequestGuards(None)
        with patch.dict(os.environ,{'UPSTASH_REDIS_REST_URL':'https://redis.example','UPSTASH_REDIS_REST_TOKEN':'test'}), patch('spieljobs.guards.httpx.AsyncClient') as client:
            client.return_value.__aenter__.return_value.post=AsyncMock(side_effect=httpx.ConnectError('offline'))
            self.assertIsNone(await guard.allow('127.0.0.1'))

    async def test_api_and_stream_have_same_final_result(self):
        data=([{'title':'Python Developer','source':'fixture','url':'https://example.com/job/1'}],[{'id':'fixture','name':'Fixture','state':'partial'}])
        with patch('spieljobs.agent.collect',AsyncMock(return_value=data)):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                regular=await client.post('/search',json={'query':'Python developer'})
                stream=await client.post('/search/stream',json={'query':'Python developer'})
        result=next(frame for frame in stream.text.split('\n\n') if frame.startswith('event: result'))
        ordinary=regular.json(); streamed=json.loads(result.split('data: ',1)[1])
        for key in ('jobs','sources','profile','warnings','model_used'):
            self.assertEqual(ordinary.get(key),streamed.get(key))
        self.assertNotEqual(ordinary['run_id'],streamed['run_id'])
        self.assertEqual(ordinary['runtime']['revision'],streamed['runtime']['revision'])

    async def test_client_cancellation_cancels_sources(self):
        from spieljobs.agent import search_jobs
        cancelled=asyncio.Event()
        async def collector(terms):
            try: await asyncio.Event().wait()
            finally: cancelled.set()
        with patch('spieljobs.agent.collect',collector):
            task=asyncio.create_task(search_jobs('Python developer'))
            await asyncio.sleep(0.02)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError): await task
        self.assertTrue(cancelled.is_set())


class HrcandoTests(unittest.IsolatedAsyncioTestCase):
    async def test_snappfood_inline_tenant_and_pagination(self):
        source=next(s for s in CAREERS if s['id']=='snappfood')
        pages=[]
        def handler(request):
            if request.method=='GET':
                return httpx.Response(200,text='<script>window.config={companyApiKey:"11111111-1111-1111-1111-111111111111"}</script>')
            payload=json.loads(request.content); number=payload['PageNumber']; pages.append(number)
            self.assertEqual(payload['CityId'],'')
            self.assertEqual(request.headers['Origin'],'https://careers.snappfood.ir')
            return httpx.Response(200,json={'succeed':True,'data':{'totalPages':2,'jobs':[{'id':number,'title':'Product Manager'}]}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            jobs=await fetch_hrcando(client,source)
        self.assertEqual(pages,[1,2])
        self.assertEqual([j['url'] for j in jobs],['https://careers.snappfood.ir/job-details/1','https://careers.snappfood.ir/job-details/2'])

class ProductionLimitTests(unittest.IsolatedAsyncioTestCase):
    async def test_production_requires_shared_limits(self):
        with patch.dict(os.environ,{'VERCEL_ENV':'production','UPSTASH_REDIS_REST_URL':'','UPSTASH_REDIS_REST_TOKEN':''}):
            self.assertIsNone(await RequestGuards(None).allow('127.0.0.1'))
