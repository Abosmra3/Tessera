import cv2
import time
import keyboard
import numpy as np
from PIL import ImageGrab

from app.core.debug import debug_print as _debug_print

__all__ = ["solve_cayo"]

                          
# Normalized coordinate ratios (0.0 to 1.0) relative to standard 16:9 canvas
NORM_TARGETS = [
    (907 / 1920.0, y1 / 1080.0, 1562 / 1920.0, y2 / 1080.0)
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

NORM_SCANS = [
    (424 / 1920.0, (360 + 76 * i) / 1080.0, 810 / 1920.0, (415 + 76 * i) / 1080.0)
    for i in range(8)
]


def _grab_with_pil(bbox):
    return ImageGrab.grab(bbox)


def _to_pixels(norm_box, width, height):
    nx1, ny1, nx2, ny2 = norm_box
    return int(nx1 * width), int(ny1 * height), int(nx2 * width), int(ny2 * height)


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
    h, w = gray.shape[:2]
    _debug_print(f'[*] captured frame shape={gray.shape}')

    templates = []
    for norm_box in NORM_TARGETS:
        x1, y1, x2, y2 = _to_pixels(norm_box, w, h)
        part = gray[y1:y2, x1:x2]
        part = cv2.resize(part, None, fx=0.91, fy=0.91)
        templates.append(part)

    scans = [
        gray[y1:y2, x1:x2]
        for (x1, y1, x2, y2) in [_to_pixels(box, w, h) for box in NORM_SCANS]
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
