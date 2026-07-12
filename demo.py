"""
PWF Auth — Python demo that exercises every client-facing endpoint.

Run:
    setx PWF_APP_SECRET "your_app_secret"     # once (Windows) — get it from the dashboard
    python demo.py PWF-XXXX-XXXX-XXXX          # or run with no argument to be prompted

Each numbered section calls one feature and prints a coloured result:
    0) app info   1) check key   2) login   3) heartbeat   4) logout
    5) trial      6) HWID reset   7) accounts (register / login / change-password)

https://pwfauth.com   ·   docs: https://pwfauth.com/api.php
"""
import os
import sys
import time

from pwfauth_client import PwfAuthClient, CryptoEnvelope, hwid  # noqa: F401 (CryptoEnvelope re-exported for users)

# Get your App Secret from the dashboard: Applications -> your app -> API key.
# NEVER commit your real secret. Prefer the PWF_APP_SECRET environment variable.
DEFAULT_APP_SECRET = ""
DEFAULT_BASE_URL = "https://pwfauth.com"

# Honour the NO_COLOR convention (https://no-color.org) — set NO_COLOR to disable.
if os.environ.get("NO_COLOR"):
    CYAN = GREEN = RED = DIM = RESET = ""
else:
    CYAN, GREEN, RED, DIM, RESET = "\033[36m", "\033[32m", "\033[31m", "\033[90m", "\033[0m"


def section(title):
    print()
    print(f"{CYAN}{title}{RESET}")


def ok(msg):
    print(f"{GREEN}  [OK] {msg}{RESET}")


def fail(title, message, code):
    print(f"{RED}  [!!] {title}: {message or code or 'unknown'}{RESET}")


def detail(label, value):
    print(f"     {label}: {value}")


def field(data, name, default=""):
    """Read a field from the reply — top level, then the flattened nested level."""
    if name in data and not isinstance(data[name], (dict, list)):
        return data[name]
    return data.get("_flat", {}).get(name, default)


def main():
    if os.name == "nt":
        os.system("")  # enable ANSI colours in the Windows console

    base_url = os.environ.get("PWF_BASE_URL") or DEFAULT_BASE_URL
    app_secret = os.environ.get("PWF_APP_SECRET") or DEFAULT_APP_SECRET
    if not app_secret:
        print("!  Set PWF_APP_SECRET (or DEFAULT_APP_SECRET in demo.py) first.")
        return 1

    license_key = sys.argv[1] if len(sys.argv) > 1 else input("Enter license key: ").strip()
    if not license_key:
        print("No key entered.")
        return 1

    client = PwfAuthClient(app_secret, base_url)
    device = hwid()

    print("PWF Auth — Python client demo   ·   https://pwfauth.com")

    try:
        # 0) APP INFO — branding + version + download URL. Encrypted reply.
        section("0) App info")
        info = client.get_app_info()
        if info.get("success"):
            ok(f"App: {field(info, 'name', '?')}   v{field(info, 'version', '?')}")
        else:
            fail("App info", info.get("message"), info.get("error_code"))

        # 1) CHECK KEY — lightweight read-only status. No session, no HWID binding.
        section("1) Check key")
        chk = client.check_key(license_key)
        if chk.get("valid"):
            key = chk.get("key", {})
            ok(f"Valid — status {key.get('status')}, expires {key.get('expires_at') or 'never'}")
        else:
            fail("Rejected", chk.get("message"), chk.get("error_code"))

        # 2) LOGIN — binds this device (HWID) and opens a session. Encrypted.
        section("2) Login")
        detail("HWID", device)
        login = client.login(license_key, device)
        session_id = ""
        if login.get("success"):
            session_id = login.get("session_id", "")
            ok(f"Logged in — session {session_id}")
        else:
            fail("Login", login.get("message"), login.get("error_code"))

        # 3) HEARTBEAT + 4) LOGOUT — only if a session opened. Encrypted.
        if session_id:
            section("3) Heartbeat")
            hb = client.heartbeat(session_id, license_key)
            if hb.get("success"):
                ok("Session alive")
            else:
                fail("Session ended", hb.get("message"), hb.get("error_code"))

            section("4) Logout")
            lo = client.logout(session_id, license_key)
            if lo.get("success"):
                ok("Logged out")
            else:
                fail("Logout", lo.get("message"), lo.get("error_code"))

        # 5) TRIAL — mint a free trial key for this device (if allowed).
        section("5) Start trial")
        tr = client.start_trial(device)
        if tr.get("success"):
            ok(f"Trial issued: {field(tr, 'license_key')}  (expires {field(tr, 'expires_at', '?')})")
        else:
            fail("Trial", tr.get("message"), tr.get("error_code"))

        # 6) HWID RESET REQUEST — ask an admin to unbind the device.
        section("6) Request HWID reset")
        rr = client.request_hwid_reset(license_key, "", "Demo: switched computers")
        if rr.get("success"):
            ok("Reset request submitted")
        else:
            fail("HWID reset", rr.get("message"), rr.get("error_code"))

        # 7) END-USER ACCOUNTS — register, login, change password.
        section("7) Account system")
        demo_user = f"demo_{int(time.time())}"
        pass1, pass2 = "DemoPass!123456", "DemoPass!654321"
        print(f"     (creates a throwaway account: {demo_user})")
        reg = client.account_register(demo_user, pass1, demo_user + "@example.com")
        if reg.get("success"):
            ok("Registered")
        else:
            fail("Register", reg.get("message"), reg.get("error_code"))
        al = client.account_login(demo_user, pass1, device)
        if al.get("success"):
            ok("Account login ok")
        else:
            fail("Account login", al.get("message"), al.get("error_code"))
        cp = client.change_password(demo_user, pass1, pass2)
        if cp.get("success"):
            ok("Password changed")
        else:
            fail("Change password", cp.get("message"), cp.get("error_code"))

        print()
        print("Done — every client feature exercised.")
        return 0
    except Exception as ex:  # noqa: BLE001 — a demo: surface any transport error simply
        fail("Network error", str(ex), "")
        return 3


if __name__ == "__main__":
    sys.exit(main())
