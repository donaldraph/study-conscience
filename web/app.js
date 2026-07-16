"use strict";

// API base is injected at deploy time into config.js as window.SC_API_BASE.
var API = (window.SC_API_BASE || "").replace(/\/?$/, "/");

var SEQ = ["--seq-0", "--seq-1", "--seq-2", "--seq-3", "--seq-4", "--seq-5", "--seq-6"];

function num(x) { var n = parseFloat(x); return isNaN(n) ? 0 : n; }
function el(id) { return document.getElementById(id); }
function show(id) { var e = el(id); if (e) e.hidden = false; }

function fetchJSON(path) {
  return fetch(API + path).then(function (r) {
    if (!r.ok && r.status !== 404) throw new Error("HTTP " + r.status);
    return r.json();
  });
}

// ---- theme toggle -------------------------------------------------------
(function initTheme() {
  var btn = el("theme-toggle");
  btn.addEventListener("click", function () {
    var root = document.documentElement;
    var cur = root.getAttribute("data-theme");
    var dark = cur ? cur === "dark"
      : window.matchMedia("(prefers-color-scheme: dark)").matches;
    root.setAttribute("data-theme", dark ? "light" : "dark");
  });
})();

// ---- render helpers -----------------------------------------------------
function renderModelBadge(source) {
  var b = el("model-badge");
  if (!source) return;
  b.hidden = false;
  b.textContent = source;
  if (/stub/i.test(source)) b.classList.add("stub");
}

function renderTiles(days) {
  if (!days) return;
  var box = el("tiles");
  ["CKA", "CKS", "CKAD"].forEach(function (exam) {
    if (days[exam] == null) return;
    var t = document.createElement("div");
    t.className = "tile";
    t.innerHTML = '<div class="exam">' + exam + '</div>' +
      '<div class="days">' + num(days[exam]) + '</div>' +
      '<div class="unit">days to exam</div>';
    box.appendChild(t);
  });
  show("tiles");
}

function renderJudgment(brief) {
  el("brief-date").textContent = brief.SK ? "· " + brief.SK : "";
  el("judgment").textContent = brief.avoidance_judgment || "(no judgment yet)";
  show("judgment-card");
}

function rampColor(idx) {
  return getComputedStyle(document.documentElement).getPropertyValue(SEQ[idx]).trim();
}

function renderHeatmap(domains) {
  if (!domains || !domains.length) return;
  var cells = domains.map(function (d) {
    return {
      exam: d.exam, domain: d.domain,
      weight: num(d.weight), share: num(d.share), gap: num(d.gap),
      days: num(d.days_to_exam),
    };
  });
  var maxGap = Math.max.apply(null, cells.map(function (c) { return Math.max(c.gap, 0); }));
  if (maxGap <= 0) maxGap = 1;

  var byExam = {};
  cells.forEach(function (c) { (byExam[c.exam] = byExam[c.exam] || []).push(c); });

  var wrap = el("heatmap");
  ["CKA", "CKS", "CKAD"].forEach(function (exam) {
    var list = byExam[exam];
    if (!list) return;
    list.sort(function (a, b) { return b.gap - a.gap; });
    var row = document.createElement("div");
    row.className = "exam-row";
    var label = document.createElement("div");
    label.className = "exam-label";
    label.textContent = exam;
    row.appendChild(label);
    var cellsWrap = document.createElement("div");
    cellsWrap.className = "cells";

    list.forEach(function (c) {
      var intensity = Math.max(c.gap, 0) / maxGap;
      var idx = Math.min(SEQ.length - 1, Math.round(intensity * (SEQ.length - 1)));
      var cell = document.createElement("div");
      cell.className = "cell";
      cell.tabIndex = 0;
      cell.style.background = rampColor(idx);
      cell.style.color = idx >= 3 ? "#ffffff" : "#0b0b0b";
      cell.innerHTML = '<div class="d-name">' + c.domain + '</div>' +
        '<div class="d-gap">' + c.gap.toFixed(2) + '</div>';
      attachTip(cell, c);
      cellsWrap.appendChild(cell);
    });
    row.appendChild(cellsWrap);
    wrap.appendChild(row);
  });
  el("legend-ramp");
  show("heatmap-card");
}

function renderDrill(drill) {
  if (!drill) return;
  el("drill-min").textContent = drill.est_minutes ? "· " + drill.est_minutes + " min" : "";
  el("drill-title").textContent = drill.title || "";
  el("drill-task").textContent = drill.task || "";
  el("drill-manifest").textContent = drill.manifest || "";
  show("drill-card");
}

function renderDecay(list) {
  if (!list || !list.length) return;
  var ul = el("decay-list");
  list.forEach(function (s) {
    var li = document.createElement("li");
    var when = s.last_practised
      ? "last practised " + s.last_practised + " (" + num(s.days_since) + "d ago)"
      : "never practised";
    li.innerHTML = s.skill + ' <span class="when">— ' + when + "</span>";
    ul.appendChild(li);
  });
  show("decay-card");
}

// ---- trend (inline SVG line) --------------------------------------------
function renderTrend(briefs) {
  show("trend-card");
  var box = el("trend");
  var pts = (briefs || []).map(function (b) {
    var top = (b.top_avoided && b.top_avoided[0]) || null;
    return top ? { date: b.SK, gap: num(top.gap) } : null;
  }).filter(Boolean);
  pts.reverse(); // history comes newest-first; plot oldest -> newest

  if (pts.length < 2) {
    box.innerHTML = '<p class="trend-empty">One night of data so far. The trend line ' +
      'fills in as the agent runs on more nights.</p>';
    return;
  }

  var W = 860, H = 180, pad = 28;
  var maxGap = Math.max.apply(null, pts.map(function (p) { return p.gap; }));
  var x = function (i) { return pad + i * (W - 2 * pad) / (pts.length - 1); };
  var y = function (g) { return H - pad - (g / (maxGap || 1)) * (H - 2 * pad); };
  var line = pts.map(function (p, i) { return (i ? "L" : "M") + x(i) + " " + y(p.gap); }).join(" ");

  var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="top-avoided gap over time">';
  svg += '<line x1="' + pad + '" y1="' + (H - pad) + '" x2="' + (W - pad) + '" y2="' + (H - pad) +
    '" stroke="var(--baseline)" stroke-width="1"/>';
  svg += '<path d="' + line + '" fill="none" stroke="var(--accent)" stroke-width="2"/>';
  pts.forEach(function (p, i) {
    svg += '<circle cx="' + x(i) + '" cy="' + y(p.gap) + '" r="3.5" fill="var(--accent)"/>';
  });
  svg += "</svg>";
  box.innerHTML = svg;
}

// ---- tooltip ------------------------------------------------------------
function attachTip(node, c) {
  var tip = el("tooltip");
  function rows() {
    return '<div class="tt-row"><span class="tt-key">' + c.exam + " · " + c.domain + "</span></div>" +
      '<div class="tt-row"><span class="tt-key">exam weight</span><b>' + (c.weight * 100).toFixed(0) + "%</b></div>" +
      '<div class="tt-row"><span class="tt-key">my share</span><b>' + (c.share * 100).toFixed(1) + "%</b></div>" +
      '<div class="tt-row"><span class="tt-key">gap</span><b>' + c.gap.toFixed(2) + "</b></div>" +
      '<div class="tt-row"><span class="tt-key">days to exam</span><b>' + c.days + "</b></div>";
  }
  function move(e) {
    tip.hidden = false;
    tip.innerHTML = rows();
    var px = (e.clientX || 0) + 14, py = (e.clientY || 0) + 14;
    if (px + 250 > window.innerWidth) px = window.innerWidth - 250;
    tip.style.left = px + "px";
    tip.style.top = py + "px";
  }
  function hide() { tip.hidden = true; }
  node.addEventListener("mousemove", move);
  node.addEventListener("mouseleave", hide);
  node.addEventListener("focus", function () {
    var r = node.getBoundingClientRect();
    move({ clientX: r.left, clientY: r.bottom });
  });
  node.addEventListener("blur", hide);
}

// ---- boot ---------------------------------------------------------------
function boot() {
  if (!API) {
    el("status").textContent = "No API base configured.";
    return;
  }
  Promise.all([
    fetchJSON("brief").catch(function () { return {}; }),
    fetchJSON("briefs?limit=30").catch(function () { return { briefs: [] }; }),
  ]).then(function (res) {
    var brief = (res[0] && res[0].brief) || null;
    var briefs = (res[1] && res[1].briefs) || [];
    if (!brief) {
      el("status").textContent = "No brief yet. The agent writes one every night.";
      return;
    }
    el("status").hidden = true;
    renderModelBadge(brief.model_source);
    renderTiles(brief.days_to_exam);
    renderJudgment(brief);
    renderHeatmap(brief.domains);
    renderDrill(brief.drill);
    renderDecay(brief.decayed_skills);
    renderTrend(briefs);
    el("foot-note").textContent =
      "Read from the study cluster's API server audit log. Model: " +
      (brief.model_source || "unknown") + ".";
  }).catch(function (err) {
    el("status").textContent = "Could not load: " + err.message;
  });
}
boot();
