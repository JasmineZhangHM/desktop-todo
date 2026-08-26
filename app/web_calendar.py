"""网页版日历：本地 HTTP 服务器（仅 127.0.0.1）+ 默认浏览器打开。

- 静态页面在 app/webcal/，通过 GET / 提供
- /api/* 读写 SQLite（Database 每次操作新建连接，跨线程安全）
- 写操作成功后 emit changed，主线程刷新悬浮便签
"""
from __future__ import annotations

import json
import threading
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal

from app import analytics
from app.database import Database, Todo
from app.settings import settings
from app.styles import COLOR_THEMES

_MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


def _todo_to_dict(t: Todo) -> dict:
    return {
        "id": t.id,
        "content": t.content,
        "status": t.status,
        "tag": t.tag,
        "due_date": t.due_date,
        "notes": t.notes,
        "board_id": t.board_id,
        "completed_at": t.completed_at,
        "time_spent": t.time_spent,
    }


def _db_todo_to_record(t: Todo, board_names: dict[int, str]) -> analytics.Record:
    """把 db 里已完成未归档的待办转成分析用 Record（时间统一为空格分隔格式）。"""

    def _norm(ts: Optional[str]) -> Optional[str]:
        return ts.replace("T", " ") if ts else None

    return analytics.Record(
        content=t.content,
        tag=t.tag,
        due_date=t.due_date,
        completed_at=_norm(t.completed_at),
        notes=t.notes,
        batch_archived_at=None,
        source_file=analytics.DB_SOURCE,
        board=board_names.get(t.board_id),
        focus_start=_norm(t.time_started_at),
        focus_end=_norm(t.time_ended_at),
        focus_seconds=t.time_spent or 0,
    )


class _Handler(BaseHTTPRequestHandler):
    # 由 WebCalendarServer 注入
    owner: "WebCalendarServer"

    server_version = "DesktopTodoCal/1.0"

    # ---------- 基础 ----------

    def log_message(self, fmt, *args):  # noqa: N802 - 静默访问日志
        pass

    def _check_host(self) -> bool:
        host = self.headers.get("Host", "")
        if host.startswith("127.0.0.1") or host.startswith("localhost"):
            return True
        self._send_json({"error": "forbidden"}, 403)
        return False

    def _send_json(self, obj, code: int = 200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> Optional[dict]:
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length)) if length else {}
            if not isinstance(data, dict):
                raise ValueError
            return data
        except (ValueError, json.JSONDecodeError):
            self._send_json({"error": "invalid json"}, 400)
            return None

    def _todo_id_from_path(self) -> Optional[int]:
        # /api/todos/<id>
        parts = self.path.split("?")[0].strip("/").split("/")
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "todos":
            try:
                return int(parts[2])
            except ValueError:
                pass
        self._send_json({"error": "not found"}, 404)
        return None

    def _handle_db(self, fn):
        """执行数据库操作，OperationalError（锁冲突等）返回 503。"""
        import sqlite3

        try:
            return True, fn()
        except sqlite3.OperationalError as e:
            self._send_json({"error": f"database busy: {e}"}, 503)
            return False, None

    # ---------- GET：静态文件 + /api/state ----------

    def do_GET(self):  # noqa: N802
        if not self._check_host():
            return
        path = self.path.split("?")[0]
        if path == "/api/state":
            self._api_state()
            return
        if path == "/api/analytics":
            self._api_analytics()
            return
        self._serve_static(path)

    def _serve_static(self, path: str):
        if path == "/":
            path = "/index.html"
        static_dir = self.owner.static_dir
        target = (static_dir / path.lstrip("/")).resolve()
        # 路径穿越防护
        if not str(target).startswith(str(static_dir.resolve())) or not target.is_file():
            self._send_json({"error": "not found"}, 404)
            return
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", _MIME.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _api_state(self):
        db = self.owner.db

        def load():
            boards = []
            for b in db.list_boards():
                theme = COLOR_THEMES.get(b.color, COLOR_THEMES["yellow"])
                boards.append(
                    {
                        "id": b.id,
                        "title": b.title,
                        "color": b.color,
                        "accent": theme["accent"],
                    }
                )
            return {
                "todos": [_todo_to_dict(t) for t in db.list_pending(None)],
                "completed": [_todo_to_dict(t) for t in db.list_completed(None, limit=500)],
                "boards": boards,
                "tags": db.list_tags(None),
                "default_board_id": db.default_board_id(),
                "today": date.today().isoformat(),
            }

        ok, state = self._handle_db(load)
        if ok:
            self._send_json(state)

    def _api_analytics(self):
        """归档 md 记录 + db 已完成未归档记录，合并出分析视图数据。"""
        db = self.owner.db
        try:
            records = list(self.owner.archive_records())
            board_names = {b.id: b.title for b in db.list_boards()}
            records.extend(
                _db_todo_to_record(t, board_names)
                for t in db.list_completed(None, limit=10000)
            )
            self._send_json(analytics.build_view_data(records))
        except Exception as e:  # noqa: BLE001 — 归档 md 格式异常等兜底
            self._send_json({"error": f"analytics failed: {e}"}, 500)

    # ---------- 写操作 ----------

    def do_POST(self):  # noqa: N802
        if not self._check_host():
            return
        if self.path.split("?")[0] != "/api/todos":
            self._send_json({"error": "not found"}, 404)
            return
        data = self._read_body()
        if data is None:
            return
        content = (data.get("content") or "").strip()
        if not content:
            self._send_json({"error": "content required"}, 400)
            return
        db = self.owner.db
        ok, new_id = self._handle_db(
            lambda: db.add(
                content,
                tag=data.get("tag") or None,
                due_date=data.get("due_date") or None,
                board_id=data.get("board_id") or None,
                notes=data.get("notes") or None,
            )
        )
        if ok:
            self.owner.changed.emit()
            self._send_json({"id": new_id}, 201)

    def do_PUT(self):  # noqa: N802
        if not self._check_host():
            return
        todo_id = self._todo_id_from_path()
        if todo_id is None:
            return
        data = self._read_body()
        if data is None:
            return
        content = (data.get("content") or "").strip()
        if not content:
            self._send_json({"error": "content required"}, 400)
            return
        db = self.owner.db
        if db.get(todo_id) is None:
            self._send_json({"error": "not found"}, 404)
            return
        ok, _ = self._handle_db(
            lambda: db.update(
                todo_id,
                content,
                data.get("tag") or None,
                data.get("due_date") or None,
                data.get("notes") or None,
            )
        )
        if ok:
            self.owner.changed.emit()
            self._send_json({"ok": True})

    def do_PATCH(self):  # noqa: N802
        if not self._check_host():
            return
        todo_id = self._todo_id_from_path()
        if todo_id is None:
            return
        data = self._read_body()
        if data is None:
            return
        db = self.owner.db
        if db.get(todo_id) is None:
            self._send_json({"error": "not found"}, 404)
            return

        def apply():
            if "due_date" in data:
                db.set_due_date(todo_id, data["due_date"] or None)
            if "done" in data:
                if data["done"]:
                    db.complete(todo_id)
                else:
                    db.uncomplete(todo_id)

        ok, _ = self._handle_db(apply)
        if ok:
            self.owner.changed.emit()
            self._send_json({"ok": True})

    def do_DELETE(self):  # noqa: N802
        if not self._check_host():
            return
        todo_id = self._todo_id_from_path()
        if todo_id is None:
            return
        db = self.owner.db
        ok, _ = self._handle_db(lambda: db.delete(todo_id))
        if ok:
            self.owner.changed.emit()
            self._send_json({"ok": True})


class WebCalendarServer(QObject):
    """懒启动的本地日历服务。changed 信号在 HTTP 线程 emit，
    PySide6 会以 QueuedConnection 投递到主线程，跨线程安全。"""

    changed = Signal()

    def __init__(self, db: Database, static_dir: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.db = db
        self.static_dir = Path(static_dir)
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        # 归档 md 解析缓存：文件签名不变则复用（focus 刷新高频触发）
        self._archive_lock = threading.Lock()
        self._archive_sig: Optional[tuple] = None
        self._archive_cache: list[analytics.Record] = []

    def archive_records(self) -> list[analytics.Record]:
        archive_dir = settings.archive_dir
        sig_items = []
        if archive_dir.exists():
            for p in sorted(archive_dir.glob("completed_*.md")):
                try:
                    st = p.stat()
                    sig_items.append((str(p), st.st_mtime_ns, st.st_size))
                except OSError:
                    continue
        sig = tuple(sig_items)
        with self._archive_lock:
            if sig != self._archive_sig:
                self._archive_cache = analytics.parse_archive_dir(archive_dir)
                self._archive_sig = sig
            return self._archive_cache

    def ensure_started(self) -> int:
        with self._lock:
            if self._server is not None:
                return self._server.server_address[1]
            handler = type("BoundHandler", (_Handler,), {"owner": self})
            self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            self._thread = threading.Thread(
                target=self._server.serve_forever, name="webcal-http", daemon=True
            )
            self._thread.start()
            return self._server.server_address[1]

    def open_in_browser(self, fragment: str = ""):
        port = self.ensure_started()
        webbrowser.open(f"http://127.0.0.1:{port}/{fragment}")

    def stop(self):
        with self._lock:
            server, thread = self._server, self._thread
            self._server = self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2)
