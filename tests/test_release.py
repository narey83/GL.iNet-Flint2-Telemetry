import importlib.util
from pathlib import Path
import shutil
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release', ROOT / 'scripts/prepare-release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'scripts').mkdir()
        (self.root / 'package').mkdir()
        shutil.copy(ROOT / 'scripts/build-ipk.py', self.root / 'scripts/build-ipk.py')
        shutil.copy(ROOT / 'package/Makefile', self.root / 'package/Makefile')

    def test_tag_and_package_versions_must_match(self):
        version = release.check_version(self.root)['VERSION']
        self.assertEqual(release.check_version(self.root, 'v' + version)['VERSION'], version)
        for tag in ['v0.0.0-1', 'main', 'v' + version + '-unexpected']:
            with self.assertRaisesRegex(ValueError, 'Release tag must'):
                release.check_version(self.root, tag)

    def test_makefile_and_builder_disagreement_fails(self):
        path = self.root / 'package/Makefile'
        path.write_text(re.sub(r'^PKG_VERSION:=.*$', 'PKG_VERSION:=0.0.0', path.read_text(), flags=re.M))
        with self.assertRaisesRegex(ValueError, 'versions differ'):
            release.check_version(self.root)

    def test_packaging_fixture_is_not_a_release_executable(self):
        path = self.root / 'package/files/usr/sbin/flint2-capture'
        path.parent.mkdir(parents=True)
        header = bytearray(64)
        header[:6] = b'\x7fELF\x02\x01'
        header[18:20] = (183).to_bytes(2, 'little')
        path.write_bytes(header)
        with self.assertRaisesRegex(ValueError, 'compiled ELF64'):
            release.prepare(self.root)
        self.assertFalse((self.root / 'dist/release').exists())
