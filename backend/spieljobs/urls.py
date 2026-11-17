"""Public listing identity: retain functional IDs, remove tracking parameters."""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING={'_ref','_t','tracking','tracking_id','gclid','fbclid','yclid','msclkid'}

def canonical_public_url(value):
    try:
        parsed=urlsplit(value or '')
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:
            return ''
        query=urlencode(sorted((key,val) for key,val in parse_qsl(parsed.query,keep_blank_values=True) if key.lower() not in _TRACKING and not key.lower().startswith('utm_')))
        return urlunsplit((parsed.scheme.lower(),parsed.netloc.lower(),parsed.path.rstrip('/') or '/',query,''))
    except (ValueError,TypeError):return ''
