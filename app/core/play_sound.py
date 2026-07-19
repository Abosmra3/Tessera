import os
import queue
import sys
import threading
from pathlib import Path

__all__ = ["play_sound", "cleanup_sound_worker"]


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


class _SoundWorker:
    def __init__(self):
        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        if os.name != "nt":
            return
        try:
            import winsound
        except Exception:
            return

        while True:
            try:
                item = self._queue.get()
                if item is None:
                    break
                sound_path = item
                try:
                    winsound.PlaySound(
                        str(sound_path),
                        winsound.SND_FILENAME,
                    )
                except Exception:
                    pass
            except Exception:
                break

    def play(self, sound_path: Path):
        try:
            self._queue.put(sound_path)
        except Exception:
            pass

    def cleanup(self):
        try:
            self._queue.put(None)
            if os.name == "nt":
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass


_worker = None
_worker_lock = threading.Lock()


def _get_worker():
    global _worker
    with _worker_lock:
        if _worker is None:
            _worker = _SoundWorker()
        return _worker


def play_sound(filename: str):
    if os.name != "nt":
        return
    if not isinstance(filename, str):
        return
    filename = filename.strip()
    if not filename:
        return

    assets_dir = _resolve_assets_dir()
    sound_path = _resolve_sound_path(assets_dir, filename)
    if sound_path is None:
        return

    worker = _get_worker()
    worker.play(sound_path)


def cleanup_sound_worker():
    global _worker
    with _worker_lock:
        if _worker is not None:
            try:
                _worker.cleanup()
            except Exception:
                pass
            _worker = None
