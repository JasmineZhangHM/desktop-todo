"""SQLite 封装：建表、字段迁移与 CRUD。

v4 改动：
- 引入 boards 表，每个 board = 一个独立的悬浮便签窗口
- todos 表加 board_id 外键
- 所有读写按 board_id 过滤；自动迁移历史数据到默认 board
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import NamedTuple, Optional


class Todo(NamedTuple):
    id: int
    content: str
    status: int
    created_at: str
    completed_at: Optional[str] = None
    tag: Optional[str] = None
    due_date: Optional[str] = None
    notes: Optional[str] = None
    board_id: Optional[int] = None
    sort_order: int = 0
    time_spent: int = 0  # 累计专注秒数（计时器写回）
    time_started_at: Optional[str] = None  # 首次开始计时的时间
    time_ended_at: Optional[str] = None    # 最近一次计时活动的时间


class Board(NamedTuple):
    id: int
    title: str
    color: str
    pos_x: Optional[int]
    pos_y: Optional[int]
    width: int
    height: int
    created_at: str


def _default_db_path() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) / "DesktopTodo" if appdata else Path.home() / ".desktop_todo"
    base.mkdir(parents=True, exist_ok=True)
    return base / "todos.db"


_REQUIRED_TODO_COLS = {
    "tag":        "TEXT",
    "due_date":   "TEXT",
    "notes":      "TEXT",
    "board_id":   "INTEGER",
    "sort_order": "INTEGER NOT NULL DEFAULT 0",
    "time_spent": "INTEGER NOT NULL DEFAULT 0",
    "time_started_at": "TEXT",
    "time_ended_at": "TEXT",
}


class Database:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or _default_db_path()
        self._default_board_id: Optional[int] = None

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self._conn() as c:
            # todos 主表
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS todos (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    content      TEXT    NOT NULL,
                    status       INTEGER NOT NULL DEFAULT 0,
                    created_at   TEXT    NOT NULL,
                    completed_at TEXT
                )
                """
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status)")

            # boards 表
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS boards (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    title       TEXT    NOT NULL DEFAULT '便签',
                    color       TEXT    NOT NULL DEFAULT 'yellow',
                    pos_x       INTEGER,
                    pos_y       INTEGER,
                    width       INTEGER DEFAULT 340,
                    height      INTEGER DEFAULT 480,
                    created_at  TEXT    NOT NULL
                )
                """
            )

            # todos 列迁移
            existing = {r["name"] for r in c.execute("PRAGMA table_info(todos)").fetchall()}
            sort_order_just_added = "sort_order" not in existing
            for col, ct in _REQUIRED_TODO_COLS.items():
                if col not in existing:
                    c.execute(f"ALTER TABLE todos ADD COLUMN {col} {ct}")
            c.execute("CREATE INDEX IF NOT EXISTS idx_todos_board ON todos(board_id)")
            # 首次加 sort_order：用 -id 让新数据（id 大）排在前
            if sort_order_just_added:
                c.execute("UPDATE todos SET sort_order = -id")

            # 默认 board：保证至少有一个，把无主 todos 接管过来
            row = c.execute("SELECT id FROM boards ORDER BY id LIMIT 1").fetchone()
            if row is None:
                now = datetime.now().isoformat(timespec="seconds")
                cur = c.execute(
                    "INSERT INTO boards (title, color, created_at) VALUES (?, ?, ?)",
                    ("默认便签", "yellow", now),
                )
                self._default_board_id = cur.lastrowid
            else:
                self._default_board_id = row["id"]
            c.execute(
                "UPDATE todos SET board_id=? WHERE board_id IS NULL",
                (self._default_board_id,),
            )

    def default_board_id(self) -> int:
        if self._default_board_id is None:
            with self._conn() as c:
                row = c.execute("SELECT id FROM boards ORDER BY id LIMIT 1").fetchone()
            self._default_board_id = row["id"] if row else None
        return self._default_board_id

    # ---------- Boards ----------

    @staticmethod
    def _row_to_board(row: sqlite3.Row) -> Board:
        data = {k: row[k] for k in row.keys() if k in Board._fields}
        return Board(**data)

    def list_boards(self) -> list[Board]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM boards ORDER BY id").fetchall()
        return [self._row_to_board(r) for r in rows]

    def get_board(self, board_id: int) -> Optional[Board]:
        with self._conn() as c:
            row = c.execute("SELECT * FROM boards WHERE id=?", (board_id,)).fetchone()
        return self._row_to_board(row) if row else None

    def add_board(self, title: str = "新便签", color: str = "yellow") -> int:
        now = datetime.now().isoformat(timespec="seconds")
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO boards (title, color, created_at) VALUES (?, ?, ?)",
                (title, color, now),
            )
            return cur.lastrowid

    def update_board(self, board_id: int, **fields) -> None:
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        params = list(fields.values()) + [board_id]
        with self._conn() as c:
            c.execute(f"UPDATE boards SET {sets} WHERE id=?", params)

    def delete_board(self, board_id: int) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM todos WHERE board_id=?", (board_id,))
            c.execute("DELETE FROM boards WHERE id=?", (board_id,))

    # ---------- Todos ----------

    def add(
        self,
        content: str,
        tag: Optional[str] = None,
        due_date: Optional[str] = None,
        board_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> int:
        if board_id is None:
            board_id = self.default_board_id()
        now = datetime.now().isoformat(timespec="seconds")
        with self._conn() as c:
            # 新待办默认排在最上方：取当前 board 内最小 sort_order - 1
            row = c.execute(
                "SELECT MIN(sort_order) AS mn FROM todos WHERE board_id=?",
                (board_id,),
            ).fetchone()
            min_so = row["mn"] if row and row["mn"] is not None else 0
            new_so = min_so - 1
            cur = c.execute(
                "INSERT INTO todos "
                "(content, status, created_at, tag, due_date, board_id, sort_order, notes) "
                "VALUES (?, 0, ?, ?, ?, ?, ?, ?)",
                (content.strip(), now, tag, due_date, board_id, new_so, notes),
            )
            return cur.lastrowid

    def update_sort_order(self, todo_id: int, sort_order: int) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE todos SET sort_order=? WHERE id=?",
                (sort_order, todo_id),
            )

    def update_sort_orders(self, mapping: dict[int, int]) -> None:
        """批量写入 sort_order：mapping = {todo_id: order}。"""
        if not mapping:
            return
        with self._conn() as c:
            c.executemany(
                "UPDATE todos SET sort_order=? WHERE id=?",
                [(so, tid) for tid, so in mapping.items()],
            )

    def update(
        self,
        todo_id: int,
        content: str,
        tag: Optional[str],
        due_date: Optional[str],
        notes: Optional[str] = None,
    ) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE todos SET content=?, tag=?, due_date=?, notes=? WHERE id=?",
                (content.strip(), tag, due_date, notes, todo_id),
            )

    def update_notes(self, todo_id: int, notes: Optional[str]) -> None:
        with self._conn() as c:
            c.execute("UPDATE todos SET notes=? WHERE id=?", (notes, todo_id))

    def set_due_date(self, todo_id: int, due_date: Optional[str]) -> None:
        """只改 due_date（日历拖拽排期 / 改期用）。"""
        with self._conn() as c:
            c.execute(
                "UPDATE todos SET due_date=? WHERE id=?", (due_date, todo_id)
            )

    def set_completed_at(self, todo_id: int, completed_at: str) -> None:
        """修改已完成待办的完成时间（历史窗口改日期用）。"""
        with self._conn() as c:
            c.execute(
                "UPDATE todos SET completed_at=? WHERE id=? AND status=1",
                (completed_at, todo_id),
            )

    def mark_timer_start(self, todo_id: int) -> None:
        """记录首次开始计时的时间（已有则不覆盖）。"""
        now = datetime.now().isoformat(timespec="seconds")
        with self._conn() as c:
            c.execute(
                "UPDATE todos SET time_started_at=? "
                "WHERE id=? AND time_started_at IS NULL",
                (now, todo_id),
            )

    def add_time_spent(self, todo_id: int, seconds: int) -> None:
        """把本次专注秒数累加到该待办，并刷新最近计时活动时间。"""
        if seconds <= 0:
            return
        now = datetime.now().isoformat(timespec="seconds")
        with self._conn() as c:
            c.execute(
                "UPDATE todos SET time_spent = time_spent + ?, time_ended_at = ? "
                "WHERE id=?",
                (int(seconds), now, todo_id),
            )

    def complete(self, todo_id: int) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._conn() as c:
            c.execute(
                "UPDATE todos SET status=1, completed_at=? WHERE id=?",
                (now, todo_id),
            )

    def uncomplete(self, todo_id: int) -> None:
        """把已完成待办恢复为待办；放到所属 board 列表最上方。"""
        with self._conn() as c:
            row = c.execute(
                "SELECT board_id FROM todos WHERE id=?", (todo_id,)
            ).fetchone()
            if row is None:
                return
            board_id = row["board_id"]
            mn_row = c.execute(
                "SELECT MIN(sort_order) AS mn FROM todos WHERE board_id=? AND status=0",
                (board_id,),
            ).fetchone()
            mn = mn_row["mn"] if mn_row else None
            new_so = (mn if mn is not None else 0) - 1
            c.execute(
                "UPDATE todos SET status=0, completed_at=NULL, sort_order=? WHERE id=?",
                (new_so, todo_id),
            )

    def delete(self, todo_id: int) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM todos WHERE id=?", (todo_id,))

    def delete_all_completed(self, board_id: Optional[int] = None) -> int:
        with self._conn() as c:
            if board_id is None:
                cur = c.execute("DELETE FROM todos WHERE status=1")
            else:
                cur = c.execute(
                    "DELETE FROM todos WHERE status=1 AND board_id=?", (board_id,)
                )
            return cur.rowcount

    def list_pending(self, board_id: Optional[int] = None) -> list[Todo]:
        sql = "SELECT * FROM todos WHERE status=0"
        params: list = []
        if board_id is not None:
            sql += " AND board_id=?"
            params.append(board_id)
        # 排序：手工 sort_order 优先；同序内 due_date（NULL 最后）；最后 created_at 倒序
        sql += """ ORDER BY
                    sort_order ASC,
                    CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
                    due_date ASC,
                    created_at DESC"""
        with self._conn() as c:
            rows = c.execute(sql, params).fetchall()
        return [Todo(**dict(r)) for r in rows]

    def list_completed(
        self, board_id: Optional[int] = None, limit: int = 200
    ) -> list[Todo]:
        if board_id is None:
            sql = "SELECT * FROM todos WHERE status=1 ORDER BY completed_at DESC LIMIT ?"
            params: tuple = (limit,)
        else:
            sql = (
                "SELECT * FROM todos WHERE status=1 AND board_id=? "
                "ORDER BY completed_at DESC LIMIT ?"
            )
            params = (board_id, limit)
        with self._conn() as c:
            rows = c.execute(sql, params).fetchall()
        return [Todo(**dict(r)) for r in rows]

    def list_tags(self, board_id: Optional[int] = None) -> list[str]:
        sql = (
            "SELECT DISTINCT tag FROM todos "
            "WHERE status=0 AND tag IS NOT NULL AND tag <> ''"
        )
        params: list = []
        if board_id is not None:
            sql += " AND board_id=?"
            params.append(board_id)
        sql += " ORDER BY tag"
        with self._conn() as c:
            rows = c.execute(sql, params).fetchall()
        return [r["tag"] for r in rows]

    def get(self, todo_id: int) -> Optional[Todo]:
        with self._conn() as c:
            row = c.execute("SELECT * FROM todos WHERE id=?", (todo_id,)).fetchone()
        return Todo(**dict(row)) if row else None
