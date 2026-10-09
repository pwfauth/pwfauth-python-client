"""Offline configuration regression checks."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

class DemoTests(unittest.TestCase):
    def test_ignores_environment_overrides(self):
        env = {**os.environ, 'PWFAUTH_SECRET': 'a'*64, 'PWF_APP_SECRET': 'b'*64,
            'PWFAUTH_BASE_URL': 'http://127.0.0.1:9', 'PWF_BASE_URL': 'http://127.0.0.1:9',
            'PYTHONIOENCODING': 'utf-8'}
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('demo.py')), 'TEST-KEY'],
            env=env, capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('Set DEFAULT_APP_SECRET', result.stdout)
        self.assertNotIn('Signed in', result.stdout)

if __name__ == '__main__':
    unittest.main()
