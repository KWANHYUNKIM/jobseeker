/* 디자인 랩 프런트 — 서버 API 만 부르고 상태는 여기서만 들고 있는다. */
const $ = (s) => document.querySelector(s);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};
const api = async (path, body) => {
  const opt = body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {};
  const r = await fetch(path, opt);
  return r.json();
};

const state = {
  refs: null, family: '', 
  meta: null,                 // 템플릿·포맷·팔레트
  jobs: [], job: null,
  template: 'role_hero', format: 'ig_portrait', palette: '',
  platforms: new Set(['instagram']),
};

/* ---------------- 탭 ---------------- */
document.querySelectorAll('.tab').forEach((b) => b.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach((x) => x.classList.toggle('on', x === b));
  document.querySelectorAll('.view').forEach((v) => v.classList.toggle('on', v.id === `view-${b.dataset.view}`));
  if (b.dataset.view === 'queue') loadQueue();
}));

/* ---------------- 1. 레퍼런스 ---------------- */
async function loadRefs() {
  const data = await api('/api/refs');
  state.refs = data;
  const syn = $('#synthesis');
  syn.append(el('h2', null, `수집물에서 뽑아낸 결론 — ${data.source || ''}`));
  const dl = el('dl');
  const LABEL = { hero: '히어로', sections: '섹션', rhythm: '리듬', anchors: '앵커', footer: '푸터', extra: '덤' };
  Object.entries(data.synthesis || {}).forEach(([k, v]) => {
    dl.append(el('dt', null, LABEL[k] || k), el('dd', null, v));
  });
  syn.append(dl);

  const fams = ['', ...Object.keys(data.families || {})];
  fams.forEach((f) => {
    const c = el('button', 'chip' + (f === state.family ? ' on' : ''), f ? `${f} — ${data.families[f]}` : `전체 ${data.refs.length}`);
    c.addEventListener('click', () => {
      state.family = f;
      document.querySelectorAll('#ref-filters .chip').forEach((x) => x.classList.toggle('on', x === c));
      drawRefs();
    });
    $('#ref-filters').append(c);
  });
  drawRefs();
}

function drawRefs() {
  const box = $('#refs');
  box.textContent = '';
  state.refs.refs
    .filter((r) => !state.family || r.family === state.family)
    .forEach((r) => {
      const card = el('div', 'ref');
      const shots = el('div', 'shots');
      (r.files || []).forEach((f) => {
        const img = el('img');
        img.src = `/refs/${f}`;
        img.loading = 'lazy';
        img.alt = r.title;
        img.addEventListener('click', () => {
          $('#lightbox-img').src = img.src;
          $('#lightbox').hidden = false;
        });
        shots.append(img);
      });
      const meat = el('div', 'meat');
      meat.append(el('h3', null, r.title));
      const who = el('div', 'who');
      who.append(document.createTextNode(`@${r.account} · #${r.tag} · ${r.id}`));
      if (r.url) {
        who.append(document.createTextNode(' · '));
        const a = el('a', null, '원본');
        a.href = r.url; a.target = '_blank'; a.rel = 'noreferrer';
        who.append(a);
      }
      meat.append(who);
      const moods = el('div', 'moods');
      (r.mood || []).forEach((m) => moods.append(el('b', null, m)));
      meat.append(moods);
      [['read', '읽은 것'], ['steal', '훔칠 것'], ['drop', '버릴 것']].forEach(([k, label]) => {
        if (!r[k]) return;
        const p = el('p', k);
        p.append(el('b', null, label), document.createTextNode(r[k]));
        meat.append(p);
      });
      card.append(shots, meat);
      box.append(card);
    });
}
$('#lightbox').addEventListener('click', () => { $('#lightbox').hidden = true; });

/* ---------------- 2. 스튜디오 ---------------- */
async function loadMeta() {
  state.meta = await api('/api/templates');
  drawControls();
}

function drawControls() {
  const box = $('#controls');
  box.textContent = '';
  const group = (label, items, key, onPick) => {
    const g = el('div', 'grp');
    g.append(el('span', null, label));
    items.forEach(({ id, name }) => {
      const b = el('button', 'chip' + (state[key] === id ? ' on' : ''), name);
      b.addEventListener('click', () => { state[key] = id; drawControls(); refreshPreview(); });
      g.append(b);
    });
    box.append(g);
  };
  group('템플릿', state.meta.templates.map((t) => ({ id: t.id, name: t.name })), 'template');
  group('포맷', state.meta.formats.map((f) => ({ id: f.id, name: `${f.label} ${f.w}×${f.h}` })), 'format');
  group('팔레트', [{ id: '', name: '자동' }, ...Object.keys(state.meta.palettes).map((p) => ({ id: p, name: p }))], 'palette');

  const t = state.meta.templates.find((x) => x.id === state.template);
  $('#tplnote').textContent = '';
  if (t) {
    $('#tplnote').append(el('b', null, `${t.name} — ${t.ref}`), document.createTextNode(t.note));
  }
}

async function loadJobs(q = '') {
  const { jobs = [] } = await api(`/api/jobs?q=${encodeURIComponent(q)}&limit=60`);
  state.jobs = jobs;
  const list = $('#joblist');
  list.textContent = '';
  if (!jobs.length) { list.append(el('div', 'empty', '없음')); return; }
  jobs.forEach((j) => {
    const b = el('button', 'jobrow' + (state.job && state.job.key === j.key ? ' on' : ''));
    b.append(el('span', 't', j.title));
    b.append(el('span', 'c', `${j.company} · ${j.career || '경력무관'} · ${j.location || '-'}`));
    b.addEventListener('click', () => pickJob(j));
    list.append(b);
  });
}

async function pickJob(job) {
  state.job = job;
  document.querySelectorAll('.jobrow').forEach((r) => r.classList.remove('on'));
  loadJobs($('#job-q').value).then(() => {
    document.querySelectorAll('.jobrow').forEach((r) => {
      if (r.querySelector('.t').textContent === job.title) r.classList.add('on');
    });
  });
  $('#btn-queue').disabled = false;
  refreshPreview();
  const caps = await api(`/api/caption?job=${encodeURIComponent(job.key)}&palette=${state.palette}`);
  const box = $('#captions');
  box.textContent = '';
  Object.entries(caps).forEach(([platform, text]) => {
    const c = el('div', 'cap');
    c.append(el('h4', null, platform), el('pre', null, text));
    box.append(c);
  });
}

function refreshPreview() {
  if (!state.job) return;
  const fmt = state.meta.formats.find((f) => f.id === state.format);
  const frame = $('#preview');
  frame.width = fmt.w; frame.height = fmt.h;
  const wrap = $('.canvas-wrap').getBoundingClientRect();
  const scale = Math.min((wrap.width - 40) / fmt.w, (wrap.height - 40) / fmt.h, 1);
  frame.style.transform = `scale(${scale})`;
  frame.style.margin = `${(fmt.h * scale - fmt.h) / 2}px ${(fmt.w * scale - fmt.w) / 2}px`;
  frame.src = `/api/preview?job=${encodeURIComponent(state.job.key)}&template=${state.template}` +
              `&format=${state.format}&palette=${state.palette}`;
}
window.addEventListener('resize', refreshPreview);

let qTimer;
$('#job-q').addEventListener('input', (e) => {
  clearTimeout(qTimer);
  qTimer = setTimeout(() => loadJobs(e.target.value), 220);
});

function drawPlatformPicker(checks) {
  const box = $('#plats');
  box.textContent = '';
  checks.forEach((c) => {
    const label = el('label');
    const cb = el('input');
    cb.type = 'checkbox';
    cb.checked = state.platforms.has(c.platform);
    cb.addEventListener('change', () => {
      cb.checked ? state.platforms.add(c.platform) : state.platforms.delete(c.platform);
    });
    label.append(cb, document.createTextNode(` ${c.platform}${c.ready ? '' : ' (자격없음)'}`));
    box.append(label);
  });
}

$('#btn-queue').addEventListener('click', async () => {
  if (!state.job) return;
  const res = await api('/api/queue', {
    job_key: state.job.key,
    template: state.template,
    formats: [state.format],
    platforms: [...state.platforms],
    palette: state.palette,
  });
  $('#hint').textContent = res.item ? `큐에 넣었습니다 — ${res.item.id}` : (res.error || '실패');
});

/* ---------------- 3. 발행 큐 ---------------- */
async function loadQueue() {
  const data = await api('/api/queue');
  drawPlatformPicker(data.platforms);
  const creds = $('#creds');
  creds.textContent = '';
  data.platforms.forEach((c) => {
    const d = el('div', 'cred ' + (c.ready ? 'ready' : 'no'));
    d.append(el('b', null, c.platform), el('div', null, c.ready ? '자격 준비됨' : `필요: ${c.missing.join(', ')}`));
    creds.append(d);
  });
  const base = el('div', 'cred ' + (data.public_base_url ? 'ready' : 'no'));
  base.append(el('b', null, 'public_base_url'),
              el('div', null, data.public_base_url || '없음 — 인스타는 공개 URL 이 필요합니다'));
  creds.append(base);

  const box = $('#items');
  box.textContent = '';
  if (!data.items.length) { box.append(el('div', 'empty', '큐가 비었습니다. 스튜디오에서 공고를 골라 넣으세요.')); return; }
  data.items.forEach((it) => box.append(queueRow(it)));
}

function queueRow(it) {
  const row = el('div', 'item');
  const firstFile = Object.values(it.files || {})[0];
  if (firstFile) {
    const img = el('img');
    img.src = '/' + firstFile.replace(/^\.?\//, '');
    img.addEventListener('click', () => { $('#lightbox-img').src = img.src; $('#lightbox').hidden = false; });
    row.append(img);
  } else {
    row.append(el('div', null, ''));
  }
  const meta = el('div', 'meta');
  meta.append(el('b', null, it.job_key), document.createElement('br'),
              el('span', null, `${it.template} · ${it.formats.join(', ')} → ${it.platforms.join(', ')}`),
              document.createTextNode(' '), el('span', 'badge ' + it.status, it.status));
  Object.entries(it.results || {}).forEach(([p, r]) => {
    meta.append(document.createTextNode(' '),
      el('span', 'badge ' + (r.ok ? (r.dry_run ? 'rendered' : 'published') : 'failed'),
         `${p}: ${r.dry_run ? 'dry' : (r.ok ? '발행됨' : '실패')}`));
  });
  row.append(meta);

  const btns = el('div', 'btns');
  const act = (label, cls, fn) => {
    const b = el('button', cls, label);
    b.addEventListener('click', async () => {
      b.disabled = true; b.textContent = '…';
      const res = await fn();
      b.disabled = false; b.textContent = label;
      const log = el('pre', 'log', (res.stdout || '') + (res.stderr || '') || JSON.stringify(res, null, 2));
      row.querySelector('.log')?.remove();
      row.append(log);
      loadQueue();
    });
    return b;
  };
  btns.append(act('렌더', 'ghost', () => api('/api/render', { id: it.id })));
  btns.append(act('DRY 발행', 'ghost', () => api('/api/publish', { id: it.id })));
  btns.append(act('실제 발행', 'primary', () => {
    if (!confirm(`${it.platforms.join(', ')} 계정에 진짜로 올립니다. 진행할까요?`)) return Promise.resolve({});
    return api('/api/publish', { id: it.id, live: true });
  }));
  btns.append(act('삭제', 'ghost', () => api('/api/queue/delete', { id: it.id })));
  row.append(btns);
  return row;
}

/* ---------------- 시작 ---------------- */
loadRefs();
loadMeta().then(() => loadJobs(''));
