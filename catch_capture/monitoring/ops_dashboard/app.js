"use strict";

const SITES_ORDER = ["wanted", "jumpit", "jobkorea", "saramin", "dev"];

// 차단/레이트리밋 reason → 한글 라벨 (block_detect 의 R_* 와 1:1)
const BLOCK_LABEL = {
  rate_limited_429: "차단 의심 · 429 과다요청",
  forbidden_403: "차단 의심 · 403 거부",
  unavailable_503: "일시 차단 · 503",
  http_error: "HTTP 오류",
  captcha_or_block_page: "캡차/차단 페이지",
};
const blockLabel = (r) => (r ? (BLOCK_LABEL[r] || r) : "");

const PHASE_LABEL = {
  idle: "대기",
  crawling: "크롤링 중",
  aggregating: "통합 중",
  blog: "기술 블로그 수집",
  building: "대시보드 빌드",
  refreshing: "뷰어 갱신",
  waiting: "다음 주기 대기",
};

// 스텝퍼 정의: state.phase / cycle 데이터로 각 단계 상태를 도출
const STEPS = [
  { key: "crawling", name: "크롤", phases: ["crawling"] },
  { key: "aggregating", name: "통합", phases: ["aggregating"] },
  { key: "blog", name: "기술블로그", phases: ["blog"] },
  { key: "building", name: "대시보드", phases: ["building"] },
  { key: "refreshing", name: "뷰어", phases: ["refreshing"] },
  { key: "waiting", name: "대기", phases: ["waiting", "idle"] },
];

let nextRunAt = null; // Date | null
let lastState = null;

const $ = (id) => document.getElementById(id);

function fmtClock(d) {
  return d.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
function parseLocal(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  return isNaN(d.getTime()) ? null : d;
}
function secs(v) {
  return v == null ? "" : ` · ${v}s`;
}
function ago(iso) {
  const d = parseLocal(iso);
  if (!d) return "—";
  const s = Math.max(0, Math.round((Date.now() - d.getTime()) / 1000));
  if (s < 60) return `${s}초 전`;
  if (s < 3600) return `${Math.floor(s / 60)}분 전`;
  return `${Math.floor(s / 3600)}시간 전`;
}

async function fetchJSON(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}

// ---- 렌더 ----------------------------------------------------------------

function dur(sec) {
  if (sec == null) return "";
  if (sec < 60) return `${sec}초`;
  if (sec < 3600) return `${Math.round(sec / 60)}분`;
  return `${Math.round(sec / 360) / 10}시간`;
}

function renderDaemon(s) {
  const dot = $("liveDot");
  const pill = $("daemonPill");
  const d = s.daemon || {};
  // daemon_health: ok(가동중) | stalled(살아있지만 멈춤/지연) | stopped(중지)
  // 구버전 서버 호환: 필드 없으면 daemon_alive 로 폴백
  const health = s.daemon_health || (s.daemon_alive ? "ok" : "stopped");
  if (health === "ok") {
    dot.className = "dot on";
    pill.className = "pill pill-on";
    pill.textContent = `데몬 가동중 · PID ${s.daemon_pid}`;
    $("cfgSub").textContent = d.keyword
      ? `keyword=${d.keyword} · 사이트당 ${d.count} · 주기 ${Math.round((d.interval || 0) / 60)}분`
      : "";
  } else if (health === "stalled") {
    dot.className = "dot warn";
    pill.className = "pill pill-warn";
    const since = s.daemon_stale_sec != null ? ` · ${dur(s.daemon_stale_sec)}째 무응답` : "";
    pill.textContent = `데몬 응답 없음 (PID ${s.daemon_pid})${since}`;
    $("cfgSub").textContent = "살아있지만 진행이 멈춤 — 로그 확인 / 재시작 필요할 수 있음";
  } else {
    dot.className = "dot off";
    pill.className = "pill pill-off";
    pill.textContent = "데몬 중지됨";
    $("cfgSub").textContent = "python -m automation.auto_crawl start 으로 시작";
  }
  $("updated").textContent = s.updated_at ? `갱신 ${ago(s.updated_at)}` : "";
}

function renderPhase(s) {
  const phase = s.phase || "idle";
  const el = $("phaseLabel");
  el.textContent = PHASE_LABEL[phase] || phase;
  el.className = "hero-phase " + phase;

  const cyc = s.cycle || {};
  let sub = "";
  if (phase === "crawling") {
    const sites = cyc.sites || {};
    const done = Object.values(sites).filter((x) => x.status === "done" || x.status === "failed").length;
    const running = Object.entries(sites).find(([, v]) => v.status === "running");
    sub = running ? `${running[0]} 수집 중 · ${done}/${Object.keys(sites).length} 완료`
                  : `${done}/${Object.keys(sites).length} 사이트 완료`;
  } else if (phase === "waiting" && cyc.finished_at) {
    const el = cyc.total_elapsed != null ? `${cyc.total_elapsed}s · ` : "";
    sub = `직전 사이클 ${el}${cyc.new_data ? "새 데이터 반영" : "변경 없음"}`;
  } else if (s.last_error) {
    sub = `최근 오류: ${s.last_error.msg}`;
  }
  $("phaseSub").textContent = sub || "—";
}

function renderCountdown(s) {
  nextRunAt = parseLocal(s.next_run_at);
}
function tickCountdown() {
  const el = $("countdown");
  const phase = (lastState && lastState.phase) || "idle";
  if (phase !== "waiting" || !nextRunAt) {
    el.textContent = phase === "waiting" ? "—" : "진행 중";
    return;
  }
  let s = Math.round((nextRunAt.getTime() - Date.now()) / 1000);
  if (s <= 0) { el.textContent = "곧 시작"; return; }
  const h = Math.floor(s / 3600); s -= h * 3600;
  const m = Math.floor(s / 60); const sec = s - m * 60;
  const pad = (n) => String(n).padStart(2, "0");
  el.textContent = h > 0 ? `${h}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`;
}

function stepStateFor(step, s) {
  const phase = s.phase || "idle";
  const cyc = s.cycle || {};
  // 현재 진행 중인 단계
  if (step.phases.includes(phase)) return { cls: "active", label: "진행 중" };

  const order = STEPS.map((x) => x.key);
  const curIdx = order.indexOf(phase);
  const myIdx = order.indexOf(step.key);

  if (step.key === "crawling") {
    const sites = Object.values(cyc.sites || {});
    if (!sites.length) return { cls: "", label: "—" };
    const failed = sites.some((x) => x.status === "failed");
    const allDone = sites.every((x) => x.status === "done" || x.status === "failed");
    if (allDone) return { cls: failed ? "failed" : "done", label: failed ? "일부 실패" : "완료" };
    return { cls: "", label: "대기" };
  }
  if (step.key === "aggregating") {
    const st = (cyc.aggregate || {}).status;
    if (st === "done") return { cls: "done", label: `완료${secs(cyc.aggregate.elapsed)}` };
    if (st === "failed") return { cls: "failed", label: "실패" };
    return { cls: "", label: "대기" };
  }
  if (step.key === "blog") {
    const b = cyc.blog || {};
    if (b.status === "done") return { cls: "done", label: `완료 · ${b.total ?? "?"}건(신규 ${b.new ?? "?"})${secs(b.elapsed)}` };
    if (b.status === "failed") return { cls: "failed", label: "실패" };
    return { cls: "", label: "대기" };
  }
  if (step.key === "building" || step.key === "refreshing") {
    const tgt = step.key === "building" ? "dashboard" : "viewer";
    const st = (cyc.refresh || {})[tgt];
    if (st === "done") return { cls: "done", label: "완료" };
    if (st === "failed") return { cls: "failed", label: "실패" };
    return { cls: "", label: "대기" };
  }
  if (step.key === "waiting") {
    return curIdx >= 0 && myIdx > curIdx ? { cls: "", label: "—" } : { cls: "", label: "대기" };
  }
  return { cls: "", label: "—" };
}

function renderStepper(s) {
  const ol = $("stepper");
  ol.innerHTML = "";
  for (const step of STEPS) {
    const st = stepStateFor(step, s);
    const li = document.createElement("li");
    li.className = st.cls;
    li.innerHTML = `<div class="st-name">${step.name}</div><div class="st-state">${st.label}</div>`;
    ol.appendChild(li);
  }
}

function renderSites(s) {
  const wrap = $("sites");
  const sites = (s.cycle || {}).sites || {};
  const keys = SITES_ORDER.filter((k) => k in sites).concat(
    Object.keys(sites).filter((k) => !SITES_ORDER.includes(k))
  );
  if (!keys.length) {
    wrap.innerHTML = `<div class="muted">아직 크롤 사이클 기록이 없습니다.</div>`;
    return;
  }
  wrap.innerHTML = "";
  for (const k of keys) {
    const v = sites[k] || {};
    const status = v.status || "pending";
    const div = document.createElement("div");
    div.className = "site " + status + (v.reason ? " blocked" : "");
    const countHtml = v.count != null
      ? `${v.count}<span class="u"> 건</span>`
      : (status === "running" ? `<span class="spin">◐</span>` : `<span class="u">—</span>`);
    const statusLabel = {
      pending: "대기", running: "수집 중…", done: `완료${secs(v.elapsed)}`,
      failed: `실패${secs(v.elapsed)}`,
    }[status] || status;
    const blockHtml = v.reason ? `<div class="site-block">⛔ ${blockLabel(v.reason)}</div>` : "";
    div.innerHTML =
      `<div class="site-name">${k}</div>` +
      `<div class="site-count">${countHtml}</div>` +
      `<div class="site-status">${statusLabel}</div>` +
      blockHtml;
    wrap.appendChild(div);
  }
  const cyc = s.cycle || {};
  $("cycleClock").textContent = cyc.started_at ? `· 시작 ${fmtClockISO(cyc.started_at)}` : "";
}
function fmtClockISO(iso) {
  const d = parseLocal(iso);
  return d ? fmtClock(d) : "";
}

function fillBar(v) {
  const pct = Math.round((v || 0) * 100);
  const cls = pct >= 70 ? "" : pct >= 45 ? "warn" : "bad";
  return `<div class="bar ${cls}"><span style="width:${pct}%"></span></div><div class="hv">${pct}%</div>`;
}

function renderHealth(s) {
  const h = s.health_latest || {};
  const banner = $("anomalyBanner");
  const anomalies = h.anomalies || [];
  if (anomalies.length) {
    banner.className = "banner warn";
    banner.innerHTML = `⚠️ 이상 감지 ${anomalies.length}건<ul>` +
      anomalies.map((a) => `<li>${a}</li>`).join("") + `</ul>`;
  } else if (h.ts) {
    banner.className = "banner ok";
    banner.innerHTML = `✓ 이상 없음 · ${fmtClockISO(h.ts)} 기준`;
  } else {
    banner.className = "";
    banner.innerHTML = "";
  }

  const el = $("health");
  if (!h.fill_rates) {
    el.innerHTML = `<div class="muted">health 기록이 아직 없습니다.</div>`;
    return;
  }
  const fr = h.fill_rates;
  const stat = `<div class="hstat">
      <div><div class="num">${h.raw_total ?? "—"}</div><div class="lbl">수집(raw)</div></div>
      <div><div class="num">${h.active ?? "—"}</div><div class="lbl">모집중</div></div>
      <div><div class="num">${h.cross_dups ?? 0}</div><div class="lbl">교차중복</div></div>
      <div><div class="num">${h.closed ?? 0}</div><div class="lbl">마감</div></div>
    </div>`;
  const rows = [
    ["주요업무", fr.main_tasks], ["자격요건", fr.qualifications],
    ["우대사항", fr.preferences], ["기술스택", fr.tech_stack],
  ].map(([k, v]) => `<div class="hrow"><div class="hk">${k}</div>${fillBar(v)}</div>`).join("");
  el.innerHTML = stat + `<div class="muted" style="font-size:11px;margin:4px 0 2px">필드 채움률</div>` + rows;
}

function renderHistory(hist) {
  const tb = $("histTable").querySelector("tbody");
  if (!hist || !hist.length) {
    tb.innerHTML = `<tr><td colspan="5" class="muted">기록 없음</td></tr>`;
    return;
  }
  const rows = hist.slice(-10).reverse().map((h) => {
    const fr = h.fill_rates || {};
    const vals = Object.values(fr);
    const avg = vals.length ? Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 100) : 0;
    return `<tr>
      <td>${fmtClockISO(h.ts)}</td>
      <td>${h.raw_total ?? "—"}</td>
      <td>${h.active ?? "—"}</td>
      <td>${h.cross_dups ?? 0}</td>
      <td>${avg}%</td>
    </tr>`;
  }).join("");
  tb.innerHTML = rows;
}

function evMessage(e) {
  switch (e.type) {
    case "daemon_start": return `데몬 시작 keyword=${e.keyword} count=${e.count} interval=${e.interval}s`;
    case "cycle_start": return `크롤 사이클 시작 [${(e.sources || []).join(", ")}]`;
    case "site_start": return `  ${e.site} 수집 시작`;
    case "site_block": return `  ⛔ ${e.site} 차단 감지 — ${blockLabel(e.reason)}${e.http_status ? ` (HTTP ${e.http_status})` : ""}`;
    case "site_done": return `  ${e.site} ${e.ok ? "완료" : "실패"} · ${e.count ?? "?"}건${secs(e.elapsed)}${e.reason ? ` · ⛔ ${blockLabel(e.reason)}` : ""}`;
    case "aggregate_start": return `통합(aggregate) 시작`;
    case "aggregate_done": return `통합 ${e.ok ? "완료" : "실패"}${secs(e.elapsed)}`;
    case "blog_start": return `기술 블로그 수집 시작`;
    case "blog_done": return `기술 블로그 ${e.ok ? "완료" : "실패"} · ${e.total ?? "?"}건(신규 ${e.new ?? "?"}, 출처 ${e.sources ?? "?"})${secs(e.elapsed)}`;
    case "refresh_start": return `${e.target === "dashboard" ? "대시보드" : "뷰어"} 갱신 시작`;
    case "refresh_done": return `${e.target === "dashboard" ? "대시보드" : "뷰어"} 갱신 ${e.ok ? "완료" : "실패"}`;
    case "cycle_done": return `사이클 완료 · ${e.new_data ? "새 데이터 반영" : "변경 없음"}${secs(e.elapsed)}`;
    case "wait": return `다음 크롤까지 ${e.interval}s 대기`;
    case "error": return `오류 [${e.where}] ${e.msg}`;
    default: return e.type;
  }
}
function renderEvents(events) {
  const el = $("eventlog");
  el.innerHTML = "";
  for (const e of events.slice().reverse()) {
    const d = parseLocal(e.ts);
    const div = document.createElement("div");
    div.className = "ev t-" + e.type;
    div.innerHTML = `<span class="et">${d ? fmtClock(d) : ""}</span><span class="em">${evMessage(e)}</span>`;
    el.appendChild(div);
  }
}

// ---- 폴링 루프 -----------------------------------------------------------

async function pollState() {
  try {
    const s = await fetchJSON("/api/state");
    lastState = s;
    renderDaemon(s);
    renderPhase(s);
    renderCountdown(s);
    renderStepper(s);
    renderSites(s);
    renderHealth(s);
    $("connState").textContent = "연결됨";
  } catch (e) {
    $("connState").textContent = "서버 연결 끊김 — ops_server.py 실행 중인지 확인";
  }
}
async function pollEvents() {
  try { renderEvents(await fetchJSON("/api/events?n=80")); } catch (e) {}
}
async function pollHealth() {
  try { renderHistory(await fetchJSON("/api/health?n=30")); } catch (e) {}
}

pollState();
pollEvents();
pollHealth();
setInterval(pollState, 2000);
setInterval(pollEvents, 3000);
setInterval(pollHealth, 10000);
setInterval(tickCountdown, 1000);
