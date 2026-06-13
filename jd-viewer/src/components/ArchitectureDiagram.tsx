import { useEffect, useState } from 'react'

// Mermaid 는 번들이 커서 동적 import 로 코드 스플릿한다(레이더 상세를 열 때만 로드).
let mermaidReady: Promise<typeof import('mermaid').default> | null = null
function loadMermaid() {
  if (!mermaidReady) {
    mermaidReady = import('mermaid').then((m) => {
      m.default.initialize({
        startOnLoad: false,
        theme: 'dark',
        securityLevel: 'loose',
        flowchart: { htmlLabels: true, curve: 'basis', nodeSpacing: 55, rankSpacing: 70, padding: 12 },
        themeVariables: { fontSize: '15px' },
      })
      return m.default
    })
  }
  return mermaidReady
}

let seq = 0

export function ArchitectureDiagram({ code, idKey }: { code: string; idKey: string }) {
  const [svg, setSvg] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [zoomOpen, setZoomOpen] = useState(false)
  const [scale, setScale] = useState(1.4)

  useEffect(() => {
    let cancelled = false
    setError(null)
    setLoading(true)
    loadMermaid()
      .then((mermaid) => {
        const id = `mmd-${idKey.replace(/[^a-zA-Z0-9]/g, '')}-${seq++}`
        return mermaid.render(id, code)
      })
      .then(({ svg }) => {
        if (cancelled) return
        setSvg(svg)
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

  // 전체화면 모달: ESC 닫기. capture 단계에서 처리하고 전파를 막아, 상위 상세 모달의
  // ESC 핸들러보다 먼저 동작하게 한다(줌만 닫히고 상세는 유지).
  useEffect(() => {
    if (!zoomOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopImmediatePropagation()
        setZoomOpen(false)
      }
      if (e.key === '+' || e.key === '=') setScale((s) => Math.min(4, s + 0.2))
      if (e.key === '-') setScale((s) => Math.max(0.4, s - 0.2))
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [zoomOpen])

  if (error) {
    return (
      <div className="rounded border border-(--color-border) bg-(--color-bg) p-3">
        <div className="text-xs text-red-400 mb-2">다이어그램 렌더 실패 — 원본 표시</div>
        <pre className="text-xs text-(--color-muted) overflow-auto whitespace-pre-wrap">{code}</pre>
      </div>
    )
  }

  return (
    <>
      <div className="rounded border border-(--color-border) bg-(--color-bg) relative">
        {loading && <div className="p-6 text-xs text-(--color-muted)">다이어그램 그리는 중…</div>}
        {!loading && (
          <button
            onClick={() => {
              setScale(1.6)
              setZoomOpen(true)
            }}
            className="absolute top-2 right-2 z-10 px-2.5 py-1 text-xs rounded bg-(--color-panel) border border-(--color-border) text-(--color-muted) hover:text-(--color-accent) hover:border-(--color-accent)"
          >
            ⛶ 크게 보기
          </button>
        )}
        {/* 인라인: 모달 폭을 꽉 채워 크게 표시. 가로가 넘치면 스크롤. */}
        <div
          className="overflow-auto p-3 [&_svg]:w-full [&_svg]:h-auto [&_svg]:min-w-[640px]"
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      </div>

      {zoomOpen && (
        <div
          className="fixed inset-0 z-[60] flex flex-col bg-black/85"
          onClick={() => setZoomOpen(false)}
        >
          <div
            className="flex items-center gap-2 px-4 py-2 border-b border-white/10 text-(--color-text)"
            onClick={(e) => e.stopPropagation()}
          >
            <span className="text-sm font-medium">아키텍처 다이어그램</span>
            <div className="ml-auto flex items-center gap-1">
              <ZoomBtn onClick={() => setScale((s) => Math.max(0.4, s - 0.2))}>−</ZoomBtn>
              <span className="w-12 text-center text-xs text-(--color-muted)">
                {Math.round(scale * 100)}%
              </span>
              <ZoomBtn onClick={() => setScale((s) => Math.min(4, s + 0.2))}>＋</ZoomBtn>
              <ZoomBtn onClick={() => setScale(1.6)}>리셋</ZoomBtn>
              <ZoomBtn onClick={() => setZoomOpen(false)}>✕ 닫기</ZoomBtn>
            </div>
          </div>
          <div
            className="flex-1 overflow-auto p-8"
            onClick={(e) => e.stopPropagation()}
          >
            <div
              className="origin-top-left inline-block transition-transform [&_svg]:h-auto"
              style={{ transform: `scale(${scale})` }}
              dangerouslySetInnerHTML={{ __html: svg }}
            />
          </div>
        </div>
      )}
    </>
  )
}

function ZoomBtn({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className="px-2.5 py-1 text-xs rounded bg-white/10 hover:bg-white/20 text-(--color-text) border border-white/10"
    >
      {children}
    </button>
  )
}
