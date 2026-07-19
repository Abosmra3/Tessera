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

_GTA_PROCESS_NAME = "GTA5.exe"
_GTA_TITLE_SUBSTRINGS = ["grand theft auto v"]

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


def _find_gta_hwnd():
    """Find GTA V's main window by process name first, then title substring."""
    import ctypes.wintypes

    psapi = ctypes.windll.psapi
    kernel32 = ctypes.windll.kernel32

    found_hwnd = [None]

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

    def _enum_callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        # Get window title
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.lower()

        # Check title substring first (fast path)
        title_match = any(sub in title for sub in _GTA_TITLE_SUBSTRINGS)

        if not title_match:
            return True

        # Verify by process name
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        hproc = kernel32.OpenProcess(0x0400 | 0x0010, False, pid.value)  # QUERY_INFO | VM_READ
        if hproc:
            try:
                name_buf = ctypes.create_unicode_buffer(260)
                if psapi.GetModuleBaseNameW(hproc, None, name_buf, 260):
                    if name_buf.value.lower() == _GTA_PROCESS_NAME.lower():
                        found_hwnd[0] = hwnd
                        return False  # Stop enumeration
                # Fallback: accept by title alone if process name unreadable
                found_hwnd[0] = hwnd
                return False
            finally:
                kernel32.CloseHandle(hproc)
        else:
            # Can't open process — accept by title
            found_hwnd[0] = hwnd
            return False
        return True

    user32.EnumWindows(EnumWindowsProc(_enum_callback), 0)
    return found_hwnd[0]


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
    hwnd = _find_gta_hwnd()
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


def kill_game():
    """Force-terminate the detected GTA V process using its known window handle."""
    import subprocess
    import ctypes.wintypes

    hwnd = current_target_hwnd
    if not hwnd:
        return  # Game not detected, nothing to kill

    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return

    try:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        subprocess.run(
            ["taskkill", "/F", "/PID", str(pid.value)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            timeout=5,
        )

    except Exception:
        pass


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


CURRENT_HOTKEYS = {}

DEFAULT_HOTKEYS = {
    "job_warp": "f5",
    "casino": "f6",
    "keypad": "ctrl+f6",
    "cayo": "f7",
    "toggle_nosave": "f8",
    "toggle_anti_afk": "ctrl+f5",
    "kill_game": "",
    "exit": "end",
    "toggle_debug": "",
}

DEFAULT_HIDDEN_ACTIONS = ["toggle_debug"]


def get_keybinds_filepath():
    import os
    appdata = os.environ.get("APPDATA")
    if not appdata:
        appdata = os.path.expanduser("~")
    folder = os.path.join(appdata, "Tessera")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "keybinds.json")


CURRENT_HIDDEN_ACTIONS = []


def load_keybinds(defaults, default_hidden=None):
    import os
    import json
    global CURRENT_HIDDEN_ACTIONS
    CURRENT_HIDDEN_ACTIONS = list(default_hidden) if default_hidden else []
    path = get_keybinds_filepath()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    raw_hidden = data.get("hidden_actions", [])
                    if isinstance(raw_hidden, list):
                        CURRENT_HIDDEN_ACTIONS = [str(a).strip().lower() for a in raw_hidden]

                    merged = dict(defaults)
                    seen_combos = set()
                    has_duplicates = False
                    for k in defaults.keys():
                        if k in data:
                            combo = str(data[k]).lower().strip()
                            if combo:
                                if combo in seen_combos:
                                    merged[k] = ""  # Unbind duplicate
                                    has_duplicates = True
                                else:
                                    merged[k] = combo
                                    seen_combos.add(combo)
                            else:
                                merged[k] = ""
                        else:
                            pass

                    if has_duplicates:
                        save_keybinds(merged, CURRENT_HIDDEN_ACTIONS)
                    return merged
        except Exception:
            pass
    return dict(defaults)


def save_keybinds(keybinds, hidden_actions):
    import os
    import json
    path = get_keybinds_filepath()
    try:
        data = dict(keybinds)
        data["hidden_actions"] = list(hidden_actions)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return True
    except Exception:
        return False


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
    
    is_shift = any(k in _pressed_keys for k in ("shift", "shift_l", "shift_r"))
    is_ctrl = any(k in _pressed_keys for k in ("ctrl", "ctrl_l", "ctrl_r"))
    is_alt = any(k in _pressed_keys for k in ("alt", "alt_l", "alt_r", "alt_gr"))

    parts = []
    if is_ctrl:
        parts.append("ctrl")
    if is_alt:
        parts.append("alt")
    if is_shift:
        parts.append("shift")
    parts.append(key_name)
    pressed_combo = "+".join(parts)

    action = None
    for act, combo in CURRENT_HOTKEYS.items():
        if combo == pressed_combo:
            action = act
            break

    if action is None:
        return

    if action == "job_warp":
        job_warp()
    elif action == "casino":
        casino_solve()
    elif action == "keypad":
        keypad_solve()
    elif action == "cayo":
        cayo_solve()
    elif action == "toggle_nosave":
        if not target_ready.is_set() or not target_focused.is_set():
            return
        nosave_toggle()
    elif action == "toggle_debug":
        _toggle_debug_hotkey()
    elif action == "toggle_anti_afk":
        anti_afk_toggle()
    elif action == "kill_game":
        kill_game()
    elif action == "exit":
        shutdown()


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
                f'<span style="color: #fbbf24; font-weight: bold;">Update available ({latest_tag})</span> - '
                f'<a href="{latest_release_url}" style="color: #38bdf8; text-decoration: underline; font-weight: bold;">click here</a> to download'
            )
    except Exception:
        latest_release_url = RELEASES_URL

    UIManager.set_update_notice(notice)


def main():
    if not check_single_instance():
        sys.exit(0)

    default_hidden_actions = DEFAULT_HIDDEN_ACTIONS

    global CURRENT_HOTKEYS
    CURRENT_HOTKEYS = load_keybinds(DEFAULT_HOTKEYS, default_hidden=default_hidden_actions)

    # Pre-create keybinds file if it does not exist
    import os
    if not os.path.exists(get_keybinds_filepath()):
        save_keybinds(CURRENT_HOTKEYS, CURRENT_HIDDEN_ACTIONS)

    def on_hotkeys_changed(new_hotkeys, new_hidden):
        global CURRENT_HOTKEYS, CURRENT_HIDDEN_ACTIONS
        CURRENT_HOTKEYS.clear()
        CURRENT_HOTKEYS.update(new_hotkeys)
        CURRENT_HIDDEN_ACTIONS = list(new_hidden)
        save_keybinds(CURRENT_HOTKEYS, CURRENT_HIDDEN_ACTIONS)

    set_debug(DEBUG_ENABLED)
    ensure_running_as_admin_or_exit()
    UIManager.init_dashboard(APP_TITLE, VERSION, CURRENT_HOTKEYS, CURRENT_HIDDEN_ACTIONS)
    UIManager.register_cleanup_callback(shutdown)
    UIManager.register_hotkeys_changed_callback(on_hotkeys_changed)
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
