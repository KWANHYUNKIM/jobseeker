import { useEffect, useRef, useState } from 'react'
import { Transformer } from 'markmap-lib'
import { Markmap, loadCSS, loadJS, globalCSS } from 'markmap-view'

const transformer = new Transformer()

let stylesInjected = false
const DARK_OVERRIDE_CSS = `
.markmap-foreign {
  color: #e6e7eb;
  font-size: 15px;
  line-height: 1.55;
  font-family: system-ui, -apple-system, 'Segoe UI', Roboto, 'Noto Sans KR', sans-serif;
}
.markmap-foreign strong { color: #fff; font-weight: 700; }
.markmap-foreign em { color: #d1d5db; font-style: italic; }
.markmap-foreign code {
  background: rgba(255,255,255,0.10);
  color: #fbbf24;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'SF Mono', Menlo, Monaco, monospace;
}
.markmap-foreign p { margin: 0; }
/* 루트와 1단계(직군) 노드는 더 굵고 크게 */
.markmap-node[data-depth="0"] .markmap-foreign,
.markmap-node[data-depth="1"] .markmap-foreign {
  font-size: 17px;
  font-weight: 700;
}
.markmap-link { stroke-width: 2; opacity: 0.9; }
.markmap-node circle { stroke-width: 2; }
.markmap-node text { font-weight: 600; }
`

function ensureMarkmapStyles() {
  if (stylesInjected || typeof document === 'undefined') return
  const style = document.createElement('style')
  style.setAttribute('data-markmap-global', '')
  style.textContent = globalCSS + '\n' + DARK_OVERRIDE_CSS
  document.head.appendChild(style)
  stylesInjected = true
}

type MMNode = {
  content: string
  children?: MMNode[]
  payload?: { fold?: number }
  state?: { path?: string }
}

// markmap-lib transformer 가 한글을 &#xXXXX; numeric entity 로 escape 함.
// 일부 환경에서 SVG foreignObject 안의 innerHTML 가 디코드 안 되는 경우가 있어
// setData 전에 직접 디코드한다 (HTML 태그 <strong> 등은 보존).
function decodeNumericEntities(s: string): string {
  return s
    .replace(/&#x([\da-fA-F]+);/g, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(parseInt(d, 10)))
}

function decodeAllContent(node: MMNode) {
  if (typeof node.content === 'string') node.content = decodeNumericEntities(node.content)
  if (node.children) for (const c of node.children) decodeAllContent(c)
}

function plainText(html: string): string {
  return html.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim()
}

function setFoldRecursive(node: MMNode, depth: number, maxOpen: number) {
  node.payload = node.payload || {}
  node.payload.fold = depth >= maxOpen ? 1 : 0
  if (node.children) {
    for (const c of node.children) setFoldRecursive(c, depth + 1, maxOpen)
  }
}

function findTopRoles(root: MMNode): MMNode[] {
  return root.children || []
}

export function MindmapView() {
  const svgRef = useRef<SVGSVGElement | null>(null)
  const mmRef = useRef<Markmap | null>(null)
  const rootRef = useRef<MMNode | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [roles, setRoles] = useState<string[]>([])

  useEffect(() => {
    let cancelled = false
    ensureMarkmapStyles()
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
        // SVG 가 0×0 이면 layout 이 깨지므로 사이즈 잡힐 때까지 대기
        const ensureSize = () => new Promise<void>((resolve) => {
          const check = () => {
            const el = svgRef.current
            if (!el) return resolve()
            const r = el.getBoundingClientRect()
            if (r.width > 0 && r.height > 0) resolve()
            else requestAnimationFrame(check)
          }
          check()
        })
        await ensureSize()
        if (cancelled || !svgRef.current) return

        const rootNode = root as unknown as MMNode
        decodeAllContent(rootNode)
        setFoldRecursive(rootNode, 0, 2)
        rootRef.current = rootNode
        setRoles((findTopRoles(rootNode) || []).map((n) => plainText(n.content)))

        if (mmRef.current) {
          mmRef.current.destroy()
          mmRef.current = null
        }
        const mm = Markmap.create(svgRef.current, {
          duration: 300,
          maxWidth: 420,
          spacingHorizontal: 120,
          spacingVertical: 14,
          paddingX: 14,
          nodeMinHeight: 22,
          initialExpandLevel: -1,
          maxInitialScale: 1.2,
          fitRatio: 0.92,
          color: (node: { state: { path: string } }) => {
            const colors = ['#c084fc', '#60a5fa', '#34d399', '#fbbf24', '#f87171', '#a78bfa', '#22d3ee']
            const i = (node.state.path.split('.').length - 1) % colors.length
            return colors[i]
          },
        })
        await mm.setData(rootNode as never)
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

  // 컨테이너 리사이즈 시 fit
  useEffect(() => {
    const el = svgRef.current
    if (!el) return
    const ro = new ResizeObserver(() => {
      if (mmRef.current) mmRef.current.fit()
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const handleFit = () => {
    mmRef.current?.fit()
  }

  const setAllFold = async (fold: 0 | 1) => {
    if (!mmRef.current || !rootRef.current) return
    const walk = (n: MMNode, depth: number) => {
      n.payload = n.payload || {}
      // 루트(0)와 직군(1)은 항상 펼침
      n.payload.fold = depth <= 1 ? 0 : fold
      if (n.children) for (const c of n.children) walk(c, depth + 1)
    }
    walk(rootRef.current, 0)
    await mmRef.current.setData(rootRef.current as never)
    await mmRef.current.fit()
  }

  const jumpToRole = async (roleName: string) => {
    if (!mmRef.current || !rootRef.current) return
    const walk = (n: MMNode, depth: number, target: string) => {
      const clean = plainText(n.content)
      n.payload = n.payload || {}
      if (depth === 1) {
        // 직군 레벨: 타겟만 펼치고 나머지는 접기
        if (clean === target) {
          n.payload.fold = 0
          if (n.children) for (const c of n.children) openAll(c)
        } else {
          n.payload.fold = 1
        }
      } else if (depth === 0) {
        n.payload.fold = 0
        if (n.children) for (const c of n.children) walk(c, depth + 1, target)
      }
    }
    const openAll = (n: MMNode) => {
      n.payload = n.payload || {}
      n.payload.fold = 0
      if (n.children) for (const c of n.children) openAll(c)
    }
    walk(rootRef.current, 0, roleName)
    await mmRef.current.setData(rootRef.current as never)
    await mmRef.current.fit()
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
    <div className="flex flex-1 flex-col min-w-0 min-h-0">
      {/* 상단 toolbar - 직군 점프 + 컨트롤 */}
      <div className="border-b border-(--color-border) bg-(--color-panel) px-4 py-2 flex flex-wrap items-center gap-2 shrink-0">
        <span className="text-[11px] text-white/60 uppercase tracking-wider font-semibold mr-1">
          직군
        </span>
        {roles.map((r) => (
          <button
            key={r}
            onClick={() => jumpToRole(r)}
            className="text-xs px-3 py-1.5 rounded-full text-white hover:bg-(--color-accent)/20 hover:text-(--color-accent) border border-(--color-border) hover:border-(--color-accent) font-medium transition"
            title={`${r} 만 펼치기`}
          >
            {r}
          </button>
        ))}
        <div className="w-px h-5 bg-(--color-border) mx-1" />
        <button
          onClick={() => setAllFold(0)}
          className="text-xs px-3 py-1.5 rounded text-white hover:bg-white/10 border border-(--color-border)"
        >
          모두 펼치기
        </button>
        <button
          onClick={() => setAllFold(1)}
          className="text-xs px-3 py-1.5 rounded text-white hover:bg-white/10 border border-(--color-border)"
        >
          직군만
        </button>
        <button
          onClick={handleFit}
          className="text-xs px-3 py-1.5 rounded text-white hover:bg-white/10 border border-(--color-border)"
        >
          화면 맞춤
        </button>
        <span className="ml-auto text-[11px] text-white/55 hidden md:inline">
          노드 클릭 = 펼침/접힘 · 휠 = 확대·축소 · 드래그 = 이동
        </span>
      </div>

      {/* 마인드맵 영역 - 풀폭 */}
      <div className="flex-1 min-w-0 min-h-0 relative bg-(--color-bg)">
        {loading && (
          <div className="absolute inset-0 pointer-events-none flex items-center justify-center text-white/60 z-10 text-sm">
            마인드맵 로딩 중…
          </div>
        )}
        <svg
          ref={svgRef}
          className="absolute inset-0 w-full h-full"
          style={{ background: 'var(--color-bg)' }}
        />
      </div>
    </div>
  )
}
