import cv2
import time
import keyboard
import numpy as np
from PIL import ImageGrab
from collections import deque, namedtuple

__all__ = ["solve_casino"]

_tofind = (950, 155, 1335, 685)

_parts = [
    [(482, 279, 482 + 102, 279 + 102), (0, 0)],
    [(627, 279, 627 + 102, 279 + 102), (1, 0)],
    [(482, 423, 482 + 102, 423 + 102), (0, 1)],
    [(627, 423, 627 + 102, 423 + 102), (1, 1)],
    [(482, 566, 482 + 102, 566 + 102), (0, 2)],
    [(627, 566, 627 + 102, 566 + 102), (1, 2)],
    [(482, 711, 482 + 102, 711 + 102), (0, 3)],
    [(627, 711, 627 + 102, 711 + 102), (1, 3)],
]


def _grab_with_pil(bbox):
    return ImageGrab.grab(bbox)


def _is_in(img, subimg):
    """Return whether `subimg` exists in `img` above threshold."""
    subimg_gray = cv2.cvtColor(np.array(subimg), cv2.COLOR_BGR2GRAY)
    res = cv2.matchTemplate(img, subimg_gray, cv2.TM_CCOEFF_NORMED)
    threshold = 0.65
    loc = np.where(res >= threshold)
    for _ in zip(*loc[::-1]):
        return True
    return False


def _find_shortest_solution(target_coordinates):
    Point = namedtuple("Point", ("x", "y"))
    ReverseLinkedNode = namedtuple("ReverseLinkedNode", ("value", "prev_node", "idx"))

    rows, cols = 4, 2
    directions = [(0, 1, "s"), (1, 0, "d"), (0, -1, "w"), (-1, 0, "a")]

    target_coordinates = [p if isinstance(p, Point) else Point(*p) for p in target_coordinates]

    target_mask = 0
    for t in target_coordinates:
        target_mask |= 1 << (t.y * cols + t.x)

    current_pos = Point(0, 0)
    visited_mask = 1
    path_head = ReverseLinkedNode(None, None, -1)
                                                                         
    if current_pos in target_coordinates:
        path_head = ReverseLinkedNode("return", path_head, 0)
    queue = deque([(current_pos, visited_mask, path_head)])

    while queue:
        current_pos, visited_mask, path_head = queue.popleft()

        if visited_mask & target_mask == target_mask:
            out = [None] * (path_head.idx + 1)
            while path_head.idx >= 0:
                out[path_head.idx] = path_head.value
                path_head = path_head.prev_node
            return out + ["tab"]

        for dx, dy, key in directions:
            nx = current_pos.x + dx
            ny = current_pos.y + dy
                                                                                 
            if nx == -1:
                nx, ny = cols - 1, ny - 1
            elif nx == cols:
                nx, ny = 0, ny + 1
            ny = ny % rows
            next_pos = Point(nx, ny)

            pos_mask = 1 << (next_pos.y * cols + next_pos.x)
            next_visited_mask = visited_mask | pos_mask
            if visited_mask == next_visited_mask:
                continue

            next_path_head = ReverseLinkedNode(key, path_head, path_head.idx + 1)
            if target_mask & pos_mask:
                next_path_head = ReverseLinkedNode("return", next_path_head, next_path_head.idx + 1)

            queue.append((next_pos, next_visited_mask, next_path_head))

    raise RuntimeError("No solution found")


def solve_casino(bbox, cancel_event=None):
    if cancel_event is not None and cancel_event.is_set():
        return
    if bbox is None:
        return

    im = _grab_with_pil(bbox)
    im = im.resize((1920, 1080))
    sub0_ = im.crop(_tofind)
    sub0 = cv2.cvtColor(
        np.array(
            sub0_.resize(
                (
                    round(sub0_.size[0] * 0.77),
                    round(sub0_.size[1] * 0.77),
                )
            )
        ),
        cv2.COLOR_BGR2GRAY,
    )

    togo = []
    for part_rect, pos in _parts:
        if cancel_event is not None and cancel_event.is_set():
            sub0_.close()
            im.close()
            return
        if _is_in(sub0, im.crop(part_rect)):
            togo.append(pos)

    if cancel_event is not None and cancel_event.is_set():
        sub0_.close()
        im.close()
        return
    sub0_.close()
    im.close()

    moves = _find_shortest_solution(togo)

    for key in moves:
        if cancel_event is not None and cancel_event.is_set():
            return
        keyboard.press(key)
        time.sleep(0.05)
        keyboard.release(key)
        time.sleep(0.05)
