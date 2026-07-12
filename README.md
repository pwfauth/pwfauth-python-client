# pwfauth-python-client

A small, readable **Python** client for the [PWF Auth](https://pwfauth.com) API —
license keys, end-user auth, and OTA update checks behind one REST API. It
exercises **every client-facing endpoint** and reproduces the server's
AES-256-CBC + HMAC-SHA256 envelope, so `login` / `heartbeat` / `logout`
interoperate **byte-for-byte**.

> Sibling projects: the VB.NET and C# examples live in
> [`pwfauth-vbnet-examples`](https://github.com/pwfauth/pwfauth-vbnet-examples).

![A full run — every endpoint green](docs/demo.png)

## Install

```bash
pip install -r requirements.txt   # only pycryptodome (the stdlib has no AES)
```

Requires Python 3.8+.

## Run the demo

```bash
# Linux/macOS
export PWF_APP_SECRET="your_app_secret"
python demo.py PWF-XXXX-XXXX-XXXX

# Windows
setx PWF_APP_SECRET "your_app_secret"
python demo.py PWF-XXXX-XXXX-XXXX
```

Run with no argument to be prompted for the key.

## Features demonstrated

| # | Feature | Endpoint | Wire format |
| --- | --- | --- | --- |
| 0 | App info + update check | `GET /api/app/info.php` | encrypted reply |
| 1 | Check a license key | `POST /api/auth/check-key.php` | plain |
| 2 | Login (bind HWID, open session) | `POST /api/auth/login.php` | **encrypted** |
| 3 | Heartbeat (keep alive / kill code) | `POST /api/auth/heartbeat.php` | **encrypted** |
| 4 | Logout | `POST /api/auth/logout.php` | **encrypted** |
| 5 | Start a free trial | `POST /api/auth/trial.php` | plain |
| 6 | Request an HWID reset | `POST /api/auth/request-hwid-reset.php` | plain |
| 7 | Register / login / change-password | `POST /api/auth/account-*.php` | plain |

## Use as a library

```python
from pwfauth_client import PwfAuthClient, hwid

client = PwfAuthClient("your_app_secret")           # or PwfAuthClient(secret, base_url=...)

info = client.get_app_info()
print(info["_flat"]["name"], info["_flat"]["version"])

result = client.login("PWF-XXXX-XXXX-XXXX", hwid())
if result.get("success"):
    session_id = result["session_id"]
    client.heartbeat(session_id, "PWF-XXXX-XXXX-XXXX")
    client.logout(session_id, "PWF-XXXX-XXXX-XXXX")
```

Every method returns the parsed JSON `dict`, plus a `_flat` key that pulls
top-level and one nested level of scalar fields together for convenience.

## How the envelope works

`login` / `heartbeat` / `logout` send an encrypted `{p, t, s}` envelope and the
server replies with one (`app/info` also returns one); the rest is plain JSON.

- `enc_key = SHA256("enc:" + app_secret)`, `mac_key = SHA256("mac:" + app_secret)`
- `p = base64(IV(16) || AES-256-CBC(inner_json))`
- `t = unix_seconds`, `s = hex(HMAC-SHA256(p + t, mac_key))`, 300 s drift window

See [`pwfauth_client.py`](pwfauth_client.py) — `CryptoEnvelope`.

## Files

| File | Role |
| --- | --- |
| `pwfauth_client.py` | The client — `CryptoEnvelope`, `hwid()`, and `PwfAuthClient` (one method per endpoint) |
| `demo.py` | A guided run through every endpoint |
| `test_envelope.py` | An offline round-trip test of the envelope (no network) |

## Security note

An app secret shipped in a client can be extracted — treat client-side license
checks as a **deterrent, not DRM**. Keep the secret out of source control; the
demo reads it from the `PWF_APP_SECRET` environment variable.

## License

MIT — see [LICENSE](LICENSE).
