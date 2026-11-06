"""Keep the standalone upstream UI and native patch copies in sync."""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OpenWrtSourcesTests(unittest.TestCase):
    def test_standalone_luci_preserves_the_mit_notice(self):
        notice = ROOT / 'openwrt/luci-app-flint2-telemetry/root/usr/share/licenses/luci-app-flint2-telemetry/LICENSE'
        self.assertEqual((ROOT / 'LICENSE').read_bytes(), notice.read_bytes())

    @unittest.skipUnless((ROOT / '.git').exists(), 'Source-pin comparison requires a git checkout')
    def test_pinned_backend_source_contains_the_tested_runtime(self):
        recipe = (ROOT / 'openwrt/flint2-telemetry/Makefile').read_text()
        commit = re.search(r'^FLINT2_SOURCE_VERSION:=([a-f0-9]{40})$', recipe, re.M).group(1)
        result = subprocess.run(
            ['git', 'diff', '--exit-code', commit, '--', 'LICENSE', 'package/files'],
            cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0,
                         'Backend source pin differs from the tested runtime; update its commit/hash '
                         'or fetch the pinned commit before running tests')

    def test_standalone_luci_sources_match_tested_ui(self):
        pairs = [
            ('www/luci-static/resources/view/flint2', 'htdocs/luci-static/resources/view/flint2'),
            ('usr/share/luci/menu.d', 'root/usr/share/luci/menu.d'),
            ('usr/share/rpcd/acl.d', 'root/usr/share/rpcd/acl.d'),
        ]
        for source, target in pairs:
            directory = ROOT / 'package/files' / source
            copied = ROOT / 'openwrt/luci-app-flint2-telemetry' / target
            self.assertEqual(sorted(p.name for p in directory.iterdir()),
                             sorted(p.name for p in copied.iterdir()))
            for path in directory.iterdir():
                self.assertEqual(path.read_bytes(), (copied / path.name).read_bytes())

    def test_standalone_capture_patches_match_vendor_build(self):
        source = ROOT / 'vendor/patches'
        target = ROOT / 'openwrt/flint2-capture/patches'
        self.assertEqual(sorted(p.name for p in source.glob('*.patch')) +
                         ['0003-reproducible-build-description.patch'],
                         sorted(p.name for p in target.glob('*.patch')))
        for path in source.glob('*.patch'):
            self.assertEqual(path.read_bytes(), (target / path.name).read_bytes())


if __name__ == '__main__':
    unittest.main()
