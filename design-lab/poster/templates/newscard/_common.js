// 카드뉴스 틀이 같이 쓰는 것 — 판을 그리는 draw(sheet, S, D) 는 틀마다 다르고 나머지는 여기.
// newscard.py 가 각 틀의 /*__COMMON__*/ 자리에 박는다. 틀은 이 줄 앞에 draw 를 정의한다.
//
// 약속: .sheet 하나를 찍는다. window.__ready / __overflow / __minBody 를 남긴다(series.html 과 같다).
// 본문 글자는 .body 클래스를 단다 — __minBody 가 그것만 잰다(18px 밑이면 렌더러가 경고).
(() => {
  const D = /*__DATA__*/;
  const S = D.slide;
  const sheet = document.createElement('div');
  sheet.className = 'sheet t-' + S.type;
  sheet.style.setProperty('--w', D.size[0] + 'px');
  sheet.style.setProperty('--h', D.size[1] + 'px');
  document.getElementById('root').append(sheet);
  draw(sheet, S, D);

  // 넘치면 .fit 붙은 것부터 줄인다 — 제목이 먼저 작아지고 본문은 18px 밑으로 안 내려간다
  let guard = 0;
  const over = () => sheet.scrollHeight > sheet.clientHeight + 1 ||
    [...sheet.querySelectorAll('.fit')].some(n => n.scrollWidth > n.clientWidth + 1);
  while (over() && guard++ < 40) {
    sheet.querySelectorAll('.fit, .body').forEach(n => {
      const s = parseFloat(getComputedStyle(n).fontSize);
      const min = n.classList.contains('body') ? 18 : 28;
      if (s > min) n.style.fontSize = Math.max(min, s * 0.95) + 'px';
    });
  }
  const imgs = [...document.images];
  Promise.all(imgs.map(i => i.complete ? 0 : new Promise(r => { i.onload = i.onerror = r; })))
    .then(() => document.fonts.ready)
    .then(() => {
      window.__minBody = Math.min(...[...sheet.querySelectorAll('.body')]
        .map(n => parseFloat(getComputedStyle(n).fontSize)).concat([99]));
      window.__overflow = over();
      window.__ready = true;
    });
})();

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}
// 줄바꿈(\n)을 살린다
function lines(n, text) {
  String(text).split('\n').forEach((t, i) => { if (i) n.append(document.createElement('br')); n.append(t); });
  return n;
}
function pad2(i) { return String(i).padStart(2, '0'); }
