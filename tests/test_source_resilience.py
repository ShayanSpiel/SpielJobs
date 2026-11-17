"""User-visible continuity when a previously healthy employer goes offline."""
import asyncio
import sys
import time
import unittest
from unittest.mock import patch

import httpx
sys.path.insert(0, 'backend')
from spieljobs import extra_sources as sources


class SourceResilienceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.source = {'id':'test-employer','name':'Employer','url':'https://example.org/jobs',
                       'kind':'recrupen','api_url':'https://example.org/jobs','company_id':1}
        self.report = {**self.source,'state':'partial','checked_at':'2026-11-17T12:00:00Z',
                       'requests':1}
        self.jobs = [{'title':'Accountant','url':'https://example.org/jobs/1'}]
        self.original_client = httpx.AsyncClient
        sources._career_cache.clear()

    def tearDown(self):
        sources._career_cache.clear()

    async def collect(self, handler, concurrent=False):
        def client(*args, **kwargs):
            return self.original_client(*args, transport=httpx.MockTransport(handler), **kwargs)
        with patch.object(sources, 'CAREERS', [self.source]), patch.object(sources.httpx, 'AsyncClient', side_effect=client):
            if concurrent:
                return await asyncio.gather(sources.collect_extra(['accountant']), sources.collect_extra(['accountant']))
            return await sources.collect_extra(['accountant'])

    def seed(self, age):
        sources._career_cache[self.source['id']] = (time.monotonic()-age, (self.jobs, self.report))

    async def test_timeout_keeps_dated_jobs_and_does_not_claim_live_availability(self):
        self.seed(400)
        def handler(request):
            raise httpx.ReadTimeout('upstream delay', request=request)
        jobs, reports = await self.collect(handler)
        report = next(r for r in reports if r['id']==self.source['id'])
        self.assertEqual(jobs, self.jobs)
        self.assertEqual(report['state'], 'stale')
        self.assertEqual(report['checked_at'], self.report['checked_at'])
        self.assertEqual(report['refresh_failure_kind'], 'timeout')
        self.assertGreaterEqual(report['cache_age_seconds'], 400)
        self.assertEqual(sources._career_cache[self.source['id']][1][1]['state'], 'partial')
        # A caller cannot mutate the retained snapshot through its response.
        jobs[0]['title'] = 'changed'
        self.assertEqual(sources._career_cache[self.source['id']][1][0][0]['title'], 'Accountant')

    async def test_old_snapshots_and_explicit_blocks_are_not_reused(self):
        for age, status in [(1900,503), (400,403), (400,404)]:
            with self.subTest(age=age, status=status):
                self.seed(age)
                jobs, reports = await self.collect(lambda request: httpx.Response(status))
                self.assertFalse(jobs)
                self.assertEqual(next(r for r in reports if r['id']==self.source['id'])['state'], 'unavailable')

    async def test_concurrent_searches_fetch_each_employer_once(self):
        calls = []
        async def handler(request):
            if request.url.host == 'example.org':
                calls.append(request.url)
                await asyncio.sleep(0.01)
                return httpx.Response(200,json=[])
            raise httpx.ConnectError('board unavailable',request=request)
        # Empty validated API results are cached too; zero vacancies is healthy.
        with patch.object(sources, 'parse_recrupen', return_value=[]):
            results = await self.collect(handler, concurrent=True)
        self.assertEqual(len(calls), 1)
        for _, reports in results:
            self.assertEqual(next(r for r in reports if r['id']==self.source['id'])['state'], 'success')

    async def test_transient_gateway_failure_retries_then_returns_live_response(self):
        calls = []
        def handler(request):
            if request.url.host != 'example.org':
                return httpx.Response(403)
            calls.append(request.url)
            return httpx.Response(503) if len(calls) == 1 else httpx.Response(200, json=[])
        with patch.object(sources, 'parse_recrupen', return_value=[]):
            jobs, reports = await self.collect(handler)
        report = next(r for r in reports if r['id']==self.source['id'])
        self.assertEqual(len(calls), 2)
        self.assertEqual(report['state'], 'success')
        self.assertEqual(report['retry_count'], 1)
        self.assertFalse(jobs)
