"""已完成历史记录窗口（按 board 过滤 + 编辑备注 + 月度追加存档）。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QFileDialog,
)

from app.database import Database, Todo
from app.dialogs import NotesDialog, CompletedAtDialog
from app.settings import settings, DEFAULT_ARCHIVE_DIR
from app.styles import HISTORY_QSS


class _ClickableLabel(QLabel):
    clicked = Signal()
    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
            e.accept()
            return
        super().mousePressEvent(e)


def _safe_filename(s: str) -> str:
    bad = '<>:"/\\|?*\n\r\t'
    cleaned = "".join(c for c in s if c not in bad).strip()
    return cleaned or "未命名"


def _fmt_duration(seconds: int) -> str:
    """把秒数转成人类可读时长：1小时5分钟 / 30分钟 / 45秒。"""
    seconds = max(0, int(seconds))
    if seconds >= 3600:
        h, rem = divmod(seconds, 3600)
        m = rem // 60
        return f"{h}小时{m}分钟" if m else f"{h}小时"
    if seconds >= 60:
        return f"{seconds // 60}分钟"
    return f"{seconds}秒"


class HistoryWindow(QWidget):
    """单实例历史窗口，可切换 board_id（None=全部 boards）。"""

    restored = Signal()  # 有待办被恢复时发出，主窗口监听并刷新悬浮窗
    analyze_requested = Signal()  # 「分析」入口：主窗口监听并打开网页分析页

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.board_id: Optional[int] = None  # None 表示跨 board

        self.setObjectName("HistoryRoot")
        self.setWindowTitle("已完成历史")
        self.resize(480, 580)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        self.title_label = QLabel("✅ 已完成")
        self.title_label.setStyleSheet("font-size:15px;font-weight:bold;color:#333;")
        archive_btn = QPushButton("📥 存档为 Markdown")
        archive_btn.setObjectName("ArchiveBtn")
        archive_btn.setCursor(Qt.PointingHandCursor)
        archive_btn.setToolTip("追加写入当月汇总文件，写入后自动清空已完成列表")
        archive_btn.clicked.connect(self._on_archive)

        analyze_btn = QPushButton("📊 分析")
        analyze_btn.setObjectName("AnalyzeBtn")
        analyze_btn.setCursor(Qt.PointingHandCursor)
        analyze_btn.setToolTip("基于归档目录里的所有 markdown 生成可视化报告")
        analyze_btn.clicked.connect(self._on_analyze)

        top.addWidget(self.title_label)
        top.addStretch(1)
        top.addWidget(analyze_btn)
        top.addWidget(archive_btn)
        layout.addLayout(top)

        # 归档路径行
        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(6)

        path_icon = QLabel("📁 归档路径：")
        path_icon.setObjectName("PathLabel")

        self.path_value = QLabel()
        self.path_value.setObjectName("PathValue")
        self.path_value.setWordWrap(False)
        self.path_value.setTextInteractionFlags(Qt.TextSelectableByMouse)

        change_btn = QPushButton("更改")
        change_btn.setObjectName("PathBtn")
        change_btn.setCursor(Qt.PointingHandCursor)
        change_btn.clicked.connect(self._on_change_archive_dir)

        reset_btn = QPushButton("↺")
        reset_btn.setObjectName("PathBtn")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.setToolTip("恢复为默认路径（项目下 DoneList/）")
        reset_btn.setFixedWidth(24)
        reset_btn.clicked.connect(self._on_reset_archive_dir)

        path_row.addWidget(path_icon)
        path_row.addWidget(self.path_value, 1)
        path_row.addWidget(change_btn)
        path_row.addWidget(reset_btn)
        layout.addLayout(path_row)

        self._refresh_path_label()

        hint = QLabel("点击任意条目可编辑备注（要点 / 感受 / 提醒）")
        hint.setStyleSheet("color:#888;font-size:12px;")
        layout.addWidget(hint)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.NoSelection)
        self.list_widget.setFocusPolicy(Qt.NoFocus)
        layout.addWidget(self.list_widget, 1)

        self.empty_label = QLabel("还没有已完成的待办～")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color:#999;")
        layout.addWidget(self.empty_label)

        self.setStyleSheet(HISTORY_QSS)

    # ---------- 外部入口 ----------

    def set_board(self, board_id: Optional[int]):
        self.board_id = board_id
        if board_id is None:
            self.title_label.setText("✅ 已完成")
        else:
            board = self.db.get_board(board_id)
            name = board.title if board else f"#{board_id}"
            self.title_label.setText(f"✅ 已完成 · {name}")

    def show_and_refresh(self):
        self.refresh()
        self.show()
        self.raise_()
        self.activateWindow()

    # ---------- 渲染 ----------

    def refresh(self):
        self.list_widget.clear()
        todos = self.db.list_completed(board_id=self.board_id)
        self.empty_label.setVisible(len(todos) == 0)
        self.list_widget.setVisible(len(todos) > 0)
        for t in todos:
            self._append_row(t)

    def _append_row(self, todo: Todo):
        item = QListWidgetItem(self.list_widget)
        item.setFlags(Qt.ItemIsEnabled)

        row = QWidget()
        v = QVBoxLayout(row)
        v.setContentsMargins(10, 6, 10, 6)
        v.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(6)

        title = _ClickableLabel(todo.content or "（无内容）")
        title.setObjectName("HistTitle")
        title.setWordWrap(True)
        title.setCursor(Qt.PointingHandCursor)
        title.setToolTip("点击编辑备注")
        title.clicked.connect(lambda tid=todo.id: self._on_edit_notes(tid))
        title_row.addWidget(title, 1)

        date_btn = QPushButton("📅")
        date_btn.setObjectName("EditDateBtn")
        date_btn.setCursor(Qt.PointingHandCursor)
        date_btn.setFixedSize(22, 22)
        date_btn.setToolTip("修改完成日期")
        date_btn.clicked.connect(
            lambda _=False, tid=todo.id: self._on_edit_completed_at(tid)
        )
        title_row.addWidget(date_btn, 0, Qt.AlignTop)

        restore_btn = QPushButton("↩")
        restore_btn.setObjectName("RestoreBtn")
        restore_btn.setCursor(Qt.PointingHandCursor)
        restore_btn.setFixedSize(22, 22)
        restore_btn.setToolTip("恢复为未完成")
        restore_btn.clicked.connect(
            lambda _=False, tid=todo.id: self._on_restore(tid)
        )
        title_row.addWidget(restore_btn, 0, Qt.AlignTop)

        v.addLayout(title_row)

        meta_parts: list[str] = []
        done_at = (todo.completed_at or "").replace("T", " ")
        if done_at:
            meta_parts.append(f"完成于 {done_at}")
        if todo.tag:
            meta_parts.append(f"#{todo.tag}")
        if self.board_id is None and todo.board_id:
            board = self.db.get_board(todo.board_id)
            if board:
                meta_parts.append(f"📌 {board.title}")
        if meta_parts:
            meta = QLabel("　·　".join(meta_parts))
            meta.setObjectName("HistMeta")
            v.addWidget(meta)

        if todo.notes:
            preview = todo.notes if len(todo.notes) <= 200 else todo.notes[:200] + "…"
            note_lbl = QLabel(preview)
            note_lbl.setObjectName("NotePreview")
            note_lbl.setWordWrap(True)
            v.addWidget(note_lbl)

        item.setSizeHint(row.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, row)

    def _on_edit_notes(self, todo_id: int):
        todo = self.db.get(todo_id)
        if not todo:
            return
        dlg = NotesDialog(todo.content or "（无内容）", todo.notes or "", parent=self)
        if dlg.exec() != NotesDialog.Accepted:
            return
        self.db.update_notes(todo_id, dlg.value() or None)
        self.refresh()

    def _on_edit_completed_at(self, todo_id: int):
        todo = self.db.get(todo_id)
        if not todo or todo.status != 1:
            return
        dlg = CompletedAtDialog(
            todo.content or "（无内容）", todo.completed_at or "", parent=self
        )
        if dlg.exec() != CompletedAtDialog.Accepted:
            return
        self.db.set_completed_at(todo_id, dlg.value())
        self.refresh()

    def _on_restore(self, todo_id: int):
        self.db.uncomplete(todo_id)
        self.refresh()
        self.restored.emit()

    # ---------- 归档路径设置 ----------

    def _refresh_path_label(self) -> None:
        p = settings.archive_dir
        text = str(p)
        if len(text) > 48:
            text = text[:18] + "…" + text[-28:]
        self.path_value.setText(text)
        self.path_value.setToolTip(str(p))

    def _on_change_archive_dir(self) -> None:
        current = settings.archive_dir
        start = str(current if current.exists() else current.parent)
        chosen = QFileDialog.getExistingDirectory(self, "选择归档目录", start)
        if not chosen:
            return
        settings.archive_dir = Path(chosen)
        self._refresh_path_label()

    def _on_reset_archive_dir(self) -> None:
        settings.reset_archive_dir()
        self._refresh_path_label()

    # ---------- 分析报告 ----------

    def _on_analyze(self) -> None:
        # 分析页已集成到网页日历（数据 = 归档 + 未归档已完成），空态由网页承担
        self.analyze_requested.emit()

    # ---------- 存档（按月追加） ----------

    def _on_archive(self):
        todos = self.db.list_completed(board_id=self.board_id, limit=10000)
        if not todos:
            QMessageBox.information(self, "存档", "暂无已完成的待办可存档。")
            return

        archive_dir = settings.archive_dir
        try:
            archive_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(
                self, "存档失败",
                f"无法创建归档目录：\n{archive_dir}\n{exc}",
            )
            return

        ym = datetime.now().strftime("%Y-%m")
        if self.board_id is None:
            # 跨所有便签合并归档：每月一个 markdown
            fname = f"completed_{ym}.md"
            scope = "全部便签"
        else:
            board = self.db.get_board(self.board_id)
            scope = board.title if board else f"board_{self.board_id}"
            fname = f"completed_{ym}_{_safe_filename(scope)}.md"
        target = archive_dir / fname

        batch = self._build_batch_markdown(todos, scope)
        try:
            if target.exists():
                prev = target.read_text(encoding="utf-8").rstrip()
                new_content = prev + "\n\n" + batch + "\n"
                action = "追加到"
            else:
                header = (
                    f"# 已完成待办存档 · {ym} · {scope}\n\n"
                    f"> 本文件聚合 {ym} 内 [{scope}] 的全部存档批次。\n"
                )
                new_content = header + "\n" + batch + "\n"
                action = "新建"
            target.write_text(new_content, encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "存档失败", f"无法写入文件：\n{exc}")
            return

        self.db.delete_all_completed(board_id=self.board_id)
        self.refresh()

        QMessageBox.information(
            self,
            "存档成功",
            f"已{action}：{target.name}\n路径：{target.parent}\n"
            f"本次写入 {len(todos)} 条，已完成列表已清空。",
        )

    def _build_batch_markdown(self, todos: list[Todo], scope: str) -> str:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        boards = {b.id: b.title for b in self.db.list_boards()}
        lines = [
            "---",
            "",
            f"## 存档于 {ts} · {len(todos)} 项 · {scope}",
            "",
        ]
        for t in todos:
            tag_part = f" `#{t.tag}`" if t.tag else ""
            due_part = f" 📅 {t.due_date}" if t.due_date else ""
            done_at = (t.completed_at or "").replace("T", " ")
            lines.append(f"- [x] {t.content or '（无内容）'}{tag_part}{due_part}")
            if done_at:
                lines.append(f"  - 完成于：{done_at}")
            board_title = boards.get(t.board_id, "未知便签")
            lines.append(f"  - 所属便签：📌 {board_title}")
            if t.time_spent:
                start = (t.time_started_at or "").replace("T", " ") or "—"
                end = (t.time_ended_at or "").replace("T", " ") or "—"
                lines.append(
                    f"  - 专注：{start} ~ {end} · 时长 {_fmt_duration(t.time_spent)}"
                )
            if t.notes:
                lines.append("  - 备注：")
                for ln in (t.notes.splitlines() or [""]):
                    lines.append(f"    > {ln}")
            lines.append("")
        return "\n".join(lines).rstrip()
