import hashlib
import importlib.util
import io
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_ipk', ROOT / 'scripts/build-ipk.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / 'package', self.root / 'package',
                        ignore=shutil.ignore_patterns('flint2-capture', '*.crt'))
        shutil.copy(ROOT / 'LICENSE', self.root / 'LICENSE')
        # Packaging fixture only: this is not an executable or a releasable asset.
        header = bytearray(64)
        header[:4] = b'\x7fELF'
        header[18:20] = (183).to_bytes(2, 'little')
        (self.root / 'package/files/usr/sbin/flint2-capture').write_bytes(header)
        self.patch = patch.object(builder, 'ROOT', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def archives(self, **kwargs):
        builder.build(**kwargs)
        path = next((self.root / 'dist').glob('*.ipk'))
        raw = path.read_bytes()
        outer = tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz')
        self.addCleanup(outer.close)
        result = []
        for name in ['data', 'control']:
            archive = tarfile.open(fileobj=io.BytesIO(outer.extractfile('./' + name + '.tar.gz').read()), mode='r:gz')
            self.addCleanup(archive.close)
            result.append(archive)
        return path, raw, *result

    def test_reproducible_package_and_safe_public_defaults(self):
        path, first, data, controls = self.archives()
        builder.build()
        self.assertEqual(first, path.read_bytes())
        self.assertIn(hashlib.sha256(first).hexdigest(), path.with_suffix('.ipk.sha256').read_text())
        self.assertNotIn('./etc/config/system', data.getnames())
        self.assertNotIn('./etc/config/firewall', data.getnames())
        self.assertNotIn('./etc/flint2/collector.crt', data.getnames())
        self.assertIn(b"option enabled '0'", data.extractfile('./etc/config/flint2').read())
        self.assertIn(b"option format 'otlp_http_json'", data.extractfile('./etc/config/flint2').read())
        for name in ['./etc/init.d/flint2', './usr/libexec/flint2/firewall-events']:
            self.assertEqual(data.getmember(name).mode, 0o755)
        for member in data:
            self.assertNotIn('..', Path(member.name).parts)
            self.assertEqual(member.uid, 0)
            for parent in Path(member.name).parents:
                if str(parent) != '.':
                    self.assertTrue(data.getmember('./' + str(parent)).isdir())
        self.assertEqual(controls.extractfile('./conffiles').read(), b'/etc/config/flint2\n')

    def test_private_site_profile_is_explicit_and_rejects_private_keys(self):
        site = self.root / 'site.config'
        site.write_text("config agent 'main'\n option enabled '1'\n")
        cert = self.root / 'ca.pem'
        cert.write_text('-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n')
        _, _, data, controls = self.archives(site_config=site, ca_file=cert)
        self.assertEqual(data.getmember('./etc/config/flint2').mode, 0o600)
        self.assertEqual(data.extractfile('./etc/config/flint2').read(), site.read_bytes())
        self.assertIn(b'/etc/flint2/collector.crt', controls.extractfile('./conffiles').read())
        cert.write_text('-----BEGIN PRIVATE KEY-----')
        with self.assertRaises(RuntimeError):
            builder.build(ca_file=cert)

    def test_requires_architecture_matching_capture_binary(self):
        binary = self.root / 'package/files/usr/sbin/flint2-capture'
        binary.write_bytes(b'wrong architecture')
        with self.assertRaises(RuntimeError):
            builder.build()
        binary.unlink()
        with self.assertRaises(RuntimeError):
            builder.build()


if __name__ == '__main__':
    unittest.main()
