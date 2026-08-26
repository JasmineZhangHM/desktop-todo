"""解析待办输入：识别 #标签 与 日期 token。

支持形式：
  #标签        → 标签为"标签"
  4-15         → 当年 4 月 15 日 (2026-04-15)
  4/15         → 同上
  2027-1-3     → 2027-01-03
  26-1-3       → 2026-01-03 (两位数年份自动加 2000)

任意顺序、任意位置；多余空格自动剔除。
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional, Tuple


_DATE_TOKEN_RE = re.compile(r"^(\d{1,4})[-/](\d{1,2})(?:[-/](\d{1,2}))?$")


def _try_parse_date_token(tok: str) -> Optional[str]:
    m = _DATE_TOKEN_RE.match(tok)
    if not m:
        return None
    a, b, c = m.group(1), m.group(2), m.group(3)
    try:
        if c is None:
            year = datetime.now().year
            month, day = int(a), int(b)
        else:
            year = int(a)
            if year < 100:
                year += 2000
            month, day = int(b), int(c)
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def parse_input(
    text: str,
) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
    """返回 (clean_content, tag, due_date_iso, notes)。

    用 `|` 分隔正文与备注：`#工作 4-20 写报告 | 包括上周与下周计划`
    `|` 后的所有内容（含空白）都进入 notes。
    """
    text = (text or "").strip()
    if not text:
        return "", None, None, None

    # 先拆 | 取备注
    notes: Optional[str] = None
    if "|" in text:
        head, _, rest = text.partition("|")
        text = head.strip()
        notes = rest.strip() or None

    tag: Optional[str] = None
    due_date: Optional[str] = None
    remaining: list[str] = []

    for tok in text.split():
        if tag is None and tok.startswith("#") and len(tok) > 1:
            tag = tok[1:]
            continue
        if due_date is None:
            d = _try_parse_date_token(tok)
            if d:
                due_date = d
                continue
        remaining.append(tok)

    return " ".join(remaining).strip(), tag, due_date, notes


def format_for_edit(
    content: str,
    tag: Optional[str],
    due_date: Optional[str],
    notes: Optional[str] = None,
) -> str:
    """把已解析字段重组为可编辑字符串（用于编辑弹窗回填）。"""
    parts: list[str] = []
    if tag:
        parts.append(f"#{tag}")
    if due_date:
        try:
            d = date.fromisoformat(due_date)
            parts.append(f"{d.month}-{d.day}")
        except ValueError:
            pass
    if content:
        parts.append(content)
    text = " ".join(parts)
    if notes:
        text = (text + " | " + notes).strip()
    return text


def format_due_label(due_date: str) -> str:
    """把 ISO 日期转成显示用短串：今天 / 明天 / M-D。"""
    try:
        d = date.fromisoformat(due_date)
    except ValueError:
        return due_date
    today = date.today()
    delta = (d - today).days
    if delta == 0:
        return "今天"
    if delta == 1:
        return "明天"
    if delta == -1:
        return "昨天"
    if delta < 0:
        return f"逾期 {-delta}天"
    return f"{d.month}-{d.day}"


def due_status(due_date: str) -> str:
    """返回 due_date 的状态分类：'overdue' | 'today' | 'tomorrow' | 'soon' | 'later'。"""
    try:
        d = date.fromisoformat(due_date)
    except ValueError:
        return "later"
    today = date.today()
    delta = (d - today).days
    if delta < 0:
        return "overdue"
    if delta == 0:
        return "today"
    if delta == 1:
        return "tomorrow"
    if delta <= 3:
        return "soon"
    return "later"
