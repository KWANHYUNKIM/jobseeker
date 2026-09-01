import { useEffect, useRef, useState } from 'react'
import { SearchInput } from './ui'
import * as d3 from 'd3'

// mindmap_tree.json 노드
interface TreeNode {
  name: string
  type: 'root' | 'domain' | 'company' | 'role'
  value?: number
  children?: TreeNode[]
  // role
  company?: string
  size?: string
  domain?: string
  tech?: string[]
  postings?: { title: string; url: string; site: string }[]
  // domain / company / root
  company_count?: number
  postings_total?: number
  total_jobs?: number
  domain_count?: number
}

const DOMAIN_COLORS = [
  '#c084fc', '#60a5fa', '#34d399', '#fbbf24', '#f87171', '#a78bfa',
  '#22d3ee', '#fb923c', '#f472b6', '#2dd4bf', '#a3e635', '#e879f9',
  '#38bdf8', '#facc15', '#4ade80', '#fca5a5', '#818cf8',
]

type HNode = d3.HierarchyCircularNode<TreeNode>

// 호버 툴팁 문구 — 구슬 종류별로 회사 이름 위주로 표시
function tipText(d: HNode): string {
  const t = d.data
  if (t.type === 'role') return `${t.company ?? ''} · ${t.name}${t.value ? ` (${t.value}건)` : ''}`
  if (t.type === 'company') return t.name
  if (t.type === 'domain') return `${t.name}${t.company_count ? ` · 회사 ${t.company_count}개` : ''}`
  return t.name
}

export function ClusterView() {
  const wrapRef = useRef<HTMLDivElement | null>(null)
  const svgRef = useRef<SVGSVGElement | null>(null)
  const tipRef = useRef<HTMLDivElement | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<TreeNode | null>(null)
  const [crumb, setCrumb] = useState<string[]>([])
  // 외부에서 호출할 zoom-out 핸들러
  const zoomOutRef = useRef<(() => void) | null>(null)
  // 검색은 원을 지우는 게 아니라 **거기로 확대한다** — 원 배치가 곧 규모의 그림이라
  // 걸러내면 그림 자체가 뜻을 잃는다. 이름으로 찾아 그 원으로 들어가는 쪽이 맞다.
  const zoomToNameRef = useRef<((q: string) => number) | null>(null)
  const [query, setQuery] = useState('')
  const [hitCount, setHitCount] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const res = await fetch('/mindmap_tree.json')
        if (!res.ok) throw new Error(`HTTP ${res.status} - mindmap_tree.json`)
        const data: TreeNode = await res.json()
        if (cancelled || !svgRef.current || !wrapRef.current) return
        render(data)
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
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function render(data: TreeNode) {
    const wrap = wrapRef.current!
    const W = Math.max(320, wrap.clientWidth)
    const H = Math.max(320, wrap.clientHeight)
    const size = Math.min(W, H)

    const domainColor = d3.scaleOrdinal<string, string>()
      .domain((data.children || []).map((d) => d.name))
      .range(DOMAIN_COLORS)

    const root: HNode = d3
      .pack<TreeNode>()
      .size([size, size])
      .padding(3)(
        d3
          .hierarchy<TreeNode>(data)
          .sum((d) => d.value || 0)
          .sort((a, b) => (b.value || 0) - (a.value || 0)),
      )

    const svg = d3.select(svgRef.current!)
    svg.selectAll('*').remove()
    svg
      .attr('viewBox', `-${size / 2} -${size / 2} ${size} ${size}`)
      .attr('width', '100%')
      .attr('height', '100%')
      .attr('preserveAspectRatio', 'xMidYMid meet')
      .style('cursor', 'pointer')
      .style('display', 'block')

    // 노드의 최상위 도메인 조상 색
    const colorOf = (d: HNode): string => {
      let n: HNode = d
      while (n.depth > 1 && n.parent) n = n.parent
      return n.depth >= 1 ? domainColor(n.data.name) : '#1e293b'
    }

    const node = svg
      .append('g')
      .selectAll('circle')
      .data(root.descendants().slice(1))
      .join('circle')
      .attr('fill', (d) => {
        const base = colorOf(d)
        if (d.data.type === 'role') return base
        return d3.color(base)!.copy({ opacity: d.depth === 1 ? 0.14 : 0.22 }).toString()
      })
      .attr('stroke', (d) => (d.data.type === 'role' ? 'none' : colorOf(d)))
      .attr('stroke-width', 1)
      .attr('stroke-opacity', 0.5)
      .attr('pointer-events', 'all')
      .on('mouseover', function (this: any, _event: MouseEvent, d: HNode) {
        d3.select(this).attr('stroke', '#fff').attr('stroke-opacity', 0.9)
        const tip = tipRef.current
        if (tip) {
          tip.textContent = tipText(d)
          tip.style.opacity = '1'
        }
      })
      .on('mousemove', function (event: MouseEvent) {
        const tip = tipRef.current
        if (!tip) return
        const [mx, my] = d3.pointer(event, wrap)
        tip.style.left = `${mx}px`
        tip.style.top = `${my}px`
      })
      .on('mouseout', function (this: any) {
        d3.select<SVGCircleElement, HNode>(this)
          .attr('stroke', (d) => (d.data.type === 'role' ? 'none' : colorOf(d)))
          .attr('stroke-opacity', 0.5)
        if (tipRef.current) tipRef.current.style.opacity = '0'
      })
      .on('click', (event: MouseEvent, d) => {
        event.stopPropagation()
        if (d.data.type === 'role') {
          setSelected(d.data)
          if (d.parent && focus !== d.parent) zoom(event, d.parent)
        } else if (focus !== d) {
          setSelected(null)
          zoom(event, d)
        }
      })

    const label = svg
      .append('g')
      .style('font-family', "system-ui, 'Noto Sans KR', sans-serif")
      .attr('pointer-events', 'none')
      .attr('text-anchor', 'middle')
      .selectAll('text')
      .data(root.descendants().slice(1))
      .join('text')
      .style('fill', '#f1f5f9')
      .style('paint-order', 'stroke')
      .style('stroke', '#0f172a')
      .style('stroke-width', '3px')
      .style('stroke-linejoin', 'round')
      .style('font-weight', (d) => (d.data.type === 'domain' ? 800 : d.data.type === 'company' ? 700 : 600))
      .style('fill-opacity', (d) => (d.parent === root ? 1 : 0))
      .style('display', (d) => (d.parent === root ? 'inline' : 'none'))
      .text((d) => labelText(d))

    svg.on('click', (event: MouseEvent) => {
      // 배경 클릭 → 한 단계 줌아웃
      if (focus.parent) zoom(event, focus.parent)
    })

    let focus: HNode = root
    let view: [number, number, number]

    function labelText(d: HNode): string {
      if (d.data.type === 'role') return `${d.data.name} ${d.value}`
      if (d.data.type === 'company') return d.data.name
      if (d.data.type === 'domain') return `${d.data.name} (${d.data.company_count})`
      return d.data.name
    }

    function zoomTo(v: [number, number, number]) {
      const k = size / v[2]
      view = v
      label.attr('transform', (d) => `translate(${(d.x - v[0]) * k},${(d.y - v[1]) * k})`)
      node.attr('transform', (d) => `translate(${(d.x - v[0]) * k},${(d.y - v[1]) * k})`)
      node.attr('r', (d) => d.r * k)
      // 폰트 크기: 원 반경에 비례
      label.style('font-size', (d) => `${Math.max(9, Math.min(d.r * k * 0.32, 22))}px`)
    }

    function zoom(event: MouseEvent | null, d: HNode) {
      focus = d
      setCrumb(focus.ancestors().reverse().map((n) => n.data.name))
      const trans = svg
        .transition()
        .duration(event && (event as any).altKey ? 1400 : 650)
        .tween('zoom', () => {
          const i = d3.interpolateZoom(view, [focus.x, focus.y, focus.r * 2 + 12])
          return (t: number) => zoomTo(i(t) as [number, number, number])
        })

      label
        .filter(function (this: any, d2) {
          return d2.parent === focus || this.style.display === 'inline'
        })
        .transition(trans as any)
        .style('fill-opacity', (d2) => (d2.parent === focus ? 1 : 0))
        .on('start', function (this: any, d2) {
          if (d2.parent === focus) this.style.display = 'inline'
        })
        .on('end', function (this: any, d2) {
          if (d2.parent !== focus) this.style.display = 'none'
        })
    }

    zoomOutRef.current = () => {
      if (focus.parent) zoom(null, focus.parent)
    }

    zoomToNameRef.current = (q: string) => {
      const needle = q.trim().toLowerCase()
      if (!needle) return 0
      const found = root.descendants().filter((d) => d.data.name.toLowerCase().includes(needle))
      // 가장 큰 원부터 — 같은 말이 여러 곳에 있으면 규모가 큰 쪽이 먼저 궁금하다.
      found.sort((a2, b2) => (b2.value ?? 0) - (a2.value ?? 0))
      if (found.length) zoom(null, found[0])
      return found.length
    }

    setCrumb([root.data.name])
    zoomTo([root.x, root.y, root.r * 2 + 12])
  }

  useEffect(() => {
    const t = setTimeout(() => {
      if (!query.trim()) {
        setHitCount(null)
        return
      }
      setHitCount(zoomToNameRef.current?.(query) ?? 0)
    }, 300)
    return () => clearTimeout(t)
  }, [query])

  if (error)
    return (
      <div className="p-8 text-red-400">
        클러스터 로드 실패: {error}
        <br />
        <span className="text-(--color-muted) text-sm">
          생성: <code>python3 jd-viewer/bin/build_mindmap.py</code> (mindmap_tree.json)
        </span>
      </div>
    )

  return (
    <div className="flex flex-1 min-h-0">
      <div className="flex-1 min-w-0 min-h-0 relative overflow-hidden bg-(--color-bg)">
        {/* breadcrumb */}
        <div className="absolute top-2 left-3 z-10 flex flex-wrap items-center gap-1 text-xs">
          {crumb.map((c, i) => (
            <span key={i} className="text-(--color-text)/70">
              {i > 0 && <span className="text-(--color-text)/30 mx-1">›</span>}
              {c}
            </span>
          ))}
        </div>
        <div className="absolute top-2 right-3 z-10 flex items-center gap-2">
          {hitCount !== null && (
            <span className="text-[11px] text-(--color-text)/60">
              {hitCount === 0 ? '걸리는 원이 없다' : `${hitCount}곳 중 가장 큰 원으로`}
            </span>
          )}
          <SearchInput
            value={query}
            onChange={setQuery}
            placeholder="기업·직군 검색"
            className="w-44 sm:w-56"
          />
        </div>
        <div className="absolute bottom-2 right-3 z-10 text-[11px] text-(--color-text)/50">
          원 클릭 = 확대 · 배경 클릭 = 뒤로 · 직군(채워진 원) 클릭 = 상세
        </div>
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center gap-3 text-(--color-text)/60 text-sm">
            <span className="jd-spinner" aria-hidden />
            클러스터 불러오는 중…
          </div>
        )}
        <div ref={wrapRef} className="absolute inset-0">
          <svg ref={svgRef} />
        </div>
        {/* 호버 툴팁 — 구슬 위에 올리면 회사 이름 표시 */}
        <div
          ref={tipRef}
          className="pointer-events-none absolute z-20 px-2 py-1 rounded text-xs font-medium bg-(--color-panel) text-(--color-text) border border-(--color-border) shadow-lg whitespace-nowrap opacity-0 transition-opacity"
          style={{ transform: 'translate(-50%, calc(-100% - 10px))' }}
        />
      </div>

      {/* 상세 패널 */}
      {selected && selected.type === 'role' && (
        <aside className="w-80 shrink-0 border-l border-(--color-border) bg-(--color-panel) overflow-auto p-4 jd-slide-in">
          <button
            onClick={() => setSelected(null)}
            className="text-xs text-(--color-muted) hover:text-(--color-text) float-right"
          >
            ✕ 닫기
          </button>
          <div className="text-[11px] text-(--color-muted)">{selected.domain}</div>
          <h2 className="text-lg font-bold text-(--color-text) mt-0.5">{selected.company}</h2>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-sm font-semibold text-(--color-accent)">{selected.name}</span>
            <span className="text-[11px] text-(--color-muted)">· {selected.value}건 공고</span>
            {selected.size && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-(--hover) text-(--color-text)/70">
                {selected.size}
              </span>
            )}
          </div>

          {selected.tech && selected.tech.length > 0 && (
            <div className="mt-3">
              <div className="text-[11px] uppercase tracking-wider text-(--color-muted) mb-1.5">
                관측 스택
              </div>
              <div className="flex flex-wrap gap-1.5">
                {selected.tech.map((t) => (
                  <span
                    key={t}
                    className="text-[12px] px-2 py-0.5 rounded-md bg-(--color-accent)/12 text-(--color-accent) border border-(--color-accent)/30"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          {selected.postings && selected.postings.length > 0 && (
            <div className="mt-4">
              <div className="text-[11px] uppercase tracking-wider text-(--color-muted) mb-1.5">
                채용공고
              </div>
              <ul className="space-y-1.5">
                {selected.postings.map((p, i) => (
                  <li key={i}>
                    <a
                      href={p.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm text-(--color-accent) hover:underline"
                    >
                      {p.title || '(제목없음)'} ↗
                    </a>
                    <span className="text-[11px] text-(--color-muted) ml-2">{p.site}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      )}
    </div>
  )
}
