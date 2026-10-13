"""Offline checks: the configuration, and the user-variables section against a stand-in client."""
import io
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

os.environ.setdefault("NO_COLOR", "1")
import demo  # noqa: E402  (after NO_COLOR, so the output has no colour codes)
from pwfauth import PwfRefusedError, PwfResponse  # noqa: E402


class FakeVarsClient:
    """Stands in for PwfClient's four variable calls, with an in-memory store."""

    def __init__(self, store=None, refuse=None):
        self.store = dict(store or {})
        self.refuse = refuse

    def get_variable(self, name):
        if self.refuse:
            raise PwfRefusedError(PwfResponse(data={"success": False, "error_code": self.refuse, "message": "Refused."}))
        return self.store.get(name)

    def set_variable(self, name, value):
        assert isinstance(value, str)
        self.store[name] = value

    def get_variables(self):
        return dict(self.store)


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


class UserVariablesTests(unittest.TestCase):
    def run_section(self, client):
        out = io.StringIO()
        with redirect_stdout(out):
            result = demo.user_variables(client)
        return result, out.getvalue()

    def test_first_run_starts_at_one(self):
        client = FakeVarsClient()
        runs, out = self.run_section(client)
        self.assertEqual(runs, 1)
        self.assertEqual(client.store["demo_runs"], "1")
        self.assertIn("demo_last_run", client.store)
        self.assertIn("1 time (kept on the server", out)

    def test_counts_on_from_the_stored_value(self):
        client = FakeVarsClient({"demo_runs": "41", "theme": "dark"})
        runs, out = self.run_section(client)
        self.assertEqual(runs, 42)
        self.assertEqual(client.store["demo_runs"], "42")
        self.assertIn("theme: dark", out)

    def test_text_typed_in_the_panel_restarts_the_count(self):
        client = FakeVarsClient({"demo_runs": "lots"})
        runs, _ = self.run_section(client)
        self.assertEqual(runs, 1)

    def test_a_refusal_is_shown_not_raised(self):
        runs, out = self.run_section(FakeVarsClient(refuse="SESSION_EXPIRED"))
        self.assertIsNone(runs)
        self.assertIn("User variables: Refused. (SESSION_EXPIRED)", out)


if __name__ == '__main__':
    unittest.main()
