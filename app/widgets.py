"""公共小控件。"""
from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QListWidget


class AutoResizeListWidget(QListWidget):
    """窗口/视口宽度变化时，强制每个 item 按当前视口宽度重算尺寸。

    解决痛点：默认 QListWidget 用创建时一次性设置的 sizeHint 排版，
    窗口收窄后 item 不会跟着变窄，导致子 widget（例如 DoneBtn）被水平裁切。
    """

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._sync_item_sizes()

    def _sync_item_sizes(self):
        vw = self.viewport().width()
        if vw <= 0:
            return
        for i in range(self.count()):
            item = self.item(i)
            w = self.itemWidget(item)
            if w is None:
                continue
            w.setFixedWidth(vw)
            h = w.sizeHint().height()
            # word-wrap 生效的行（history 展开态等）用 heightForWidth 作兜底
            if w.hasHeightForWidth():
                h = max(h, w.heightForWidth(vw))
            item.setSizeHint(QSize(vw, h))

    def refresh_item_sizes(self):
        """在外部手动触发（例如展开/收起后）重新对齐 item 尺寸。"""
        self._sync_item_sizes()
