// JD 기술스택 대시보드 — 필터링 + 차트
'use strict';

const SIZE_ORDER = ['대기업', '중견기업', '중소기업'];
const SIZE_COLORS = {
  '대기업': '#7cc4ff',
  '중견기업': '#a3e635',
  '중소기업': '#f59e0b',
};
const ROLE_ORDER = [
  '백엔드', '프론트엔드', '모바일', 'AI/ML', '펌웨어/임베디드',
  'DevOps/인프라', '데이터', '보안', '게임', 'QA', '풀스택', '기타',
];

const state = {
  raw: null,
  filters: {
    sizes: new Set(),
    roles: new Set(),
    sites: new Set(),
    q: '',
  },
  charts: {},
};

// ---------- 부트 ----------
fetch('data.json', { cache: 'no-store' })
  .then(r => r.json())
  .then(data => {
    state.raw = data;
    document.getElementById('meta-line').textContent =
      `소스: ${data.source_dir || '(없음)'} · 생성: ${data.generated_at} · 키워드: ${data.keyword || '전체'}`;
    init();
  })
  .catch(err => {
    document.getElementById('meta-line').textContent = `데이터 로드 실패: ${err}`;
  });

function init() {
  const jobs = state.raw.jobs || [];
  buildFilterChips(jobs);
  attachListeners();
  render();
}

// ---------- 필터 UI ----------
function buildFilterChips(jobs) {
  const sizeCount = countBy(jobs, j => [j.company_size]);
  const roleCount = countBy(jobs, j => j.roles);
  const siteCount = countBy(jobs, j => [j.site || 'unknown']);

  renderChips('filter-size', orderedKeys(sizeCount, SIZE_ORDER), sizeCount, state.filters.sizes);
  renderChips('filter-role', orderedKeys(roleCount, ROLE_ORDER), roleCount, state.filters.roles);
  renderChips('filter-site', Object.keys(siteCount).sort(), siteCount, state.filters.sites);
}

function renderChips(containerId, keys, counts, selectedSet) {
  const c = document.getElementById(containerId);
  c.innerHTML = '';
  for (const k of keys) {
    const chip = document.createElement('span');
    chip.className = 'chip' + (selectedSet.has(k) ? ' active' : '');
    chip.innerHTML = `${escapeHtml(k)} <span class="count">${counts[k]}</span>`;
    chip.addEventListener('click', () => {
      if (selectedSet.has(k)) selectedSet.delete(k);
      else selectedSet.add(k);
      render();
    });
    c.appendChild(chip);
  }
}

function attachListeners() {
  document.getElementById('filter-search').addEventListener('input', e => {
    state.filters.q = e.target.value.trim().toLowerCase();
    render();
  });
  document.getElementById('reset-filters').addEventListener('click', () => {
    state.filters.sizes.clear();
    state.filters.roles.clear();
    state.filters.sites.clear();
    state.filters.q = '';
    document.getElementById('filter-search').value = '';
    render();
  });
}

function applyFilters(jobs) {
  const { sizes, roles, sites, q } = state.filters;
  return jobs.filter(j => {
    if (sizes.size && !sizes.has(j.company_size)) return false;
    if (roles.size && !j.roles.some(r => roles.has(r))) return false;
    if (sites.size && !sites.has(j.site || 'unknown')) return false;
    if (q) {
      const hay = [
        j.company, j.title, (j.tech_stack || []).join(' '),
        (j.tech_tags || []).join(' '), (j.roles || []).join(' '),
      ].join(' ').toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

// ---------- 렌더 ----------
function render() {
  const all = state.raw.jobs || [];
  const filtered = applyFilters(all);

  renderKpis(filtered, all);
  // chip 카운트는 필터 적용 후 동적으로 다시 그리지 않음(전체 분포 유지)
  // chip 활성화 상태만 업데이트
  for (const id of ['filter-size', 'filter-role', 'filter-site']) {
    const set = id === 'filter-size' ? state.filters.sizes
              : id === 'filter-role' ? state.filters.roles
              : state.filters.sites;
    [...document.getElementById(id).children].forEach(ch => {
      const name = ch.firstChild.textContent.trim();
      ch.classList.toggle('active', set.has(name));
    });
  }

  renderSizeChart(filtered);
  renderRoleChart(filtered);
  renderRoleSizeChart(filtered);
  renderTechChart(filtered);
  renderCompChart(filtered);
  renderLearningPriority(filtered);
  renderRoleTechGrid(filtered);
  renderSizeTechGrid(filtered);
  renderTable(filtered);
}

const TIERS = [
  { key: 'S', min: 0.60, max: 1.01, desc: '사실상 필수' },
  { key: 'A', min: 0.40, max: 0.60, desc: '강력 권장' },
  { key: 'B', min: 0.20, max: 0.40, desc: '알면 좋음' },
  { key: 'C', min: 0.10, max: 0.20, desc: '보너스' },
];

function renderLearningPriority(jobs) {
  const wrap = document.getElementById('learning-tiers');
  wrap.innerHTML = '';
  const total = jobs.length;
  if (total === 0) {
    wrap.innerHTML = `<div class="tier-empty">필터에 해당하는 공고 없음</div>`;
    return;
  }
  // 1) 기술별 등장 공고 수
  const techCnt = countBy(jobs, j => j.tech_stack);
  // 2) 역량도 같이 보면 좋지만 카드 분리 — 여기서는 기술만
  const entries = Object.entries(techCnt)
    .map(([t, n]) => [t, n, n / total])
    .sort((a, b) => b[2] - a[2]);

  for (const tier of TIERS) {
    const items = entries.filter(([, , p]) => p >= tier.min && p < tier.max).slice(0, 12);
    const card = document.createElement('div');
    card.className = `tier-card tier-${tier.key}`;
    const range = `${Math.round(tier.min*100)}~${tier.max>1?100:Math.round(tier.max*100)}%`;
    card.innerHTML = `
      <div class="tier-head">
        <span class="tier-badge">${tier.key}</span>
        <span class="tier-range">${range}</span>
      </div>
      <div class="tier-desc">${tier.desc}</div>
      <div class="tier-list">
        ${items.length === 0
          ? `<div class="tier-empty">해당 없음</div>`
          : items.map(([t, n, p]) => `
              <div class="tier-item" data-tech="${escapeHtml(t)}">
                <span>${escapeHtml(t)}</span>
                <span class="pct">${Math.round(p*100)}% · ${n}건</span>
              </div>
            `).join('')}
      </div>
    `;
    card.querySelectorAll('.tier-item').forEach(el => {
      el.addEventListener('click', () => {
        const tech = el.dataset.tech;
        document.getElementById('filter-search').value = tech;
        state.filters.q = tech.toLowerCase();
        render();
        document.querySelector('#jobs-title')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
    wrap.appendChild(card);
  }
}

function renderKpis(filtered, all) {
  const total = all.length;
  const shown = filtered.length;
  const bySize = countBy(filtered, j => [j.company_size]);
  const pct = (k) => total === 0 ? 0 : Math.round((bySize[k] || 0) / Math.max(shown, 1) * 100);
  const html = `
    <div class="kpi"><div class="label">전체</div><div class="value">${total}</div></div>
    <div class="kpi"><div class="label">필터 후</div><div class="value">${shown}</div></div>
    <div class="kpi"><div class="label">대기업</div><div class="value">${bySize['대기업']||0} <span style="font-size:11px;color:var(--muted)">${pct('대기업')}%</span></div></div>
    <div class="kpi"><div class="label">중견기업</div><div class="value">${bySize['중견기업']||0} <span style="font-size:11px;color:var(--muted)">${pct('중견기업')}%</span></div></div>
    <div class="kpi"><div class="label">중소기업</div><div class="value">${bySize['중소기업']||0} <span style="font-size:11px;color:var(--muted)">${pct('중소기업')}%</span></div></div>
  `;
  document.getElementById('kpis').innerHTML = html;
}

// ----- Chart.js helpers -----
function destroyChart(key) {
  if (state.charts[key]) {
    state.charts[key].destroy();
    state.charts[key] = null;
  }
}

const COMMON_OPTS = {
  responsive: true, maintainAspectRatio: false,
  plugins: {
    legend: { labels: { color: '#e6e9ef', font: { size: 11 } } },
    tooltip: { backgroundColor: '#1f232c', borderColor: '#2a2f3a', borderWidth: 1 },
  },
  scales: {
    x: { ticks: { color: '#8a93a6', font: { size: 11 } }, grid: { color: '#2a2f3a' } },
    y: { ticks: { color: '#8a93a6', font: { size: 11 } }, grid: { color: '#2a2f3a' } },
  },
};

function renderSizeChart(jobs) {
  destroyChart('size');
  const cnt = countBy(jobs, j => [j.company_size]);
  const labels = SIZE_ORDER.filter(k => cnt[k]);
  const data = labels.map(k => cnt[k]);
  const colors = labels.map(k => SIZE_COLORS[k]);
  const ctx = document.getElementById('chart-size');
  ctx.parentElement.style.height = '280px';
  state.charts.size = new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets: [{ data, backgroundColor: colors, borderColor: '#181b22', borderWidth: 2 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'right', labels: { color: '#e6e9ef', font: { size: 12 } } } },
    },
  });
}

function renderRoleChart(jobs) {
  destroyChart('role');
  const cnt = countBy(jobs, j => j.roles);
  const labels = ROLE_ORDER.filter(k => cnt[k]);
  const data = labels.map(k => cnt[k]);
  const ctx = document.getElementById('chart-role');
  ctx.parentElement.style.height = '280px';
  state.charts.role = new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets: [{ label: '공고 수', data, backgroundColor: '#7cc4ff' }] },
    options: { ...COMMON_OPTS, indexAxis: 'y', plugins: { ...COMMON_OPTS.plugins, legend: { display: false } } },
  });
}

function renderRoleSizeChart(jobs) {
  destroyChart('roleSize');
  const counts = {};
  for (const j of jobs) {
    for (const r of j.roles) {
      counts[r] = counts[r] || {};
      counts[r][j.company_size] = (counts[r][j.company_size] || 0) + 1;
    }
  }
  const roles = ROLE_ORDER.filter(r => counts[r]);
  const datasets = SIZE_ORDER.map(size => ({
    label: size,
    data: roles.map(r => (counts[r] && counts[r][size]) || 0),
    backgroundColor: SIZE_COLORS[size],
  }));
  const ctx = document.getElementById('chart-role-size');
  ctx.parentElement.style.height = '340px';
  state.charts.roleSize = new Chart(ctx, {
    type: 'bar',
    data: { labels: roles, datasets },
    options: {
      ...COMMON_OPTS,
      scales: {
        x: { ...COMMON_OPTS.scales.x, stacked: true },
        y: { ...COMMON_OPTS.scales.y, stacked: true },
      },
    },
  });
}

function renderTechChart(jobs) {
  destroyChart('tech');
  const cnt = countBy(jobs, j => j.tech_stack);
  const top = Object.entries(cnt).sort((a, b) => b[1] - a[1]).slice(0, 15);
  const labels = top.map(([k]) => k);
  const data = top.map(([, v]) => v);
  const ctx = document.getElementById('chart-tech');
  ctx.parentElement.style.height = '380px';
  state.charts.tech = new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets: [{ label: '공고 수', data, backgroundColor: '#a3e635' }] },
    options: { ...COMMON_OPTS, indexAxis: 'y', plugins: { ...COMMON_OPTS.plugins, legend: { display: false } } },
  });
}

function renderCompChart(jobs) {
  destroyChart('comp');
  const cnt = countBy(jobs, j => j.competencies);
  const top = Object.entries(cnt).sort((a, b) => b[1] - a[1]).slice(0, 15);
  const labels = top.map(([k]) => k);
  const data = top.map(([, v]) => v);
  const ctx = document.getElementById('chart-comp');
  ctx.parentElement.style.height = '380px';
  state.charts.comp = new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets: [{ label: '공고 수', data, backgroundColor: '#f59e0b' }] },
    options: { ...COMMON_OPTS, indexAxis: 'y', plugins: { ...COMMON_OPTS.plugins, legend: { display: false } } },
  });
}

function renderRoleTechGrid(jobs) {
  const wrap = document.getElementById('role-tech-grid');
  wrap.innerHTML = '';
  const byRole = {};
  for (const j of jobs) {
    for (const r of j.roles) {
      byRole[r] = byRole[r] || [];
      byRole[r].push(j);
    }
  }
  const roles = ROLE_ORDER.filter(r => byRole[r]);
  for (const r of roles) {
    const arr = byRole[r];
    const cnt = countBy(arr, j => j.tech_stack);
    const top = Object.entries(cnt).sort((a, b) => b[1] - a[1]).slice(0, 10);
    if (top.length === 0) continue;
    const max = top[0][1];
    const card = document.createElement('div');
    card.className = 'role-tech-card';
    card.innerHTML = `
      <h3>${escapeHtml(r)} <span class="count">${arr.length}건</span></h3>
      <div class="tech-bar">
        ${top.map(([tech, v]) => `
          <div class="tech-bar-row">
            <div class="name">${escapeHtml(tech)}</div>
            <div class="bar"><div style="width: ${Math.round(v/max*100)}%"></div></div>
            <div class="pct">${Math.round(v/arr.length*100)}%</div>
          </div>
        `).join('')}
      </div>
    `;
    wrap.appendChild(card);
  }
}

function renderSizeTechGrid(jobs) {
  const wrap = document.getElementById('size-tech-grid');
  wrap.innerHTML = '';
  const bySize = {};
  for (const j of jobs) {
    bySize[j.company_size] = bySize[j.company_size] || [];
    bySize[j.company_size].push(j);
  }
  const SIZE_CLASS = { '대기업': 'size-large', '중견기업': 'size-mid', '중소기업': 'size-small' };
  for (const s of SIZE_ORDER) {
    const arr = bySize[s];
    if (!arr) continue;
    const cnt = countBy(arr, j => j.tech_stack);
    const top = Object.entries(cnt).sort((a, b) => b[1] - a[1]).slice(0, 12);
    const max = top[0]?.[1] || 1;
    const card = document.createElement('div');
    card.className = 'role-tech-card';
    card.innerHTML = `
      <h3>${escapeHtml(s)} <span class="count">${arr.length}건</span></h3>
      <div class="tech-bar">
        ${top.map(([tech, v]) => `
          <div class="tech-bar-row ${SIZE_CLASS[s]}">
            <div class="name">${escapeHtml(tech)}</div>
            <div class="bar"><div style="width: ${Math.round(v/max*100)}%"></div></div>
            <div class="pct">${Math.round(v/arr.length*100)}%</div>
          </div>
        `).join('')}
      </div>
    `;
    wrap.appendChild(card);
  }
}

function renderTable(jobs) {
  document.getElementById('jobs-title').textContent = `공고 목록 (${jobs.length}건)`;
  const tbody = document.querySelector('#jobs-table tbody');
  const MAX_ROWS = 500;
  const slice = jobs.slice(0, MAX_ROWS);
  tbody.innerHTML = slice.map(j => `
    <tr>
      <td class="company">${escapeHtml(j.company)}</td>
      <td><span class="size-pill ${escapeHtml(j.company_size)}">${escapeHtml(j.company_size)}</span></td>
      <td>${j.url ? `<a href="${escapeHtml(j.url)}" target="_blank" rel="noopener">${escapeHtml(j.title)}</a>` : escapeHtml(j.title)}</td>
      <td>${(j.roles || []).map(r => `<span class="role-tag">${escapeHtml(r)}</span>`).join('')}</td>
      <td>${(j.tech_stack || []).slice(0, 8).map(t => `<span class="tech-tag">${escapeHtml(t)}</span>`).join('')}</td>
      <td>${escapeHtml(j.career || '')}</td>
      <td>${escapeHtml(j.location || '')}</td>
      <td>${escapeHtml(j.site || '')}</td>
    </tr>
  `).join('');
  if (jobs.length > MAX_ROWS) {
    tbody.insertAdjacentHTML('beforeend',
      `<tr><td colspan="8" style="text-align:center;color:var(--muted);">… 상위 ${MAX_ROWS}건만 표시 (필터로 좁히세요)</td></tr>`);
  }
}

// ---------- 유틸 ----------
function countBy(arr, keyFn) {
  const out = {};
  for (const x of arr) {
    const keys = keyFn(x);
    for (const k of keys) {
      if (!k) continue;
      out[k] = (out[k] || 0) + 1;
    }
  }
  return out;
}

function orderedKeys(obj, preferred) {
  const present = new Set(Object.keys(obj));
  const head = preferred.filter(k => present.has(k));
  const tail = [...present].filter(k => !preferred.includes(k)).sort();
  return [...head, ...tail];
}

function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}
