"""Versioned source boundary. Adapters emit evidence, never presentation guesses."""
from datetime import date
from hashlib import sha256
import re
from urllib.parse import urlsplit, urlunsplit
from .urls import canonical_public_url
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class Compensation(BaseModel):
    minimum: float | None = None
    maximum: float | None = None
    currency: str | None = None
    period: str | None = None
    unit: str | None = None
    raw_text: str | None = None


class JobRecord(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str = ''
    title: str = Field(min_length=2, max_length=200)
    url: str
    source: str
    company: str | None = None
    location: str | None = None
    posted_date: str | None = None
    checked_at: str | None = None
    status: str = 'unknown'
    status_evidence: str = 'Source does not establish current vacancy status.'
    description: str | None = None
    salary: str | None = None
    compensation: Compensation | None = None
    contract: str | None = None
    experience: str | None = None
    skills: list[str] = Field(default_factory=list)


def normalized_location(value):
    parts=[re.sub(r'\s+',' ',part).strip() for part in re.split(r'[,،/]',value) if part.strip()]
    return '، '.join(dict.fromkeys(parts)) or None


def normalize_jobs(rows, source, checked_at):
    """Quarantine malformed rows; preserve valid siblings and stable identities."""
    jobs = []; rejected = 0; seen = set()
    for row in rows[:500]:
        try:
            item = dict(row)
            parsed = urlsplit(item.get('url') or '')
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Unsafe listing URL')
            canonical = canonical_public_url(item.get('url'))
            item['url'] = canonical
            item['source'] = source['id']
            item['checked_at'] = checked_at
            if isinstance(item.get('location'),str):
                raw_location=item['location']
                item['location']=normalized_location(raw_location)
                item['location_text']=raw_location
            item['title'] = re.sub(r'\s+', ' ', item.get('title') or '').strip()
            if item.get('posted_date'):
                try:
                    value = str(item['posted_date'])[:10]
                    item['posted_date'] = date.fromisoformat(value).isoformat()
                except ValueError:
                    item['posted_date'] = None
            item['id'] = sha256((source['id'] + ':' + canonical).encode()).hexdigest()[:24]
            record = JobRecord.model_validate(item).model_dump()
            if record['id'] not in seen:
                seen.add(record['id']); jobs.append(record)
        except (ValidationError, ValueError, TypeError, AttributeError):
            rejected += 1
    return jobs, rejected


class SourceMaintenance(ValueError):
    pass


class SourceAccessRestricted(ValueError):
    pass


def source_failure(exc):
    """Machine-readable cause, safe for UI and monitoring without raw responses."""
    import httpx
    if isinstance(exc, SourceMaintenance): return 'source_maintenance',None
    if isinstance(exc, SourceAccessRestricted): return 'blocked',None
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return ('rate_limited' if status == 429 else 'blocked' if status in (401,403) else 'not_found' if status in (404,410) else 'http_error'), status
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return 'timeout', None
    if isinstance(exc, httpx.ConnectError):
        return 'connection_failed', None
    return 'schema_changed', None
