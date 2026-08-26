"""创建资本市场项目岗职业场景的演示 SQLite 数据库。

数据库位于项目内 DemoData，和真实 APPDATA 完全隔离。脚本通过版本号判断
是否需要刷新；只重建演示库中的 boards/todos，不删除任何文件。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import Database  # noqa: E402


DEMO_DB = ROOT / "DemoData" / "DesktopTodo" / "todos.db"
DEMO_VERSION = 2


def _current_version() -> int:
    if not DEMO_DB.exists():
        return 0
    try:
        with sqlite3.connect(DEMO_DB) as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='demo_meta'"
            ).fetchone()
            if not row:
                return 0
            value = conn.execute(
                "SELECT value FROM demo_meta WHERE key='version'"
            ).fetchone()
            return int(value[0]) if value else 0
    except (sqlite3.Error, ValueError):
        return 0


def _prepare_empty_demo_db() -> Database:
    DEMO_DB.parent.mkdir(parents=True, exist_ok=True)
    db = Database(DEMO_DB)
    db.init()
    with sqlite3.connect(DEMO_DB) as conn:
        conn.execute("DELETE FROM todos")
        conn.execute("DELETE FROM boards")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS demo_meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        conn.execute("DELETE FROM demo_meta")
    # init() 重新创建默认便签；使用新对象避免沿用旧 default_board_id 缓存。
    db = Database(DEMO_DB)
    db.init()
    return db


def _pending(
    db: Database,
    board_id: int,
    content: str,
    tag: str,
    due_date: Optional[str],
    notes: Optional[str] = None,
) -> None:
    db.add(content, tag, due_date, board_id=board_id, notes=notes)


def _completed(
    db: Database,
    board_id: int,
    content: str,
    tag: str,
    due_date: str,
    completed_at: str,
    notes: str,
    focus_start: str,
    focus_end: str,
    focus_seconds: int,
) -> None:
    todo_id = db.add(content, tag, due_date, board_id=board_id, notes=notes)
    with sqlite3.connect(DEMO_DB) as conn:
        conn.execute(
            """
            UPDATE todos
               SET status=1, completed_at=?, time_started_at=?,
                   time_ended_at=?, time_spent=?
             WHERE id=?
            """,
            (completed_at, focus_start, focus_end, focus_seconds, todo_id),
        )


def create_demo_database() -> None:
    if _current_version() == DEMO_VERSION:
        return

    db = _prepare_empty_demo_db()

    ipo_board = db.default_board_id()
    db.update_board(
        ipo_board,
        title="项目A｜科技企业IPO",
        color="yellow",
        width=370,
        height=540,
    )
    refinancing_board = db.add_board("项目B｜制造企业定增", "blue")
    research_board = db.add_board("行业研究", "green")
    daily_board = db.add_board("日常事项", "pink")

    # 项目A：申报材料、数据核对和跨中介协调并行。
    _pending(
        db, ipo_board, "核对招股书业务章节反馈", "申报材料", "2026-08-26",
        "逐条确认发行人、律师和会计师意见是否已经合并。",
    )
    _pending(
        db, ipo_board, "更新监管问询回复分工表", "申报材料", "2026-08-26",
        "标出今天需要反馈的事项和对应责任人。",
    )
    _pending(
        db, ipo_board, "催收董监高关联方调查表", "尽调核查", "2026-08-27",
        "还缺两份签字版，收到后同步更新底稿索引。",
    )
    _pending(
        db, ipo_board, "复核研发费用抽凭差异说明", "数据核对", None,
        "重点看人员名单、项目归集和财务数据口径是否一致。",
    )

    # 项目B：发行阶段短任务密集，最适合展示桌面悬浮和日期分栏。
    _pending(
        db, refinancing_board, "更新定增发行关键时间表", "发行执行", "2026-08-26",
        "同步董事会材料、监管报送和投资者沟通节点。",
    )
    _pending(
        db, refinancing_board, "跟律师确认认购邀请书版本", "协调沟通", "2026-08-26",
        "核对正文和全部附件是否为同一版。",
    )
    _pending(
        db, refinancing_board, "检查投资者适当性材料缺口", "发行执行", "2026-08-27",
        "把缺失文件按投资者列成清单，逐项关闭。",
    )
    _pending(
        db, refinancing_board, "准备定价配售会材料", "发行执行", "2026-08-28",
        "报价汇总、配售测算和合规意见分别复核。",
    )

    # 行业研究：展示长期事项与项目任务共存，但不需要切到另一个软件。
    _pending(
        db, research_board, "更新半导体可比公司估值表", "行业研究", "2026-08-26",
        "补充最新收盘价、盈利预测和估值倍数。",
    )
    _pending(
        db, research_board, "完成本周行业动态摘要", "行业研究", "2026-08-28",
        "只保留会影响项目判断的政策和公司公告。",
    )
    _pending(
        db, research_board, "整理再融资最新案例数据", "行业研究", None,
    )

    # 日常行政：让数据更接近真实职场，而不是只有“大项目”。
    _pending(db, daily_board, "提交本周工时", "行政", "2026-08-26")
    _pending(db, daily_board, "整理差旅报销票据", "行政", "2026-08-29")
    _pending(
        db, daily_board, "完成本周项目复盘", "复盘", "2026-08-28",
        "回看已完成记录，找出重复返工最多的环节。",
    )

    # 尚未归档的完成记录，用于演示统一历史、补充复盘和“未归档”徽标。
    _completed(
        db, ipo_board, "整理中介协调会纪要", "协调沟通", "2026-08-26",
        "2026-08-26 10:18:00",
        "会后事项已经拆到具体责任人和日期，不再只留在会议纪要里。",
        "2026-08-26 09:12:00", "2026-08-26 10:18:00", 66 * 60,
    )
    _completed(
        db, refinancing_board, "复核董事会预案关键数据", "数据核对", "2026-08-25",
        "2026-08-25 19:36:00",
        "募集金额与募投项目金额口径已经统一，修改处同步到了引用章节。",
        "2026-08-25 17:28:00", "2026-08-25 19:36:00", 128 * 60,
    )
    _completed(
        db, research_board, "更新行业周报框架", "行业研究", "2026-08-25",
        "2026-08-25 11:08:00",
        "减少了新闻堆砌，改成数据变化、原因和对项目影响三个部分。",
        "2026-08-25 09:42:00", "2026-08-25 11:08:00", 86 * 60,
    )
    _completed(
        db, daily_board, "提交部门周报和工时", "行政", "2026-08-25",
        "2026-08-25 18:12:00",
        "直接根据本周完成记录汇总，比临时回忆少漏了两个事项。",
        "2026-08-25 17:32:00", "2026-08-25 18:12:00", 40 * 60,
    )

    with sqlite3.connect(DEMO_DB) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO demo_meta (key, value) VALUES ('version', ?)",
            (str(DEMO_VERSION),),
        )


if __name__ == "__main__":
    create_demo_database()
