import sys
import ctypes
import multiprocessing
import threading
from queue import Empty
from PyQt6.QtWidgets import QApplication, QWidget, QLabel
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, QPoint, QRectF
from PyQt6.QtGui import QFont, QPainter, QColor, QBrush, QPainterPath, QTextDocument


                 
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x20
WS_EX_NOACTIVATE = 0x08000000

                                                                             
              
                                                                             

ANIM_SLIDE_MS = 180
ANIM_WIDTH_MS = 160
POLL_INTERVAL_MS = 40
AUTO_HIDE_MS = 3000

COLOR_GREEN = QColor(60, 160, 90)
COLOR_RED = QColor(180, 70, 70)
COLOR_BLUE = QColor(80, 140, 220)
COLOR_YELLOW = QColor(196, 168, 64)
COLOR_NEUTRAL = QColor(120, 120, 120)
EVENT_BANNER = "BANNER"
__all__ = ["banner"]

                                                                                        


def _resolve_color(color_value):
    if isinstance(color_value, str):
        name = color_value.strip().lower()
        if name == "green":
            return COLOR_GREEN
        if name == "red":
            return COLOR_RED
        if name == "blue":
            return COLOR_BLUE
        if name == "yellow":
            return COLOR_YELLOW
        if name == "neutral":
            return COLOR_NEUTRAL
        parsed = QColor(color_value)
        if parsed.isValid():
            return parsed
        return COLOR_NEUTRAL

    if isinstance(color_value, (tuple, list)) and len(color_value) == 3:
        try:
            return QColor(int(color_value[0]), int(color_value[1]), int(color_value[2]))
        except (TypeError, ValueError):
            return COLOR_NEUTRAL

    if isinstance(color_value, QColor):
        return color_value

    return COLOR_NEUTRAL


def _serialize_color(color):
    if isinstance(color, str):
        return color
    if isinstance(color, QColor):
        return (color.red(), color.green(), color.blue())
    if isinstance(color, (tuple, list)) and len(color) == 3:
        try:
            return (int(color[0]), int(color[1]), int(color[2]))
        except (TypeError, ValueError):
            return "neutral"
    return "neutral"


def _coerce_duration_ms(value):
    if value is None:
        return None
    try:
        duration = int(value)
    except (TypeError, ValueError):
        return None
    return duration if duration > 0 else None


def _format_countdown_text(template, message, remaining):
    try:
        return str(template).format(message=message, remaining=remaining)
    except Exception:
        return f"{message} · {remaining}s"


class Banner(QWidget):
    """HUD banner widget"""

    def __init__(self, screen_geom, width=130, height=48, margin=12, anim_ms=ANIM_SLIDE_MS):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus)

        self._w = width
        self._h = height
        self.margin = margin
        self.anim_ms = anim_ms
                                                                             
        self._accent_color = QColor(60, 160, 90)

        self.resize(width, height)
        self.screen_geom = screen_geom
                                                                             

               
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.label.setFont(QFont("Segoe UI", 12))
        self.label.setStyleSheet("color: rgba(255,255,255,230); padding-left: 0px;")

                                                                        
        self._text_doc = QTextDocument()
        self._text_doc.setDefaultFont(self.label.font())

              
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.animation.setDuration(anim_ms)

                                                          
        self._width_anim = QPropertyAnimation(self, b"minimumWidth")
        self._width_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._width_anim.setDuration(ANIM_WIDTH_MS)
                                                                     
        self._width_anim_value_slot = None
        self._width_anim_finished_slot = None
        self._animation_finished_slot = None

                                    
        self._off_timer = QTimer()
        self._off_timer.setSingleShot(True)
        self._off_timer.timeout.connect(self.slide_out)

                       
        QTimer.singleShot(0, self._setup_clickthrough)
        QTimer.singleShot(0, self._setup_blur)

                             
        self._update_geometry()
                                                                        
        self._update_positions()
                         
        self.move(self.offscreen_pos)

                                                                             
           
                                                                             

    def _setup_clickthrough(self):
        hwnd = int(self.winId())
        user32 = ctypes.windll.user32

        cur = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        new = cur | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new)

        HWND_TOPMOST = -1
        SWP_NOMOVE = 0x2
        SWP_NOSIZE = 0x1
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE)

    def _setup_blur(self):
        hwnd = int(self.winId())
        try:
            class ACCENT_POLICY(ctypes.Structure):
                _fields_ = [
                    ("AccentState", ctypes.c_int),
                    ("AccentFlags", ctypes.c_int),
                    ("GradientColor", ctypes.c_int),
                    ("AnimationId", ctypes.c_int),
                ]

            class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
                _fields_ = [
                    ("Attribute", ctypes.c_int),
                    ("Data", ctypes.c_void_p),
                    ("SizeOfData", ctypes.c_size_t),
                ]

            ACCENT_ENABLE_ACRYLIC = 4
            SetWCA = getattr(ctypes.windll.user32, "SetWindowCompositionAttribute", None)
            if not SetWCA:
                return

            policy = ACCENT_POLICY()
            policy.AccentState = ACCENT_ENABLE_ACRYLIC
            policy.AccentFlags = 2
            policy.GradientColor = (180 << 24) | (16 << 16) | (16 << 8) | 16

            data = WINDOWCOMPOSITIONATTRIBDATA()
            data.Attribute = 19
            data.Data = ctypes.byref(policy)
            data.SizeOfData = ctypes.sizeof(policy)

            SetWCA(hwnd, ctypes.byref(data))

        except Exception:
            pass

                                                                             
                    
                                                                             

    def _update_geometry(self):
        padding, pill_height, accent_w = self._layout_metrics()

        self._padding = padding
        self._pill_height = pill_height
        self._pill_width = accent_w
        self._pill_radius = accent_w / 2.0

                                        
        self._pill_rect = QRectF(
            float(padding),
            float(padding),
            float(accent_w),
            float(pill_height),
        )
        label_start = padding + accent_w + padding
        self._label_rect = (label_start, 0, max(0, self._w - label_start - padding), self._h)

        self._card_radius = int(self._h * 0.36)
        self._card_rect = QRectF(self.rect())

    def _compute_effective_width(self, text: str) -> int:
        """Compute desired width for `text`, then clamp to available screen width.

        This centralizes the padding/pill/text math and ensures a single clamped width
        is used by callers before updating positions or starting animations.
        """
        label_w = int(self._measure_text_width(text))
        padding, pill_height, accent_w = self._layout_metrics()

        desired_w = padding + accent_w + padding + label_w + padding

                                                               
                                                                     
        available_w = max(1, int(self.screen_geom.width() - 2 * self.margin))
        min_w = min(130, available_w)
        max_w = min(int(self.screen_geom.width() * 0.5), 800, available_w)
        if max_w < min_w:
            max_w = min_w

        return int(max(min_w, min(desired_w, max_w)))

    def _prepare_geometry_for_text(self, text: str) -> int:
        """Compute final clamped width for `text` and update positions.

        Returns the computed width. This centralizes width clamping and ensures
        positions (onscreen/offscreen) are computed from the final width.
        """
        new_w = self._compute_effective_width(text)
        self._update_positions(new_w)
        return int(new_w)

    def _measure_text_width(self, html_text: str) -> float:
                                                                     
        doc = self._text_doc
        doc.setDefaultFont(self.label.font())
        doc.setHtml(html_text)
                                                            
        try:
            w = doc.idealWidth()
        except Exception:
            w = doc.size().width()
        return float(w)

    def _layout_metrics(self):
        """Return (padding, pill_height, accent_w) for current height/width."""
        padding = max(8, int(self._h * 0.12))
        pill_height = max(8, self._h - 2 * padding)
        accent_w = min(max(10, int(pill_height * 0.28)), int(self._w * 0.18))
        if accent_w > pill_height:
            accent_w = pill_height
        return padding, pill_height, accent_w

    def _anchored_x_for_width(self, width: int) -> int:
                                                                          
        return int(self.screen_geom.left() + self.screen_geom.width() - self.margin - int(width))

    def _apply_width(self, new_width: int):
        self._width_anim.stop()
        current_width = self.width()
        if new_width == current_width:
            self._w = current_width
            self.setMinimumWidth(current_width)
            self.resize(current_width, self._h)
            self._update_geometry()
            self.label.setGeometry(*self._label_rect)
            return

                                       
        self._width_anim.setStartValue(self.width())
        self._width_anim.setEndValue(new_width)

                                                                   
        self._update_positions(new_width)

                                                                                
        def _compute_label_rect_for_width(w: int):
            padding = max(8, int(self._h * 0.12))
            pill_height = max(8, self._h - 2 * padding)
            accent_w = min(max(10, int(pill_height * 0.28)), int(w * 0.18))
            if accent_w > pill_height:
                accent_w = pill_height
            label_start = padding + accent_w + padding
            return (label_start, 0, max(0, w - label_start - padding), self._h)

                                                                                  
        if self._width_anim_value_slot is not None:
            try:
                self._width_anim.valueChanged.disconnect(self._width_anim_value_slot)
            except Exception:
                pass
            self._width_anim_value_slot = None

        if self._width_anim_finished_slot is not None:
            try:
                self._width_anim.finished.disconnect(self._width_anim_finished_slot)
            except Exception:
                pass
            self._width_anim_finished_slot = None

                                                                    
        def _on_width_changed(value):
            try:
                value = int(value)
            except Exception:
                value = new_width

            if value == self._w:
                return

            self._w = value
                                                  
            self.setMinimumWidth(self._w)
                                                                     
            self.resize(self._w, self._h)
                                           
            self.label.setGeometry(*_compute_label_rect_for_width(self._w))
                                                            
            self.move(self._anchored_x_for_width(self._w), self.y())

                                                         
        def _on_width_anim_finished():
            try:
                end_w = int(self._width_anim.endValue())
            except Exception:
                end_w = int(new_width)

            self._w = end_w
            self.setMinimumWidth(end_w)
            self.resize(end_w, self._h)
            self._update_geometry()
            self.label.setGeometry(*self._label_rect)
            self.move(self._anchored_x_for_width(self._w), self.y())

                                                                   
            if self._width_anim_value_slot is not None:
                try:
                    self._width_anim.valueChanged.disconnect(self._width_anim_value_slot)
                except Exception:
                    pass
            if self._width_anim_finished_slot is not None:
                try:
                    self._width_anim.finished.disconnect(self._width_anim_finished_slot)
                except Exception:
                    pass

                                                                      
            self._width_anim_value_slot = None
            self._width_anim_finished_slot = None

                                                                  
        self._width_anim_value_slot = _on_width_changed
        self._width_anim_finished_slot = _on_width_anim_finished

        self._width_anim.valueChanged.connect(self._width_anim_value_slot)
        self._width_anim.finished.connect(self._width_anim_finished_slot)
        self._width_anim.start()


    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

                         
        card_path = QPainterPath()
        card_path.addRoundedRect(self._card_rect, self._card_radius, self._card_radius)
        p.fillPath(card_path, QColor(16, 16, 16, 140))

                        
        p.setPen(QColor(255, 255, 255, 18))
        p.drawPath(card_path)

              
        pill_path = QPainterPath()
        pill_path.addRoundedRect(self._pill_rect, self._pill_radius, self._pill_radius)
        p.fillPath(pill_path, QBrush(self._accent_color))

    def resizeEvent(self, event):
        self._update_geometry()
        self.label.setGeometry(*self._label_rect)
        super().resizeEvent(event)

    def slide_in(self):
        self._cancel_animation()

        start_pos = self.pos()

        self.animation.setStartValue(start_pos)
        self.animation.setEndValue(self.onscreen_pos)

        self.show()
        self.animation.start()

    def slide_out(self):
        self._cancel_animation()

        start_pos = self.pos()
        self.animation.setStartValue(start_pos)
        self.animation.setEndValue(self.offscreen_pos)

                                                                     
        if self._animation_finished_slot is not None:
            try:
                self.animation.finished.disconnect(self._animation_finished_slot)
            except Exception:
                pass

        self._animation_finished_slot = self.hide
        self.animation.finished.connect(self._animation_finished_slot)
        self.animation.start()

    def _cancel_animation(self):
                                                                                
        self.animation.stop()
        if self._animation_finished_slot is not None:
            try:
                self.animation.finished.disconnect(self._animation_finished_slot)
            except Exception:
                pass
            self._animation_finished_slot = None

    def _update_positions(self, width: int = None):

        w = self._w if width is None else int(width)
                                                                               
        available_w = max(1, int(self.screen_geom.width() - 2 * self.margin))
        if w < 1:
            w = 1
        if w > available_w:
                                                                                        
            if width is None:
                self._w = available_w
                                                                 
                self.resize(self._w, self._h)
                self._update_geometry()
                self.label.setGeometry(*self._label_rect)
            w = available_w
                                  
        onscreen_x = self._anchored_x_for_width(w)

        onscreen_y = int(self.screen_geom.top() + self.margin)
        offscreen_x = onscreen_x
        offscreen_y = int(self.screen_geom.top() - self._h - self.margin)

                         
        self.onscreen_pos = QPoint(int(onscreen_x), int(onscreen_y))
        self.offscreen_pos = QPoint(int(offscreen_x), int(offscreen_y))

    def set_state(self, text, color: QColor, auto_hide_ms=None):
                                                                         
        self._accent_color = color
                                                                  
        new_w = self._prepare_geometry_for_text(text)

                                                                   
        self._apply_width(new_w)
        self.label.setText(text)
        self.update()

                                                            
        self._off_timer.stop()

        self.slide_in()
        if auto_hide_ms is not None:
            self._off_timer.start(auto_hide_ms)

    def update_text_only(self, text: str):
        """Update label text and width without restarting slide animation."""
                                                                               
        new_w = self._prepare_geometry_for_text(text)
        self.label.setText(text)
        self._apply_width(new_w)
        self.update()

def _overlay_main(event_queue):
    app = QApplication(sys.argv)
    screen = app.primaryScreen()
    if screen is None:
        screens = app.screens()
        screen = screens[0] if screens else None
    if screen is None:
        return
    geom = screen.availableGeometry()

    banner = Banner(geom)
    countdown = {
        "remaining": 0,
        "message": "",
        "template": "{message} · {remaining}s",
    }

    countdown_timer = QTimer()
    countdown_timer.setInterval(1000)
    countdown_slot = {"fn": None}

    def _disconnect_countdown_slot():
        slot = countdown_slot["fn"]
        if slot is None:
            return
        try:
            countdown_timer.timeout.disconnect(slot)
        except (TypeError, RuntimeError):
            pass
        countdown_slot["fn"] = None

    def _stop_countdown():
        if countdown_timer.isActive():
            countdown_timer.stop()
        _disconnect_countdown_slot()
        countdown["remaining"] = 0

    def _start_countdown():
        if countdown["remaining"] <= 0:
            return

        def _tick():
            countdown["remaining"] -= 1
            if countdown["remaining"] <= 0:
                _stop_countdown()
                                                                                 
                banner.update_text_only(str(countdown.get("message", "")))
                return

            banner.update_text_only(
                _format_countdown_text(
                    countdown.get("template"),
                    countdown.get("message"),
                    countdown["remaining"],
                )
            )

        countdown_slot["fn"] = _tick
        countdown_timer.timeout.connect(_tick)
        countdown_timer.start()

    def _handle_banner(payload):
        _stop_countdown()

        message = str(payload.get("message", ""))
        color = _resolve_color(payload.get("color", "neutral"))
        duration_ms = _coerce_duration_ms(payload.get("duration_ms"))

        countdown_seconds = payload.get("countdown_seconds")
        try:
            countdown_seconds = int(countdown_seconds) if countdown_seconds is not None else None
        except (TypeError, ValueError):
            countdown_seconds = None

        if countdown_seconds is not None and countdown_seconds > 0:
            min_duration_ms = countdown_seconds * 1000
            if duration_ms is not None and duration_ms < min_duration_ms:
                duration_ms = min_duration_ms

            countdown["remaining"] = countdown_seconds
            countdown["message"] = message
            countdown["template"] = payload.get("countdown_template") or "{message} · {remaining}s"

            banner.set_state(
                _format_countdown_text(countdown["template"], message, countdown_seconds),
                color,
                auto_hide_ms=duration_ms,
            )
            _start_countdown()
            return

        banner.set_state(message, color, auto_hide_ms=duration_ms)

    def _process_event(event):
        if isinstance(event, tuple) and len(event) == 2 and event[0] == EVENT_BANNER and isinstance(event[1], dict):
            _handle_banner(event[1])
            return False

        return False

    def process_events():
        while True:
            try:
                event = event_queue.get_nowait()
            except Empty:
                break
            except (EOFError, OSError):
                app.quit()
                return

            try:
                should_stop = _process_event(event)
            except Exception:
                continue

            if should_stop:
                return

    timer = QTimer()
    timer.timeout.connect(process_events)
    timer.start(POLL_INTERVAL_MS)

    app.exec()


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
        _proc = _ctx.Process(target=_overlay_main, args=(_queue,), daemon=True)
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


def banner(
    message,
    color="neutral",
    duration_ms=None,
    countdown_seconds=None,
    countdown_template=None,
):
    """Show a banner with optional countdown.

    - `duration_ms=None` means sticky.
    - `countdown_template` can use `{message}` and `{remaining}` placeholders.
    - If countdown is enabled and duration is set, minimum duration is countdown.
    - Countdown only affects displayed text; it does not change banner lifecycle.
    """
    payload = {
        "message": "" if message is None else str(message),
        "color": _serialize_color(color),
        "duration_ms": _coerce_duration_ms(duration_ms),
    }

    countdown_value = None
    if countdown_seconds is not None:
        try:
            countdown_value = int(countdown_seconds)
        except (TypeError, ValueError):
            countdown_value = None

    if countdown_value is not None and countdown_value > 0:
        payload["countdown_seconds"] = countdown_value
        min_duration_ms = countdown_value * 1000
        if payload["duration_ms"] is not None and payload["duration_ms"] < min_duration_ms:
            payload["duration_ms"] = min_duration_ms

    if countdown_template is not None:
        payload["countdown_template"] = countdown_template

    _enqueue_event((EVENT_BANNER, payload))
