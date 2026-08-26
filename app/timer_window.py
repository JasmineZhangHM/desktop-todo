"""专注计时器：绑定一条待办，支持倒计时（番茄钟）与正向秒表。

- 倒计时：选预设时长（25/45/60/自定义），跑到 0 系统通知提醒。
- 秒表：从 0 正向累加，手动停止。
- 两种模式跑过的真实秒数都会累加写回该待办的 time_spent。
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QInputDialog,
)

from app.database import Database, Todo
from app.floating_window import _DragLabel
from app.styles import TIMER_QSS

MODE_COUNTDOWN = "countdown"
MODE_STOPWATCH = "stopwatch"
_PRESETS = [25, 45, 60]  # 分钟


def _fmt(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class FocusTimerWindow(QWidget):
    """单实例计时器；通过 bind_todo() 绑定不同待办。"""

    finished = Signal(str)  # 倒计时结束，携带待办标题用于通知

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.todo_id: Optional[int] = None
        self.todo_title: str = ""

        self._mode = MODE_COUNTDOWN
        self._preset_min = 25
        self._remaining = self._preset_min * 60   # 倒计时剩余
        self._elapsed = 0                          # 秒表已用
        self._session_seconds = 0                  # 本段未写回的真实计时
        self._running = False

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(290, 320)

        self._build_ui()
        self.setStyleSheet(TIMER_QSS)
        self._refresh_mode_buttons()
        self._refresh_preset_buttons()
        self._update_display()

    # ---------- UI ----------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        container = QFrame()
        container.setObjectName("TimerRoot")
        outer.addWidget(container)

        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 12)
        v.setSpacing(8)

        # 标题栏（可拖动 + 关闭）
        bar = QFrame()
        bar.setObjectName("TimerBar")
        bar.setFixedHeight(30)
        hb = QHBoxLayout(bar)
        hb.setContentsMargins(10, 0, 6, 0)
        title = _DragLabel("⏱ 专注计时")
        title.setObjectName("TimerTitle")
        title.setCursor(Qt.SizeAllCursor)
        close = QPushButton("✕")
        close.setObjectName("TimerClose")
        close.setCursor(Qt.PointingHandCursor)
        close.setFixedSize(24, 22)
        close.clicked.connect(self.hide)
        hb.addWidget(title, 1)
        hb.addWidget(close)
        v.addWidget(bar)

        # 绑定的待办
        self.bound_lbl = QLabel("未绑定待办")
        self.bound_lbl.setObjectName("TimerBound")
        self.bound_lbl.setAlignment(Qt.AlignCenter)
        self.bound_lbl.setWordWrap(True)
        v.addWidget(self.bound_lbl)

        # 模式切换
        mode_row = QHBoxLayout()
        mode_row.setContentsMargins(12, 0, 12, 0)
        mode_row.setSpacing(8)
        self.countdown_btn = QPushButton("倒计时")
        self.countdown_btn.setCursor(Qt.PointingHandCursor)
        self.countdown_btn.clicked.connect(lambda: self._set_mode(MODE_COUNTDOWN))
        self.stopwatch_btn = QPushButton("秒表")
        self.stopwatch_btn.setCursor(Qt.PointingHandCursor)
        self.stopwatch_btn.clicked.connect(lambda: self._set_mode(MODE_STOPWATCH))
        mode_row.addStretch(1)
        mode_row.addWidget(self.countdown_btn)
        mode_row.addWidget(self.stopwatch_btn)
        mode_row.addStretch(1)
        v.addLayout(mode_row)

        # 大显示
        self.display = QLabel("25:00")
        self.display.setObjectName("TimerDisplay")
        self.display.setAlignment(Qt.AlignCenter)
        v.addWidget(self.display)

        # 倒计时预设
        self.preset_row_widget = QWidget()
        preset_row = QHBoxLayout(self.preset_row_widget)
        preset_row.setContentsMargins(12, 0, 12, 0)
        preset_row.setSpacing(6)
        self._preset_btns: dict[int, QPushButton] = {}
        preset_row.addStretch(1)
        for m in _PRESETS:
            b = QPushButton(f"{m}分")
            b.setObjectName("PresetBtn")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, mm=m: self._set_preset(mm))
            preset_row.addWidget(b)
            self._preset_btns[m] = b
        custom = QPushButton("自定义")
        custom.setObjectName("PresetBtn")
        custom.setCursor(Qt.PointingHandCursor)
        custom.clicked.connect(self._set_custom_preset)
        preset_row.addWidget(custom)
        preset_row.addStretch(1)
        v.addWidget(self.preset_row_widget)

        # 控制
        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(12, 4, 12, 0)
        ctrl_row.setSpacing(8)
        self.start_btn = QPushButton("开始")
        self.start_btn.setObjectName("CtrlBtn")
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self._toggle_start)
        reset_btn = QPushButton("重置")
        reset_btn.setObjectName("CtrlBtnGhost")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.clicked.connect(self._reset)
        ctrl_row.addWidget(self.start_btn, 2)
        ctrl_row.addWidget(reset_btn, 1)
        v.addLayout(ctrl_row)

        self.hint = QLabel("")
        self.hint.setObjectName("TimerHint")
        self.hint.setAlignment(Qt.AlignCenter)
        v.addWidget(self.hint)

    # ---------- 外部入口 ----------

    def bind_todo(self, todo: Todo):
        """绑定到一条待办；切换前把上一段计时写回。"""
        self._stop_timer(flush=True)
        self.todo_id = todo.id
        self.todo_title = todo.content or "（无内容）"
        self.bound_lbl.setText(f"▶ {self.todo_title}")
        total = todo.time_spent or 0
        if total > 0:
            self.hint.setText(f"已累计专注 {total // 60} 分钟")
        else:
            self.hint.setText("")
        # 重置当前模式的计时
        self._reset(flush=False)

    def show_for(self, todo: Todo):
        self.bind_todo(todo)
        self.show()
        self.raise_()
        self.activateWindow()

    # ---------- 计时逻辑 ----------

    def _tick(self):
        self._session_seconds += 1
        if self._mode == MODE_COUNTDOWN:
            self._remaining -= 1
            if self._remaining <= 0:
                self._remaining = 0
                self._update_display()
                self._stop_timer(flush=True)
                self.start_btn.setText("开始")
                self.finished.emit(self.todo_title)
                self.hint.setText("⏰ 时间到！")
                return
        else:
            self._elapsed += 1
        self._update_display()

    def _toggle_start(self):
        if self._running:
            self._stop_timer(flush=True)
            self.start_btn.setText("继续")
            return
        if self._mode == MODE_COUNTDOWN and self._remaining <= 0:
            self._remaining = self._preset_min * 60
        if self.todo_id is not None:
            self.db.mark_timer_start(self.todo_id)
        self._running = True
        self._timer.start()
        self.start_btn.setText("暂停")

    def _stop_timer(self, flush: bool):
        if self._timer.isActive():
            self._timer.stop()
        self._running = False
        if flush:
            self._flush()

    def _flush(self):
        if self.todo_id is not None and self._session_seconds > 0:
            self.db.add_time_spent(self.todo_id, self._session_seconds)
        self._session_seconds = 0

    def _reset(self, flush: bool = True):
        self._stop_timer(flush=flush)
        if self._mode == MODE_COUNTDOWN:
            self._remaining = self._preset_min * 60
        else:
            self._elapsed = 0
        self.start_btn.setText("开始")
        self._update_display()

    def _set_mode(self, mode: str):
        if mode == self._mode:
            return
        self._stop_timer(flush=True)
        self._mode = mode
        self.preset_row_widget.setVisible(mode == MODE_COUNTDOWN)
        self.start_btn.setText("开始")
        if mode == MODE_COUNTDOWN:
            self._remaining = self._preset_min * 60
        else:
            self._elapsed = 0
        self._refresh_mode_buttons()
        self._update_display()

    def _set_preset(self, minutes: int):
        self._stop_timer(flush=True)
        self._preset_min = minutes
        self._remaining = minutes * 60
        self.start_btn.setText("开始")
        self._refresh_preset_buttons()
        self._update_display()

    def _set_custom_preset(self):
        minutes, ok = QInputDialog.getInt(
            self, "自定义时长", "分钟：", value=self._preset_min, minValue=1, maxValue=600,
        )
        if ok:
            self._set_preset(minutes)

    # ---------- 显示 ----------

    def _update_display(self):
        if self._mode == MODE_COUNTDOWN:
            self.display.setText(_fmt(self._remaining))
        else:
            self.display.setText(_fmt(self._elapsed))

    def _refresh_mode_buttons(self):
        self.countdown_btn.setObjectName(
            "ModeBtnActive" if self._mode == MODE_COUNTDOWN else "ModeBtn"
        )
        self.stopwatch_btn.setObjectName(
            "ModeBtnActive" if self._mode == MODE_STOPWATCH else "ModeBtn"
        )
        for b in (self.countdown_btn, self.stopwatch_btn):
            b.style().unpolish(b)
            b.style().polish(b)

    def _refresh_preset_buttons(self):
        for m, b in self._preset_btns.items():
            b.setObjectName("PresetBtnActive" if m == self._preset_min else "PresetBtn")
            b.style().unpolish(b)
            b.style().polish(b)

    # ---------- 关闭：写回未结算的计时 ----------

    def closeEvent(self, e):
        self._stop_timer(flush=True)
        super().closeEvent(e)

    def hideEvent(self, e):
        self._stop_timer(flush=True)
        super().hideEvent(e)
