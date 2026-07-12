"""
PWF Auth — Python client.

A small, readable client for the PWF Auth API (https://pwfauth.com). It talks to
every client-facing endpoint and reproduces the server's AES-256-CBC + HMAC-SHA256
envelope so that login / heartbeat / logout interoperate byte-for-byte.

Only dependency: pycryptodome (for AES; the Python standard library has no cipher).
Everything else — HTTP, JSON, hashing, HMAC — is standard library.

Docs: https://pwfauth.com/api.php
"""
import base64
import getpass
import hashlib
import hmac
import json
import os
import platform
import time
import urllib.error
import urllib.request

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


class CryptoEnvelope:
    """
    AES-256-CBC + HMAC-SHA256 envelope — mirrors the server's PayloadCrypto exactly.

    Envelope:  {"p": base64(IV(16) || ciphertext), "t": unix_ts,
                "s": hex(hmac_sha256(p + t, mac_key))}
    Keys:      enc_key = SHA256("enc:" + app_secret)
               mac_key = SHA256("mac:" + app_secret)
    """
    MAX_DRIFT_SECONDS = 300  # keep in sync with the server

    def __init__(self, app_secret: str):
        if not app_secret:
            raise ValueError("App secret cannot be empty.")
        self._enc_key = hashlib.sha256(("enc:" + app_secret).encode("utf-8")).digest()
        self._mac_key = hashlib.sha256(("mac:" + app_secret).encode("utf-8")).digest()

    def encrypt(self, inner_json: str) -> str:
        """Wrap a plain JSON string in an encrypted {p,t,s} envelope."""
        iv = os.urandom(16)
        cipher = AES.new(self._enc_key, AES.MODE_CBC, iv)
        ciphertext = cipher.encrypt(pad(inner_json.encode("utf-8"), AES.block_size))

        p = base64.b64encode(iv + ciphertext).decode("ascii")
        t = int(time.time())
        s = self._hmac_hex(p + str(t))
        return json.dumps({"p": p, "t": t, "s": s})

    def decrypt(self, envelope_json: str) -> str:
        """Verify + decrypt a {p,t,s} envelope; return the inner JSON string."""
        env = json.loads(envelope_json)
        p, t, s = env["p"], int(env["t"]), env["s"]

        expected = self._hmac_hex(p + str(t))
        if not hmac.compare_digest(expected, (s or "").lower()):
            raise ValueError("HMAC verification failed")

        if abs(int(time.time()) - t) > self.MAX_DRIFT_SECONDS:
            raise ValueError("Request expired (replay protection)")

        combined = base64.b64decode(p)
        if len(combined) <= 16:
            raise ValueError("Malformed ciphertext")

        iv, ciphertext = combined[:16], combined[16:]
        cipher = AES.new(self._enc_key, AES.MODE_CBC, iv)
        return unpad(cipher.decrypt(ciphertext), AES.block_size).decode("utf-8")

    @staticmethod
    def is_envelope(text: str) -> bool:
        """True when the text looks like an encrypted {p,t,s} envelope (vs a plain
        JSON error the server returns before crypto runs)."""
        try:
            obj = json.loads(text)
        except (ValueError, TypeError):
            return False
        return isinstance(obj, dict) and "p" in obj and "t" in obj and "s" in obj

    def _hmac_hex(self, message: str) -> str:
        return hmac.new(self._mac_key, message.encode("utf-8"), hashlib.sha256).hexdigest()


def hwid() -> str:
    """A stable per-machine hardware id sent at login (the server binds the license
    to it). Derived from machine + user + OS + CPU count — good enough to show the
    flow; a production app would combine more hardware signals."""
    seed = "|".join([
        platform.node(),
        getpass.getuser(),
        platform.system(),
        str(os.cpu_count() or 0),
    ])
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32].lower()


class PwfAuthClient:
    """One method per endpoint. Plain JSON for check-key / trial / request-hwid-reset
    / accounts; the encrypted envelope for login / heartbeat / logout; app/info
    returns an encrypted reply."""

    def __init__(self, app_secret: str, base_url: str = "https://pwfauth.com"):
        if not app_secret or not app_secret.strip():
            raise ValueError("app_secret is required.")
        self._app_secret = app_secret.strip()
        self._base_url = base_url.rstrip("/")
        self._crypto = CryptoEnvelope(self._app_secret)

    # ── Plain read-only status ──────────────────────────────────────────────
    def check_key(self, license_key: str) -> dict:
        return self._parse(self._post("/api/auth/check-key.php",
                                       json.dumps({"license_key": (license_key or "").strip()})))

    # ── Encrypted session flow ──────────────────────────────────────────────
    def login(self, license_key: str, device_hwid: str) -> dict:
        inner = json.dumps({"license_key": (license_key or "").strip(), "hwid": (device_hwid or "").strip()})
        return self._parse(self._send_envelope("/api/auth/login.php", inner))

    def heartbeat(self, session_id: str, license_key: str) -> dict:
        inner = json.dumps({"session_id": session_id, "license_key": license_key})
        return self._parse(self._send_envelope("/api/auth/heartbeat.php", inner))

    def logout(self, session_id: str, license_key: str) -> dict:
        inner = json.dumps({"session_id": session_id, "license_key": license_key})
        return self._parse(self._send_envelope("/api/auth/logout.php", inner))

    # ── Plain endpoints ─────────────────────────────────────────────────────
    def start_trial(self, device_hwid: str) -> dict:
        return self._parse(self._post("/api/auth/trial.php", json.dumps({"hwid": device_hwid})))

    def request_hwid_reset(self, license_key: str, username: str, reason: str) -> dict:
        return self._parse(self._post("/api/auth/request-hwid-reset.php",
                                       json.dumps({"license_key": license_key, "username": username, "reason": reason})))

    def account_register(self, username: str, password: str, email: str) -> dict:
        return self._parse(self._post("/api/auth/account-register.php",
                                       json.dumps({"username": username, "password": password, "email": email})))

    def account_login(self, username: str, password: str, device_hwid: str) -> dict:
        return self._parse(self._post("/api/auth/account-login.php",
                                       json.dumps({"username": username, "password": password, "hwid": device_hwid})))

    def change_password(self, username: str, current_password: str, new_password: str) -> dict:
        return self._parse(self._post("/api/auth/change-password.php",
                                       json.dumps({"username": username,
                                                   "current_password": current_password,
                                                   "new_password": new_password})))

    def get_app_info(self) -> dict:
        raw = self._get("/api/app/info.php")
        return self._parse(self._crypto.decrypt(raw) if CryptoEnvelope.is_envelope(raw) else raw)

    # ── low-level helpers ───────────────────────────────────────────────────
    def _send_envelope(self, path: str, inner_json: str) -> str:
        raw = self._post(path, self._crypto.encrypt(inner_json))
        return self._crypto.decrypt(raw) if CryptoEnvelope.is_envelope(raw) else raw

    def _post(self, path: str, body: str) -> str:
        req = urllib.request.Request(self._base_url + path, data=body.encode("utf-8"), method="POST")
        req.add_header("Content-Type", "application/json")
        return self._send(req)

    def _get(self, path: str) -> str:
        return self._send(urllib.request.Request(self._base_url + path, method="GET"))

    def _send(self, req: urllib.request.Request) -> str:
        req.add_header("X-App-Secret", self._app_secret)
        req.add_header("User-Agent", "PwfAuthPythonClient/1.0 (+https://pwfauth.com)")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            # The API returns JSON (or an encrypted envelope) with non-2xx codes too.
            return e.read().decode("utf-8")

    @staticmethod
    def _parse(raw: str) -> dict:
        """Parse a JSON reply and add a `_flat` dict (top level + one nested-object
        level of scalars) so callers can read any field without digging."""
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return {"success": False, "message": "Unexpected response from the server.", "_raw": raw}
        if not isinstance(data, dict):
            data = {"_value": data}
        flat = {}
        for key, value in data.items():
            if isinstance(value, dict):
                for ck, cv in value.items():
                    if not isinstance(cv, (dict, list)):
                        flat[ck] = cv
            elif not isinstance(value, list):
                flat[key] = value
        data["_flat"] = flat
        return data
