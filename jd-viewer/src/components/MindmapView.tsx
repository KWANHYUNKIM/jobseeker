import { useEffect, useRef, useState } from 'react'
import { SearchInput } from './ui'
import { Transformer } from 'markmap-lib'
import { Markmap, loadCSS, loadJS, globalCSS } from 'markmap-view'

const transformer = new Transformer()

let stylesInjected = false
const DARK_OVERRIDE_CSS = `
.markmap-foreign {
  color: #e6e7eb;
  font-size: 16px;
  line-height: 1.6;
  font-family: system-ui, -apple-system, 'Segoe UI', Roboto, 'Noto Sans KR', sans-serif;
}
.markmap-foreign strong { color: #fff; font-weight: 700; }
.markmap-foreign em { color: #d1d5db; font-style: italic; }
.markmap-foreign a { color: #7dd3fc; text-decoration: none; }
.markmap-foreign a:hover { color: #bae6fd; text-decoration: underline; }
.markmap-foreign code {
  background: rgba(96,165,250,0.16);
  color: #93c5fd;
  padding: 1.5px 7px;
  border-radius: 5px;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  font-family: 'SF Mono', Menlo, Monaco, monospace;
}
.markmap-foreign p { margin: 0; }
/* 루트(0)·도메인(1) 큼직하게, 기업(2) 강조 */
.markmap-node[data-depth="0"] .markmap-foreign { font-size: 22px; font-weight: 800; }
.markmap-node[data-depth="1"] .markmap-foreign { font-size: 19px; font-weight: 700; }
.markmap-node[data-depth="2"] .markmap-foreign { font-size: 16.5px; font-weight: 700; }
.markmap-link { stroke-width: 2.2; opacity: 0.9; }
.markmap-node circle { stroke-width: 2.4; r: 5; cursor: pointer; }
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
  const [domains, setDomains] = useState<string[]>([])
  const [query, setQuery] = useState('')
  const [matchCount, setMatchCount] = useState<number | null>(null)

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
        // 기본: 루트 + 도메인(depth1)까지만 펼침. 기업/직군은 접어 가독성 확보.
        setFoldRecursive(rootNode, 0, 1)
        rootRef.current = rootNode
        setDomains(
          (findTopRoles(rootNode) || [])
            .map((n) => plainText(n.content))
            .filter((t) => t && !t.startsWith('📊')),
        )

        if (mmRef.current) {
          mmRef.current.destroy()
          mmRef.current = null
        }
        const mm = Markmap.create(svgRef.current, {
          duration: 300,
          maxWidth: 360,
          spacingHorizontal: 140,
          spacingVertical: 20,
          paddingX: 16,
          nodeMinHeight: 28,
          initialExpandLevel: -1,
          maxInitialScale: 1.1,
          fitRatio: 0.88,
          color: (node: { state: { path: string } }) => {
            const colors = ['#c084fc', '#60a5fa', '#34d399', '#fbbf24', '#f87171', '#a78bfa', '#22d3ee']
            const i = (node.state.path.split('.').length - 1) % colors.length
            return colors[i]
          },
        })
        // ⚠️ 여기서 ref 를 늦게 잡으면 안 된다. 개발 모드의 재마운트에서 정리 함수가
        // 먼저 돌면 그때는 mmRef 가 아직 비어 있어 아무것도 못 지우고, 뒤늦게 대입된
        // 인스턴스만 남는다 — 화면에는 맵이 보이는데 **펼치기·접기·검색이 죽은 인스턴스를
        // 잡고 있어 아무 반응이 없다.** 만들자마자 잡고, 그 사이 취소됐으면 스스로 지운다.
        if (cancelled) {
          mm.destroy()
          return
        }
        mmRef.current = mm
        await mm.setData(rootNode as never)
        await mm.fit()
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

  // openToDepth=1 → 도메인만 / 0 → 모두 펼침
  const setAllFold = async (openToDepth: number) => {
    if (!mmRef.current || !rootRef.current) return
    const walk = (n: MMNode, depth: number) => {
      n.payload = n.payload || {}
      n.payload.fold = depth >= openToDepth ? 1 : 0
      if (n.children) for (const c of n.children) walk(c, depth + 1)
    }
    walk(rootRef.current, 0)
    await mmRef.current.setData(rootRef.current as never)
    await mmRef.current.fit()
  }

  // 도메인 클릭: 해당 도메인의 기업 목록까지만 펼치고(직군/공고는 접음) 나머지 도메인은 접는다.
  // 마인드맵의 검색은 목록 필터와 다르다. 노드를 지우면 가지가 끊겨 어디에 걸린
  // 것인지 알 수 없으므로, **걸린 가지만 펼치고 나머지는 접는다.**
  useEffect(() => {
    const needle = query.trim().toLowerCase()
    const t = setTimeout(async () => {
      const mm = mmRef.current
      const root = rootRef.current
      if (!mm || !root) return
      if (!needle) {
        setMatchCount(null)
        const reset = (n: MMNode, depth: number) => {
          n.payload = n.payload || {}
          n.payload.fold = depth >= 1 ? 1 : 0
          if (n.children) for (const c of n.children) reset(c, depth + 1)
        }
        reset(root, 0)
      } else {
        let found = 0
        const walk = (n: MMNode): boolean => {
          const self = plainText(n.content).toLowerCase().includes(needle)
          if (self) found += 1
          let inChild = false
          if (n.children) for (const c of n.children) inChild = walk(c) || inChild
          n.payload = n.payload || {}
          n.payload.fold = self || inChild ? 0 : 1
          return self || inChild
        }
        walk(root)
        setMatchCount(found)
      }
      await mm.setData(root as never)
      await mm.fit()
    }, 250) // 글자마다 트리 전체를 다시 그리면 큰 맵에서 입력이 밀린다
    return () => clearTimeout(t)
  }, [query])

  const jumpToDomain = async (domainName: string) => {
    if (!mmRef.current || !rootRef.current) return
    const walk = (n: MMNode, depth: number, target: string) => {
      const clean = plainText(n.content)
      n.payload = n.payload || {}
      if (depth === 0) {
        n.payload.fold = 0
        if (n.children) for (const c of n.children) walk(c, depth + 1, target)
      } else if (depth === 1) {
        // 도메인 레벨: 타겟만 펼치고(기업 보임) 나머지는 접기
        if (clean === target) {
          n.payload.fold = 0
          // 기업(depth2)은 펼치되 그 하위(직군)는 접어 둔다
          if (n.children) for (const c of n.children) (c.payload = c.payload || {}).fold = 1
        } else {
          n.payload.fold = 1
        }
      }
    }
    walk(rootRef.current, 0, domainName)
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
        <SearchInput
          value={query}
          onChange={setQuery}
          placeholder="기업·직군·기술 검색"
          className="w-full sm:w-64"
        />
        {matchCount !== null && (
          <span className="text-[11px] text-(--color-muted)">
            {matchCount === 0 ? '걸리는 마디가 없다' : <>걸린 마디 <b className="text-(--color-text)">{matchCount}</b></>}
          </span>
        )}
        <span className="text-[11px] text-(--color-text)/60 uppercase tracking-wider font-semibold mr-1">
          도메인
        </span>
        {domains.map((r) => (
          <button
            key={r}
            onClick={() => jumpToDomain(r)}
            className="text-xs px-3 py-1.5 rounded-full text-(--color-text) hover:bg-(--color-accent)/20 hover:text-(--color-accent) border border-(--color-border) hover:border-(--color-accent) font-medium transition"
            title={`${r} 의 기업만 펼치기`}
          >
            {r}
          </button>
        ))}
        <div className="w-px h-5 bg-(--color-border) mx-1" />
        <button
          onClick={() => setAllFold(99)}
          className="text-xs px-3 py-1.5 rounded text-(--color-text) hover:bg-(--hover) border border-(--color-border)"
        >
          모두 펼치기
        </button>
        <button
          onClick={() => setAllFold(2)}
          className="text-xs px-3 py-1.5 rounded text-(--color-text) hover:bg-(--hover) border border-(--color-border)"
        >
          기업까지
        </button>
        <button
          onClick={() => setAllFold(1)}
          className="text-xs px-3 py-1.5 rounded text-(--color-text) hover:bg-(--hover) border border-(--color-border)"
        >
          도메인만
        </button>
        <button
          onClick={handleFit}
          className="text-xs px-3 py-1.5 rounded text-(--color-text) hover:bg-(--hover) border border-(--color-border)"
        >
          화면 맞춤
        </button>
        <span className="ml-auto text-[11px] text-(--color-text)/55 hidden md:inline">
          노드 클릭 = 펼침/접힘 · 휠 = 확대·축소 · 드래그 = 이동
        </span>
      </div>

      {/* 마인드맵 영역 - 풀폭 */}
      <div className="flex-1 min-w-0 min-h-0 relative bg-(--color-bg)">
        {loading && (
          <div className="absolute inset-0 pointer-events-none flex items-center justify-center gap-3 text-(--color-text)/60 z-10 text-sm">
            <span className="jd-spinner" aria-hidden />
            마인드맵 불러오는 중…
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
