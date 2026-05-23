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
from app.solvers.cayo import solve_cayo
from app.solvers.casino import solve_casino
from app.helpers.anti_afk import toggle_anti_afk, stop_anti_afk
from app.helpers.job_warp import run_job_warp
from app.helpers.nosave import (
    toggle_nosave,
    run_nosave_startup_check,
    force_disable_nosave,
)
from app.ui.terminal_ui import UIManager, console

_shift_down = False

VERSION = APP_VERSION
APP_TITLE = "Tessera"

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
    if _shift_down:
        return False

    def _run():
        run_job_warp(cancel_event=target_undetected)

    Thread(
        target=_run,
        daemon=True,
    ).start()
    return True


@_require_target
def cayo_solve():
    if _shift_down:
        return False
    def _run():
        UIManager.set_solver_b_running(True)
        try:
            solve_cayo(current_bbox, cancel_event=target_undetected)
        finally:
            UIManager.set_solver_b_running(False)

    return _run_guarded(_solver_b_lock, "_solver_b_running", _run)


@_require_target
def casino_solve():
    if _shift_down:
        return False
    def _run():
        UIManager.set_solver_a_running(True)
        try:
            solve_casino(current_bbox, cancel_event=target_undetected)
        finally:
            UIManager.set_solver_a_running(False)

    return _run_guarded(_solver_a_lock, "_solver_a_running", _run)


@_require_target
def nosave_toggle():
    if _shift_down:
        return False

    def _run():
        toggle_nosave(cancel_event=target_undetected)

    Thread(target=_run, daemon=True).start()
    return True


def anti_afk_toggle():
    if _shift_down:
        return False

    enabled = toggle_anti_afk(
        is_target_ready=lambda: target_ready.is_set(),
        get_target_hwnd=lambda: current_target_hwnd,
    )
    UIManager.set_anti_afk_state("ACTIVE" if enabled else "INACTIVE")
    return True


def shutdown():
    if _shift_down:
        return

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


def _on_press(key):
    global _shift_down
    if key in (
        pynput_keyboard.Key.shift,
        pynput_keyboard.Key.shift_l,
        pynput_keyboard.Key.shift_r,
    ):
        _shift_down = True


def _on_release(key):
    global _shift_down
    if key in (
        pynput_keyboard.Key.shift,
        pynput_keyboard.Key.shift_l,
        pynput_keyboard.Key.shift_r,
    ):
        _shift_down = False


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
        "cayo": "f7",
        "toggle_nosave": "f8",
        "toggle_anti_afk": "ctrl+alt+k",
        "exit": "end",
    }

    ensure_running_as_admin_or_exit()
    UIManager.init_dashboard(APP_TITLE, VERSION, hotkey_map)
    UIManager.set_anti_afk_state("INACTIVE")
    run_nosave_startup_check()

    Thread(target=update_monitor, daemon=True).start()

    target_monitor = TargetEventMonitor()
    target_monitor.start()

    shift_listener = pynput_keyboard.Listener(
        on_press=_on_press,
        on_release=_on_release,
        daemon=True,
    )
    shift_listener.start()

    hotkeys = pynput.keyboard.GlobalHotKeys(
        {
            "<shift>+<f5>": show_readme,
            "<ctrl>+<alt>+<f5>": open_latest_release,
            "<f5>": job_warp,
            "<f6>": casino_solve,
            "<f7>": cayo_solve,
            "<f8>": nosave_toggle,
            "<ctrl>+<alt>+k": anti_afk_toggle,
            "<end>": shutdown,
        }
    )

    hotkeys.start()
    hotkeys.join()
