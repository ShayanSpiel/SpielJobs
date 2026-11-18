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

    async def test_company_board_fallback_preserves_jobvision_url_and_provenance(self):
        self.source.update(kind='html', jobvision_fallback_id=581)

        def handler(request):
            if request.url.host == 'example.org':
                raise httpx.ConnectError('careers host unavailable', request=request)
            if b'"companyId":581' in request.content:
                return httpx.Response(200, json={'data': {'jobPosts': [
                    {'id': 42, 'title': 'Accountant', 'company': {'id': 581, 'nameFa': 'ازکی'}},
                ]}})
            return httpx.Response(200, json={'data': {'jobPosts': []}})

        jobs, reports = await self.collect(handler)
        report = next(r for r in reports if r['id'] == self.source['id'])
        self.assertEqual(report['provider'], 'jobvision')
        self.assertEqual(report['state'], 'partial')
        self.assertEqual(jobs[0]['url'], 'https://jobvision.ir/jobs/42')

    async def test_browser_verification_with_status_200_is_reported_as_blocked(self):
        self.source.update(kind='html', access_challenge_marker='__arcsjsc')

        def handler(request):
            if request.url.host == 'example.org':
                return httpx.Response(200, text='<script>document.cookie="__arcsjsc=fixture"</script>')
            return httpx.Response(403)

        jobs, reports = await self.collect(handler)
        report = next(r for r in reports if r['id'] == self.source['id'])
        self.assertFalse(jobs)
        self.assertEqual((report['state'], report['failure_kind']), ('unavailable', 'blocked'))

    async def test_employer_feed_retains_primary_retrieval_failure(self):
        self.source.update(kind='html', jobvision_fallback_id=581,
                           unavailable_marker='scheduled maintenance')

        for status, page, failure in [
            (403, '', 'blocked'),
            (200, '<p>scheduled maintenance</p>', 'source_maintenance'),
            (200, '<div>Loading...</div>', 'schema_changed'),
        ]:
            with self.subTest(failure=failure):
                sources._career_cache.clear()

                def handler(request):
                    if request.url.host == 'example.org':
                        return httpx.Response(status, text=page)
                    return httpx.Response(200, json={'data': {'jobPosts': []}})

                _, reports = await self.collect(handler)
                report = next(r for r in reports if r['id'] == self.source['id'])
                self.assertEqual(report['state'], 'success')
                self.assertEqual(report['provider'], 'jobvision')
                self.assertEqual(report['primary_failure_kind'], failure)
                self.assertEqual(report['primary_http_status'], 403 if status == 403 else None)

    async def test_public_listing_fallback_requires_matching_employer_application(self):
        self.source.update(kind='html', hiretik_fallback_url='https://hiretik.com/companies/arvan',
                           application_host='jobs.arvancloud.ir')
        identity = '00c1ae1f-17fb-476c-a33c-e33c6584792c'

        def page(host):
            return f'''<article data-job-id="{identity}">
                <a href="/jobs/{identity}">Core System Engineer</a>
                <a href="https://{host}/o/core-system-engineer/c/new" data-track="apply"
                   data-track-job-id="{identity}">Apply</a>
            </article>'''

        for host in ('unrelated.example', 'jobs.arvancloud.ir'):
            def handler(request):
                if request.url.host == 'hiretik.com':
                    return httpx.Response(200, text=page(host))
                return httpx.Response(403)

            jobs, reports = await self.collect(handler)
            report = next(r for r in reports if r['id'] == self.source['id'])
            if host == 'unrelated.example':
                self.assertFalse(jobs)
                self.assertEqual(report['state'], 'unavailable')
                continue
            self.assertEqual(report['provider'], 'hiretik')
            self.assertEqual(report['primary_failure_kind'], 'blocked')
            self.assertEqual(jobs[0]['url'], f'https://hiretik.com/jobs/{identity}')
            self.assertEqual(jobs[0]['application_url'], f'https://{host}/o/core-system-engineer/c/new')
