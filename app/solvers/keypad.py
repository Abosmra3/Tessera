import cv2
import time
import keyboard
import numpy as np
from PIL import ImageGrab

from app.core.debug import debug_print as _debug_print

# Normalized coordinate ratios relative to standard canvas and cropped keypad bounds
NORM_KEYPAD_BOX = (454 / 1920.0, 300 / 1080.0, 1080 / 1920.0, 830 / 1080.0)
NORM_HEIGHTS = [h / 530.0 for h in [2, 110, 218, 326, 434]]
NORM_LENGTHS = [l / 626.0 for l in [50, 158, 266, 374, 482, 590]]
NORM_CHECK_POINT = (44 / 626.0, 92 / 530.0)

CAPTURE_INTERVAL = 0.1
CAPTURE_DURATION = 3.0
REQUIRED_REPEATS = 3
ROUND_DELAY = 4.0


def _sleep_with_cancel(duration, cancel_event=None):
    deadline = time.time() + duration
    while time.time() < deadline:
        if cancel_event is not None and cancel_event.is_set():
            return False
        time.sleep(min(0.1, deadline - time.time()))
    return True


def _build_digits_lookup(row_count):
    return {
        tuple(1 if row_index == active_row else 0 for row_index in range(row_count)): active_row + 1
        for active_row in range(row_count)
    }


def _sample_point(img, row_index, column_index):
    h, w = img.shape[:2]
    py = int(NORM_HEIGHTS[row_index] * h)
    px = int(NORM_LENGTHS[column_index] * w)
    return img[py:py + 1, px:px + 1]


def _prepare_keypad_image(image):
    hsv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2HSV)

    lower = np.array([50, 50, 50])
    upper = np.array([96, 255, 255])

    mask = cv2.inRange(hsv, lower, upper)
    mintimg = cv2.bitwise_and(np.array(image), np.array(image), mask=mask)

    gray_image = cv2.cvtColor(mintimg, cv2.COLOR_RGB2GRAY)
    (_, black_and_white_image) = cv2.threshold(gray_image, 215, 255, cv2.THRESH_BINARY)
    return black_and_white_image


def _column_has_dot(img, column_index, row_count):
    for row_index in range(row_count):
        if np.mean(_sample_point(img, row_index, column_index)) == 255:
            return True
    return False


def detect_grid_size(img):
    active_columns = sum(
        1
        for column_index in range(len(NORM_LENGTHS))
        if _column_has_dot(img, column_index, len(NORM_HEIGHTS))
    )

    if active_columns == 6:
        return 5, 6
    if active_columns == 5:
        return 4, 5

    raise KeyError(f"Unsupported keypad width detected: {active_columns}")


def dot_check(column_index, img, row_count):
    hint = []

    for row_index in range(row_count):
        crop_img = _sample_point(img, row_index, column_index)

        if np.mean(crop_img) == 255:
            hint.append(1)
        else:
            hint.append(0)

    return _build_digits_lookup(row_count)[tuple(hint)]


def decode_pattern(img):
    row_count, column_count = detect_grid_size(img)
    numbers = []

    for column_index in range(column_count):
        numbers.append(dot_check(column_index, img, row_count))

    return row_count, column_count, tuple(numbers)


def capture_keypad_pattern(bbox, duration=CAPTURE_DURATION, interval=CAPTURE_INTERVAL, cancel_event=None):
    deadline = time.time() + duration
    last_pattern = None
    flashes = []
    pattern_counts = {}

    while time.time() < deadline:
        if cancel_event is not None and cancel_event.is_set():
            return None
        im = ImageGrab.grab(bbox)
        im = im.resize((1920, 1080))
        w, h = im.size
        nx1, ny1, nx2, ny2 = NORM_KEYPAD_BOX
        screen = im.crop((int(nx1 * w), int(ny1 * h), int(nx2 * w), int(ny2 * h)))
        black_and_white_image = _prepare_keypad_image(screen)

        try:
            pattern = decode_pattern(black_and_white_image)
        except KeyError:
            pattern = None

        if pattern != last_pattern:
            last_pattern = pattern
            if pattern is not None:
                flashes.append(pattern)
                pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
                row_count, column_count, numbers = pattern
                _debug_print(f'[*] Flash {len(flashes)}: {row_count}x{column_count} -> {list(numbers)}')

                if pattern_counts[pattern] >= REQUIRED_REPEATS:
                    return pattern

        if not _sleep_with_cancel(interval, cancel_event):
            return None

    if flashes:
        best_pattern, best_count = max(pattern_counts.items(), key=lambda item: item[1])
        if best_count >= 2:
            return best_pattern
        return flashes[-1]

    raise KeyError('No valid keypad pattern detected during capture window')


def check(bbox, cancel_event=None):
    while True:
        if cancel_event is not None and cancel_event.is_set():
            return False
        im = ImageGrab.grab(bbox)
        im = im.resize((1920, 1080))
        w, h = im.size
        nx1, ny1, nx2, ny2 = NORM_KEYPAD_BOX
        screen = im.crop((int(nx1 * w), int(ny1 * h), int(nx2 * w), int(ny2 * h)))
        grayImage = cv2.cvtColor(np.array(screen), cv2.COLOR_BGR2GRAY)
        (_, blackAndWhiteImage) = cv2.threshold(grayImage, 215, 255, cv2.THRESH_BINARY)

        sw_h, sw_w = blackAndWhiteImage.shape[:2]
        px = int(NORM_CHECK_POINT[0] * sw_w)
        py = int(NORM_CHECK_POINT[1] * sw_h)
        crop_img = blackAndWhiteImage[py:py + 1, px:px + 1]

        if np.mean(crop_img) == 0:
            keyboard.press_and_release('w')
            if not _sleep_with_cancel(0.025, cancel_event):
                return False
        elif np.mean(crop_img) == 255:
            return True


def calculate(numbers, cancel_event=None):
    keyboardgo = []

    for i in range(len(numbers)):
        if i == 0:
            keyboardgo.extend(['s'] * (numbers[i] - 1))
        if i > 0:
            a = i - 1
            if numbers[i] == numbers[a]:
                keyboardgo.append('1')
            elif numbers[i] < numbers[a]:
                value = numbers[a] - numbers[i]
                for _ in range(value):
                    keyboardgo.append('w')
            elif numbers[i] > numbers[a]:
                value = numbers[i] - numbers[a]
                for _ in range(value):
                    keyboardgo.append('s')
        keyboardgo.append('return')

    _debug_print(f'[*] computed moves={keyboardgo}')
    for key in keyboardgo:
        if cancel_event is not None and cancel_event.is_set():
            return False
        keyboard.press_and_release(key)
        if key in ('s', 'w'):
            if not _sleep_with_cancel(0.025, cancel_event):
                return False
        if key == 'return':
            if not _sleep_with_cancel(0.1, cancel_event):
                return False

    return True


def main(bbox, cancel_event=None, status_callback=None):
    try:
        total_rounds = None

        for round_index in range(1, 5):
            if cancel_event is not None and cancel_event.is_set():
                return

            _debug_print(f'[*] Capturing keypad flashes every {CAPTURE_INTERVAL:.1f}s for {CAPTURE_DURATION:.1f}s')
            pattern = capture_keypad_pattern(bbox, cancel_event=cancel_event)
            if pattern is None:
                return

            row_count, column_count, numbers = pattern
            if total_rounds is None:
                total_rounds = 3 if (row_count, column_count) == (4, 5) else 4
                _debug_print(f'[*] Detected layout {row_count}x{column_count}; running {total_rounds} total rounds')

            _debug_print(f'[*] Locked keypad layout: {row_count}x{column_count} -> {list(numbers)}')

            if not check(bbox, cancel_event=cancel_event):
                return
            if not calculate(list(numbers), cancel_event=cancel_event):
                return

            if status_callback is not None:
                rounds_left = total_rounds - round_index
                if rounds_left > 0:
                    status_callback(f"{rounds_left} LEFT")

            if round_index >= total_rounds:
                break

            _debug_print(f'[*] Waiting {ROUND_DELAY:.1f}s before next capture')
            if not _sleep_with_cancel(ROUND_DELAY, cancel_event):
                return
    except KeyError as e:
        _debug_print(f'[!] Cyan pattern not detected: {e} - current resolution {bbox[2]}x{bbox[3]}')
        if status_callback is not None:
            status_callback("FAIL")
            if not _sleep_with_cancel(3.0, cancel_event):
                return
            status_callback("READY")


def solve_keypad(bbox, cancel_event=None, status_callback=None):
    if cancel_event is not None and cancel_event.is_set():
        return
    if bbox is None:
        return

    _debug_print('[*] START solve_keypad')
    _debug_print(f'[*] bbox={bbox}')
    try:
        main(bbox, cancel_event=cancel_event, status_callback=status_callback)
    finally:
        _debug_print('[*] END solve_keypad')
