"""程序入口：协调多个 board / 悬浮窗 / 历史窗 / 托盘。"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from app.database import Database, Board
from app.floating_window import FloatingWindow, raise_to_front
from app.history_window import HistoryWindow
from app.hotkey import GlobalHotkey
from app.timer_window import FocusTimerWindow
from app.tray import TrayIcon
from app.web_calendar import WebCalendarServer


def resource_path(relative: str) -> str:
    """兼容 PyInstaller 打包后的资源路径。"""
    base = getattr(sys, "_MEIPASS", Path(__file__).parent)
    return str(Path(base) / relative)


class App:
    def __init__(self, qapp: QApplication, db: Database, icon_path: str):
        self.qapp = qapp
        self.db = db
        self.icon_path = icon_path

        self.windows: Dict[int, FloatingWindow] = {}
        self.history_window = HistoryWindow(db)
        self.history_window.restored.connect(self._refresh_all_floating)
        self.history_window.analyze_requested.connect(
            lambda: self.web_calendar.open_in_browser("#analytics")
        )

        # 日历视图：本地网页版（懒启动 HTTP 服务，默认浏览器打开）
        self.web_calendar = WebCalendarServer(db, resource_path("app/webcal"))
        self.web_calendar.changed.connect(self._refresh_all_floating)
        qapp.aboutToQuit.connect(self.web_calendar.stop)

        # 专注计时器（单实例，绑定不同待办）
        self.timer_window = FocusTimerWindow(db)
        self.timer_window.finished.connect(self._on_timer_finished)

        # 启动时为每个已存在的 board 打开一个窗口
        for board in self.db.list_boards():
            self._open_board(board)

        self.tray = TrayIcon(
            icon_path=icon_path,
            on_summon_all=self.summon_all,
            on_toggle_all=self.toggle_all,
            on_new_board=self.create_new_board,
            on_show_board=self.show_board,
            on_history_all=self.show_combined_history,
            on_quit=qapp.quit,
            on_calendar=self.show_calendar,
            board_provider=self._board_menu_data,
        )
        self.tray.show()

        # 全局热键：Ctrl+Alt+M 呼出所有便签
        self.hotkey = GlobalHotkey("<ctrl>+<alt>+m")
        self.hotkey.triggered.connect(self.summon_all)
        self.hotkey.start()

    # ---------- 窗口管理 ----------

    def _open_board(self, board: Board):
        win = FloatingWindow(self.db, board, on_new_board=self.create_new_board)
        win.history_requested.connect(self.show_history_for)
        win.focus_board_requested.connect(self.show_board)
        win.delete_board_requested.connect(self.delete_board)
        win.calendar_requested.connect(self.show_calendar)
        win.timer_requested.connect(self.open_timer_for)
        self.windows[board.id] = win
        win.show()

    def create_new_board(self):
        board_id = self.db.add_board(title="新便签", color="yellow")
        board = self.db.get_board(board_id)
        if board:
            self._open_board(board)

    def show_board(self, board_id: int):
        win = self.windows.get(board_id)
        if win:
            # 显示前先修正可能因显示器/分辨率变化而落到屏幕外的位置；
            # 再使用 Windows 兼容的前台激活方式，避免窗口实际已显示却被压住。
            win.ensure_on_screen()
            raise_to_front(win)

    def delete_board(self, board_id: int):
        win = self.windows.pop(board_id, None)
        if win is not None:
            win.hide()
            win.deleteLater()
        self.db.delete_board(board_id)
        # 防止"全删光"：自动新建一个默认便签
        if not self.windows:
            self.create_new_board()

    def _refresh_all_floating(self):
        """历史窗里恢复待办后调用，刷新所有悬浮窗以显示恢复的条目。"""
        for w in self.windows.values():
            w.refresh()

    def toggle_all(self):
        any_visible = any(w.isVisible() for w in self.windows.values())
        for w in self.windows.values():
            if any_visible:
                w.hide()
            else:
                w.show()
                w.raise_()

    def summon_all(self):
        """托盘单击 / 全局热键的统一呼出入口。

        只操作可见便签：用户主动关闭过的便签不会被一同呼出。
        可见便签都已在前台时隐藏；否则把它们拉到最前并激活。
        一个可见便签都没有时不响应（可从托盘菜单"显示 / 隐藏所有便签"全部恢复）。
        """
        visible = [w for w in self.windows.values() if w.isVisible()]
        if not visible:
            return
        all_front = all(w.isActiveWindow() for w in visible)
        if all_front:
            for w in visible:
                w.hide()
            return
        for w in visible:
            raise_to_front(w)

    # ---------- 历史（统一展示，跨所有便签） ----------

    def show_history_for(self, board_id: int):
        # 不再按 board 过滤；所有便签的已完成统一展示
        self.history_window.set_board(None)
        self.history_window.show_and_refresh()

    def show_combined_history(self):
        self.history_window.set_board(None)
        self.history_window.show_and_refresh()

    # ---------- 日历视图 ----------

    def show_calendar(self):
        self.web_calendar.open_in_browser()

    # ---------- 专注计时器 ----------

    def open_timer_for(self, todo_id: int):
        todo = self.db.get(todo_id)
        if todo is None:
            return
        self.timer_window.show_for(todo)

    def _on_timer_finished(self, title: str):
        self.tray.showMessage(
            "专注结束 ⏰",
            f"「{title}」这一段专注完成啦！",
            self.tray.icon(),
            8000,
        )
        self._refresh_all_floating()

    # ---------- 托盘菜单数据 ----------

    def _board_menu_data(self) -> list[tuple[int, str, bool]]:
        result: list[tuple[int, str, bool]] = []
        for board in self.db.list_boards():
            win = self.windows.get(board.id)
            visible = bool(win and win.isVisible())
            result.append((board.id, board.title, visible))
        return result


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    icon_path = resource_path("assets/icon.png")
    if Path(icon_path).exists():
        app.setWindowIcon(QIcon(icon_path))

    db = Database()
    db.init()

    App(app, db, icon_path)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
