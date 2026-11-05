"""Informational CLI flags must work without router modules or configuration."""
from pathlib import Path
import os
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
LUA = shutil.which('lua5.1') or shutil.which('lua')


@unittest.skipUnless(LUA, 'Lua interpreter is unavailable')
class CliTests(unittest.TestCase):
    def run_agent(self, flag):
        return subprocess.run(
            [LUA, str(ROOT / 'package/files/usr/sbin/flint2-agent'), flag],
            env={**os.environ, 'LUA_PATH': '/nonexistent/?.lua',
                 'LUA_CPATH': '/nonexistent/?.so', 'FLINT2_CONFIG_DIR': '/nonexistent'},
            capture_output=True, text=True, timeout=3, check=False)

    def test_information_needs_no_configuration_or_modules(self):
        version = self.run_agent('--version')
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertEqual(version.stdout.strip(), 'flint2-telemetry 0.4.0')
        for flag in ['--help', '-h']:
            result = self.run_agent(flag)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Usage:', result.stdout)

    def test_unknown_option_does_not_start_agent(self):
        result = self.run_agent('--invalid-option')
        self.assertEqual(result.returncode, 2)
        self.assertIn('Unknown option:', result.stderr)


if __name__ == '__main__':
    unittest.main()
