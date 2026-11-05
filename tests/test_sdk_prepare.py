import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sdk_prepare', ROOT / 'scripts/prepare-openwrt-sdk.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SdkPrepareTests(unittest.TestCase):
    def test_normalizes_known_generator_once_and_preserves_other_text(self):
        with tempfile.TemporaryDirectory() as directory:
            sdk = Path(directory)
            (sdk / 'scripts').mkdir()
            path = sdk / 'scripts/package-metadata.pl'
            path.write_text('before\n' + module.BEFORE + 'after\n')
            module.prepare(sdk)
            self.assertEqual(path.read_text(), 'before\n' + module.AFTER + 'after\n')
            module.prepare(sdk)
            self.assertEqual(path.read_text(), 'before\n' + module.AFTER + 'after\n')

    def test_unknown_generator_fails_without_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            sdk = Path(directory)
            (sdk / 'scripts').mkdir()
            path = sdk / 'scripts/package-metadata.pl'
            path.write_text('different upstream implementation\n')
            with self.assertRaises(ValueError):
                module.prepare(sdk)
            self.assertEqual(path.read_text(), 'different upstream implementation\n')

    def test_removed_implication_is_a_tautology(self):
        for option in [False, True]:
            for libc in [False, True]:
                self.assertTrue(not (option and libc) or libc)

    def test_relocates_only_sdk_libtool_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            sdk = Path(directory)
            (sdk / 'scripts').mkdir()
            (sdk / 'scripts/package-metadata.pl').write_text(module.BEFORE)
            (sdk / 'staging_dir').mkdir()
            archive = sdk / 'staging_dir/libstdc++.la'
            archive.write_text("libdir='/builder/shared-workdir/build/staging_dir/toolchain/lib'\n")
            other = sdk / 'staging_dir/unrelated.txt'
            other.write_text('/builder/shared-workdir/build/staging_dir/')
            module.prepare(sdk)
            self.assertEqual(archive.read_text(), f"libdir='{sdk.resolve()}/staging_dir/toolchain/lib'\n")
            self.assertEqual(other.read_text(), '/builder/shared-workdir/build/staging_dir/')
