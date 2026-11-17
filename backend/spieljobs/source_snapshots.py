"""Shared public employer snapshots using the existing Upstash REST connection.

Never stores board queries, resume text or user identifiers. Shared cache failures
are optional: retrieval continues directly from the source.
"""
import hashlib
import json
import os
import time
from datetime import datetime

import httpx

MAX_AGE_SECONDS = 1800
MAX_BYTES = 2_000_000


def snapshot_key(source):
    # Changing an adapter or its configuration must invalidate old evidence.
    from .revision import RUNTIME_REVISION
    config = json.dumps(source, sort_keys=True, ensure_ascii=True)
    fingerprint = hashlib.sha256(config.encode()).hexdigest()[:16]
    return f'spieljobs:source:{RUNTIME_REVISION}:{source["id"]}:{fingerprint}'


async def command(client, args):
    endpoint = os.getenv('UPSTASH_REDIS_REST_URL')
    token = os.getenv('UPSTASH_REDIS_REST_TOKEN')
    if not endpoint or not token:
        return None
    try:
        response = await client.post(endpoint.rstrip('/'),
            headers={'Authorization': f'Bearer {token}'}, json=args, timeout=0.8)
        response.raise_for_status()
        body = response.json()
        return body.get('result') if isinstance(body, dict) else None
    except (httpx.HTTPError, ValueError, TypeError):
        return None


async def load_snapshot(client, source):
    encoded = await command(client, ['GET', snapshot_key(source)])
    if not isinstance(encoded, str) or len(encoded.encode()) > MAX_BYTES:
        return None
    try:
        record = json.loads(encoded)
        age = time.time() - record['stored_at']
        if not 0 <= age < MAX_AGE_SECONDS:
            return None
        jobs, report = record['jobs'], record['report']
        if not isinstance(jobs, list) or not isinstance(report, dict):
            return None
        if report.get('id') != source['id'] or report.get('state') not in ('success', 'partial'):
            return None
        datetime.fromisoformat(report['checked_at'])
        # Validate shared records with the same schema as live retrieval.
        from .contracts import normalize_jobs
        jobs, rejected = normalize_jobs(jobs, source, report['checked_at'])
        if rejected:
            return None
        return time.monotonic() - age, (jobs, report)
    except (ValueError, TypeError, KeyError, OverflowError):
        return None


async def save_snapshot(client, source, jobs, report):
    encoded = json.dumps({'stored_at':time.time(), 'jobs':jobs, 'report':report}, ensure_ascii=False)
    if len(encoded.encode()) > MAX_BYTES:
        return
    await command(client, ['SET', snapshot_key(source), encoded, 'EX', str(MAX_AGE_SECONDS)])
