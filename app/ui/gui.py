"""Window-based dashboard helpers for the automation toolkit.

This module preserves the existing status API but renders the dashboard in a
compact Qt desktop window instead of a terminal console layout.
"""

import sys
import os
import threading
from pathlib import Path

from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QSizePolicy, QVBoxLayout, QWidget, QDialog, QFormLayout, QPushButton, QCheckBox

EVENT_INIT = "INIT"
EVENT_STATE = "STATE"


def _pyqt_key_to_name(key_code) -> str:
    # Function keys
    if Qt.Key.Key_F1 <= key_code <= Qt.Key.Key_F12:
        return f"f{key_code - Qt.Key.Key_F1 + 1}"
    # Standard letters / digits
    if Qt.Key.Key_A <= key_code <= Qt.Key.Key_Z:
        return chr(key_code).lower()
    if Qt.Key.Key_0 <= key_code <= Qt.Key.Key_9:
        return chr(key_code)
    # Modifiers
    if key_code == Qt.Key.Key_Control:
        return "ctrl"
    if key_code == Qt.Key.Key_Alt:
        return "alt"
    if key_code == Qt.Key.Key_Shift:
        return "shift"
    # Special keys
    special = {
        Qt.Key.Key_Escape: "escape",
        Qt.Key.Key_Tab: "tab",
        Qt.Key.Key_Space: "space",
        Qt.Key.Key_Return: "return",
        Qt.Key.Key_Enter: "enter",
        Qt.Key.Key_Backspace: "backspace",
        Qt.Key.Key_Delete: "delete",
        Qt.Key.Key_End: "end",
        Qt.Key.Key_Home: "home",
        Qt.Key.Key_Left: "left",
        Qt.Key.Key_Up: "up",
        Qt.Key.Key_Right: "right",
        Qt.Key.Key_Down: "down",
        Qt.Key.Key_PageUp: "pageup",
        Qt.Key.Key_PageDown: "pagedown",
    }
    return special.get(key_code, "").lower()


class KeybindRecordField(QPushButton):
    def __init__(self, action_name: str, current_value: str, dialog=None):
        super().__init__()
        self._action = action_name
        self._value = ""
        self._dialog = dialog
        self._is_duplicate = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.set_value(current_value)

    def set_value(self, val: str, is_duplicate: bool = False):
        self._value = str(val).lower().strip()
        self._is_duplicate = is_duplicate
        if self._is_duplicate:
            self.setText(UIManager._format_hotkey(self._value) if self._value else "UNBOUND")
            self.setStyleSheet(
                "QPushButton {"
                "  background: #1e1111;"
                "  color: #ff6b6b;"
                "  border: 1.5px solid #ef4444;"
                "  border-radius: 4px;"
                "  padding: 4px;"
                "  font-family: 'Segoe UI';"
                "  font-size: 11px;"
                "  font-weight: 700;"
                "}"
                "QPushButton:focus {"
                "  background: #2a1616;"
                "  border-color: #f87171;"
                "}"
            )
        elif not self._value:
            self.setText("UNBOUND")
            self.setStyleSheet(
                "QPushButton {"
                "  background: #11161c;"
                "  color: #ff6b6b;"
                "  border: 1px solid #ff6b6b;"
                "  border-radius: 4px;"
                "  padding: 4px;"
                "  font-family: 'Segoe UI';"
                "  font-size: 11px;"
                "  font-weight: 700;"
                "  font-style: italic;"
                "}"
                "QPushButton:focus {"
                "  background: #1a1e24;"
                "  border-color: #58c8ff;"
                "}"
            )
        else:
            self.setText(UIManager._format_hotkey(self._value))
            self.setStyleSheet(
                "QPushButton {"
                "  background: #11161c;"
                "  color: #58c8ff;"
                "  border: 1px solid #2d3945;"
                "  border-radius: 4px;"
                "  padding: 4px;"
                "  font-family: 'Segoe UI';"
                "  font-size: 11px;"
                "  font-weight: 700;"
                "}"
                "QPushButton:focus {"
                "  background: #1a1e24;"
                "  border-color: #58c8ff;"
                "}"
            )

    def focusInEvent(self, event):
        self.setText("Press keys...")
        self.setStyleSheet(
            "QPushButton {"
            "  background: #1a202c;"
            "  color: #ffffff;"
            "  border: 1px solid #58c8ff;"
            "  border-radius: 4px;"
            "  padding: 4px;"
            "  font-family: 'Segoe UI';"
            "  font-size: 11px;"
            "  font-weight: 700;"
            "}"
        )
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        if self._dialog:
            self._dialog.validate_keybinds()
        else:
            self.set_value(self._value)
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        key_code = event.key()
        if key_code == Qt.Key.Key_Delete:
            self.set_value("")
            self.clearFocus()
            if self._dialog:
                self._dialog.validate_keybinds()
            event.accept()
            return

        mods = event.modifiers()
        is_ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        is_alt = bool(mods & Qt.KeyboardModifier.AltModifier)
        is_shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)

        if key_code in {Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Shift}:
            parts = []
            if is_ctrl: parts.append("CTRL")
            if is_alt: parts.append("ALT")
            if is_shift: parts.append("SHIFT")
            parts.append("...")
            self.setText(" + ".join(parts))
            event.accept()
            return

        key_name = _pyqt_key_to_name(key_code)
        if not key_name:
            event.accept()
            return

        parts = []
        if is_ctrl: parts.append("ctrl")
        if is_alt: parts.append("alt")
        if is_shift: parts.append("shift")
        parts.append(key_name)
        combo = "+".join(parts)
        self.set_value(combo)
        self.clearFocus()
        if self._dialog:
            self._dialog.validate_keybinds()
        event.accept()


class ResetConfirmationDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Reset Keybinds")
        self.setFixedSize(320, 120)
        self.setStyleSheet(
            "QDialog {"
            "  background: #0d1117;"
            "  border: 1px solid #283541;"
            "}"
            "QLabel {"
            "  color: #f2f2f2;"
            "  font-family: 'Segoe UI';"
            "  font-size: 12px;"
            "}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.label = QLabel("Are you sure you want to reset to default keybinds?")
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.label)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.yes_btn = QPushButton("Yes")
        self.yes_btn.setStyleSheet(
            "QPushButton {"
            "  background: #7f1d1d;"
            "  color: #fca5a5;"
            "  border: 1px solid #991b1b;"
            "  border-radius: 8px;"
            "  font-family: 'Segoe UI';"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "  padding: 4px 16px;"
            "}"
            "QPushButton:hover {"
            "  background: #b91c1c;"
            "  color: #ffffff;"
            "}"
        )
        self.yes_btn.clicked.connect(self.accept)

        self.no_btn = QPushButton("No")
        self.no_btn.setStyleSheet(
            "QPushButton {"
            "  background: #374151;"
            "  color: #c8d6df;"
            "  border: 1px solid #4b5563;"
            "  border-radius: 8px;"
            "  font-family: 'Segoe UI';"
            "  font-size: 11px;"
            "  padding: 4px 16px;"
            "}"
            "QPushButton:hover {"
            "  background: #4b5563;"
            "  color: #ffffff;"
            "}"
        )
        self.no_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.yes_btn)
        btn_layout.addWidget(self.no_btn)
        layout.addLayout(btn_layout)


class KeybindEditorDialog(QDialog):
    def __init__(self, parent, hotkeys: dict[str, str], hidden_actions: list[str]):
        super().__init__(parent)
        self.setWindowTitle("Edit Keybinds")
        self.setFixedSize(380, 540)
        self.reset_triggered = False
        self.setStyleSheet(
            "QDialog {"
            "  background: #0d1117;"
            "  border: 1px solid #283541;"
            "}"
            "QLabel {"
            "  color: #f2f2f2;"
            "  font-family: 'Segoe UI';"
            "  font-size: 12px;"
            "}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Edit Hotkeys")
        title.setStyleSheet("font-size: 14px; font-weight: 800; color: #ffffff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(8)

        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        show_lbl = QLabel("Show")
        show_lbl.setStyleSheet("color: #63b4ff; font-family: 'Segoe UI'; font-size: 10px; font-weight: 700; text-transform: uppercase;")
        show_lbl.setFixedWidth(42)
        header_layout.addWidget(show_lbl)

        act_lbl = QLabel("Action")
        act_lbl.setStyleSheet("color: #868b93; font-family: 'Segoe UI'; font-size: 10px; font-weight: 700; text-transform: uppercase;")
        header_layout.addWidget(act_lbl)
        header_layout.addStretch()

        keybind_lbl = QLabel("Keybind")
        keybind_lbl.setStyleSheet("color: #868b93; font-family: 'Segoe UI'; font-size: 10px; font-weight: 700; text-transform: uppercase;")

        form_layout.addRow(header_widget, keybind_lbl)

        self.fields: dict[str, KeybindRecordField] = {}
        self.checkboxes: dict[str, QCheckBox] = {}
        labels_map = {
            "job_warp": "Job Warp",
            "casino": "Casino Fingerprint",
            "keypad": "Kortz/Casino Keypad",
            "cayo": "Cayo Fingerprint",
            "toggle_nosave": "Nosave Toggle",
            "toggle_anti_afk": "Anti AFK Toggle",
            "kill_game": "Kill Game",
            "exit": "Exit Program",
            "toggle_debug": "Debug Toggle",
        }

        for key, display_label in labels_map.items():
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            cb = QCheckBox()
            cb.setChecked(key not in hidden_actions)
            cb.setStyleSheet("QCheckBox::indicator { width: 14px; height: 14px; }")
            cb.setFixedWidth(42)
            self.checkboxes[key] = cb
            row_layout.addWidget(cb)

            lbl = QLabel(display_label)
            row_layout.addWidget(lbl)
            row_layout.addStretch()

            current_val = hotkeys.get(key, "")
            field = KeybindRecordField(key, current_val, dialog=self)
            self.fields[key] = field

            form_layout.addRow(row_widget, field)

        layout.addLayout(form_layout)

        footer = QLabel("Press Del to unbind a hotkey. Press Save to apply.")
        footer.setStyleSheet("color: #868b93; font-size: 10px; font-style: italic;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: 700; margin-top: 2px;")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setObjectName("resetKeybindsBtn")
        reset_btn.setStyleSheet(
            "QPushButton#resetKeybindsBtn {"
            "  background: #7f1d1d;"
            "  color: #fca5a5;"
            "  border: 1px solid #991b1b;"
            "  border-radius: 8px;"
            "  font-family: 'Segoe UI';"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "  padding: 6px;"
            "  margin-top: 4px;"
            "}"
            "QPushButton#resetKeybindsBtn:hover {"
            "  background: #b91c1c;"
            "  color: #ffffff;"
            "}"
        )
        reset_btn.clicked.connect(self._reset_keybinds)
        layout.addWidget(reset_btn)

        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.accept)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            "QPushButton {"
            "  background: #374151;"
            "  color: #c8d6df;"
            "  border: 1px solid #4b5563;"
            "  border-radius: 8px;"
            "  font-family: 'Segoe UI';"
            "  padding: 6px 16px;"
            "}"
            "QPushButton:hover {"
            "  background: #4b5563;"
            "}"
        )
        cancel_btn.clicked.connect(self.reject)

        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(self.save_btn)
        layout.addLayout(btn_box)

        self.validate_keybinds()

    def _reset_keybinds(self) -> None:
        confirm = ResetConfirmationDialog(self)
        if confirm.exec() != QDialog.DialogCode.Accepted:
            return

        self.reset_triggered = True

        from app.core.main import DEFAULT_HOTKEYS, DEFAULT_HIDDEN_ACTIONS

        for key, field in self.fields.items():
            field.set_value(DEFAULT_HOTKEYS.get(key, ""))

        for key, cb in self.checkboxes.items():
            cb.setChecked(key not in DEFAULT_HIDDEN_ACTIONS)

        self.validate_keybinds()

    def validate_keybinds(self) -> None:
        vals = [f._value for f in self.fields.values() if f._value]
        duplicates = {v for v in vals if vals.count(v) > 1}

        for field in self.fields.values():
            is_dup = (field._value in duplicates)
            field.set_value(field._value, is_duplicate=is_dup)

        if duplicates:
            self.error_label.setText("Error: You cannot have duplicate keybinds!")
            self.error_label.setVisible(True)
            self.save_btn.setEnabled(False)
            self.save_btn.setStyleSheet(
                "QPushButton {"
                "  background: #374151;"
                "  color: #9ca3af;"
                "  border: 1px solid #4b5563;"
                "  border-radius: 8px;"
                "  font-family: 'Segoe UI';"
                "  font-weight: 600;"
                "  padding: 6px 16px;"
                "}"
            )
        else:
            self.error_label.setVisible(False)
            self.save_btn.setEnabled(True)
            self.save_btn.setStyleSheet(
                "QPushButton {"
                "  background: #059669;"
                "  color: #ffffff;"
                "  border: 1px solid #047857;"
                "  border-radius: 8px;"
                "  font-family: 'Segoe UI';"
                "  font-weight: 600;"
                "  padding: 6px 16px;"
                "}"
                "QPushButton:hover {"
                "  background: #10b981;"
                "}"
            )

    def get_result(self) -> tuple[dict[str, str], list[str]]:
        hotkeys = {key: field._value for key, field in self.fields.items()}
        hidden = [key for key, cb in self.checkboxes.items() if not cb.isChecked()]
        return hotkeys, hidden


def _resolve_icon_path() -> str:
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    icon_path = base_dir / "assets" / "icon.png"
    if icon_path.exists():
        return str(icon_path)
    icon_path = Path("assets/icon.png")
    if icon_path.exists():
        return str(icon_path.resolve())
    return ""


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
        "Anti AFK",
        "Casino Fingerprint",
        "Kortz/Casino Keypad",
        "Cayo Fingerprint",
        "Nosave",
        "Game",
        "Debug",
    ]

    def __init__(self):
        super().__init__(None)
        self._title_label = QLabel()
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setFixedHeight(24)
        self._title_label.setStyleSheet("margin-bottom: 2px;")

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
        self._debug_editor.setMinimumHeight(120)
        self._debug_editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._debug_panel.add_widget(self._debug_editor)
        self._footer_label = QLabel()
        self._footer_label.setWordWrap(True)
        self._footer_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._footer_label.setStyleSheet("color: #868b93; font-size: 11px;")
        self._footer_label.setTextFormat(Qt.TextFormat.RichText)
        self._footer_label.setOpenExternalLinks(True)

        self._status_rows: dict[str, QLabel] = {}
        self._app_title = "Tessera"
        self._version = ""
        self._hotkeys: dict[str, str] = {}
        self._hidden_actions: list[str] = []
        self._has_flashed_update = False
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
        main_layout.addWidget(self._title_label, 0)

        content = QHBoxLayout()
        content.setSpacing(10)
        content.addWidget(self._controls_panel, 1)
        content.addWidget(self._status_panel, 1)
        main_layout.addLayout(content, 0)

        self._edit_keybinds_btn = QPushButton("Edit Keybinds")
        self._edit_keybinds_btn.setObjectName("editKeybindsBtn")
        self._edit_keybinds_btn.setStyleSheet(
            "QPushButton#editKeybindsBtn {"
            "  background: #11161c;"
            "  color: #868b93;"
            "  border: 1px solid #2d3945;"
            "  border-radius: 8px;"
            "  font-family: 'Segoe UI';"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  padding: 5px 0px;"
            "}"
            "QPushButton#editKeybindsBtn:hover {"
            "  background: #11161c;"
            "  border-color: #3d5068;"
            "  color: #f2f2f2;"
            "}"
            "QPushButton#editKeybindsBtn:pressed {"
            "  background: #0d1117;"
            "}"
        )
        self._edit_keybinds_btn.clicked.connect(self._open_keybind_editor)

        main_layout.addWidget(self._edit_keybinds_btn, 0)
        main_layout.addWidget(self._debug_panel, 1)
        main_layout.addWidget(self._footer_label, 0)

        self.setWindowFlags(Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setWindowTitle("Tessera")
        icon_path = _resolve_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
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
        self.adjustSize()
        self._position_window()

    def _build_controls(self) -> None:
        self._controls_panel.clear_content()

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        rows = [
            ("F5", "Job Warp", "job_warp"),
            ("CTRL + F5", "Anti AFK toggle", "toggle_anti_afk"),
            ("F6", "Casino Fingerprint", "casino"),
            ("CTRL + F6", "Kortz/Casino Keypad", "keypad"),
            ("F7", "Cayo Fingerprint", "cayo"),
            ("F8", "Nosave toggle", "toggle_nosave"),
            ("END", "Exit", "exit"),
            ("CTRL + ALT + F8", "Debug toggle", "toggle_debug"),
        ]
        if self._hotkeys:
            rows = [
                (UIManager._format_hotkey(self._hotkeys.get("job_warp", "")), "Job Warp", "job_warp"),
                (UIManager._format_hotkey(self._hotkeys.get("toggle_anti_afk", "")), "Anti AFK toggle", "toggle_anti_afk"),
                (UIManager._format_hotkey(self._hotkeys.get("casino", "")), "Casino Fingerprint", "casino"),
                (UIManager._format_hotkey(self._hotkeys.get("keypad", "")), "Kortz/Casino Keypad", "keypad"),
                (UIManager._format_hotkey(self._hotkeys.get("cayo", "")), "Cayo Fingerprint", "cayo"),
                (UIManager._format_hotkey(self._hotkeys.get("toggle_nosave", "")), "Nosave toggle", "toggle_nosave"),
                (UIManager._format_hotkey(self._hotkeys.get("kill_game", "")), "Kill Game", "kill_game"),
                (UIManager._format_hotkey(self._hotkeys.get("exit", "")), "Exit", "exit"),
                (UIManager._format_hotkey(self._hotkeys.get("toggle_debug", "")), "Debug toggle", "toggle_debug"),
            ]

        for key, label, action_name in rows:
            if action_name in self._hidden_actions:
                continue

            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            is_unbound = (key.strip() == "" or key.strip().lower() == "unbound")
            display_key = "UNBOUND" if is_unbound else key

            key_label = QLabel(display_key)
            if is_unbound:
                key_label.setStyleSheet("color: #ff6b6b; font-family: 'Segoe UI'; font-size: 11px; font-weight: 700; font-style: italic;")
            else:
                key_label.setStyleSheet("color: #58c8ff; font-family: 'Segoe UI'; font-size: 12px; font-weight: 700;")

            key_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value_label = QLabel(label)
            value_label.setStyleSheet("color: #f0f0f0; font-family: 'Segoe UI'; font-size: 12px; font-weight: 600;")
            value_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            row_layout.addWidget(value_label)
            row_layout.addWidget(key_label, 1)
            layout.addWidget(row)

        control_container = QWidget()
        control_container.setLayout(layout)
        self._controls_panel.add_widget(control_container)

    def _open_keybind_editor(self) -> None:
        dialog = KeybindEditorDialog(self, dict(self._hotkeys), list(self._hidden_actions))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_hotkeys, new_hidden = dialog.get_result()
            if dialog.reset_triggered:
                import os
                try:
                    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
                    path = os.path.join(appdata, "Tessera", "keybinds.json")
                    if os.path.exists(path):
                        os.remove(path)
                except Exception:
                    pass
                try:
                    from app.core.debug import set_debug
                    set_debug(False)
                    UIManager.set_debug_state("DISABLED")
                except Exception:
                    pass

            self._hotkeys = new_hotkeys
            self._hidden_actions = new_hidden
            self._build_controls()
            self._build_status()

            if UIManager._hotkeys_changed_callback is not None:
                try:
                    UIManager._hotkeys_changed_callback(new_hotkeys, new_hidden)
                except Exception:
                    pass

    def _build_status(self) -> None:
        self._status_panel.clear_content()
        self._status_rows.clear()

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        status_to_action = {
            "Job Warp": "job_warp",
            "Casino Fingerprint": "casino",
            "Kortz/Casino Keypad": "keypad",
            "Cayo Fingerprint": "cayo",
            "Nosave": "toggle_nosave",
            "Debug": "toggle_debug",
            "Anti AFK": "toggle_anti_afk",
        }

        for label in self._STATUS_LABELS:
            act = status_to_action.get(label)
            if act and act in self._hidden_actions:
                continue

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
        self.set_state(self._state)

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
    def set_metadata(self, app_title: str, version: str, hotkeys: dict[str, str], hidden_actions: list[str]) -> None:
        self._app_title = app_title
        self._version = version
        self._hotkeys = hotkeys
        self._hidden_actions = hidden_actions
        self._build_controls()
        self._build_status()
        self.set_state(self._state)
        self.adjustSize()
        self.resize(self.minimumSizeHint())

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
        
        icon_path = _resolve_icon_path()
        icon_td = f'<td style="vertical-align: middle; padding-right: 6px;"><img src="{icon_path}" width="14" height="14"/></td>' if icon_path else ""

        title_html = (
            f'<table align="center" cellpadding="0" cellspacing="0">'
            f'<tr>'
            f'{icon_td}'
            f'<td style="font-family: \'Segoe UI\'; font-size: 18px; font-weight: 800; color: #ffffff; letter-spacing: 0.8px; padding-right: 8px; vertical-align: middle;">{self._app_title.upper()}</td>'
            f'<td style="vertical-align: bottom; padding-bottom: 2px;">'
            f'<span style="font-family: \'Segoe UI\'; font-size: 10px; font-weight: 700; color: #58c8ff; background-color: rgba(88, 200, 255, 0.15); border: 1px solid rgba(88, 200, 255, 0.3); border-radius: 4px; padding: 0px 3px; vertical-align: middle;">{self._version}</span>'
            f'</td>'
            f'</tr>'
            f'</table>'
        )
        if self._title_label.text() != title_html:
            self._title_label.setText(title_html)

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
            self.resize(self.minimumSizeHint())

        footer_lines = []
        footer_lines.append('<a href="https://github.com/Abosmra3/Tessera?ref=tessera#how-to-use-the-tool" style="color: #70889b; text-decoration: underline;">Open guide</a>')
        footer_lines.append("Keep game's window visible.")
        footer_lines.append('<span style="color: #5a6a75;">Enjoying Tessera? <a href="https://github.com/Abosmra3/Tessera?ref=tessera" style="color: #70889b; text-decoration: underline;">Star the project</a> and share it with friends.</span>')
        if self._state.get("nosave_error"):
            footer_lines.append(self._state["nosave_error"])
        if self._state.get("update_text"):
            footer_lines.append(self._state["update_text"])

        footer_text = "<br>".join(footer_lines)
        if self._footer_label.text() != footer_text:
            self._footer_label.setText(footer_text)
            self._footer_label.setStyleSheet(
                "color: #ffffff; background: #5b1e1e; border: 1px solid #7d2c2c; border-radius: 6px; padding: 6px; font-size: 11px;"
                if self._state.get("nosave_error")
                else "color: #9aa6b2; background: #10171e; border: 1px solid #24303a; border-radius: 6px; padding: 6px; font-size: 11px;"
            )

        update_text = self._state.get("update_text", "")
        if update_text and not self._has_flashed_update:
            self._has_flashed_update = True
            self._start_update_flash_animation(update_text)

    def _start_update_flash_animation(self, original_text: str) -> None:
        on_text = original_text.replace("#fbbf24", "#f97316")
        off_text = original_text.replace("#fbbf24", "#9aa6b2")
        intervals = [250 * i for i in range(1, 15)]

        def make_flash_step(step_idx):
            def step():
                if self._closed:
                    return
                if self._state.get("update_text") != original_text:
                    return

                if step_idx == 13:
                    current_text = original_text
                else:
                    is_on = (step_idx % 2 != 0)
                    current_text = on_text if is_on else off_text

                footer_lines = []
                footer_lines.append('<a href="https://github.com/Abosmra3/Tessera?ref=tessera#how-to-use-the-tool" style="color: #70889b; text-decoration: underline;">Open guide</a>')
                footer_lines.append("Keep game's window visible.")
                footer_lines.append('<span style="color: #5a6a75;">Enjoying Tessera? <a href="https://github.com/Abosmra3/Tessera?ref=tessera" style="color: #70889b; text-decoration: underline;">Star the project</a> and share it with friends.</span>')
                if self._state.get("nosave_error"):
                    footer_lines.append(self._state["nosave_error"])

                footer_lines.append(current_text)
                self._footer_label.setText("<br>".join(footer_lines))
            return step

        for idx, ms in enumerate(intervals):
            QTimer.singleShot(ms, make_flash_step(idx))


class UISignals(QObject):
    init_dashboard = pyqtSignal(str, str, dict, list)
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
            list(UIManager._hidden_actions),
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

    if isinstance(event, tuple) and event[0] == EVENT_INIT and len(event) >= 5:
        _signals.init_dashboard.emit(event[1], event[2], event[3], event[4])
        return

    if isinstance(event, tuple) and event[0] == EVENT_STATE and len(event) >= 2:
        _signals.state_changed.emit(event[1])


class UIManager:
    """Renders a clean, live dashboard window."""

    _lock = threading.RLock()
    _cleanup_callback = None
    _hotkeys_changed_callback = None

    @staticmethod
    def register_cleanup_callback(callback) -> None:
        UIManager._cleanup_callback = callback

    @staticmethod
    def register_hotkeys_changed_callback(callback) -> None:
        UIManager._hotkeys_changed_callback = callback

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

    _hidden_actions: list[str] = []

    @staticmethod
    def init_dashboard(app_title: str, version: str, hotkeys: dict[str, str], hidden_actions: list[str]) -> None:
        with UIManager._lock:
            UIManager._app_title = app_title
            UIManager._version = version
            UIManager._hotkeys = hotkeys
            UIManager._hidden_actions = list(hidden_actions)
            _enqueue_event((EVENT_INIT, app_title, version, hotkeys, hidden_actions))
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
