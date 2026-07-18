import base64
import sys
import webbrowser
import ctypes
import ctypes.wintypes
import msvcrt
import threading
from threading import Thread

import pynput
from pynput import keyboard as pynput_keyboard

from app.core.updater import get_update_status
from app.core.version import APP_VERSION
from app.core.debug import get_debug_enabled, set_debug, toggle_debug
from app.solvers.cayo import solve_cayo
from app.solvers.casino import solve_casino
from app.solvers.keypad import solve_keypad
from app.helpers.anti_afk import toggle_anti_afk, stop_anti_afk
from app.helpers.job_warp import run_job_warp
from app.helpers.nosave import (
    toggle_nosave,
    run_nosave_startup_check,
    force_disable_nosave,
    is_nosave_retryable,
)
from app.ui.terminal_ui import UIManager, console

VERSION = APP_VERSION
APP_TITLE = "Tessera"
DEBUG_ENABLED = "--debug" in sys.argv[1:]

_TARGET_WINDOW_TITLE = base64.b64decode("R3JhbmQgVGhlZnQgQXV0byBW").decode("utf-8")

README_URL = "https://github.com/Abosmra3/Tessera#how-to-use-the-tool"
RELEASES_URL = "https://github.com/Abosmra3/Tessera/releases"
latest_release_url = RELEASES_URL
_update_notice_initialized = False
_update_notice_lock = threading.Lock()


def show_readme():
    if not README_URL:
        return
    try:
        webbrowser.open(README_URL)
    except Exception:
        pass


def open_latest_release():
    if not latest_release_url:
        return
    try:
        webbrowser.open(latest_release_url)
    except Exception:
        pass


user32 = ctypes.windll.user32


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def find_window(title: str):
    return user32.FindWindowW(None, title)


def get_window_rect(hwnd):
    rect = RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return (rect.left, rect.top, rect.right, rect.bottom)
    return None


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def ensure_running_as_admin_or_exit():
    if is_admin():
        return

    console.print("[yellow][!] Administrator permission is required.[/yellow]")
    console.print("[dim]Press any key to continue and restart as Administrator...[/dim]")
    try:
        msvcrt.getch()
    except Exception:
        input()

    console.print("[yellow][!] Restarting as Administrator...[/yellow]")

    if getattr(sys, "frozen", False):
        executable = sys.executable
        params = " ".join(f'"{arg}"' for arg in sys.argv[1:])
    else:
        executable = sys.executable
        script = sys.argv[0]
        params = " ".join([f'"{script}"'] + [f'"{arg}"' for arg in sys.argv[1:]])

    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            executable,
            params,
            None,
            1,
        )
        if result <= 32:
            raise OSError(f"ShellExecuteW failed with code {result}")
    except Exception:
        console.print("[red][!] Failed to elevate privileges.[/red]")
        sys.exit(1)

    sys.exit(0)


current_bbox = None
target_ready = threading.Event()
target_focused = threading.Event()
target_undetected = threading.Event()
current_target_hwnd = None
current_target_ui_state = None


EVENT_SYSTEM_FOREGROUND = 0x0003
EVENT_OBJECT_SHOW = 0x8002
EVENT_OBJECT_DESTROY = 0x8001
WINEVENT_OUTOFCONTEXT = 0x0000
OBJID_WINDOW = 0
def _set_target_state(ready: bool, focused: bool):
    global current_bbox, current_target_ui_state
    if not ready:
        target_ready.clear()
        target_focused.clear()
        target_undetected.set()
        current_bbox = None
        if current_target_ui_state != "UNDETECTED":
            current_target_ui_state = "UNDETECTED"
            UIManager.set_target_state("UNDETECTED")
        return

    target_ready.set()
    target_undetected.clear()
    if focused:
        target_focused.set()
        if current_target_ui_state != "FOCUSED":
            current_target_ui_state = "FOCUSED"
            UIManager.set_target_state("FOCUSED")
    else:
        target_focused.clear()
        if current_target_ui_state != "UNFOCUSED":
            current_target_ui_state = "UNFOCUSED"
            UIManager.set_target_state("UNFOCUSED")


def _refresh_target_state():
    global current_bbox, current_target_hwnd
    hwnd = find_window(_TARGET_WINDOW_TITLE)
    if not hwnd:
        current_target_hwnd = None
        _set_target_state(False, False)
        return

    current_target_hwnd = hwnd
    if current_bbox is None:
        current_bbox = get_window_rect(hwnd)
    fg = user32.GetForegroundWindow()
    is_focused = False
    if fg:
        try:
            is_focused = (fg == hwnd) or bool(user32.IsChild(hwnd, fg))
        except Exception:
            is_focused = (fg == hwnd)
    _set_target_state(True, is_focused)


class TargetEventMonitor:
    def __init__(self):
        self._thread = None
        self._hooks = []
        self._proc = None
        self._lock = threading.Lock()

    def _emit_state_if_changed(self):
        _refresh_target_state()

    def _callback(self, hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
        if idObject != OBJID_WINDOW and event in (EVENT_OBJECT_SHOW, EVENT_OBJECT_DESTROY):
            return
        if event in (EVENT_OBJECT_SHOW, EVENT_OBJECT_DESTROY):
            if current_target_hwnd is not None and hwnd != current_target_hwnd:
                return
        self._emit_state_if_changed()

    def _run(self):
        WinEventProcType = ctypes.WINFUNCTYPE(
            None,
            ctypes.wintypes.HANDLE,
            ctypes.wintypes.DWORD,
            ctypes.wintypes.HWND,
            ctypes.wintypes.LONG,
            ctypes.wintypes.LONG,
            ctypes.wintypes.DWORD,
            ctypes.wintypes.DWORD,
        )
        self._proc = WinEventProcType(self._callback)

        user32_local = ctypes.windll.user32
        for evt in (EVENT_SYSTEM_FOREGROUND, EVENT_OBJECT_SHOW, EVENT_OBJECT_DESTROY):
            hook = user32_local.SetWinEventHook(
                evt,
                evt,
                0,
                self._proc,
                0,
                0,
                WINEVENT_OUTOFCONTEXT,
            )
            if hook:
                self._hooks.append(hook)

        self._emit_state_if_changed()

        msg = ctypes.wintypes.MSG()
        while user32_local.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
            user32_local.TranslateMessage(ctypes.byref(msg))
            user32_local.DispatchMessageW(ctypes.byref(msg))

        for hook in self._hooks:
            try:
                user32_local.UnhookWinEvent(hook)
            except Exception:
                pass
        self._hooks.clear()

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = Thread(target=self._run, daemon=True, name="target_event_monitor")
            self._thread.start()


_solver_b_running = False
_solver_b_lock = threading.Lock()

_solver_a_running = False
_solver_a_lock = threading.Lock()

_keypad_running = False
_keypad_lock = threading.Lock()
_keypad_cancel_event = threading.Event()
_pressed_keys = set()


def _run_guarded(lock, flag_name, target, *args):
    g = globals()
    with lock:
        if g[flag_name]:
            return False
        g[flag_name] = True

    def _runner():
        try:
            target(*args)
        finally:
            with lock:
                g[flag_name] = False

    Thread(target=_runner, daemon=True).start()
    return True


def _require_target(fn):
    def wrapper():
        if not target_ready.is_set():
            return False
        if not target_focused.is_set():
            return False
        result = fn()
        if result is None:
            return True
        return bool(result)

    return wrapper


@_require_target
def job_warp():
    def _run():
        run_job_warp(cancel_event=target_undetected)

    Thread(
        target=_run,
        daemon=True,
    ).start()
    return True


@_require_target
def cayo_solve():
    def _run():
        UIManager.set_solver_b_running(True)
        try:
            solve_cayo(current_bbox, cancel_event=target_undetected)
        finally:
            UIManager.set_solver_b_running(False)

    return _run_guarded(_solver_b_lock, "_solver_b_running", _run)


@_require_target
def casino_solve():
    def _run():
        UIManager.set_solver_a_running(True)
        try:
            solve_casino(current_bbox, cancel_event=target_undetected)
        finally:
            UIManager.set_solver_a_running(False)

    return _run_guarded(_solver_a_lock, "_solver_a_running", _run)


@_require_target
def keypad_solve():
    global _keypad_running
    with _keypad_lock:
        if _keypad_running:
            _keypad_cancel_event.set()
            return True
        _keypad_running = True
        _keypad_cancel_event.clear()

    def _run():
        UIManager.set_keypad_running(True)
        try:
            solve_keypad(
                current_bbox,
                cancel_event=_keypad_cancel_event,
                status_callback=UIManager.set_keypad_status,
            )
        finally:
            global _keypad_running
            with _keypad_lock:
                _keypad_running = False
                _keypad_cancel_event.clear()
            UIManager.set_keypad_running(False)

    Thread(target=_run, daemon=True).start()
    return True


@_require_target
def nosave_toggle():
    def _run():
        toggle_nosave(cancel_event=target_undetected)

    Thread(target=_run, daemon=True).start()
    return True


def anti_afk_toggle():
    enabled = toggle_anti_afk(
        is_target_ready=lambda: target_ready.is_set(),
        get_target_hwnd=lambda: current_target_hwnd,
    )
    UIManager.set_anti_afk_state("ACTIVE" if enabled else "INACTIVE")
    return True


def shutdown():
    _keypad_cancel_event.set()

    try:
        stop_anti_afk()
        UIManager.set_anti_afk_state("INACTIVE")
    except Exception:
        pass

    try:
        force_disable_nosave()
    except Exception:
        pass

    sys.exit(0)


def _toggle_debug_hotkey():
    enabled = toggle_debug()
    UIManager.set_debug_state("ENABLED" if enabled else "DISABLED")


def _normalize_key(key):
    key_char = getattr(key, "char", None)
    if key_char is not None:
        return str(key_char).lower()
    key_name = getattr(key, "name", None)
    if key_name is not None:
        return str(key_name).lower()
    return str(key).lower()


def _is_modifier_key(key):
    return _normalize_key(key) in {
        "shift",
        "shift_l",
        "shift_r",
        "ctrl",
        "ctrl_l",
        "ctrl_r",
        "alt",
        "alt_l",
        "alt_r",
        "alt_gr",
    }


def _dispatch_hotkey(key):
    key_name = _normalize_key(key)
    if key == pynput_keyboard.Key.end:
        shutdown()
        return

    is_shift = "shift" in _pressed_keys or "shift_l" in _pressed_keys or "shift_r" in _pressed_keys
    is_ctrl = "ctrl" in _pressed_keys or "ctrl_l" in _pressed_keys or "ctrl_r" in _pressed_keys
    is_alt = "alt" in _pressed_keys or "alt_l" in _pressed_keys or "alt_r" in _pressed_keys or "alt_gr" in _pressed_keys

    if key == pynput_keyboard.Key.f5:
        if is_ctrl and is_alt:
            anti_afk_toggle()
        elif is_shift:
            show_readme()
        elif not is_ctrl and not is_alt:
            job_warp()
        return

    if key == pynput_keyboard.Key.f6:
        if is_ctrl and not is_shift and not is_alt:
            keypad_solve()
        elif not is_shift and not is_ctrl and not is_alt:
            casino_solve()
        return

    if key == pynput_keyboard.Key.f7:
        if not is_shift and not is_ctrl and not is_alt:
            cayo_solve()
        return

    if key == pynput_keyboard.Key.f8:
        if is_ctrl and is_alt and not is_shift:
            _toggle_debug_hotkey()
        elif not is_shift and not is_ctrl and not is_alt:
            if not target_ready.is_set() or not target_focused.is_set():
                return
            nosave_toggle()
        return

    if key_name == "k" and is_ctrl and is_alt:
        anti_afk_toggle()
        return


def _on_press(key):
    if _is_modifier_key(key):
        _pressed_keys.add(_normalize_key(key))
        return

    _dispatch_hotkey(key)


def _on_release(key):
    if _is_modifier_key(key):
        _pressed_keys.discard(_normalize_key(key))


def update_monitor():
    global latest_release_url, _update_notice_initialized
    with _update_notice_lock:
        if _update_notice_initialized:
            return
        _update_notice_initialized = True

    notice = ""
    try:
        available, latest_tag, release_url = get_update_status()
        latest_release_url = release_url or RELEASES_URL
        if available and latest_tag:
            notice = (
                f"Update available ({latest_tag}) - press CTRL + ALT + F5 to open release"
            )
    except Exception:
        latest_release_url = RELEASES_URL

    UIManager.set_update_notice(notice)


def main():
    hotkey_map = {
        "show_readme": "shift+f5",
        "show_release": "ctrl+alt+f5",
        "job_warp": "f5",
        "casino": "f6",
        "keypad": "ctrl+f6",
        "cayo": "f7",
        "toggle_nosave": "f8",
        "toggle_debug": "ctrl+alt+f8",
        "toggle_anti_afk": "ctrl+alt+f5",
        "exit": "end",
    }

    set_debug(DEBUG_ENABLED)
    ensure_running_as_admin_or_exit()
    UIManager.init_dashboard(APP_TITLE, VERSION, hotkey_map)
    UIManager.set_debug_state("ENABLED" if get_debug_enabled() else "DISABLED")
    UIManager.set_anti_afk_state("INACTIVE")
    run_nosave_startup_check()

    Thread(target=update_monitor, daemon=True).start()

    target_monitor = TargetEventMonitor()
    target_monitor.start()

    hotkey_listener = pynput_keyboard.Listener(
        on_press=_on_press,
        on_release=_on_release,
        daemon=True,
    )
    hotkey_listener.start()
    hotkey_listener.join()
