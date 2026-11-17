"""Public HTTP transport. Search orchestration lives in agent.search_events."""
from contextlib import asynccontextmanager
import asyncio
import json
import logging
import os

from fastapi import FastAPI, File, HTTPException, UploadFile, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from .agent import search_events, search_jobs
from .analytics import analytics_context
from .guards import RequestGuards
from .resumes import extract_resume
from .tracing import observation, flush_trace_client, trace_scope
from .mcp_server import mcp

from .revision import RUNTIME_REVISION
REVISION = RUNTIME_REVISION
mcp_http_app = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(app):
    async with mcp.session_manager.run():
        yield
        await asyncio.to_thread(flush_trace_client)


app = FastAPI(title='SpielJobs API', version='0.1.0', lifespan=lifespan)
app.add_middleware(RequestGuards)
origins = os.getenv('SPIELJOBS_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000,https://job.spielos.xyz').split(',')
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in origins if o.strip()], allow_methods=['GET', 'POST'], allow_headers=['Content-Type','X-POSTHOG-DISTINCT-ID','X-POSTHOG-SESSION-ID'])


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    resume: str = Field(default='', max_length=30000)
    session_id: str | None = Field(default=None,max_length=128,pattern=r'^[A-Za-z0-9_.:-]+$')

    @field_validator('query')
    @classmethod
    def nonblank_query(cls, value):
        if not value.strip():
            raise ValueError('Query must not be blank')
        return value.strip()


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc):
    # Pydantic's default includes submitted input, potentially a private resume.
    return JSONResponse({'detail': [{'loc': error['loc'], 'msg': error['msg'], 'type': error['type']} for error in exc.errors()]}, 422)


@app.get('/health')
async def health():
    return {'ok': True, 'runtime_revision': REVISION,
        'langfuse_configured': bool(os.getenv('LANGFUSE_PUBLIC_KEY') and os.getenv('LANGFUSE_SECRET_KEY')),
        'shared_rate_limit_configured': bool(os.getenv('UPSTASH_REDIS_REST_URL') and os.getenv('UPSTASH_REDIS_REST_TOKEN'))}


@app.post('/search')
async def search(request: SearchRequest, http_request:Request):
    try:
        with analytics_context(http_request.headers):
            return await search_jobs(request.query, request.resume,session_id=request.session_id)
    except TimeoutError:
        raise HTTPException(504, 'Search exceeded its time budget') from None


@app.post('/search/stream')
async def stream_search(request: SearchRequest, http_request:Request):
    async def events():
        try:
            with analytics_context(http_request.headers):
                async for kind, data in search_events(request.query, request.resume, 'web_stream',session_id=request.session_id):
                    yield 'event: ' + kind + '\ndata: ' + json.dumps(data, ensure_ascii=False) + '\n\n'
        except Exception as exc:
            # Log exception class only: source/model errors may contain input.
            logging.getLogger(__name__).warning('Search stream failed: %s', type(exc).__name__)
            yield 'event: error\ndata: ' + json.dumps({'message': 'جست‌وجو با خطا متوقف شد. دوباره تلاش کنید.'}, ensure_ascii=False) + '\n\n'
    return StreamingResponse(events(), media_type='text/event-stream', headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})


@app.post('/resume')
async def resume(file: UploadFile = File(...)):
    try:
        data = await file.read(2_000_001)
        if len(data) > 2_000_000:
            raise HTTPException(413, 'Resume must be under 2 MB')
        with trace_scope(channel='resume_upload',trace_name='spieljobs.resume.extract'), observation('spieljobs.resume.extract', 'chain', input={'file_size_bytes': len(data)}) as span:
            try:
                async with asyncio.timeout(5):
                    text = await asyncio.to_thread(extract_resume, data)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from None
            except TimeoutError:
                raise HTTPException(400, 'Resume took too long to read') from None
            except Exception:
                raise HTTPException(400, 'Resume could not be read') from None
            span.update(output={'extracted_characters': len(text)})
            return {'text': text}
    finally:
        await file.close()


# Keep /mcp at the root path expected by Streamable HTTP clients.
app.mount('/', mcp_http_app)
