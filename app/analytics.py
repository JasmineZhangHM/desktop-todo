"""DoneList 分析数据层：解析归档 markdown -> 视图 JSON。

渲染在网页端（app/webcal/analytics.js，经 /api/analytics 取数）。
db 里已完成未归档的记录由 web_calendar 转成 Record 合并进来，
其 source_file 固定为 DB_SOURCE。
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ---------- 数据模型 ----------

DB_SOURCE = "__db__"  # source_file 取此值 = 来自数据库（已完成未归档）


@dataclass
class Record:
    content: str
    tag: Optional[str]
    due_date: Optional[str]
    completed_at: Optional[str]
    notes: Optional[str]
    batch_archived_at: Optional[str]
    source_file: str
    board: Optional[str] = None
    focus_start: Optional[str] = None
    focus_end: Optional[str] = None
    focus_seconds: int = 0


# ---------- 解析 ----------

_BATCH_HEADER = re.compile(r"^##\s+存档于\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})")
_ITEM_LINE = re.compile(r"^-\s+\[x\]\s+(.*)$")
_TAG_RE = re.compile(r"\s*`#([^`]+)`")
_DUE_RE = re.compile(r"\s*📅\s*(\d{4}-\d{2}-\d{2})")
_DONE_RE = re.compile(r"^\s*-\s+完成于：(.+?)\s*$")
_NOTE_RE = re.compile(r"^\s*>\s?(.*)$")
_BOARD_RE = re.compile(r"^\s*-\s+所属便签：\s*📌?\s*(.+?)\s*$")
_FOCUS_RE = re.compile(r"^\s*-\s+专注：\s*(.+?)\s*~\s*(.+?)\s*·\s*时长\s*(.+?)\s*$")

_DUR_H = re.compile(r"(\d+)\s*小时")
_DUR_M = re.compile(r"(\d+)\s*分钟")
_DUR_S = re.compile(r"(\d+)\s*秒")

_TAG_ALIASES: dict[str, str] = {}


def _parse_duration_zh(text: str) -> int:
    """把「1小时5分钟 / 30分钟 / 45秒」解析为秒。"""
    total = 0
    h = _DUR_H.search(text)
    m = _DUR_M.search(text)
    s = _DUR_S.search(text)
    if h:
        total += int(h.group(1)) * 3600
    if m:
        total += int(m.group(1)) * 60
    if s:
        total += int(s.group(1))
    return total


def _canonical_tag(tag: Optional[str]) -> Optional[str]:
    if not tag:
        return None
    return _TAG_ALIASES.get(tag, tag)


def _split_item_line(raw: str) -> tuple[str, Optional[str], Optional[str]]:
    tag_match = _TAG_RE.search(raw)
    due_match = _DUE_RE.search(raw)
    tag = tag_match.group(1).strip() if tag_match else None
    due = due_match.group(1) if due_match else None
    content = raw
    if tag_match:
        content = content.replace(tag_match.group(0), "")
    if due_match:
        content = content.replace(due_match.group(0), "")
    return content.strip(), tag, due


def parse_archive_dir(archive_dir: Path) -> list[Record]:
    if not archive_dir.exists():
        return []
    out: list[Record] = []
    for md_file in sorted(archive_dir.glob("completed_*.md")):
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            continue
        out.extend(_parse_one(md_file, text))
    return out


def _parse_one(path: Path, text: str) -> list[Record]:
    lines = text.splitlines()
    records: list[Record] = []
    cur_batch: Optional[str] = None
    i = 0
    while i < len(lines):
        line = lines[i]
        bm = _BATCH_HEADER.match(line)
        if bm:
            cur_batch = bm.group(1)
            i += 1
            continue
        im = _ITEM_LINE.match(line)
        if not im:
            i += 1
            continue
        content, tag, due = _split_item_line(im.group(1))
        completed_at: Optional[str] = None
        notes_lines: list[str] = []
        board: Optional[str] = None
        focus_start: Optional[str] = None
        focus_end: Optional[str] = None
        focus_seconds = 0
        i += 1
        while i < len(lines):
            sub = lines[i]
            if not sub.strip():
                i += 1
                continue
            if _BATCH_HEADER.match(sub) or _ITEM_LINE.match(sub):
                break
            dm = _DONE_RE.match(sub)
            if dm:
                completed_at = dm.group(1).replace("T", " ")
                i += 1
                continue
            bdm = _BOARD_RE.match(sub)
            if bdm:
                board = bdm.group(1).strip()
                i += 1
                continue
            fm = _FOCUS_RE.match(sub)
            if fm:
                s_raw = fm.group(1).strip()
                e_raw = fm.group(2).strip()
                focus_start = None if s_raw == "—" else s_raw
                focus_end = None if e_raw == "—" else e_raw
                focus_seconds = _parse_duration_zh(fm.group(3))
                i += 1
                continue
            if sub.strip().startswith("- 备注："):
                i += 1
                while i < len(lines):
                    nm = _NOTE_RE.match(lines[i])
                    if nm:
                        notes_lines.append(nm.group(1))
                        i += 1
                    else:
                        break
                continue
            i += 1
        records.append(Record(
            content=content,
            tag=tag,
            due_date=due,
            completed_at=completed_at,
            notes="\n".join(notes_lines).strip() or None,
            batch_archived_at=cur_batch,
            source_file=path.name,
            board=board,
            focus_start=focus_start,
            focus_end=focus_end,
            focus_seconds=focus_seconds,
        ))
    return records


# ---------- 视图数据 ----------

_NO_TAG = "无标签"
_NO_BOARD = "未分类"


def build_view_data(records: list[Record]) -> dict:
    active = [r for r in records if r.completed_at]
    if not active:
        return {
            "total": 0, "records": [], "tags": [], "boards": [],
            "total_focus_seconds": 0, "date_range": None,
        }

    tag_counter: Counter = Counter()
    board_counter: Counter = Counter()
    total_focus = 0
    out_records: list[dict] = []
    for r in active:
        canon = _canonical_tag(r.tag) or _NO_TAG
        tag_counter[canon] += 1
        board = r.board or _NO_BOARD
        board_counter[board] += 1
        focus = r.focus_seconds or 0
        total_focus += focus
        out_records.append({
            "content": r.content,
            "tag": canon,
            "board": board,
            "completed_at": r.completed_at,
            "due_date": r.due_date,
            "notes": r.notes,
            "focus_start": r.focus_start,
            "focus_end": r.focus_end,
            "focus_seconds": focus,
            "source": "db" if r.source_file == DB_SOURCE else "archive",
        })

    out_records.sort(key=lambda x: x["completed_at"])
    dates = [r["completed_at"][:10] for r in out_records]

    return {
        "total": len(out_records),
        "records": out_records,
        "tags": [{"name": k, "count": v} for k, v in tag_counter.most_common()],
        "boards": [{"name": k, "count": v} for k, v in board_counter.most_common()],
        "total_focus_seconds": total_focus,
        "date_range": {"from": dates[0], "to": dates[-1]},
    }
