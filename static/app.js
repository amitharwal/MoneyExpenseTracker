(() => {
  "use strict";

  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
  const CSRF = $('meta[name="csrf-token"]').content;
  const { categories: CATEGORIES, today: TODAY } = window.LEDGER;

  // Rich but not neon category hues; readable on light and dark.
  const CAT_COLORS = {
    Housing: "#4c6ef5", Groceries: "#37b24d", Dining: "#f76707", Transport: "#15aabf",
    Bills: "#f59f00", Shopping: "#e64980", Entertainment: "#7950f2", Health: "#12b886",
    Travel: "#228be6", Other: "#868e96", Salary: "#2f9e44", Freelance: "#0ca678",
    Investments: "#74b816", Gifts: "#d6336c",
  };
  const catColor = (c) => CAT_COLORS[c] || "#868e96";

  // --- Formatting -----------------------------------------------------------

  const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
  const usd0 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
  const money = (v) => (v < 0 ? "−" : "") + usd.format(Math.abs(v));
  const money0 = (v) => (v < 0 ? "−" : "") + usd0.format(Math.abs(v));
  const signed = (v) => (v < 0 ? "−" : "+") + usd.format(Math.abs(v));
  const pct = (v, digits = 1) => (v < 0 ? "−" : "+") + Math.abs(v).toFixed(digits) + "%";
  const parseDate = (iso) => { const [y, m, d] = iso.split("-").map(Number); return new Date(y, m - 1, d || 1); };
  const fmtDate = (iso, opts) => parseDate(iso).toLocaleDateString("en-US", opts);
  const ordinal = (n) => n + (["th", "st", "nd", "rd"][(n % 100 - 20) % 10] || ["th", "st", "nd", "rd"][n % 100] || "th");

  function relDay(iso) {
    const days = Math.round((parseDate(iso) - parseDate(TODAY)) / 86400000);
    if (days === 0) return "Today";
    if (days === 1) return "Tomorrow";
    if (days === -1) return "Yesterday";
    if (days > 1 && days < 7) return `In ${days} days`;
    return null;
  }

  // Where spending "should" be by today: recurring bills count in full, the rest accrues daily.
  function paceFor(c, monthPace) {
    if (!c.budget) return monthPace;
    const fixed = Math.min(c.fixed || 0, c.budget);
    return Math.min(1, (fixed + (c.budget - fixed) * monthPace) / c.budget);
  }

  const tone = (v, goodWhenUp = true) => (!v ? "" : (v > 0) === goodWhenUp ? "pos" : "neg");

  function esc(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // --- API + toast ----------------------------------------------------------

  async function api(path, options = {}) {
    const headers = { "X-CSRF-Token": CSRF };
    if (!(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
    let res;
    try {
      res = await fetch(path, { credentials: "same-origin", ...options, headers });
    } catch (_) {
      throw new Error("Can't reach Ledger. Is it still running?");
    }
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.error || "Something went wrong.");
    return body;
  }

  let toastTimer;
  function toast(msg, action) {
    const el = $("#toast");
    el.innerHTML = `<span>${esc(msg)}</span>`;
    if (action) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = action.label;
      btn.addEventListener("click", () => { el.classList.remove("show"); action.run(); });
      el.appendChild(btn);
    }
    el.classList.toggle("has-action", !!action);
    el.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("show"), action ? 6000 : 2800);
  }

  // --- Shared row renderers -------------------------------------------------

  const txnCache = new Map();

  function mono(category) {
    return `<span class="mono" style="--c:${catColor(category)}" aria-hidden="true">${esc(category[0])}</span>`;
  }

  function txnRow(t, meta) {
    txnCache.set(t.id, t);
    const amt = t.kind === "income"
      ? `<span class="pos">+${usd.format(t.amount)}</span>`
      : `−${usd.format(t.amount)}`;
    return `
      <button class="txn" type="button" data-txn="${t.id}">
        ${mono(t.category)}
        <span>
          <span class="txn-title"><span>${esc(t.note || t.category)}</span>${t.recurring ? '<span class="tag-rec" title="Recurring">Monthly</span>' : ""}</span>
          <span class="txn-meta">${esc(meta)}</span>
        </span>
        <span class="txn-amt num">${amt}</span>
      </button>`;
  }

  // =========================================================================
  // Router
  // =========================================================================

  const VIEWS = {
    overview: loadOverview, activity: loadActivity, import: loadImport,
    budgets: loadBudgets, recurring: loadRecurring, settings: loadSettings,
  };
  let currentView = null;

  function route() {
    const name = location.hash.slice(1) in VIEWS ? location.hash.slice(1) : "overview";
    if (name !== currentView) {
      currentView = name;
      $$("[data-view]").forEach((v) => { v.hidden = v.dataset.view !== name; });
      $$("[data-nav]").forEach((a) => {
        if (a.dataset.nav === name) a.setAttribute("aria-current", "page");
        else a.removeAttribute("aria-current");
      });
      window.scrollTo(0, 0);
    }
    VIEWS[name]();
  }

  const refresh = () => VIEWS[currentView]();
  window.addEventListener("hashchange", route);

  // =========================================================================
  // Overview
  // =========================================================================

  const RANGE_LABELS = {
    "1M": "past month", "3M": "past 3 months", "6M": "past 6 months",
    "YTD": "year to date", "1Y": "past year", "ALL": "all time",
  };
  let ovRange = "3M";
  let ov = null;

  async function loadOverview() {
    try { ov = await api(`/api/overview?range=${ovRange}`); } catch (e) { toast(e.message); return; }
    renderOverview();
  }

  function renderOverview() {
    const hour = new Date().getHours();
    const part = hour < 12 ? "morning" : hour < 18 ? "afternoon" : "evening";
    $("#ov-greeting").textContent = `Good ${part}`;
    $("#ov-demo").hidden = !ov.has_demo;
    $("#ov-date").textContent = fmtDate(TODAY, { weekday: "long", month: "long", day: "numeric" });
    $("#ov-empty").hidden = ov.has_any;
    showQuote(ov.balance, ov.change, ov.change_pct, RANGE_LABELS[ov.range]);
    drawChart();

    // KPIs
    const m = ov.month;
    $("#kpi-spent-label").textContent = `Spent in ${m.label}`;
    $("#kpi-income-label").textContent = `Earned in ${m.label}`;
    $("#kpi-spent").textContent = money(m.spent);
    $("#kpi-spent-sub").innerHTML = m.spent_change == null ? "No data for last month"
      : `<span class="${tone(Math.round(m.spent_change), false)}">${pct(m.spent_change, 0)}</span> vs. same point last month`;
    $("#kpi-income").textContent = money(m.income);
    $("#kpi-income-sub").innerHTML = m.income_change == null ? "No data for last month"
      : `<span class="${tone(Math.round(m.income_change))}">${pct(m.income_change, 0)}</span> vs. same point last month`;
    $("#kpi-net").innerHTML = `<span class="${m.net < 0 ? "neg" : ""}">${signed(m.net)}</span>`;
    $("#kpi-net-sub").textContent = m.income ? `${Math.round((m.net / m.income) * 100)}% of income kept` : `Day ${m.day} of ${m.days}`;
    $("#kpi-projected").textContent = money(m.projected);
    $("#kpi-projected-sub").textContent = m.bills_left || m.income_left
      ? `${money0(m.bills_left)} in bills still due this month`
      : "Nothing else due this month";

    // Insights
    $("#ov-insights").innerHTML = ov.insights.map((i) => `
      <article class="insight ${i.tone}">
        <h3>${esc(i.title)}</h3>
        <p>${esc(i.body)}</p>
      </article>`).join("");
    $("#ov-insights").hidden = !ov.insights.length;

    // Categories: one stacked bar for the month, then a legend with budget progress
    $("#ov-cats-title").textContent = `Spending in ${m.label}`;
    const pace = m.day / m.days;
    const cats = ov.categories;
    $("#ov-cats-empty").hidden = cats.length > 0;
    $("#ov-stack").hidden = !cats.length;
    $("#ov-stack").innerHTML = cats.map((c) =>
      `<span style="flex:${c.spent} 1 0;background:${catColor(c.name)}" title="${esc(c.name)}: ${money0(c.spent)}"></span>`
    ).join("");
    $("#ov-cats").innerHTML = cats.map((c) => {
      const share = m.spent ? Math.round((c.spent / m.spent) * 100) : 0;
      let sub = `${share}% of spending`;
      let bar = "";
      if (c.budget) {
        const over = c.spent > c.budget;
        sub = over ? `<span class="neg">${money0(c.spent - c.budget)} over budget</span>` : `${money0(c.budget - c.spent)} left of ${money0(c.budget)}`;
        bar = `
          <div class="bar thin ${over ? "over" : ""}" style="--fill:${catColor(c.name)}">
            <span class="bar-fill" style="width:${Math.min(c.spent / c.budget, 1) * 100}%"></span>
            <span class="bar-pace" style="left:${paceFor(c, pace) * 100}%"></span>
          </div>`;
      }
      return `
        <li style="--c:${catColor(c.name)}">
          <div class="cat-top">
            <span class="cat-name"><span class="cat-swatch"></span>${esc(c.name)}</span>
            <span class="cat-amt num">${money0(c.spent)}</span>
          </div>
          <p class="cat-sub num">${sub}</p>
          ${bar}
        </li>`;
    }).join("");

    // Upcoming
    $("#ov-upcoming-empty").hidden = ov.upcoming.length > 0;
    $("#ov-upcoming").innerHTML = ov.upcoming.map((u) => `
      <li>
        <span class="date-block" style="--c:${catColor(u.category)}"><small>${fmtDate(u.date, { month: "short" })}</small><b>${parseDate(u.date).getDate()}</b></span>
        <span>
          <span class="up-name">${esc(u.note)}</span><br>
          <span class="up-meta">${esc(u.category)} · ${relDay(u.date) || fmtDate(u.date, { weekday: "long" })}</span>
        </span>
        <span class="up-amt num ${u.kind === "income" ? "pos" : ""}">${u.kind === "income" ? "+" : "−"}${usd.format(u.amount)}</span>
      </li>`).join("");

    // Recent
    $("#ov-recent-empty").hidden = ov.recent.length > 0;
    $("#ov-recent").innerHTML = ov.recent.map((t) =>
      `<li>${txnRow(t, `${t.category} · ${relDay(t.date) || fmtDate(t.date, { month: "short", day: "numeric" })}`)}</li>`
    ).join("");
  }

  function showQuote(value, change, changePct, label) {
    $("#ov-balance").textContent = money(value);
    const el = $("#ov-change");
    el.textContent = signed(change) + (changePct == null ? "" : ` (${pct(changePct, 2)})`);
    el.className = change < 0 ? "neg" : change > 0 ? "pos" : "";
    $("#ov-change-label").textContent = label;
  }

  $("#ov-ranges").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-range]");
    if (!btn) return;
    ovRange = btn.dataset.range;
    $$("#ov-ranges button").forEach((b) => b.setAttribute("aria-selected", b === btn));
    loadOverview();
  });

  // --- Chart ----------------------------------------------------------------

  const chart = {
    root: $("#chart"),
    svg: $("#chart svg"),
    line: $("#chart .chart-line"),
    dim: $("#chart .chart-line-dim"),
    base: $("#chart .chart-base"),
    cursor: $("#chart .chart-cursor"),
    dot: $("#chart .chart-dot"),
    area: $("#chart .chart-area"),
    axis: $("#chart .chart-axis"),
    pts: [],
    path: "",
  };

  function drawChart() {
    const { series, opening, change } = ov;
    const w = chart.svg.clientWidth, h = chart.svg.clientHeight;
    if (!w) return;
    const pad = 12;
    const values = series.map((p) => p.v);
    const min = Math.min(opening, ...values), max = Math.max(opening, ...values);
    const y = (v) => (max === min ? h / 2 : pad + (1 - (v - min) / (max - min)) * (h - pad * 2));
    const n = series.length;

    chart.root.style.setProperty("--trend", change < 0 ? "var(--neg)" : change > 0 ? "var(--pos)" : "var(--ink)");
    chart.svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    chart.pts = series.map((p, i) => ({ ...p, x: n === 1 ? w : (i / (n - 1)) * w, y: y(p.v) }));
    chart.path = chart.pts.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
    chart.line.setAttribute("d", chart.path);
    chart.dim.setAttribute("d", "");
    chart.h = h;
    chart.flat = max === min;  // nothing to shade under a flat line
    chart.area.setAttribute("d", chart.flat ? "" : areaPath(chart.pts));
    const by = y(opening);
    Object.entries({ x1: 0, x2: w, y1: by, y2: by }).forEach(([k, v]) => chart.base.setAttribute(k, v));
    chart.cursor.setAttribute("y1", 0);
    chart.cursor.setAttribute("y2", h);

    // Axis labels: 5 evenly spaced dates
    const long = n > 100;
    const ticks = n < 2 ? [0] : [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(f * (n - 1)));
    chart.axis.innerHTML = [...new Set(ticks)].map((i) => {
      const p = chart.pts[i];
      const label = fmtDate(p.d, long ? { month: "short", year: "2-digit" } : { month: "short", day: "numeric" });
      return `<span style="left:${(p.x / w) * 100}%">${label}</span>`;
    }).join("");
  }

  function areaPath(pts) {
    if (!pts.length) return "";
    const line = pts.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
    return `${line} L${pts[pts.length - 1].x.toFixed(1)} ${chart.h} L${pts[0].x.toFixed(1)} ${chart.h} Z`;
  }

  function scrub(clientX) {
    const pts = chart.pts;
    if (!pts.length) return;
    const rect = chart.svg.getBoundingClientRect();
    const x = Math.max(0, Math.min(rect.width, clientX - rect.left));
    const i = pts.length === 1 ? 0 : Math.round((x / rect.width) * (pts.length - 1));
    const p = pts[i];

    chart.root.classList.add("scrubbing");
    // Accent line up to the cursor, dimmed after it
    chart.line.setAttribute("d", pts.slice(0, i + 1).map((q, j) => `${j ? "L" : "M"}${q.x.toFixed(1)} ${q.y.toFixed(1)}`).join(" "));
    chart.dim.setAttribute("d", pts.slice(i).map((q, j) => `${j ? "L" : "M"}${q.x.toFixed(1)} ${q.y.toFixed(1)}`).join(" "));
    chart.area.setAttribute("d", chart.flat ? "" : areaPath(pts.slice(0, i + 1)));
    chart.cursor.setAttribute("x1", p.x);
    chart.cursor.setAttribute("x2", p.x);
    chart.dot.setAttribute("cx", p.x);
    chart.dot.setAttribute("cy", p.y);

    const change = p.v - ov.opening;
    showQuote(p.v, change, ov.opening > 0 ? (change / ov.opening) * 100 : null,
      fmtDate(p.d, { weekday: "short", month: "short", day: "numeric", year: "numeric" }));
  }

  function endScrub() {
    if (!ov) return;
    chart.root.classList.remove("scrubbing");
    chart.line.setAttribute("d", chart.path);
    chart.dim.setAttribute("d", "");
    chart.area.setAttribute("d", chart.flat ? "" : areaPath(chart.pts));
    showQuote(ov.balance, ov.change, ov.change_pct, RANGE_LABELS[ov.range]);
  }

  chart.svg.addEventListener("pointermove", (e) => scrub(e.clientX));
  chart.svg.addEventListener("pointerdown", (e) => scrub(e.clientX));
  chart.svg.addEventListener("pointerleave", endScrub);
  chart.svg.addEventListener("pointercancel", endScrub);
  chart.svg.addEventListener("pointerup", (e) => { if (e.pointerType !== "mouse") endScrub(); });

  let resizeFrame;
  window.addEventListener("resize", () => {
    cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(() => { if (ov && currentView === "overview") drawChart(); });
  });

  // =========================================================================
  // Activity
  // =========================================================================

  const act = { q: "", kind: "", category: "", month: "", source: "" };
  let actRequest = 0;

  (function fillCategoryFilter() {
    const sel = $("#act-category");
    const groups = [["Spending", CATEGORIES.expense], ["Income", CATEGORIES.income]];
    sel.innerHTML += groups.map(([label, cats]) =>
      `<optgroup label="${label}">${cats.map((c) => `<option>${esc(c)}</option>`).join("")}</optgroup>`
    ).join("");
  })();

  async function loadActivity() {
    const id = ++actRequest;
    const params = new URLSearchParams(Object.entries(act).filter(([, v]) => v));
    let data;
    try { data = await api(`/api/transactions?${params}`); } catch (e) { toast(e.message); return; }
    if (id !== actRequest) return; // a newer search is in flight
    renderActivity(data);
  }

  function renderActivity(data) {
    // Month filter options
    const monthSel = $("#act-month");
    const current = monthSel.value;
    monthSel.innerHTML = `<option value="">All time</option>` + data.months.map((m) =>
      `<option value="${m}">${fmtDate(m, { month: "long", year: "numeric" })}</option>`).join("");
    monthSel.value = data.months.includes(current) ? current : "";

    const rows = data.transactions;
    const net = data.income - data.spent;
    const sourceChip = act.source ? `<button class="chip" type="button" data-clear-source>Just imported ✕</button>` : "";
    $("#act-summary").innerHTML = sourceChip + (rows.length
      ? `<span><b>${rows.length.toLocaleString()}</b> transaction${rows.length === 1 ? "" : "s"}</span>
         <span>In <b class="pos">${money(data.income)}</b></span>
         <span>Out <b>${money(data.spent)}</b></span>
         <span>Net <b class="${net < 0 ? "neg" : ""}">${signed(net)}</b></span>`
      : "");

    $("#act-empty").hidden = rows.length > 0;
    const groups = new Map();
    rows.forEach((t) => { if (!groups.has(t.date)) groups.set(t.date, []); groups.get(t.date).push(t); });
    $("#act-list").innerHTML = [...groups].map(([date, items]) => {
      const dayNet = items.reduce((s, t) => s + (t.kind === "income" ? t.amount : -t.amount), 0);
      const label = relDay(date) || fmtDate(date, { weekday: "long", month: "long", day: "numeric", year: "numeric" });
      return `
        <div class="day-group">
          <div class="day-head"><span>${label}</span><span class="num">${signed(dayNet)}</span></div>
          ${items.map((t) => txnRow(t, t.category)).join("")}
        </div>`;
    }).join("");
  }

  let searchTimer;
  $("#act-q").addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { act.q = e.target.value.trim(); loadActivity(); }, 180);
  });
  $("#act-kind").addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    act.kind = btn.dataset.kind;
    $$("#act-kind button").forEach((b) => b.setAttribute("aria-pressed", b === btn));
    loadActivity();
  });
  $("#act-summary").addEventListener("click", (e) => {
    if (e.target.closest("[data-clear-source]")) { act.source = ""; loadActivity(); }
  });
  $("#act-category").addEventListener("change", (e) => { act.category = e.target.value; loadActivity(); });
  $("#act-month").addEventListener("change", (e) => { act.month = e.target.value; loadActivity(); });

  // =========================================================================
  // Budgets
  // =========================================================================

  async function loadBudgets() {
    let data;
    try { data = await api("/api/budgets"); } catch (e) { toast(e.message); return; }
    renderBudgets(data);
  }

  function renderBudgets(data) {
    const pace = data.day / data.days;
    const set = data.categories.filter((c) => c.budget);
    const total = set.reduce((s, c) => s + c.budget, 0);
    const spent = set.reduce((s, c) => s + c.spent, 0);
    const left = total - spent;

    $("#bud-month").textContent = `${data.month} · day ${data.day} of ${data.days}`;
    $("#bud-total").textContent = money0(total);
    $("#bud-count").textContent = set.length ? `${set.length} categor${set.length === 1 ? "y" : "ies"}` : "No budgets yet";
    $("#bud-spent").textContent = money0(spent);
    $("#bud-spent-sub").textContent = total ? `${Math.round((spent / total) * 100)}% used, ${Math.round(pace * 100)}% of month gone` : "";
    $("#bud-left").innerHTML = `<span class="${left < 0 ? "neg" : ""}">${money0(left)}</span>`;
    const daysLeft = data.days - data.day + 1;
    $("#bud-left-sub").textContent = total && left > 0 ? `${money0(left / daysLeft)} a day for ${daysLeft} days` : "";

    $("#bud-list").innerHTML = data.categories.map((c) => {
      let status = "", cls = "";
      if (c.budget) {
        const remaining = c.budget - c.spent;
        if (remaining < 0) { status = `${money0(-remaining)} over`; cls = "over"; }
        else if (c.spent > c.budget * paceFor(c, pace) * 1.1) { status = `${money0(remaining)} left · ahead of pace`; cls = "warn"; }
        else { status = `${money0(remaining)} left`; cls = "ok"; }
      } else {
        status = c.spent ? "No limit set" : "";
      }
      const scale = c.budget || Math.max(c.average, c.spent, 1);
      const width = Math.min(c.spent / scale, 1) * 100;
      return `
        <li class="budget ${c.budget ? "" : "unset"}">
          <div class="budget-name">
            ${mono(c.name)}
            <span>${esc(c.name)}<small class="num">avg ${money0(c.average)}/mo</small></span>
          </div>
          <div class="budget-track">
            <div class="bar ${c.budget && c.spent > c.budget ? "over" : ""}" style="--fill:${catColor(c.name)}">
              <span class="bar-fill" style="width:${width}%"></span>
              ${c.budget ? `<span class="bar-pace" style="left:${paceFor(c, pace) * 100}%"></span>` : ""}
            </div>
            <div class="budget-status num">
              <span>${money0(c.spent)} spent</span>
              <span class="status ${cls}">${status}</span>
            </div>
          </div>
          <label class="budget-input">
            <span>$</span>
            <input class="num" inputmode="decimal" data-budget="${esc(c.name)}" aria-label="${esc(c.name)} monthly budget"
                   value="${c.budget ? Math.round(c.budget) : ""}" placeholder="${Math.round(c.average) || "Set"}">
          </label>
        </li>`;
    }).join("");
  }

  $("#bud-list").addEventListener("change", async (e) => {
    const input = e.target.closest("input[data-budget]");
    if (!input) return;
    const value = input.value.replace(/[^\d.]/g, "");
    try {
      await api(`/api/budgets/${encodeURIComponent(input.dataset.budget)}`, { method: "PUT", body: JSON.stringify({ amount: value }) });
      toast(value ? `${input.dataset.budget} budget set to ${usd0.format(value)}` : `${input.dataset.budget} budget removed`);
      loadBudgets();
    } catch (err) { toast(err.message); }
  });
  $("#bud-list").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && e.target.matches("input[data-budget]")) e.target.blur();
  });

  // =========================================================================
  // Recurring
  // =========================================================================

  const recCache = new Map();

  async function loadRecurring() {
    let data;
    try { data = await api("/api/recurring"); } catch (e) { toast(e.message); return; }
    renderRecurring(data);
  }

  function renderRecurring(data) {
    $("#rec-income").textContent = money(data.income);
    $("#rec-fixed").textContent = money(data.fixed);
    $("#rec-share").textContent = data.fixed_share == null ? "—" : `${Math.round(data.fixed_share)}%`;
    $("#rec-share-sub").textContent = data.fixed_share == null ? "Add a paycheck to compare"
      : data.fixed_share > 50 ? "Over half of income is committed" : "Of monthly income is committed";

    $("#rec-empty").hidden = data.items.length > 0;
    $("#rec-list").innerHTML = data.items.map((r) => {
      recCache.set(r.id, r);
      return `
        <li class="rec ${r.active ? "" : "paused"}">
          ${mono(r.category)}
          <span>
            <span class="rec-name">${esc(r.note)}</span><br>
            <span class="rec-meta">${esc(r.category)} · Monthly on the ${ordinal(r.day)}</span>
          </span>
          <span class="rec-next">${r.active ? `Next<b>${relDay(r.next_date) || fmtDate(r.next_date, { month: "short", day: "numeric" })}</b>` : "<b>Paused</b>"}</span>
          <span class="rec-amt num ${r.kind === "income" ? "pos" : ""}">${r.kind === "income" ? "+" : "−"}${usd.format(r.amount)}</span>
          <span class="rec-actions">
            <button class="btn btn-outline btn-sm" type="button" data-rec-toggle="${r.id}">${r.active ? "Pause" : "Resume"}</button>
            <button class="btn btn-outline btn-sm" type="button" data-rec-edit="${r.id}">Edit</button>
          </span>
        </li>`;
    }).join("");
  }

  $("#rec-list").addEventListener("click", async (e) => {
    const edit = e.target.closest("[data-rec-edit]");
    if (edit) { openDrawer("rec", recCache.get(Number(edit.dataset.recEdit))); return; }
    const toggle = e.target.closest("[data-rec-toggle]");
    if (!toggle) return;
    const r = recCache.get(Number(toggle.dataset.recToggle));
    toggle.disabled = true;
    try {
      await api(`/api/recurring/${r.id}`, { method: "PATCH", body: JSON.stringify({ active: !r.active }) });
      toast(`${r.note} ${r.active ? "paused" : "resumed"}`);
      loadRecurring();
    } catch (err) { toast(err.message); toggle.disabled = false; }
  });

  // =========================================================================
  // Drawer — add/edit transactions and recurring items
  // =========================================================================

  const drawer = {
    el: $("#drawer"), backdrop: $("#drawer-backdrop"), form: $("#drawer-form"),
    mode: "txn", item: null, kind: "expense", category: null, lastFocus: null,
  };
  const f = {
    title: $("#drawer-title"), amount: $("#f-amount"), note: $("#f-note"), noteLabel: $("#f-note-label"),
    category: $("#f-category"), date: $("#f-date"), dateLabel: $("#f-date-label"),
    repeat: $("#f-repeat"), repeatWrap: $("#f-repeat-wrap"), error: $("#f-error"), quick: $("#f-quick"),
    del: $("#f-delete"), submit: $("#f-submit"),
  };

  function setDrawerKind(kind, keepCategory) {
    drawer.kind = kind;
    drawer.el.dataset.kind = kind;
    $$("#f-kind button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.kind === kind));
    const options = CATEGORIES[kind];
    if (keepCategory && options.includes(keepCategory)) drawer.category = keepCategory;
    else if (!options.includes(drawer.category)) drawer.category = options[0];
    f.category.innerHTML = options.map((c) => `
      <button type="button" class="chip-opt" role="radio" data-category="${esc(c)}" style="--c:${catColor(c)}"
              aria-checked="${c === drawer.category}">${esc(c)}</button>`).join("");
  }

  f.category.addEventListener("click", (e) => {
    const chip = e.target.closest("[data-category]");
    if (!chip) return;
    drawer.category = chip.dataset.category;
    $$("[data-category]", f.category).forEach((b) => b.setAttribute("aria-checked", b === chip));
  });

  function openDrawer(mode, item = null) {
    drawer.mode = mode;
    drawer.item = item;
    drawer.lastFocus = document.activeElement;
    const isRec = mode === "rec";

    f.title.textContent = item ? (isRec ? "Edit recurring" : "Edit transaction") : (isRec ? "New recurring" : "New transaction");
    f.noteLabel.textContent = isRec ? "Name" : "Description";
    f.note.placeholder = isRec ? "e.g. Rent, Netflix, Paycheck" : "e.g. Trader Joe's";
    f.dateLabel.textContent = isRec ? "Next date" : "Date";
    if (isRec) f.date.removeAttribute("max"); else f.date.max = TODAY;
    f.repeatWrap.hidden = isRec || !!item;
    $("#f-quick-wrap").hidden = isRec || !!item;
    f.quick.value = "";
    f.repeat.checked = false;
    f.del.hidden = !item;
    f.del.classList.remove("armed");
    f.del.textContent = "Delete";
    f.error.hidden = true;

    drawer.category = null;
    setDrawerKind(item ? item.kind : "expense", item && item.category);
    f.amount.value = item ? item.amount.toFixed(2) : "";
    f.note.value = item ? item.note : "";
    f.date.value = item ? (isRec ? item.next_date : item.date) : TODAY;
    f.submit.textContent = item ? "Save changes" : (isRec ? "Add recurring" : "Add transaction");

    drawer.el.hidden = false;
    drawer.backdrop.hidden = false;
    document.body.style.overflow = "hidden";
    requestAnimationFrame(() => (item || isRec ? f.amount : f.quick).focus());
  }

  // Typing a sentence in the quick-add line fills in the form as you go
  f.quick.addEventListener("input", async () => {
    const q = parseQuick(f.quick.value);
    if (q.amount) f.amount.value = q.amount.toFixed(2);
    f.note.value = q.note;
    f.date.value = q.date;
    const category = q.category || (q.note ? await suggestCategory(q.note, q.kind) : null);
    setDrawerKind(q.kind, category || undefined);
  });
  f.quick.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); drawer.form.requestSubmit(); }
  });

  function closeDrawer() {
    drawer.el.hidden = true;
    drawer.backdrop.hidden = true;
    document.body.style.overflow = "";
    if (drawer.lastFocus) drawer.lastFocus.focus();
  }

  $("#f-kind").addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (btn) setDrawerKind(btn.dataset.kind);
  });

  f.amount.addEventListener("input", () => {
    let v = f.amount.value.replace(/[^\d.]/g, "");
    const [whole, ...rest] = v.split(".");
    if (rest.length) v = `${whole}.${rest.join("").slice(0, 2)}`;
    f.amount.value = v;
  });

  drawer.form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const isRec = drawer.mode === "rec";
    const payload = {
      kind: drawer.kind,
      amount: f.amount.value,
      category: drawer.category,
      note: f.note.value,
      date: f.date.value,
    };
    if (!isRec && f.repeat.checked) payload.repeat = true;
    if (!(parseFloat(payload.amount) > 0)) return showError("Enter an amount greater than $0.", f.amount);
    if (isRec && !payload.note.trim()) return showError("Give it a name, like “Rent” or “Paycheck”.", f.note);

    const base = isRec ? "/api/recurring" : "/api/transactions";
    const url = drawer.item ? `${base}/${drawer.item.id}` : base;
    f.submit.disabled = true;
    try {
      const saved = await api(url, { method: drawer.item ? "PATCH" : "POST", body: JSON.stringify(payload) });
      closeDrawer();
      if (saved.learned) toast(`Saved. “${saved.learned}” will go to ${saved.category} from now on.`);
      else toast(drawer.item ? "Changes saved" : `${isRec ? "Recurring item" : drawer.kind === "income" ? "Income" : "Expense"} added`);
      refresh();
    } catch (err) {
      showError(err.message);
    } finally {
      f.submit.disabled = false;
    }
  });

  function showError(msg, focusEl) {
    f.error.textContent = msg;
    f.error.hidden = false;
    if (focusEl) focusEl.focus();
  }

  f.del.addEventListener("click", async () => {
    if (!f.del.classList.contains("armed")) {
      f.del.classList.add("armed");
      f.del.textContent = "Confirm delete";
      return;
    }
    const isRec = drawer.mode === "rec";
    f.del.disabled = true;
    try {
      await api(`/api/${isRec ? "recurring" : "transactions"}/${drawer.item.id}`, { method: "DELETE" });
      closeDrawer();
      toast(isRec ? "Recurring item deleted (past entries kept)" : "Transaction deleted");
      refresh();
    } catch (err) {
      showError(err.message);
    } finally {
      f.del.disabled = false;
    }
  });

  drawer.backdrop.addEventListener("click", closeDrawer);

  // =========================================================================
  // Global actions + keyboard
  // =========================================================================

  document.addEventListener("click", async (e) => {
    const row = e.target.closest("[data-txn]");
    if (row) { openDrawer("txn", txnCache.get(Number(row.dataset.txn))); return; }

    const action = e.target.closest("[data-action]");
    if (!action) return;
    switch (action.dataset.action) {
      case "new-txn": openDrawer("txn"); break;
      case "new-rec": openDrawer("rec"); break;
      case "close": closeDrawer(); break;
      case "theme": cycleTheme(); break;
      case "palette": openPalette(); break;
      case "new-rule": openRule(); break;
      case "close-rule": closeRule(); break;
      case "import-cancel": resetImport(); break;
      case "backup-now": backupNow(); break;
      case "copy-folder":
        navigator.clipboard.writeText($("#set-folder").textContent).then(() => toast("Path copied"));
        break;
      case "demo":
        action.disabled = true;
        try {
          await api("/api/demo", { method: "POST" });
          toast("Sample data loaded");
          refresh();
        } catch (err) { toast(err.message); action.disabled = false; }
        break;
      case "remove-demo":
        action.disabled = true;
        try {
          await api("/api/demo", { method: "DELETE" });
          toast("Sample data removed");
          refresh();
        } catch (err) { toast(err.message); action.disabled = false; }
        break;
    }
  });

  const GO = { o: "overview", a: "activity", i: "import", b: "budgets", r: "recurring", s: "settings" };
  let gPressed = 0;

  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      palette.el.hidden ? openPalette() : closePalette();
      return;
    }
    if (e.key === "Escape") {
      if (!palette.el.hidden) return closePalette();
      if (!rule.el.hidden) return closeRule();
      if (!drawer.el.hidden) return closeDrawer();
    }
    const typing = e.target.closest("input, select, textarea");
    const overlay = !drawer.el.hidden || !rule.el.hidden || !palette.el.hidden;
    if (typing || e.metaKey || e.ctrlKey || e.altKey || overlay) return;
    const key = e.key.toLowerCase();
    if (Date.now() - gPressed < 1200 && GO[key]) { location.hash = GO[key]; gPressed = 0; return; }
    if (key === "g") { gPressed = Date.now(); return; }
    if (key === "n") { e.preventDefault(); openDrawer("txn"); }
    if (key === "i") { e.preventDefault(); location.hash = "import"; }
    if (key === "/") { e.preventDefault(); location.hash = "activity"; setTimeout(() => $("#act-q").focus(), 0); }
  });

  // =========================================================================
  // Quick add — "12.50 lunch dining yesterday" → a transaction
  // =========================================================================

  const WEEKDAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
  const MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];
  const INCOME_WORDS = new Set(["income", "paycheck", "paid", "salary", "refund", "refunded", "received", "earned", "dividend", "interest", "reimbursement", "bonus"]);
  const ALIASES = {
    Dining: ["lunch", "dinner", "breakfast", "brunch", "coffee", "food", "restaurant", "drinks", "takeout", "snack"],
    Groceries: ["grocery", "groceries", "supermarket"],
    Transport: ["gas", "uber", "lyft", "taxi", "cab", "bus", "train", "subway", "parking", "fuel", "toll"],
    Housing: ["rent", "mortgage"],
    Bills: ["bill", "bills", "phone", "internet", "electric", "electricity", "water", "utilities", "insurance"],
    Shopping: ["clothes", "shoes", "amazon", "gift"],
    Entertainment: ["movie", "movies", "concert", "netflix", "spotify", "game", "games", "tickets"],
    Health: ["doctor", "pharmacy", "medicine", "gym", "dentist"],
    Travel: ["flight", "hotel", "airbnb", "trip"],
    Salary: ["paycheck", "salary", "payroll"],
    Freelance: ["invoice", "client", "freelance"],
    Investments: ["dividend", "interest"],
  };

  const isoDate = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

  function parseQuick(text) {
    const today = parseDate(TODAY);
    let tokens = text.trim().split(/\s+/).filter(Boolean);
    let amount = null, kind = "expense", category = null, date = new Date(today);
    const used = new Set();

    tokens.forEach((t, i) => {
      if (amount != null) return;
      const m = t.match(/^([+-]?)\$?(\d+(?:[.,]\d{1,2})?)$/);
      if (m) { amount = parseFloat(m[2].replace(",", ".")); if (m[1] === "+") kind = "income"; used.add(i); }
    });

    const lower = tokens.map((t) => t.toLowerCase().replace(/[.,!]$/, ""));
    lower.forEach((t, i) => {
      if (used.has(i)) return;
      if (t === "today") used.add(i);
      else if (t === "yesterday") { date.setDate(date.getDate() - 1); used.add(i); }
      else if (WEEKDAYS.some((w) => w.startsWith(t) && t.length >= 3)) {
        const target = WEEKDAYS.findIndex((w) => w.startsWith(t));
        let back = (today.getDay() - target + 7) % 7;
        if (lower[i - 1] === "last") { back = back || 7; used.add(i - 1); }
        date = new Date(today); date.setDate(date.getDate() - back); used.add(i);
      } else if (/^\d+$/.test(t) && lower[i + 1] === "days" && lower[i + 2] === "ago") {
        date = new Date(today); date.setDate(date.getDate() - Number(t)); used.add(i).add(i + 1).add(i + 2);
      } else if (/^\d{1,2}\/\d{1,2}(?:\/\d{2,4})?$/.test(t)) {
        const [mo, da, yr] = t.split("/").map(Number);
        date = new Date(yr ? (yr < 100 ? 2000 + yr : yr) : today.getFullYear(), mo - 1, da);
        if (!yr && date > today) date.setFullYear(date.getFullYear() - 1);
        used.add(i);
      } else if (MONTHS.includes(t.slice(0, 3)) && t.length >= 3 && /^\d{1,2}$/.test(lower[i + 1] || "")) {
        date = new Date(today.getFullYear(), MONTHS.indexOf(t.slice(0, 3)), Number(lower[i + 1]));
        if (date > today) date.setFullYear(date.getFullYear() - 1);
        used.add(i).add(i + 1);
      }
    });

    if (lower.some((t, i) => !used.has(i) && INCOME_WORDS.has(t))) kind = "income";

    // An exact category name is consumed; an alias word stays in the description
    const names = CATEGORIES[kind];
    lower.forEach((t, i) => {
      if (used.has(i) || category) return;
      const exact = names.find((c) => c.toLowerCase() === t);
      if (exact) { category = exact; used.add(i); }
    });
    if (!category) {
      for (const [cat, words] of Object.entries(ALIASES)) {
        if (names.includes(cat) && lower.some((t, i) => !used.has(i) && words.includes(t))) { category = cat; break; }
      }
    }

    const rest = tokens.filter((_, i) => !used.has(i)).join(" ").replace(/^(?:on|for|at)\s+/i, "");
    const note = rest ? rest[0].toUpperCase() + rest.slice(1) : "";
    if (date > today) date = new Date(today);
    return { amount, kind, category, note, date: isoDate(date) };
  }

  const suggestCache = new Map();
  async function suggestCategory(text, kind) {
    const key = `${kind}|${text.toLowerCase()}`;
    if (!suggestCache.has(key)) {
      suggestCache.set(key, api(`/api/suggest?kind=${kind}&q=${encodeURIComponent(text)}`)
        .then((r) => (r.via ? r.category : null)).catch(() => null));
    }
    return suggestCache.get(key);
  }

  async function quickAdd(q) {
    const category = q.category || (q.note && await suggestCategory(q.note, q.kind)) || "Other";
    const payload = { kind: q.kind, amount: q.amount.toFixed(2), category, note: q.note, date: q.date };
    try {
      const t = await api("/api/transactions", { method: "POST", body: JSON.stringify(payload) });
      toast(`${q.kind === "income" ? "Income" : "Expense"} of ${usd.format(q.amount)} added to ${category}`, {
        label: "Undo",
        run: async () => { await api(`/api/transactions/${t.id}`, { method: "DELETE" }); toast("Removed"); refresh(); },
      });
      refresh();
    } catch (err) { toast(err.message); }
  }

  // =========================================================================
  // Command palette (⌘K)
  // =========================================================================

  const palette = { el: $("#palette"), backdrop: $("#palette-backdrop"), input: $("#palette-q"), list: $("#palette-list"), items: [], index: 0, lastFocus: null, searchId: 0 };

  const COMMANDS = [
    { label: "New transaction", hint: "N", run: () => openDrawer("txn") },
    { label: "Import a statement", hint: "I", run: () => { location.hash = "import"; setTimeout(() => $("#imp-file").click(), 50); } },
    { label: "Go to Overview", hint: "G O", run: () => { location.hash = "overview"; } },
    { label: "Go to Activity", hint: "G A", run: () => { location.hash = "activity"; } },
    { label: "Go to Import & rules", hint: "G I", run: () => { location.hash = "import"; } },
    { label: "Go to Budgets", hint: "G B", run: () => { location.hash = "budgets"; } },
    { label: "Go to Recurring", hint: "G R", run: () => { location.hash = "recurring"; } },
    { label: "Go to Settings & backups", hint: "G S", run: () => { location.hash = "settings"; } },
    { label: "New recurring bill or paycheck", run: () => openDrawer("rec") },
    { label: "New category rule", run: () => openRule() },
    { label: "Back up now", run: () => backupNow() },
    { label: "Export all transactions (CSV)", run: () => { location.href = "/export.csv"; } },
    { label: "Switch theme", run: () => cycleTheme() },
  ];

  function openPalette() {
    palette.lastFocus = document.activeElement;
    palette.el.hidden = false;
    palette.backdrop.hidden = false;
    palette.input.value = "";
    renderPalette();
    palette.input.focus();
  }

  function closePalette() {
    palette.el.hidden = true;
    palette.backdrop.hidden = true;
    if (palette.lastFocus && document.contains(palette.lastFocus)) palette.lastFocus.focus();
  }

  async function renderPalette() {
    const q = palette.input.value.trim();
    const items = [];
    const quick = q ? parseQuick(q) : null;
    if (quick && quick.amount) {
      const cat = quick.category || (quick.note && await suggestCategory(quick.note, quick.kind)) || "Other";
      if (palette.input.value.trim() !== q) return; // typed more while we waited
      items.push({
        kind: "quick",
        html: `<span class="pal-quick ${quick.kind}">${quick.kind === "income" ? "+" : "−"}${usd.format(quick.amount)}</span>
               <span class="pal-main">${esc(quick.note || cat)}</span>
               <span class="pal-meta"><span class="cat-swatch" style="background:${catColor(cat)}"></span>${esc(cat)} · ${esc(relDay(quick.date) || fmtDate(quick.date, { month: "short", day: "numeric" }))}</span>`,
        hint: "Enter to add",
        run: () => quickAdd({ ...quick, category: cat }),
      });
    }
    const needle = q.toLowerCase();
    COMMANDS.filter((c) => !needle || c.label.toLowerCase().includes(needle)).forEach((c) =>
      items.push({ kind: "cmd", html: `<span class="pal-main">${esc(c.label)}</span>`, hint: c.hint || "", run: c.run }));
    if (q.length >= 2 && !(quick && quick.amount)) {
      items.push({
        kind: "search", html: `<span class="pal-main">Search activity for “${esc(q)}”</span>`, hint: "",
        run: () => { location.hash = "activity"; $("#act-q").value = q; act.q = q; loadActivity(); },
      });
    }
    palette.items = items;
    palette.index = 0;
    paintPalette();

    // Matching transactions, fetched after the instant results
    if (q.length >= 2 && !(quick && quick.amount)) {
      const id = ++palette.searchId;
      try {
        const res = await api(`/api/transactions?q=${encodeURIComponent(q)}&limit=6`);
        if (id !== palette.searchId || palette.el.hidden) return;
        res.transactions.forEach((t) => {
          txnCache.set(t.id, t);
          palette.items.push({
            kind: "txn",
            html: `<span class="pal-main">${esc(t.note || t.category)}</span>
                   <span class="pal-meta">${esc(t.category)} · ${fmtDate(t.date, { month: "short", day: "numeric", year: "numeric" })}</span>
                   <span class="pal-amt num ${t.kind === "income" ? "pos" : ""}">${t.kind === "income" ? "+" : "−"}${usd.format(t.amount)}</span>`,
            hint: "",
            run: () => openDrawer("txn", t),
          });
        });
        paintPalette();
      } catch (_) { /* search is best-effort */ }
    }
  }

  function paintPalette() {
    palette.list.innerHTML = palette.items.length
      ? palette.items.map((it, i) => `
          <li role="option" class="pal-item pal-${it.kind}" data-index="${i}" aria-selected="${i === palette.index}">
            ${it.html}${it.hint ? `<kbd>${esc(it.hint)}</kbd>` : ""}
          </li>`).join("")
      : `<li class="pal-empty">No matches. Try “12.50 lunch yesterday” to add a transaction.</li>`;
    const sel = palette.list.querySelector('[aria-selected="true"]');
    if (sel) sel.scrollIntoView({ block: "nearest" });
  }

  function runPaletteItem(i) {
    const it = palette.items[i];
    if (!it) return;
    closePalette();
    it.run();
  }

  palette.input.addEventListener("input", renderPalette);
  palette.input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); palette.index = Math.min(palette.index + 1, palette.items.length - 1); paintPalette(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); palette.index = Math.max(palette.index - 1, 0); paintPalette(); }
    else if (e.key === "Enter") { e.preventDefault(); runPaletteItem(palette.index); }
  });
  palette.list.addEventListener("click", (e) => {
    const li = e.target.closest("[data-index]");
    if (li) runPaletteItem(Number(li.dataset.index));
  });
  palette.list.addEventListener("mousemove", (e) => {
    const li = e.target.closest("[data-index]");
    if (li && Number(li.dataset.index) !== palette.index) { palette.index = Number(li.dataset.index); paintPalette(); }
  });
  palette.backdrop.addEventListener("click", closePalette);

  // =========================================================================
  // Import
  // =========================================================================

  const imp = { data: null, items: [], filter: "all" };
  const STATUS_LABEL = {
    imported: "Already imported", possible: "Possible duplicate", transfer: "Looks like a transfer",
  };

  async function loadImport() {
    loadRules();
  }

  function resetImport() {
    imp.data = null;
    imp.items = [];
    $("#imp-file").value = "";
    $("#imp-mapping").hidden = true;
    $("#imp-review").hidden = true;
    $("#imp-drop").hidden = false;
  }

  async function uploadStatement(file) {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    $("#imp-drop").classList.add("busy");
    try {
      imp.data = await api("/api/import/parse", { method: "POST", body: form });
      imp.items = imp.data.items;
      imp.filter = "all";
      $("#imp-drop").hidden = true;
      renderMapping();
      renderImportRows();
      $("#imp-review").hidden = false;
      $("#imp-review").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      toast(err.message);
    } finally {
      $("#imp-drop").classList.remove("busy");
      $("#imp-file").value = "";
    }
  }

  function renderMapping() {
    const d = imp.data;
    const csv = d.format === "csv";
    $("#imp-mapping").hidden = !csv;
    $("#imp-filename").textContent = d.filename;
    if (!csv) return;
    $("#imp-profile").textContent = d.profile ? `· remembered from last time` : "";
    const sample = (i) => (d.rows.find((r) => r[i] && r[i].trim()) || [])[i] || "";
    const options = `<option value="">—</option>` + d.headers.map((h, i) =>
      `<option value="${i}">${esc(h)}${sample(i) ? ` · ${esc(sample(i).slice(0, 24))}` : ""}</option>`).join("");
    $$("#imp-mapping select[data-map]").forEach((sel) => {
      const key = sel.dataset.map;
      if (key !== "date_format") sel.innerHTML = options;
      const v = d.mapping[key];
      sel.value = v == null ? "" : String(v);
    });
    $('#imp-mapping [data-map="invert"]').checked = !!d.mapping.invert;
    const split = d.mapping.amount == null;
    $('#imp-mapping [data-map="amount"]').closest(".field").classList.toggle("dim", split);
    $$('#imp-mapping [data-map="debit"], #imp-mapping [data-map="credit"]').forEach((el) => el.closest(".field").classList.toggle("dim", !split));
  }

  $("#imp-mapping").addEventListener("change", async (e) => {
    const el = e.target.closest("[data-map]");
    if (!el || !imp.data) return;
    const key = el.dataset.map;
    const m = imp.data.mapping;
    if (key === "invert") m.invert = el.checked;
    else if (key === "date_format") m.date_format = el.value || null;
    else m[key] = el.value === "" ? null : Number(el.value);
    if (key === "amount" && m.amount != null) { m.debit = null; m.credit = null; }
    if ((key === "debit" || key === "credit") && el.value !== "") m.amount = null;
    if (key === "date") m.date_format = null;
    try {
      const res = await api("/api/import/preview", {
        method: "POST", body: JSON.stringify({ headers: imp.data.headers, rows: imp.data.rows, mapping: m }),
      });
      imp.data.mapping = res.mapping;
      imp.items = res.items;
      renderMapping();
      renderImportRows();
    } catch (err) { toast(err.message); }
  });

  function importCategoryOptions(kind, selected) {
    return CATEGORIES[kind].map((c) => `<option ${c === selected ? "selected" : ""}>${esc(c)}</option>`).join("");
  }

  function visibleImportItems() {
    return imp.items.filter((it) => {
      if (imp.filter === "new") return it.status === "new";
      if (imp.filter === "other") return !it.error && it.category === "Other";
      if (imp.filter === "skip") return !it.include;
      return true;
    });
  }

  function renderImportRows() {
    const rows = visibleImportItems();
    $("#imp-rows").innerHTML = rows.map((it) => {
      const i = imp.items.indexOf(it);
      if (it.error) {
        return `<tr class="imp-error"><td class="c-check"></td><td colspan="4"><span class="badge badge-neg">${esc(it.error)}</span> <span class="muted">${esc(it.raw || "(empty row)")}</span></td></tr>`;
      }
      const badge = STATUS_LABEL[it.status] ? `<span class="badge badge-${it.status}">${STATUS_LABEL[it.status]}</span>` : "";
      const learnt = it.via === "rule" ? `<span class="badge badge-rule" title="Matched one of your rules">Rule</span>` : "";
      return `
        <tr class="${it.include ? "" : "excluded"}" data-i="${i}">
          <td class="c-check"><input type="checkbox" data-field="include" ${it.include ? "checked" : ""} aria-label="Include"></td>
          <td class="c-date num">${fmtDate(it.date, { month: "short", day: "numeric" })}<br><span class="muted">${parseDate(it.date).getFullYear()}</span></td>
          <td class="c-desc">
            <input class="cell-input" data-field="note" value="${esc(it.note)}" aria-label="Description">
            <span class="raw" title="${esc(it.raw)}">${esc(it.raw)}</span> ${badge}${learnt}
          </td>
          <td class="c-cat">
            <span class="cat-select" style="--c:${catColor(it.category)}">
              <select data-field="category" aria-label="Category">${importCategoryOptions(it.kind, it.category)}</select>
            </span>
          </td>
          <td class="c-amt num ${it.kind === "income" ? "pos" : ""}">${it.kind === "income" ? "+" : "−"}${usd.format(it.amount)}</td>
        </tr>`;
    }).join("") || `<tr><td colspan="5" class="muted imp-none">Nothing in this filter.</td></tr>`;
    renderImportSummary();
  }

  function renderImportSummary() {
    const chosen = imp.items.filter((it) => it.include);
    const out = chosen.filter((it) => it.kind === "expense").reduce((s, it) => s + it.amount, 0);
    const inc = chosen.filter((it) => it.kind === "income").reduce((s, it) => s + it.amount, 0);
    const count = (st) => imp.items.filter((it) => it.status === st).length;
    const parts = [`<b>${chosen.length}</b> selected`];
    if (count("imported")) parts.push(`${count("imported")} already imported`);
    if (count("possible")) parts.push(`${count("possible")} possible duplicates`);
    if (count("transfer")) parts.push(`${count("transfer")} transfers`);
    parts.push(`Out <b>${money(out)}</b>`, `In <b class="pos">${money(inc)}</b>`);
    $("#imp-summary").innerHTML = parts.map((p) => `<span>${p}</span>`).join("");
    const btn = $("#imp-commit");
    btn.textContent = chosen.length ? `Import ${chosen.length} transaction${chosen.length === 1 ? "" : "s"}` : "Nothing selected";
    btn.disabled = !chosen.length;
    const selectable = imp.items.filter((it) => !it.error);
    $("#imp-all").checked = selectable.length > 0 && selectable.every((it) => it.include);
  }

  $("#imp-rows").addEventListener("change", (e) => {
    const tr = e.target.closest("tr[data-i]");
    const field = e.target.dataset.field;
    if (!tr || !field) return;
    const it = imp.items[Number(tr.dataset.i)];
    if (field === "include") {
      it.include = e.target.checked;
      tr.classList.toggle("excluded", !it.include);
      renderImportSummary();
    } else if (field === "category") {
      it.category = e.target.value;
      // Same merchant elsewhere in this file? Give it the same category.
      let others = 0;
      imp.items.forEach((o) => {
        if (o !== it && !o.error && o.kind === it.kind && o.note === it.note && o.category === o.suggested) {
          o.category = it.category;
          others++;
        }
      });
      if (others) toast(`Also set ${others} other “${it.note}” row${others === 1 ? "" : "s"} to ${it.category}`);
      renderImportRows();
    } else if (field === "note") {
      it.note = e.target.value.trim();
      it.renamed = true;
    }
  });

  $("#imp-all").addEventListener("change", (e) => {
    imp.items.forEach((it) => { if (!it.error) it.include = e.target.checked; });
    renderImportRows();
  });

  $("#imp-filter").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-filter]");
    if (!btn) return;
    imp.filter = btn.dataset.filter;
    $$("#imp-filter button").forEach((b) => b.setAttribute("aria-pressed", b === btn));
    renderImportRows();
  });

  $("#imp-commit").addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    try {
      const d = imp.data;
      const res = await api("/api/import/commit", {
        method: "POST",
        body: JSON.stringify({
          items: imp.items.filter((it) => !it.error),
          mapping: d.format === "csv" ? d.mapping : null,
          signature: d.signature || null,
          filename: d.filename,
        }),
      });
      let msg = `Imported ${res.imported} transaction${res.imported === 1 ? "" : "s"}`;
      if (res.learned) msg += ` · learned ${res.learned} new rule${res.learned === 1 ? "" : "s"}`;
      if (res.skipped) msg += ` · ${res.skipped} skipped`;
      resetImport();
      toast(msg);
      loadRules();
      act.source = "import";
      location.hash = "activity";
    } catch (err) {
      toast(err.message);
      btn.disabled = false;
    }
  });

  $("#imp-file").addEventListener("change", (e) => uploadStatement(e.target.files[0]));
  const drop = $("#imp-drop");
  ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", (e) => uploadStatement(e.dataTransfer.files[0]));
  // Dropping a file anywhere on the page goes to the importer
  window.addEventListener("dragover", (e) => { if ([...e.dataTransfer.types].includes("Files")) e.preventDefault(); });
  window.addEventListener("drop", (e) => {
    if (e.target.closest("#imp-drop, #restore-file")) return;
    if (e.dataTransfer.files.length) { e.preventDefault(); location.hash = "import"; uploadStatement(e.dataTransfer.files[0]); }
  });

  // =========================================================================
  // Rules
  // =========================================================================

  const rule = { el: $("#rule-drawer"), backdrop: $("#rule-backdrop"), item: null, kind: "expense", category: null, cache: new Map() };

  async function loadRules() {
    let data;
    try { data = await api("/api/rules"); } catch (e) { toast(e.message); return; }
    $("#rule-empty").hidden = data.rules.length > 0;
    $("#rule-list").innerHTML = data.rules.map((r) => {
      rule.cache.set(r.id, r);
      return `
        <li>
          <button type="button" class="rule-row" data-rule="${r.id}">
            <span class="rule-pattern">“${esc(r.pattern)}”</span>
            <span class="rule-arrow">→</span>
            <span class="rule-cat"><span class="cat-swatch" style="background:${catColor(r.category)}"></span>${esc(r.category)}${r.rename ? ` <span class="muted">as “${esc(r.rename)}”</span>` : ""}</span>
            <span class="muted rule-kind">${r.kind === "income" ? "Income" : "Expense"}</span>
          </button>
        </li>`;
    }).join("");
  }

  $("#rule-list").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-rule]");
    if (btn) openRule(rule.cache.get(Number(btn.dataset.rule)));
  });

  function setRuleKind(kind, keep) {
    rule.kind = kind;
    $$("#r-kind button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.kind === kind));
    const options = CATEGORIES[kind];
    rule.category = keep && options.includes(keep) ? keep : (options.includes(rule.category) ? rule.category : options[0]);
    $("#r-category").innerHTML = options.map((c) => `
      <button type="button" class="chip-opt" role="radio" data-category="${esc(c)}" style="--c:${catColor(c)}"
              aria-checked="${c === rule.category}">${esc(c)}</button>`).join("");
  }

  function openRule(item = null) {
    rule.item = item;
    $("#rule-title").textContent = item ? "Edit rule" : "New rule";
    $("#r-pattern").value = item ? item.pattern : "";
    $("#r-rename").value = item && item.rename ? item.rename : "";
    $("#r-error").hidden = true;
    $("#r-delete").hidden = $("#r-apply").hidden = !item;
    $("#r-delete").classList.remove("armed");
    $("#r-delete").textContent = "Delete";
    rule.category = null;
    setRuleKind(item ? item.kind : "expense", item && item.category);
    rule.el.hidden = rule.backdrop.hidden = false;
    $("#r-pattern").focus();
  }

  function closeRule() { rule.el.hidden = rule.backdrop.hidden = true; }

  $("#r-kind").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) setRuleKind(b.dataset.kind); });
  $("#r-category").addEventListener("click", (e) => {
    const chip = e.target.closest("[data-category]");
    if (!chip) return;
    rule.category = chip.dataset.category;
    $$("#r-category [data-category]").forEach((b) => b.setAttribute("aria-checked", b === chip));
  });
  rule.backdrop.addEventListener("click", closeRule);

  $("#rule-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = { pattern: $("#r-pattern").value, kind: rule.kind, category: rule.category, rename: $("#r-rename").value };
    try {
      await api(rule.item ? `/api/rules/${rule.item.id}` : "/api/rules", { method: rule.item ? "PATCH" : "POST", body: JSON.stringify(payload) });
      closeRule();
      toast("Rule saved");
      loadRules();
    } catch (err) { $("#r-error").textContent = err.message; $("#r-error").hidden = false; }
  });

  $("#r-delete").addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    if (!btn.classList.contains("armed")) { btn.classList.add("armed"); btn.textContent = "Confirm delete"; return; }
    try {
      await api(`/api/rules/${rule.item.id}`, { method: "DELETE" });
      closeRule();
      toast("Rule deleted");
      loadRules();
    } catch (err) { toast(err.message); }
  });

  $("#r-apply").addEventListener("click", async () => {
    try {
      const res = await api(`/api/rules/${rule.item.id}/apply`, { method: "POST" });
      toast(res.changed ? `Re-filed ${res.changed} past transaction${res.changed === 1 ? "" : "s"}` : "No past transactions needed changing");
    } catch (err) { toast(err.message); }
  });

  // =========================================================================
  // Settings & backups
  // =========================================================================

  const fmtBytes = (n) => n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`;

  async function loadSettings() {
    let d;
    try { d = await api("/api/data"); } catch (e) { toast(e.message); return; }
    $("#set-count").textContent = d.counts.transactions.toLocaleString();
    $("#set-count-sub").textContent = d.first_date ? `since ${fmtDate(d.first_date, { month: "short", year: "numeric" })} · ${d.counts.imported.toLocaleString()} imported` : "";
    $("#set-rules").textContent = d.counts.rules.toLocaleString();
    $("#set-size").textContent = fmtBytes(d.db_size);
    $("#set-folder").textContent = d.folder;
    $("#set-demo").hidden = !d.counts.demo;
    $("#set-demo-count").textContent = `${d.counts.demo.toLocaleString()} sample transactions are mixed in with your data.`;
    $("#backup-list").innerHTML = d.backups.map((b) => `
      <li>
        <span><b class="num">${fmtDate(b.created.slice(0, 10), { weekday: "short", month: "short", day: "numeric", year: "numeric" })}</b>
          <span class="muted num">${b.created.slice(11)} · ${fmtBytes(b.size)}${/before-(import|restore)/.test(b.name) ? ` · before ${b.name.match(/before-(\w+)/)[1]}` : ""}</span></span>
        <span class="head-actions">
          <a class="btn btn-outline btn-sm" href="/api/backups/${encodeURIComponent(b.name)}">Download</a>
          <button class="btn btn-outline btn-sm" type="button" data-restore="${esc(b.name)}">Restore</button>
        </span>
      </li>`).join("") || `<li class="muted">No backups yet.</li>`;
  }

  async function backupNow() {
    try {
      await api("/api/backups", { method: "POST" });
      toast("Backup saved");
      if (currentView === "settings") loadSettings();
    } catch (err) { toast(err.message); }
  }

  $("#backup-list").addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-restore]");
    if (!btn) return;
    if (!btn.classList.contains("armed")) {
      $$("#backup-list .armed").forEach((b) => { b.classList.remove("armed", "btn-danger"); b.textContent = "Restore"; });
      btn.classList.add("armed", "btn-danger");
      btn.textContent = "Replace current data?";
      return;
    }
    btn.disabled = true;
    try {
      await api(`/api/backups/${encodeURIComponent(btn.dataset.restore)}/restore`, { method: "POST" });
      toast("Restored. Your previous data was backed up first.");
      loadSettings();
    } catch (err) { toast(err.message); btn.disabled = false; }
  });

  $("#restore-file").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    try {
      await api("/api/restore", { method: "POST", body: form });
      toast("Restored. Your previous data was backed up first.");
      loadSettings();
    } catch (err) { toast(err.message); }
    e.target.value = "";
  });

  // --- Theme ----------------------------------------------------------------

  const THEMES = ["system", "light", "dark"];
  function applyThemeLabel() {
    const t = document.documentElement.dataset.theme || "system";
    $("#theme-label").textContent = `Theme: ${t[0].toUpperCase()}${t.slice(1)}`;
  }
  function cycleTheme() {
    const current = document.documentElement.dataset.theme || "system";
    const next = THEMES[(THEMES.indexOf(current) + 1) % THEMES.length];
    if (next === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = next;
    try { next === "system" ? localStorage.removeItem("theme") : localStorage.setItem("theme", next); } catch (_) { /* storage unavailable */ }
    applyThemeLabel();
  }

  applyThemeLabel();
  route();
})();
