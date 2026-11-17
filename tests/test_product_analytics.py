import unittest
from unittest.mock import AsyncMock, patch
from spieljobs import analytics

class ProductAnalyticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_events_link_to_browser_without_private_search_text(self):
        client=type('Client',(),{'capture_immediate':AsyncMock()})()
        state={'run_id':'run-1','query':'private query','resume':'private resume','jobs':[{'description':'private detail'}],'sources':[{'state':'partial'}],'runtime':{'duration_ms':150}}
        with patch.dict('os.environ',{'POSTHOG_PROJECT_TOKEN':'test','POSTHOG_HOST':'https://us.i.posthog.com'}),patch.object(analytics,'_client',client):
            with analytics.analytics_context({'x-posthog-distinct-id':'visitor-1','x-posthog-session-id':'session-1'}):
                await analytics.record_search(state,'web_stream')
        args=client.capture_immediate.call_args.kwargs
        self.assertEqual(args['distinct_id'],'visitor-1')
        self.assertEqual(args['properties']['$session_id'],'session-1')
        self.assertNotIn('private',str(args))
        self.assertEqual(args['properties']['result_count'],1)

    async def test_delivery_failure_does_not_break_search(self):
        client=type('Client',(),{'capture_immediate':AsyncMock(side_effect=OSError())})()
        with patch.dict('os.environ',{'POSTHOG_PROJECT_TOKEN':'test','POSTHOG_HOST':'https://us.i.posthog.com'}),patch.object(analytics,'_client',client):
            await analytics.record_search({'run_id':'run-1'},'mcp')
