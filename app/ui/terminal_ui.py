"""Terminal UI helpers for the automation toolkit."""

import threading

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


class UIManager:
    """Renders a clean, live terminal dashboard."""

    _STATUS_VALUE_WIDTH = 10
    _lock = threading.RLock()
    _live: Live | None = None
    _app_title = ""
    _version = ""
    _hotkeys: dict[str, str] = {}
    _title_panel_cache: Panel | None = None
    _hotkeys_panel_cache: Panel | None = None
    _status_panel_cache: Panel | None = None
    _footer_panel_cache: Panel | None = None
    _state = {
        "target": "UNDETECTED",
        "nosave": "INACTIVE",
        "anti_afk": "INACTIVE",
        "job_warp": "READY",
        "cayo": "READY",
        "casino": "READY",
        "update_text": "",
    }

    @staticmethod
    def init_dashboard(app_title: str, version: str, hotkeys: dict[str, str]) -> None:
        with UIManager._lock:
            UIManager._app_title = app_title
            UIManager._version = version
            UIManager._hotkeys = hotkeys
            UIManager._title_panel_cache = UIManager._title_panel()
            UIManager._hotkeys_panel_cache = UIManager._hotkeys_panel()
            UIManager._status_panel_cache = UIManager._status_panel()
            UIManager._footer_panel_cache = UIManager._footer_panel()
            if UIManager._live is None:
                UIManager._live = Live(
                    console=console,
                    auto_refresh=False,
                    transient=False,
                )
                UIManager._live.start()
            UIManager._refresh_locked()

    @staticmethod
    def set_target_state(state: str) -> None:
        with UIManager._lock:
            new_value = state.upper()
            if UIManager._state["target"] == new_value:
                return
            UIManager._state["target"] = new_value
            UIManager._status_panel_cache = None
            UIManager._refresh_locked()

    @staticmethod
    def set_nosave_state(state: str) -> None:
        with UIManager._lock:
            new_value = state.upper()
            if UIManager._state["nosave"] == new_value:
                return
            UIManager._state["nosave"] = new_value
            UIManager._status_panel_cache = None
            UIManager._refresh_locked()

    @staticmethod
    def set_anti_afk_state(state: str) -> None:
        with UIManager._lock:
            new_value = state.upper()
            if UIManager._state["anti_afk"] == new_value:
                return
            UIManager._state["anti_afk"] = new_value
            UIManager._status_panel_cache = None
            UIManager._refresh_locked()

    @staticmethod
    def set_job_warp_running(is_running: bool) -> None:
        with UIManager._lock:
            new_value = "RUNNING" if is_running else "READY"
            if UIManager._state["job_warp"] == new_value:
                return
            UIManager._state["job_warp"] = new_value
            UIManager._status_panel_cache = None
            UIManager._refresh_locked()

    @staticmethod
    def set_solver_b_running(is_running: bool) -> None:
        with UIManager._lock:
            new_value = "RUNNING" if is_running else "READY"
            if UIManager._state["cayo"] == new_value:
                return
            UIManager._state["cayo"] = new_value
            UIManager._status_panel_cache = None
            UIManager._refresh_locked()

    @staticmethod
    def set_solver_a_running(is_running: bool) -> None:
        with UIManager._lock:
            new_value = "RUNNING" if is_running else "READY"
            if UIManager._state["casino"] == new_value:
                return
            UIManager._state["casino"] = new_value
            UIManager._status_panel_cache = None
            UIManager._refresh_locked()

    @staticmethod
    def set_update_notice(message: str) -> None:
        with UIManager._lock:
            if UIManager._state["update_text"] == message:
                return
            UIManager._state["update_text"] = message
            UIManager._footer_panel_cache = None
            UIManager._refresh_locked()

    @staticmethod
    def _refresh_locked() -> None:
        if UIManager._live is not None:
            UIManager._live.update(UIManager._build_dashboard(), refresh=True)

    @staticmethod
    def _build_dashboard():
        title_panel = UIManager._title_panel_cache or UIManager._title_panel()
        hotkeys_panel = UIManager._hotkeys_panel_cache or UIManager._hotkeys_panel()
        status_panel = UIManager._status_panel_cache or UIManager._status_panel()
        footer_panel = UIManager._footer_panel_cache or UIManager._footer_panel()
        UIManager._status_panel_cache = status_panel
        UIManager._footer_panel_cache = footer_panel
        return Group(
            title_panel,
            Columns(
                [hotkeys_panel, status_panel],
                expand=True,
                equal=True,
            ),
            footer_panel,
        )

    @staticmethod
    def _title_panel() -> Panel:
        title = Text(justify="center")
        title.append(UIManager._app_title or "Tessera", style="bold white")
        title.append("  ", style="white")
        title.append(UIManager._version or "", style="bold bright_black")
        return Panel(
            Align.center(title),
            box=box.SQUARE,
            border_style="bright_black",
            padding=(0, 2),
        )

    @staticmethod
    def _hotkeys_panel() -> Panel:
        table = Table(box=None, show_header=False, pad_edge=False, expand=True)
        table.add_column(style="bold bright_cyan", width=16)
        table.add_column(style="white")

        rows = [
            ("F5", "Job Warp"),
            ("F6", "Casino"),
            ("F7", "Cayo"),
            ("F8", "Nosave toggle"),
            ("CTRL + ALT + K", "Anti AFK toggle"),
            ("END", "Exit"),
        ]
        if UIManager._hotkeys:
            rows = [
                (UIManager._format_hotkey(UIManager._hotkeys["job_warp"]), "Job Warp"),
                (UIManager._format_hotkey(UIManager._hotkeys["casino"]), "Casino"),
                (UIManager._format_hotkey(UIManager._hotkeys["cayo"]), "Cayo"),
                (UIManager._format_hotkey(UIManager._hotkeys["toggle_nosave"]), "Nosave toggle"),
                (UIManager._format_hotkey(UIManager._hotkeys["toggle_anti_afk"]), "Anti AFK toggle"),
                (UIManager._format_hotkey(UIManager._hotkeys["exit"]), "Exit"),
            ]

        for key, label in rows:
            table.add_row(key, label)

        return Panel(
            table,
            title="[bold white]Controls[/bold white]",
            box=box.ROUNDED,
            border_style="bright_black",
            padding=(0, 1),
        )

    @staticmethod
    def _status_text(value: str, row_label: str | None = None) -> Text:
        display_value = value.upper()
        if row_label == "Nosave":
            text = Text(display_value.ljust(UIManager._STATUS_VALUE_WIDTH))
            if display_value == "ERROR":
                text.stylize("bold white on red")
            elif display_value == "VERIFYING":
                text.stylize("bold yellow")
            elif display_value == "ACTIVE":
                text.stylize("bold green")
            elif display_value == "INACTIVE":
                text.stylize("bold red")
            else:
                text.stylize("bold white")
            return text

        text = Text(display_value.ljust(UIManager._STATUS_VALUE_WIDTH))
        if value in ("UNDETECTED", "INACTIVE", "ERROR"):
            text.stylize("bold red")
        elif value == "VERIFYING":
            text.stylize("bold yellow")
        elif value in ("FOCUSED", "ACTIVE", "RUNNING", "DETECTED"):
            text.stylize("bold green")
        elif value == "READY":
            text.stylize("bold blue")
        elif value == "UNFOCUSED":
            text.stylize("bold yellow")
        else:
            text.stylize("bold white")
        return text

    @staticmethod
    def _status_panel() -> Panel:
        table = Table(box=None, show_header=False, pad_edge=False, expand=True)
        table.add_column(style="bold white", justify="left", width=12)
        table.add_column(justify="left", width=UIManager._STATUS_VALUE_WIDTH, no_wrap=True)

        rows = [
            ("Job Warp", UIManager._state["job_warp"]),
            ("Casino", UIManager._state["casino"]),
            ("Cayo", UIManager._state["cayo"]),
            ("Nosave", UIManager._state["nosave"]),
            ("Anti AFK", UIManager._state["anti_afk"]),
            ("Target", UIManager._state["target"]),
        ]

        for label, value in rows:
            label_text = Text(label, style="bold white")
            if label == "Nosave" and value == "ERROR":
                label_text = Text(label, style="bold white on red")
            table.add_row(label_text, UIManager._status_text(value, label))

        return Panel(
            table,
            title="[bold white]Live Status[/bold white]",
            box=box.ROUNDED,
            border_style="green",
            padding=(0, 1),
        )

    @staticmethod
    def _footer_panel() -> Panel:
        guide_hotkey = "SHIFT+F5"
        if UIManager._hotkeys:
            guide_hotkey = UIManager._format_hotkey(UIManager._hotkeys["show_readme"])

        footer_rows = Table.grid(expand=True)
        footer_rows.add_column()
        footer_rows.add_row(f"[bright_black]Open guide: {guide_hotkey}[/bright_black]")
        footer_rows.add_row("[bright_black]Keep this window visible and run as Administrator.[/bright_black]")

        update_text = (UIManager._state.get("update_text") or "").strip()
        if update_text:
            update_row = Text(update_text, style="yellow")
            update_row.no_wrap = False
            update_row.overflow = "fold"
            footer_rows.add_row(update_row)

        return Panel(
            footer_rows,
            box=box.SQUARE,
            border_style="bright_black",
            padding=(0, 2),
        )

    @staticmethod
    def _format_hotkey(hotkey_str: str) -> str:
        return " + ".join(part.strip().upper() for part in hotkey_str.split("+"))
