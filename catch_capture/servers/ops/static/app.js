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
  alba: "컴퓨터 알바 수집",
  contests: "공모전 수집",
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
  { key: "alba", name: "컴퓨터 알바", phases: ["alba"] },
  { key: "contests", name: "공모전", phases: ["contests"] },
  { key: "blog", name: "기술블로그", phases: ["blog"] },
  { key: "waiting", name: "대기", phases: ["waiting", "idle"] },
];

let nextRunAt = null; // Date | null
// 개요는 여러 API 를 한 장으로 접는다 — 각 폴링이 여기 넣고 renderOverview 를 부른다.
const OV = { crawlers: null, db: null, loops: null, builders: null, state: null };
let lastState = null;

const $ = (id) => document.getElementById(id);

// 시각은 24시간 한 형식(오전/오후 섞지 않는다)
function fmtClock(d) {
  return d.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
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
  const pill = $("daemonText");   // 알약 안의 글자만 바꾼다(점은 따로)
  const d = s.daemon || {};
  // daemon_health: ok(가동중) | stalled(살아있지만 멈춤/지연) | stopped(중지)
  // 구버전 서버 호환: 필드 없으면 daemon_alive 로 폴백
  const health = s.daemon_health || (s.daemon_alive ? "ok" : "stopped");
  if (health === "ok") {
    dot.className = "dot on";
    pill.textContent = `데몬 가동중 · PID ${s.daemon_pid}`;
    $("cfgSub").textContent = d.keyword
      ? `keyword=${d.keyword} · 사이트당 ${d.count} · 주기 ${Math.round((d.interval || 0) / 60)}분`
      : "";
  } else if (health === "stalled") {
    dot.className = "dot warn";
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
      pill.textContent = busy ? "회차 실행 중" : cr.via === "windows-task" ? "작업 스케줄러 매시간 실행" : "launchd 매시간 실행";
      $("cfgSub").textContent = `launchd · ${(cr.interval || "").replace(" seconds", "초")} 주기 · 실행 ${cr.runs}회`;
    } else {
      dot.className = "dot off";
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
  el.className = "phase " + phase;

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
  if (step.key === "alba") {
    const a = cyc.alba || {};
    // 출처(당근·알바천국·알바몬·사람인·잡코리아) 중 일부만 실패하면 단계는 완료이고 failed 에 이름이 남는다.
    const bad = (a.failed || []).length ? ` · 실패 ${a.failed.join(",")}` : "";
    if (a.status === "done") return { cls: "done", label: a.skipped ? "건너뜀(마감 확인 중)" : `완료 · 모집중 ${a.open ?? "?"}건(신규 ${a.new ?? "?"}, 마감 ${a.closed_now ?? 0})${bad}${secs(a.elapsed)}` };
    if (a.status === "failed") return { cls: "failed", label: "실패" };
    if (a.status === "running") return { cls: "active", label: "수집 중" };
    return { cls: "", label: "대기" };
  }
  if (step.key === "contests") {
    // 하루 한 번만 실제로 받는다 — 나머지 회차는 '건너뜀'(마감일 계산만)이 정상이다.
    const c = cyc.contests || {};
    if (c.status === "done") return { cls: "done", label: `완료 · 접수중 ${c.open ?? "?"}건(신규 ${c.new ?? "?"}, 마감 ${c.closed_now ?? 0})${secs(c.elapsed)}` };
    if (c.status === "skipped") return { cls: "done", label: c.reason === "locked" ? "건너뜀(마감 확인 중)" : `건너뜀(오늘 받음) · 접수중 ${c.open ?? "?"}건` };
    if (c.status === "failed") return { cls: "failed", label: "실패" };
    if (c.status === "running") return { cls: "active", label: "수집 중" };
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

// 이번 회차 사이트별 수집 — 한 사이트 = 표 한 줄(결과 · 건수 · 소요)
function renderSites(s) {
  const tb = $("sites").querySelector("tbody");
  const sites = (s.cycle || {}).sites || {};
  const keys = SITES_ORDER.filter((k) => k in sites).concat(
    Object.keys(sites).filter((k) => !SITES_ORDER.includes(k))
  );
  if (!keys.length) {
    tb.innerHTML = `<tr><td colspan="4" class="muted">아직 크롤 사이클 기록이 없습니다.</td></tr>`;
    return;
  }
  const RES = { pending: ["unknown", "대기"], running: ["warn", "수집 중"], done: ["ok", "완료"], failed: ["error", "실패"] };
  tb.innerHTML = keys.map((k) => {
    const v = sites[k] || {};
    const status = v.status || "pending";
    const [cls, word] = RES[status] || ["unknown", status];
    const res = status === "running" ? `<span class="phase"><span class="spin">◐</span> 수집 중</span>`
      : status === "pending" ? `<span class="muted">대기</span>` : `<span class="cst ${cls}">${word}</span>`;
    const block = v.reason ? `<span class="blocked-line">⛔ ${esc(blockLabel(v.reason))}</span>` : "";
    return `<tr><td>${esc(k)}${block}</td><td>${res}</td>` +
      `<td class="n">${v.count != null ? v.count.toLocaleString() + "건" : "—"}</td>` +
      `<td class="n">${v.elapsed != null ? v.elapsed + "s" : "—"}</td></tr>`;
  }).join("");
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
// 파일 나이를 막대로 — 6시간 기준선을 넘은 줄만 빨갛다. 이번 사이클 상태가 모두 같으면
// (보통 '이번 사이클 미실행') 줄마다 되풀이하지 않고 패널 머리에 한 번만 적는다.
function renderBuilders(s, files) {
  const wrap = $("builders");
  const cyc = (s.cycle || {}).builders || {};
  const rows = files && files.length ? files : Object.keys(cyc).map((n) => ({ name: n }));
  if (!rows.length) {
    wrap.innerHTML = `<div class="muted">아직 빌더 실행 기록이 없습니다.</div>`;
    return;
  }
  const LIM = 6 * 3600;
  const stale = rows.filter((r) => r.exists && r.age_sec > LIM).length;
  const missing = rows.filter((r) => r.exists === false).length;
  // 개요가 '멈춤'(빨강)으로 세는 것과 같은 등급 — 사이드 배지도 빨강
  const bb = $("navBuilderBadge");
  bb.textContent = stale + missing ? String(stale + missing) : "";
  bb.className = "navbadge " + (stale + missing ? "bad" : "");
  $("builderSub").textContent =
    (missing ? `${missing}개 없음 · ` : "") + (stale ? `${stale}개 6시간 이상 정체` : "전부 최신");

  const label = (r) => {
    const c = cyc[r.name] || {};
    const status = c.status || (r.exists === false ? "failed" : "pending");
    return {
      pending: "이번 사이클 미실행", running: "생성 중…",
      done: `완료${secs(c.elapsed)}`, failed: `실패${c.detail ? " " + c.detail : ""}`,
      skipped: c.detail || "건너뜀",
    }[status] || status;
  };
  const labels = rows.map(label);
  const same = labels.every((l) => l === labels[0]);
  $("builderNote").textContent = same ? `이번 사이클: ${labels[0]}` : "";
  const maxAge = Math.max(LIM * 1.5, ...rows.filter((r) => r.exists).map((r) => r.age_sec || 0));
  const limPct = (100 * LIM) / maxAge;
  wrap.innerHTML =
    `<div class="brow head"><span>빌더</span><span class="btrack-lab"><i style="left:${limPct}%">6시간</i></span>` +
    `<span class="b-age">나이</span>${same ? "<span></span>" : "<span>이번 사이클</span>"}</div>` +
    rows.map((r, i) => {
      const bad = r.exists === false || r.age_sec > LIM;
      const pct = r.exists === false ? 0 : Math.max(1, (100 * (r.age_sec || 0)) / maxAge);
      const title = r.file ? `${r.file}${r.mtime ? " · " + r.mtime : ""}` : r.name;
      return `<div class="brow${bad ? " bad" : ""}" title="${esc(title)}"><span class="b-name">${bad ? "■ " : ""}${esc(r.name)}</span>` +
        `<span class="btrack"><span style="width:${pct}%"></span><i style="left:${limPct}%"></i></span>` +
        `<span class="b-age">${r.exists === false ? "파일 없음" : fmtAge(r.age_sec) + " 전"}</span>` +
        `<span class="b-st">${same ? "" : esc(labels[i])}</span></div>`;
    }).join("");
}

// 작은 숫자 칸(콘텐츠·성과) — 라벨 · 값 · 보조
function statHtml(label, val, sub, cls) {
  return `<div class="stat ${cls || ""}"><div class="s-lab">${esc(label)}</div>` +
    `<div class="s-val">${typeof val === "number" ? val.toLocaleString() : esc(val)}</div>` +
    (sub ? `<div class="s-sub">${esc(sub)}</div>` : "") + `</div>`;
}
// KPI 띠 한 칸 — 라벨 · 값 32 Light · (문제일 때) 상태 칩 · 보조
function kpiHtml({ label, val, unit, sub, lv, chip, href, labCls }) {
  const tag = href ? "a" : "div";
  return `<${tag} class="kpi"${href ? ` href="${href}"` : ""}><div class="k-lab ${labCls || ""}">${esc(label)}</div>` +
    `<div class="k-val ${lv === "bad" ? "bad" : ""}">${esc(val)}${unit ? `<span class="u">${esc(unit)}</span>` : ""}</div>` +
    (chip ? `<div class="k-chip">${chip}</div>` : "") +
    (sub ? `<div class="k-sub">${esc(sub)}</div>` : "") + `</${tag}>`;
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
  stats.innerHTML = cells.map((c) => statHtml(c.name, c.v, c.sub)).join("");
  const rows = (list, empty) =>
    (list && list.length
      ? list.slice(0, 8).map(([k, n]) =>
          `<tr><td title="${esc(k)}">${esc(k)}</td><td class="n">${n.toLocaleString()}</td></tr>`).join("")
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
  const qb = $("navQualityBadge");
  qb.textContent = anomalies.length ? String(anomalies.length) : "";
  qb.className = "navbadge " + (anomalies.length ? "warn" : "");
  // 판정은 KPI 띠 첫 칸(구석 메타로 숨기지 않는다). 이상이 있으면 목록만 아래 띠로.
  banner.className = anomalies.length ? "banner warn" : "";
  banner.innerHTML = anomalies.length
    ? `<b>! 이상 감지 ${anomalies.length}건</b><ul>` + anomalies.map((a) => `<li>${esc(a)}</li>`).join("") + `</ul>` : "";
  const verdict = !h.ts ? kpiHtml({ label: "판정", val: "기록 없음" })
    : kpiHtml({ label: `${fmtClockISO(h.ts)} 기준`, val: anomalies.length ? `! 이상 ${anomalies.length}건` : "✓ 이상 없음",
      labCls: anomalies.length ? "warn" : "" });
  const n = (v) => (v ?? 0).toLocaleString();
  $("qualityKpis").innerHTML = verdict + (h.ts
    ? kpiHtml({ label: "수집(raw)", val: n(h.raw_total) }) + kpiHtml({ label: "모집중", val: n(h.active) }) +
      kpiHtml({ label: "교차중복", val: n(h.cross_dups) }) + kpiHtml({ label: "마감", val: n(h.closed) }) : "");

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
  el.innerHTML = [
    ["주요업무", fr.main_tasks], ["자격요건", fr.qualifications],
    ["우대사항", fr.preferences], ["기술스택", fr.tech_stack],
  ].map(([k, v]) => `<div class="hrow"><div class="hk">${k}</div>${fillBar(v)}</div>`).join("");
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
      <td class="n">${(h.raw_total ?? 0).toLocaleString()}</td>
      <td class="n">${(h.active ?? 0).toLocaleString()}</td>
      <td class="n">${(h.cross_dups ?? 0).toLocaleString()}</td>
      <td class="n">${avg}%</td>
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
    case "alba_start": return `컴퓨터 알바 수집 시작`;
    case "alba_done": return `컴퓨터 알바 ${e.ok ? "완료" : "실패"} · 누적 ${e.total ?? "?"}건(모집중 ${e.open ?? "?"}, 신규 ${e.new ?? "?"}, 마감 ${e.closed_now ?? 0})${secs(e.elapsed)}`;
    case "contests_start": return `IT·디자인 공모전 수집 시작`;
    case "contests_done": return e.skipped ? `공모전 — ${e.reason === "locked" ? "마감 확인 중이라" : "12시간 안에 받아서"} 건너뜀(마감일 지나 닫음 ${e.closed_now ?? 0}건)` : `공모전 ${e.ok ? "완료" : "실패"} · 누적 ${e.total ?? "?"}건(접수중 ${e.open ?? "?"}, 신규 ${e.new ?? "?"}, 마감 ${e.closed_now ?? 0})${secs(e.elapsed)}`;
    case "contests_check": return e.skipped ? `공모전 마감 확인 — 수집 중이라 건너뜀` : `공모전 마감 확인 · 접수중 ${e.open ?? "?"}건, 이번에 마감 ${e.closed_now ?? 0}건`;
    case "alba_check": return e.skipped ? `컴퓨터 알바 마감 확인 — 회차가 도는 중이라 건너뜀` : `컴퓨터 알바 마감 확인 · 모집중 ${e.open ?? "?"}건, 이번에 마감 ${e.closed_now ?? 0}건`;
    case "refresh_start": return `${e.target === "dashboard" ? "대시보드" : "뷰어"} 갱신 시작`;
    case "refresh_done": return `${e.target === "dashboard" ? "대시보드" : "뷰어"} 갱신 ${e.ok ? "완료" : "실패"}`;
    case "cycle_done": return `사이클 완료 · ${e.new_data ? "새 데이터 반영" : "변경 없음"}${secs(e.elapsed)}`;
    case "wait": return `다음 크롤까지 ${e.interval}s 대기`;
    case "error": return `오류 [${e.where}] ${e.msg}`;
    default: {
      // 이름만 있는 단계 이벤트(builder_start·hardware_done …)도 원시 키 대신 우리 말로
      const m = /^(.+)_(start|done)$/.exec(e.type || "");
      if (m) {
        const what = EV_STAGE[m[1]] || m[1];
        const tail = e.name ? ` · ${e.name}` : "";
        return m[2] === "start" ? `${what} 시작${tail}` : `${what} ${e.ok === false ? "실패" : "완료"}${tail}${secs(e.elapsed)}`;
      }
      return e.type;
    }
  }
}
const EV_STAGE = { builder: "뷰어 빌더", prebuilt: "완제품 조립PC 수집", hardware: "부품 가격 수집", careers: "취업후기 수집" };
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

// ---- 개요 (v2) -------------------------------------------------------------
// 결론 문장 → 상태 4칸 → 먼저 고칠 것(원인 하나를 고치면 같이 풀리는 경보 수) · 단계별 상태(누르면 탭).
// 숫자는 각 탭이 쓰는 같은 API 에서만 온다 — 개요는 요약, 근거는 탭.
const LV = { bad: 0, warn: 1, unknown: 2, ok: 3 };
const ICON = { ok: "✓", warn: "!", bad: "■", unknown: "?" };
const agoSec = (sec) => (sec == null || !isFinite(sec) ? "—" : fmtAge(Math.round(sec)) + " 전");
function renderOverview() {
  const cr = OV.crawlers, db = OV.db, loops = Array.isArray(OV.loops) ? OV.loops : null, bl = OV.builders;
  if (!cr && !db) return;
  const sch = (cr && cr.scheduler) || {};
  const lds = sch.launchd || [];
  const dm = sch.daemon || {};
  const ldOf = (label) => lds.find((l) => l.label === label);
  const crawlerLd = ldOf("com.jobseeker.crawler"), closeLd = ldOf("com.jobseeker.closecheck");
  const running = dm.phase && !["waiting", "idle"].includes(dm.phase) && dm.updated_at &&
    Date.now() - new Date(dm.updated_at).getTime() < 20 * 60 * 1000;
  const newestSec = cr && cr.newest_at ? Math.max(0, (Date.now() - new Date(cr.newest_at).getTime()) / 1000) : null;

  // ── 상태 4칸
  const cells = [];
  const ldOffList = lds.filter((l) => !l.loaded);
  const schedTotal = lds.length + 1, schedOff = ldOffList.length + (dm.pid ? 0 : 1);
  const schedLv = running || (crawlerLd && crawlerLd.loaded) ? (ldOffList.length ? "warn" : "ok") : "bad";
  cells.push({ lv: schedLv, label: "크롤 스케줄러", val: schedLv === "ok" ? "정상" : `${schedOff}/${schedTotal} 꺼짐`,
    chip: schedLv === "ok" ? (running ? "지금 회차 실행 중" : "정상") : schedLv === "warn" ? "일부 꺼짐" : "꺼짐",
    sub: schedLv === "ok" ? (running ? "지금 회차 실행 중" : crawlerLd && crawlerLd.via === "windows-task" ? "작업 스케줄러가 회차를 띄웁니다" : "launchd 가 회차를 띄웁니다")
      : [dm.pid ? null : "데몬", ...ldOffList.map((l) => l.label.replace("com.jobseeker.", ""))].filter(Boolean).join(" · ") + " 꺼짐",
    tab: "crawlers" });
  let dbLv = "unknown", dbVal = "—", dbSub = "";
  if (db && db.ok) {
    const h = db.jobs.last_write_age_hours;
    dbLv = h == null ? "unknown" : h <= 3 ? "ok" : h <= 24 ? "warn" : "bad";
    dbVal = agoH(h);
    dbSub = `24시간 신규 ${db.jobs.new_24h.toLocaleString()}건 · 마지막 ${db.jobs.last_write ? db.jobs.last_write.slice(5, 16).replace("T", " ") : "—"}`;
  } else if (db) { dbLv = "bad"; dbVal = "연결 안 됨"; dbSub = "jobseeker-db 컨테이너 확인"; }
  cells.push({ lv: dbLv, label: "DB 적재", val: dbVal, sub: dbSub, tab: "db",
    chip: { ok: "정상", warn: "늦음", bad: "멈춤", unknown: "모름" }[dbLv] });
  if (cr) {
    const c = cr.counts || {}, nb = (c.stale || 0) + (c.error || 0);
    // 값 = 정상/전체 — 보조 줄에서 같은 숫자를 다시 쓰지 않는다
    cells.push({ lv: nb ? "bad" : c.warn ? "warn" : "ok", label: "크롤러 출처", val: `${c.ok || 0}/${cr.total || 0}`,
      chip: c.error ? `실패 ${c.error}곳` : c.stale ? `멈춤 ${c.stale}곳` : c.warn ? `늦음 ${c.warn}곳` : "정상",
      sub: `정상 출처 · 늦음 ${c.warn || 0} · 멈춤 ${c.stale || 0} · 실패 ${c.error || 0}`, tab: "crawlers" });
  }
  let loopBad = [], loopSched = [];
  if (loops) {
    loopBad = loops.filter((r) => r.state === "stale" || r.state === "stopped");
    loopSched = loopBad.filter((r) => r.kind === "launchd" || r.kind === "cycle");
    cells.push({ lv: loopBad.length ? "warn" : "ok", label: "반복 작업",
      val: loopBad.length ? `${loopBad.length}/${loops.length}` : `${loops.length}개`, chip: loopBad.length ? "멈춤?" : "정상",
      sub: loopSched.length ? `그중 ${loopSched.length}개는 스케줄러가 원인` : loopBad.length ? "세션·러너가 닫힘" : "모두 제때", tab: "loops" });
  }
  // 판정에 들어가는 영역 = 이 칸들. KPI 띠로 한 번만 보이고, 아래 '단계별 세부' 표에는 다시 넣지 않는다.
  // 값은 32 Light, 상태는 문제일 때만 칩(정상은 회색 ✓ 글자). 나쁜 칸이 왼쪽.
  const CHIPW = { bad: "stale", warn: "warn", unknown: "unknown", ok: "ok" };
  const sorted = cells.slice().sort((a, b) => LV[a.lv] - LV[b.lv]);
  $("ovSum").innerHTML = sorted.map((c) => kpiHtml({ label: c.label, val: c.val, lv: c.lv, href: "#" + c.tab,
    chip: `<span class="cst ${CHIPW[c.lv]}">${esc(c.chip || { ok: "정상", warn: "확인 필요", bad: "멈춤", unknown: "모름" }[c.lv])}</span>`,
    sub: c.sub })).join("");

  // ── 결론 문장 — 무엇을 셌는지 같이 말한다(위 칸 수 중 문제 칸 수)
  const nProb = cells.filter((c) => c.lv === "bad" || c.lv === "warn").length;
  const now = new Date();
  const stamp = `${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")} ` +
    `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")} 기준`;
  const stalled = newestSec != null && newestSec > 3 * 3600 && !running;
  const head = `${cells.length}개 영역 중 ${nProb}곳 확인 필요`;
  $("ovTitle").textContent = !nProb ? "모두 정상 — 제때 받고 있어요"
    : stalled ? `${head} — 수집이 ${fmtAge(Math.round(newestSec))}째 멈춰 있어요`
    : running ? `${head} — 지금 회차가 도는 중이에요` : head;
  $("ovDesc").textContent = (db && db.ok && dbLv === "bad"
    ? `공고가 DB 에 마지막으로 들어간 지 ${agoH(db.jobs.last_write_age_hours)} — 뷰어 목록이 그때 그대로입니다 · `
    : newestSec != null ? `가장 최근 수집 ${fmtAge(Math.round(newestSec))} 전 · ` : "") + stamp;

  // ── 먼저 고칠 것 — 원인 순서: 스케줄러 → DB → 멈춘 출처 묶음 → 세션 루프
  const staleBuilders = (bl || []).filter((b) => b.exists === false || b.age_sec > 6 * 3600);
  const fixes = [];
  if (crawlerLd && !crawlerLd.loaded && !running) {
    fixes.push({ t: "채용 크롤 사이클 launchd 등록", lv: "bad", p: "미등록", cmd: "deploy/setup-crawler.sh",
      eff: `함께 풀리는 것 · 크롤 단계 ${loopSched.length}개 · 뷰어 데이터 빌더 ${staleBuilders.length}개`,
      freed: loopSched.length + staleBuilders.length });
  }
  if (closeLd && !closeLd.loaded) {
    fixes.push({ t: "마감 재확인 launchd 등록", lv: "bad", p: "미등록",
      cmd: "com.jobseeker.closecheck → python -m pipeline.close_check --limit 100",
      eff: "10분마다 100건 — 마감된 공고가 목록에 남지 않게" });
  }
  if (db && !db.ok) fixes.push({ t: "정본 DB 연결", lv: "bad", p: "연결 안 됨", cmd: "docker ps  # jobseeker-db", eff: "뷰어는 정적 파일로 물러서 있어요" });
  for (const g of (cr && cr.groups) || []) {
    const bad = g.rows.filter((r) => r.state === "stale" || r.state === "error");
    if (!bad.length || (g.key === "closecheck" && closeLd && !closeLd.loaded)) continue;
    const ages = bad.map((r) => r.age_hours).filter((x) => x != null);
    fixes.push({ t: `${g.name} ${ages.length ? agoH(Math.min(...ages)) : "멈춤"}`, lv: "bad", p: `멈춤 ${bad.length}곳`,
      cmd: bad.map((r) => r.name).join(" · "), eff: bad[0].error || bad[0].detail || "", err: !!bad[0].error });
  }
  const sess = loopBad.filter((r) => r.kind === "claude-loop");
  if (sess.length) fixes.push({ t: `세션 루프 다시 띄우기 ${sess.length}개`, lv: "warn", p: "멈춤?",
    cmd: "python -m automation.loops repeat <키> --every 60m",
    eff: sess.slice(0, 4).map((r) => r.name).join(" · ") + (sess.length > 4 ? " …" : "") });
  const top = fixes.slice(0, 3);
  $("ovFixSub").textContent = top.length && top[0].freed ? `1번 하나로 경보 ${top[0].freed}개가 같이 풀려요`
    : fixes.length > 3 ? `그 밖에 ${fixes.length - 3}개` : "";
  $("ovFix").innerHTML = top.length ? top.map((f, i) => `<div class="fix">` +
    `<span class="fix-no">${i + 1}</span><div class="fix-body"><div class="fix-t"><span>${esc(f.t)}</span>` +
    `<span class="cst ${f.lv === "bad" ? "stale" : "warn"}">${esc(f.p)}</span></div>` +
    (f.eff ? `<div class="fix-eff${f.err ? " err" : ""}" title="${esc(f.eff)}">${esc(f.eff)}</div>` : "") +
    `<code class="fix-cmd" title="${esc(f.cmd)}">${esc(f.cmd)}</code></div></div>`).join("")
    : `<div class="okline">✓ 지금 고칠 것이 없어요</div>`;

  // ── 단계별 세부 — 위 KPI 칸(DB 적재·반복 작업·스케줄러·출처 합계)은 빼고, 한 단계 = 한 줄, 나쁜 것이 위
  const stages = [];
  if (bl && bl.length) {
    const ages = bl.filter((b) => b.exists).map((b) => b.age_sec);
    stages.push({ n: "뷰어 데이터 빌더", lv: staleBuilders.length ? "bad" : "ok", p: staleBuilders.length ? `${staleBuilders.length}개 멈춤` : "최신",
      last: agoSec(ages.length ? Math.min(...ages) : null), sub: `${bl.length}개 중 6시간 넘은 것 ${staleBuilders.length}`, tab: "builders" });
  }
  for (const g of (cr && cr.groups) || []) {
    const lv = groupLevel(g.rows) || "unknown", nb = g.rows.filter((r) => r.state === "stale" || r.state === "error").length;
    const ages = g.rows.map((r) => r.age_hours).filter((x) => x != null);
    stages.push({ n: g.name, lv, last: ages.length ? agoH(Math.min(...ages)) : "—",
      p: lv === "bad" ? `멈춤 ${nb}곳` : lv === "warn" ? `늦음 ${g.rows.filter((r) => r.state === "warn").length}` : lv === "ok" ? "정상" : "모름",
      sub: `${g.rows.length}곳 · ${g.rows.reduce((a, r) => a + (r.count || 0), 0).toLocaleString()}건`, tab: "crawlers" });
  }
  const h = (OV.state || {}).health_latest || {};
  if (h.ts) {
    const an = (h.anomalies || []).length, fr = Object.values(h.fill_rates || {});
    stages.push({ n: "데이터 품질", lv: an ? "warn" : "ok", p: an ? `이상 ${an}건` : "이상 없음", last: h.ts.slice(5, 16).replace("T", " "),
      sub: fr.length ? `필드 채움률 ${Math.round(Math.min(...fr) * 100)}~${Math.round(Math.max(...fr) * 100)}%` : "", tab: "quality" });
  }
  stages.sort((a, b) => LV[a.lv] - LV[b.lv]);
  $("ovStages").innerHTML = `<div class="stg head"><span>상태</span><span>단계</span><span class="r">마지막</span><span></span></div>` +
    stages.map((st) => `<a class="stg" href="#${st.tab}">` +
      `<span><span class="cst ${st.lv === "bad" ? "stale" : st.lv}">${esc(st.p)}</span></span>` +
      `<span class="stg-n"><b>${esc(st.n)}</b><small>${esc(st.sub)}</small></span>` +
      `<span class="r${st.lv === "bad" ? " badtxt" : ""}">${esc(st.last)}</span><span class="stg-arr">›</span></a>`).join("");
}

// ---- 폴링 루프 -----------------------------------------------------------

async function pollState() {
  try {
    const s = await fetchJSON("/api/state");
    lastState = s;
    OV.state = s;
    renderDaemon(s);
    renderPhase(s);
    renderCountdown(s);
    renderStepper(s);
    renderSites(s);
    renderHealth(s);
    try {
      OV.builders = await fetchJSON("/api/builders");
      renderBuilders(s, OV.builders);
    } catch (e) {
      renderBuilders(s, null);
    }
    renderOverview();
    $("connState").textContent = "연결됨";
    $("connState").className = "conn";
    document.body.classList.remove("offline");
  } catch (e) {
    // 끊기면 화면 값은 '마지막 값'이다 — 회색으로 눌러 지금 값처럼 읽히지 않게 하고 헤더 알약도 바꾼다
    $("connState").textContent = "서버 연결 끊김 — python -m servers.ops.server 가 떠 있는지 확인";
    $("connState").className = "conn off";
    document.body.classList.add("offline");
    $("liveDot").className = "dot";
    $("daemonText").textContent = lastState && lastState.updated_at ? `마지막 확인 · ${ago(lastState.updated_at)}` : "연결 끊김";
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
    stats.innerHTML = `<div class="muted">다음 할 일 — <code>python3 guide-engine/autoguide.py --all</code> 로 만듭니다.</div>`;
    tbody.innerHTML = "";
    $("autoguideTable").classList.add("hide");
    return;
  }
  $("autoguideTable").classList.remove("hide");
  const stale = a.age_sec > 24 * 3600;
  $("autoguideSub").textContent =
    `${fmtAge(a.age_sec)} 전 생성${stale ? " · 하루 넘음, 다시 돌릴 때" : ""}`;

  const cards = [
    ["회사", a.companies], ["공고", a.postings],
    ["중복 뺀 자리", a.distinct_active], ["본문 있음", a.with_body],
    ["규모 근거", a.with_facts], ["연봉 근거", a.with_salary],
  ];
  stats.innerHTML = cards.map(([label, n]) => statHtml(label, n ?? 0)).join("");

  tbody.innerHTML = (a.top || []).map((c) =>
    `<tr><td>${esc(c.name)}</td><td class="n">${c.active}</td><td class="n">${c.distinct}</td>` +
    `<td class="n">${(c.body ?? 0).toLocaleString()}</td>` +
    `<td class="n">${c.facts ? "O" : "—"}</td><td class="n">${c.salary ? "O" : "—"}</td></tr>`).join("");
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
      `<div class="muted">다음 할 일 — <code>./deploy/setup-publisher.sh</code> 로 데몬을 등록하고 <code>publish.cli approve</code> 로 포스터를 승인합니다.</div>`;
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
    : `<div class="okline" style="margin-bottom:12px">✓ 정상 — 예약대로 올라갑니다</div>`;

  const quota = s.quota ? `${s.quota.used}/${s.quota.limit}` : "—";
  const token = s.token_days_left == null ? "—" : `${s.token_days_left}일`;
  const cards = [
    ["예약", (c.scheduled ?? 0) + (c.approved ?? 0), ""],
    ["게시됨", c.published ?? 0, ""],
    ["연습 발행", c.rehearsed ?? 0, ""],
    ["실패", c.failed ?? 0, c.failed ? "bad" : ""],
    ["24시간 한도", quota, ""],
    ["토큰 남은 날", token, s.token_days_left != null && s.token_days_left <= 7 ? "bad" : ""],
  ];
  $("igStats").innerHTML = cards.map(([label, n, cls]) => statHtml(label, n, "", cls)).join("");

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
  const KIND = { launchd: "launchd", cycle: "크롤 단계", "claude-loop": "/loop 엔진", task: "윈도우 작업" };
  const STATE = { ok: "정상", stale: "멈춤?", stopped: "꺼짐", unknown: "모름" };
  const bad = rows.filter((r) => r.state === "stale" || r.state === "stopped");
  const lb = $("navLoopsBadge");
  lb.textContent = bad.length ? String(bad.length) : "";
  lb.className = "navbadge " + (bad.length ? "warn" : "");
  $("loopsSub").textContent = `전체 ${rows.length}`;
  // 멈춘 것을 원인별로 묶는다 — 스케줄러(launchd·크롤 단계)가 꺼진 것은 '먼저 고칠 것' 하나로 같이 풀리고,
  // /loop·repeat 엔진은 세션·러너가 닫혀서 멈춘다. 정상·모름은 접어 둔다.
  // /loop 엔진의 재시작 명령은 키만 다르다 — 명령은 묶음 위에 한 번, 줄에는 키만.
  const sched = bad.filter((r) => r.kind === "launchd" || r.kind === "cycle");
  const sess = bad.filter((r) => !(r.kind === "launchd" || r.kind === "cycle"));
  const age = (r) => (r.age_hours == null ? "—" : fmtAge(Math.round(r.age_hours * 3600)) + " 전");
  const TPL = "python -m automation.loops repeat <키> --every 60m";
  const grp = (title, desc, lv, list, tpl) => {
    if (!list.length) return "";
    const kinds = [...new Set(list.map((r) => r.kind))];
    const body = kinds.map((k) => {
      const part = list.filter((r) => r.kind === k);
      return (kinds.length > 1 || k !== "claude-loop" ? `<tr class="kind"><td colspan="3">${esc(KIND[k] || k)} · ${part.length}개</td></tr>` : "") +
        part.map((r) => `<tr title="${esc(r.note || "")}"><td>${esc(r.name)}</td>` +
          `<td class="key" title="${esc(r.kind === "claude-loop" ? r.key : r.run)}">${esc(r.kind === "claude-loop" ? r.key : r.run)}</td>` +
          `<td class="n age">${age(r)}</td></tr>`).join("");
    }).join("");
    return `<section class="panel lgroup ${lv}"><div class="mhead"><h3>${title}</h3>` +
      `<span class="cst ${lv === "bad" ? "stale" : "warn"}">${list.length}개 확인 필요</span></div>` +
      `<p class="lg-desc">${desc}</p>` + (tpl ? `<div class="lg-cmd"><code>${esc(tpl)}</code></div>` : "") +
      `<div class="tablewrap"><table class="tbl"><thead><tr><th>작업</th><th>${tpl ? "&lt;키&gt; · 명령" : "명령"}</th><th class="n">마지막</th></tr></thead>` +
      `<tbody>${body}</tbody></table></div></section>`;
  };
  $("loopGroups").innerHTML = bad.length
    ? grp("스케줄러가 꺼져서 멈춤", "개요의 '먼저 고칠 것'(launchd 등록)으로 같이 풀려요.", "bad", sched, "") +
      grp("세션·러너가 닫혀서 멈춤", "/loop 엔진은 세션이 닫히면 멈춰요 — repeat 러너로 다시 띄웁니다.", "off", sess,
        sess.some((r) => r.kind === "claude-loop") ? TPL : "")
    : `<section class="panel"><div class="okline">✓ 반복 작업 ${rows.length}개 모두 정상</div></section>`;
  // 진행률이 있는 엔진(직무 역설계 등) — 몇 개 끝났고 몇 개 남았나, 지금 몇 개를 쓰는 중인가, 오늘 회차·비용.
  $("loopProgress").innerHTML = rows.filter((r) => r.progress).map((r) => {
    const p = r.progress;
    const pct = p.total ? (p.done / p.total) * 100 : 0;
    const lr = r.last_run;
    const last = lr ? `마지막 회차 ${lr.ok ? "성공" : "실패"} · ${Math.round((lr.seconds || 0) / 60)}분 · $${(lr.cost_usd || 0).toFixed(2)}` +
      (lr.started ? ` · ${esc(lr.started.slice(11, 16))} 시작` : "") : "아직 회차 기록 없음";
    return `<section class="panel lprog">` +
      `<div class="lp-h"><b>${esc(r.name)}</b><span class="lp-busy${p.busy ? " on" : ""}">${p.busy ? `● 지금 ${p.busy}개 쓰는 중` : "○ 쉬는 중"}</span></div>` +
      `<div class="lp-key">${esc(r.key)} · ${esc(r.cadence)}</div>` +
      `<div class="lp-nums"><span class="lp-big">${p.done.toLocaleString()}</span><span class="muted"> / ${p.total.toLocaleString()} (${pct < 1 ? pct.toFixed(2) : pct.toFixed(1)}%)</span></div>` +
      `<div class="lp-bar" role="progressbar" aria-valuenow="${p.done}" aria-valuemax="${p.total}"><i style="width:${Math.max(pct, 0.4)}%"></i></div>` +
      `<div class="lp-meta">오늘 ${p.today_ok}/${p.today_runs}회 성공 · $${p.today_cost.toFixed(1)} · 풀이가 붙은 공고 ${p.jobs}건 · ${last}</div>` +
      `</section>`;
  }).join("");
  const rest = rows.filter((r) => !bad.includes(r));
  const nOk = rest.filter((r) => r.state === "ok").length;
  $("loopOkSum").textContent = `정상 ${nOk}개 · 모름 ${rest.length - nOk}개 — 펼쳐서 보기`;
  tb.innerHTML = "";
  for (const r of rest) {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td><span class="cst ${r.state === "ok" ? "ok" : "unknown"}">${STATE[r.state] || r.state}</span></td>` +
      `<td>${KIND[r.kind] || r.kind}</td>` +
      `<td title="${esc(r.note || "")}">${esc(r.name)}<small>${esc(r.key)}${r.backlog ? " · " + esc(r.backlog) : ""}</small></td>` +
      `<td>${esc(r.cadence)}</td>` +
      `<td class="nowrap">${age(r)}</td>` +
      `<td><small>${esc(r.kind === "claude-loop" ? "python -m automation.loops prompt " + r.key : r.run)}</small></td>`;
    tb.appendChild(tr);
  }
}

async function pollLoops() {
  try { OV.loops = await fetchJSON("/api/loops"); renderLoops(OV.loops); renderOverview(); } catch (_) {}
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
  OV.crawlers = d;
  const c = d.counts || {};
  const bad = (c.stale || 0) + (c.error || 0);
  // KPI 띠: 출처 수 · 정상 · 늦음 · 멈춤 · 실패 — 라벨이 아이콘+색, 값은 문제일 때만 빨강
  $("crawlKpis").innerHTML =
    kpiHtml({ label: "출처", val: (d.total || 0).toLocaleString(), unit: "곳" }) +
    kpiHtml({ label: "✓ 정상", val: String(c.ok || 0) }) +
    kpiHtml({ label: "! 늦음", val: String(c.warn || 0), labCls: "warn" }) +
    kpiHtml({ label: "■ 멈춤", val: String(c.stale || 0), labCls: "bad", lv: c.stale ? "bad" : "" }) +
    kpiHtml({ label: "■ 실패", val: String(c.error || 0), labCls: "bad", lv: c.error ? "bad" : "" });

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

  // (헤더의 '확인 필요 N곳' 알약은 없앴다 — 같은 사실이 사이드 크롤러 배지와 개요 제목에 있다)
  $("heroAge").className = "k-val " + (level === "bad" ? "bad" : "");
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

  // ── 묶음 표 — 한 묶음 = 한 줄(상태 · 이름 · 정상 출처 · 건수 · 마지막). 문제 묶음만 펼쳐 출처 표를 들여 보인다.
  const groups = d.groups || [];
  $("crawlGroups").innerHTML =
    `<div class="ghead"><span></span><span>상태</span><span>묶음</span><span class="n">정상 출처</span><span class="n">건수</span><span class="n">마지막</span></div>` +
    groups.map((g) => {
      const lv = groupLevel(g.rows);
      const open = g.key in groupOpen ? groupOpen[g.key] : lv === "bad" && g.rows.length <= 12;
      const rows = g.rows.slice().sort((a, b) =>
        (SEVERITY[a.state] ?? 9) - (SEVERITY[b.state] ?? 9) || (b.count || 0) - (a.count || 0));
      const nb = rows.filter((r) => r.state === "stale" || r.state === "error").length;
      const nOk = rows.filter((r) => r.state === "ok").length;
      const sum = rows.reduce((a, r) => a + (r.count || 0), 0);
      const ages = rows.map((r) => r.age_hours).filter((x) => x != null);
      const body = rows.map((r) =>
        `<tr><td><span class="cst ${r.state}">${CST[r.state] || r.state}</span></td>` +
        `<td>${esc(r.name)}</td>` +
        `<td class="n">${r.count == null ? "—" : r.count.toLocaleString()}</td>` +
        `<td class="n">${r.age_hours == null ? "—" : fmtAge(Math.round(r.age_hours * 3600)) + " 전"}</td>` +
        `<td class="n muted">${esc(r.detail)}</td>` +
        `<td class="err"><span class="clamp" title="${esc(r.error)}">${esc(r.error)}</span></td></tr>`).join("");
      return `<details class="cgroup" data-g="${esc(g.key)}"${open ? " open" : ""}>` +
        `<summary><span><span class="cst ${lv === "bad" ? "stale" : lv || "unknown"}">${lv === "bad" ? nb + "곳 문제" : lv === "warn" ? "늦음" : "정상"}</span></span>` +
        `<span class="g-name">${esc(g.name)}</span><span class="n">${nOk}/${rows.length}곳 정상</span>` +
        `<span class="n">${sum.toLocaleString()}건</span><span class="n">${ages.length ? agoH(Math.min(...ages)) : "—"}</span></summary>` +
        `<div class="cwrap"><table class="ctable">` +
        `<colgroup><col class="c-st"><col class="c-nm"><col class="c-n"><col class="c-age"><col class="c-dt"><col></colgroup>` +
        `<thead><tr><th>상태</th><th>출처</th><th class="n">건수</th><th class="n">마지막</th><th class="n">세부</th><th>오류</th></tr></thead>` +
        `<tbody>${body}</tbody></table></div></details>`;
    }).join("");

  // ── 스케줄러 — 칸 셋(데몬 · 작업들). 종료코드가 0 이 아니면 이유를 글로 적는다(색만으로 말하지 않는다)
  const tiles = [
    { name: "auto_crawl 데몬", val: dm.pid ? "✓ 살아 있음" : "꺼짐",
      sub: dm.pid ? `pid ${dm.pid} · ${dm.phase || ""}` : "launchd 가 회차를 띄운다" },
    ...lds.map((l) => {
      const exitOk = l.last_exit === "0" || l.last_exit === "(never exited)" || l.last_exit == null;
      return {
        name: l.label.replace("com.jobseeker.", l.via === "windows-task" ? "작업 스케줄러 · " : "launchd · "),
        val: l.loaded ? (l.pid ? "실행 중" : "✓ 등록됨") : "■ 미등록",
        sub: l.loaded ? `실행 ${l.runs ?? "—"}회 · ${(l.interval || "").replace(" seconds", "초 주기")}` : "setup 스크립트 필요",
        badLine: !l.loaded ? "" : exitOk ? "" : `■ 종료코드 ${l.last_exit}`,
        bad: !l.loaded,
      };
    }),
  ];
  $("crawlSched").innerHTML = tiles.map((t) =>
    `<div class="sch"><div class="s-name">${esc(t.name)}</div>` +
    `<div class="s-val"${t.bad ? ' style="color:var(--bad)"' : ""}>${esc(t.val)}</div><div class="s-sub">${esc(t.sub)}</div>` +
    (t.badLine ? `<div class="s-bad">${esc(t.badLine)}</div>` : "") + `</div>`).join("");

  if (lastState) renderDaemon(lastState);
  renderOverview();
}

$("crawlGroups").addEventListener("toggle", (e) => {
  const el = e.target.closest && e.target.closest("details.cgroup");
  if (el) groupOpen[el.dataset.g] = el.open;
}, true);
async function pollCrawlers() {
  try { renderCrawlers(await fetchJSON("/api/crawlers")); } catch (e) {
    $("crawlBanner").innerHTML = `<div class="banner bad">■ 크롤러 상태를 읽지 못했습니다 — ${esc(e.message)}</div>`;
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
// 구역 탭 — 주소의 #해시가 탭이다(#builders-sec·#guide 같은 옛 구역 이름도 그 탭으로 간다).
const TAB_ALIAS = { "builders-sec": "builders", autoguide: "content", guide: "content", visits: "perf", social: "perf" };
function showTab() {
  const h = (location.hash || "#overview").slice(1);
  const tab = TAB_ALIAS[h] || (document.querySelector(`#tabs a[data-tab="${h}"]`) ? h : "overview");
  document.querySelectorAll("main .page").forEach((el) => el.classList.toggle("hide", el.dataset.tab !== tab));
  document.querySelectorAll("#tabs a").forEach((a) => {
    const on = a.dataset.tab === tab;
    a.classList.toggle("active", on);
    if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  window.scrollTo(0, 0);
}
window.addEventListener("hashchange", showTab);
showTab();

// DB 저장 현황 — 정본 DB 에 실제로 들어간 것. 뷰어 목록은 이 숫자를 보여준다.
const SITE_LABEL = { wanted: "원티드", jumpit: "점핏", jobkorea: "잡코리아", saramin: "사람인", dev: "캐치",
  remote: "해외 원격", ats: "회사 채용페이지", boards: "기타 보드·공공" };
function cstBadge(state) { return `<span class="cst ${state}">${CST[state] || state}</span>`; }
function agoH(h) { return h == null ? "—" : fmtAge(Math.round(h * 3600)) + " 전"; }
function renderDb(d) {
  OV.db = d;
  renderOverview();
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
  const fl = d.tables.find((t) => t.key === "project");
  const lastLv = lv === "stale" ? "bad" : lv;
  $("dbTiles").innerHTML =
    kpiHtml({ label: "모집중 공고", val: j.active.toLocaleString(), sub: `전체 ${j.total.toLocaleString()}건` }) +
    kpiHtml({ label: "24시간 신규", val: j.new_24h.toLocaleString(), sub: "처음 본 공고" }) +
    kpiHtml({ label: "마지막 공고 적재", val: agoH(j.last_write_age_hours), lv: lastLv,
      chip: lastLv === "ok" ? "" : `<span class="cst ${lastLv === "bad" ? "stale" : lastLv}">${{ warn: "늦음", bad: "멈춤", unknown: "모름" }[lastLv]}</span>`,
      sub: j.last_write ? j.last_write.slice(5, 16).replace("T", " ") : "—" }) +
    (fl && fl.total != null ? kpiHtml({ label: "외주 프로젝트", val: (fl.sub ?? 0).toLocaleString(), sub: `모집중 · 24시간 신규 ${fl.new_24h}` }) : "");

  document.querySelector("#dbSites tbody").innerHTML = d.sites.map((s) =>
    `<tr><td>${esc(SITE_LABEL[s.site] || s.site)}</td><td>${cstBadge(s.state)}</td>` +
    `<td class="n">${s.active.toLocaleString()}</td><td class="n">${s.total.toLocaleString()}</td>` +
    `<td class="n">${s.new_24h ? "+" + s.new_24h.toLocaleString() : "0"}</td><td class="n">${agoH(s.age_hours)}</td></tr>`).join("");

  const SUB = { project: "모집중", job_state: "마감", hw_price_day: "부품" };
  document.querySelector("#dbTables tbody").innerHTML = d.tables.map((t) => t.error
    ? `<tr><td>${esc(t.name)}</td><td>${cstBadge("error")}</td><td colspan="3" class="muted">${esc(t.error)}</td></tr>`
    : `<tr><td>${esc(t.name)}</td><td>${cstBadge(t.state)}</td>` +
      `<td class="n">${t.total.toLocaleString()}${t.sub != null && SUB[t.key] ? ` <span class="muted">· ${SUB[t.key]} ${t.sub.toLocaleString()}</span>` : ""}</td>` +
      `<td class="n">${t.new_24h.toLocaleString()}</td><td class="n">${agoH(t.age_hours)}</td></tr>`).join("");

  // 신규 막대 — 한 색, 가장 큰 회차만 진하게(숫자가 이미 말하니 막대는 비교만)
  const maxNew = Math.max(1, ...d.runs.map((r) => r.n_new || 0));
  document.querySelector("#dbRuns tbody").innerHTML = d.runs.map((r) =>
    `<tr><td>${esc((r.started_at || "").slice(5, 16).replace("T", " "))}</td>` +
    `<td>${r.ok ? cstBadge("ok") : cstBadge("error")}</td>` +
    `<td class="n">${(r.n_raw || 0).toLocaleString()}</td><td class="n">${(r.n_upserted || 0).toLocaleString()}</td>` +
    `<td class="n">+${(r.n_new || 0).toLocaleString()}</td>` +
    `<td><div class="minibar${(r.n_new || 0) === maxNew ? " max" : ""}" title="신규 ${r.n_new}"><span style="width:${Math.round(100 * (r.n_new || 0) / maxNew)}%"></span></div></td></tr>`).join("");
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
  $("guideStats").innerHTML = cards.map(([label, n]) => statHtml(label, n)).join("");
  const doing = cs.filter((c) => c.status !== "done").map((c) => esc(c.name));
  $("guideQueue").innerHTML =
    (doing.length ? `진행 중: <b>${doing.join(", ")}</b><br>` : "") +
    ((g.queue || []).length ? g.queue.map((q) => esc(q.name)).join(" → ") : `<span class="muted">대기열 비어 있음</span>`);

  // 작은 상자 안 스크롤 대신 페이지 스크롤 — 처음엔 20곳만, 나머지는 '더 보기'(검색하면 맞는 곳 전부)
  const q = ($("guideFilter").value || "").trim().toLowerCase();
  const all = cs.filter((c) => !q || `${c.name} ${c.name_en} ${c.one_liner}`.toLowerCase().includes(q));
  const rows = q || guideAll ? all : all.slice(0, 20);
  const more = $("guideMore");
  more.classList.toggle("hide", rows.length >= all.length);
  more.textContent = `나머지 ${all.length - rows.length}곳 더 보기`;
  $("guideTable").querySelector("tbody").innerHTML = rows.map((c, i) => {
    const tag = c.status === "done" ? "" : `<span class="tag">진행 중</span>`;
    const posts = (c.posting_list || []).map((p) =>
      `<li><span class="muted">${esc(p.site)}</span> ` +
      (p.url ? `<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.title)}</a>` : esc(p.title)) + `</li>`).join("");
    return `<tr class="guiderow" data-i="${i}"><td class="nowrap"><b>${esc(c.name)}</b>${tag}` +
      `${c.name_en ? `<small>${esc(c.name_en)}</small>` : ""}</td>` +
      `<td>${esc((c.one_liner || "").replace(/\*\*/g, ""))}</td><td class="n">${c.postings}</td><td class="n">${c.study_items}</td>` +
      `<td class="n">${c.salary ? "O" : "—"}</td><td class="n muted">${esc(c.updated_at)}</td></tr>` +
      `<tr class="guidedetail hide" data-for="${i}"><td colspan="6"><ul>${posts || "<li class=muted>공고 없음</li>"}</ul>` +
      `<div class="muted">공개 인물 ${c.people}명</div></td></tr>`;
  }).join("") || `<tr><td colspan="6" class="muted">맞는 회사가 없습니다</td></tr>`;
}
let guideAll = false;
$("guideFilter").addEventListener("input", () => renderGuide());
$("guideMore").addEventListener("click", () => { guideAll = true; renderGuide(); });
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
