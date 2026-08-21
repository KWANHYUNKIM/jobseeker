import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

// Mermaid 는 번들이 커서 동적 import 로 코드 스플릿한다(다이어그램을 열 때만 로드).
let mermaidReady: Promise<typeof import('mermaid').default> | null = null
function loadMermaid() {
  if (!mermaidReady) mermaidReady = import('mermaid').then((m) => m.default)
  return mermaidReady
}

let seq = 0

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
  const [themeV, setThemeV] = useState(0)

  // 앱 테마 토글 시 다이어그램을 현재 테마로 다시 렌더
  useEffect(() => {
    const on = () => setThemeV((v) => v + 1)
    window.addEventListener('themechange', on)
    return () => window.removeEventListener('themechange', on)
  }, [])

  useEffect(() => {
    let cancelled = false
    setError(null)
    setLoading(true)
    loadMermaid()
      .then((mermaid) => {
        const css = getComputedStyle(document.documentElement)
        const v = (n: string, fb: string) => css.getPropertyValue(n).trim() || fb
        const isLight = document.documentElement.classList.contains('light')
        const bg = v('--color-bg', '#0b0c10')
        const panel = v('--color-panel', '#15171d')
        const border = v('--color-border', '#2a2d36')
        const text = v('--color-text', '#e6e7eb')
        const muted = v('--color-muted', '#9aa0aa')
        const accent = v('--color-accent', '#03C75A')

        mermaid.initialize({
          startOnLoad: false,
          theme: 'base',
          securityLevel: 'loose',
          fontFamily: "system-ui, 'Segoe UI', Roboto, 'Noto Sans KR', sans-serif",
          flowchart: {
            htmlLabels: true,
            curve: 'basis',
            nodeSpacing: 46,
            rankSpacing: 68,
            padding: 14,
            useMaxWidth: false,
          },
          sequence: { useMaxWidth: false, actorMargin: 62, boxMargin: 12 },
          // 팔레트를 앱과 묶는다. 노드는 패널색 위에 옅은 액센트 테두리 —
          // 회색 상자만 늘어놓으면 어디가 중요한지 그림이 말해 주지 못한다.
          themeVariables: {
            darkMode: !isLight,
            background: bg,
            fontSize: '14px',
            primaryColor: panel,
            primaryTextColor: text,
            primaryBorderColor: isLight ? border : `${accent}66`,
            secondaryColor: bg,
            secondaryTextColor: muted,
            secondaryBorderColor: border,
            tertiaryColor: bg,
            tertiaryTextColor: muted,
            tertiaryBorderColor: border,
            lineColor: muted,
            textColor: text,
            mainBkg: panel,
            nodeBorder: isLight ? border : `${accent}66`,
            clusterBkg: 'transparent',
            clusterBorder: border,
            edgeLabelBackground: panel,
            titleColor: text,
            // 시퀀스
            actorBkg: panel,
            actorBorder: isLight ? border : `${accent}66`,
            actorTextColor: text,
            actorLineColor: muted,
            signalColor: text,
            signalTextColor: muted,
            labelBoxBkgColor: panel,
            labelBoxBorderColor: border,
            labelTextColor: text,
            noteBkgColor: isLight ? '#f4f5f7' : '#1d2028',
            noteTextColor: text,
            noteBorderColor: border,
            // 상태도
            labelColor: text,
            altBackground: bg,
          },
        })
        const id = `mmd-${idKey.replace(/[^a-zA-Z0-9]/g, '')}-${seq++}`
        return mermaid.render(id, code)
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
  }, [code, idKey, themeV])

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
