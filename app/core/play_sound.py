import multiprocessing
import os
import sys
import threading
from pathlib import Path

CMD_PLAY = "PLAY"

__all__ = ["play_sound"]


def _resolve_assets_dir() -> Path:
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base_dir / "assets"


def _resolve_sound_path(assets_dir: Path, filename: str):
    try:
        name = Path(filename).name
    except Exception:
        return None
    if not name:
        return None
    sound_path = assets_dir / name
    if not sound_path.exists():
        return None
    return sound_path


def _sound_worker(event_queue):
    if os.name != "nt":
        return

    try:
        import winsound
    except Exception:
        return

    assets_dir = _resolve_assets_dir()

    while True:
        try:
            event = event_queue.get()
        except (EOFError, OSError):
            break

        if not isinstance(event, tuple) or len(event) != 2:
            continue

        cmd, payload = event
        if cmd != CMD_PLAY:
            continue

        sound_path = _resolve_sound_path(assets_dir, str(payload))
        if sound_path is None:
            continue

        try:
            winsound.PlaySound(
                str(sound_path),
                winsound.SND_FILENAME | winsound.SND_ASYNC,
            )
        except Exception:
            pass


_ctx = multiprocessing.get_context("spawn")
_proc = None
_queue = None
_lifecycle_lock = threading.Lock()


def _ensure_started():
    global _proc, _queue
    with _lifecycle_lock:
        if _proc is not None and _proc.is_alive():
            return

        _queue = _ctx.Queue()
        _proc = _ctx.Process(target=_sound_worker, args=(_queue,), daemon=True)
        _proc.start()


def _enqueue_event(event):
    _ensure_started()
    with _lifecycle_lock:
        queue_ref = _queue
    if queue_ref is None:
        return
    try:
        queue_ref.put(event)
    except (EOFError, OSError):
        pass


def play_sound(filename: str):
    if os.name != "nt":
        return
    if not isinstance(filename, str):
        return
    filename = filename.strip()
    if not filename:
        return
    _enqueue_event((CMD_PLAY, filename))
