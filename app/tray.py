"""系统托盘图标 + 菜单。"""
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor
from PySide6.QtWidgets import QSystemTrayIcon, QMenu


def _fallback_icon() -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(QColor("transparent"))
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#FFCF5C"))
    p.setPen(QColor("#B8860B"))
    p.drawEllipse(4, 4, 56, 56)
    p.end()
    return QIcon(pix)


class TrayIcon(QSystemTrayIcon):
    """托盘菜单：
    - 显示/隐藏所有便签
    - 新建便签
    - 各 board 列表（点击聚焦该便签）
    - 查看全部历史
    - 退出
    """

    def __init__(
        self,
        icon_path: str,
        on_summon_all: Callable[[], None],
        on_toggle_all: Callable[[], None],
        on_new_board: Callable[[], None],
        on_show_board: Callable[[int], None],
        on_history_all: Callable[[], None],
        on_quit: Callable[[], None],
        on_calendar: Optional[Callable[[], None]] = None,
        board_provider: Optional[Callable[[], list[tuple[int, str, bool]]]] = None,
    ):
        icon = QIcon(icon_path) if Path(icon_path).exists() else _fallback_icon()
        super().__init__(icon)
        self.setToolTip("桌面悬浮便签")

        self._on_summon_all = on_summon_all
        self._on_toggle_all = on_toggle_all
        self._on_new_board = on_new_board
        self._on_show_board = on_show_board
        self._on_history_all = on_history_all
        self._on_quit = on_quit
        self._on_calendar = on_calendar
        self._board_provider = board_provider

        self._menu = QMenu()
        self.setContextMenu(self._menu)
        self._build_menu()

        # 在 menu 即将弹出前刷新 board 列表
        self._menu.aboutToShow.connect(self._build_menu)

        # 左键单击 = 把所有便签呼到最前（已都在前才隐藏）
        self.activated.connect(
            lambda r: on_summon_all()
            if r == QSystemTrayIcon.Trigger else None
        )

    def _build_menu(self):
        self._menu.clear()

        toggle_act = QAction("显示 / 隐藏所有便签", self._menu)
        toggle_act.triggered.connect(self._on_toggle_all)
        self._menu.addAction(toggle_act)

        new_act = QAction("➕ 新建便签", self._menu)
        new_act.triggered.connect(self._on_new_board)
        self._menu.addAction(new_act)

        if self._board_provider:
            try:
                boards = self._board_provider()
            except Exception:
                boards = []
            if boards:
                self._menu.addSeparator()
                for bid, title, visible in boards:
                    label = ("● " if visible else "○ ") + title
                    a = QAction(label, self._menu)
                    a.triggered.connect(
                        lambda _=False, b=bid: self._on_show_board(b)
                    )
                    self._menu.addAction(a)

        self._menu.addSeparator()
        if self._on_calendar:
            calendar_act = QAction("📅 日历视图", self._menu)
            calendar_act.triggered.connect(self._on_calendar)
            self._menu.addAction(calendar_act)
        history_act = QAction("查看全部历史…", self._menu)
        history_act.triggered.connect(self._on_history_all)
        self._menu.addAction(history_act)

        quit_act = QAction("退出", self._menu)
        quit_act.triggered.connect(self._on_quit)
        self._menu.addAction(quit_act)

    def refresh_boards(self):
        self._build_menu()
