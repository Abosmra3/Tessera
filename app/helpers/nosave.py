import base64
import subprocess
import socket
import threading
import time
from app.helpers.firewall_check import get_firewall_health_summary
from app.ui.terminal_ui import UIManager
from app.core.play_sound import play_sound

__all__ = [
    "toggle_nosave",
    "run_nosave_startup_check",
    "force_disable_nosave",
    "is_nosave_retryable",
]

try:
    from app.ui import overlay
except Exception:
    overlay = None

RULE_NAME = "NOSAVE_OUT"
BLOCK_IP = base64.b64decode("MTkyLjgxLjI0MS4xNzE=").decode("utf-8")
SOCKET_CHECK_TIMEOUT_SEC = 1.0

_firewall_enabled = False
_startup_failed = False
_toggle_lock = threading.Lock()


def _run_netsh(args):
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(
        ["netsh", "advfirewall", "firewall"] + args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )


def _safe_overlay(fn):
    try:
        fn()
    except Exception:
        pass


def _banner_on():
    if overlay:
        overlay.banner("Nosave <b>ON</b>", color="green")


def _banner_off():
    if overlay:
        overlay.banner("Nosave <b>OFF</b>", color="red", duration_ms=3000)


def _rule_exists() -> bool:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(
        ["netsh", "advfirewall", "firewall", "show", "rule", f"name={RULE_NAME}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    return result.returncode == 0


def _test_ip_blocked(timeout: float = SOCKET_CHECK_TIMEOUT_SEC) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((BLOCK_IP, 80)) != 0
    except Exception:
        return False


def _apply_verified_enabled_state() -> None:
    global _firewall_enabled
    _firewall_enabled = True
    UIManager.set_nosave_state("ACTIVE")

    _safe_overlay(_banner_on)

    play_sound("on.wav")


def _apply_verified_disabled_state() -> None:
    global _firewall_enabled
    _firewall_enabled = False
    UIManager.set_nosave_state("INACTIVE")

    _safe_overlay(_banner_off)

    play_sound("off.wav")


def _sync_status():
    global _firewall_enabled
    if _startup_failed:
        _firewall_enabled = False
        error_reason = _get_nosave_error_reason()
        UIManager.set_nosave_error_notice(f"{error_reason} Press F8 to recheck.")
        UIManager.set_nosave_state("ERROR")
        return
    _firewall_enabled = _rule_exists()
    UIManager.set_nosave_state("ACTIVE" if _firewall_enabled else "INACTIVE")


def _get_nosave_error_reason() -> str:
    try:
        summary = get_firewall_health_summary()
        return summary["reason"]
    except Exception:
        return "Nosave failed because the Windows Firewall test could not be completed."


def _delete_rule_by_name() -> None:
    _run_netsh([
        "delete", "rule",
        f"name={RULE_NAME}",
    ])


def is_nosave_retryable() -> bool:
    """Return True when the nosave startup verifier failed and can be retried."""
    return _startup_failed


def force_disable_nosave() -> None:
    """Remove block rule without verification, overlay, or sound."""
    global _firewall_enabled
    _delete_rule_by_name()
    _firewall_enabled = False
    UIManager.set_nosave_state("INACTIVE")


def _reset_rule_on_startup() -> None:
    force_disable_nosave()


def run_nosave_startup_check() -> None:
    """Silently verify firewall effectiveness once at startup via socket test."""
    global _firewall_enabled, _startup_failed
    with _toggle_lock:
        _startup_failed = False
        _firewall_enabled = False
        UIManager.set_nosave_state("VERIFYING")
        UIManager.set_nosave_error_notice("")

        _delete_rule_by_name()
        _run_netsh([
            "add", "rule",
            f"name={RULE_NAME}",
            "dir=out",
            "action=block",
            f"remoteip={BLOCK_IP}",
        ])
        time.sleep(0.35)
        blocked_ok = _test_ip_blocked()

        _delete_rule_by_name()
        time.sleep(0.2)

        if blocked_ok:
            UIManager.set_nosave_state("INACTIVE")
            return

        _startup_failed = True
        error_reason = _get_nosave_error_reason()
        UIManager.set_nosave_error_notice(f"{error_reason} Press F8 to recheck.")
        UIManager.set_nosave_state("ERROR")


def _cancelled(cancel_event=None) -> bool:
    return cancel_event is not None and cancel_event.is_set()


def _force_disable_rule() -> None:
    global _firewall_enabled
    _delete_rule_by_name()
    _firewall_enabled = False
    UIManager.set_nosave_state("INACTIVE")
    _safe_overlay(_banner_off)


def _add_firewall_rule(cancel_event=None):
    with _toggle_lock:
        if _cancelled(cancel_event):
            _force_disable_rule()
            return

        _delete_rule_by_name()
        _run_netsh([
            "add", "rule",
            f"name={RULE_NAME}",
            "dir=out",
            "action=block",
            f"remoteip={BLOCK_IP}",
        ])

        time.sleep(0.2)
        if _cancelled(cancel_event):
            _force_disable_rule()
            return

        _apply_verified_enabled_state()


def _delete_firewall_rule(cancel_event=None):
    with _toggle_lock:
        if _cancelled(cancel_event):
            _force_disable_rule()
            return

        _delete_rule_by_name()

        time.sleep(0.2)
        if _cancelled(cancel_event):
            _force_disable_rule()
            return

        _apply_verified_disabled_state()


def toggle_nosave(cancel_event=None):
    if _cancelled(cancel_event):
        _force_disable_rule()
        return

    if _startup_failed:
        UIManager.set_nosave_state("VERIFYING")
        UIManager.set_nosave_error_notice("")
        run_nosave_startup_check()
        if _startup_failed:
            error_reason = _get_nosave_error_reason()
            UIManager.set_nosave_error_notice(f"{error_reason} Press F8 to recheck.")
            UIManager.set_nosave_state("ERROR")
        else:
            UIManager.set_nosave_state("INACTIVE")
        return

    if _firewall_enabled:
        _delete_firewall_rule(cancel_event=cancel_event)
    else:
        _add_firewall_rule(cancel_event=cancel_event)
