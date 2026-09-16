// 한 장짜리 틀들이 같이 쓰는 것 — carousel.py 가 각 틀의 /*__FRAME_JS__*/ 자리에 박는다.
//   데이터 읽기 · 브랜드 ui 를 CSS 변수로 · 섹션을 쓰기 좋은 모양으로 · 본문 글자 크기 맞추기
// 틀은 모양만 정한다. 무엇을 넣을지(전문 전부)와 얼마나 크게 쓸지는 여기서 같다.
window.Frame = {
  async init() {
    const D = JSON.parse(document.getElementById('data').textContent);
    const ui = (D.brand && D.brand.ui) || {};
    const st = document.documentElement.style;
    const set = (k, v) => st.setProperty('--' + k, v);
    set('w', D.fmt.w + 'px'); set('h', D.fmt.h + 'px'); set('u', Math.min(D.fmt.w, D.fmt.h) / 100 + 'px');
    // 브랜드가 없으면 흑백 종이 — 틀이 원래 가진 모양으로 돌아간다
    set('paper', ui.paper || '#f5f1ec');
    set('ink', ui.ink || '#111111');
    set('text', ui.text || '#2b2b2b');
    set('sub', ui.sub || '#8a8a8a');
    set('accent', ui.accent || ui.ink || '#111111');
    set('font', ui.font || "'Noto Sans KR','Malgun Gothic',sans-serif");
    // fonts.ready 는 '이미 요청된' 글꼴만 기다린다. 아직 글자가 없으면 아무것도 요청되지 않아
    // 곧바로 풀리고, fit 이 대체 서체로 치수를 잰다. 선언된 글꼴을 전부 먼저 불러 둔다.
    if (document.fonts) {
      await Promise.all([...document.fonts].map(f => f.load().catch(() => null)));
      await document.fonts.ready;
    }

    const el = (tag, cls, text) => {
      const n = document.createElement(tag);
      if (cls) n.className = cls;
      if (text != null) n.textContent = text;
      return n;
    };

    // 섹션 → { tasks:[{no,title,items}], qualifications, preferences, benefits:[{label,text}] }
    const S = { tasks: [], qualifications: [], preferences: [], benefits: [] };
    for (const s of D.sections) {
      if (s.kicker === 'Tasks') S.tasks.push({ no: s.no ? Number(s.no) : S.tasks.length + 1, title: s.title === '주요업무' ? '' : s.title, items: s.items });
      else if (s.kicker === 'Requirements') S.qualifications = s.items;
      else if (s.kicker === 'Preferred') S.preferences = s.items;
      else if (s.kicker === 'Benefits') S.benefits = s.items;
    }
    const career = D.meta.map(m => m.replace(/^경력\s*/, '')).join(' · ');

    return { D, ui, S, el, set, career, brand: D.brand || null };
  },

  // candidates 마다 본문 글자 크기(--f)를 이분 탐색해 가장 크게 들어가는 것을 고른다.
  // render(candidate) 는 --f 가 정해진 상태에서 그리고, 넘치지 않으면 true 를 돌려준다.
  fit(F, candidates, render, { lo = 8, hi = 48 } = {}) {
    const tries = candidates.map(c => {
      let a = lo, b = hi;
      while (b - a > 0.25) {
        const f = (a + b) / 2;
        F.set('f', f + 'px');
        if (render(c)) a = f; else b = f;
      }
      return { c, f: a };
    });
    const win = tries.reduce((x, y) => (y.f > x.f + 0.3 ? y : x));   // 비슷하면 앞의 것
    F.set('f', win.f + 'px');
    render(win.c);
    this.period(F);
    window.__layout = { candidate: win.c, font_px: Math.round(win.f * 10) / 10,
                        columns: win.c.columns || 1, tries: tries.map(t => ({ ...t.c, f: t.f })) };
    window.__paged = true;
  },

  // '언제까지' — 이 판에서 제일 먼저 찾는 것이다. 마감을 안 그린 판에만 붙인다.
  //
  // 전용 판이 17개다. 판마다 마감 자리를 손으로 넣으면 빠지는 판이 생긴다(실제로 11개가 빠져
  // 있었다). 그래서 여기서 한 번에 붙인다 — 이미 마감을 그린 판은 건드리지 않고, 사이트 이름을
  // 뺄 때 비워 둔 '지원' 칸(.apply)이 있으면 그 자리에, 없으면 판 오른쪽 아래에 절대배치한다.
  // fit 이 끝난 뒤에 붙이므로(절대배치) 본문 글자 크기를 깎지 않는다.
  period(F) {
    const label = (F.D.until || '').trim();
    const sheet = document.querySelector('.sheet');
    if (!label || !sheet || sheet.querySelector('.period')) return;
    if (sheet.textContent.includes(label)) return;   // 판이 이미 이 문구를 그렸다

    const box = document.createElement('div');
    box.className = 'period';
    box.textContent = label;
    const slot = sheet.querySelector('.apply');
    if (slot && !slot.textContent.trim()) {
      slot.append(box);
    } else {
      // 판마다 아래 오른쪽이 비어 있지 않다(쿠팡은 바코드가 있다). 네 귀퉁이를 재 보고
      // 다른 것과 가장 덜 겹치는 자리에 놓는다 — 겹치면 마감이 안 읽힌다.
      if (getComputedStyle(sheet).position === 'static') sheet.style.position = 'relative';
      box.style.position = 'absolute';
      box.style.zIndex = 9;
      sheet.append(box);
      const pad = 'calc(var(--u) * 2.2)';
      const corners = [
        { bottom: pad, right: pad }, { bottom: pad, left: pad },
        { top: pad, right: pad }, { top: pad, left: pad },
      ];
      // 글자·그림이 있는 잎 요소들만 본다(칸 자체는 넓어서 늘 겹친다)
      const marks = [...sheet.querySelectorAll('*')].filter(n => n !== box && !n.contains(box)
        && (n.tagName === 'IMG' || n.tagName === 'SVG' || n.tagName === 'CANVAS'
            || (!n.children.length && n.textContent.trim())));
      const overlap = (r) => marks.reduce((sum, n) => {
        const m = n.getBoundingClientRect();
        const w = Math.min(r.right, m.right) - Math.max(r.left, m.left);
        const h = Math.min(r.bottom, m.bottom) - Math.max(r.top, m.top);
        return sum + (w > 0 && h > 0 ? w * h : 0);
      }, 0);
      let best = null;
      for (const c of corners) {
        Object.assign(box.style, { top: '', right: '', bottom: '', left: '' }, c);
        const area = overlap(box.getBoundingClientRect());
        if (area === 0) { best = null; break; }               // 빈 자리를 찾았다
        if (!best || area < best.area) best = { c, area };
      }
      if (best) Object.assign(box.style, { top: '', right: '', bottom: '', left: '' }, best.c);
    }
    if (!document.getElementById('period-style')) {
      const st = document.createElement('style');
      st.id = 'period-style';
      // 판마다 색이 다르므로 판의 글자색·바탕색을 그대로 쓴다(테두리만 둔다).
      st.textContent = `.period{font-size:calc(var(--u) * 2);font-weight:800;letter-spacing:-.01em;`
        + `padding:calc(var(--u) * .6) calc(var(--u) * 1.4);border:2px solid currentColor;`
        + `border-radius:999px;white-space:nowrap;line-height:1.1}`;
      document.head.append(st);
    }
  },

  // 고정 높이 상자가 세로·가로로 넘치는지
  overflows(box) {
    return box.scrollHeight > box.clientHeight + 1 || box.scrollWidth > box.clientWidth + 1;
  },
};
