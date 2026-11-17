"""v4 reads must paginate, decode I/O and preserve missing cost evidence."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import Mock
from spieljobs.langfuse_api import observation_rows, observation_io, trace_summary

class ObservationReadTests(unittest.TestCase):
    def setUp(self):
        self.end=datetime.now(timezone.utc); self.start=self.end-timedelta(hours=1)
        self.client=NS(api=NS(observations=NS(get_many=Mock())))

    def test_cursor_pagination_and_bounded_usage_fields(self):
        get=self.client.api.observations.get_many
        get.side_effect=[NS(data=[1],meta=NS(cursor='next')),NS(data=[2],meta=NS(cursor=None))]
        self.assertEqual(list(observation_rows(self.client,start=self.start,end=self.end)),[1,2])
        self.assertEqual(get.call_args.kwargs['cursor'],'next')
        self.assertIn('usage',get.call_args.kwargs['fields'].split(','))
        with self.assertRaises(ValueError):list(observation_rows(self.client,start=self.end-timedelta(days=15),end=self.end))
        with self.assertRaises(ValueError):list(observation_rows(self.client,start=self.start.replace(tzinfo=None),end=self.end))

    def test_repeated_cursor_is_an_error(self):
        self.client.api.observations.get_many.return_value=NS(data=[],meta=NS(cursor='loop'))
        with self.assertRaises(RuntimeError):list(observation_rows(self.client,start=self.start,end=self.end))

    def test_raw_io_and_missing_cost_are_not_zero(self):
        self.assertEqual(observation_io('{"jobs":[]}'),{'jobs':[]})
        self.assertEqual(observation_io('plain text'),'plain text')
        row=NS(id='root',trace_id='t',parent_observation_id=None,name='spieljobs.search',type='GENERATION',total_cost=None,input='{"request":"test"}',output='{"jobs":[]}')
        result=trace_summary([row],'t')
        self.assertIsNone(result['known_cost'])
        self.assertEqual(result['generations_without_cost'],['root'])
        self.assertEqual(result['output'],{'jobs':[]})
