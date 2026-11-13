import { useEffect, useMemo, useState } from 'react'
import * as d3 from 'd3'
import { docFetch } from '../../../api/client'
import { CompanyMark, ErrorState, Loader } from '../../../components/ui'

// mindmap_tree.json — 루트 → 도메인 → 회사 → 직군(value = 공고 수). bin/build_mindmap_tree.py 가 만든다.
interface TreeNode {
  name: string
  type: 'root' | 'domain' | 'company' | 'role'
  value?: number
  size?: string
  company_count?: number
  postings_total?: number
  total_jobs?: number
  domain_count?: number
  children?: TreeNode[]
}

export interface MindmapSummary {
  companies: number
  domains: number
  jobs: number
}

// 도메인 색 — 회사 수가 많은 순서대로. '기타/미상' 은 늘 회색.
const COLORS = ['#f45757', '#4f7cf0', '#2bb673', '#f2a93b', '#8b5cf6', '#0ea5e9', '#e05fb4', '#64748b', '#14b8a6', '#f97316', '#6366f1', '#84cc16', '#94a3b8', '#ef4444', '#a855f7', '#10b981']
const ETC = '기타/미상'

interface Company {
  name: string
  size: string
  jobs: number
  roles: { name: string; n: number }[]
}
interface Domain {
  name: string
  color: string
  companies: Company[]
  jobs: number
  roles: { name: string; n: number }[]
}

function toDomains(root: TreeNode): Domain[] {
  const ds = (root.children ?? []).map((d) => {
    const companies: Company[] = (d.children ?? [])
      .map((c) => ({
        name: c.name,
        size: c.size ?? '',
        jobs: c.postings_total ?? (c.children ?? []).reduce((a, r) => a + (r.value ?? 0), 0),
        roles: (c.children ?? []).map((r) => ({ name: r.name, n: r.value ?? 0 })).sort((a, b) => b.n - a.n),
      }))
      .sort((a, b) => b.jobs - a.jobs)
    const byRole = new Map<string, number>()
    for (const c of companies) for (const r of c.roles) byRole.set(r.name, (byRole.get(r.name) ?? 0) + r.n)
    return {
      name: d.name,
      color: '',
      companies,
      jobs: companies.reduce((a, c) => a + c.jobs, 0),
      roles: [...byRole].map(([name, n]) => ({ name, n })).sort((a, b) => b.n - a.n),
    }
  })
  // 회사 수 많은 순(같으면 원래 순서). 색은 그 순서로 준다.
  const sorted = ds.map((d, i) => ({ d, i })).sort((a, b) => b.d.companies.length - a.d.companies.length || a.i - b.i).map((x) => x.d)
  sorted.forEach((d, i) => (d.color = d.name === ETC ? '#94a3b8' : COLORS[i % COLORS.length]))
  return sorted
}

/** 원 반지름 — 회사 수의 제곱근에 비례하되 1곳짜리도 글자가 들어갈 만큼은 크게. */
const radiusOf = (n: number) => 30 + 13 * Math.sqrt(n)

/**
 * 채용 기업 맵(캐치형 04 커리어 마인드맵) — 사업 도메인 하나가 원 하나(크기 = 회사 수).
 * 원을 누르면 오른쪽에 그 도메인의 숫자·많이 뽑는 회사·직군 막대가 뜬다.
 * 회사 검색은 그 회사가 속한 도메인을 고른다.
 */
export function DomainMap({ query, onSummary }: { query: string; onSummary?: (s: MindmapSummary) => void }) {
  const [root, setRoot] = useState<TreeNode | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [picked, setPicked] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    docFetch('/mindmap_tree.json')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status} - mindmap_tree.json`)
        return r.json() as Promise<TreeNode>
      })
      .then((d) => !cancelled && setRoot(d))
      .catch((e) => !cancelled && setError(String(e)))
    return () => {
      cancelled = true
    }
  }, [])

  const domains = useMemo(() => (root ? toDomains(root) : []), [root])
  useEffect(() => {
    if (root && onSummary)
      onSummary({ companies: root.company_count ?? 0, domains: root.domain_count ?? domains.length, jobs: root.total_jobs ?? 0 })
  }, [root, domains.length, onSummary])

  // 처음 고른 도메인 — 공고가 가장 많은 회사가 속한 곳.
  const fallback = useMemo(() => {
    let best: Domain | null = null
    for (const d of domains) if (!best || (d.companies[0]?.jobs ?? 0) > (best.companies[0]?.jobs ?? 0)) best = d
    return best?.name ?? null
  }, [domains])

  // 검색어가 있으면 그 회사의 도메인을 고른다.
  const hit = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return null
    return domains.find((d) => d.companies.some((c) => c.name.toLowerCase().includes(q)))?.name ?? null
  }, [domains, query])

  const sel = domains.find((d) => d.name === (hit ?? picked ?? fallback)) ?? null

  const layout = useMemo(() => {
    // 원 사이를 조금 띄워 놓는다(GAP) — 붙어 있으면 테두리가 겹쳐 한 덩어리로 읽힌다.
    const GAP = 5
    const packed = domains.map((d) => ({ d, r: radiusOf(d.companies.length) + GAP, x: 0, y: 0 }))
    d3.packSiblings(packed)
    const enc = d3.packEnclose(packed)
    const circles = packed.map((c) => ({ ...c, r: c.r - GAP }))
    return { circles, enc }
  }, [domains])

  if (error) return <ErrorState title="마인드맵 데이터를 불러오지 못했습니다" detail={error} />
  if (!root) return <Loader label="채용 기업 맵 불러오는 중…" />

  const { circles, enc } = layout
  const pad = 12
  const vb = `${enc.x - enc.r - pad} ${enc.y - enc.r - pad} ${(enc.r + pad) * 2} ${(enc.r + pad) * 2}`
  const q = query.trim().toLowerCase()

  return (
    <div className="flex flex-col lg:flex-row gap-6 items-start">
      <section className="w-full lg:w-[872px] shrink-0 rounded-[30px] border border-[#e2e8ec] bg-white px-[35px] pt-[25px] pb-[36px]">
        <h2 className="flex flex-wrap items-baseline gap-x-[15px]">
          <span className="text-[19px] font-bold leading-[27px] tracking-[-0.16px] text-[#272727]">채용 기업 맵</span>
          <span className="text-[13px] tracking-[-0.16px] text-[#999]">원 크기 = 회사 수 · 원을 누르면 그 도메인의 회사와 직군이 열려요</span>
        </h2>
        <svg viewBox={vb} className="mt-6 mx-auto block w-full max-w-[680px] aspect-square" role="img" aria-label="도메인별 회사 수 원 그림">
          {circles.map(({ d, r, x, y }) => {
            const on = d === sel
            const big = r >= 80
            const fs = big ? 18 : r >= 60 ? 15 : 13
            const lines = wrapLabel(d.name, Math.floor((r * 2.2) / fs))
            const names = d.companies.slice(0, 3).map((c) => c.name).join(' · ')
            const total = lines.length * fs * 1.4 + 18 + (big ? 22 : 0)
            let ty = y - total / 2 + fs
            return (
              <g key={d.name} onClick={() => setPicked(d.name)} className="cursor-pointer" role="button" aria-label={`${d.name} ${d.companies.length}곳`}>
                {on && <circle cx={x} cy={y} r={r + 6.5} fill="none" stroke="#272727" strokeWidth={3} />}
                <circle cx={x} cy={y} r={r} fill={d.color} fillOpacity={0.12} stroke={d.color} strokeWidth={on ? 3 : 2} />
                {lines.map((ln, i) => (
                  <text key={i} x={x} y={ty + i * fs * 1.25} textAnchor="middle" fontSize={fs} fontWeight={700} fill={d.color} letterSpacing={-0.3}>
                    {ln}
                  </text>
                ))}
                {(() => {
                  ty += (lines.length - 1) * fs * 1.25 + 22
                  return (
                    <>
                      <text x={x} y={ty} textAnchor="middle" fontSize={12} fill="#474747">
                        {big ? `${d.companies.length}곳 · ${d.jobs}건` : `${d.companies.length}곳`}
                      </text>
                      {big && (
                        <text x={x} y={ty + 23} textAnchor="middle" fontSize={12} fill="#666">
                          {names.length > 18 ? names.slice(0, 17) + '…' : names}
                        </text>
                      )}
                    </>
                  )
                })()}
                {q && d.companies.some((c) => c.name.toLowerCase().includes(q)) && (
                  <circle cx={x} cy={y} r={r + 2} fill="none" stroke="#272727" strokeDasharray="4 4" strokeWidth={1.5} />
                )}
              </g>
            )
          })}
        </svg>
        <ul className="mt-6 flex flex-wrap gap-x-[30px] gap-y-[6px]">
          {domains.map((d) => (
            <li key={d.name}>
              <button type="button" onClick={() => setPicked(d.name)} className="flex items-center gap-[5px] text-[13px] leading-[19px] tracking-[-0.16px] text-[#474747] hover:text-[#272727]">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: d.color }} />
                {d.name} {d.companies.length}
              </button>
            </li>
          ))}
        </ul>
      </section>

      {sel && <DomainPanel d={sel} />}
    </div>
  )
}

function DomainPanel({ d }: { d: Domain }) {
  const max = Math.max(1, ...d.roles.map((r) => r.n))
  return (
    <aside className="w-full lg:w-[360px] shrink-0">
      <div className="rounded-3xl border-2 px-[24px] pt-[22px] pb-[22px]" style={{ borderColor: d.color }}>
        <div className="text-[13px] tracking-[-0.16px] text-[#777]">선택한 도메인</div>
        <div className="mt-1 pb-[11px] border-b border-[#eee] text-2xl font-bold leading-9 tracking-[-0.16px]" style={{ color: d.color }}>
          {d.name}
        </div>
        <div className="mt-[14px] grid grid-cols-2 gap-[10px]">
          {[
            [d.companies.length, '곳'],
            [d.jobs, '건'],
          ].map(([n, u]) => (
            <div key={u} className="h-14 rounded-[14px] bg-[#f7f9fa] px-[14px] flex items-center gap-0.5">
              <span className="text-[22px] font-bold text-[#272727] tabular-nums">{n}</span>
              <span className="mt-1.5 text-sm text-[#474747]">{u}</span>
            </div>
          ))}
        </div>
      </div>

      <h3 className="mt-6 text-[17px] font-bold leading-[25px] tracking-[-0.16px] text-[#272727]">많이 뽑는 회사</h3>
      <ul className="mt-2">
        {d.companies.slice(0, 8).map((c) => (
          <li key={c.name} className="flex items-center gap-3 h-[63px] border-b border-[#eef1f3] px-1">
            <span className="grid place-items-center w-9 h-9 rounded-[9px] overflow-hidden shrink-0">
              <CompanyMark name={c.name} size={36} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[15px] font-bold leading-[21px] tracking-[-0.16px] text-[#272727] truncate">{c.name}</span>
              <span className="block text-xs leading-[18px] text-[#888] truncate">
                {[c.size, c.roles.slice(0, 2).map((r) => r.name).join(', ')].filter(Boolean).join(' · ')}
              </span>
            </span>
            <span className="shrink-0 text-[15px] font-bold text-[#272727] tabular-nums">{c.jobs}건</span>
          </li>
        ))}
      </ul>

      <h3 className="mt-6 text-[17px] font-bold leading-[25px] tracking-[-0.16px] text-[#272727]">이 도메인의 직군</h3>
      <ul className="mt-2 flex flex-col gap-[9px]">
        {d.roles.slice(0, 6).map((r) => (
          <li key={r.name} className="flex items-center">
            <span className="w-[106px] shrink-0 text-sm leading-[21px] text-[#474747] truncate">{r.name}</span>
            <span className="flex-1 h-3 rounded-md bg-[#f1f3f5] overflow-hidden">
              <span className="block h-full rounded-md" style={{ width: `${(r.n / max) * 100}%`, background: d.color }} />
            </span>
            <span className="w-[34px] shrink-0 text-right text-sm font-bold text-[#272727] tabular-nums">{r.n}</span>
          </li>
        ))}
      </ul>
    </aside>
  )
}

/** 원 안 이름 줄바꿈 — 한 줄에 `per` 글자까지. 'B2B SaaS/엔터프라이즈' → 'B2B SaaS/엔터프', '라이즈'. */
function wrapLabel(s: string, per: number): string[] {
  const n = Math.max(4, per)
  if (s.length <= n) return [s]
  const out: string[] = []
  for (let i = 0; i < s.length; i += n) out.push(s.slice(i, i + n))
  return out.slice(0, 3)
}
