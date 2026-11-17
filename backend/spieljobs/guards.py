"""HTTP abuse controls. Redis counters are shared across serverless instances.

The local fallback only protects a single process; configure Redis for a public
release. No query, resume, or raw IP is stored in the counters.
"""
import asyncio
import hashlib
import os
import time
from collections import OrderedDict

import httpx
from starlette.responses import JSONResponse

MAX_BODY = 2_100_000


class RequestGuards:
    def __init__(self, app):
        self.app = app
        self.windows = OrderedDict()
        self.active = 0

    async def allow(self, identity):
        limit = int(os.getenv('SPIELJOBS_REQUESTS_PER_MINUTE', '10'))
        bucket = int(time.time() // 60)
        digest = hashlib.sha256(identity.encode()).hexdigest()[:32]
        key = f'{{spieljobs}}:requests:{bucket}:{digest}'
        global_key = f'{{spieljobs}}:requests:{bucket}:global'
        endpoint = os.getenv('UPSTASH_REDIS_REST_URL')
        token = os.getenv('UPSTASH_REDIS_REST_TOKEN')
        if endpoint and token:
            # A single atomic script sets expiry with the first increment.
            script = "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],120) end; local g=redis.call('INCR',KEYS[2]); if g==1 then redis.call('EXPIRE',KEYS[2],120) end; return {n,g}"
            try:
                async with httpx.AsyncClient(timeout=2) as client:
                    response = await client.post(endpoint.rstrip('/'),
                        headers={'Authorization': f'Bearer {token}'},
                        json=['EVAL', script, '2', key, global_key])
                    response.raise_for_status()
                    count, total = response.json()['result']
                    return int(count) <= limit and int(total) <= int(os.getenv('SPIELJOBS_GLOBAL_REQUESTS_PER_MINUTE', '120'))
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                # A broken shared limiter must not silently open paid endpoints.
                return None
        if os.getenv('VERCEL_ENV') == 'production':
            # Never expose paid anonymous endpoints with process-local quotas
            # pretending to protect a horizontally scaled production service.
            return None
        self.windows = OrderedDict((k, v) for k, v in self.windows.items() if v[0] == bucket)
        _, count = self.windows.pop(digest, (bucket, 0))
        self.windows[digest] = (bucket, count + 1)
        while len(self.windows) > 4096:
            self.windows.popitem(last=False)
        return count < limit

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        protected = scope['method'] == 'POST' and scope['path'] in ('/search', '/search/stream', '/resume', '/mcp', '/mcp/')
        if not protected:
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        try:
            length = int(headers.get(b'content-length', b'0'))
        except ValueError:
            length = MAX_BODY + 1
        if length < 0 or length > MAX_BODY:
            return await JSONResponse({'detail': 'Request too large'}, 413)(scope, receive, send)
        # Trust the platform-injected address only on Vercel. Locally, use the
        # socket address; a client-supplied X-Forwarded-For cannot evade quotas.
        identity = (scope.get('client') or ('unknown',))[0]
        if os.getenv('VERCEL') == '1':
            identity = headers.get(b'x-vercel-forwarded-for', identity.encode()).decode().split(',')[0].strip()
        allowed = await self.allow(identity)
        if allowed is None:
            return await JSONResponse({'detail': 'Request limits temporarily unavailable'}, 503)(scope, receive, send)
        if not allowed:
            return await JSONResponse({'detail': 'Too many requests'}, 429, headers={'Retry-After': '60'})(scope, receive, send)
        if self.active >= int(os.getenv('SPIELJOBS_MAX_CONCURRENT_REQUESTS', '4')):
            return await JSONResponse({'detail': 'Service busy; retry shortly'}, 503, headers={'Retry-After': '5'})(scope, receive, send)
        self.active += 1
        try:
            # Buffer within the cap before parsing multipart/JSON, including
            # chunked uploads with no Content-Length.
            chunks = []; size = 0
            while True:
                try:
                    async with asyncio.timeout(15):
                        message = await receive()
                except TimeoutError:
                    return await JSONResponse({'detail': 'Request upload timed out'}, 408)(scope, receive, send)
                if message['type'] == 'http.disconnect':
                    return
                size += len(message.get('body', b''))
                if size > MAX_BODY:
                    return await JSONResponse({'detail': 'Request too large'}, 413)(scope, receive, send)
                chunks.append(message.get('body', b''))
                if not message.get('more_body', False):
                    break
            body = b''.join(chunks); delivered = False
            async def bounded_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {'type': 'http.request', 'body': body, 'more_body': False}
                return await receive()
            async def private_send(message):
                if message['type'] == 'http.response.start':
                    message['headers'] = list(message.get('headers', [])) + [(b'cache-control', b'no-store'), (b'x-content-type-options', b'nosniff')]
                await send(message)
            await self.app(scope, bounded_receive, private_send)
        finally:
            self.active -= 1
