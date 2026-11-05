"""Check the public artifact's references, scoping and portable data contract."""
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'integrations/graylog/flint2-dashboards.json'


class ContentPackTests(unittest.TestCase):
    def setUp(self):
        self.text = PACK.read_text()
        self.pack = json.loads(self.text)
        self.entities = self.pack['entities']
        self.stream = next(e for e in self.entities if e['type']['name'] == 'stream')
        self.dashboards = [e['data'] for e in self.entities if e['type']['name'] == 'dashboard']

    def test_download_checksum_matches_the_artifact(self):
        expected = PACK.with_suffix('.json.sha256').read_text().strip()
        self.assertEqual(expected, hashlib.sha256(PACK.read_bytes()).hexdigest() + '  ' + PACK.name)

    def test_ten_complete_dashboards_with_consistent_widget_and_search_ids(self):
        self.assertEqual(len(self.dashboards), 10)
        count = 0
        for dashboard in self.dashboards:
            queries = {q['id']: q for q in dashboard['search']['queries']}
            self.assertEqual(set(dashboard['state']), set(queries))
            for query_id, state in dashboard['state'].items():
                widgets = {w['id']: w for w in state['widgets']}
                search_types = {s['id']: s for s in queries[query_id]['search_types']}
                self.assertEqual(set(widgets), set(state['widget_mapping']))
                self.assertEqual(set(widgets), set(state['positions']))
                self.assertEqual(set(widgets), set(state['titles']['widget']))
                for widget_id, mapped in state['widget_mapping'].items():
                    self.assertTrue(mapped)
                    for search_id in mapped:
                        self.assertIn(search_id, search_types)
                        self.assertEqual(widgets[widget_id]['query'], search_types[search_id]['query'])
                count += len(widgets)
        self.assertEqual(count, 183)

    def test_explicit_input_scope_and_internal_stream_references(self):
        data = self.stream['data']
        self.assertEqual(data['matching_type']['@value'], 'AND')
        self.assertFalse(data['remove_matches']['@value'])
        rules = {r['field']['@value']: r for r in data['stream_rules']}
        self.assertEqual(rules['event_module']['value']['@value'], 'flint2')
        self.assertEqual(rules['gl2_source_input']['value'],
                         {'@type': 'parameter', '@value': 'FLINT2_INPUT_ID'})
        self.assertEqual(self.pack['parameters'][0]['default_value'], 'SET_YOUR_GELF_INPUT_ID')
        for dashboard in self.dashboards:
            for query in dashboard['search']['queries']:
                self.assertEqual(query['filter'], {'type': 'and', 'filters': [
                    {'type': 'stream', 'id': self.stream['id']}]})
                for search in query['search_types']:
                    self.assertEqual(search['streams'], [self.stream['id']])
                for state in dashboard['state'].values():
                    for widget in state['widgets']:
                        self.assertEqual(widget['streams'], [self.stream['id']])
        pipeline = next(e['data'] for e in self.entities if e['type']['name'] == 'pipeline')
        self.assertEqual(pipeline['connected_streams'], [{'@type': 'string', '@value': self.stream['id']}])

    def test_no_site_entities_lookups_or_legacy_field_dependencies(self):
        self.assertEqual({e['type']['name'] for e in self.entities},
                         {'dashboard', 'stream', 'pipeline', 'pipeline_rule'})
        self.assertEqual(len({e['id'] for e in self.entities}), len(self.entities))
        self.assertNotRegex(self.text, r'\b[0-9a-f]{24}\b')
        self.assertNotIn('owner', self.text)
        self.assertNotIn('index_set_id', self.text)
        self.assertNotIn('pppoe-wan', self.text)
        self.assertNotIn('lookup_value(', self.text)
        self.assertNotIn('PRIVATE KEY', self.text)
        addresses = set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d+)?', self.text))
        self.assertEqual(addresses, {'10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'})
        for legacy in ['flow_bytes', 'flow_mb', 'flow_wan_side', 'lan_direction', 'fw_action', 'vpn_peer']:
            self.assertNotRegex(self.text, r'\b' + legacy + r'\b')

    def test_enrichment_writes_only_backend_fields_and_guards_module(self):
        rules = [e['data']['source']['@value'] for e in self.entities if e['type']['name'] == 'pipeline_rule']
        self.assertEqual(len(rules), 16)
        for source in rules:
            self.assertIn('to_string($message.event_module) == "flint2"', source)
            destinations = re.findall(r'set_field\("([^"]+)"', source)
            self.assertTrue(destinations)
            self.assertTrue(all(f.startswith('flint2_dashboard_') for f in destinations))
            self.assertNotIn('route_to_stream', source)
            self.assertNotIn('remove_field', source)
