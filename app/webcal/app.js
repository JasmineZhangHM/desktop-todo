"use strict";

// ---------- 全局状态 ----------

const state = {
  todos: [],
  completed: [],
  archived: [],       // 归档 md 里的历史已办（只读，来自 /api/analytics）
  boards: [],
  tags: [],
  defaultBoardId: null,
  today: null,        // 服务端下发，避免时区不一致
  view: "calendar",   // calendar | analytics
  calMode: "biweek",  // month | biweek | week，init 时从 localStorage 恢复
  anchor: null,       // "YYYY-MM-DD"，当前日历视图的锚点日期
  tagFilter: null,    // null = 全部
  boardFilter: null,  // null = 全部（board_id）
  editingId: null,    // null = 新增模式
};

const $ = (sel) => document.querySelector(sel);

// ---------- API ----------

async function api(path, options = {}) {
  let resp;
  try {
    resp = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (e) {
    $("#offline-banner").hidden = false;
    throw e;
  }
  $("#offline-banner").hidden = true;
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || `HTTP ${resp.status}`);
  }
  return resp.json();
}

async function reload() {
  const data = await api("/api/state");
  state.todos = data.todos;
  state.completed = data.completed;
  state.boards = data.boards;
  state.tags = data.tags;
  state.defaultBoardId = data.default_board_id;
  state.today = data.today;
  render();
}

async function mutate(path, options) {
  await api(path, options);
  await reload();
}

async function loadArchive() {
  const data = await api("/api/analytics");
  state.archived = data.records.filter((r) => r.source === "archive");
  renderGrid();
}

// ---------- 日期工具 ----------

function ymd(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function parseYmd(s) {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function boardOf(id) {
  return state.boards.find((b) => b.id === id) || null;
}

function boardByName(name) {
  return state.boards.find((b) => b.title === name) || null;
}

function matchTag(t) {
  return state.tagFilter === null || t.tag === state.tagFilter;
}

function matchBoard(t) {
  return state.boardFilter === null || t.board_id === state.boardFilter;
}

function matchFilters(t) {
  return matchTag(t) && matchBoard(t);
}

// 归档记录只有便签名字，没有 board_id；按名字对齐现存便签
function matchFiltersArchived(r) {
  if (state.tagFilter !== null && r.tag !== state.tagFilter) return false;
  if (state.boardFilter !== null) {
    const b = boardOf(state.boardFilter);
    if (!b || r.board !== b.title) return false;
  }
  return true;
}

// 已完成条目落在哪一天：优先 due_date，否则完成日
function completedDay(t) {
  return t.due_date || (t.completed_at ? t.completed_at.slice(0, 10) : null);
}

// ---------- 渲染 ----------

function render() {
  renderBoardBar();
  renderTagBar();
  renderLegend();
  renderUnscheduled();
  renderGrid();
  renderBoardSelect();
  renderTagOptions();
}

function renderBoardBar() {
  const bar = $("#board-bar");
  bar.innerHTML = "";
  const mk = (label, value, accent) => {
    const btn = document.createElement("button");
    btn.className = "tag-chip" + (state.boardFilter === value ? " active" : "");
    if (accent) {
      const dot = document.createElement("span");
      dot.className = "chip-dot";
      dot.style.background = accent;
      btn.appendChild(dot);
    }
    btn.appendChild(document.createTextNode(label));
    btn.onclick = () => {
      state.boardFilter = value;
      render();
    };
    bar.appendChild(btn);
  };
  mk("全部", null, null);
  state.boards.forEach((b) => mk(b.title, b.id, b.accent));
}

function renderTagBar() {
  const bar = $("#tag-bar");
  bar.innerHTML = "";
  const mk = (label, value) => {
    const btn = document.createElement("button");
    btn.className = "tag-chip" + (state.tagFilter === value ? " active" : "");
    btn.textContent = label;
    btn.onclick = () => {
      state.tagFilter = value;
      render();
    };
    bar.appendChild(btn);
  };
  mk("全部", null);
  state.tags.forEach((t) => mk("#" + t, t));
}

function renderLegend() {
  const box = $("#board-legend");
  box.innerHTML = "";
  state.boards.forEach((b) => {
    const item = document.createElement("span");
    item.className = "item";
    item.innerHTML = `<span class="dot" style="background:${b.accent}"></span>`;
    item.appendChild(document.createTextNode(b.title));
    box.appendChild(item);
  });
}

// inCell: 日格内用两行排版（标题独占整行可换行，标签另起一行）；侧栏保持单行密排
function makeChip(todo, { done = false, archived = false, inCell = false } = {}) {
  const chip = document.createElement("div");
  chip.className =
    "todo-chip" +
    (inCell ? " in-cell" : "") +
    (done ? " done" : "") +
    (archived ? " done archived" : "");
  chip.draggable = !done && !archived;
  if (todo.id != null) chip.dataset.id = todo.id;

  const board = archived ? boardByName(todo.boardName) : boardOf(todo.board_id);
  const dot = document.createElement("span");
  dot.className = "dot";
  dot.style.background = board ? board.accent : "#CCC";
  dot.title = archived ? todo.boardName || "" : board ? board.title : "";
  chip.appendChild(dot);

  if (!archived) {
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = done;
    cb.title = done ? "恢复为待办" : "标记完成";
    cb.onclick = (e) => {
      e.stopPropagation();
      mutate(`/api/todos/${todo.id}`, {
        method: "PATCH",
        body: JSON.stringify({ done: !done }),
      });
    };
    chip.appendChild(cb);
  }

  const txt = document.createElement("span");
  txt.className = "txt";
  txt.textContent = todo.content;
  txt.title = todo.content + (todo.notes ? `\n📝 ${todo.notes}` : "");
  chip.appendChild(txt);

  if (todo.tag) {
    const tm = document.createElement("span");
    tm.className = "tag-mark";
    tm.textContent = "#" + todo.tag;
    chip.appendChild(tm);
  }

  if (!done && !archived) {
    chip.addEventListener("dragstart", (e) => {
      e.dataTransfer.setData("text/plain", `todo:${todo.id}`);
      e.dataTransfer.effectAllowed = "move";
      chip.classList.add("dragging");
    });
    chip.addEventListener("dragend", () => chip.classList.remove("dragging"));
  }
  chip.onclick = () => openDialog(todo, null, { readonly: archived });
  return chip;
}

function renderUnscheduled() {
  const list = $("#unscheduled");
  list.innerHTML = "";
  const items = state.todos.filter((t) => !t.due_date && matchFilters(t));
  if (!items.length) {
    const li = document.createElement("li");
    li.className = "empty-hint";
    li.textContent = "没有未排期的待办";
    list.appendChild(li);
    return;
  }
  items.forEach((t) => {
    const li = document.createElement("li");
    li.appendChild(makeChip(t));
    list.appendChild(li);
  });
}

// 各视图模式：行数 / 单格折叠前可见条数
const CAL_MODE_KEY = "webcal_cal_mode";
const CAL_MODES = ["month", "biweek", "week"];
const MODE_ROWS = { month: 6, biweek: 2, week: 1 };
// 原 MODE_MAX_VISIBLE 已删除：日格改为始终可滚动，溢出与否在布局后实测

// 当前视图的网格范围：起始日（周日对齐）、行数、月视图的"本月"月份
function gridRange() {
  const a = parseYmd(state.anchor);
  if (state.calMode === "month") {
    const first = new Date(a.getFullYear(), a.getMonth(), 1);
    const start = new Date(first);
    start.setDate(first.getDate() - first.getDay());
    return { start, rows: 6, month: a.getMonth() };
  }
  const start = new Date(a);
  start.setDate(a.getDate() - a.getDay()); // 回退到本周周日
  return { start, rows: MODE_ROWS[state.calMode], month: null };
}

function renderCalTitle(start, days) {
  if (state.calMode === "month") {
    const a = parseYmd(state.anchor);
    $("#month-title").textContent = `${a.getFullYear()}年${a.getMonth() + 1}月`;
    return;
  }
  const end = new Date(start);
  end.setDate(start.getDate() + days - 1);
  const left = `${start.getFullYear()}年${start.getMonth() + 1}月${start.getDate()}日`;
  const right = end.getFullYear() === start.getFullYear()
    ? `${end.getMonth() + 1}月${end.getDate()}日`
    : `${end.getFullYear()}年${end.getMonth() + 1}月${end.getDate()}日`;
  $("#month-title").textContent = `${left} – ${right}`;
}

function renderGrid() {
  const grid = $("#grid");

  // 重建前抓取滚动位置：mutate → reload → render 会整树重建，
  // 否则每次勾选待办，月视图网格和格内都会跳回顶部
  const gridScroll = grid.scrollTop;
  const bodyScroll = new Map();
  grid.querySelectorAll(".day-cell").forEach((c) => {
    const b = c.querySelector(".day-body");
    if (b && b.scrollTop) bodyScroll.set(c.dataset.date, b.scrollTop);
  });

  grid.innerHTML = "";

  // 按天分桶
  const byDay = new Map();
  const put = (day, entry) => {
    if (!byDay.has(day)) byDay.set(day, []);
    byDay.get(day).push(entry);
  };
  state.todos.forEach((t) => {
    if (t.due_date && matchFilters(t)) put(t.due_date, { todo: t, done: false });
  });
  state.completed.forEach((t) => {
    const day = completedDay(t);
    if (day && matchFilters(t)) put(day, { todo: t, done: true });
  });
  // 归档历史：按完成日铺入（只读）
  state.archived.forEach((r) => {
    if (!matchFiltersArchived(r)) return;
    put(r.completed_at.slice(0, 10), {
      todo: {
        id: null,
        content: r.content,
        tag: r.tag === "无标签" ? null : r.tag,
        due_date: r.due_date,
        notes: r.notes,
        board_id: null,
        boardName: r.board === "未分类" ? null : r.board,
      },
      archived: true,
    });
  });

  // 网格范围由视图模式决定：月 6 行 / 双周 2 行 / 周 1 行
  const { start, rows, month } = gridRange();
  grid.className = "grid mode-" + state.calMode;
  renderCalTitle(start, rows * 7);

  for (let i = 0; i < rows * 7; i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    const key = ymd(d);
    const inMonth = month === null || d.getMonth() === month;

    const cell = document.createElement("div");
    cell.className = "day-cell";
    const dow = d.getDay();
    if (dow === 0 || dow === 6) cell.classList.add("weekend");
    if (!inMonth) cell.classList.add("other-month");
    if (key === state.today) cell.classList.add("today");
    cell.dataset.date = key;

    const entries = byDay.get(key) || [];

    const head = document.createElement("div");
    head.className = "day-head";
    const num = document.createElement("span");
    num.className = "day-num";
    // 月初标出月份，跨月边界（尤其双周 / 周视图）才读得懂
    num.textContent = d.getDate() === 1 ? `${d.getMonth() + 1}月1日` : d.getDate();
    head.appendChild(num);

    if (entries.length) {
      const badge = document.createElement("span");
      badge.className = "day-count";
      badge.textContent = entries.length;
      badge.title = `共 ${entries.length} 项，格内可滚动查看`;
      badge.hidden = true;          // 由 syncDayBodies 实测溢出后才显示
      head.appendChild(badge);
    }

    const add = document.createElement("button");
    add.className = "add-btn";
    add.textContent = "＋";
    add.title = "新增待办";
    add.onclick = (e) => {
      e.stopPropagation();
      openDialog(null, key);
    };
    head.appendChild(add);
    cell.appendChild(head);

    // 全量渲染 + 格内可滚动。原来的 slice(maxVisible) 截断与 "+n 项" 展开按钮已删除：
    // 那段展开逻辑判断的 cell.classList.contains("expanded") 恒为 false（cell 刚创建），
    // 且只改 DOM，任何写操作触发 reload() → render() 就会被冲掉。
    const body = document.createElement("div");
    body.className = "day-body";
    entries.forEach((e) =>
      body.appendChild(
        makeChip(e.todo, { done: e.done, archived: e.archived, inCell: true })
      )
    );
    cell.appendChild(body);

    // 双击空白也可新增
    cell.addEventListener("dblclick", (e) => {
      if (e.target === cell || e.target === body) openDialog(null, key);
    });

    // 拖拽落格 → 改期
    cell.addEventListener("dragover", (e) => {
      e.preventDefault();
      cell.classList.add("drag-over");
    });
    // 子节点变多后，掠过子元素也会触发 dragleave，需要判断是否真的离开了整个格子
    cell.addEventListener("dragleave", (e) => {
      if (!cell.contains(e.relatedTarget)) cell.classList.remove("drag-over");
    });
    cell.addEventListener("drop", (e) => {
      e.preventDefault();
      cell.classList.remove("drag-over");
      const id = parseDragId(e);
      if (id != null) {
        mutate(`/api/todos/${id}`, {
          method: "PATCH",
          body: JSON.stringify({ due_date: key }),
        });
      }
    });

    grid.appendChild(cell);
  }

  grid.scrollTop = gridScroll;
  syncDayBodies(grid, bodyScroll);
}

// 布局完成后一次性实测：哪些日格真的溢出（取决于标题折了几行），顺便还原格内滚动位置。
// 溢出每次渲染重新实测，所以永远准、不会过期，也就不需要任何新的持久状态。
function syncDayBodies(grid, bodyScroll) {
  requestAnimationFrame(() => {
    grid.querySelectorAll(".day-cell").forEach((cell) => {
      const body = cell.querySelector(".day-body");
      if (!body) return;
      const prev = bodyScroll.get(cell.dataset.date);
      if (prev) body.scrollTop = prev;
      const overflow = body.scrollHeight - body.clientHeight > 1;
      cell.classList.toggle("has-more", overflow);
      const badge = cell.querySelector(".day-count");
      if (badge) badge.hidden = !overflow;
    });
  });
}

function parseDragId(e) {
  const data = e.dataTransfer.getData("text/plain");
  if (data && data.startsWith("todo:")) return parseInt(data.slice(5), 10);
  return null;
}

// 拖回"未安排"区 → 清除日期
const unscheduledBox = $("#unscheduled");
unscheduledBox.addEventListener("dragover", (e) => {
  e.preventDefault();
  unscheduledBox.classList.add("drag-over");
});
unscheduledBox.addEventListener("dragleave", () =>
  unscheduledBox.classList.remove("drag-over")
);
unscheduledBox.addEventListener("drop", (e) => {
  e.preventDefault();
  unscheduledBox.classList.remove("drag-over");
  const id = parseDragId(e);
  if (id != null) {
    mutate(`/api/todos/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ due_date: null }),
    });
  }
});

// ---------- 弹窗 ----------

function renderBoardSelect() {
  const sel = $("#f-board");
  sel.innerHTML = "";
  state.boards.forEach((b) => {
    const opt = document.createElement("option");
    opt.value = b.id;
    opt.textContent = b.title;
    sel.appendChild(opt);
  });
}

function renderTagOptions() {
  const dl = $("#tag-options");
  dl.innerHTML = "";
  state.tags.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t;
    dl.appendChild(opt);
  });
}

function openDialog(todo, presetDate, { readonly = false } = {}) {
  state.editingId = todo && !readonly ? todo.id : null;
  $("#dialog-title").textContent = readonly ? "已办详情（已归档）" : todo ? "编辑待办" : "新增待办";
  $("#f-content").value = todo ? todo.content : "";
  $("#f-tag").value = todo && todo.tag ? todo.tag : "";
  $("#f-date").value = todo ? todo.due_date || "" : presetDate || "";
  $("#f-notes").value = todo && todo.notes ? todo.notes : "";

  const boardSel = $("#f-board");
  renderBoardSelect();
  if (readonly) {
    // 归档记录只有便签名字；便签可能已删除，临时补一个选项用于展示
    const name = todo.boardName || "未分类";
    const exist = boardByName(name);
    if (exist) {
      boardSel.value = exist.id;
    } else {
      const opt = document.createElement("option");
      opt.value = "__archived__";
      opt.textContent = name;
      boardSel.appendChild(opt);
      boardSel.value = "__archived__";
    }
  } else {
    boardSel.value = todo ? todo.board_id : state.defaultBoardId;
  }
  boardSel.disabled = !!todo; // 编辑不支持改所属便签

  ["#f-content", "#f-tag", "#f-date", "#f-notes"].forEach(
    (sel) => ($(sel).disabled = readonly)
  );
  $("#btn-save").hidden = readonly;
  $("#btn-delete").hidden = readonly || !todo;
  $("#btn-cancel").textContent = readonly ? "关闭" : "取消";

  $("#todo-dialog").showModal();
  if (!readonly) $("#f-content").focus();
}

$("#todo-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    content: $("#f-content").value.trim(),
    tag: $("#f-tag").value.trim().replace(/^#/, "") || null,
    due_date: $("#f-date").value || null,
    notes: $("#f-notes").value.trim() || null,
  };
  if (!payload.content) return;
  try {
    if (state.editingId != null) {
      await mutate(`/api/todos/${state.editingId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    } else {
      payload.board_id = parseInt($("#f-board").value, 10);
      await mutate("/api/todos", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    }
    $("#todo-dialog").close();
  } catch (err) {
    alert("保存失败：" + err.message);
  }
});

$("#btn-cancel").onclick = () => $("#todo-dialog").close();

$("#btn-delete").onclick = async () => {
  if (state.editingId == null) return;
  if (!confirm("确定删除这条待办吗？")) return;
  await mutate(`/api/todos/${state.editingId}`, { method: "DELETE" });
  $("#todo-dialog").close();
};

// ---------- 导航 ----------

function shiftView(delta) {
  const a = parseYmd(state.anchor);
  if (state.calMode === "month") {
    // 用 1 号做月运算，避免 31 号跨月溢出
    state.anchor = ymd(new Date(a.getFullYear(), a.getMonth() + delta, 1));
  } else {
    a.setDate(a.getDate() + delta * (state.calMode === "biweek" ? 14 : 7));
    state.anchor = ymd(a);
  }
  renderGrid();
}

$("#prev-month").onclick = () => shiftView(-1);
$("#next-month").onclick = () => shiftView(1);
$("#today-btn").onclick = () => {
  state.anchor = state.today;
  renderGrid();
};

// ---------- 日历视图模式（月 / 双周 / 周） ----------

const MODE_NAV_TITLE = { month: "月", biweek: "两周", week: "周" };

function setCalMode(mode, { save = true } = {}) {
  state.calMode = mode;
  if (save) localStorage.setItem(CAL_MODE_KEY, mode);
  document.querySelectorAll(".mode-btn").forEach((b) =>
    b.classList.toggle("active", b.dataset.mode === mode)
  );
  $("#prev-month").title = "上一" + MODE_NAV_TITLE[mode];
  $("#next-month").title = "下一" + MODE_NAV_TITLE[mode];
  renderGrid();
}

document.querySelectorAll(".mode-btn").forEach((b) => {
  b.onclick = () => setCalMode(b.dataset.mode);
});

// ---------- 视图切换（日历 / 分析） ----------

function setView(v) {
  state.view = v;
  $("#view-calendar").hidden = v !== "calendar";
  $("#view-analytics").hidden = v !== "analytics";
  $("#tab-calendar").classList.toggle("active", v === "calendar");
  $("#tab-analytics").classList.toggle("active", v === "analytics");
  const wantHash = v === "analytics" ? "#analytics" : "";
  if (location.hash !== wantHash) {
    history.replaceState(null, "", location.pathname + wantHash);
  }
  if (v === "analytics") Analytics.load().catch(() => {});
}

$("#tab-calendar").onclick = () => setView("calendar");
$("#tab-analytics").onclick = () => setView("analytics");
window.addEventListener("hashchange", () =>
  setView(location.hash === "#analytics" ? "analytics" : "calendar")
);

// Qt 侧改动后回到页面自动刷新
function refreshAll() {
  reload().catch(() => {});
  loadArchive().catch(() => {});
  if (state.view === "analytics") Analytics.load().catch(() => {});
}
window.addEventListener("focus", refreshAll);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) refreshAll();
});

// ---------- 启动 ----------

(async function init() {
  const saved = localStorage.getItem(CAL_MODE_KEY);
  state.calMode = CAL_MODES.includes(saved) ? saved : "biweek";
  state.anchor = ymd(new Date()); // 先用本机时间兜底，reload 后以服务端 today 校准
  if (location.hash === "#analytics") setView("analytics");
  try {
    await reload();
    state.anchor = state.today;
    setCalMode(state.calMode, { save: false }); // 点亮模式按钮 + renderGrid
    await loadArchive();
  } catch (e) {
    console.error(e);
  }
})();
