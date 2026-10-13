"""
PWF Auth — a guided console tour of the official `pwfauth` package.

Run:
    pip install -r requirements.txt
    Configure DEFAULT_APP_SECRET below before running.
    python demo.py PWF-XXXX-XXXX-XXXX          # or run with no argument to be prompted

Each numbered section calls one feature and prints a coloured result:
    0) app info   1) check key   2) sign in (and move the license here)
    3) update check, remote texts and slides
    4) user variables: values kept on the server for this key
    5) live session: the heartbeat and the kill switch   6) sign out
Optional, because they create data in your application:
    --trial      7) a free trial key for this computer
    --accounts   8) a throwaway user account: register, sign in, change password

https://pwfauth.com   ·   docs: https://pwfauth.com/docs
"""
import argparse
import os
import sys
import threading
import time

from pwfauth import (PwfClient, PwfError, PwfErrorCodes, PwfHttpError, PwfRefusedError,
                     PwfSecurityError, __version__ as PWFAUTH_VERSION)

# Get your App Secret from the dashboard: Applications -> your app -> API key.
# Configure this before building. Do not commit your real app secret.
DEFAULT_APP_SECRET = ""
DEFAULT_BASE_URL = "https://pwfauth.com"
APP_VERSION = "1.0.0"  # this app's version, for the update check

# Honour the NO_COLOR convention (https://no-color.org) — set NO_COLOR to disable.
if os.environ.get("NO_COLOR"):
    CYAN = GREEN = RED = YELLOW = RESET = ""
else:
    CYAN, GREEN, RED, YELLOW, RESET = "\033[36m", "\033[32m", "\033[31m", "\033[33m", "\033[0m"


def section(title):
    print()
    print(f"{CYAN}{title}{RESET}")


def ok(msg):
    print(f"{GREEN}  [OK] {msg}{RESET}")


def fail(title, message, code=None):
    text = message or code or "unknown"
    if code and message:
        text += f" ({code})"
    print(f"{RED}  [!!] {title}: {text}{RESET}")


def note(msg):
    print(f"{YELLOW}  [..] {msg}{RESET}")


def detail(label, value):
    print(f"     {label}: {value}")


def ask(question):
    """y/N from the keyboard; "no" when there is none (CI, pipes)."""
    try:
        return sys.stdin.isatty() and input(f"     {question} [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:  # Windows reports NUL as a terminal
        return False


# ── the tour ────────────────────────────────────────────────────────────────

def app_info(client):
    # 0) APP INFO — branding, version, download URL, social links. Encrypted reply.
    section("0) App info")
    info = client.get_app_info()
    if not info.success:
        fail("App info", info.message, info.error_code)
        return
    app = info.data.get("app") or {}
    ok(f"App: {app.get('name', '?')}   v{app.get('version', '?')}")
    if app.get("maintenance_mode"):
        note(f"Maintenance: {app.get('maintenance_msg')}")
    links = app.get("social_links") or []
    if links:
        detail("Social links", ", ".join(link.get("label") or link.get("platform", "?") for link in links))


def check_key(client, license_key):
    # 1) CHECK KEY — read-only status. No session, so no device seat is used.
    section("1) Check key")
    chk = client.check_key(license_key)
    if chk.success and chk.data.get("valid"):
        key = chk.data.get("key") or {}
        ok(f"Valid — status {key.get('status')}, expires {key.get('expires_at') or 'when first used / never'}")
    else:
        fail("Rejected", chk.message, chk.error_code)


def sign_in(client, license_key, move):
    # 2) SIGN IN — binds the key to this computer and opens a session. Encrypted.
    section("2) Sign in")
    detail("HWID", client.hardware_id)
    login = client.login(license_key)
    if not login.success and login.error_code in (PwfErrorCodes.HWID_MISMATCH,
                                                  PwfErrorCodes.DEVICE_LIMIT):
        # Bound to another computer: the customer can move it here by themselves.
        fail("Bound to another computer", login.message, login.error_code)
        if not (move or ask("Move this license to this PC? It then stops working on the other one.")):
            return False
        moved = client.reset_hardware_id(license_key, "Moved with the Python console demo")
        if not moved.success:
            fail("Move", moved.message, moved.error_code)
            return False
        ok(f"Moved here. The next move is allowed after {moved.data.get('next_reset_at')}")
        login = client.login(license_key)

    if not login.success:
        fail("Sign in", login.message, login.error_code)
        return False

    lic = login.license
    ok(f"Signed in — session {client.session_id}")
    if lic is not None:
        detail("Status", lic.status)
        detail("Expires", "never (lifetime)" if lic.is_lifetime else f"{lic.expires_at}  ({lic.days_remaining} days left)")
    seller = login.data.get("seller") or {}
    if seller.get("name"):
        detail("Sold by", seller["name"])
    return True


def app_content(client):
    # 3) UPDATE CHECK, REMOTE TEXTS, SLIDES — while signed in.
    section("3) Update check, texts and slides")
    upd = client.check_update(APP_VERSION)
    if not upd.success:
        fail("Update check", upd.message, upd.error_code)
    elif upd.data.get("update_available"):
        update = upd.data.get("update") or {}
        ok(f"Update available: v{update.get('version')} — {update.get('changelog') or 'no changelog'}")
    else:
        ok(f"v{APP_VERSION} is the latest")

    texts = client.get_texts()
    if texts.success:
        ok(f"Remote texts: {len(texts.data.get('texts') or [])}")
    else:
        fail("Remote texts", texts.message, texts.error_code)

    slides = client.get_slides()
    if slides.success:
        ok(f"Slides: {len(slides.data.get('slides') or [])}")
    else:
        fail("Slides", slides.message, slides.error_code)


def user_variables(client):
    # 4) USER VARIABLES — small values kept on the server for this key: settings, progress,
    # flags. They follow the key to a new PC, and you see and edit them in your panel
    # (Licences -> the key -> Variables). The demo counts its own runs.
    section("4) User variables")
    try:
        try:
            runs = int(client.get_variable("demo_runs") or 0) + 1
        except ValueError:  # someone typed text into it in the panel
            runs = 1
        client.set_variable("demo_runs", str(runs))
        client.set_variable("demo_last_run", time.strftime("%Y-%m-%d %H:%M:%S"))
    except PwfRefusedError as ex:
        fail("User variables", str(ex), ex.error_code)
        return None
    ok(f"This key has run the demo {runs} time{'' if runs == 1 else 's'} (kept on the server as demo_runs)")
    for name, value in sorted(client.get_variables().items()):
        detail(name, value)
    detail("Try it", "open this key in your panel: Licences -> the key -> Variables")
    return runs


def live_session(client, seconds):
    # 5) HEARTBEAT — keeps the session alive AND enforces the kill switch.
    section("5) Live session")

    def on_session_ended(error_code, message):
        # Runs on the heartbeat thread: banned, paused, expired, reset, revoked,
        # maintenance, or the server stopped answering. A real app stops here — with
        # os._exit, because sys.exit() would only end this thread.
        fail("Session ended", message, error_code)
        print("     A real app stops here, and so does this demo.")
        sys.stdout.flush()
        os._exit(4)

    client.on_session_ended = on_session_ended
    client.start_heartbeat()
    ok(f"Heartbeat every {client.heartbeat_interval:g} seconds")
    detail("Try it", "ban, pause or reset this key in your dashboard: the demo stops on the next beat")
    if seconds is not None:
        print(f"     Signing out in {seconds:g} seconds...")
        time.sleep(seconds)
    else:
        try:
            input("     Press Enter to sign out... ")
        except EOFError:  # no keyboard (CI, pipes)
            pass


def sign_out(client):
    # 6) SIGN OUT — ends the session on the server. The key stays bound here.
    section("6) Sign out")
    lo = client.logout()
    if lo is not None and lo.success:
        ok("Signed out")
    else:
        note("Signed out here; the server will end the session on its own timeout")


def trial(client):
    # 7) TRIAL — a free trial key for this computer (when the app allows trials).
    section("7) Free trial")
    tr = client.create_trial()
    if tr.success:
        ok(f"Trial key: {tr.data.get('trial_key')}  (expires {tr.data.get('expires_at')})")
    else:
        fail("Trial", tr.message, tr.error_code)


def accounts(client):
    # 8) USER ACCOUNTS — register, sign in, change the password.
    section("8) User accounts")
    user = f"demo_{int(time.time())}"
    pass1, pass2 = "DemoPass!123456", "DemoPass!654321"
    print(f"     (creates a throwaway account: {user})")
    reg = client.register_account(user, pass1, email=f"{user}@example.com")
    if not reg.success:
        fail("Register", reg.message, reg.error_code)
        if reg.error_code == PwfErrorCodes.KEY_REQUIRED:
            detail("Tip", "this app wants a key at sign-up: register_account_with_key(user, password, key)")
        return
    ok("Registered")

    al = client.account_login(user, pass1)
    if not al.success:
        fail("Account sign-in", al.message, al.error_code)
        return
    ok(f"Account signed in — session {client.session_id}")

    cp = client.change_account_password(user, pass1, pass2)
    if cp.success:
        ok("Password changed — this signs the account out on every device")
    else:
        fail("Change password", cp.message, cp.error_code)
    client.logout()


def main():
    parser = argparse.ArgumentParser(description="A guided tour of the pwfauth package.")
    parser.add_argument("license_key", nargs="?", help="the key to sign in with (prompted when left out)")
    parser.add_argument("--move", action="store_true",
                        help="move the license here without asking when it is bound to another PC")
    parser.add_argument("--seconds", type=float, metavar="N",
                        help="keep the session open N seconds instead of waiting for Enter")
    parser.add_argument("--trial", action="store_true", help="also create a free trial key")
    parser.add_argument("--accounts", action="store_true", help="also create a throwaway user account")
    args = parser.parse_args()

    if os.name == "nt":
        os.system("")  # enable ANSI colours in the Windows console

    app_secret = DEFAULT_APP_SECRET.strip()
    if not app_secret:
        print("!  Set DEFAULT_APP_SECRET in demo.py first.")
        return 1
    base_url = DEFAULT_BASE_URL

    license_key = args.license_key or input("Enter license key: ").strip()
    if not license_key:
        print("No key entered.")
        return 1

    client = PwfClient(app_secret, base_url=base_url)
    print(f"PWF Auth — Python console demo (pwfauth {PWFAUTH_VERSION})   ·   https://pwfauth.com")

    try:
        app_info(client)
        check_key(client, license_key)
        signed_in = sign_in(client, license_key, args.move)
        if signed_in:
            app_content(client)
            user_variables(client)
            live_session(client, args.seconds)
            sign_out(client)
        if args.trial:
            trial(client)
        if args.accounts:
            accounts(client)
    except PwfSecurityError as ex:
        # A plain "success" where the server always encrypts: a proxy, a hosts-file
        # entry or a fake server answered. Never unlock the app on it.
        fail("Not the license server", str(ex))
        return 3
    except PwfHttpError as ex:
        fail("No connection" if ex.status == 0 else f"HTTP {ex.status}", str(ex))
        return 3
    except PwfError as ex:
        fail("Error", str(ex))
        return 3

    print()
    print("Done.")
    return 0 if signed_in else 2


if __name__ == "__main__":
    sys.exit(main())
