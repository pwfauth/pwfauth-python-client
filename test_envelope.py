"""
Offline self-test for the envelope (no network, no app needed).

Proves that CryptoEnvelope.encrypt -> decrypt round-trips, that tampering is
rejected, and that is_envelope() classifies payloads correctly. Run it directly
or via `python -m unittest test_envelope`.
"""
import json
import unittest

from pwfauth_client import CryptoEnvelope


class EnvelopeTests(unittest.TestCase):
    SECRET = "test_secret_0123456789"

    def test_round_trip(self):
        crypto = CryptoEnvelope(self.SECRET)
        inner = json.dumps({"license_key": "PWF-1234-5678-9012", "hwid": "abc123"})
        envelope = crypto.encrypt(inner)

        parsed = json.loads(envelope)
        self.assertEqual({"p", "t", "s"}, set(parsed.keys()))
        self.assertEqual(inner, crypto.decrypt(envelope))

    def test_tampered_ciphertext_is_rejected(self):
        crypto = CryptoEnvelope(self.SECRET)
        env = json.loads(crypto.encrypt('{"x":1}'))
        env["s"] = "0" * 64  # wrong HMAC
        with self.assertRaises(ValueError):
            crypto.decrypt(json.dumps(env))

    def test_wrong_secret_cannot_decrypt(self):
        good = json.loads(CryptoEnvelope(self.SECRET).encrypt('{"x":1}'))
        with self.assertRaises(ValueError):
            CryptoEnvelope("a_different_secret").decrypt(json.dumps(good))

    def test_is_envelope(self):
        self.assertTrue(CryptoEnvelope.is_envelope(CryptoEnvelope(self.SECRET).encrypt("{}")))
        self.assertFalse(CryptoEnvelope.is_envelope('{"success": false, "message": "nope"}'))
        self.assertFalse(CryptoEnvelope.is_envelope("not json at all"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
