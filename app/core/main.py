import sys
import webbrowser
import ctypes
import ctypes.wintypes
import threading
from threading import Thread

from PyQt6.QtCore import QSharedMemory
from PyQt6.QtWidgets import QApplication
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
from app.ui.gui import UIManager

VERSION = APP_VERSION
APP_TITLE = "Tessera"
DEBUG_ENABLED = "--debug" in sys.argv[1:]

_TARGET_WINDOW_TITLE = "Grand Theft Auto V"

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


_shared_memory = None


def check_single_instance() -> bool:
    global _shared_memory
    if QApplication.instance() is None:
        _app = QApplication(sys.argv)
    _shared_memory = QSharedMemory("TesseraSingleInstanceKey")
    if not _shared_memory.create(1):
        hwnd = ctypes.windll.user32.FindWindowW(None, "Tessera")
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        ctypes.windll.user32.MessageBoxW(
            None,
            "Tessera is already running.",
            "Tessera",
            0x40 | 0x0
        )
        return False
    return True


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def ensure_running_as_admin_or_exit():
    if is_admin():
        return

    if getattr(sys, "frozen", False):
        executable = sys.executable
        params = " ".join(f'"{arg}"' for arg in sys.argv[1:])
    else:
        executable = sys.executable
        if executable.lower().endswith("python.exe"):
            executable = executable[:-10] + "pythonw.exe"
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
        ctypes.windll.user32.MessageBoxW(
            None,
            "Administrator permission is required to run this application. Please restart as Administrator.",
            "Permission Required",
            0x10 | 0x0
        )
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


class GuardedTask:
    """Encapsulates execution state and locking for background solver threads."""

    def __init__(self, name: str):
        self.name = name
        self._lock = threading.Lock()
        self._running = False

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def run(self, target, *args) -> bool:
        with self._lock:
            if self._running:
                return False
            self._running = True

        def _runner():
            try:
                target(*args)
            finally:
                with self._lock:
                    self._running = False

        Thread(target=_runner, daemon=True, name=f"task_{self.name}").start()
        return True


class ToggleableGuardedTask(GuardedTask):
    """Guarded task that cancels a running instance if triggered again."""

    def __init__(self, name: str):
        super().__init__(name)
        self.cancel_event = threading.Event()

    def toggle_or_run(self, target, *args) -> bool:
        with self._lock:
            if self._running:
                self.cancel_event.set()
                return True
            self._running = True
            self.cancel_event.clear()

        def _runner():
            try:
                target(self.cancel_event, *args)
            finally:
                with self._lock:
                    self._running = False
                    self.cancel_event.clear()

        Thread(target=_runner, daemon=True, name=f"task_{self.name}").start()
        return True

    def cancel(self):
        self.cancel_event.set()


_cayo_task = GuardedTask("cayo")
_casino_task = GuardedTask("casino")
_job_warp_task = ToggleableGuardedTask("job_warp")
_nosave_task = GuardedTask("nosave")
_keypad_task = ToggleableGuardedTask("keypad")
_pressed_keys = set()


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
    def _run(cancel_event):
        run_job_warp(cancel_event=cancel_event)

    return _job_warp_task.toggle_or_run(_run)


@_require_target
def cayo_solve():
    def _run():
        UIManager.set_solver_b_running(True)
        try:
            solve_cayo(current_bbox, cancel_event=target_undetected)
        finally:
            UIManager.set_solver_b_running(False)

    return _cayo_task.run(_run)


@_require_target
def casino_solve():
    def _run():
        UIManager.set_solver_a_running(True)
        try:
            solve_casino(current_bbox, cancel_event=target_undetected)
        finally:
            UIManager.set_solver_a_running(False)

    return _casino_task.run(_run)


@_require_target
def keypad_solve():
    def _run(cancel_event):
        UIManager.set_keypad_running(True)
        try:
            solve_keypad(
                current_bbox,
                cancel_event=cancel_event,
                status_callback=UIManager.set_keypad_status,
            )
        finally:
            UIManager.set_keypad_running(False)

    return _keypad_task.toggle_or_run(_run)


@_require_target
def nosave_toggle():
    def _run():
        toggle_nosave(cancel_event=target_undetected)

    return _nosave_task.run(_run)


def anti_afk_toggle():
    enabled = toggle_anti_afk(
        is_target_ready=lambda: target_ready.is_set(),
        get_target_hwnd=lambda: current_target_hwnd,
    )
    UIManager.set_anti_afk_state("ACTIVE" if enabled else "INACTIVE")
    return True


def shutdown():
    import os
    import subprocess

    _keypad_task.cancel()
    _job_warp_task.cancel()

    try:
        stop_anti_afk()
    except Exception:
        pass

    # Delete the firewall rule directly without acquiring _toggle_lock
    # or updating UI — we're about to kill the process anyway.
    try:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        subprocess.run(
            ["netsh", "advfirewall", "firewall", "delete", "rule", "name=NOSAVE_OUT"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            timeout=5,
        )
    except Exception:
        pass

    # Terminate the overlay child process without acquiring its lock.
    try:
        from app.ui import overlay as _overlay_mod
        proc = _overlay_mod._proc
        if proc is not None and proc.is_alive():
            proc.terminate()
            proc.join(timeout=2)
            if proc.is_alive():
                proc.kill()
    except Exception:
        pass

    try:
        from app.core.play_sound import cleanup_sound_worker
        cleanup_sound_worker()
    except Exception:
        pass

    os._exit(0)


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
            open_latest_release()
        elif is_shift:
            show_readme()
        elif not is_ctrl and not is_alt:
            job_warp()
        return

    if key == pynput_keyboard.Key.f6:
        if is_ctrl and is_alt and not is_shift:
            anti_afk_toggle()
        elif is_ctrl and not is_shift and not is_alt:
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
    if not check_single_instance():
        sys.exit(0)

    hotkey_map = {
        "show_readme": "shift+f5",
        "show_release": "ctrl+alt+f5",
        "job_warp": "f5",
        "casino": "f6",
        "keypad": "ctrl+f6",
        "cayo": "f7",
        "toggle_nosave": "f8",
        "toggle_debug": "ctrl+alt+f8",
        "toggle_anti_afk": "ctrl+alt+f6",
        "exit": "end",
    }

    set_debug(DEBUG_ENABLED)
    ensure_running_as_admin_or_exit()
    UIManager.init_dashboard(APP_TITLE, VERSION, hotkey_map)
    UIManager.register_cleanup_callback(shutdown)
    UIManager.set_debug_state("ENABLED" if get_debug_enabled() else "DISABLED")
    UIManager.set_anti_afk_state("INACTIVE")
    Thread(
        target=run_nosave_startup_check,
        daemon=True,
        name="nosave_startup_check",
    ).start()

    Thread(target=update_monitor, daemon=True).start()

    target_monitor = TargetEventMonitor()
    target_monitor.start()

    hotkey_listener = pynput_keyboard.Listener(
        on_press=_on_press,
        on_release=_on_release,
        daemon=True,
    )
    hotkey_listener.start()

    try:
        UIManager.run_event_loop()
    finally:
        shutdown()
