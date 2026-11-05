import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('provision', ROOT / 'scripts/provision-graylog.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeGraylog:
    base_url = 'https://graylog.example.invalid'

    def __init__(self):
        self.stream_body = None
        self.index_lookup = False

    def request(self, method, path, body=None):
        if method == 'GET':
            if path == '/system/inputs':
                return {'inputs': []}
            if path == '/streams':
                return {'streams': []}
            if path == '/system/indices/index_sets':
                self.index_lookup = True
                return {'index_sets': [{'id': 'default-index', 'default': True}]}
            if path == '/views':
                return {'views': []}
        if path == '/streams':
            self.stream_body = body
            return {'stream_id': 'stream'}
        if path == '/system/inputs':
            return {'id': 'input'}
        if path == '/views/search':
            return {'id': 'search'}
        if path == '/views':
            return {'id': 'view'}
        if path in ['/streams/stream/rules', '/streams/stream/resume']:
            return {}
        raise AssertionError((method, path))


class ProvisionTests(unittest.TestCase):
    def test_clean_install_uses_default_or_explicit_index_set(self):
        for configured in [None, 'chosen-index']:
            with self.subTest(configured=configured), tempfile.TemporaryDirectory() as directory:
                api = FakeGraylog()
                env = {} if configured is None else {'GRAYLOG_INDEX_SET_ID': configured}
                with patch.object(module, 'ROOT', Path(directory)), patch.dict(module.os.environ, env, clear=True):
                    module.provision(api)
                self.assertEqual(api.stream_body['index_set_id'], configured or 'default-index')
                self.assertEqual(api.index_lookup, configured is None)
                self.assertTrue((Path(directory) / 'dist/graylog-resources.json').is_file())
