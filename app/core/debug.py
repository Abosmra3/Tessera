DEBUG = False


def set_debug(enabled: bool):
    global DEBUG
    DEBUG = bool(enabled)


def get_debug_enabled() -> bool:
    return bool(DEBUG)


def toggle_debug() -> bool:
    global DEBUG
    DEBUG = not DEBUG
    return bool(DEBUG)


def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)
    try:
        from app.ui.gui import UIManager
        msg = " ".join(str(a) for a in args)
        if msg:
            UIManager.append_debug_line(msg)
    except Exception:
        pass
