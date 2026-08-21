import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

// Mermaid 는 번들이 커서 동적 import 로 코드 스플릿한다(다이어그램을 열 때만 로드).
let mermaidReady: Promise<typeof import('mermaid').default> | null = null
function loadMermaid() {
  if (!mermaidReady) mermaidReady = import('mermaid').then((m) => m.default)
  return mermaidReady
}

let seq = 0

// ── 도판(圖版) 양식 ────────────────────────────────────────────────────────
// 교과서 그림처럼 그린다: 종이 위의 잉크, 각진 모서리, 그림자·그라데이션 없음.
// 강조는 색이 아니라 자리로 하고, 색을 쓰는 곳은 그림마다 한 군데(:::accent)뿐이다.
//
// **앱 테마를 따르지 않는다.** 도판은 본문에 끼워 넣은 인쇄물이지 UI 가 아니라서,
// 어두운 테마에서도 흰 종이 그대로 둔다 — 그래야 그림 하나가 어디서 시작하고
// 어디서 끝나는지가 눈에 잡힌다. (테마를 따르게 하려면 PAPER/INK 만 갈아 끼우면 된다.)
type Plate = {
  isLight: boolean
  paper: string
  ink: string
  faint: string
  accentBg: string
  accentInk: string
}
function plate(): Plate {
  return {
    isLight: true, // 도판은 언제나 밝다 — mermaid 의 darkMode 계산도 이 값을 따른다
    paper: '#ffffff',
    ink: '#16181d',
    faint: '#8b9099',
    accentBg: '#fbdcc4', // 살구색 — 그림마다 한 군데뿐인 강조
    accentInk: '#b4460d',
  }
}

// 필자가 매번 classDef 를 선언하지 않아도 되게 표준 클래스를 앞에 붙인다.
// 규격을 데이터가 아니라 렌더러가 들고 있어야, 나중에 양식을 바꿀 때
// 그림 311장을 다시 건드리지 않는다.
const CLASSED = /^\s*(flowchart|graph|stateDiagram)/
function withStandardClasses(code: string, p: Plate): string {
  if (!CLASSED.test(code.trim())) return code // 시퀀스도는 classDef 를 안 받는다
  const defs = [
    `classDef accent fill:${p.accentBg},stroke:${p.ink},color:${p.ink}`,
    `classDef quiet fill:${p.paper},stroke:${p.faint},color:${p.faint}`,
    `classDef list fill:${p.paper},stroke:${p.ink},color:${p.ink},text-align:left`,
  ]
  const lines = code.split('\n')
  const head = lines.findIndex((l) => l.trim() !== '')
  lines.splice(head + 1, 0, ...defs.map((d) => '  ' + d))
  return lines.join('\n')
}

// mermaid 는 svg 에 `style="max-width: 123px"` 를 박고 width/height 를 지운다.
// 그 상태로는 우리가 크기를 잡을 수 없어서 걷어내고, 대신 viewBox 에서 원본
// 치수를 읽어 온다. 확대의 기준이 되는 값이라 여기서 한 번만 구한다.
function normalize(svg: string): { html: string; w: number; h: number } {
  const vb = svg.match(/viewBox="([\d.\-\s]+)"/)
  let w = 900
  let h = 600
  if (vb) {
    const p = vb[1].trim().split(/\s+/).map(Number)
    if (p.length === 4 && p[2] > 0 && p[3] > 0) {
      w = p[2]
      h = p[3]
    }
  }
  const html = svg
    .replace(/style="[^"]*max-width:[^"]*"/, 'style="width:100%;height:100%"')
    .replace(/\swidth="[^"]*"/, '')
    .replace(/\sheight="[^"]*"/, '')
  return { html, w, h }
}

export function ArchitectureDiagram({ code, idKey }: { code: string; idKey: string }) {
  const [svg, setSvg] = useState('')
  const [dim, setDim] = useState({ w: 900, h: 600 })
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [zoomOpen, setZoomOpen] = useState(false)
  useEffect(() => {
    let cancelled = false
    setError(null)
    setLoading(true)
    loadMermaid()
      .then((mermaid) => {
        const p = plate()

        mermaid.initialize({
          startOnLoad: false,
          theme: 'base',
          securityLevel: 'loose',
          fontFamily: "system-ui, 'Segoe UI', Roboto, 'Noto Sans KR', sans-serif",
          flowchart: {
            htmlLabels: true,
            // 인쇄 도판은 곡선을 쓰지 않는다. 선이 어디서 어디로 가는지가
            // 모양보다 중요해서 직선이 읽기 쉽다.
            curve: 'linear',
            nodeSpacing: 40,
            rankSpacing: 64,
            padding: 12,
            // 기본값(200px)은 한국어에서 '…아니 / 다' 처럼 낱말을 잘라 놓는다.
            // 줄바꿈은 필자가 <br/> 로 정하게 두고, 자동 줄바꿈은 넉넉히 뒤로 민다.
            wrappingWidth: 300,
            useMaxWidth: false,
          },
          sequence: { useMaxWidth: false, actorMargin: 62, boxMargin: 12 },
          // 도판 양식: 종이 위의 잉크. 상자는 전부 같은 무게로 두고,
          // 색은 한 곳(:::accent)에만 쓴다 — 색이 여러 개면 강조가 사라진다.
          themeVariables: {
            darkMode: !p.isLight,
            background: p.paper,
            fontSize: '13.5px',
            primaryColor: p.paper,
            primaryTextColor: p.ink,
            primaryBorderColor: p.ink,
            secondaryColor: p.paper,
            secondaryTextColor: p.ink,
            secondaryBorderColor: p.ink,
            tertiaryColor: p.paper,
            tertiaryTextColor: p.ink,
            tertiaryBorderColor: p.ink,
            lineColor: p.ink,
            textColor: p.ink,
            mainBkg: p.paper,
            nodeBorder: p.ink,
            clusterBkg: 'transparent',
            clusterBorder: p.ink,
            edgeLabelBackground: p.paper,
            titleColor: p.ink,
            // 시퀀스
            actorBkg: p.paper,
            actorBorder: p.ink,
            actorTextColor: p.ink,
            actorLineColor: p.faint,
            signalColor: p.ink,
            signalTextColor: p.ink,
            labelBoxBkgColor: p.paper,
            labelBoxBorderColor: p.ink,
            labelTextColor: p.ink,
            noteBkgColor: p.accentBg,
            noteTextColor: p.ink,
            noteBorderColor: p.ink,
            // 상태도
            labelColor: p.ink,
            altBackground: p.paper,
          },
        })
        const id = `mmd-${idKey.replace(/[^a-zA-Z0-9]/g, '')}-${seq++}`
        return mermaid.render(id, withStandardClasses(code, p))
      })
      .then(({ svg }) => {
        if (cancelled) return
        const n = normalize(svg)
        setSvg(n.html)
        setDim({ w: n.w, h: n.h })
        setLoading(false)
      })
      .catch((e) => {
        if (cancelled) return
        setError(String(e?.message ?? e))
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [code, idKey])

  if (error) {
    return (
      <div className="rounded-lg border border-(--color-border) bg-(--color-bg) p-3">
        <div className="text-xs text-red-400 mb-2">다이어그램 렌더 실패 — 원본 표시</div>
        <pre className="text-xs text-(--color-muted) overflow-auto whitespace-pre-wrap">{code}</pre>
      </div>
    )
  }

  return (
    <>
      <div className="rounded-lg border border-(--color-border) bg-(--color-bg) relative group">
        {loading && <div className="p-6 text-xs text-(--color-muted)">다이어그램 그리는 중…</div>}
        {!loading && (
          <button
            onClick={() => setZoomOpen(true)}
            className="absolute top-2 right-2 z-10 px-2.5 py-1 text-xs rounded-md bg-(--color-panel)/90 backdrop-blur border border-(--color-border) text-(--color-muted) hover:text-(--color-accent) hover:border-(--color-accent) transition-colors"
          >
            ⛶ 크게 보기
          </button>
        )}
        {/* 인라인은 '읽히는 미리보기'다. 원본 비율을 지키되 폭을 넘으면 줄이고,
            세로로 긴 그림은 잘라서 높이를 먹지 않게 한다 — 전체는 모달에서 본다. */}
        {!loading && (
          <div className="mmd overflow-auto p-3 max-h-[68vh]">
            <div
              style={{ width: dim.w, height: dim.h, maxWidth: '100%', aspectRatio: `${dim.w} / ${dim.h}` }}
              dangerouslySetInnerHTML={{ __html: svg }}
            />
          </div>
        )}
      </div>

      {zoomOpen && (
        <ZoomModal svg={svg} w={dim.w} h={dim.h} onClose={() => setZoomOpen(false)} />
      )}
    </>
  )
}

// 전체화면 뷰어.
//
// 전에는 스크롤 컨테이너 안의 inline-block 에 transform: scale() 만 걸었다.
// transform 은 레이아웃 박스를 바꾸지 않아서 스크롤 영역은 확대 전 크기로 남고,
// 확대된 그림의 오른쪽·아래가 스크롤로 닿지 않는 곳에 잘려 나갔다.
// 이제 바깥 상자에 '확대된 치수'를 실제로 주고 안쪽만 transform 으로 키운다.
function ZoomModal({
  svg,
  w,
  h,
  onClose,
}: {
  svg: string
  w: number
  h: number
  onClose: () => void
}) {
  const viewport = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(1)
  const [fitScale, setFitScale] = useState(1)
  const dragging = useRef<{ x: number; y: number; sl: number; st: number } | null>(null)

  const PAD = 48

  // 열릴 때 '화면에 맞춤'을 기본으로 — 전체 구조를 먼저 보여주고, 확대는 사용자가 고른다.
  const fit = useCallback(() => {
    const el = viewport.current
    if (!el) return 1
    const s = Math.min((el.clientWidth - PAD) / w, (el.clientHeight - PAD) / h)
    const clamped = Math.max(0.1, Math.min(4, s))
    setFitScale(clamped)
    setScale(clamped)
    return clamped
  }, [w, h])

  useLayoutEffect(() => {
    fit()
    const el = viewport.current
    if (!el || typeof ResizeObserver === 'undefined') return
    // 창 크기가 바뀌면 맞춤 배율 기준도 다시 잡는다(현재 배율은 건드리지 않는다).
    const ro = new ResizeObserver(() => {
      const v = viewport.current
      if (!v) return
      const s = Math.min((v.clientWidth - PAD) / w, (v.clientHeight - PAD) / h)
      setFitScale(Math.max(0.1, Math.min(4, s)))
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [fit, w, h])

  // ESC 는 capture 단계에서 처리하고 전파를 막아, 상위 상세 모달의 ESC 핸들러보다
  // 먼저 동작하게 한다(줌만 닫히고 상세는 유지).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopImmediatePropagation()
        onClose()
      } else if (e.key === '+' || e.key === '=') setScale((s) => Math.min(4, s + 0.15))
      else if (e.key === '-' || e.key === '_') setScale((s) => Math.max(0.1, s - 0.15))
      else if (e.key === '0') fit()
      else if (e.key === '1') setScale(1)
      else return
      if (e.key !== 'Escape') e.preventDefault()
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [onClose, fit])

  // 커서 위치를 고정한 채 확대 — 그림 한구석을 들여다볼 때 그 점이 달아나지 않는다.
  const onWheel = (e: React.WheelEvent) => {
    if (!(e.ctrlKey || e.metaKey)) return
    e.preventDefault()
    const el = viewport.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const px = e.clientX - rect.left + el.scrollLeft
    const py = e.clientY - rect.top + el.scrollTop
    setScale((prev) => {
      const next = Math.max(0.1, Math.min(4, prev * (e.deltaY < 0 ? 1.12 : 1 / 1.12)))
      const k = next / prev
      requestAnimationFrame(() => {
        el.scrollLeft = px * k - (e.clientX - rect.left)
        el.scrollTop = py * k - (e.clientY - rect.top)
      })
      return next
    })
  }

  const onDown = (e: React.MouseEvent) => {
    const el = viewport.current
    if (!el || e.button !== 0) return
    dragging.current = { x: e.clientX, y: e.clientY, sl: el.scrollLeft, st: el.scrollTop }
  }
  const onMove = (e: React.MouseEvent) => {
    const d = dragging.current
    const el = viewport.current
    if (!d || !el) return
    el.scrollLeft = d.sl - (e.clientX - d.x)
    el.scrollTop = d.st - (e.clientY - d.y)
  }
  const endDrag = () => {
    dragging.current = null
  }

  const pct = Math.round(scale * 100)

  return (
    <div className="fixed inset-0 z-[60] flex flex-col bg-(--color-bg)">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-(--color-border) shrink-0">
        <span className="text-sm font-medium text-(--color-text)">다이어그램</span>
        <span className="text-[11px] text-(--color-muted) hidden sm:inline">
          드래그로 이동 · Ctrl+휠 확대 · 0 맞춤 · 1 원본 · Esc 닫기
        </span>
        <div className="ml-auto flex items-center gap-1">
          <ZoomBtn onClick={() => setScale((s) => Math.max(0.1, s - 0.15))}>−</ZoomBtn>
          <span className="w-14 text-center text-xs text-(--color-muted) tabular-nums">{pct}%</span>
          <ZoomBtn onClick={() => setScale((s) => Math.min(4, s + 0.15))}>＋</ZoomBtn>
          <ZoomBtn onClick={fit} active={Math.abs(scale - fitScale) < 0.005}>
            맞춤
          </ZoomBtn>
          <ZoomBtn onClick={() => setScale(1)} active={Math.abs(scale - 1) < 0.005}>
            100%
          </ZoomBtn>
          <ZoomBtn onClick={onClose}>✕ 닫기</ZoomBtn>
        </div>
      </div>

      <div
        ref={viewport}
        className="mmd flex-1 overflow-auto select-none cursor-grab active:cursor-grabbing"
        onWheel={onWheel}
        onMouseDown={onDown}
        onMouseMove={onMove}
        onMouseUp={endDrag}
        onMouseLeave={endDrag}
      >
        {/* 바깥 상자가 '확대된 실제 치수'를 차지한다 → 스크롤 범위가 그림과 일치한다.
            그림이 화면보다 작을 때는 가운데로 온다. */}
        <div className="min-w-full min-h-full flex items-center justify-center p-6">
          <div style={{ width: w * scale, height: h * scale, flex: '0 0 auto' }}>
            <div
              style={{
                width: w,
                height: h,
                transform: `scale(${scale})`,
                transformOrigin: 'top left',
              }}
              dangerouslySetInnerHTML={{ __html: svg }}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

function ZoomBtn({
  onClick,
  active,
  children,
}: {
  onClick: () => void
  active?: boolean
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={
        'px-2.5 py-1 text-xs rounded-md border transition-colors ' +
        (active
          ? 'border-(--color-accent) text-(--color-accent)'
          : 'border-(--color-border) text-(--color-muted) hover:text-(--color-text) hover:border-(--color-accent)/50')
      }
    >
      {children}
    </button>
  )
}
