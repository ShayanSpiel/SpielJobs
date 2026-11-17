"""Bounded first-party careers discovery when an employer's configured URL moves.

No search-engine snippets or invented job data are returned as vacancies.
"""
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup


async def fetch_career_page(client, source, stats):
    async def get(url):
        stats['requests'] += 1
        response = await client.get(url)
        response.raise_for_status()
        return response
    try:
        response = await get(source['url'])
        return response
    except (httpx.ConnectError, httpx.HTTPStatusError) as original:
        if isinstance(original, httpx.HTTPStatusError) and original.response.status_code not in (404,410,502,503):
            raise
        # Only inspect the known employer's own homepage, then one careers link.
        homepage = source.get('site_url')
        if not homepage or homepage.rstrip('/') == source['url'].rstrip('/'):
            raise
        home = await get(homepage)
        soup = BeautifulSoup(home.text, 'html.parser')
        candidates = []
        home_host = urlparse(str(home.url)).hostname or ''
        root = home_host.removeprefix('www.')
        for link in soup.select('a[href]'):
            url = urljoin(str(home.url), link['href'])
            parsed = urlparse(url)
            label = ' '.join(link.get_text(' ', strip=True).lower().replace('\u200c',' ').split())
            # Only a first-party host is followed automatically. External ATS
            # must be explicitly registered and reviewed in source_registry.py.
            if parsed.scheme != 'https' or not parsed.hostname or not (parsed.hostname == root or parsed.hostname.endswith('.' + root)):
                continue
            if any(term in label for term in ('فرصت شغلی','فرصت های شغلی','استخدام','careers','job openings')) or any(term in parsed.path.lower() for term in ('career','jobs','positions')):
                candidates.append(url)
        if not candidates:
            raise original
        return await get(candidates[0])
