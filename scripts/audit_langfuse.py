"""Read source failures from the repository's configured project without a CLI."""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from spieljobs.tracing import get_trace_client
from spieljobs.langfuse_api import observation_rows, observation_io


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--hours',type=int,default=4)
    parser.add_argument('--output')
    args=parser.parse_args()
    if not 1<=args.hours<=336: parser.error('--hours must be between 1 and 336')
    client=get_trace_client()
    if client is None: sys.exit('No configured Langfuse client.')
    end=datetime.now(timezone.utc); start=end-timedelta(hours=args.hours)
    counts=Counter()
    try:
        projects=client.api.projects.get()
        for level in ('WARNING','ERROR'):
            for row in observation_rows(client,start=start,end=end,level=level):
                if not row.name.startswith('spieljobs.source.'): continue
                output=observation_io(row.output)
                output=output if isinstance(output,dict) else {}
                counts[(row.name.removeprefix('spieljobs.source.'),output.get('failure_kind') or output.get('state'),output.get('http_status'))]+=1
        result={'projects':[{'id':p.id,'name':p.name} for p in projects.data],
            'from':start.isoformat(),'to':end.isoformat(),
            'source_failures':[{'source':key[0],'cause':key[1],'http_status':key[2],'observations':count}
                for key,count in counts.most_common()]}
        encoded=json.dumps(result,ensure_ascii=False,indent=2)
        if args.output: Path(args.output).write_text(encoded)
        print(encoded)
    finally: client.shutdown()


if __name__=='__main__': main()
