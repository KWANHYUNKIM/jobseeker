import { useEffect, useRef, useState } from 'react'
import { Transformer } from 'markmap-lib'
import { Markmap, loadCSS, loadJS } from 'markmap-view'

const transformer = new Transformer()

export function MindmapView() {
  const svgRef = useRef<SVGSVGElement | null>(null)
  const mmRef = useRef<Markmap | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const res = await fetch('/mindmap.md')
        if (!res.ok) throw new Error(`HTTP ${res.status} - mindmap.md`)
        const md = await res.text()
        const { root, features } = transformer.transform(md)
        const assets = transformer.getUsedAssets(features)
        if (assets.styles) loadCSS(assets.styles)
        if (assets.scripts) loadJS(assets.scripts)
        if (cancelled || !svgRef.current) return
        if (mmRef.current) {
          mmRef.current.destroy()
          mmRef.current = null
        }
        const mm = Markmap.create(svgRef.current, {
          duration: 300,
          maxWidth: 380,
          spacingHorizontal: 90,
          spacingVertical: 8,
          paddingX: 8,
          color: (node: { state: { path: string } }) => {
            const colors = ['#c084fc', '#60a5fa', '#34d399', '#fbbf24', '#f87171', '#a78bfa', '#22d3ee']
            const i = (node.state.path.split('.').length - 1) % colors.length
            return colors[i]
          },
        })
        await mm.setData(root)
        await mm.fit()
        mmRef.current = mm
        setLoading(false)
      } catch (e) {
        if (!cancelled) {
          setError(String(e))
          setLoading(false)
        }
      }
    }
    load()
    return () => {
      cancelled = true
      if (mmRef.current) {
        mmRef.current.destroy()
        mmRef.current = null
      }
    }
  }, [])

  const handleFit = () => {
    mmRef.current?.fit()
  }

  if (error) {
    return (
      <div className="p-8 text-red-400">
        마인드맵 로드 실패: {error}
        <br />
        <span className="text-(--color-muted) text-sm">
          jd-viewer/public/mindmap.md 가 있는지 확인하세요. (생성: <code>python3 bin/build_mindmap.py</code>)
        </span>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col min-w-0 min-h-0">
      <div className="flex items-center gap-3 px-4 py-2 border-b border-(--color-border) bg-(--color-panel)">
        <span className="text-sm text-(--color-muted)">
          직군별 커리어 마인드맵 — 데이터: <code>public/mindmap.md</code>
        </span>
        <div className="ml-auto flex gap-2">
          <button
            onClick={handleFit}
            className="px-3 py-1 text-sm bg-(--color-bg) border border-(--color-border) rounded hover:border-(--color-accent)"
          >
            화면맞춤
          </button>
        </div>
      </div>
      {loading && (
        <div className="absolute inset-0 pointer-events-none flex items-center justify-center text-(--color-muted)">
          마인드맵 로딩 중…
        </div>
      )}
      <svg
        ref={svgRef}
        className="flex-1 w-full h-full"
        style={{ background: 'var(--color-bg)' }}
      />
    </div>
  )
}
