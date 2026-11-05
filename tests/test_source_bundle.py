import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bundle', ROOT / 'scripts/bundle-sources.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SourceBundleTests(unittest.TestCase):
    def test_public_allowlist_excludes_site_material_and_binary_assets(self):
        names = [p.relative_to(ROOT).as_posix() for p in module.public_files(ROOT)]
        self.assertIn('scripts/build-capture.sh', names)
        self.assertIn('feed/keys/flint2-telemetry.pub', names)
        self.assertIn('integrations/graylog/flint2-dashboards.json', names)
        self.assertIn('vendor/patches/0001-nfprobe-ring-publication.patch', names)
        self.assertIn('package/files/usr/share/licenses/flint2-capture/THIRD-PARTY-LICENSES', names)
        for name in names:
            self.assertFalse(name.startswith(('local/', 'dist/')))
            self.assertNotIn('__pycache__', name)
            self.assertNotEqual(name, 'package/files/usr/sbin/flint2-capture')
            self.assertNotIn(Path(name).suffix, {'.crt', '.pem', '.key', '.pyc'})

    def test_rejects_wrong_upstream_source_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            (cache / 'pmacct-1.7.9.tar.gz').write_bytes(b'incorrect source')
            output = cache / 'release.tar.gz'
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                module.bundle(cache, output)
            self.assertFalse(output.exists())
