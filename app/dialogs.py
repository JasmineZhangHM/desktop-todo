"""可复用弹窗：编辑待办 / 编辑备注 / 修改完成日期。"""
from __future__ import annotations

from datetime import date as _date, datetime as _datetime, timedelta as _timedelta
from typing import Optional

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QTextEdit,
    QPushButton, QLabel, QDateEdit,
)

from app.parser import parse_input, format_for_edit, format_due_label


_CHIP_INACTIVE = (
    "QPushButton { background:#FFF3E0; color:#E65100;"
    " border:1px solid #FFCC80; border-radius:10px;"
    " padding:4px 14px; font-size:12px; }"
    "QPushButton:hover { background:#FFE0B2; border:1px solid #FF9800; }"
)
_CHIP_ACTIVE = (
    "QPushButton { background:#FB8C00; color:#FFFFFF;"
    " border:1px solid #E65100; border-radius:10px;"
    " padding:4px 14px; font-size:12px; font-weight:bold; }"
    "QPushButton:hover { background:#F57C00; }"
)
_CHIP_NEUTRAL = (
    "QPushButton { background:#F5F5F5; color:#777;"
    " border:1px solid #DDD; border-radius:10px;"
    " padding:4px 12px; font-size:12px; }"
    "QPushButton:hover { background:#EEEEEE; color:#333; }"
)


class EditTodoDialog(QDialog):
    """编辑未完成待办：分字段表单（内容 / 标签 / 日期 / 备注）。

    左下角"删除"按钮直接删除该待办（外部需 done() 拿到 DELETE 结果码）。
    `value()` 仍返回 `#标签 4-20 内容 | 备注` 形式的字符串，与既有调用方兼容。
    """

    DELETE = 100  # exec() 的自定义返回码

    def __init__(self, raw_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑待办")
        self.resize(440, 400)

        content, tag, due_date, notes = parse_input(raw_text)
        self._due: Optional[str] = due_date

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(8)

        # ---- 内容 ----
        layout.addWidget(self._field_label("📝 内容"))
        self.content_input = QLineEdit(content)
        self.content_input.setPlaceholderText("写点要做的事…")
        self.content_input.setStyleSheet(self._input_qss())
        layout.addWidget(self.content_input)

        layout.addSpacing(2)

        # ---- 标签 ----
        layout.addWidget(self._field_label("🏷 标签"))
        self.tag_input = QLineEdit(tag or "")
        self.tag_input.setPlaceholderText("可空；不需要写 # 号")
        self.tag_input.setStyleSheet(self._input_qss())
        layout.addWidget(self.tag_input)

        layout.addSpacing(2)

        # ---- 日期 ----
        layout.addWidget(self._field_label("📅 日期"))
        date_row = QHBoxLayout()
        date_row.setSpacing(6)
        today = _date.today()
        self._date_options: list[tuple[str, str]] = [
            ("今天", today.isoformat()),
            ("明天", (today + _timedelta(days=1)).isoformat()),
            ("后天", (today + _timedelta(days=2)).isoformat()),
        ]
        self._date_btns: list[QPushButton] = []
        for label, iso in self._date_options:
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, x=iso: self._toggle_date(x))
            date_row.addWidget(btn)
            self._date_btns.append(btn)
        clear_btn = QPushButton("清除")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet(_CHIP_NEUTRAL)
        clear_btn.clicked.connect(lambda: self._set_date(None))
        date_row.addWidget(clear_btn)
        date_row.addStretch(1)
        self.date_hint = QLabel("")
        self.date_hint.setStyleSheet("color:#888;font-size:12px;")
        date_row.addWidget(self.date_hint)
        layout.addLayout(date_row)

        layout.addSpacing(4)

        # ---- 备注 ----
        layout.addWidget(self._field_label("💭 备注"))
        self.notes_input = QTextEdit()
        self.notes_input.setPlainText(notes or "")
        self.notes_input.setFixedHeight(90)
        self.notes_input.setStyleSheet(
            "QTextEdit { background:#FFFFFF; border:1px solid #E0E0E0;"
            " border-radius:4px; padding:6px; font-size:13px; color:#333; }"
            "QTextEdit:focus { border:1px solid #1A56DB; }"
        )
        layout.addWidget(self.notes_input, 1)

        # ---- 按钮 ----
        btn_row = QHBoxLayout()
        del_btn = QPushButton("删除")
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet(
            "QPushButton { color:#C62828; padding:6px 14px;"
            " border:1px solid #FFCDD2; border-radius:4px; background:#FFFFFF; }"
            "QPushButton:hover { background:#FFEBEE; border:1px solid #EF9A9A; }"
        )
        del_btn.clicked.connect(lambda: self.done(EditTodoDialog.DELETE))
        btn_row.addWidget(del_btn)
        btn_row.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setStyleSheet(
            "QPushButton { padding:6px 14px; border:1px solid #DDD;"
            " border-radius:4px; background:#FFFFFF; color:#555; }"
            "QPushButton:hover { background:#F5F5F5; }"
        )
        cancel.clicked.connect(self.reject)
        ok = QPushButton("保存")
        ok.setCursor(Qt.PointingHandCursor)
        ok.setDefault(True)
        ok.setStyleSheet(
            "QPushButton { padding:6px 16px; border:1px solid #1A56DB;"
            " border-radius:4px; background:#1A56DB; color:#FFFFFF;"
            " font-weight:bold; }"
            "QPushButton:hover { background:#1545A8; }"
        )
        ok.clicked.connect(self.accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        layout.addLayout(btn_row)

        self.content_input.setFocus()
        self.content_input.selectAll()
        self._refresh_date_state()

    @staticmethod
    def _field_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#555;font-size:12px;font-weight:bold;")
        return lbl

    @staticmethod
    def _input_qss() -> str:
        return (
            "QLineEdit { background:#FFFFFF; border:1px solid #E0E0E0;"
            " border-radius:4px; padding:6px 8px; font-size:13px; color:#333; }"
            "QLineEdit:focus { border:1px solid #1A56DB; }"
        )

    def _toggle_date(self, iso: str) -> None:
        self._due = None if self._due == iso else iso
        self._refresh_date_state()

    def _set_date(self, iso: Optional[str]) -> None:
        self._due = iso
        self._refresh_date_state()

    def _refresh_date_state(self) -> None:
        for btn, (_, iso) in zip(self._date_btns, self._date_options):
            btn.setStyleSheet(_CHIP_ACTIVE if self._due == iso else _CHIP_INACTIVE)
        if self._due:
            label = format_due_label(self._due)
            self.date_hint.setText(f"已选：{label}（{self._due}）")
        else:
            self.date_hint.setText("无截止日期")

    def value(self) -> str:
        content = self.content_input.text().strip()
        tag = self.tag_input.text().strip().lstrip("#") or None
        notes = self.notes_input.toPlainText().strip() or None
        return format_for_edit(content, tag, self._due, notes)


class NotesDialog(QDialog):
    """已完成待办的备注编辑：要点 / 感受 / 提醒事项等。"""

    def __init__(self, title: str, initial: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑备注")
        self.resize(460, 340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        head = QLabel(f"📝 {title}")
        head.setStyleSheet("font-weight:bold;color:#333;font-size:14px;")
        head.setWordWrap(True)
        layout.addWidget(head)

        hint = QLabel("可记录：要点回顾 / 心得感受 / 后续提醒（支持多行）")
        hint.setStyleSheet("color:#888;font-size:12px;")
        layout.addWidget(hint)

        self.editor = QTextEdit()
        self.editor.setPlainText(initial or "")
        self.editor.setStyleSheet(
            "QTextEdit { background:#FFFFFF; border:1px solid #E0E0E0; "
            "border-radius:6px; padding:8px; font-size:13px; color:#333; }"
        )
        layout.addWidget(self.editor, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("保存")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        layout.addLayout(btn_row)

    def value(self) -> str:
        return self.editor.toPlainText().strip()


class CompletedAtDialog(QDialog):
    """修改已完成待办的完成日期（保留原时分秒）。"""

    def __init__(self, title: str, completed_at: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("修改完成日期")
        self.resize(320, 160)
        try:
            self._orig = _datetime.fromisoformat(completed_at)
        except (TypeError, ValueError):
            self._orig = _datetime.now()  # 异常数据兜底

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        head = QLabel(f"📅 {title}")
        head.setStyleSheet("font-weight:bold;color:#333;font-size:14px;")
        head.setWordWrap(True)
        layout.addWidget(head)

        self.date_edit = QDateEdit(
            QDate(self._orig.year, self._orig.month, self._orig.day)
        )
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setStyleSheet(
            "QDateEdit { background:#FFFFFF; border:1px solid #E0E0E0;"
            " border-radius:4px; padding:6px 8px; font-size:13px; color:#333; }"
        )
        layout.addWidget(self.date_edit)

        hint = QLabel(f"完成时刻保留原时间 {self._orig.strftime('%H:%M:%S')}")
        hint.setStyleSheet("color:#888;font-size:12px;")
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("保存")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        layout.addLayout(btn_row)

    def value(self) -> str:
        d = self.date_edit.date()
        return _datetime(
            d.year(), d.month(), d.day(),
            self._orig.hour, self._orig.minute, self._orig.second,
        ).isoformat(timespec="seconds")
