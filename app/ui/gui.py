"""Window-based dashboard helpers for the automation toolkit.

This module preserves the existing status API but renders the dashboard in a
compact Qt desktop window instead of a terminal console layout.
"""

import sys
import threading

from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QSizePolicy, QVBoxLayout, QWidget

EVENT_INIT = "INIT"
EVENT_STATE = "STATE"


class _PanelWidget(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("panel")
        self.setStyleSheet(
            "QFrame#panel {"
            "  background: #11161c;"
            "  border: 1px solid #2d3945;"
            "  border-radius: 8px;"
            "}"
        )
        self._title = QLabel(title)
        self._title.setStyleSheet("color: #f2f2f2; font-family: 'Segoe UI'; font-size: 12px; font-weight: 700;")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setFixedHeight(20)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 6, 10, 8)
        self._layout.setSpacing(4)
        self._layout.addWidget(self._title)

        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(4)
        self._layout.addLayout(self._content_layout)

    def add_widget(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget)

    def clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()


class _DashboardWindow(QWidget):
    _STATUS_LABELS = [
        "Job Warp",
        "Casino Fingerprint",
        "Kortz/Casino Keypad",
        "Cayo Fingerprint",
        "Nosave",
        "Debug",
        "Anti AFK",
        "Game",
    ]

    def __init__(self):
        super().__init__(None)
        self._title_label = QLabel()
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setFixedHeight(18)
        self._title_label.setStyleSheet("color: #f4f6fb; font-family: 'Segoe UI'; font-size: 13px; font-weight: 700; padding-bottom: 2px;")

        self._controls_panel = _PanelWidget("Controls")
        self._status_panel = _PanelWidget("Live Status")
        self._status_panel._title.setStyleSheet("color: #f2f2f2; font-family: 'Segoe UI'; font-size: 12px; font-weight: 700;")
        self._status_panel._title.setFixedHeight(20)
        self._debug_panel = _PanelWidget("Debug Output")
        self._debug_panel.setVisible(False)
        self._debug_editor = QPlainTextEdit()
        self._debug_editor.setReadOnly(True)
        self._debug_editor.setStyleSheet(
            "QPlainTextEdit {"
            "  background: #0b1015;"
            "  color: #c8d6df;"
            "  border: 1px solid #24303a;"
            "  border-radius: 6px;"
            "  font-family: 'Segoe UI';"
            "  font-size: 11px;"
            "  padding: 4px;"
            "}"
        )
        self._debug_editor.setMaximumHeight(160)
        self._debug_panel.add_widget(self._debug_editor)
        self._footer_label = QLabel()
        self._footer_label.setWordWrap(True)
        self._footer_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._footer_label.setStyleSheet("color: #868b93; font-size: 11px;")

        self._status_rows: dict[str, QLabel] = {}
        self._app_title = "Tessera"
        self._version = ""
        self._hotkeys: dict[str, str] = {}
        self._closed = False
        self._state = {
            "target": "UNDETECTED",
            "nosave": "INACTIVE",
            "nosave_error": "",
            "anti_afk": "INACTIVE",
            "job_warp": "READY",
            "cayo": "READY",
            "casino": "READY",
            "keypad": "READY",
            "debug": "DISABLED",
            "update_text": "",
        }

        self._build_controls()
        self._build_status()
        self.set_state(self._state)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)
        main_layout.addWidget(self._title_label)

        content = QHBoxLayout()
        content.setSpacing(10)
        content.addWidget(self._controls_panel, 1)
        content.addWidget(self._status_panel, 1)
        main_layout.addLayout(content)
        main_layout.addWidget(self._debug_panel)
        main_layout.addWidget(self._footer_label)

        self.setWindowFlags(Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setWindowTitle("Tessera")
        self.setObjectName("mainWindow")
        self.setStyleSheet(
            "QWidget#mainWindow {"
            "  background: #0d1117;"
            "  border: 1px solid #283541;"
            "  border-radius: 10px;"
            "}"
            "QWidget {"
            "  color: #f4f6fb;"
            "}"
        )
        self.resize(760, 420)
        self.adjustSize()
        self._position_window()

    def _build_controls(self) -> None:
        self._controls_panel.clear_content()

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        rows = [
            ("F5", "Job Warp"),
            ("F6", "Casino Fingerprint"),
            ("CTRL + F6", "Kortz/Casino Keypad"),
            ("F7", "Cayo Fingerprint"),
            ("F8", "Nosave toggle"),
            ("CTRL + ALT + F8", "Debug toggle"),
            ("CTRL + ALT + F6", "Anti AFK toggle"),
            ("END", "Exit"),
        ]
        if self._hotkeys:
            rows = [
                (UIManager._format_hotkey(self._hotkeys["job_warp"]), "Job Warp"),
                (UIManager._format_hotkey(self._hotkeys["casino"]), "Casino Fingerprint"),
                (UIManager._format_hotkey(self._hotkeys.get("keypad", "ctrl+f6")), "Kortz/Casino Keypad"),
                (UIManager._format_hotkey(self._hotkeys["cayo"]), "Cayo Fingerprint"),
                (UIManager._format_hotkey(self._hotkeys["toggle_nosave"]), "Nosave toggle"),
                (UIManager._format_hotkey(self._hotkeys["toggle_debug"]), "Debug toggle"),
                (UIManager._format_hotkey(self._hotkeys["toggle_anti_afk"]), "Anti AFK toggle"),
                (UIManager._format_hotkey(self._hotkeys["exit"]), "Exit"),
            ]

        for key, label in rows:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            key_label = QLabel(key)
            key_label.setStyleSheet("color: #58c8ff; font-family: 'Segoe UI'; font-size: 12px; font-weight: 700;")
            key_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value_label = QLabel(label)
            value_label.setStyleSheet("color: #f0f0f0; font-family: 'Segoe UI'; font-size: 12px;")
            value_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            row_layout.addWidget(value_label)
            row_layout.addWidget(key_label, 1)
            layout.addWidget(row)

        control_container = QWidget()
        control_container.setLayout(layout)
        self._controls_panel.add_widget(control_container)

    def _build_status(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        for label in self._STATUS_LABELS:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(10)

            key_label = QLabel(label)
            key_label.setStyleSheet("color: #f0f0f0; font-family: 'Segoe UI'; font-size: 12px; font-weight: 600;")

            value_label = QLabel()
            value_label.setStyleSheet("color: #ffffff; font-family: 'Segoe UI'; font-size: 12px; font-weight: 600;")
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            row_layout.addWidget(key_label)
            row_layout.addWidget(value_label, 1)
            self._status_rows[label] = value_label
            layout.addWidget(row)

        status_container = QWidget()
        status_container.setLayout(layout)
        self._status_panel.add_widget(status_container)

    def _position_window(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            screens = QApplication.screens()
            screen = screens[0] if screens else None
        if screen is None:
            return
        geometry = screen.availableGeometry()
        self.move(geometry.right() - self.width() - 20, geometry.top() + 20)

    def _set_status_value(self, label: str, value: str) -> None:
        value_label = self._status_rows.get(label)
        if value_label is None:
            return
        val_str = str(value)
        if value_label.text() != val_str:
            value_label.setText(val_str)
            value_label.setStyleSheet(self._style_for_status_value(label, val_str))

    @staticmethod
    def _style_for_status_value(label: str, value: str) -> str:
        value_upper = str(value).upper()
        if label == "Nosave" and value_upper.startswith("ERROR:"):
            return "color: #ffffff; background: rgba(160, 30, 30, 180); border-radius: 6px; padding: 2px 6px; font-family: 'Segoe UI'; font-size: 12px; font-weight: 700;"
        if label == "Debug":
            return "color: #ff66f8; font-family: 'Segoe UI'; font-size: 12px; font-weight: 700;"
        if value_upper in {"UNDETECTED", "INACTIVE", "ERROR", "FAIL"}:
            return "color: #ff6b6b; font-family: 'Segoe UI'; font-size: 12px; font-weight: 700;"
        if value_upper == "VERIFYING":
            return "color: #ffc34d; font-family: 'Segoe UI'; font-size: 12px; font-weight: 700;"
        if value_upper in {"FOCUSED", "ACTIVE", "RUNNING", "DETECTED"} or value_upper.endswith(" LEFT"):
            return "color: #57f897; font-family: 'Segoe UI'; font-size: 12px; font-weight: 700;"
        if value_upper == "READY":
            return "color: #63b4ff; font-family: 'Segoe UI'; font-size: 12px; font-weight: 700;"
        if value_upper == "UNFOCUSED":
            return "color: #ffc34d; font-family: 'Segoe UI'; font-size: 12px; font-weight: 700;"
        return "color: #ffffff; font-family: 'Segoe UI'; font-size: 12px; font-weight: 700;"

    def set_metadata(self, app_title: str, version: str, hotkeys: dict[str, str]) -> None:
        self._app_title = app_title
        self._version = version
        self._hotkeys = hotkeys
        self._build_controls()
        self.set_state(self._state)

    def closeEvent(self, event) -> None:
        self._closed = True
        self.hide()
        event.accept()
        if UIManager._cleanup_callback is not None:
            try:
                UIManager._cleanup_callback()
            except Exception:
                pass
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def set_state(self, state: dict[str, str]) -> None:
        if self._closed:
            return

        self._state = dict(state)
        
        title_text = f"{self._app_title}  {self._version}"
        if self._title_label.text() != title_text:
            self._title_label.setText(title_text)

        self._set_status_value("Job Warp", self._state["job_warp"])
        self._set_status_value("Casino Fingerprint", self._state["casino"])
        self._set_status_value("Kortz/Casino Keypad", self._state["keypad"])
        self._set_status_value("Cayo Fingerprint", self._state["cayo"])
        self._set_status_value("Nosave", self._state["nosave"])
        self._set_status_value("Debug", self._state["debug"])
        self._set_status_value("Anti AFK", self._state["anti_afk"])
        self._set_status_value("Game", self._state["target"])

        debug_text = str(self._state.get("debug_output", "")).strip()
        if self._debug_editor.toPlainText() != debug_text:
            self._debug_editor.setPlainText(debug_text)
            bar = self._debug_editor.verticalScrollBar()
            bar.setValue(bar.maximum())

        was_visible = self._debug_panel.isVisible()
        is_visible = (self._state.get("debug") == "ENABLED")
        if was_visible != is_visible:
            self._debug_panel.setVisible(is_visible)
            self.adjustSize()

        guide_hotkey = UIManager._format_hotkey(self._hotkeys.get("show_readme", "shift+f5"))
        footer_lines = [f"Open guide: {guide_hotkey}", "Keep game's window visible."]
        if self._state.get("nosave_error"):
            footer_lines.append(self._state["nosave_error"])
        if self._state.get("update_text"):
            footer_lines.append(self._state["update_text"])

        footer_text = "\n".join(footer_lines)
        if self._footer_label.text() != footer_text:
            self._footer_label.setText(footer_text)
            self._footer_label.setStyleSheet(
                "color: #ffffff; background: #5b1e1e; border: 1px solid #7d2c2c; border-radius: 6px; padding: 6px; font-size: 11px;"
                if self._state.get("nosave_error")
                else "color: #9aa6b2; background: #10171e; border: 1px solid #24303a; border-radius: 6px; padding: 6px; font-size: 11px;"
            )


class UISignals(QObject):
    init_dashboard = pyqtSignal(str, str, dict)
    state_changed = pyqtSignal(dict)


_signals: UISignals | None = None
_app = None
_window = None
_lifecycle_lock = threading.Lock()


def _ensure_started():
    global _app, _window, _signals
    with _lifecycle_lock:
        if _window is not None:
            return

        _app = QApplication.instance()
        if _app is None:
            _app = QApplication(sys.argv)
            _app.setQuitOnLastWindowClosed(False)

        _signals = UISignals()
        _window = _DashboardWindow()
        _window.set_metadata(
            UIManager._app_title or "Tessera",
            UIManager._version or "",
            dict(UIManager._hotkeys),
        )
        _window.set_state(dict(UIManager._state))
        _signals.init_dashboard.connect(_window.set_metadata)
        _signals.state_changed.connect(_window.set_state)
        _window.show()
        _window.raise_()


def _enqueue_event(event):
    _ensure_started()
    if _signals is None:
        return

    if isinstance(event, tuple) and event[0] == EVENT_INIT and len(event) >= 4:
        _signals.init_dashboard.emit(event[1], event[2], event[3])
        return

    if isinstance(event, tuple) and event[0] == EVENT_STATE and len(event) >= 2:
        _signals.state_changed.emit(event[1])


class UIManager:
    """Renders a clean, live dashboard window."""

    _lock = threading.RLock()
    _cleanup_callback = None

    @staticmethod
    def register_cleanup_callback(callback) -> None:
        UIManager._cleanup_callback = callback
    _app_title = ""
    _version = ""
    _hotkeys: dict[str, str] = {}
    _state = {
        "target": "UNDETECTED",
        "nosave": "INACTIVE",
        "nosave_error": "",
        "anti_afk": "INACTIVE",
        "job_warp": "READY",
        "cayo": "READY",
        "casino": "READY",
        "keypad": "READY",
        "debug": "DISABLED",
        "debug_output": "",
        "update_text": "",
    }

    @staticmethod
    def run_event_loop() -> None:
        app = QApplication.instance()
        if app is not None:
            app.exec()

    @staticmethod
    def init_dashboard(app_title: str, version: str, hotkeys: dict[str, str]) -> None:
        with UIManager._lock:
            UIManager._app_title = app_title
            UIManager._version = version
            UIManager._hotkeys = hotkeys
            _enqueue_event((EVENT_INIT, app_title, version, hotkeys))
            UIManager._refresh_locked()

    @staticmethod
    def set_target_state(state: str) -> None:
        with UIManager._lock:
            new_value = state.upper()
            if UIManager._state["target"] == new_value:
                return
            UIManager._state["target"] = new_value
            UIManager._refresh_locked()

    @staticmethod
    def set_nosave_state(state: str) -> None:
        with UIManager._lock:
            new_value = state.upper()
            if UIManager._state["nosave"] == new_value:
                return
            UIManager._state["nosave"] = new_value
            UIManager._refresh_locked()

    @staticmethod
    def set_anti_afk_state(state: str) -> None:
        with UIManager._lock:
            new_value = state.upper()
            if UIManager._state["anti_afk"] == new_value:
                return
            UIManager._state["anti_afk"] = new_value
            UIManager._refresh_locked()

    @staticmethod
    def set_job_warp_running(is_running: bool) -> None:
        with UIManager._lock:
            new_value = "RUNNING" if is_running else "READY"
            if UIManager._state["job_warp"] == new_value:
                return
            UIManager._state["job_warp"] = new_value
            UIManager._refresh_locked()

    @staticmethod
    def set_solver_b_running(is_running: bool) -> None:
        with UIManager._lock:
            new_value = "RUNNING" if is_running else "READY"
            if UIManager._state["cayo"] == new_value:
                return
            UIManager._state["cayo"] = new_value
            UIManager._refresh_locked()

    @staticmethod
    def set_solver_a_running(is_running: bool) -> None:
        with UIManager._lock:
            new_value = "RUNNING" if is_running else "READY"
            if UIManager._state["casino"] == new_value:
                return
            UIManager._state["casino"] = new_value
            UIManager._refresh_locked()

    @staticmethod
    def set_keypad_running(is_running: bool) -> None:
        with UIManager._lock:
            if is_running:
                new_value = "RUNNING"
                if UIManager._state["keypad"] == new_value:
                    return
                UIManager._state["keypad"] = new_value
                UIManager._refresh_locked()
                return

            current_value = UIManager._state["keypad"]
            if current_value == "FAIL":
                return
            if UIManager._state["keypad"] == "READY":
                return
            UIManager._state["keypad"] = "READY"
            UIManager._refresh_locked()

    @staticmethod
    def set_keypad_status(status: str) -> None:
        with UIManager._lock:
            new_value = status.upper()
            if UIManager._state["keypad"] == new_value:
                return
            UIManager._state["keypad"] = new_value
            UIManager._refresh_locked()

    @staticmethod
    def append_debug_line(message: str) -> None:
        with UIManager._lock:
            text = str(message).strip()
            if not text:
                return
            UIManager._state.setdefault("debug_output", "")
            lines = [line for line in str(UIManager._state["debug_output"]).splitlines() if line]
            lines.append(text)
            if len(lines) > 250:
                lines = lines[-250:]
            UIManager._state["debug_output"] = "\n".join(lines)
            UIManager._refresh_locked()

    @staticmethod
    def set_debug_state(state: str) -> None:
        with UIManager._lock:
            new_value = str(state).upper()
            if new_value not in {"ENABLED", "DISABLED"}:
                new_value = "ENABLED" if str(state).lower() in {"true", "1", "on"} else "DISABLED"
            if UIManager._state["debug"] == new_value:
                return
            UIManager._state["debug"] = new_value
            UIManager._refresh_locked()

    @staticmethod
    def set_update_notice(message: str) -> None:
        with UIManager._lock:
            if UIManager._state["update_text"] == message:
                return
            UIManager._state["update_text"] = message
            UIManager._refresh_locked()

    @staticmethod
    def set_nosave_error_notice(message: str) -> None:
        with UIManager._lock:
            if UIManager._state["nosave_error"] == message:
                return
            UIManager._state["nosave_error"] = message
            UIManager._refresh_locked()

    @staticmethod
    def _refresh_locked() -> None:
        _enqueue_event((EVENT_STATE, dict(UIManager._state)))

    @staticmethod
    def _format_hotkey(hotkey_str: str) -> str:
        return " + ".join(part.strip().upper() for part in hotkey_str.split("+"))
