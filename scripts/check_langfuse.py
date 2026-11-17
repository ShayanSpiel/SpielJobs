"""Send a synthetic observation and read it through the v4 observations API."""
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from spieljobs.tracing import get_trace_client, trace_scope
from spieljobs.langfuse_api import observation_rows
client=get_trace_client()
if client is None: sys.exit('Langfuse is disabled, unconfigured, or could not initialize.')
try:
    if not client.auth_check(): sys.exit('Langfuse authentication failed.')
    print('Langfuse authentication succeeded.')
    started=datetime.now(timezone.utc)-timedelta(seconds=5)
    with trace_scope(session_id='spieljobs-connection-check',channel='verification',trace_name='spieljobs.connection_check'):
        with client.start_as_current_observation(name='spieljobs.connection_check',as_type='span',input={'synthetic':True}) as span:
            trace_id=client.get_current_trace_id()
            span.update(output={'synthetic':True,'completed':True})
    client.flush()
    for _ in range(20):
        rows=list(observation_rows(client,start=started,end=datetime.now(timezone.utc)+timedelta(seconds=1),trace_id=trace_id))
        if rows:
            print('Trace was sent and read back:',trace_id)
            break
        time.sleep(2)
    else: sys.exit('Authentication succeeded, but observation ingestion could not be verified.')
except Exception as exc:
    sys.exit(f'Langfuse verification failed: {type(exc).__name__}.')
finally:
    client.shutdown()
