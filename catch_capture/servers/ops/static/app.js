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
  freelance: "외주·프리 수집",
  building: "대시보드 빌드",
  refreshing: "뷰어 갱신",
  waiting: "다음 주기 대기",
};

// 스텝퍼 정의: state.phase / cycle 데이터로 각 단계 상태를 도출
// 회차 순서(auto_crawl.run_cycle): 공고가 먼저 DB·뷰어에 들어가고, 키워드 무관 단계는 그 뒤다.
const STEPS = [
  { key: "crawling", name: "크롤", phases: ["crawling"] },
  { key: "aggregating", name: "통합·DB", phases: ["aggregating"] },
  { key: "building", name: "대시보드", phases: ["building"] },
  { key: "refreshing", name: "뷰어", phases: ["refreshing"] },
  { key: "freelance", name: "외주·프리", phases: ["freelance"] },
  { key: "blog", name: "기술블로그", phases: ["blog"] },
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
    // 운영은 상주 데몬이 아니라 launchd 가 매시간 `once` 를 띄운다 — 그때는 데몬이 꺼진 게 정상이다.
    const ld = ((lastCrawlers || {}).scheduler || {}).launchd || [];
    const cr = ld.find((l) => l.label === "com.jobseeker.crawler");
    if (cr && cr.loaded) {
      const busy = !["waiting", "idle"].includes(s.phase || "idle");
      dot.className = busy ? "dot on" : "dot";
      pill.className = "pill " + (busy ? "pill-on" : "pill-muted");
      pill.textContent = busy ? "회차 실행 중" : "launchd 매시간 실행";
      $("cfgSub").textContent = `launchd · ${(cr.interval || "").replace(" seconds", "초")} 주기 · 실행 ${cr.runs}회`;
    } else {
      dot.className = "dot off";
      pill.className = "pill pill-off";
      pill.textContent = "크롤 스케줄 없음";
      $("cfgSub").textContent = "deploy/setup-crawler.sh 로 launchd 등록";
    }
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
  } else if (s.last_error && Date.now() - (parseLocal(s.last_error.ts) || 0) < 24 * 3600 * 1000) {
    // 하루 지난 오류는 지금 상태가 아니다 — 8월의 디스크 부족이 두 달 내내 떠 있었다
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
  if (step.key === "freelance") {
    const f = cyc.freelance || {};
    if (f.status === "done") return { cls: "done", label: `완료 · 모집중 ${f.active ?? "?"}건(신규 ${f.new ?? "?"})${secs(f.elapsed)}` };
    if (f.status === "failed") return { cls: "failed", label: "실패" };
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
  $("cycleClock").textContent = cyc.started_at ? `회차 시작 ${cyc.started_at.slice(5, 16).replace("T", " ")}` : "";
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

// 뷰어가 읽는 산출물별 상태. 두 가지를 겹쳐 보여준다.
//   - 이번 사이클에서 그 빌더가 어떻게 끝났는지 (run_state.cycle.builders)
//   - 산출물 파일이 실제로 얼마나 오래됐는지 (/api/builders 의 mtime)
// 후자가 핵심이다. 데몬이 멈추면 사이클 상태는 아예 갱신되지 않는데, 화면은 며칠 전
// JSON 을 그대로 잘 보여주기 때문에 "정상"으로 보인다. 파일 나이를 같이 띄워야
// 어떤 화면이 지금 몇 시간째 옛 데이터인지 드러난다.
function renderBuilders(s, files) {
  const wrap = $("builders");
  const cyc = (s.cycle || {}).builders || {};
  const rows = files && files.length ? files : Object.keys(cyc).map((n) => ({ name: n }));
  if (!rows.length) {
    wrap.innerHTML = `<div class="muted">아직 빌더 실행 기록이 없습니다.</div>`;
    return;
  }
  const stale = rows.filter((r) => r.exists && r.age_sec > 6 * 3600).length;
  const missing = rows.filter((r) => r.exists === false).length;
  $("builderSub").textContent =
    (missing ? `${missing}개 없음 · ` : "") + (stale ? `${stale}개 6시간 이상 정체` : "전부 최신");

  wrap.innerHTML = "";
  for (const r of rows) {
    const c = cyc[r.name] || {};
    const status = c.status || (r.exists === false ? "failed" : "pending");
    const div = document.createElement("div");
    div.className = "site " + (status === "skipped" ? "pending" : status);
    const label = {
      pending: "이번 사이클 미실행", running: "생성 중…",
      done: `완료${secs(c.elapsed)}`, failed: `실패${c.detail ? " " + c.detail : ""}`,
      skipped: c.detail || "건너뜀",
    }[status] || status;
    const ageHtml = r.exists === false
      ? `<span class="u">파일 없음</span>`
      : `${fmtAge(r.age_sec)}<span class="u"> 전</span>`;
    div.innerHTML =
      `<div class="site-name">${r.name}</div>` +
      `<div class="site-count">${ageHtml}</div>` +
      `<div class="site-status">${label}</div>`;
    if (r.exists && r.age_sec > 6 * 3600) div.classList.add("blocked");
    div.title = r.file ? `${r.file}${r.mtime ? " · " + r.mtime : ""}` : r.name;
    wrap.appendChild(div);
  }
}

function fmtAge(sec) {
  if (sec == null) return "—";
  if (sec < 90) return `${sec}초`;
  if (sec < 5400) return `${Math.round(sec / 60)}분`;
  if (sec < 48 * 3600) return `${Math.round(sec / 3600)}시간`;
  return `${Math.round(sec / 86400)}일`;
}

// 방문·유입. 크롤이 만든 숫자가 아니라 방문자가 만든 숫자다.
// 비어 있을 때 '아직 아무도 안 왔다'와 '수집이 안 돌고 있다'를 구분해 준다 —
// 둘을 뭉뚱그리면 몇 주 동안 0 을 보면서 원인을 모른다.
function renderVisits(e) {
  const stats = $("visitStats");
  const src = document.querySelector("#srcTable tbody");
  const land = document.querySelector("#landTable tbody");
  if (!e) {
    stats.innerHTML = `<div class="muted">engagement.json 이 없습니다 — ` +
      `수집 서버(<code>engagement.collect</code>, 8772)와 집계(<code>engagement.score</code>)가 도는지 확인하세요.</div>`;
    $("visitSub").textContent = "";
    src.innerHTML = ""; land.innerHTML = "";
    return;
  }
  const t = e.traffic || {}, tot = e.totals || {};
  $("visitSub").textContent = e.generated_at ? `집계 ${e.generated_at}` : "";
  if (!t.visits) {
    stats.innerHTML = `<div class="muted">아직 방문 기록이 없습니다. ` +
      `수집은 돌고 있고(집계 파일 존재) 방문이 없거나, 뷰어가 아직 새 빌드가 아닙니다.</div>`;
    src.innerHTML = ""; land.innerHTML = "";
    return;
  }
  const cells = [
    { name: "방문", v: t.visits, sub: "페이지 로드" },
    { name: "순 방문자", v: t.visitors, sub: `신규 ${t.new_in_window ?? 0}` },
    { name: "세션 길이", v: fmtSecs(tot.median_session_secs), sub: "중앙값" },
    { name: "세션당 열람", v: tot.median_views_per_session ?? 0, sub: "중앙값" },
    { name: "원본 이동", v: tot.outbound ?? 0, sub: "지원하러 나감" },
  ];
  stats.innerHTML = "";
  for (const c of cells) {
    const d = document.createElement("div");
    d.className = "site";
    d.innerHTML = `<div class="site-name">${c.name}</div>` +
      `<div class="site-count">${c.v}</div><div class="site-status">${c.sub}</div>`;
    stats.appendChild(d);
  }
  const rows = (list, empty) =>
    (list && list.length
      ? list.slice(0, 8).map(([k, n]) =>
          `<tr><td title="${k}">${k}</td><td class="num">${n.toLocaleString()}</td></tr>`).join("")
      : `<tr><td class="muted">${empty}</td></tr>`);
  src.innerHTML = rows(t.sources, "유입 기록 없음");
  land.innerHTML = rows(t.landings, "랜딩 기록 없음");
}

function fmtSecs(v) {
  if (!v) return "0초";
  return v < 90 ? `${Math.round(v)}초` : `${Math.round(v / 60)}분`;
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

  $("kpiActive").textContent = h.active != null ? h.active.toLocaleString() : "—";
  $("kpiActiveSub").textContent = h.ts
    ? `수집 ${(h.raw_total ?? 0).toLocaleString()} · ${anomalies.length ? "이상 " + anomalies.length + "건" : "이상 없음"}`
    : "기록 없음";
  const el = $("health");
  if (!h.fill_rates) {
    el.innerHTML = `<div class="muted">health 기록이 아직 없습니다.</div>`;
    return;
  }
  const fr = h.fill_rates;
  const stat = `<div class="hstat">
      <div><div class="num">${(h.raw_total ?? 0).toLocaleString()}</div><div class="lbl">수집(raw)</div></div>
      <div><div class="num">${(h.active ?? 0).toLocaleString()}</div><div class="lbl">모집중</div></div>
      <div><div class="num">${(h.cross_dups ?? 0).toLocaleString()}</div><div class="lbl">교차중복</div></div>
      <div><div class="num">${(h.closed ?? 0).toLocaleString()}</div><div class="lbl">마감</div></div>
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
      <td>${h.ts ? h.ts.slice(5, 16).replace("T", " ") : "—"}</td>
      <td>${(h.raw_total ?? 0).toLocaleString()}</td>
      <td>${(h.active ?? 0).toLocaleString()}</td>
      <td>${(h.cross_dups ?? 0).toLocaleString()}</td>
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
    case "freelance_start": return `외주·프리 프로젝트 수집 시작`;
    case "freelance_done": return `외주·프리 ${e.ok ? "완료" : "실패"} · 누적 ${e.total ?? "?"}건(모집중 ${e.active ?? "?"}, 신규 ${e.new ?? "?"})${secs(e.elapsed)}`;
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
    try {
      renderBuilders(s, await fetchJSON("/api/builders"));
    } catch (e) {
      renderBuilders(s, null);
    }
    $("connState").textContent = "연결됨";
  } catch (e) {
    $("connState").textContent = "서버 연결 끊김 — python -m servers.ops.server 가 떠 있는지 확인";
  }
}
async function pollEvents() {
  try { renderEvents(await fetchJSON("/api/events?n=80")); } catch (e) {}
}
// 자동 브리핑은 사이클이 아니라 사람이 돌린다. 그래서 "몇 건"보다 **언제 돌렸나**를
// 먼저 보여준다 — 공고는 매 사이클 바뀌는데 이 산출물은 다시 돌리기 전까지 안 바뀐다.
function renderAutoguide(a) {
  const stats = $("autoguideStats");
  const tbody = $("autoguideTable").querySelector("tbody");
  if (!a || !a.exists) {
    $("autoguideSub").textContent = "아직 생성 안 됨";
    stats.innerHTML = `<div class="muted">python3 guide-engine/autoguide.py --all 로 만듭니다.</div>`;
    tbody.innerHTML = "";
    return;
  }
  const stale = a.age_sec > 24 * 3600;
  $("autoguideSub").textContent =
    `${fmtAge(a.age_sec)} 전 생성${stale ? " · 하루 넘음, 다시 돌릴 때" : ""}`;

  const cards = [
    ["회사", a.companies], ["공고", a.postings],
    ["중복 뺀 자리", a.distinct_active], ["본문 있음", a.with_body],
    ["규모 근거", a.with_facts], ["연봉 근거", a.with_salary],
  ];
  stats.innerHTML = cards.map(([label, n]) =>
    `<div class="site done"><div class="site-name">${label}</div>` +
    `<div class="site-count">${(n ?? 0).toLocaleString()}</div>` +
    `<div class="site-status">&nbsp;</div></div>`).join("");

  tbody.innerHTML = (a.top || []).map((c) =>
    `<tr><td>${c.name}</td><td>${c.active}</td><td>${c.distinct}</td>` +
    `<td>${(c.body ?? 0).toLocaleString()}</td>` +
    `<td>${c.facts ? "O" : "—"}</td><td>${c.salary ? "O" : "—"}</td></tr>`).join("");
}

// ---- 인스타 발행 ------------------------------------------------------------
const IG_STATE = {
  approved: "승인됨", scheduled: "예약", published: "게시됨",
  rehearsed: "연습 발행", failed: "실패", skipped: "뺌",
};
const PLATFORM_LABEL = { instagram: "인스타", facebook: "페이스북", linkedin: "링크드인" };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function fmtWhen(iso) {
  const d = parseLocal(iso);
  if (!d) return "—";
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  const hm = d.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false });
  return sameDay ? `오늘 ${hm}` : `${d.getMonth() + 1}/${d.getDate()} ${hm}`;
}

function renderPublish(p) {
  const banner = $("igBanner");
  if (!p || !p.exists) {
    $("igSub").textContent = "아직 설치 안 됨";
    banner.innerHTML = "";
    $("igStats").innerHTML =
      `<div class="muted">./deploy/setup-publisher.sh 로 데몬을 등록하고 publish.cli approve 로 포스터를 승인합니다.</div>`;
    ["igScheduled", "igProblems"].forEach((id) => ($(id).querySelector("tbody").innerHTML = ""));
    $("igRecent").innerHTML = "";
    $("igLog").innerHTML = "";
    return;
  }
  const s = p.status || {};
  const c = p.counts || {};
  // 데몬은 5분마다 돈다. 20분 넘게 상태 파일이 안 바뀌면 launchd 등록이 빠졌거나 죽은 것.
  const stale = s.age_sec == null || s.age_sec > 1200;
  const live = s.mode === "live";
  $("igSub").textContent = `${live ? "실제 발행" : "연습 모드"} · 데몬 ${s.age_sec == null ? "기록 없음" : fmtAge(s.age_sec) + " 전"}` +
    (s.slots && s.slots.length ? ` · 발행 시각 ${s.slots.join(", ")}` : "");

  const warns = [];
  if (stale) warns.push("데몬 상태가 20분 넘게 갱신되지 않았습니다 — launchd 등록(com.jobseeker.publisher) 확인");
  if (!live) {
    const lacking = Object.entries(s.missing_by || {}).map(([p, m]) => `${PLATFORM_LABEL[p] || p}: ${m.join(", ")}`);
    const why = !s.live ? "autopublish.live 가 꺼져 있어" : `자격이 모자라(${lacking.join(" / ")})`;
    warns.push(`${why} 실제로는 올라가지 않습니다. 시각이 된 항목은 '연습 발행'으로 남습니다`);
  } else {
    // 한쪽 자격만 있으면 그 한 곳으로만 나간다 — 조용히 한 군데만 올라가는 걸 눈에 보이게 한다
    const off = Object.entries(s.ready || {}).filter(([, ok]) => !ok).map(([p]) => PLATFORM_LABEL[p] || p);
    if (off.length) warns.push(`${off.join(", ")} 자격이 없어 그곳은 건너뜁니다`);
  }
  if (!s.public_base_url) warns.push("public_base_url 이 없습니다 — 인스타가 이미지를 받아 갈 공개 주소가 필요합니다");
  if (s.token_days_left != null && s.token_days_left <= 7)
    warns.push(`인스타 토큰이 ${s.token_days_left}일 뒤 만료됩니다 — 데몬이 갱신을 시도합니다. 실패하면 publish.cli token-refresh`);
  banner.innerHTML = warns.length
    ? `<div class="banner warn">확인 필요<ul>${warns.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></div>`
    : `<div class="banner ok">정상 — 예약대로 올라갑니다</div>`;

  const quota = s.quota ? `${s.quota.used}/${s.quota.limit}` : "—";
  const token = s.token_days_left == null ? "—" : `${s.token_days_left}일`;
  const cards = [
    ["예약", (c.scheduled ?? 0) + (c.approved ?? 0), "scheduled"],
    ["게시됨", c.published ?? 0, "done"],
    ["연습 발행", c.rehearsed ?? 0, "pending"],
    ["실패", c.failed ?? 0, c.failed ? "failed" : "done"],
    ["24시간 한도", quota, "done"],
    ["토큰 남은 날", token, s.token_days_left != null && s.token_days_left <= 7 ? "failed" : "done"],
  ];
  $("igStats").innerHTML = cards.map(([label, n, cls]) =>
    `<div class="site ${cls === "scheduled" ? "running" : cls}"><div class="site-name">${label}</div>` +
    `<div class="site-count">${typeof n === "number" ? n.toLocaleString() : esc(n)}</div>` +
    `<div class="site-status">&nbsp;</div></div>`).join("");

  // 묶음이면 '이번 주 채용 · 9월 14–20일 · 묶음 6장' 처럼 보인다(company/role 자리에 카테고리가 온다)
  const bundle = (r) => (r.kind === "collection" ? ` <span class="igtag">묶음 ${r.slides}장</span>` : "");
  const who = (r) => `${esc(r.company || r.job_key)}${bundle(r)}` +
    `<div class="muted" style="font-size:11px">${esc(r.role)}</div>`;
  const where = (r) => (r.platforms || []).map((x) => PLATFORM_LABEL[x] || x).join("·");
  const errText = (r) => Object.entries(r.errors || {})
    .map(([pf, e]) => `${PLATFORM_LABEL[pf] || pf}: ${e}`).join(" / ") || r.last_event;

  $("igScheduled").querySelector("tbody").innerHTML = (p.scheduled || []).length
    ? p.scheduled.map((r) =>
        `<tr><td>${who(r)}</td><td>${fmtWhen(r.scheduled_at)}` +
        `<div class="muted" style="font-size:11px">${esc(where(r))}${r.attempts ? ` · 재시도 ${r.attempts}` : ""}</div></td></tr>`).join("")
    : `<tr><td class="muted">예약된 포스터가 없습니다</td><td></td></tr>`;

  $("igProblems").querySelector("tbody").innerHTML = (p.problems || []).length
    ? p.problems.map((r) =>
        `<tr><td>${who(r)}</td><td><span class="igtag ig-${r.status}">${IG_STATE[r.status] || r.status}</span>` +
        ((r.posted || []).length ? ` <span class="muted">${esc(r.posted.map((x) => PLATFORM_LABEL[x] || x).join("·"))} 올라감</span>` : "") +
        `<div class="muted" style="font-size:11px;text-align:left">${esc(errText(r))}</div></td></tr>`).join("")
    : `<tr><td class="muted">없음</td><td></td></tr>`;

  $("igRecent").innerHTML = (p.recent || []).length
    ? p.recent.map((r) => {
        const when = r.status === "published" ? fmtWhen(r.published_at) : fmtWhen(r.slot);
        const thumb = r.image_url
          ? `<img src="${esc(r.image_url)}" alt="" loading="lazy">`
          : `<div class="igthumb-empty">${r.status === "rehearsed" ? "연습" : "—"}</div>`;
        const react = r.likes != null ? `♥ ${r.likes} · 💬 ${r.comments ?? 0}` : "";
        // 플랫폼마다 링크가 다르다. 게시된 곳만 링크로 걸고, 안 나간 곳은 회색으로 남긴다.
        const links = (r.platforms || []).map((pf) => {
          const label = PLATFORM_LABEL[pf] || pf;
          const href = (r.links || {})[pf];
          return href
            ? `<a href="${esc(href)}" target="_blank" rel="noopener">${label} ↗</a>`
            : `<span class="muted">${label}</span>`;
        }).join(" · ");
        return `<div class="igpost">${thumb}<div class="igmeta">` +
          `<div class="igco">${esc(r.company || r.job_key)}${bundle(r)}</div>` +
          `<div class="muted">${esc(r.role)}</div>` +
          `<div><span class="igtag ig-${r.status}">${IG_STATE[r.status]}</span> ${when}</div>` +
          `<div class="iglinks">${links}</div>` +
          `<div class="muted">${react}</div></div></div>`;
      }).join("")
    : `<div class="muted">아직 올라간 포스터가 없습니다</div>`;

  $("igLog").innerHTML = (s.log || []).map((e) =>
    `<div class="ev"><span class="et">${fmtWhen(e.at)}</span><span class="em">${esc(e.msg)}</span></div>`).join("")
    || `<div class="muted">기록 없음</div>`;
}

async function pollPublish() {
  try { renderPublish(await fetchJSON("/api/publish")); } catch (_) { /* 연결 표시는 pollState 가 한다 */ }
}

// 반복 작업 등록부 — 멈춘 것을 산출물의 나이로 드러낸다. 데몬 상태만 보면 /loop 엔진이
// 세션과 함께 꺼진 것은 영영 안 보인다.
function renderLoops(rows) {
  const tb = document.querySelector("#loopsTable tbody");
  if (!Array.isArray(rows)) {
    tb.innerHTML = `<tr><td colspan="6" class="muted">등록부를 읽지 못했습니다${rows && rows.error ? ": " + rows.error : ""}</td></tr>`;
    return;
  }
  const KIND = { launchd: "launchd", cycle: "크롤 단계", "claude-loop": "/loop 엔진" };
  const STATE = { ok: "정상", stale: "멈춤?", stopped: "꺼짐", unknown: "모름" };
  const bad = rows.filter((r) => r.state === "stale" || r.state === "stopped");
  const lb = $("navLoopsBadge");
  lb.textContent = bad.length ? String(bad.length) : "";
  lb.className = "navbadge " + (bad.length ? "warn" : "");
  $("loopsSub").textContent = bad.length ? `${bad.length}개 확인 필요 · 전체 ${rows.length}` : `전체 ${rows.length} · 모두 정상`;
  tb.innerHTML = "";
  for (const r of rows) {
    const tr = document.createElement("tr");
    const age = r.age_hours == null ? "—" : fmtAge(Math.round(r.age_hours * 3600)) + " 전";
    const cls = r.state === "ok" ? "" : r.state === "unknown" ? "muted" : "warn";
    tr.innerHTML =
      `<td class="${cls}">${STATE[r.state] || r.state}</td>` +
      `<td>${KIND[r.kind] || r.kind}</td>` +
      `<td title="${(r.note || "").replace(/"/g, "&quot;")}">${r.name}<div class="muted" style="font-size:11px">${r.key}${r.backlog ? " · " + r.backlog : ""}</div></td>` +
      `<td>${r.cadence}</td>` +
      `<td>${age}</td>` +
      `<td style="font-size:11px">${r.kind === "claude-loop" ? "python -m automation.loops prompt " + r.key : r.run}</td>`;
    tb.appendChild(tr);
  }
}

async function pollLoops() {
  try { renderLoops(await fetchJSON("/api/loops")); } catch (_) {}
}

// 크롤러 현황 — 출처마다 '마지막으로 실제 받은 때'와 건수.
// 묶음 타일(한눈에) → 펼치는 표(드릴다운). 문제 있는 묶음은 펼쳐서, 문제 줄은 위로 올려 보인다.
const CST = { ok: "정상", warn: "늦음", stale: "멈춤", error: "실패", unknown: "모름" };
const SEVERITY = { error: 0, stale: 1, warn: 2, unknown: 3, ok: 4 };
const groupOpen = {};      // 사람이 펼치고 접은 것은 30초마다 다시 그려도 지킨다
let lastCrawlers = null;

function groupLevel(rows) {
  if (rows.some((r) => r.state === "stale" || r.state === "error")) return "bad";
  if (rows.some((r) => r.state === "warn")) return "warn";
  return rows.length ? "ok" : "";
}

function renderCrawlers(d) {
  lastCrawlers = d;
  const c = d.counts || {};
  const bad = (c.stale || 0) + (c.error || 0);
  $("crawlSub").textContent = `출처 ${d.total}곳 · 정상 ${c.ok || 0} · 늦음 ${c.warn || 0} · 멈춤 ${c.stale || 0} · 실패 ${c.error || 0}`;

  // ── 판정: 가장 최근 수집의 나이가 1순위다(전부 멈췄으면 개별 출처는 의미가 없다)
  const newestAge = d.newest_at ? Math.max(0, (Date.now() - new Date(d.newest_at).getTime()) / 1000) : null;
  const sch = d.scheduler || {};
  const dm = sch.daemon || {};
  const lds = sch.launchd || [];
  const crawlerLd = lds.find((l) => l.label === "com.jobseeker.crawler") || {};
  const running = dm.phase && !["waiting", "idle"].includes(dm.phase) &&
    dm.updated_at && (Date.now() - new Date(dm.updated_at).getTime()) < 20 * 60 * 1000;
  let level = "ok";
  if (newestAge == null || newestAge > 24 * 3600) level = "bad";
  else if (newestAge > 3 * 3600 || bad) level = "warn";

  const verdict = $("verdictPill");
  verdict.className = "verdict " + level;
  verdict.textContent = { ok: "✓ 크롤 정상", warn: `! 확인 필요 ${bad ? bad + "곳" : ""}`.trim(), bad: "■ 크롤 멈춤" }[level];

  const hero = $("heroKpi");
  hero.className = "kpi hero-kpi " + level;
  $("heroAge").textContent = newestAge == null ? "기록 없음" : fmtAge(Math.round(newestAge)) + " 전";
  $("heroSub").textContent = running ? `지금 수집 중 · ${PHASE_LABEL[dm.phase] || dm.phase}`
    : level === "bad" ? "하루 넘게 새로 받은 것이 없습니다"
    : level === "warn" ? (bad ? `${bad}곳 확인 필요 — 아래 크롤러 현황` : "3시간 넘게 새 수집 없음")
    : "제때 받고 있습니다";

  const total = d.total || 0;
  $("kpiSources").textContent = `${c.ok || 0} / ${total}`;
  $("kpiSourcesSub").textContent = bad ? `멈춤·실패 ${bad}곳` : (c.warn ? `늦음 ${c.warn}곳` : "모두 제때");

  const badge = $("navCrawlBadge");
  badge.textContent = bad ? String(bad) : "";
  badge.className = "navbadge " + (bad ? "bad" : "");

  // ── 배너: 전부 멈춘 경우만 크게. 원인 후보(데몬·launchd)를 같이 적는다
  let banner = "";
  if (level === "bad" && !running) {
    banner = `<div class="banner bad">■ 마지막 수집이 <b>${fmtAge(Math.round(newestAge || 0))} 전</b>입니다` +
      (dm.cycle_finished_at ? ` · 마지막 회차 끝 ${esc(dm.cycle_finished_at.replace("T", " "))}` : "") +
      ` · 크롤 데몬 ${dm.pid ? "살아 있음" : "꺼짐"} · launchd 크롤러 ` +
      (crawlerLd.loaded ? `등록됨(실행 ${esc(crawlerLd.runs)}회, ${esc(crawlerLd.state)})` : "<b>미등록</b> — deploy/setup-crawler.sh") + `</div>`;
  }
  $("crawlBanner").innerHTML = banner;

  // ── 묶음 타일
  const groups = d.groups || [];
  $("crawlGroupTiles").innerHTML = groups.map((g) => {
    const lv = groupLevel(g.rows);
    const nb = g.rows.filter((r) => r.state === "stale" || r.state === "error").length;
    const nOk = g.rows.filter((r) => r.state === "ok").length;
    const sum = g.rows.reduce((a, r) => a + (r.count || 0), 0);
    const ages = g.rows.map((r) => r.age_hours).filter((x) => x != null);
    const age = ages.length ? Math.min(...ages) : null;
    const word = { ok: "✓ 정상", warn: "! 늦음", bad: `■ ${nb}곳 문제` }[lv] || "—";
    return `<button type="button" class="gtile ${lv}" data-g="${esc(g.key)}">` +
      `<div class="g-name">${esc(g.name)}</div>` +
      `<div class="g-main">${word}</div>` +
      `<div class="g-sub">${nOk}/${g.rows.length}곳 정상 · ${sum.toLocaleString()}건` +
      `${age != null ? " · " + fmtAge(Math.round(age * 3600)) + " 전" : ""}</div></button>`;
  }).join("");

  // ── 펼치는 표
  $("crawlGroups").innerHTML = groups.map((g) => {
    const lv = groupLevel(g.rows);
    const open = g.key in groupOpen ? groupOpen[g.key] : lv === "bad" && g.rows.length <= 12;
    const rows = g.rows.slice().sort((a, b) =>
      (SEVERITY[a.state] ?? 9) - (SEVERITY[b.state] ?? 9) || (b.count || 0) - (a.count || 0));
    const nb = rows.filter((r) => r.state === "stale" || r.state === "error").length;
    const body = rows.map((r) =>
      `<tr class="${r.state === "stale" || r.state === "error" ? "row-bad" : ""}">` +
      `<td><span class="cst ${r.state}">${CST[r.state] || r.state}</span></td>` +
      `<td>${esc(r.name)}</td>` +
      `<td class="n">${r.count == null ? "—" : r.count.toLocaleString()}</td>` +
      `<td class="n">${r.age_hours == null ? "—" : fmtAge(Math.round(r.age_hours * 3600)) + " 전"}</td>` +
      `<td class="muted">${esc(r.detail)}</td>` +
      `<td class="err">${esc(r.error)}</td></tr>`).join("");
    return `<details class="cgroup" data-g="${esc(g.key)}"${open ? " open" : ""}>` +
      `<summary><span class="cst ${lv === "bad" ? "stale" : lv || "unknown"}">${lv === "bad" ? nb + "곳" : lv === "warn" ? "늦음" : "정상"}</span>` +
      `${esc(g.name)}<span class="g-meta">${g.rows.length}곳 · ${g.rows.reduce((a, r) => a + (r.count || 0), 0).toLocaleString()}건</span></summary>` +
      `<div class="cwrap"><table class="ctable">` +
      `<colgroup><col class="c-st"><col class="c-nm"><col class="c-n"><col class="c-age"><col class="c-dt"><col></colgroup>` +
      `<thead><tr><th>상태</th><th>출처</th><th class="n">건수</th><th class="n">마지막</th><th>세부</th><th>오류</th></tr></thead>` +
      `<tbody>${body}</tbody></table></div></details>`;
  }).join("");

  // ── 스케줄러
  const tiles = [
    { name: "auto_crawl 데몬", val: dm.pid ? "살아 있음" : "꺼짐",
      sub: dm.pid ? `pid ${dm.pid} · ${esc(dm.phase || "")}` : "launchd 가 회차를 띄운다",
      cls: dm.pid ? "done" : "pending" },
    ...lds.map((l) => {
      const fine = !!l.loaded && (l.last_exit === "0" || l.last_exit === "(never exited)");
      return {
        name: l.label.replace("com.jobseeker.", "launchd · "),
        val: l.loaded ? (l.pid ? "실행 중" : "등록됨") : "미등록",
        sub: l.loaded ? `실행 ${esc(l.runs)}회 · 종료코드 ${esc(l.last_exit)} · ${esc((l.interval || "").replace(" seconds", "초 주기"))}` : "setup 스크립트 필요",
        cls: fine ? "done" : "failed blocked",
      };
    }),
  ];
  $("crawlSched").innerHTML = tiles.map((t) =>
    `<div class="site ${t.cls}"><div class="site-name">${esc(t.name)}</div>` +
    `<div class="site-count" style="font-size:18px">${esc(t.val)}</div><div class="site-status">${t.sub}</div></div>`).join("");

  if (lastState) renderDaemon(lastState);
}

$("crawlGroups").addEventListener("toggle", (e) => {
  const el = e.target.closest && e.target.closest("details.cgroup");
  if (el) groupOpen[el.dataset.g] = el.open;
}, true);
$("crawlGroupTiles").addEventListener("click", (e) => {
  const t = e.target.closest(".gtile");
  if (!t) return;
  const det = $("crawlGroups").querySelector(`details[data-g="${t.dataset.g}"]`);
  if (!det) return;
  det.open = true;
  groupOpen[t.dataset.g] = true;
  det.scrollIntoView({ block: "start" });
});

async function pollCrawlers() {
  try { renderCrawlers(await fetchJSON("/api/crawlers")); } catch (e) {
    $("crawlSub").textContent = "읽기 실패: " + e.message;
  }
}

// ── 테마 전환 · 목차 강조 ────────────────────────────────────────────
$("themeBtn").addEventListener("click", () => {
  const root = document.documentElement;
  const dark = root.dataset.theme ? root.dataset.theme === "dark"
    : window.matchMedia("(prefers-color-scheme: dark)").matches;
  root.dataset.theme = dark ? "light" : "dark";
  try { localStorage.setItem("ops-theme", root.dataset.theme); } catch (_) {}
});
(() => {
  const links = [...document.querySelectorAll("#sidenav a")];
  const byId = new Map(links.map((a) => [a.getAttribute("href").slice(1), a]));
  const io = new IntersectionObserver((ents) => {
    for (const en of ents) {
      if (!en.isIntersecting) continue;
      links.forEach((a) => a.classList.remove("active"));
      const a = byId.get(en.target.id);
      if (a) a.classList.add("active");
    }
  }, { rootMargin: "-80px 0px -70% 0px" });
  byId.forEach((_, id) => { const el = document.getElementById(id); if (el) io.observe(el); });
})();

// DB 저장 현황 — 정본 DB 에 실제로 들어간 것. 뷰어 목록은 이 숫자를 보여준다.
const SITE_LABEL = { wanted: "원티드", jumpit: "점핏", jobkorea: "잡코리아", saramin: "사람인", dev: "캐치",
  remote: "해외 원격", ats: "회사 채용페이지", boards: "기타 보드·공공" };
function cstBadge(state) { return `<span class="cst ${state}">${CST[state] || state}</span>`; }
function agoH(h) { return h == null ? "—" : fmtAge(Math.round(h * 3600)) + " 전"; }
function renderDb(d) {
  const badge = $("navDbBadge");
  if (!d || !d.ok) {
    $("dbBanner").innerHTML = `<div class="banner bad">✕ DB 에 붙지 못했습니다 — ${esc((d && d.error) || "응답 없음")}. ` +
      `<code>docker ps</code> 로 jobseeker-db 가 떠 있는지 확인하세요. 뷰어는 정적 파일로 물러섭니다.</div>`;
    $("dbSub").textContent = "";
    badge.textContent = "!"; badge.className = "navbadge bad";
    return;
  }
  const j = d.jobs;
  const lv = j.last_write_age_hours == null ? "unknown" : j.last_write_age_hours <= 3 ? "ok" : j.last_write_age_hours <= 24 ? "warn" : "stale";
  const bad = d.sites.concat(d.tables).filter((r) => r.state === "stale" || r.state === "error").length;
  badge.textContent = bad ? String(bad) : ""; badge.className = "navbadge " + (bad ? "warn" : "");
  $("dbSub").textContent = `조회 ${d.generated_at.slice(11, 19)}`;
  $("dbBanner").innerHTML = lv === "stale"
    ? `<div class="banner bad">■ 공고가 DB 에 마지막으로 들어간 지 <b>${agoH(j.last_write_age_hours)}</b> — 뷰어 목록이 그때 상태입니다.</div>` : "";
  const tiles = [
    ["모집중 공고", j.active.toLocaleString(), `전체 ${j.total.toLocaleString()}건`],
    ["24시간 신규", j.new_24h.toLocaleString(), "처음 본 공고"],
    ["마지막 공고 적재", agoH(j.last_write_age_hours), j.last_write ? j.last_write.slice(5, 16).replace("T", " ") : "—"],
  ];
  const fl = d.tables.find((t) => t.key === "project");
  if (fl && fl.total != null) tiles.push(["외주 프로젝트", (fl.sub ?? 0).toLocaleString(), `모집중 · 24시간 신규 ${fl.new_24h}`]);
  $("dbTiles").innerHTML = tiles.map(([n, v, sub], i) =>
    `<div class="site ${i === 2 ? (lv === "ok" ? "done" : "failed blocked") : "done"}"><div class="site-name">${n}</div>` +
    `<div class="site-count">${v}</div><div class="site-status">${esc(sub)}</div></div>`).join("");

  document.querySelector("#dbSites tbody").innerHTML = d.sites.map((s) =>
    `<tr><td>${esc(SITE_LABEL[s.site] || s.site)}</td><td>${cstBadge(s.state)}</td>` +
    `<td>${s.active.toLocaleString()}</td><td>${s.total.toLocaleString()}</td>` +
    `<td>${s.new_24h ? "+" + s.new_24h.toLocaleString() : "0"}</td><td>${agoH(s.age_hours)}</td></tr>`).join("");

  const SUB = { project: "모집중", job_state: "마감", hw_price_day: "부품" };
  document.querySelector("#dbTables tbody").innerHTML = d.tables.map((t) => t.error
    ? `<tr><td>${esc(t.name)}</td><td>${cstBadge("error")}</td><td colspan="3" class="muted">${esc(t.error)}</td></tr>`
    : `<tr><td>${esc(t.name)}</td><td>${cstBadge(t.state)}</td>` +
      `<td>${t.total.toLocaleString()}${t.sub != null && SUB[t.key] ? `<div class="muted" style="font-size:11.5px">${SUB[t.key]} ${t.sub.toLocaleString()}</div>` : ""}</td>` +
      `<td>${t.new_24h.toLocaleString()}</td><td>${agoH(t.age_hours)}</td></tr>`).join("");

  const maxNew = Math.max(1, ...d.runs.map((r) => r.n_new || 0));
  document.querySelector("#dbRuns tbody").innerHTML = d.runs.map((r) =>
    `<tr><td>${esc((r.started_at || "").slice(5, 16).replace("T", " "))}</td>` +
    `<td>${r.ok ? cstBadge("ok") : cstBadge("error")}</td>` +
    `<td>${(r.n_raw || 0).toLocaleString()}</td><td>${(r.n_upserted || 0).toLocaleString()}</td>` +
    `<td><b>+${(r.n_new || 0).toLocaleString()}</b></td>` +
    `<td><div class="minibar" title="신규 ${r.n_new}"><span style="width:${Math.round(100 * (r.n_new || 0) / maxNew)}%"></span></div></td></tr>`).join("");
}
async function pollDb() {
  try { renderDb(await fetchJSON("/api/db")); } catch (e) { renderDb({ ok: false, error: e.message }); }
}

async function pollAutoguide() {
  try { renderAutoguide(await fetchJSON("/api/autoguide")); } catch (e) {}
}

// 취업 브리핑 — 조사 끝난 회사 목록. 행을 누르면 브리핑이 다룬 공고가 펼쳐진다.
let guideData = null;
function renderGuide(g) {
  if (g) guideData = g;
  g = guideData;
  if (!g) return;
  const cs = g.companies || [];
  const done = cs.filter((c) => c.status === "done").length;
  $("guideSub").textContent = `index ${g.updated_at || "—"}`;
  const cards = [
    ["조사 완료", done], ["진행 중", cs.length - done], ["대기열", (g.queue || []).length],
    ["공고", cs.reduce((a, c) => a + c.postings, 0)], ["학습 항목", cs.reduce((a, c) => a + c.study_items, 0)],
  ];
  $("guideStats").innerHTML = cards.map(([label, n]) =>
    `<div class="site done"><div class="site-name">${label}</div>` +
    `<div class="site-count">${n.toLocaleString()}</div><div class="site-status">&nbsp;</div></div>`).join("");
  const doing = cs.filter((c) => c.status !== "done").map((c) => esc(c.name));
  $("guideQueue").innerHTML =
    (doing.length ? `진행 중: <b>${doing.join(", ")}</b> · ` : "") +
    ((g.queue || []).length ? `다음 차례: ${g.queue.map((q) => esc(q.name)).join(" → ")}` : "대기열 비어 있음");

  const q = ($("guideFilter").value || "").trim().toLowerCase();
  const rows = cs.filter((c) => !q || `${c.name} ${c.name_en} ${c.one_liner}`.toLowerCase().includes(q));
  $("guideTable").querySelector("tbody").innerHTML = rows.map((c, i) => {
    const tag = c.status === "done" ? "" : ` <span class="pill pill-warn">진행 중</span>`;
    const posts = (c.posting_list || []).map((p) =>
      `<li><span class="muted">${esc(p.site)}</span> ` +
      (p.url ? `<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.title)}</a>` : esc(p.title)) + `</li>`).join("");
    return `<tr class="guiderow" data-i="${i}"><td class="nowrap"><b>${esc(c.name)}</b>${tag}` +
      `${c.name_en ? `<div class="muted">${esc(c.name_en)}</div>` : ""}</td>` +
      `<td>${esc((c.one_liner || "").replace(/\*\*/g, ""))}</td><td class="nowrap">${c.postings}</td><td class="nowrap">${c.study_items}</td>` +
      `<td class="nowrap">${c.salary ? "O" : "—"}</td><td class="nowrap muted">${esc(c.updated_at)}</td></tr>` +
      `<tr class="guidedetail hide" data-for="${i}"><td colspan="6"><ul>${posts || "<li class=muted>공고 없음</li>"}</ul>` +
      `<div class="muted">공개 인물 ${c.people}명</div></td></tr>`;
  }).join("") || `<tr><td colspan="6" class="muted">맞는 회사가 없습니다</td></tr>`;
}
$("guideFilter").addEventListener("input", () => renderGuide());
$("guideTable").addEventListener("click", (e) => {
  const tr = e.target.closest("tr.guiderow");
  if (!tr || e.target.closest("a")) return;
  const d = $("guideTable").querySelector(`tr[data-for="${tr.dataset.i}"]`);
  if (d) d.classList.toggle("hide");
});
async function pollGuide() {
  // 30초마다 다시 그리면 펼쳐 둔 행이 접힌다 — 목록이 바뀐 때만 다시 그린다.
  try {
    const g = await fetchJSON("/api/guide");
    const sig = JSON.stringify([g.updated_at, g.companies.length, g.queue.length, g.companies.map((c) => c.status)]);
    if (sig !== pollGuide.sig) { pollGuide.sig = sig; renderGuide(g); }
  } catch (e) {}
}

async function pollHealth() {
  try { renderHistory(await fetchJSON("/api/health?n=30")); } catch (e) {}
  // 집계는 사이클마다 한 번이라 자주 볼 이유가 없다 — health 와 같은 주기에 얹는다.
  try { renderVisits(await fetchJSON("/api/engagement")); } catch (e) { renderVisits(null); }
}

pollState();
pollEvents();
pollHealth();
pollAutoguide();
pollGuide();
pollLoops();
pollCrawlers();
pollDb();
pollPublish();
setInterval(pollState, 2000);
setInterval(pollEvents, 3000);
setInterval(pollHealth, 10000);
setInterval(pollAutoguide, 30000);
setInterval(pollGuide, 30000);
setInterval(pollLoops, 60000);
setInterval(pollCrawlers, 30000);
setInterval(pollDb, 30000);
// 데몬이 5분마다 도니 15초면 충분하다.
setInterval(pollPublish, 15000);
setInterval(tickCountdown, 1000);
