"""创建与真实用户数据完全隔离的演示 SQLite 数据库。

由项目根目录的 start_demo.bat 调用。脚本只在演示数据库不存在时写入，
不会删除或覆盖录屏过程中已经修改过的演示数据。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import Database  # noqa: E402


DEMO_DB = ROOT / "DemoData" / "DesktopTodo" / "todos.db"


def _add_pending(
    db: Database,
    board_id: int,
    content: str,
    tag: str,
    due_date: str | None,
    notes: str | None = None,
) -> int:
    return db.add(
        content=content,
        tag=tag,
        due_date=due_date,
        board_id=board_id,
        notes=notes,
    )


def _add_completed(
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
    todo_id = db.add(
        content=content,
        tag=tag,
        due_date=due_date,
        board_id=board_id,
        notes=notes,
    )
    with sqlite3.connect(DEMO_DB) as conn:
        conn.execute(
            """
            UPDATE todos
               SET status=1,
                   completed_at=?,
                   time_started_at=?,
                   time_ended_at=?,
                   time_spent=?
             WHERE id=?
            """,
            (
                completed_at,
                focus_start,
                focus_end,
                focus_seconds,
                todo_id,
            ),
        )


def create_demo_database() -> None:
    if DEMO_DB.exists():
        return

    DEMO_DB.parent.mkdir(parents=True, exist_ok=True)
    db = Database(DEMO_DB)
    db.init()

    # 默认便签改成第一组演示分类，再新增与历史数据一致的三组便签。
    tool_board = db.default_board_id()
    db.update_board(
        tool_board,
        title="工具开发",
        color="yellow",
        width=350,
        height=520,
    )
    content_board = db.add_board("内容创作", "pink")
    growth_board = db.add_board("个人成长", "green")
    life_board = db.add_board("个人生活", "blue")

    # 工具开发：突出日期、标签、备注与专注入口。
    _add_pending(
        db,
        tool_board,
        "完成安装包兼容性测试",
        "测试",
        "2026-08-26",
        "分别测试首次启动、关闭后恢复和系统托盘。",
    )
    _add_pending(
        db,
        tool_board,
        "优化首次启动说明",
        "工具开发",
        "2026-08-27",
        "把安装步骤压缩到三步以内。",
    )
    _add_pending(
        db,
        tool_board,
        "整理第一批用户反馈",
        "复盘",
        "2026-08-29",
        "只记录重复出现的问题，不急着增加新功能。",
    )
    _add_pending(
        db,
        tool_board,
        "检查窗口在不同分辨率下的位置",
        "测试",
        None,
    )

    # 内容创作：直接对应本次小红书录屏任务。
    _add_pending(
        db,
        content_board,
        "录制快速新增待办镜头",
        "内容创作",
        "2026-08-26",
        "画面只保留桌面和悬浮便签。",
    )
    _add_pending(
        db,
        content_board,
        "录制统一复盘功能",
        "内容创作",
        "2026-08-26",
        "点击已完成事项，补充一句真实复盘。",
    )
    _add_pending(
        db,
        content_board,
        "调整视频字幕节奏",
        "内容创作",
        "2026-08-27",
        "每屏只保留一个重点，避免字幕盖住操作。",
    )
    _add_pending(
        db,
        content_board,
        "发布前检查全部演示画面",
        "测试",
        "2026-08-27",
        "重点检查通知、浏览器标签和文件路径。",
    )

    # 个人成长：展示同一工具中不同类型事项的统一管理。
    _add_pending(
        db,
        growth_board,
        "阅读一篇产品设计文章",
        "学习",
        "2026-08-26",
        "读完只记三条真正影响设计判断的内容。",
    )
    _add_pending(
        db,
        growth_board,
        "完成本周个人复盘",
        "复盘",
        "2026-08-28",
        "回看已完成记录，找出最有效的专注时段。",
    )
    _add_pending(
        db,
        growth_board,
        "整理两周读书笔记",
        "学习",
        None,
    )

    # 个人生活：让演示数据不像单纯的项目管理后台。
    _add_pending(
        db,
        life_board,
        "预约年度体检",
        "生活",
        "2026-08-27",
    )
    _add_pending(
        db,
        life_board,
        "备份手机照片",
        "生活",
        "2026-08-30",
    )
    _add_pending(
        db,
        life_board,
        "整理桌面和充电线",
        "生活",
        None,
    )

    # 少量尚未归档的已完成事项：历史页有内容，分析页也能展示“未归档”徽标。
    _add_completed(
        db,
        tool_board,
        "完成演示数据隔离测试",
        "测试",
        "2026-08-26",
        "2026-08-26 09:18:00",
        "真实数据库、演示数据库和演示归档已经完全分开。",
        "2026-08-26 08:42:00",
        "2026-08-26 09:18:00",
        36 * 60,
    )
    _add_completed(
        db,
        content_board,
        "确定第一条视频的核心结构",
        "内容创作",
        "2026-08-25",
        "2026-08-25 20:42:00",
        "不做完整功能说明，只讲随手记、做完消和以后统一复盘。",
        "2026-08-25 19:48:00",
        "2026-08-25 20:42:00",
        54 * 60,
    )
    _add_completed(
        db,
        growth_board,
        "整理本周学习重点",
        "学习",
        "2026-08-24",
        "2026-08-24 21:16:00",
        "学习内容不再按来源分类，只保留真正改变做法的部分。",
        "2026-08-24 20:28:00",
        "2026-08-24 21:16:00",
        48 * 60,
    )
    _add_completed(
        db,
        life_board,
        "清理电脑桌面文件",
        "生活",
        "2026-08-25",
        "2026-08-25 18:06:00",
        "桌面只保留正在处理的内容，录屏时也不会误露私人文件。",
        "2026-08-25 17:38:00",
        "2026-08-25 18:06:00",
        28 * 60,
    )


if __name__ == "__main__":
    create_demo_database()
