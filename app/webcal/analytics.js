"use strict";

// 分析视图：渲染逻辑迁移自原 analytics.py 的 _HTML_TEMPLATE。
// IIFE 封装，只暴露 window.Analytics = { load }，避免与 app.js 全局符号冲突。
(function () {
  const TAG_COLORS = [
    "#4C7EF3", "#3F9D6B", "#E0883C", "#C2557A", "#7B69C4",
    "#3FA7A0", "#B5894E", "#5B8B6B", "#9E6B85", "#5B7C8A", "#A65A5A", "#6F8A6B",
  ];
  const WEEK_CN = "日一二三四五六";

  let DATA = null;
  let tagColor = {};
  let activeTag = "__ALL__";
  let activeBoard = "__ALL__";
  // 时间区间筛选：预设 key + 生效的起止日（'YYYY-MM-DD'，null = 不限）
  let rangePreset = "__ALL__";
  let rangeFrom = null;
  let rangeTo = null;
  const tip = document.getElementById("an-tip");

  // 预设区间。基准「今天」用本机时间：页面由本机 127.0.0.1 服务，与服务端同机同时区。
  // 不用 DATA.date_range.to —— 这一周真没完成事，「近7天」就该显示 0，不该被粉饰。
  const RANGE_PRESETS = [
    { key: "__ALL__", label: "全部" },
    { key: "7d", label: "近 7 天" },
    { key: "30d", label: "近 30 天" },
    { key: "month", label: "本月" },
    { key: "year", label: "今年" },
  ];

  function presetBounds(key) {
    if (key === "__ALL__") return [null, null];
    const now = new Date();
    const to = formatDate(now);
    if (key === "7d") return [formatDate(addDays(now, -6)), to];
    if (key === "30d") return [formatDate(addDays(now, -29)), to];
    if (key === "month") return [formatDate(new Date(now.getFullYear(), now.getMonth(), 1)), to];
    if (key === "year") return [formatDate(new Date(now.getFullYear(), 0, 1)), to];
    return [null, null];
  }

  async function load() {
    const resp = await fetch("/api/analytics");
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error || `HTTP ${resp.status}`);
    }
    DATA = await resp.json();
    tagColor = {};
    DATA.tags.forEach((t, i) => { tagColor[t.name] = TAG_COLORS[i % TAG_COLORS.length]; });
    render();
  }

  function render() {
    const empty = DATA.total === 0;
    document.getElementById("an-empty").hidden = !empty;
    document.getElementById("an-content").hidden = empty;
    if (empty) {
      document.getElementById("an-range").textContent = "";
      return;
    }
    const [ef, et] = effectiveRange();
    const rangeEl = document.getElementById("an-range");
    if (!rangeFrom && !rangeTo) {
      rangeEl.textContent = `${ef} ～ ${et}`;
    } else {
      rangeEl.textContent = `${ef} ～ ${et} · 命中 ${getFiltered().length} 项`;
    }
    renderFilters();
    renderStats();
    renderHeatmap();
    renderDaily();
  }

  /* ── filters ── */
  function chipHtml(label, count, active, color, key, attr) {
    const style = active && color ? `background:${color};border-color:${color}` : "";
    return `<div class="an-chip ${active ? "active" : ""}" data-${attr}="${escapeAttr(key)}" style="${style}">
      ${escapeHtml(label)} <span class="c">${count}</span></div>`;
  }
  // 按给定维度统计分组计数，返回 [{name, count}] 按 count 降序
  function countBy(records, key) {
    const m = new Map();
    records.forEach((r) => m.set(r[key], (m.get(r[key]) || 0) + 1));
    return [...m.entries()]
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, "zh"));
  }

  // 只应用时间区间，不应用便签/标签
  function recordsInRange() {
    if (!rangeFrom && !rangeTo) return DATA.records;
    return DATA.records.filter((r) => {
      const d = r.completed_at.slice(0, 10);   // 定宽 YYYY-MM-DD，字符串比较即日期比较
      return (!rangeFrom || d >= rangeFrom) && (!rangeTo || d <= rangeTo);
    });
  }

  // 当前生效的展示区间：未设区间时退回数据自身跨度
  function effectiveRange() {
    return [rangeFrom || DATA.date_range.from, rangeTo || DATA.date_range.to];
  }

  // 时间区间 + 指定便签下的记录子集（便签为 __ALL__ 时即整个区间）
  function scopedRecords(board = activeBoard) {
    const inRange = recordsInRange();
    return board === "__ALL__" ? inRange : inRange.filter((r) => r.board === board);
  }

  function renderFilters() {
    const inRange = recordsInRange();
    const scoped = scopedRecords();

    // 便签：整块隐藏与否继续看全局 DATA.boards —— 否则区间一收窄、恰好只剩一个便签
    // 有数据时整块会突然消失，很跳。
    const boardBlock = document.getElementById("an-board-block");
    if (DATA.boards.length <= 1) {
      boardBlock.style.display = "none";
    } else {
      boardBlock.style.display = "";
      const bs = [chipHtml("全部", inRange.length, activeBoard === "__ALL__", "#2B2F36", "__ALL__", "board")];
      countBy(inRange, "board").forEach((b) =>
        bs.push(chipHtml(b.name, b.count, activeBoard === b.name, "#5B616B", b.name, "board")));
      document.getElementById("an-board-bar").innerHTML = bs.join("");
    }

    // 标签：只列出当前便签（+ 区间）下真实出现过的，计数实时派生
    const tags = [chipHtml("全部", scoped.length, activeTag === "__ALL__", "#2B2F36", "__ALL__", "tag")];
    countBy(scoped, "tag").forEach((t) =>
      tags.push(chipHtml(t.name, t.count, activeTag === t.name, colorOfTag(t.name), t.name, "tag")));
    document.getElementById("an-tag-bar").innerHTML = tags.join("");

    renderRangeBar();

    document.querySelectorAll("#an-tag-bar .an-chip").forEach((el) =>
      el.addEventListener("click", () => { activeTag = el.dataset.tag; render(); }));
    document.querySelectorAll("#an-board-bar .an-chip").forEach((el) =>
      el.addEventListener("click", () => {
        const next = el.dataset.board;
        // 切换便签后，若当前标签在新便签下不存在，回落到「全部」，否则会停在空结果上
        const allowed = new Set(scopedRecords(next).map((r) => r.tag));
        if (activeTag !== "__ALL__" && !allowed.has(activeTag)) activeTag = "__ALL__";
        activeBoard = next;
        render();
      }));
  }

  function renderRangeBar() {
    const bar = document.getElementById("an-range-bar");
    if (!bar) return;
    bar.innerHTML = RANGE_PRESETS.map((r) => {
      const [f, t] = presetBounds(r.key);
      const n = r.key === "__ALL__"
        ? DATA.records.length
        : DATA.records.filter((x) => {
            const d = x.completed_at.slice(0, 10);
            return (!f || d >= f) && (!t || d <= t);
          }).length;
      return chipHtml(r.label, n, rangePreset === r.key, "#3F9D6B", r.key, "range");
    }).join("");

    bar.querySelectorAll(".an-chip").forEach((el) =>
      el.addEventListener("click", () => applyPreset(el.dataset.range)));

    const from = document.getElementById("an-date-from");
    const to = document.getElementById("an-date-to");
    if (from) from.value = rangeFrom || "";
    if (to) to.value = rangeTo || "";
  }

  // 切换区间后，若当前便签/标签在新区间里没有数据，回落到「全部」，避免停在空结果上
  function reconcileAfterRangeChange() {
    const inRange = recordsInRange();
    if (activeBoard !== "__ALL__" && !inRange.some((r) => r.board === activeBoard)) {
      activeBoard = "__ALL__";
    }
    if (activeTag !== "__ALL__" && !scopedRecords().some((r) => r.tag === activeTag)) {
      activeTag = "__ALL__";
    }
  }

  function applyPreset(key) {
    rangePreset = key;
    [rangeFrom, rangeTo] = presetBounds(key);
    reconcileAfterRangeChange();
    render();
  }

  function applyCustomRange() {
    const from = document.getElementById("an-date-from");
    const to = document.getElementById("an-date-to");
    rangeFrom = from && from.value ? from.value : null;
    rangeTo = to && to.value ? to.value : null;
    // 不自动纠正倒置区间：那会在用户还没填完另一个框时就把它改掉。
    // 起止填反了自然是 0 项，用户一眼能看出来并自行修正。
    rangePreset = !rangeFrom && !rangeTo ? "__ALL__" : "custom";
    reconcileAfterRangeChange();
    render();
  }

  function colorOfTag(name) {
    if (!tagColor[name]) {
      // 兜底：万一派生出的标签不在 DATA.tags 里，按名字稳定取一个色
      let h = 0;
      for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
      tagColor[name] = TAG_COLORS[h % TAG_COLORS.length];
    }
    return tagColor[name];
  }

  function getFiltered() {
    return recordsInRange().filter((r) =>
      (activeTag === "__ALL__" || r.tag === activeTag) &&
      (activeBoard === "__ALL__" || r.board === activeBoard));
  }

  /* ── stats ── */
  function renderStats() {
    const recs = getFiltered();
    const days = new Set(recs.map((r) => r.completed_at.slice(0, 10)));
    const focus = recs.reduce((s, r) => s + (r.focus_seconds || 0), 0);
    const tags = new Set(recs.map((r) => r.tag));
    const cards = [
      { n: recs.length, l: "完成", accent: true },
      { n: days.size, l: "活跃天数" },
      { n: focus ? fmtFocus(focus) : "0", l: "专注时长" },
      { n: tags.size, l: "涉及标签" },
    ];
    document.getElementById("an-stats").innerHTML = cards.map((c) =>
      `<div class="an-stat ${c.accent ? "accent" : ""}"><div class="num">${c.n}</div><div class="lab">${c.l}</div></div>`
    ).join("");
  }

  /* ── heatmap ── */
  function renderHeatmap() {
    const records = getFiltered();
    const byDate = {};
    records.forEach((r) => { const d = r.completed_at.slice(0, 10); (byDate[d] = byDate[d] || []).push(r); });

    const [ef, et] = effectiveRange();
    const startDate = parseDate(ef);
    const endDate = parseDate(et);
    const gridStart = addDays(startDate, -startDate.getDay());
    const gridEnd = addDays(endDate, 6 - endDate.getDay());
    const totalWeeks = Math.round((gridEnd - gridStart) / 86400000 + 1) / 7;

    const counts = Object.values(byDate).map((v) => v.length);
    const maxCount = Math.max(1, ...counts);
    function lvl(c) {
      if (c === 0) return 0;
      if (c <= maxCount * 0.25) return 1;
      if (c <= maxCount * 0.50) return 2;
      if (c <= maxCount * 0.75) return 3;
      return 4;
    }
    const lc = ["var(--hm-0)", "var(--hm-1)", "var(--hm-2)", "var(--hm-3)", "var(--hm-4)"];

    const cells = [];
    for (let w = 0; w < totalWeeks; w++) {
      for (let dow = 0; dow < 7; dow++) {
        const d = addDays(gridStart, w * 7 + dow);
        const ds = formatDate(d);
        const inRange = d >= startDate && d <= endDate;
        const c = (byDate[ds] || []).length;
        cells.push(inRange
          ? `<div class="hm-cell" style="background:${lc[lvl(c)]}" data-date="${ds}"></div>`
          : `<div class="hm-cell empty"></div>`);
      }
    }
    document.getElementById("heatmap").innerHTML = cells.join("");

    const months = [];
    let lastM = -1;
    for (let w = 0; w < totalWeeks; w++) {
      const m = addDays(gridStart, w * 7).getMonth();
      months.push(`<span>${m !== lastM ? (m + 1) + "月" : ""}</span>`);
      lastM = m;
    }
    document.getElementById("hm-months").innerHTML = months.join("");

    document.querySelectorAll("#heatmap .hm-cell[data-date]").forEach((el) => {
      el.addEventListener("mouseenter", (e) => {
        const ds = el.dataset.date;
        const tasks = byDate[ds] || [];
        const dt = parseDate(ds);
        let html = `<div class="tt">${dt.getMonth() + 1}月${dt.getDate()}日 周${WEEK_CN[dt.getDay()]}</div>
          <div class="tm">完成 ${tasks.length} 项</div>`;
        if (tasks.length) {
          const items = tasks.slice(0, 10).map((t) =>
            `<li><span class="h">${t.completed_at.slice(11, 16)}</span>${escapeHtml(clip(t.content, 38))}</li>`).join("");
          html += `<ul>${items}${tasks.length > 10 ? `<li style="opacity:.5">…还有 ${tasks.length - 10} 项</li>` : ""}</ul>`;
        }
        showTip(html, e);
      });
      el.addEventListener("mousemove", moveTip);
      el.addEventListener("mouseleave", hideTip);
    });
  }

  /* ── daily list ── */
  function renderDaily() {
    const records = getFiltered();
    const byDate = {};
    records.forEach((r) => { const d = r.completed_at.slice(0, 10); (byDate[d] = byDate[d] || []).push(r); });
    const dates = Object.keys(byDate).sort().reverse();

    const host = document.getElementById("an-daily");
    if (!dates.length) { host.innerHTML = `<div class="an-empty-list">这个筛选下还没有完成记录～</div>`; return; }

    const html = dates.map((d) => {
      const dt = parseDate(d);
      const tasks = byDate[d].slice().sort((a, b) => b.completed_at.localeCompare(a.completed_at));
      const rows = tasks.map((t) => {
        const time = t.completed_at.slice(11, 16);
        const tagPill = `<span class="an-pill tag" style="background:${tagColor[t.tag] || "#9AA0A8"}">#${escapeHtml(t.tag)}</span>`;
        const boardPill = (DATA.boards.length > 1 && t.board)
          ? `<span class="an-pill board">📌 ${escapeHtml(t.board)}</span>` : "";
        const focusPill = t.focus_seconds
          ? `<span class="an-pill focus" title="${t.focus_start || ""} ~ ${t.focus_end || ""}">⏱ ${fmtDurZh(t.focus_seconds)}</span>` : "";
        const srcPill = t.source === "db"
          ? `<span class="an-pill fresh" title="尚未存档为 Markdown">未归档</span>` : "";
        const notes = t.notes ? `<div class="notes">${escapeHtml(t.notes)}</div>` : "";
        return `<div class="an-task">
          <div class="an-task-row">
            <span class="time">${time}</span>
            <span class="ctext">${escapeHtml(t.content || "（无内容）")}</span>
            <span class="an-task-badges">${tagPill}${boardPill}${focusPill}${srcPill}</span>
          </div>${notes}
        </div>`;
      }).join("");
      return `<div class="an-day-group">
        <div class="an-day-head">
          <span class="d">${dt.getMonth() + 1}月${dt.getDate()}日</span>
          <span class="dow">周${WEEK_CN[dt.getDay()]}</span>
          <span class="cnt">${tasks.length} 项</span>
        </div>${rows}
      </div>`;
    }).join("");
    host.innerHTML = html;
  }

  /* ── tooltip ── */
  function showTip(html, e) { tip.innerHTML = html; tip.style.display = "block"; moveTip(e); }
  function moveTip(e) {
    const w = tip.offsetWidth, h = tip.offsetHeight;
    let left = e.clientX + 14, top = e.clientY + 14;
    if (left + w > window.innerWidth - 12) left = e.clientX - w - 14;
    if (top + h > window.innerHeight - 12) top = e.clientY - h - 14;
    tip.style.left = Math.max(8, left) + "px";
    tip.style.top = Math.max(8, top) + "px";
  }
  function hideTip() { tip.style.display = "none"; }

  /* ── helpers ── */
  function parseDate(s) { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); }
  function addDays(d, n) { const r = new Date(d); r.setDate(r.getDate() + n); return r; }
  function formatDate(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }
  function fmtFocus(sec) {
    sec = Math.round(sec); if (!sec) return "0";
    const h = Math.floor(sec / 3600), m = Math.round((sec % 3600) / 60);
    if (h && m) return `${h}h${m}m`; if (h) return `${h}h`; return `${m}m`;
  }
  function fmtDurZh(sec) {
    sec = Math.round(sec);
    if (sec >= 3600) { const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60); return m ? `${h}小时${m}分钟` : `${h}小时`; }
    if (sec >= 60) return `${Math.floor(sec / 60)}分钟`;
    return `${sec}秒`;
  }
  function clip(s, n) { s = String(s || ""); return s.length > n ? s.slice(0, n) + "…" : s; }
  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function escapeAttr(s) { return escapeHtml(s); }

  // 自定义日期输入只绑定一次（renderFilters 会重写 chips，但这三个元素是静态的）
  ["an-date-from", "an-date-to"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("change", applyCustomRange);
  });
  const resetBtn = document.getElementById("an-range-reset");
  if (resetBtn) resetBtn.addEventListener("click", () => applyPreset("__ALL__"));

  window.Analytics = { load };
})();
