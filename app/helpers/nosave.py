import subprocess
import socket
import threading
import time
from app.helpers.firewall_check import get_firewall_health_summary
from app.ui.gui import UIManager
from app.core.play_sound import play_sound
from app.core.debug import debug_print as _debug_print

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
BLOCK_IP = "192.81.241.171"
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
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        policy = win32com.client.Dispatch("HNetCfg.FwPolicy2")
        try:
            policy.Rules.Item(RULE_NAME)
            return True
        except Exception:
            return False
    except Exception:
        pass
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(
        ["netsh", "advfirewall", "firewall", "show", "rule", f"name={RULE_NAME}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    return result.returncode == 0


def _add_rule_out(name: str, remoteip: str) -> None:
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        policy = win32com.client.Dispatch("HNetCfg.FwPolicy2")
        rule = win32com.client.Dispatch("HNetCfg.FwRule")
        rule.Name = name
        rule.Description = "Tessera NoSave outbound block rule"
        rule.Direction = 2
        rule.Action = 0
        rule.Enabled = True
        rule.RemoteAddresses = remoteip
        policy.Rules.Add(rule)
        return
    except Exception:
        pass
    _run_netsh([
        "add", "rule",
        f"name={name}",
        "dir=out",
        "action=block",
        f"remoteip={remoteip}",
    ])


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


def _get_nosave_error_reason() -> str:
    try:
        summary = get_firewall_health_summary()
        return summary["reason"]
    except Exception:
        return "Nosave failed because the Windows Firewall test could not be completed."


def _delete_rule_by_name() -> None:
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        policy = win32com.client.Dispatch("HNetCfg.FwPolicy2")
        policy.Rules.Remove(RULE_NAME)
        return
    except Exception:
        pass
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
    with _toggle_lock:
        _delete_rule_by_name()
        _firewall_enabled = False
        UIManager.set_nosave_state("INACTIVE")


def run_nosave_startup_check() -> None:
    """Silently verify firewall effectiveness once at startup via socket test."""
    global _firewall_enabled, _startup_failed
    with _toggle_lock:
        _debug_print("[*] START nosave_startup_check")
        if _rule_exists():
            _delete_rule_by_name()

        _startup_failed = False
        _firewall_enabled = False
        UIManager.set_nosave_state("VERIFYING")
        UIManager.set_nosave_error_notice("")

        _delete_rule_by_name()
        _debug_print(f"[*] Nosave: Creating test rule to block remote server ({BLOCK_IP})")
        _add_rule_out(RULE_NAME, BLOCK_IP)
        time.sleep(0.35)
        
        _debug_print("[*] Nosave: Verifying save server block status...")
        blocked_ok = _test_ip_blocked()

        _delete_rule_by_name()
        time.sleep(0.2)

        if not blocked_ok:
            _debug_print("[!] Nosave: Block check FAILED (server was still reachable)")
            _delete_rule_by_name()
            _startup_failed = True
            _firewall_enabled = False
            error_reason = _get_nosave_error_reason()
            UIManager.set_nosave_error_notice(f"{error_reason} Press F8 to recheck.")
            UIManager.set_nosave_state("ERROR")
            _debug_print("[*] END nosave_startup_check - FAILED")
            return

        _debug_print("[*] Nosave: Block check SUCCEEDED (server correctly blocked)")
        _startup_failed = False
        if _rule_exists():
            _delete_rule_by_name()
            time.sleep(0.1)

        _firewall_enabled = False
        UIManager.set_nosave_state("INACTIVE")
        _debug_print("[*] END nosave_startup_check - PASSED")


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

        _debug_print(f"[*] Nosave: Blocking remote save server ({BLOCK_IP})")
        _delete_rule_by_name()
        _add_rule_out(RULE_NAME, BLOCK_IP)

        time.sleep(0.05)
        if _cancelled(cancel_event):
            _force_disable_rule()
            return

        _apply_verified_enabled_state()


def _delete_firewall_rule(cancel_event=None):
    with _toggle_lock:
        if _cancelled(cancel_event):
            _force_disable_rule()
            return

        _debug_print("[*] Nosave: Unblocking remote save server")
        _delete_rule_by_name()

        time.sleep(0.05)
        if _cancelled(cancel_event):
            _force_disable_rule()
            return

        _apply_verified_disabled_state()


def toggle_nosave(cancel_event=None):
    if _cancelled(cancel_event):
        _force_disable_rule()
        return

    if _startup_failed:
        _debug_print("[*] Nosave: Retrying failed startup check...")
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
        _debug_print("[*] START toggle_nosave (Disabling outbound block)")
        _delete_firewall_rule(cancel_event=cancel_event)
        _debug_print("[*] END toggle_nosave (Saves unblocked)")
    else:
        _debug_print("[*] START toggle_nosave (Enabling outbound block)")
        _add_firewall_rule(cancel_event=cancel_event)
        _debug_print("[*] END toggle_nosave (Saves blocked)")
