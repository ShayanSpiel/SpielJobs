"""Real HTTP/MCP and Langfuse checks; synthetic input, no user resume."""
import asyncio
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from spieljobs.tracing import get_trace_client
from spieljobs.langfuse_api import observation_rows,trace_summary

async def main():
    started=datetime.now(timezone.utc)-timedelta(seconds=5)
    async with httpx.AsyncClient(timeout=115,trust_env=False) as web:
        health=(await web.get('http://127.0.0.1:8000/health')).json()
        print('Health:',json.dumps(health),flush=True)
        async with streamable_http_client('http://127.0.0.1:8000/mcp') as (read,write,_):
            async with ClientSession(read,write) as session:
                await session.initialize()
                tools=await session.list_tools()
                print('MCP tools:',[t.name for t in tools.tools],flush=True)
                result=await session.call_tool('search_live_jobs',{'query':'حسابدار در لندن','session_id':'release-mcp-check'})
                print('MCP tool call:', 'error' if result.isError else 'completed',flush=True)
        response=await web.post('http://127.0.0.1:8000/search',json={'query':'حسابدار مسلط به اکسل در تهران','session_id':'release-v4-session','resume':'Synthetic candidate: accountant with Excel and bookkeeping experience.'})
        response.raise_for_status(); state=response.json()
        print('Search results:',len(state.get('jobs',[])),'model:',state.get('model_used'),'trace:',state.get('trace_id'),flush=True)
    client=get_trace_client()
    try:
        if client is None:raise RuntimeError('No Langfuse client')
        await asyncio.sleep(3)
        rows=list(observation_rows(client,start=started,end=datetime.now(timezone.utc)+timedelta(seconds=1),trace_id=state['trace_id']))
        summary=trace_summary(rows,state['trace_id'])
        summary['sessions']=[{'id':row.id,'name':row.name,'type':str(row.type),'session_id':getattr(row,'session_id',None),'cost':str(row.total_cost) if row.total_cost is not None else None} for row in rows]
        scores=client.api.scores.get_many(trace_id=state['trace_id'],limit=100)
        summary['scores']=[{'name':s.name,'observation_id':getattr(s,'observation_id',None),'value':s.value} for s in scores.data]
        summary['health']=health
        Path('/tmp/spieljobs-v4-release-verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
        print('Observed:',len(rows),'scores:',len(scores.data),'generations:',sum(str(r.type).upper()=='GENERATION' for r in rows),flush=True)
        print('Sessions:',sorted({str(getattr(r,'session_id',None)) for r in rows}),flush=True)
    finally:
        if client:client.shutdown()

if __name__=='__main__':asyncio.run(main())
