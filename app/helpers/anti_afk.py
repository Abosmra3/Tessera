import ctypes
import threading
import time
from collections.abc import Callable

import keyboard

try:
    from app.ui import overlay
except Exception:
    overlay = None

from app.core.play_sound import play_sound
from app.core.debug import debug_print as _debug_print

__all__ = ["toggle_anti_afk", "stop_anti_afk", "is_anti_afk_enabled"]

INTERVAL_SECONDS = 14 * 60
PRESS_DURATION_SECONDS = 0.05
FOCUS_SETTLE_SECONDS = 0.05

_SW_RESTORE = 9
_VK_MENU = 0x12
_VK_TAB = 0x09
_KEYEVENTF_KEYUP = 0x0002
_GA_ROOT = 2

_user32 = ctypes.windll.user32

_lock = threading.Lock()
_enabled = False
_worker_thread = None
_stop_event = None


def _safe_overlay(fn):
    try:
        fn()
    except Exception:
        pass


def _banner_on():
    if overlay:
        overlay.banner(
            "Anti AFK <b>ON</b> (every 14m)",
            color="green",
            duration_ms=3000,
        )


def _banner_off():
    if overlay:
        overlay.banner(
            "Anti AFK <b>OFF</b>",
            color="red",
            duration_ms=3000,
        )


def _tap_alt():
    _user32.keybd_event(_VK_MENU, 0, 0, 0)
    _user32.keybd_event(_VK_MENU, 0, _KEYEVENTF_KEYUP, 0)


def _focus_window(hwnd: int) -> bool:
    if not hwnd:
        return False
    _user32.ShowWindow(hwnd, _SW_RESTORE)
    _user32.BringWindowToTop(hwnd)
    _tap_alt()
    return bool(_user32.SetForegroundWindow(hwnd))


def _root_window(hwnd: int) -> int:
    if not hwnd:
        return 0
    try:
        root = _user32.GetAncestor(hwnd, _GA_ROOT)
        return int(root) if root else int(hwnd)
    except Exception:
        return int(hwnd)


def _alt_tab_once():
    _user32.keybd_event(_VK_MENU, 0, 0, 0)
    _user32.keybd_event(_VK_TAB, 0, 0, 0)
    _user32.keybd_event(_VK_TAB, 0, _KEYEVENTF_KEYUP, 0)
    _user32.keybd_event(_VK_MENU, 0, _KEYEVENTF_KEYUP, 0)


def _is_target_focused(target_hwnd: int, foreground_hwnd: int) -> bool:
    if not target_hwnd or not foreground_hwnd:
        return False
    if foreground_hwnd == target_hwnd:
        return True
    try:
        return bool(_user32.IsChild(target_hwnd, foreground_hwnd))
    except Exception:
        return False


def _press_a_and_d():
    keyboard.press("a")
    keyboard.press("d")
    time.sleep(PRESS_DURATION_SECONDS)
    keyboard.release("d")
    keyboard.release("a")


def _do_anti_afk_cycle(
    is_target_ready_fn: Callable[[], bool],
    get_target_hwnd_fn: Callable[[], int | None],
):
    if not is_target_ready_fn():
        return

    target_hwnd = get_target_hwnd_fn()
    if not target_hwnd:
        return

    _debug_print("[*] Anti AFK: Cycle triggered. Checking window focus...")
    original_hwnd = _root_window(_user32.GetForegroundWindow())
    target_was_focused = _is_target_focused(target_hwnd, original_hwnd)
    switched_focus = False

    if not target_was_focused:
        _debug_print(f"[*] Anti AFK: Switching focus to game (hwnd: {target_hwnd})")
        if not _focus_window(target_hwnd):
            _debug_print("[!] Anti AFK: Failed to focus game window")
            return
        switched_focus = True
        time.sleep(FOCUS_SETTLE_SECONDS)

    try:
        _debug_print("[*] Anti AFK: Sending A and D keypresses to reset AFK timer")
        _press_a_and_d()
    finally:
        if switched_focus and original_hwnd and original_hwnd != target_hwnd:
            _debug_print(f"[*] Anti AFK: Restoring focus to previous window (hwnd: {original_hwnd})")
            if not _focus_window(original_hwnd):
                _alt_tab_once()


def _worker_loop(
    stop_event: threading.Event,
    is_target_ready_fn: Callable[[], bool],
    get_target_hwnd_fn: Callable[[], int | None],
):
    while not stop_event.is_set():
        try:
            _do_anti_afk_cycle(is_target_ready_fn, get_target_hwnd_fn)
        except Exception:
            pass

        if stop_event.wait(INTERVAL_SECONDS):
            break


def _stop_locked():
    global _enabled, _worker_thread, _stop_event

    _enabled = False
    if _stop_event is not None:
        _stop_event.set()

    _worker_thread = None
    _stop_event = None


def is_anti_afk_enabled() -> bool:
    with _lock:
        return _enabled


def toggle_anti_afk(
    *,
    is_target_ready: Callable[[], bool],
    get_target_hwnd: Callable[[], int | None],
) -> bool:
    """Toggle anti-afk worker and return current enabled state."""
    global _enabled, _worker_thread, _stop_event

    with _lock:
        if _enabled:
            _stop_locked()
            _debug_print("[*] END anti_afk (worker loop stopped)")
            new_state = False
        else:
            _enabled = True
            _stop_event = threading.Event()
            _worker_thread = threading.Thread(
                target=_worker_loop,
                args=(_stop_event, is_target_ready, get_target_hwnd),
                daemon=True,
                name="anti_afk_worker",
            )
            _worker_thread.start()
            _debug_print("[*] START anti_afk (worker loop started)")
            new_state = True

    _safe_overlay(_banner_on if new_state else _banner_off)
    play_sound("on.wav" if new_state else "off.wav")
    return new_state


def stop_anti_afk() -> None:
    with _lock:
        if not _enabled:
            return
        _stop_locked()
