"""Exercise the public protocol with the same ASGI app used in deployment."""
import unittest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from spieljobs.server import app

class RemoteMcpTests(unittest.TestCase):
    def test_initialize_list_and_search_tool(self):
        headers={'Accept':'application/json, text/event-stream','Content-Type':'application/json'}
        expected={'jobs':[{'title':'کارشناس پشتیبانی','url':'https://example.org/job/1'}],'sources':[]}
        with patch('spieljobs.mcp_server.search_jobs',new=AsyncMock(return_value=expected)) as search, TestClient(app) as client:
            init=client.post('/mcp',headers=headers,json={'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'test','version':'1'}}})
            self.assertEqual(init.status_code,200)
            listed=client.post('/mcp',headers=headers,json={'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}})
            self.assertEqual(listed.status_code,200)
            self.assertIn('search_live_jobs',[tool['name'] for tool in listed.json()['result']['tools']])
            result=client.post('/mcp',headers=headers,json={'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'search_live_jobs','arguments':{'query':'کارشناس پشتیبانی'}}})
            self.assertEqual(result.status_code,200)
            self.assertIn('کارشناس پشتیبانی',result.text)
            search.assert_awaited_once_with('کارشناس پشتیبانی','',channel='mcp',session_id=None)
