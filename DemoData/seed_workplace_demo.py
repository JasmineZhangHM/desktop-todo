"""生成不带金融行业特征的通用演示数据。

便签按生活领域分为「工作 / 学习 / 生活」；标签在便签内继续区分
具体项目或事项类型。例如工作便签用「客户A项目 / 客户B项目 / 日常工作」
三个标签区分项目。所有数据只写入项目内 DemoData，与真实 APPDATA
完全隔离。
"""
from __future__ import annotations

import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import Database  # noqa: E402


DEMO_DB = ROOT / "DemoData" / "DesktopTodo" / "todos.db"
ARCHIVE_DIR = ROOT / "DemoData" / "WorkplaceDoneList"
DEMO_VERSION = 4


# 日期、完成时间、事项、标签（项目/类型）、便签（领域）、专注分钟、复盘备注。
HISTORY = [
    ("2026-06-03", "11:20", "整理客户A首次访谈记录", "客户A项目", "工作", 95, "访谈结束当天就标出事实、判断和待确认项，后面写方案时少翻了很多聊天记录。"),
    ("2026-06-05", "18:10", "汇总20家门店周销售数据", "客户A项目", "工作", 130, None),
    ("2026-06-08", "16:45", "更新客户A项目进度表", "客户A项目", "工作", 48, None),
    ("2026-06-10", "10:30", "整理零售行业案例资料", "行业研究", "学习", 72, None),
    ("2026-06-12", "17:40", "提交本周工时", "日常工作", "工作", 0, None),
    ("2026-06-15", "20:15", "核对门店客流与转化率口径", "客户A项目", "工作", 146, "发现两张表使用了不同的门店范围，先锁定统计口径比继续改公式更重要。"),
    ("2026-06-18", "15:50", "搭建客户B流程访谈提纲", "客户B项目", "工作", 88, None),
    ("2026-06-21", "19:30", "整理客户B现有流程图", "客户B项目", "工作", 118, None),
    ("2026-06-23", "11:45", "完成效率工具案例研究", "行业研究", "学习", 76, None),
    ("2026-06-26", "18:25", "输出客户A周会纪要", "客户A项目", "工作", 54, "会议纪要只写结论没有用，这次把每个会后动作都补上了责任人和日期。"),
    ("2026-06-28", "15:10", "提交六月差旅报销", "日常工作", "工作", 32, None),
    ("2026-06-30", "21:50", "完成六月工作复盘", "日常工作", "工作", 52, "本月返工最多的原因是数据口径和交付版本没有提前确认。"),

    ("2026-07-02", "18:40", "确认客户A下周访谈名单", "客户A项目", "工作", 45, None),
    ("2026-07-04", "11:10", "整理门店经理访谈共性问题", "客户A项目", "工作", 82, None),
    ("2026-07-07", "22:30", "修改客户A阶段汇报材料", "客户A项目", "工作", 188, "先改故事线再调每一页，比一开始就纠结字体和图表快很多。"),
    ("2026-07-10", "17:55", "更新客户反馈关闭清单", "客户A项目", "工作", 64, None),
    ("2026-07-12", "20:15", "整理项目文件命名与版本", "客户A项目", "工作", 97, None),
    ("2026-07-15", "18:20", "完成客户B部门访谈纪要", "客户B项目", "工作", 105, None),
    ("2026-07-18", "21:05", "汇总客户B流程耗时数据", "客户B项目", "工作", 152, "同一个审批动作在不同部门叫法不一样，合并数据前先建立了统一字段。"),
    ("2026-07-21", "17:40", "更新客户B问题优先级矩阵", "客户B项目", "工作", 86, None),
    ("2026-07-23", "11:25", "跟客户确认阶段汇报时间", "客户B项目", "工作", 24, None),
    ("2026-07-25", "09:15", "完成企业效率案例周报", "行业研究", "学习", 91, None),
    ("2026-07-28", "19:50", "更新项目方法论素材库", "行业研究", "学习", 74, None),
    ("2026-07-30", "18:05", "提交部门周报和工时", "日常工作", "工作", 38, None),
    ("2026-07-31", "21:45", "完成七月工作复盘", "日常工作", "工作", 55, "两个项目并行时，最容易遗漏的不是大任务，而是会后临时答应的小事项。"),

    ("2026-08-01", "10:25", "更新客户A门店数据看板", "客户A项目", "工作", 96, None),
    ("2026-08-01", "18:10", "整理阶段汇报待确认问题", "客户A项目", "工作", 68, None),
    ("2026-08-04", "20:50", "核对门店名单与区域分类", "客户A项目", "工作", 132, "区域名称看起来只是格式问题，但会直接影响后面的分组统计。"),
    ("2026-08-06", "17:30", "完成客户A汇报材料初稿", "客户A项目", "工作", 164, None),
    ("2026-08-06", "21:40", "汇总客户A反馈意见", "客户A项目", "工作", 72, None),
    ("2026-08-09", "11:35", "更新客户B流程优化事项表", "客户B项目", "工作", 84, None),
    ("2026-08-11", "18:15", "核对客户B问卷回收数据", "客户B项目", "工作", 137, "剔除重复提交前先保留原始表，所有清洗规则都单独记录。"),
    ("2026-08-13", "15:25", "跟客户确认试运行部门", "客户B项目", "工作", 42, None),
    ("2026-08-14", "19:10", "准备客户B阶段汇报材料", "客户B项目", "工作", 128, None),
    ("2026-08-14", "21:00", "更新本月行业案例数据", "行业研究", "学习", 57, None),
    ("2026-08-17", "09:05", "完成企业服务行业周报", "行业研究", "学习", 88, None),
    ("2026-08-18", "18:25", "整理三个流程优化案例", "行业研究", "学习", 94, None),
    ("2026-08-18", "20:00", "提交八月差旅报销", "日常工作", "工作", 30, None),
    ("2026-08-20", "10:15", "汇总客户A材料缺口", "客户A项目", "工作", 66, None),
    ("2026-08-20", "17:40", "复核汇报PPT中的数据和图表", "客户A项目", "工作", 118, None),
    ("2026-08-21", "11:05", "整理客户B试运行问题清单", "客户B项目", "工作", 78, None),
    ("2026-08-21", "19:05", "完成客户B流程手册修改", "客户B项目", "工作", 156, "把例外情况单独列出来以后，一线同事反馈流程更容易照着执行。"),
    ("2026-08-22", "10:35", "准备客户B项目汇报会", "客户B项目", "工作", 108, None),
    ("2026-08-22", "15:00", "汇总各部门试运行反馈", "客户B项目", "工作", 92, None),
    ("2026-08-22", "18:30", "更新下一阶段行动清单", "客户B项目", "工作", 74, None),
    ("2026-08-23", "20:10", "整理下周研究选题", "行业研究", "学习", 61, None),
    ("2026-08-24", "10:00", "输出客户A周会纪要", "客户A项目", "工作", 48, None),
    ("2026-08-24", "22:00", "完成客户A最终汇报材料", "客户A项目", "工作", 176, "先锁定数据版本再统一改图，避免不同同事导出的数字互相覆盖。"),
    ("2026-08-25", "14:20", "更新客户B项目总结报告", "客户B项目", "工作", 142, None),
    ("2026-08-25", "18:05", "提交本周工时和部门周报", "日常工作", "工作", 40, None),
    ("2026-08-26", "20:35", "完成本周工作复盘", "日常工作", "工作", 62, "本周完成最多的是客户交付，但最需要改进的是会后事项和文件版本的跟踪。"),

    ("2026-06-07", "10:20", "完成周末晨跑", "健康", "生活", 42, None),
    ("2026-06-20", "17:30", "整理家中换季衣物", "家庭", "生活", 65, None),
    ("2026-07-11", "11:40", "完成年度体检预约", "健康", "生活", 18, None),
    ("2026-07-26", "18:05", "备份手机照片", "整理", "生活", 46, "按年份整理后再备份，以后查找更方便。"),
    ("2026-08-08", "09:50", "给家里的植物换土", "家庭", "生活", 38, None),
    ("2026-08-23", "16:15", "整理桌面和充电线", "整理", "生活", 32, "常用的线材固定放置，不再每次重新找。"),
]


def _write_archives() -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    grouped = defaultdict(list)
    for record in HISTORY:
        grouped[record[0][:7]].append(record)
    for month, records in grouped.items():
        records.sort(key=lambda record: (record[0], record[1]))
        lines = [
            f"# 已完成待办存档 · {month} · 通用演示",
            "",
            "> 客户、项目与个人记录均为虚构内容，不代表任何真实公司或个人。",
            "",
            "---",
            "",
            f"## 存档于 {month}-{records[-1][0][-2:]} 22:30:00 · {len(records)} 项 · 全部便签",
            "",
        ]
        for day, end_hm, content, tag, board, focus_min, note in records:
            lines.append(f"- [x] {content} `#{tag}` 📅 {day}")
            lines.append(f"  - 完成于：{day} {end_hm}:00")
            lines.append(f"  - 所属便签：📌 {board}")
            if focus_min:
                end = datetime.strptime(f"{day} {end_hm}", "%Y-%m-%d %H:%M")
                start = end - timedelta(minutes=focus_min)
                duration = (
                    f"{focus_min // 60}小时{focus_min % 60}分钟"
                    if focus_min >= 60 and focus_min % 60
                    else f"{focus_min // 60}小时"
                    if focus_min >= 60
                    else f"{focus_min}分钟"
                )
                lines.append(
                    f"  - 专注：{start:%Y-%m-%d %H:%M}:00 ~ {end:%Y-%m-%d %H:%M}:00 · 时长 {duration}"
                )
            if note:
                lines.extend(["  - 备注：", f"    > {note}"])
            lines.append("")
        (ARCHIVE_DIR / f"completed_{month}.md").write_text(
            "\n".join(lines), encoding="utf-8"
        )


def _version() -> int:
    if not DEMO_DB.exists():
        return 0
    try:
        with sqlite3.connect(DEMO_DB) as conn:
            row = conn.execute(
                "SELECT value FROM demo_meta WHERE key='version'"
            ).fetchone()
            return int(row[0]) if row else 0
    except (sqlite3.Error, ValueError):
        return 0


def _reset_demo_db() -> Database:
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
    db = Database(DEMO_DB)
    db.init()
    return db


def _pending(db, board, content, tag, due, note=None):
    db.add(content, tag, due, board_id=board, notes=note)


def _completed(db, board, content, tag, completed_at, note, minutes):
    day = completed_at[:10]
    todo_id = db.add(content, tag, day, board_id=board, notes=note)
    end = datetime.strptime(completed_at, "%Y-%m-%d %H:%M:%S")
    start = end - timedelta(minutes=minutes)
    with sqlite3.connect(DEMO_DB) as conn:
        conn.execute(
            "UPDATE todos SET status=1, completed_at=?, time_started_at=?, "
            "time_ended_at=?, time_spent=? WHERE id=?",
            (completed_at, start.isoformat(sep=" "), end.isoformat(sep=" "), minutes * 60, todo_id),
        )


def create_demo() -> None:
    _write_archives()
    if _version() == DEMO_VERSION:
        return
    db = _reset_demo_db()
    work = db.default_board_id()
    db.update_board(work, title="工作", color="yellow", width=370, height=540)
    study = db.add_board("学习", "green")
    life = db.add_board("生活", "blue")

    # 工作便签：用标签区分项目，而不是为每个项目再建一张便签。
    _pending(db, work, "核对本周门店销售数据", "客户A项目", "2026-08-26", "确认门店范围和销售额口径一致。")
    _pending(db, work, "更新客户反馈关闭清单", "客户A项目", "2026-08-26")
    _pending(db, work, "确认下周门店访谈名单", "客户A项目", "2026-08-27")
    _pending(db, work, "复核阶段汇报PPT数据", "客户A项目", None)
    _pending(db, work, "整理试运行问题清单", "客户B项目", "2026-08-26")
    _pending(db, work, "跟客户确认汇报会时间", "客户B项目", "2026-08-26")
    _pending(db, work, "汇总各部门流程反馈", "客户B项目", "2026-08-27")
    _pending(db, work, "修改流程操作手册", "客户B项目", "2026-08-28")
    _pending(db, work, "提交本周工时", "日常工作", "2026-08-26")
    _pending(db, work, "整理差旅报销票据", "日常工作", "2026-08-29")
    _pending(db, work, "完成本周工作复盘", "日常工作", "2026-08-28")

    # 学习与生活分别使用独立便签，便于在桌面上整体显示/隐藏。
    _pending(db, study, "更新企业服务案例库", "行业研究", "2026-08-26")
    _pending(db, study, "完成本周行业动态摘要", "行业研究", "2026-08-28")
    _pending(db, study, "整理下月阅读选题", "阅读", None)
    _pending(db, life, "预约年度体检", "健康", "2026-08-27")
    _pending(db, life, "备份手机照片", "整理", "2026-08-30")
    _pending(db, life, "整理桌面和充电线", "整理", None)

    _completed(db, work, "输出客户A周会纪要", "客户A项目", "2026-08-26 10:18:00", "会后动作已经拆到责任人和日期。", 54)
    _completed(db, work, "完成客户B流程数据核对", "客户B项目", "2026-08-25 19:36:00", "统一字段后再合并数据，减少了返工。", 112)
    _completed(db, study, "更新行业周报框架", "行业研究", "2026-08-25 11:08:00", "减少新闻堆砌，只保留变化、原因和影响。", 76)
    _completed(db, work, "提交部门周报和工时", "日常工作", "2026-08-25 18:12:00", "直接根据完成记录汇总，少漏了两个事项。", 36)
    _completed(db, life, "清理电脑桌面文件", "整理", "2026-08-24 18:06:00", "桌面只保留正在处理的内容。", 28)

    with sqlite3.connect(DEMO_DB) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO demo_meta (key, value) VALUES ('version', ?)",
            (str(DEMO_VERSION),),
        )


if __name__ == "__main__":
    create_demo()
