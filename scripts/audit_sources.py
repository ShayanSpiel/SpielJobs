"""Run from the actual hosting region; output observable adapter health as JSON.

A parsed vacancy is not proof of complete recall. No private user input is used.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
os.environ['SPIELJOBS_TRACING_ENABLED'] = 'false'
from spieljobs.sources import collect
from spieljobs.models import extract_profile


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='/tmp/spieljobs-source-audit.json')
    args = parser.parse_args()
    jobs, sources = await collect(['product manager'])
    diagnostics = {}
    terms, model = await extract_profile('I have experience in product management and AI. What roles fit?', '', diagnostics)
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'environment': 'vercel' if os.getenv('VERCEL') else 'local',
              'query': 'product manager', 'candidate_count': len(jobs), 'sources': sources,
              'model': {'provider_used': model, 'terms': terms, 'diagnostics': diagnostics},
              'limitation': 'Adapter audit only. Requires reviewed relevance labels and comparison with source listings for recall.'}
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2))
    for source in sources:
        print(source['id'], source['state'], source.get('failure_kind',''), source.get('http_status',''))
    print('Candidates:', len(jobs), '| Model:', model or diagnostics.get('reason'), '| Report:', args.output)


if __name__ == '__main__':
    asyncio.run(main())
