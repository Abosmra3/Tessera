import keyboard
import time
import threading
from app.ui import overlay
from app.ui.gui import UIManager
from app.core.debug import debug_print as _debug_print

__all__ = ["run_job_warp"]

_run_lock = threading.Lock()
_abort_event = None
_running = False


def _safe_overlay(fn):
    try:
        fn()
    except Exception:
        pass


def _banner_started():
    overlay.banner(
        "Job Warp <b>Started</b> press F5 to abort",
        color="green",
        countdown_seconds=40,
        countdown_template="{message} · {remaining}s",
    )


def _banner_cancelled():
    overlay.banner("Job Warp <b>Cancelled</b>", color="red", duration_ms=3000)


def _banner_done():
    overlay.banner("Job Warp <b>Complete</b>", color="blue", duration_ms=3000)


def _tap_key(key, hold_time=0.05, gap_time=0.05):
    keyboard.press(key)
    time.sleep(hold_time)
    keyboard.release(key)
    time.sleep(gap_time)


def _tap_combo(keys, hold_time=0.05, gap_time=0.05):
    for k in keys:
        keyboard.press(k)
    time.sleep(hold_time)
    for k in reversed(keys):
        keyboard.release(k)
    time.sleep(gap_time)


def _is_cancelled(abort_event, cancel_event=None):
    return abort_event.is_set() or (cancel_event is not None and cancel_event.is_set())


def _wait_with_cancel(seconds: float, abort_event, cancel_event=None, step: float = 0.05) -> bool:
    waited = 0.0
    while waited < seconds:
        if _is_cancelled(abort_event, cancel_event):
            return True
        sleep_for = min(step, seconds - waited)
        time.sleep(sleep_for)
        waited += sleep_for
    return _is_cancelled(abort_event, cancel_event)


def run_job_warp(cancel_event=None):
    global _abort_event, _running

    with _run_lock:
        if _running:
            if _abort_event and not _abort_event.is_set():
                _debug_print("[*] Job Warp: Abort requested by user")
                _abort_event.set()
            return

        _running = True
        _abort_event = threading.Event()
        abort_event = _abort_event
        UIManager.set_job_warp_running(True)

    try:
        _debug_print("[*] START job_warp")
        _safe_overlay(_banner_started)

        if _is_cancelled(abort_event, cancel_event):
            _debug_print("[*] Job Warp: Cancelled before starting")
            return
        _debug_print("[*] Job Warp: Initiating inputs (Space -> Enter -> Alt+F4)")
        _tap_key('space')
        if _is_cancelled(abort_event, cancel_event):
            _debug_print("[*] Job Warp: Cancelled after Space")
            return
        _tap_key('enter')
        if _is_cancelled(abort_event, cancel_event):
            _debug_print("[*] Job Warp: Cancelled after Enter")
            return
        _tap_combo(['alt', 'f4'])

        _debug_print("[*] Job Warp: Waiting 40s for game session alert screen...")
        if _wait_with_cancel(40.0, abort_event, cancel_event):
            _debug_print("[*] Job Warp: Cancelled during wait; pressing ESC to cancel")
            _tap_key('esc')
            _safe_overlay(_banner_cancelled)
            return

        _debug_print("[*] Job Warp: Session alert detected/timeout; pressing ESC to warp")
        _tap_key('esc')
        _safe_overlay(_banner_done)

    finally:
        with _run_lock:
            _running = False
            if _abort_event is abort_event:
                _abort_event = None
        UIManager.set_job_warp_running(False)
        _debug_print("[*] END job_warp")
