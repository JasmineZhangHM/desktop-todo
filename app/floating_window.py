"""桌面悬浮便签：每个 FloatingWindow 绑定一个 board，独立颜色 / 位置 / 内容。

v4 改动：
- 删除最小化按钮
- 标题栏左侧：[+ 新建便签]   中间：[标题/拖动手柄]   右侧：[● 颜色] [✕ 关闭]
- 颜色按钮弹出色板菜单，应用主题色到当前便签
- 行布局精简到单行：内容 + 标签 + 日期 + 圆按钮
- 分栏拆为：🔴 已逾期 / 📅 今天 / ⏰ 近期 / 📆 以后 / 📝 无日期
- "今天" / "无日期" 分栏内的行不再重复显示日期
- 激活的标签筛选下，行内不再重复该标签
- 位置/尺寸 500ms 防抖写回 boards 表
"""
from __future__ import annotations

from datetime import date as _date, timedelta as _timedelta
from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal, QPoint, QRect, QSize, QTimer, QMimeData
from PySide6.QtGui import (
    QMouseEvent, QCursor, QPainter, QColor, QAction, QPixmap, QIcon, QDrag,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QFrame, QMenu,
    QApplication, QInputDialog, QMessageBox, QDialog, QWidgetAction,
    QSizePolicy,
)

from app.database import Database, Board, Todo
from app.dialogs import EditTodoDialog
from app.parser import parse_input, format_for_edit, format_due_label, due_status
from app.styles import COLOR_THEMES, floating_qss


RESIZE_MARGIN = 8


def raise_to_front(w: QWidget):
    """把窗口拉到最前并激活。

    Windows 有焦点抢占限制：被其他前台窗口压住时 `raise_() + activateWindow()`
    不一定生效。临时打开 StaysOnTop 让窗口提到 Z 序最顶，再立刻关掉，
    既能跨进程抢到前台，又不会留下"始终置顶"状态。
    """
    w.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    w.show()
    w.setWindowFlag(Qt.WindowStaysOnTopHint, False)
    w.show()
    w.raise_()
    w.activateWindow()


_CURSOR_MAP = {
    "left": Qt.SizeHorCursor,    "right": Qt.SizeHorCursor,
    "top": Qt.SizeVerCursor,     "bottom": Qt.SizeVerCursor,
    "topleft": Qt.SizeFDiagCursor, "bottomright": Qt.SizeFDiagCursor,
    "topright": Qt.SizeBDiagCursor, "bottomleft": Qt.SizeBDiagCursor,
}

# 分栏：(key, 标题, header objectName, predicate(due_status), 行内日期是否冗余)
# "近期" 吸收原"以后"和"无日期"，作为兜底桶
SECTIONS = [
    ("overdue",  "🔴 已逾期", "SectionHeaderOverdue", lambda s: s == "overdue",                  False),
    ("today",    "📅 今天",   "SectionHeaderToday",   lambda s: s == "today",                    True),
    ("tomorrow", "🌤 明天",   "SectionHeader",        lambda s: s == "tomorrow",                 True),
    ("soon",     "⏰ 近期",   "SectionHeader",        lambda s: s in ("soon", "later") or s is None, False),
]


class ClickableLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
            e.accept()
            return
        super().mousePressEvent(e)


class ElidedLabel(QLabel):
    """单行省略号标签：水平可压缩到 0，超长尾部显示 …；点击发 clicked。

    自绘文本，因此颜色 / 悬停色由构造参数控制（不走 QSS 的 color）。
    水平用 Ignored 策略，让正文给固定宽度的 ✓ 按钮等让位。
    """

    clicked = Signal()

    def __init__(
        self,
        text: str = "",
        color: str = "#333",
        hover_color: Optional[str] = None,
        font_px: int = 13,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._full = text or ""
        self._color = QColor(color)
        self._hover_color = QColor(hover_color) if hover_color else QColor(color)
        self._hovering = False
        f = self.font()
        f.setPixelSize(font_px)
        self.setFont(f)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setToolTip(self._full)

    def setFullText(self, text: str):
        self._full = text or ""
        self.setToolTip(self._full)
        self.update()

    def minimumSizeHint(self) -> QSize:
        return QSize(0, self.fontMetrics().height())

    def sizeHint(self) -> QSize:
        return QSize(0, self.fontMetrics().height())

    def enterEvent(self, e):
        self._hovering = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hovering = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setFont(self.font())
        elided = self.fontMetrics().elidedText(
            self._full, Qt.ElideRight, self.width()
        )
        p.setPen(self._hover_color if self._hovering else self._color)
        p.drawText(self.rect(), Qt.AlignLeft | Qt.AlignVCenter, elided)

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
            e.accept()
            return
        super().mousePressEvent(e)


class _DragLabel(QLabel):
    """标题区域：单击拖动整窗 / 双击重命名。"""

    rename_requested = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._drag_offset: Optional[QPoint] = None

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            self._drag_offset = (
                e.globalPosition().toPoint()
                - self.window().frameGeometry().topLeft()
            )
            e.accept()

    def mouseMoveEvent(self, e: QMouseEvent):
        if e.buttons() & Qt.LeftButton and self._drag_offset is not None:
            self.window().move(e.globalPosition().toPoint() - self._drag_offset)
            e.accept()

    def mouseReleaseEvent(self, e: QMouseEvent):
        self._drag_offset = None

    def mouseDoubleClickEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            self.rename_requested.emit()
            e.accept()
            return
        super().mouseDoubleClickEvent(e)


class DragHandle(QLabel):
    """每行左侧的拖动手柄；按住可拖动整行调整顺序。"""

    def __init__(self, todo_id: int, parent: Optional[QWidget] = None):
        super().__init__("⠿", parent)
        self.todo_id = todo_id
        self.setObjectName("DragHandle")
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("按住拖动调整顺序")
        self.setFixedWidth(16)
        self.setAlignment(Qt.AlignCenter)
        self._press_pos: Optional[QPoint] = None

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            self._press_pos = e.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent):
        if not (e.buttons() & Qt.LeftButton) or self._press_pos is None:
            return super().mouseMoveEvent(e)
        delta = (e.position().toPoint() - self._press_pos).manhattanLength()
        if delta < QApplication.startDragDistance():
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(f"todo:{self.todo_id}")
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction)
        self._press_pos = None
        self.setCursor(Qt.OpenHandCursor)

    def mouseReleaseEvent(self, e: QMouseEvent):
        self._press_pos = None
        self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(e)


class ReorderableListWidget(QListWidget):
    """支持自定义 mime（"todo:<id>"）的 drop 接收。"""

    todo_dropped = Signal(int, int)  # todo_id, target_row_idx

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasText() and e.mimeData().text().startswith("todo:"):
            e.acceptProposedAction()
            return
        super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasText() and e.mimeData().text().startswith("todo:"):
            e.acceptProposedAction()
            return
        super().dragMoveEvent(e)

    def dropEvent(self, e):
        text = e.mimeData().text()
        if text.startswith("todo:"):
            try:
                todo_id = int(text[5:])
            except ValueError:
                return super().dropEvent(e)
            pos = e.position().toPoint()
            target_item = self.itemAt(pos)
            if target_item is None:
                target_idx = self.count()
            else:
                target_idx = self.row(target_item)
                rect = self.visualItemRect(target_item)
                if pos.y() > rect.center().y():
                    target_idx += 1
            self.todo_dropped.emit(todo_id, target_idx)
            e.acceptProposedAction()
            return
        super().dropEvent(e)


class ColorSwatchRow(QWidget):
    """三点菜单顶部的色板横排：6 色 + 当前色 ✓ 标记。"""

    color_chosen = Signal(str)

    def __init__(self, current_color: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        for key, theme in COLOR_THEMES.items():
            is_cur = key == current_color
            btn = QPushButton("✓" if is_cur else "")
            btn.setFixedSize(30, 30)
            border = (
                f"2px solid {theme['accent_hover']}" if is_cur
                else f"1px solid {theme['border']}"
            )
            btn.setStyleSheet(
                "QPushButton { "
                f"background: {theme['title_bg']}; "
                f"border: {border}; "
                f"border-radius: 6px; "
                f"color: {theme['accent_text']}; "
                "font-weight: bold; font-size: 14px; }"
                "QPushButton:hover { "
                f"border: 2px solid {theme['accent']}; "
                "}"
            )
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(theme["name"])
            btn.clicked.connect(lambda _=False, k=key: self.color_chosen.emit(k))
            layout.addWidget(btn)


class BoardListDialog(QDialog):
    """便签列表：所有 boards 以彩色卡片列出，点击即聚焦该便签。"""

    board_selected = Signal(int)

    def __init__(self, boards: list, current_id: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("便签列表")
        self.resize(320, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        head = QLabel(f"共 {len(boards)} 个便签 · 点击切换")
        head.setStyleSheet("color:#888;font-size:12px;padding:0 0 4px 0;")
        layout.addWidget(head)

        for board in boards:
            theme = COLOR_THEMES.get(board.color, COLOR_THEMES["yellow"])
            mark = "  ✓" if board.id == current_id else ""
            btn = QPushButton(f"{board.title}{mark}")
            btn.setMinimumHeight(40)
            btn.setStyleSheet(
                "QPushButton { "
                f"background: {theme['body_bg']}; "
                f"border: 1px solid {theme['border']}; "
                f"border-left: 5px solid {theme['accent']}; "
                "border-radius: 6px; padding: 8px 12px; "
                "text-align: left; color: #333; font-size: 13px; }"
                "QPushButton:hover { "
                f"background: {theme['title_bg']}; "
                "}"
            )
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, bid=board.id: self._select(bid))
            layout.addWidget(btn)

        layout.addStretch(1)

    def _select(self, board_id: int):
        self.board_selected.emit(board_id)
        self.accept()


class FloatingWindow(QWidget):
    """单个便签窗口；绑定 board。"""

    history_requested = Signal(int)        # board_id
    focus_board_requested = Signal(int)    # 切到某个 board
    delete_board_requested = Signal(int)   # 删除某个 board
    calendar_requested = Signal()          # 打开日历视图
    timer_requested = Signal(int)          # 对某条待办开始计时（todo_id）

    def __init__(
        self,
        db: Database,
        board: Board,
        on_new_board: Callable[[], None],
    ):
        super().__init__()
        self.db = db
        self.board = board
        self.on_new_board = on_new_board
        self._active_tag: Optional[str] = None
        self._active_due: Optional[str] = None  # 当前选中的日期 chip（与 _active_tag 同语义）

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setMinimumSize(300, 360)

        # 几何防抖写回
        self._geom_save_timer = QTimer(self)
        self._geom_save_timer.setSingleShot(True)
        self._geom_save_timer.setInterval(500)
        self._geom_save_timer.timeout.connect(self._save_geometry)
        self._geometry_inited = False

        # 缩放热区状态
        self._resize_edge: Optional[str] = None
        self._resize_start_pos: Optional[QPoint] = None
        self._resize_start_geo: Optional[QRect] = None

        # ---------- 容器 ----------
        container = QFrame(self)
        container.setObjectName("Container")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            RESIZE_MARGIN, RESIZE_MARGIN, RESIZE_MARGIN, RESIZE_MARGIN
        )
        outer.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(6)

        # ---------- 标题栏 ----------
        title_bar = QFrame()
        title_bar.setObjectName("TitleBar")
        title_bar.setFixedHeight(34)
        tb = QHBoxLayout(title_bar)
        tb.setContentsMargins(4, 0, 4, 0)
        tb.setSpacing(2)

        new_btn = QPushButton("+")
        new_btn.setObjectName("IconBtn")
        new_btn.setToolTip("新建便签")
        new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.setFixedSize(28, 26)
        new_btn.clicked.connect(self._on_new_board_clicked)
        tb.addWidget(new_btn)

        self.title_label = _DragLabel(f"📌 {board.title}")
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setCursor(Qt.SizeAllCursor)
        self.title_label.setToolTip("单击拖动 / 双击重命名")
        self.title_label.rename_requested.connect(self._on_rename_board)
        tb.addWidget(self.title_label, 1)

        self.more_btn = QPushButton("⋯")
        self.more_btn.setObjectName("IconBtn")
        self.more_btn.setToolTip("更多（颜色 / 便签列表 / 删除）")
        self.more_btn.setCursor(Qt.PointingHandCursor)
        self.more_btn.setFixedSize(28, 26)
        self.more_btn.clicked.connect(self._open_more_menu)
        tb.addWidget(self.more_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("IconBtn")
        close_btn.setToolTip("关闭（托盘可恢复）")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedSize(28, 26)
        close_btn.clicked.connect(self.hide)
        tb.addWidget(close_btn)

        layout.addWidget(title_bar)

        # ---------- 输入区 ----------
        input_row = QHBoxLayout()
        input_row.setContentsMargins(8, 4, 8, 0)
        self.input = QLineEdit()
        self.input.setObjectName("Input")
        self.input.setPlaceholderText("#标签 4-20 内容 | 备注（均可省略）…")
        self.input.returnPressed.connect(self._on_add)
        # 输入变化时刷新日期 chip 的激活状态
        self.input.textChanged.connect(lambda _=None: self._render_date_bar())
        add_btn = QPushButton("+")
        add_btn.setObjectName("AddBtn")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._on_add)
        input_row.addWidget(self.input)
        input_row.addWidget(add_btn)
        layout.addLayout(input_row)

        # ---------- 列表（支持拖动重排） ----------
        self.list_widget = ReorderableListWidget()
        self.list_widget.setSelectionMode(QListWidget.NoSelection)
        self.list_widget.setFocusPolicy(Qt.NoFocus)
        self.list_widget.todo_dropped.connect(self._on_todo_dropped)
        layout.addWidget(self.list_widget, 1)

        # ---------- 日期快捷 chip ----------
        self.date_bar = QWidget()
        self.date_bar_layout = QHBoxLayout(self.date_bar)
        self.date_bar_layout.setContentsMargins(8, 2, 8, 0)
        self.date_bar_layout.setSpacing(4)
        layout.addWidget(self.date_bar)

        # ---------- 标签筛选 ----------
        self.tag_bar = QWidget()
        self.tag_bar_layout = QHBoxLayout(self.tag_bar)
        self.tag_bar_layout.setContentsMargins(8, 0, 8, 0)
        self.tag_bar_layout.setSpacing(4)
        layout.addWidget(self.tag_bar)

        # ---------- 底部 ----------
        footer = QHBoxLayout()
        footer.setContentsMargins(8, 0, 8, 0)
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color:#888;font-size:12px;")
        history_btn = QPushButton("查看历史 →")
        history_btn.setObjectName("FooterBtn")
        history_btn.setCursor(Qt.PointingHandCursor)
        history_btn.clicked.connect(
            lambda: self.history_requested.emit(self.board.id)
        )
        footer.addWidget(self.count_label)
        footer.addStretch(1)
        footer.addWidget(history_btn)
        layout.addLayout(footer)

        # 应用主题
        self.apply_theme(board.color)

        # 几何：从 board 恢复，没有则智能放置（按 board id 错开）
        w = max(board.width or 340, self.minimumWidth())
        h = max(board.height or 480, self.minimumHeight())
        self.resize(w, h)
        if board.pos_x is not None and board.pos_y is not None:
            self.move(board.pos_x, board.pos_y)
            self.ensure_on_screen()
        else:
            self._move_to_top_right()
        self._geometry_inited = True

        self.refresh()

    # ---------- 主题 ----------

    def apply_theme(self, color_key: str):
        if color_key not in COLOR_THEMES:
            color_key = "yellow"
        self.board = self.board._replace(color=color_key)
        self.setStyleSheet(floating_qss(color_key))

    # ---------- 绘制 ----------

    def paintEvent(self, e):
        # alpha=1 填充整窗：让 Windows 把透明边距也视为窗口内容，确保边缘缩放可触发
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 1))

    # ---------- 边缘缩放 ----------

    def _hit_test(self, pos: QPoint) -> Optional[str]:
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        m = RESIZE_MARGIN + 2
        left, right = x <= m, x >= w - m
        top, bottom = y <= m, y >= h - m
        if left and top: return "topleft"
        if right and top: return "topright"
        if left and bottom: return "bottomleft"
        if right and bottom: return "bottomright"
        if left: return "left"
        if right: return "right"
        if top: return "top"
        if bottom: return "bottom"
        return None

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._resize_edge and (e.buttons() & Qt.LeftButton):
            self._do_resize(e.globalPosition().toPoint())
            e.accept()
            return
        edge = self._hit_test(e.position().toPoint())
        if edge:
            self.setCursor(QCursor(_CURSOR_MAP[edge]))
        else:
            self.unsetCursor()
        super().mouseMoveEvent(e)

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            edge = self._hit_test(e.position().toPoint())
            if edge:
                self._resize_edge = edge
                self._resize_start_pos = e.globalPosition().toPoint()
                self._resize_start_geo = self.geometry()
                e.accept()
                return
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent):
        if self._resize_edge:
            self._resize_edge = None
            self.unsetCursor()
            self._save_geometry()
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def leaveEvent(self, e):
        if not self._resize_edge:
            self.unsetCursor()
        super().leaveEvent(e)

    def _do_resize(self, global_pos: QPoint):
        delta = global_pos - self._resize_start_pos
        g = self._resize_start_geo
        new = QRect(g)
        edge = self._resize_edge
        min_w, min_h = self.minimumWidth(), self.minimumHeight()
        if "left" in edge:    new.setLeft(min(g.left() + delta.x(), g.right() - min_w))
        if "right" in edge:   new.setRight(max(g.right() + delta.x(), g.left() + min_w))
        if "top" in edge:     new.setTop(min(g.top() + delta.y(), g.bottom() - min_h))
        if "bottom" in edge:  new.setBottom(max(g.bottom() + delta.y(), g.top() + min_h))
        self.setGeometry(new)

    # ---------- 几何持久化 ----------

    def moveEvent(self, e):
        super().moveEvent(e)
        if self._geometry_inited:
            self._geom_save_timer.start()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._geometry_inited:
            self._geom_save_timer.start()

    def _save_geometry(self):
        try:
            self.db.update_board(
                self.board.id,
                pos_x=self.x(), pos_y=self.y(),
                width=self.width(), height=self.height(),
            )
        except Exception:
            pass

    def _move_to_top_right(self):
        screen = self.screen().availableGeometry()
        # 多便签错开堆叠：以 board id 偏移
        offset = (30 * (self.board.id - 1)) % 200
        self.move(screen.right() - self.width() - 24 - offset,
                  screen.top() + 60 + offset)

    def ensure_on_screen(self):
        """确保窗口至少有一块可操作区域位于任一当前屏幕内。

        外接显示器断开、分辨率或缩放比例变化后，数据库中的旧坐标可能
        已经落在所有屏幕之外。此时把便签移回当前屏幕右上角。
        """
        window_rect = QRect(self.x(), self.y(), self.width(), self.height())
        # 只要标题栏仍有足够区域可见，用户就能把窗口拖回来；
        # 仅正文边缘露在屏幕上时仍视为越界。
        draggable_rect = QRect(
            window_rect.x(), window_rect.y(), window_rect.width(), 50
        )
        for screen in QApplication.screens():
            visible = draggable_rect.intersected(screen.availableGeometry())
            if visible.width() >= 100 and visible.height() >= 30:
                return
        self._move_to_top_right()
        self._save_geometry()

    # ---------- 业务行为 ----------

    def _on_new_board_clicked(self):
        if self.on_new_board:
            self.on_new_board()

    def _open_more_menu(self):
        """三点菜单：色板 + 便签列表 + 删除（类似 Sticky Notes）。"""
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#FFFFFF; border:1px solid #DDDDDD; padding:2px 0; }"
            "QMenu::separator { height:1px; background:#EEEEEE; margin:4px 8px; }"
        )

        # ---- 顶部色板 ----
        color_row = ColorSwatchRow(self.board.color)
        color_row.color_chosen.connect(
            lambda k: (self._on_color_chosen(k), menu.close())
        )
        color_action = QWidgetAction(menu)
        color_action.setDefaultWidget(color_row)
        menu.addAction(color_action)

        menu.addSeparator()

        # ---- 便签列表 ----
        list_btn = QPushButton("☰   便签列表")
        list_btn.setCursor(Qt.PointingHandCursor)
        list_btn.setStyleSheet(
            "QPushButton { color:#444; padding:8px 16px; text-align:left; "
            "border:none; background:transparent; font-size:13px; }"
            "QPushButton:hover { background:#F2F2F2; }"
        )
        list_btn.clicked.connect(
            lambda: (menu.close(), self._open_board_list())
        )
        list_action = QWidgetAction(menu)
        list_action.setDefaultWidget(list_btn)
        menu.addAction(list_action)

        # ---- 日历视图 ----
        cal_btn = QPushButton("📅   日历视图")
        cal_btn.setCursor(Qt.PointingHandCursor)
        cal_btn.setStyleSheet(
            "QPushButton { color:#444; padding:8px 16px; text-align:left; "
            "border:none; background:transparent; font-size:13px; }"
            "QPushButton:hover { background:#F2F2F2; }"
        )
        cal_btn.clicked.connect(
            lambda: (menu.close(), self.calendar_requested.emit())
        )
        cal_action = QWidgetAction(menu)
        cal_action.setDefaultWidget(cal_btn)
        menu.addAction(cal_action)

        menu.addSeparator()

        # ---- 删除便签（红色） ----
        del_btn = QPushButton("🗑   删除笔记")
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet(
            "QPushButton { color:#C62828; padding:8px 16px; text-align:left; "
            "border:none; background:transparent; font-size:13px; }"
            "QPushButton:hover { background:#FFEBEE; }"
        )
        del_btn.clicked.connect(
            lambda: (menu.close(), self._on_delete_board())
        )
        del_action = QWidgetAction(menu)
        del_action.setDefaultWidget(del_btn)
        menu.addAction(del_action)

        # 弹出位置：在按钮下方右对齐
        pos = self.more_btn.mapToGlobal(
            QPoint(self.more_btn.width(), self.more_btn.height())
        )
        # 先 sizeHint 拿到宽度再右对齐
        size = menu.sizeHint()
        menu.exec_(QPoint(pos.x() - size.width(), pos.y()))

    def _on_color_chosen(self, color_key: str):
        self.apply_theme(color_key)
        self.db.update_board(self.board.id, color=color_key)
        self.refresh()  # 用新主题色重建行（正文 hover 色随主题）

    def _open_board_list(self):
        boards = self.db.list_boards()
        dlg = BoardListDialog(boards, current_id=self.board.id, parent=self)
        dlg.board_selected.connect(self.focus_board_requested.emit)
        dlg.exec()

    def _on_delete_board(self):
        reply = QMessageBox.question(
            self,
            "删除便签",
            f"确定删除便签 [{self.board.title}] 吗？\n"
            f"该便签内所有未完成 / 已完成待办都会被删除（无法恢复）。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self.delete_board_requested.emit(self.board.id)

    def _on_add(self):
        text = self.input.text().strip()
        if not text:
            return
        content, tag, due, notes = parse_input(text)
        if not content and not tag and not notes:
            return
        self.db.add(
            content or "（无内容）", tag, due,
            board_id=self.board.id, notes=notes,
        )
        self._reset_input_to_chips()
        self.refresh()

    def _reset_input_to_chips(self):
        """清掉正文与备注，但保留 #active_tag 和 active_due 作为预填，便于连续录入。"""
        prefill = format_for_edit("", self._active_tag, self._active_due, None)
        if prefill:
            prefill += " "
        self.input.setText(prefill)
        self.input.setCursorPosition(len(prefill))

    def _on_complete(self, todo_id: int):
        self.db.complete(todo_id)
        self.refresh()

    def _on_edit(self, todo_id: int):
        todo = self.db.get(todo_id)
        if not todo:
            return
        raw = format_for_edit(todo.content, todo.tag, todo.due_date, todo.notes)
        dlg = EditTodoDialog(raw, parent=self)
        result = dlg.exec()

        if result == EditTodoDialog.DELETE:
            preview = (todo.content or "")[:30]
            reply = QMessageBox.question(
                self, "删除待办",
                f"确定删除「{preview}」吗？此操作无法撤销。",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.db.delete(todo_id)
                self.refresh()
            return

        if result != EditTodoDialog.Accepted:
            return
        text = dlg.value()
        if not text:
            return
        content, tag, due, notes = parse_input(text)
        self.db.update(todo_id, content or todo.content, tag, due, notes)
        self.refresh()

    def _on_set_tag_filter(self, tag: Optional[str]):
        self._active_tag = tag
        self.refresh()
        # 用统一 helper 回填，保留已选日期；点 "全部" 时只清标签部分
        self._reset_input_to_chips()
        if tag is not None:
            self.input.setFocus()
            self.input.deselect()

    def _on_rename_board(self):
        text, ok = QInputDialog.getText(
            self, "重命名便签", "便签名称：", text=self.board.title,
        )
        if not ok:
            return
        new_title = text.strip()
        if not new_title or new_title == self.board.title:
            return
        self.db.update_board(self.board.id, title=new_title)
        self.board = self.board._replace(title=new_title)
        self.title_label.setText(f"📌 {new_title}")

    def _on_todo_dropped(self, todo_id: int, target_row: int):
        """把 todo_id 移动到 target_row 位置，重新分配整窗 sort_order。"""
        # 收集当前可见 todo_id 顺序，以及到达 target_row 前经过的 header 数
        ordered_ids: list[int] = []
        headers_before = 0
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            tid = item.data(Qt.UserRole)
            if tid is None:
                if i < target_row:
                    headers_before += 1
            else:
                ordered_ids.append(tid)

        if todo_id not in ordered_ids:
            return  # 防御

        current_pos = ordered_ids.index(todo_id)
        ordered_ids.pop(current_pos)

        target_pos = target_row - headers_before
        if current_pos < target_pos:
            target_pos -= 1  # 移除后位置前移
        target_pos = max(0, min(target_pos, len(ordered_ids)))
        ordered_ids.insert(target_pos, todo_id)

        # 整窗重新分配 sort_order = 0..N-1
        self.db.update_sort_orders({tid: idx for idx, tid in enumerate(ordered_ids)})
        self.refresh()

    # ---------- 渲染 ----------

    def refresh(self):
        self.list_widget.clear()
        all_todos = self.db.list_pending(board_id=self.board.id)
        todos = (
            all_todos if self._active_tag is None
            else [t for t in all_todos if t.tag == self._active_tag]
        )

        # 分桶
        buckets: dict[str, list[Todo]] = {k: [] for k, *_ in SECTIONS}
        for t in todos:
            status = due_status(t.due_date) if t.due_date else None
            for key, _, _, predicate, _ in SECTIONS:
                if predicate(status):
                    buckets[key].append(t)
                    break

        for key, title, header_obj, _, date_redundant in SECTIONS:
            items = buckets[key]
            if not items:
                continue
            self._add_section_header(title, header_obj, len(items))
            for t in items:
                self._append_row(
                    t,
                    hide_date=date_redundant,
                    hide_tag=(self._active_tag is not None and self._active_tag == t.tag),
                )

        self.count_label.setText(f"未完成 {len(todos)} 项")
        self._render_date_bar()
        self._render_tag_bar()

    def _add_section_header(self, text: str, header_obj: str, count: int):
        item = QListWidgetItem()
        item.setFlags(Qt.NoItemFlags)
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        title = QLabel(text)
        title.setObjectName(header_obj)
        cnt = QLabel(str(count))
        cnt.setObjectName("SectionCount")
        cnt.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h.addWidget(title, 1)
        h.addWidget(cnt, 0)
        item.setSizeHint(row.sizeHint() + QSize(0, 4))
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, row)

    def _append_row(self, todo: Todo, hide_date: bool, hide_tag: bool):
        item = QListWidgetItem(self.list_widget)
        item.setFlags(Qt.ItemIsEnabled)
        item.setData(Qt.UserRole, todo.id)  # 标记 todo 行（headers 不设此值）

        row = QWidget()
        row.setMinimumHeight(30)
        h = QHBoxLayout(row)
        h.setContentsMargins(4, 4, 10, 4)
        h.setSpacing(4)

        # 拖动手柄（按住可重排）
        handle = DragHandle(todo.id)
        h.addWidget(handle, 0, Qt.AlignVCenter)

        # 内容 + 备注（垂直排列）；用 ElidedLabel 让正文可压缩，✓ 始终可见
        accent_hover = COLOR_THEMES.get(
            self.board.color, COLOR_THEMES["yellow"]
        )["accent_hover"]
        content_lbl = ElidedLabel(
            todo.content or "（无内容）",
            color="#333", hover_color=accent_hover, font_px=13,
        )
        content_lbl.setCursor(Qt.PointingHandCursor)
        content_lbl.clicked.connect(lambda tid=todo.id: self._on_edit(tid))

        if todo.notes:
            cb = QVBoxLayout()
            cb.setContentsMargins(0, 0, 0, 0)
            cb.setSpacing(1)
            cb.addWidget(content_lbl)
            notes_lbl = ElidedLabel(todo.notes, color="#888", font_px=11)
            notes_lbl.setCursor(Qt.PointingHandCursor)
            notes_lbl.clicked.connect(lambda tid=todo.id: self._on_edit(tid))
            cb.addWidget(notes_lbl)
            h.addLayout(cb, 1)
        else:
            h.addWidget(content_lbl, 1)

        # 标签（仅在未筛选 / 与筛选不同时展示）
        if not hide_tag and todo.tag:
            tag_lbl = QLabel(f"#{todo.tag}")
            tag_lbl.setObjectName("TagInline")
            h.addWidget(tag_lbl, 0)

        # 日期（仅在分栏未表达时展示）
        if not hide_date and todo.due_date:
            ds = due_status(todo.due_date)
            if ds == "overdue":
                try:
                    days = (_date.today() - _date.fromisoformat(todo.due_date)).days
                    text = f"逾期 {days} 天"
                except Exception:
                    text = "已逾期"
                obj = "DateOverdue"
            else:
                text = format_due_label(todo.due_date)
                obj = "DateToday" if ds == "today" else "DateNormal"
            date_lbl = QLabel(text)
            date_lbl.setObjectName(obj)
            h.addWidget(date_lbl, 0)

        # 已累计专注时长徽标
        if todo.time_spent:
            spent_lbl = QLabel(f"⏱{todo.time_spent // 60}m")
            spent_lbl.setObjectName("DateNormal")
            spent_lbl.setToolTip(f"已累计专注 {todo.time_spent // 60} 分钟")
            h.addWidget(spent_lbl, 0)

        # 计时按钮（绑定该待办开始专注计时）
        timer_btn = QPushButton("⏱")
        timer_btn.setObjectName("TimerBtn")
        timer_btn.setCursor(Qt.PointingHandCursor)
        timer_btn.setFixedSize(22, 22)
        timer_btn.setToolTip("开始专注计时")
        timer_btn.clicked.connect(
            lambda _=False, tid=todo.id: self.timer_requested.emit(tid)
        )
        h.addWidget(timer_btn, 0, Qt.AlignVCenter)

        # 完成圆按钮
        done_btn = QPushButton("✓")
        done_btn.setObjectName("DoneBtn")
        done_btn.setCursor(Qt.PointingHandCursor)
        done_btn.setFixedSize(22, 22)
        done_btn.setToolTip("点击标记完成")
        done_btn.clicked.connect(
            lambda _=False, tid=todo.id: self._on_complete(tid)
        )
        h.addWidget(done_btn, 0, Qt.AlignVCenter)

        item.setSizeHint(row.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, row)

    def _render_date_bar(self):
        """日期 chip：今天 / 明天 / 后天。激活态高亮当前已选日期；再次点击切换关闭。"""
        while self.date_bar_layout.count():
            child = self.date_bar_layout.takeAt(0)
            w = child.widget()
            if w is not None:
                w.deleteLater()

        # 当前输入解析出的日期 → 决定哪个 chip 激活
        current_due: Optional[str] = None
        if hasattr(self, "input"):
            _, _, current_due, _ = parse_input(self.input.text())

        today = _date.today()
        options = [
            ("今天", today),
            ("明天", today + _timedelta(days=1)),
            ("后天", today + _timedelta(days=2)),
        ]
        for label, d in options:
            iso = d.isoformat()
            is_active = current_due == iso
            btn = QPushButton(label)
            btn.setObjectName("DateChipActive" if is_active else "DateChip")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(
                "再次点击取消" if is_active
                else f"插入 {d.month}-{d.day} 到输入框"
            )
            btn.clicked.connect(
                lambda _=False, dt=iso: self._on_quick_date(dt)
            )
            self.date_bar_layout.addWidget(btn)
        self.date_bar_layout.addStretch(1)

    def _on_quick_date(self, date_iso: str):
        """点击日期 chip：填入或切换关闭当前选中的日期（保留 #tag / 正文 / 备注）。"""
        current = self.input.text()
        content, tag, current_due, notes = parse_input(current)
        new_due = None if current_due == date_iso else date_iso
        self._active_due = new_due  # 让状态成为 chip 真值，添加待办后据此回填
        text = format_for_edit(content, tag, new_due, notes)
        if text and not text.endswith(" "):
            text += " "
        self.input.setText(text)
        self.input.setFocus()
        self.input.setCursorPosition(len(self.input.text()))

    def _render_tag_bar(self):
        while self.tag_bar_layout.count():
            child = self.tag_bar_layout.takeAt(0)
            w = child.widget()
            if w is not None:
                w.deleteLater()

        tags = self.db.list_tags(board_id=self.board.id)
        if not tags:
            self.tag_bar.hide()
            return
        self.tag_bar.show()

        all_btn = QPushButton("全部")
        all_btn.setCursor(Qt.PointingHandCursor)
        all_btn.setObjectName(
            "TagFilterActive" if self._active_tag is None else "TagFilter"
        )
        all_btn.clicked.connect(lambda: self._on_set_tag_filter(None))
        self.tag_bar_layout.addWidget(all_btn)

        for tag in tags:
            btn = QPushButton(f"#{tag}")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setObjectName(
                "TagFilterActive" if self._active_tag == tag else "TagFilter"
            )
            btn.clicked.connect(
                lambda _=False, t=tag: self._on_set_tag_filter(t)
            )
            self.tag_bar_layout.addWidget(btn)
        self.tag_bar_layout.addStretch(1)

    # ---------- 外部控制 ----------

    def toggle_visible(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def closeEvent(self, e):
        e.ignore()
        self._save_geometry()
        self.hide()
