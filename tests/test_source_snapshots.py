import json
import os
import sys
import time
import unittest
from unittest.mock import patch

import httpx
sys.path.insert(0, 'backend')
from spieljobs.source_snapshots import load_snapshot, save_snapshot


class SharedSnapshotTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.source = {'id':'employer','name':'Employer','url':'https://example.org/jobs'}
        self.report = {**self.source,'state':'partial','checked_at':'2026-11-17T12:00:00+00:00','requests':1}
        self.jobs = [{'title':'Accountant','company':'Employer','url':'https://example.org/jobs/1','source':'employer'}]
        self.env = patch.dict(os.environ, {'UPSTASH_REDIS_REST_URL':'https://cache.example.org', 'UPSTASH_REDIS_REST_TOKEN':'test-token'})
        self.env.start()
        self.addCleanup(self.env.stop)

    async def test_new_worker_recovers_public_jobs_from_shared_store(self):
        store = {}
        def handler(request):
            args = json.loads(request.content)
            self.assertEqual(request.headers['Authorization'], 'Bearer test-token')
            if args[0] == 'SET':
                self.assertEqual(args[-2:], ['EX','1800'])
                store[args[1]] = args[2]
                return httpx.Response(200,json={'result':'OK'})
            return httpx.Response(200,json={'result':store.get(args[1])})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await save_snapshot(client,self.source,self.jobs,self.report)
            cached = await load_snapshot(client,self.source)
            self.assertIsNotNone(cached)
            self.assertEqual(cached[1][0][0]['title'], 'Accountant')
            self.assertEqual(cached[1][1]['checked_at'], self.report['checked_at'])
            # A different source configuration cannot use the old snapshot.
            self.assertIsNone(await load_snapshot(client,{**self.source,'url':'https://new.example.org'}))

    async def test_unavailable_cache_does_not_block_source_retrieval(self):
        def handler(request):
            raise httpx.ConnectError('cache unavailable',request=request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            self.assertIsNone(await load_snapshot(client,self.source))
            await save_snapshot(client,self.source,self.jobs,self.report)

    async def test_expired_or_wrong_source_evidence_is_rejected(self):
        for age, report in [(1900,self.report),(0,{**self.report,'id':'other'}),(0,{**self.report,'state':'unavailable'})]:
            data=json.dumps({'stored_at':time.time()-age,'jobs':self.jobs,'report':report})
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200,json={'result':data}))) as client:
                self.assertIsNone(await load_snapshot(client,self.source))
