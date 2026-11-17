"""Bounded observations-first reads for Langfuse v4 / Python SDK v5."""
import json
from datetime import timedelta
from decimal import Decimal

OBSERVATION_FIELDS='core,basic,time,io,metadata,usage,trace_context'


def observation_rows(client, *, start, end, fields=OBSERVATION_FIELDS, **filters):
    if start.tzinfo is None or end.tzinfo is None or not timedelta(0)<end-start<=timedelta(days=14):
        raise ValueError('Observation reads need an explicit timezone and a window of at most 14 days')
    cursor=None; seen=set()
    while True:
        page=client.api.observations.get_many(from_start_time=start,to_start_time=end,
            fields=fields,limit=100,**filters,**({'cursor':cursor} if cursor else {}))
        yield from page.data
        cursor=getattr(page.meta,'cursor',None)
        if not cursor: return
        if cursor in seen: raise RuntimeError('Langfuse returned a repeated pagination cursor')
        seen.add(cursor)


def observation_io(value):
    """v2 I/O is a raw string; plain text stays text, JSON is decoded locally."""
    if isinstance(value,str):
        try: return json.loads(value)
        except ValueError: pass
    return value


def trace_summary(rows, trace_id):
    selected=[row for row in rows if row.trace_id==trace_id]
    roots=[row for row in selected if row.parent_observation_id is None]
    root=next((row for row in roots if row.name=='spieljobs.search'),roots[0] if roots else None)
    costs=[Decimal(str(row.total_cost)) for row in selected if getattr(row,'total_cost',None) is not None]
    return {'trace_id':trace_id,'observation_count':len(selected),
        'root_id':root.id if root else None,
        'input':observation_io(root.input) if root else None,
        'output':observation_io(root.output) if root else None,
        'known_cost':str(sum(costs,Decimal(0))) if costs else None,
        'generations_without_cost':[row.id for row in selected
            if str(row.type).upper()=='GENERATION' and getattr(row,'total_cost',None) is None]}
