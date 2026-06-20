"use strict";

// ── API 헬퍼 ────────────────────────────────────────────────
async function api(path, opts) {
  const res = await fetch(path, opts);
  let data = null;
  try { data = await res.json(); } catch (e) { /* no body */ }
  if (!res.ok) throw new Error((data && data.error) || res.statusText);
  return data;
}
const getJSON = (p) => api(p);
const postJSON = (p, body) => api(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
const patchJSON = (p, body) => api(p, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
const del = (p) => api(p, { method: "DELETE" });

const el = (tag, attrs, ...kids) => {
  const n = document.createElement(tag);
  if (attrs) for (const k in attrs) {
    if (k === "class") n.className = attrs[k];
    else if (k === "html") n.innerHTML = attrs[k];
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), attrs[k]);
    else if (attrs[k] != null) n.setAttribute(k, attrs[k]);
  }
  for (const c of kids) if (c != null) n.append(c.nodeType ? c : document.createTextNode(c));
  return n;
};
const esc = (s) => (s == null ? "" : String(s));

let toastTimer;
function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg; t.classList.remove("hide");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.add("hide"), 3500);
}

// ── 라우팅 ──────────────────────────────────────────────────
const TABS = [
  { id: "jobs", label: "JD 검색·생성" },
  { id: "forms", label: "지원 폼" },
  { id: "watch", label: "재공고 추적" },
  { id: "profile", label: "사실 프로필" },
  { id: "apps", label: "지원 현황" },
  { id: "settings", label: "설정" },
];
let current = "jobs";

function renderNav() {
  const nav = document.getElementById("nav");
  nav.innerHTML = "";
  TABS.forEach((t) => nav.append(el("button", {
    class: t.id === current ? "active" : "",
    onclick: () => { current = t.id; route(); },
  }, t.label)));
}
function route() {
  renderNav();
  const v = document.getElementById("view");
  v.innerHTML = "";
  ({ jobs: viewJobs, forms: viewForms, watch: viewWatch, profile: viewProfile, apps: viewApps, settings: viewSettings }[current])(v);
}

async function refreshAIState() {
  try {
    const h = await getJSON("/api/health");
    document.getElementById("aistate").textContent = h.ai ? "AI 키: 설정됨" : "AI 키 없음 — 설정 탭에서 입력";
  } catch (e) { /* */ }
}

// ── JD 검색 + 적합도 + 생성 ─────────────────────────────────
function viewJobs(v) {
  const left = el("div", { class: "col" });
  const right = el("div", { class: "col" });
  v.append(el("div", { class: "row" }, left, right));

  const input = el("input", { placeholder: "회사·직무·기술 검색 (예: react 백엔드)", onkeydown: (e) => { if (e.key === "Enter") search(); } });
  const listBox = el("div", { class: "joblist" });
  left.append(el("div", { class: "card" },
    el("h2", null, "채용공고 검색"),
    el("div", { class: "flex" }, input, el("button", { class: "btn", onclick: () => search() }, "검색")),
    el("div", { class: "muted small", style: "margin:8px 0" }, "크롤된 공고에서 검색합니다."),
    listBox));

  const detail = el("div", { class: "card" }, el("div", { class: "muted" }, "왼쪽에서 공고를 선택하세요."));
  right.append(detail);

  async function search() {
    listBox.innerHTML = "검색 중…";
    try {
      const r = await getJSON("/api/jobs?limit=40&q=" + encodeURIComponent(input.value || ""));
      listBox.innerHTML = "";
      listBox.append(el("div", { class: "muted small", style: "margin-bottom:8px" }, `${r.total}건 중 ${r.count}건`));
      r.items.forEach((j) => listBox.append(el("div", { class: "jobitem", onclick: () => openJob(j.key, detail) },
        el("div", { class: "co" }, esc(j.company)),
        el("div", { class: "ti" }, esc(j.title)),
        el("div", { class: "small muted" }, [j.career, j.location, j.dday].filter(Boolean).join(" · ")))));
    } catch (e) { listBox.innerHTML = ""; listBox.append(el("div", { class: "muted" }, "오류: " + e.message)); }
  }
  search();
}

async function openJob(key, detail) {
  detail.innerHTML = "불러오는 중…";
  let job;
  try { job = await getJSON("/api/job?key=" + encodeURIComponent(key)); }
  catch (e) { detail.innerHTML = ""; detail.append(el("div", { class: "muted" }, "오류: " + e.message)); return; }
  detail.innerHTML = "";
  detail.append(el("h2", null, esc(job.company)));
  detail.append(el("div", { class: "muted", style: "margin-bottom:8px" }, esc(job.title)));
  if (job.url) detail.append(el("div", { style: "margin-bottom:8px" }, el("a", { href: job.url, target: "_blank" }, "공고 원문 ↗")));
  (job.tech_stack || "").toString().split(/[,\s]+/).filter(Boolean).slice(0, 20)
    .forEach((t) => detail.append(el("span", { class: "chip" }, t)));

  const out = el("div", { style: "margin-top:12px" });
  const actions = el("div", { class: "flex", style: "margin-top:12px; flex-wrap:wrap" },
    el("button", { class: "btn sm", onclick: () => doAnalyze(key, out) }, "적합도 분석"),
    el("button", { class: "btn sm", onclick: () => doGenerate(key, "resume", out) }, "이력서 생성"),
    el("button", { class: "btn sm", onclick: () => doGenerate(key, "cover_letter", out) }, "자기소개서 생성"),
    el("button", { class: "btn sm ghost", onclick: () => addToApps(job) }, "지원에 추가"),
    el("button", { class: "btn sm ghost", onclick: () => addToWatch(job) }, "재공고 추적"));
  detail.append(actions, out);

  const tasks = el("div", { class: "small muted", style: "margin-top:10px; white-space:pre-wrap" },
    "주요업무: " + esc((job.main_tasks || "").toString().slice(0, 400)) +
    "\n\n자격요건: " + esc((job.qualifications || "").toString().slice(0, 400)));
  detail.append(tasks);
}

async function doAnalyze(key, out) {
  out.innerHTML = "<div class='muted'>분석 중… (AI 호출, 수초 소요)</div>";
  try {
    const r = await postJSON("/api/analyze", { key });
    const cls = r.fit_score >= 70 ? "good" : r.fit_score >= 45 ? "mid" : "low";
    out.innerHTML = "";
    out.append(el("div", { class: "card" },
      el("div", { class: "flex" }, el("span", { class: "score " + cls }, r.fit_score + "점"),
        el("div", { class: "muted small" }, esc(r.summary))),
      el("h2", { style: "margin-top:12px" }, "충족 (프로필 근거 있음)"),
      el("ul", { class: "matched" }, ...(r.matched || []).map((m) => el("li", null, `${m.requirement} — ${m.evidence}`))),
      el("h2", null, "갭 (근거 없음 / 보완 필요)"),
      el("ul", { class: "gaps" }, ...(r.gaps || []).map((g) => el("li", null, `${g.requirement} — ${g.note}`))),
      (r.missing_skills || []).length ? el("div", null, el("b", null, "부족 스킬: "), (r.missing_skills || []).join(", ")) : null,
      el("p", { class: "muted" }, esc(r.recommendation))));
  } catch (e) { out.innerHTML = "<div class='muted'>오류: " + esc(e.message) + "</div>"; }
}

async function doGenerate(key, kind, out) {
  out.innerHTML = "<div class='muted'>생성 중… (AI 호출, 십수초 소요될 수 있음)</div>";
  try {
    const r = await postJSON("/api/generate", { key, kind });
    out.innerHTML = "";
    out.append(el("div", { class: "card" },
      el("h2", null, (kind === "resume" ? "이력서" : "자기소개서") + " 초안 #" + r.resume_id),
      el("pre", { class: "doc" }, esc(r.document)),
      el("button", { class: "btn sm ghost", onclick: () => { navigator.clipboard.writeText(r.document); toast("복사됨"); } }, "본문 복사"),
      (r.gaps || []).length ? el("div", { style: "margin-top:12px" }, el("h2", null, "⚠ 사실 근거가 없어 비운 항목"),
        el("ul", { class: "gaps" }, ...(r.gaps || []).map((g) => el("li", null, `${g.wanted} — ${g.note}`)))) : null,
      (r.facts_used || []).length ? el("div", { class: "small muted", style: "margin-top:8px" }, "사용한 사실: " + (r.facts_used || []).join("; ")) : null));
  } catch (e) { out.innerHTML = "<div class='muted'>오류: " + esc(e.message) + "</div>"; }
}

async function addToApps(job) {
  try {
    await postJSON("/api/applications", { job: { site: job.site, idx: job.idx, company: job.company, title: job.title, url: job.url }, status: "관심" });
    toast("지원 현황에 추가됨");
  } catch (e) { toast("오류: " + e.message); }
}

async function addToWatch(job) {
  try {
    await postJSON("/api/watchlist", { key: job.key || (job.site + ":" + job.idx), company: job.company });
    toast("재공고 추적에 추가됨 (JD 스냅샷 저장)");
  } catch (e) { toast("오류: " + e.message); }
}

// ── 재공고 추적 (워치리스트) ─────────────────────────────────
async function viewWatch(v) {
  // 추가 폼
  const co = el("input", { placeholder: "회사명 (예: 토스)", style: "max-width:220px" });
  const kw = el("input", { placeholder: "직무·기술 키워드 (예: 백엔드 java)", style: "max-width:260px" });
  const note = el("input", { placeholder: "메모 (선택)" });
  v.append(el("div", { class: "card" },
    el("h2", null, "재공고 추적 추가"),
    el("div", { class: "muted small", style: "margin-bottom:8px" }, "관심 회사·직무를 등록해두면, 같은 조건의 공고가 다시 열렸는지 확인할 수 있습니다. (JD 상세의 '재공고 추적' 버튼을 쓰면 그 공고 내용까지 스냅샷으로 보관)"),
    el("div", { class: "flex", style: "flex-wrap:wrap" }, co, kw),
    el("div", { style: "margin-top:8px" }, note),
    el("div", { style: "margin-top:8px" }, el("button", { class: "btn", onclick: async () => {
      if (!co.value.trim() && !kw.value.trim()) { toast("회사 또는 키워드를 입력하세요"); return; }
      try { await postJSON("/api/watchlist", { company: co.value.trim(), keyword: kw.value.trim(), note: note.value.trim() }); toast("추가됨"); route(); }
      catch (e) { toast("오류: " + e.message); }
    } }, "추가"))));

  // 목록 + 전체 확인
  let data;
  try { data = await getJSON("/api/watchlist"); } catch (e) { v.append(el("div", { class: "muted" }, "오류: " + e.message)); return; }
  const listCard = el("div", { class: "card" },
    el("div", { class: "flex" }, el("h2", null, "추적 목록"), el("span", { class: "spacer" }),
      data.items.length ? el("button", { class: "btn sm", onclick: () => checkAll() }, "전체 재등장 확인") : null));
  if (!data.items.length) listCard.append(el("div", { class: "muted" }, "아직 추적 항목이 없습니다."));

  const rowOf = (w) => {
    const out = el("div");
    const snap = w.snapshot || {};
    return el("div", { class: "rowitem", id: "watch-" + w.id },
      el("div", { class: "flex" },
        el("div", null,
          el("b", null, esc(w.company || "(회사 미지정)") + (w.keyword ? " · " + esc(w.keyword) : "")),
          snap.title ? el("div", { class: "small muted" }, "스냅샷: " + esc(snap.title) + (snap.url ? "" : "")) : null,
          w.note ? el("div", { class: "small muted" }, "메모: " + esc(w.note)) : null,
          el("div", { class: "small muted" }, "등록 " + esc((w.created_at || "").slice(0, 10)))),
        el("span", { class: "spacer" }),
        snap.url ? el("a", { href: snap.url, target: "_blank", class: "small" }, "스냅샷 원문 ↗") : null),
      el("div", { class: "flex", style: "margin-top:8px; flex-wrap:wrap" },
        el("button", { class: "btn sm", onclick: () => checkOne(w.id, out) }, "지금 떴나 확인"),
        snap.qualifications ? el("button", { class: "btn sm ghost", onclick: () => { out.innerHTML = ""; out.append(el("pre", { class: "doc" }, "자격요건:\n" + esc(snap.qualifications) + "\n\n우대:\n" + esc(snap.preferences || ""))); } }, "보관된 요구사항") : null,
        el("button", { class: "btn sm ghost", onclick: async () => { if (confirm("삭제할까요?")) { await del("/api/watchlist?id=" + w.id); route(); } } }, "삭제")),
      out);
  };
  // 년도별 그룹
  const byYear = {};
  data.items.forEach((w) => { const y = (w.year || (w.created_at || "").slice(0, 4)) || "기타"; (byYear[y] = byYear[y] || []).push(w); });
  Object.keys(byYear).sort((a, b) => b.localeCompare(a)).forEach((y) => {
    listCard.append(el("div", { class: "small muted", style: "margin:14px 0 6px; border-top:1px solid var(--line); padding-top:10px" },
      (y === "기타" ? "연도 미상" : y + "년") + " · " + byYear[y].length + "건"));
    byYear[y].slice().reverse().forEach((w) => listCard.append(rowOf(w)));
  });
  v.append(listCard);
}

function renderMatches(matches, out) {
  out.innerHTML = "";
  if (!matches.length) { out.append(el("div", { class: "small muted", style: "margin-top:6px" }, "지금 열려있는 매칭 공고 없음.")); return; }
  out.append(el("div", { class: "small", style: "margin-top:6px; color:var(--good)" }, "🔔 지금 열려있는 매칭 공고 " + matches.length + "건:"));
  matches.forEach((m) => out.append(el("div", { class: "small", style: "margin-left:6px" },
    "• " + esc(m.company) + " — ", m.url ? el("a", { href: m.url, target: "_blank" }, esc(m.title)) : esc(m.title),
    m.dday ? el("span", { class: "muted" }, "  (" + esc(m.dday) + ")") : null)));
}

async function checkOne(id, out) {
  out.innerHTML = "<div class='muted small'>확인 중…</div>";
  try { const r = await postJSON("/api/watchlist/check", { id }); renderMatches((r.results[0] || {}).matches || [], out); }
  catch (e) { out.innerHTML = "<div class='muted small'>오류: " + esc(e.message) + "</div>"; }
}

async function checkAll() {
  toast("전체 확인 중…");
  try {
    const r = await postJSON("/api/watchlist/check", {});
    let hit = 0;
    (r.results || []).forEach((res) => {
      const row = document.getElementById("watch-" + res.id);
      if (row) { const out = row.lastChild; renderMatches(res.matches || [], out); }
      if ((res.matches || []).length) hit++;
    });
    toast(`확인 완료 — 매칭 있는 추적 ${hit}건`);
  } catch (e) { toast("오류: " + e.message); }
}

// ── 지원 폼 수집 (북마클릿) ─────────────────────────────────
// 지원 페이지에서 자소서 문항·글자수를 읽어 클립보드로 복사한다.
// 페이지에서 네트워크 호출을 하지 않으므로 CORS/혼합콘텐츠/계정 위험이 없음.
// 실제 JS 함수로 작성 → toString()으로 직렬화해 bookmarklet URL 생성(이스케이프 버그 방지).
// 문항 추출 휴리스틱: aria-label → label[for] → 부모 label → dt/dd → 컨테이너 내 제목요소
// (legend/label/dt/th/strong/h*/class*=tit·title·label·question·subject·head) → 직전 형제 → placeholder.
// 글자수 카운터('0/500', '(1000자)')는 제거. 사람인/잡코리아식 div.tit 구조 검증 완료.
function __jsScrapeForm() {
  function clean(s) {
    return (s || "")
      .replace(/[0-9]+\s*\/\s*[0-9]+\s*(자|byte|bytes|글자)?/gi, "")
      .replace(/[\(\[]\s*[0-9]+\s*자\s*[\)\]]/g, "")
      .replace(/\s*\*\s*$/, "")
      .replace(/\s+/g, " ").trim();
  }
  function titleOf(e) {
    var q = e.getAttribute("aria-label") || "";
    if (!q && e.id) { try { var l = document.querySelector('label[for="' + CSS.escape(e.id) + '"]'); if (l) q = l.innerText; } catch (_) {} }
    if (!q) { var p = e.closest("label"); if (p) q = p.innerText; }
    if (!q) { var dd = e.closest("dd"); if (dd) { var dt = dd.previousElementSibling; if (dt && dt.tagName === "DT") q = dt.innerText; } }
    if (!clean(q)) {
      var c = e.closest("div,li,section,fieldset,tr,dl,td,p");
      for (var hop = 0; c && hop < 3 && !clean(q); hop++) {
        var t = c.querySelector("legend,label,dt,th,strong,b,h1,h2,h3,h4,h5,h6,[class*=tit],[class*=title],[class*=label],[class*=question],[class*=subject],[class*=head]");
        if (t && t.innerText && !t.contains(e)) q = t.innerText;
        c = c.parentElement;
      }
    }
    if (!clean(q)) { var s = e.previousElementSibling; while (s && !clean(q)) { if (s.innerText) q = s.innerText; s = s.previousElementSibling; } }
    if (!clean(q)) { var ph = e.getAttribute("placeholder") || ""; if (ph && !/입력|선택|example|search|검색|here/i.test(ph)) q = ph; }
    return clean(q).slice(0, 300);
  }
  var fs = [];
  document.querySelectorAll("textarea,input[type=text],input[type=email],input[type=tel],input:not([type]),select").forEach(function (e) {
    if (e.offsetParent === null) return;
    var q = titleOf(e); if (!q) return;
    var m = e.getAttribute("maxlength"); m = (m && parseInt(m) > 0) ? parseInt(m) : null;
    var t = e.tagName.toLowerCase();
    fs.push({ q: q, type: t === "textarea" ? "textarea" : (t === "select" ? "select" : "text"), maxlen: m });
  });
  var d = { url: location.href, host: location.host, title: document.title, fields: fs };
  var j = JSON.stringify(d);
  navigator.clipboard.writeText(j).then(function () { alert("폼 " + fs.length + "개 항목 복사됨! 관리자 > 지원 폼 탭에 붙여넣기 하세요."); }, function () { window.prompt("복사 실패 — 수동 복사:", j); });
}
const BOOKMARKLET = "javascript:(" + __jsScrapeForm.toString().replace(/\s+/g, " ") + ")();";

async function viewForms(v) {
  // 1) 북마클릿 설치
  const bm = el("a", { class: "btn", style: "text-decoration:none; display:inline-block" }, "📋 지원폼 수집");
  bm.setAttribute("href", BOOKMARKLET);
  bm.addEventListener("click", (e) => e.preventDefault());
  v.append(el("div", { class: "card" },
    el("h2", null, "1. 북마클릿 설치 (한 번만)"),
    el("div", { class: "muted small", style: "margin-bottom:8px" }, "아래 버튼을 브라우저 북마크바로 드래그하세요. (또는 코드 복사 → 새 북마크의 URL로 붙여넣기)"),
    el("div", { class: "flex", style: "flex-wrap:wrap" }, bm,
      el("button", { class: "btn ghost sm", onclick: () => { navigator.clipboard.writeText(BOOKMARKLET); toast("북마클릿 코드 복사됨"); } }, "코드 복사")),
    el("div", { class: "muted small", style: "margin-top:10px" },
      "사용법: ①지원 페이지를 직접 로그인해서 연다 → ②북마클릿 클릭(문항이 클립보드로 복사됨) → ③아래에 붙여넣기.")));

  // 2) 붙여넣기 수집
  const paste = el("textarea", { placeholder: "여기에 붙여넣기 (북마클릿이 복사한 JSON). 또는 문항을 한 줄에 하나씩 적어도 됩니다." });
  v.append(el("div", { class: "card" },
    el("h2", null, "2. 폼 붙여넣기"),
    paste,
    el("div", { style: "margin-top:8px" }, el("button", { class: "btn", onclick: async () => {
      const raw = paste.value.trim();
      if (!raw) { toast("내용을 붙여넣으세요"); return; }
      let cap;
      try {
        cap = JSON.parse(raw);
        if (!cap.fields) throw new Error("no fields");
      } catch (e) {
        // JSON이 아니면 줄 단위 문항으로 처리(폴백)
        cap = { title: "직접 입력", fields: raw.split("\n").map((s) => s.trim()).filter(Boolean).map((q) => ({ q, type: "textarea" })) };
      }
      try { await postJSON("/api/captures", cap); paste.value = ""; toast("수집됨"); route(); }
      catch (e) { toast("오류: " + e.message); }
    } }, "수집 저장"))));

  // 3) 수집 목록
  let data;
  try { data = await getJSON("/api/captures"); } catch (e) { v.append(el("div", { class: "muted" }, "오류: " + e.message)); return; }
  const listCard = el("div", { class: "card" }, el("h2", null, "3. 수집한 지원 폼"));
  if (!data.items.length) listCard.append(el("div", { class: "muted" }, "아직 수집한 폼이 없습니다."));
  const rowOf = (c) => {
    const out = el("div");
    const keyInput = el("input", { placeholder: "연결할 JD key (선택, 예: wanted:6)", style: "max-width:260px" });
    return el("div", { class: "rowitem" },
      el("div", { class: "flex" },
        el("div", null, el("b", null, esc(c.title || c.host)), el("div", { class: "small muted" }, esc(c.host) + " · 문항 " + (c.fields || []).length + "개 · " + esc((c.created_at || "").slice(0, 10)))),
        el("span", { class: "spacer" }),
        c.url ? el("a", { href: c.url, target: "_blank", class: "small" }, "원문 ↗") : null),
      el("div", { class: "flex", style: "margin-top:8px; flex-wrap:wrap" }, keyInput,
        el("button", { class: "btn sm", onclick: () => genAnswers(c.id, keyInput.value.trim(), out) }, "AI 답안 생성"),
        el("button", { class: "btn sm ghost", onclick: () => { out.innerHTML = ""; (c.fields || []).forEach((f) => out.append(el("div", { class: "small muted" }, "• " + f.q + (f.maxlen ? ` (최대 ${f.maxlen}자)` : "")))); } }, "문항 보기"),
        el("button", { class: "btn sm ghost", onclick: async () => { if (confirm("삭제할까요?")) { await del("/api/captures?id=" + c.id); route(); } } }, "삭제")),
      out);
  };
  // 년도별 그룹 — 최신 연도 먼저, 각 연도 안에서도 최신 먼저
  const byYear = {};
  data.items.forEach((c) => { const y = (c.year || (c.created_at || "").slice(0, 4)) || "기타"; (byYear[y] = byYear[y] || []).push(c); });
  Object.keys(byYear).sort((a, b) => b.localeCompare(a)).forEach((y) => {
    listCard.append(el("div", { class: "small muted", style: "margin:14px 0 6px; border-top:1px solid var(--line); padding-top:10px" },
      (y === "기타" ? "연도 미상" : y + "년") + " · " + byYear[y].length + "건"));
    byYear[y].slice().reverse().forEach((c) => listCard.append(rowOf(c)));
  });
  v.append(listCard);
}

async function genAnswers(captureId, key, out) {
  out.innerHTML = "<div class='muted'>답안 생성 중… (AI 호출)</div>";
  try {
    const body = { capture_id: captureId };
    if (key) body.key = key;
    const r = await postJSON("/api/answer", body);
    out.innerHTML = "";
    (r.answers || []).forEach((a) => {
      const over = a.maxlen > 0 && a.char_count > a.maxlen;
      out.append(el("div", { class: "card", style: "margin-top:10px" },
        el("div", { class: "flex" }, el("b", null, esc(a.q)),
          el("span", { class: "spacer" }),
          el("span", { class: "small " + (over ? "" : "muted"), style: over ? "color:var(--bad)" : "" }, (a.char_count || 0) + "자")),
        a.answer ? el("pre", { class: "doc" }, esc(a.answer)) : el("div", { class: "muted small" }, "(답안 비움)"),
        a.answer ? el("button", { class: "btn sm ghost", onclick: () => { navigator.clipboard.writeText(a.answer); toast("복사됨"); } }, "복사") : null,
        a.gap ? el("div", { class: "small", style: "color:var(--warn); margin-top:6px" }, "⚠ " + esc(a.gap)) : null));
    });
    if (r.notes) out.append(el("div", { class: "small muted", style: "margin-top:8px" }, esc(r.notes)));
  } catch (e) { out.innerHTML = "<div class='muted'>오류: " + esc(e.message) + "</div>"; }
}

// ── 사실 프로필 ─────────────────────────────────────────────
async function viewProfile(v) {
  let p;
  try { p = await getJSON("/api/profile"); } catch (e) { v.append(el("div", { class: "muted" }, "오류: " + e.message)); return; }

  const f = {};
  const field = (key, label, val, ta) => {
    const node = ta ? el("textarea", null) : el("input", null);
    node.value = val || "";
    f[key] = node;
    return el("div", null, el("label", null, label), node);
  };

  // 단순 필드
  const basic = el("div", { class: "card" }, el("h2", null, "기본 정보"),
    field("name", "이름", p.name),
    field("headline", "한 줄 소개", p.headline),
    field("email", "이메일", (p.contact || {}).email),
    field("phone", "연락처", (p.contact || {}).phone),
    field("location", "지역", (p.contact || {}).location),
    field("summary", "자기소개 요약 (사실 기반)", p.summary, true),
    field("skills", "보유 스킬 (쉼표로 구분)", (p.skills || []).join(", "), true));

  // 경력 / 프로젝트 / 학력 / 자격증 — 반복 행 편집기
  const expBox = listEditor("경력", p.experiences || [], [["company", "회사"], ["role", "직책"], ["start", "시작"], ["end", "종료"], ["bullets", "성과(줄바꿈 구분)", true]]);
  const projBox = listEditor("프로젝트", p.projects || [], [["name", "이름"], ["role", "역할"], ["period", "기간"], ["stack", "스택(쉼표)"], ["bullets", "내용(줄바꿈 구분)", true], ["url", "링크"]]);
  const eduBox = listEditor("학력", p.education || [], [["school", "학교"], ["degree", "학위"], ["major", "전공"], ["start", "시작"], ["end", "종료"]]);
  const certBox = listEditor("자격증", p.certifications || [], [["name", "이름"], ["issuer", "발급"], ["date", "취득일"]]);
  const linkBox = listEditor("링크", p.links || [], [["label", "이름"], ["url", "URL"]]);

  const save = el("button", { class: "btn", onclick: async () => {
    const profile = {
      name: f.name.value, headline: f.headline.value,
      contact: { email: f.email.value, phone: f.phone.value, location: f.location.value },
      summary: f.summary.value,
      skills: f.skills.value.split(",").map((s) => s.trim()).filter(Boolean),
      experiences: expBox.collect(), projects: projBox.collect(),
      education: eduBox.collect(), certifications: certBox.collect(), links: linkBox.collect(),
    };
    try { await postJSON("/api/profile", profile); toast("프로필 저장됨"); }
    catch (e) { toast("오류: " + e.message); }
  } }, "프로필 저장");

  v.append(el("div", { class: "muted small", style: "margin-bottom:12px" }, "이 프로필이 모든 AI 생성·분석의 '유일한 근거'입니다. 사실만 입력하세요."),
    basic, expBox.node, projBox.node, eduBox.node, certBox.node, linkBox.node,
    el("div", { style: "margin:16px 0 40px" }, save));
}

// 반복 항목 편집기. fields = [[key,label,isTextarea?]]
function listEditor(title, items, fields) {
  const rows = el("div");
  function addRow(data) {
    data = data || {};
    const inputs = {};
    const inner = fields.map(([key, label, ta]) => {
      // 배열 필드(bullets/stack)는 줄바꿈/쉼표 문자열로 표시
      let val = data[key];
      if (Array.isArray(val)) val = val.join(key === "stack" ? ", " : "\n");
      const node = (ta ? el("textarea", null) : el("input", null));
      node.value = val || "";
      inputs[key] = node;
      return el("div", null, el("label", null, label), node);
    });
    const row = el("div", { class: "rowitem" }, ...inner,
      el("button", { class: "btn sm ghost", style: "margin-top:8px", onclick: () => row.remove() }, "행 삭제"));
    row._collect = () => {
      const o = {};
      for (const [key] of fields) {
        let val = inputs[key].value;
        if (key === "bullets") o[key] = val.split("\n").map((s) => s.trim()).filter(Boolean);
        else if (key === "stack") o[key] = val.split(",").map((s) => s.trim()).filter(Boolean);
        else o[key] = val;
      }
      return o;
    };
    rows.append(row);
  }
  (items || []).forEach(addRow);
  const node = el("div", { class: "card" }, el("h2", null, title), rows,
    el("button", { class: "btn sm ghost", onclick: () => addRow({}) }, "+ 행 추가"));
  return { node, collect: () => Array.from(rows.children).map((r) => r._collect()).filter((o) => Object.values(o).some((x) => (Array.isArray(x) ? x.length : x))) };
}

// ── 지원 현황 ───────────────────────────────────────────────
async function viewApps(v) {
  let data;
  try { data = await getJSON("/api/applications"); } catch (e) { v.append(el("div", { class: "muted" }, "오류: " + e.message)); return; }
  if (!data.items.length) { v.append(el("div", { class: "card muted" }, "아직 추가한 지원이 없습니다. 'JD 검색·생성' 탭에서 '지원에 추가'를 눌러보세요.")); return; }
  const table = el("table", null, el("thead", null, el("tr", null,
    el("th", null, "회사"), el("th", null, "직무"), el("th", null, "상태"), el("th", null, "메모"), el("th", null, ""))));
  const tbody = el("tbody");
  table.append(tbody);
  data.items.forEach((a) => {
    const statusSel = el("select", { onchange: async () => { try { await patchJSON("/api/applications?id=" + a.id, { status: statusSel.value }); toast("상태 변경"); } catch (e) { toast(e.message); } } },
      ...data.statuses.map((s) => el("option", { value: s, selected: s === a.status ? "selected" : null }, s)));
    const note = el("input", { value: a.note || "", onchange: async () => { try { await patchJSON("/api/applications?id=" + a.id, { note: note.value }); } catch (e) { toast(e.message); } } });
    tbody.append(el("tr", null,
      el("td", null, esc(a.job.company), a.job.url ? el("div", null, el("a", { href: a.job.url, target: "_blank", class: "small" }, "↗")) : null),
      el("td", null, esc(a.job.title)),
      el("td", null, statusSel),
      el("td", null, note),
      el("td", null, el("button", { class: "btn sm ghost", onclick: async () => { if (confirm("삭제할까요?")) { await del("/api/applications?id=" + a.id); route(); } } }, "삭제"))));
  });
  v.append(el("div", { class: "card" }, el("h2", null, "지원 현황"), table));
}

// ── 설정 ────────────────────────────────────────────────────
async function viewSettings(v) {
  const h = await getJSON("/api/health").catch(() => ({ ai: false }));
  const key = el("input", { type: "password", placeholder: "sk-ant-..." });
  v.append(el("div", { class: "card" },
    el("h2", null, "Anthropic API 키"),
    el("div", { class: "muted small", style: "margin-bottom:8px" }, "현재 상태: " + (h.ai ? "설정됨 ✅" : "없음 — AI 기능을 쓰려면 입력하세요")),
    el("label", null, "API 키 (로컬 .secrets.json에만 저장, git 제외)"), key,
    el("div", { style: "margin-top:10px" }, el("button", { class: "btn", onclick: async () => {
      if (!key.value.trim()) { toast("키를 입력하세요"); return; }
      try { await postJSON("/api/settings/apikey", { key: key.value.trim() }); key.value = ""; toast("저장됨"); refreshAIState(); route(); }
      catch (e) { toast("오류: " + e.message); }
    } }, "저장"))));
  v.append(el("div", { class: "card muted small" },
    el("h2", null, "보안"),
    "이 관리자는 127.0.0.1(이 맥)에서만 접속됩니다. 공개 사이트(ngrok)에는 노출되지 않습니다. ",
    "프로필·지원·생성물·API키는 모두 git에서 제외된 로컬 파일에만 저장됩니다."));
}

// ── 시작 ────────────────────────────────────────────────────
refreshAIState();
route();
