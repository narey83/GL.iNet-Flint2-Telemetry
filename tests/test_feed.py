import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('feed', ROOT / 'scripts/publish-feed.py')
feed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feed)
USIGN = os.environ.get('FLINT2_TEST_USIGN')


class FeedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def test_advertised_dashboards_match_the_actual_content_pack(self):
        capabilities = json.loads((ROOT / 'feed/dashboard-capabilities.json').read_text())
        pack = json.loads((ROOT / 'integrations/graylog/flint2-dashboards.json').read_text())
        actual = {e['data']['title']['@value'].removeprefix('Flint2 · '):
                  sum(len(p['widgets']) for p in e['data']['state'].values())
                  for e in pack['entities'] if e['type']['name'] == 'dashboard'}
        self.assertEqual({d['name']: d['widgets'] for d in capabilities}, actual)
        self.assertEqual(sum(d['widgets'] for d in capabilities), 183)
        for d in capabilities:
            self.assertTrue(d['capability'])
            self.assertIn('| ' + d['name'] + ' |', (ROOT / 'README.md').read_text())

    def test_landing_page_renders_dashboard_capabilities_and_links(self):
        setup, _ = feed.bootstrap(self.directory, ROOT / 'feed/keys/flint2-telemetry.pub')
        page = feed.render_landing({'version': '0.3.1-6'}, setup, ROOT / 'feed/keys/flint2-telemetry.pub')
        self.assertEqual(page.count('<tr><th>'), 11)  # Header and ten dashboard rows.
        for d in json.loads((ROOT / 'feed/dashboard-capabilities.json').read_text()):
            import html
            self.assertIn(html.escape(d['name']), page)
            self.assertIn(html.escape(d['capability']), page)
        self.assertNotIn("' +", page)
        self.assertIn('https://github.com/' + feed.REPO + '/blob/main/docs/integrations/GRAYLOG.md', page)
        self.assertIn('not WireGuard handshakes', page)
        self.assertIn(feed.LABEL, page)

    def test_index_has_real_size_hash_and_qualified_description(self):
        path = self.directory / 'package.ipk'
        path.write_bytes(b'package bytes')
        fields = {'Package': 'flint2-telemetry', 'Version': '0.3.1-6',
                  'Architecture': feed.ARCH, 'Description': 'Generic'}
        entry = feed.control_fields(feed.index_entry(path, fields).strip().encode())
        self.assertEqual(entry['Filename'], path.name)
        self.assertEqual(entry['Size'], str(path.stat().st_size))
        self.assertEqual(entry['SHA256sum'], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertIn('GL-MT6000 vendor OpenWrt 21.02', entry['Description'])
        self.assertEqual(fields['Description'], 'Generic')

    def test_legacy_signature_padding_and_compression(self):
        for length in range(256):
            data = feed.pad_index(b'A' * length)
            self.assertNotIn((64 + len(data)) % 128, (110, 111))
            self.assertTrue(data.startswith(b'A' * length))
            self.assertEqual(gzip.decompress(gzip.compress(data, mtime=0)), data)

    def test_rejects_injected_or_duplicate_control_fields(self):
        for raw in [b'Package: x\nPackage: y\n', b'Package: x\nInjected\n', b'Version: 1\n']:
            with self.assertRaises(ValueError):
                feed.control_fields(raw)

    def test_bootstrap_contains_only_public_trust_and_its_own_feed(self):
        path, fields = feed.bootstrap(self.directory, ROOT / 'feed/keys/flint2-telemetry.pub')
        self.assertEqual(fields['Package'], 'flint2-telemetry-feed')
        self.assertEqual(fields['Architecture'], feed.ARCH)
        _, payload = feed.read_package(path)
        self.assertEqual(set(payload), {'etc/opkg/flint2-telemetry.conf',
                         'etc/opkg/keys/' + feed.KEY_ID,
                         'usr/share/licenses/flint2-telemetry-feed/LICENSE'})
        self.assertEqual(payload['etc/opkg/flint2-telemetry.conf'].decode(),
                         f'src/gz {feed.FEED_NAME} {feed.BASE_URL}/{feed.LANE}\n')
        self.assertNotIn('check_signature', payload['etc/opkg/flint2-telemetry.conf'].decode())
        with tarfile.open(path) as outer:
            with tarfile.open(fileobj=io.BytesIO(outer.extractfile('./control.tar.gz').read())) as control:
                preinst = control.extractfile('./preinst').read()
                self.assertIn(b'glinet,gl-mt6000', preinst)
                self.assertIn(b'DISTRIB_RELEASE', preinst)
                self.assertIn(b'command -v fw3', preinst)
        self.assertNotIn(b'PRIVATE KEY', path.read_bytes())

    def fixture_release(self):
        archive = runpy.run_path(str(ROOT / 'scripts/build-ipk.py'))['archive']
        native = bytearray(65536)
        native[:6] = b'\x7fELF\x02\x01'
        native[18:20] = (183).to_bytes(2, 'little')
        defaults = (ROOT / 'package/files/etc/config/flint2').read_bytes()
        package = self.directory / f'flint2-telemetry_0.3.1-6_{feed.ARCH}.ipk'
        control = b'Package: flint2-telemetry\nVersion: 0.3.1-6\nArchitecture: aarch64_cortex-a53\nDescription: Fixture only\n'
        package.write_bytes(archive([('control.tar.gz', archive([('control', control, 0o644)]), 0o644),
                           ('data.tar.gz', archive([('etc/config/flint2', defaults, 0o644),
                            ('usr/sbin/flint2-capture', bytes(native), 0o755)]), 0o644)]))
        source = self.directory / 'flint2-telemetry_0.3.1-6-sources.tar.gz'
        source.write_bytes(archive([('source/' + name, b'fixture', 0o644) for name in [
            'third-party/pmacct-1.7.9.tar.gz', 'third-party/libpcap-1.11.0.tar.gz',
            'vendor/patches/0001-nfprobe-ring-publication.patch']]))
        info = {'version': '0.3.1-6', 'tag': 'v0.3.1-6', 'architecture': feed.ARCH,
                'firmware_abi': feed.ABI, 'site_profile_included': False,
                'native_capture_built': True, 'commit': 'a' * 40,
                'capture_sha256': hashlib.sha256(native).hexdigest()}
        metadata = self.directory / 'BUILD-INFO.json'
        def save():
            metadata.write_text(json.dumps(info))
            (self.directory / 'SHA256SUMS').write_text(''.join(feed.digest(p) + '  ' + p.name + '\n'
                                                    for p in [package, source, metadata]))
        save()
        return defaults, package, info, save

    def test_release_rejects_wrong_abi_site_profile_and_missing_sources(self):
        defaults, package, info, save = self.fixture_release()
        release = {'tag_name': 'v0.3.1-6', 'draft': False, 'prerelease': False}
        feed.validate_release(self.directory, release, defaults)
        for key, wrong in [('firmware_abi', 'OpenWrt fw4'), ('architecture', 'x86_64'),
                           ('site_profile_included', True), ('native_capture_built', False)]:
            original = info[key]
            info[key] = wrong
            save()
            with self.assertRaisesRegex(ValueError, 'qualified feed target'):
                feed.validate_release(self.directory, release, defaults)
            info[key] = original
        save()
        with self.assertRaisesRegex(ValueError, 'site profile'):
            feed.validate_release(self.directory, release, b'other defaults')
        source = self.directory / 'flint2-telemetry_0.3.1-6-sources.tar.gz'
        archive = runpy.run_path(str(ROOT / 'scripts/build-ipk.py'))['archive']
        good_source = source.read_bytes()
        source.write_bytes(archive([('LICENSE', b'fixture', 0o644)]))
        save()
        with self.assertRaisesRegex(ValueError, 'Incomplete corresponding sources'):
            feed.validate_release(self.directory, release, defaults)
        source.write_bytes(good_source)
        save()
        package.write_bytes(package.read_bytes() + b'tampered')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            feed.validate_release(self.directory, release, defaults)
        with self.assertRaisesRegex(ValueError, 'stable version'):
            feed.validate_release(self.directory, dict(release, prerelease=True), defaults)

    @unittest.skipUnless(USIGN, 'Set FLINT2_TEST_USIGN to run native signature checks')
    def test_real_signature_and_tampering_rejection(self):
        secret, public = self.directory / 'test.key', self.directory / 'test.pub'
        subprocess.run([USIGN, '-G', '-s', str(secret), '-p', str(public)], check=True)
        message, signature = self.directory / 'Packages', self.directory / 'Packages.sig'
        message.write_bytes(feed.pad_index(b'Package: test\nVersion: 1\n\n'))
        subprocess.run([USIGN, '-S', '-s', str(secret), '-m', str(message), '-x', str(signature)], check=True)
        command = [USIGN, '-V', '-q', '-p', str(public), '-m', str(message), '-x', str(signature)]
        subprocess.run(command, check=True)
        message.write_bytes(message.read_bytes() + b'tampered')
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
