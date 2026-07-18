import cv2
import time
import keyboard
import numpy as np
from PIL import ImageGrab

from app.core.debug import debug_print as _debug_print

__all__ = ["solve_cayo"]

                          
_targets = [
    (907, y1, 1562, y2)
    for y1, y2 in [
        (331, 431),
        (404, 504),
        (500, 600),
        (560, 660),
        (627, 727),
        (697, 809),
        (780, 883),
        (863, 975),
    ]
]

                
_scan = [(424, 360 + 76 * i, 810, 415 + 76 * i) for i in range(8)]


def _grab_with_pil(bbox):
    return ImageGrab.grab(bbox)


def _best_match_index(part, templates, threshold=0.65):
    """Return best template index or -1 if below threshold."""
    best_idx = -1
    best_score = threshold

    for i, tpl in enumerate(templates):
        _, score, _, _ = cv2.minMaxLoc(
            cv2.matchTemplate(tpl, part, cv2.TM_CCOEFF_NORMED)
        )
        if score > best_score:
            best_score = score
            best_idx = i

    return best_idx


def solve_cayo(bbox, cancel_event=None):
    if cancel_event is not None and cancel_event.is_set():
        return
    if bbox is None:
        return

    _debug_print('[*] START solve_cayo')
    _debug_print(f'[*] bbox={bbox}')

    raw = np.array(_grab_with_pil(bbox))
    gray = cv2.cvtColor(raw, cv2.COLOR_RGB2GRAY)
    gray = cv2.resize(gray, (1920, 1080), interpolation=cv2.INTER_AREA)
    _debug_print(f'[*] captured frame shape={gray.shape}')

                                        
    templates = []
    for x1, y1, x2, y2 in _targets:
        part = gray[y1:y2, x1:x2]
        part = cv2.resize(part, None, fx=0.91, fy=0.91)
        templates.append(part)

    scans = [
        gray[y1:y2, x1:x2]
        for (x1, y1, x2, y2) in _scan
    ]
    _debug_print(f'[*] created {len(templates)} templates and {len(scans)} scan regions')

    moves = []

    for i, scan_img in enumerate(scans):
        j = _best_match_index(scan_img, templates)
        if j == -1:
            continue

                                
        diff = i - j
        path = min(diff, diff - 8, diff + 8, key=abs)

        if path:
            key = 'd' if path > 0 else 'a'
            moves.extend([key] * abs(path))

        _debug_print(f'[*] scan {i} -> match {j}, diff {diff}, path {path}')
        moves.append('s')

                             
    if moves and moves[-1] == 's':
        moves.pop()

    _debug_print(f'[*] computed moves={moves}')

    for key in moves:
        if cancel_event is not None and cancel_event.is_set():
            return
        _debug_print(f'[*] pressing {key}')
        keyboard.press(key)
        time.sleep(0.05)
        keyboard.release(key)
        time.sleep(0.05)

    _debug_print('[*] END solve_cayo')
