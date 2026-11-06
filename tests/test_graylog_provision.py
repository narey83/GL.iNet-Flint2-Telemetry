import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('provision', ROOT / 'scripts/provision-graylog.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeGraylog:
    base_url = 'https://graylog.example.invalid'

    def __init__(self):
        self.stream_body = None
        self.input_body = None
        self.existing_inputs = []
        self.index_lookup = False
        self.rule_body = None
        self.pipeline_body = None
        self.connection_body = None
        self.view_body = None
        self.existing_pipelines = []
        self.existing_connections = []

    def request(self, method, path, body=None):
        if method == 'GET':
            if path == '/system/inputs':
                return {'inputs': self.existing_inputs}
            if path == '/streams':
                return {'streams': []}
            if path == '/system/indices/index_sets':
                self.index_lookup = True
                return {'index_sets': [{'id': 'default-index', 'default': True}]}
            if path == '/views':
                return {'views': []}
            if path == '/system/pipelines/pipeline':
                return self.existing_pipelines
            if path == '/system/pipelines/connections':
                return self.existing_connections
            if path == '/system/pipelines/rule':
                return []
        if path == '/streams':
            self.stream_body = body
            return {'stream_id': 'stream'}
        if path == '/system/inputs':
            self.input_body = body
            return {'id': 'input'}
        if path == '/views/search':
            return {'id': 'search'}
        if path == '/views':
            self.view_body = body
            return {'id': 'view'}
        if path == '/system/pipelines/rule':
            self.rule_body = body
            return {'id': 'rule'}
        if path == '/system/pipelines/pipeline':
            self.pipeline_body = body
            return {'id': 'pipeline'}
        if path == '/system/pipelines/connections/to_stream':
            self.connection_body = body
            return {}
        if path in ['/streams/stream/rules', '/streams/stream/resume']:
            return {}
        raise AssertionError((method, path))


class ProvisionTests(unittest.TestCase):
    def test_api_path_validation_is_not_an_assertion(self):
        api = module.Graylog('dummy', base_url='https://graylog.example.invalid')
        for path in ['relative', '/bad\nheader', '/bad"quote']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                api.request('GET', path)

    def test_mismatched_existing_input_fails(self):
        api = FakeGraylog()
        api.existing_inputs = [{'id': 'wrong', 'title': module.TITLE,
                                'type': 'wrong', 'attributes': {'port': 12201}}]
        with (tempfile.TemporaryDirectory() as directory,
              patch.object(module, 'ROOT', Path(directory)),
              self.assertRaisesRegex(ValueError, 'unexpected type or port')):
            module.provision(api)

    def test_existing_routing_pipeline_is_not_duplicated(self):
        api = FakeGraylog()
        api.existing_pipelines = [{'id': 'routing', 'title': 'Routing',
                                   'source': 'rule "Flint2 interface Mbps display"'}]
        api.existing_connections = [{'stream_id': 'stream', 'pipeline_ids': ['routing']}]
        module.ensure_mbps_pipeline(api, 'stream')
        self.assertIsNotNone(api.rule_body)
        self.assertIsNone(api.pipeline_body)
        self.assertIsNone(api.connection_body)

    def test_clean_install_uses_default_or_explicit_index_set(self):
        for configured in [None, 'chosen-index']:
            with self.subTest(configured=configured), tempfile.TemporaryDirectory() as directory:
                api = FakeGraylog()
                env = {} if configured is None else {'GRAYLOG_INDEX_SET_ID': configured}
                with patch.object(module, 'ROOT', Path(directory)), patch.dict(module.os.environ, env, clear=True):
                    module.provision(api)
                self.assertEqual(api.stream_body['index_set_id'], configured or 'default-index')
                self.assertEqual(api.input_body['configuration']['bind_address'], '127.0.0.1')
                self.assertEqual(api.index_lookup, configured is None)
                self.assertTrue((Path(directory) / 'dist/graylog-resources.json').is_file())
                self.assertIn('/ 1000000.0', api.rule_body['source'])
                self.assertEqual(api.connection_body, {'stream_id': 'stream', 'pipeline_ids': ['pipeline']})
                state = next(iter(api.view_body['state'].values()))
                rate_widgets = [w for w in state['widgets'] if any('mbps' in s['function']
                                for s in w.get('config', {}).get('series', []))]
                self.assertEqual(len(rate_widgets), 2)
                self.assertIn('WAN traffic · 24 hours (Mbps)', state['titles']['widget'].values())
