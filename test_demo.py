"""
Offline checks for demo.py (no PWF Auth server, no app secret needed).

A tiny local HTTP server plays a FAKE license server that answers every request
with a plain {"success": true}. The real server encrypts those replies, so the
demo must refuse to sign in. Run it directly or via `python -m unittest test_demo`.
"""
import http.server
import os
import subprocess
import sys
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


class FakeServer(http.server.BaseHTTPRequestHandler):
    def _reply(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        body = b'{"success": true, "session_id": "fake", "valid": true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = _reply

    def log_message(self, *args):
        pass


def run_demo(*args, **env):
    full_env = {k: v for k, v in os.environ.items()
                if k not in ("PWFAUTH_SECRET", "PWF_APP_SECRET", "PWFAUTH_BASE_URL", "PWF_BASE_URL")}
    full_env.update(env, NO_COLOR="1", PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, os.path.join(HERE, "demo.py"), *args],
                          capture_output=True, text=True, encoding="utf-8",
                          env=full_env, stdin=subprocess.DEVNULL, timeout=60)


class DemoTests(unittest.TestCase):
    def test_needs_a_secret(self):
        result = run_demo("PWF-TEST-KEY")
        self.assertEqual(1, result.returncode)
        self.assertIn("Set PWFAUTH_SECRET", result.stdout)

    def test_refuses_a_fake_server(self):
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeServer)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            result = run_demo("PWF-TEST-KEY",
                              PWFAUTH_SECRET="0123456789abcdef" * 4,
                              PWFAUTH_BASE_URL=f"http://127.0.0.1:{server.server_port}")
        finally:
            server.shutdown()
        self.assertEqual(3, result.returncode, result.stdout + result.stderr)
        self.assertIn("Not the license server", result.stdout)
        self.assertNotIn("Signed in", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
