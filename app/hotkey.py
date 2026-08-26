"""全局快捷键监听：pynput 后台线程 → Qt 主线程 signal。"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class GlobalHotkey(QObject):
    """注册一个全局快捷键；按下时发 `triggered` 信号（主线程）。

    pynput 的回调在它自己的监听线程，**禁止**直接动 Qt 控件。
    通过 Signal 自动跨线程派发到主线程。
    """

    triggered = Signal()

    def __init__(self, combo: str = "<ctrl>+<alt>+m"):
        super().__init__()
        self.combo = combo
        self._listener = None

    def start(self) -> bool:
        try:
            from pynput import keyboard
        except Exception as e:
            print(f"[hotkey] pynput 未安装，跳过全局快捷键：{e}")
            return False
        try:
            self._listener = keyboard.GlobalHotKeys(
                {self.combo: self.triggered.emit}
            )
            self._listener.start()
            return True
        except Exception as e:
            print(f"[hotkey] 注册 {self.combo} 失败：{e}")
            self._listener = None
            return False

    def stop(self):
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
