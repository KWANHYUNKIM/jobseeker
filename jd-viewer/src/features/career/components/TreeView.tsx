import { useEffect, useMemo, useState } from 'react'
import { docFetch } from '../../../api/client'
import { CompanyMark, ErrorState, Loader } from '../../../components/ui'
import { toDomains, type Company, type Domain, type TreeNode } from './DomainMap'

// 줄 높이·자리(px) — 캐치형 18 트리 보드의 2배율 값
const ROW_D = 61 // 도메인 줄 간격
const ROW_C = 72 // 회사 줄 간격
const ROW_R = 44 // 직군 줄 간격
const X_ROOT = 40
const W_ROOT = 200
const X_DOM = 450
const W_DOM = 270
const X_CO = 860
const W_CO = 300
const X_ROLE = 1190
const W_ROLE = 180
const PAD_T = 20
const CAP = 15 // 도메인 하나에 처음 보이는 회사 수 — 나머지는 '더 보기'

type Fold = 'domains' | 'companies' | 'all'

/**
 * 커리어 마인드맵 · 트리(캐치형 18) — 채용 기업 맵 → 도메인 → 회사 → 직군을 왼쪽에서 오른쪽으로 편다.
 * 도메인 단추의 +/− 로 그 도메인의 회사를 펴고 접고, 회사를 누르면 그 회사가 뽑는 직군이 네 번째 칸에 열린다.
 * 회사 검색은 걸린 회사의 도메인만 펴서 보여 준다. 아래 '데이터 개요' 는 도메인별 회사 수.
 */
export function TreeView({ query }: { query: string }) {
  const [root, setRoot] = useState<TreeNode | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState<Set<string>>(new Set())
  const [inited, setInited] = useState(false)
  const [picked, setPicked] = useState<string | null>(null)
  const [more, setMore] = useState<Set<string>>(new Set())

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
  // 처음엔 회사가 가장 많은 도메인 하나를 펴 둔다
  if (!inited && domains.length) {
    setInited(true)
    setOpen(new Set([domains[0].name]))
  }

  // 회사 검색 — 걸린 회사의 도메인만 편다(지우면 손으로 편 상태로 돌아간다)
  const q = query.trim().toLowerCase()
  const hits = useMemo(
    () => (q ? new Set(domains.filter((d) => d.companies.some((c) => c.name.toLowerCase().includes(q))).map((d) => d.name)) : null),
    [domains, q],
  )
  const isOpen = (d: Domain) => (hits ? hits.has(d.name) : open.has(d.name))

  const fold = (f: Fold) => {
    setPicked(null)
    setMore(new Set())
    setOpen(f === 'domains' ? new Set() : new Set(domains.map((d) => d.name)))
  }
  const toggle = (name: string) =>
    setOpen((s) => {
      const n = new Set(s)
      if (n.has(name)) n.delete(name)
      else n.add(name)
      return n
    })

  if (error) return <ErrorState title="마인드맵 데이터를 불러오지 못했습니다" detail={error} />
  if (!root) return <Loader label="채용 기업 맵 불러오는 중…" />

  // 펼친 도메인의 회사(검색 중이면 걸린 회사만)를 위에서부터 늘어놓는다
  // 도메인마다 CAP 곳까지, 그 뒤는 '+N곳 더 보기' 한 줄(c: null)
  const cos: { d: Domain; c: Company | null; rest?: number }[] = []
  for (const d of domains) {
    if (!isOpen(d)) continue
    const list = d.companies.filter((c) => !q || c.name.toLowerCase().includes(q))
    const cap = more.has(d.name) || q ? list.length : CAP
    for (const c of list.slice(0, cap)) cos.push({ d, c })
    if (list.length > cap) cos.push({ d, c: null, rest: list.length - cap })
  }
  const pickedCo = cos.find((x) => x.c?.name === picked) ?? null
  const roles = pickedCo?.c?.roles ?? []

  const domH = domains.length * ROW_D
  const coH = cos.length * ROW_C
  const roleTop = pickedCo ? cos.indexOf(pickedCo) * ROW_C : 0
  const height = Math.max(domH, coH, roleTop + roles.length * ROW_R) + PAD_T * 2
  const rootY = PAD_T + domH / 2
  const domY = (i: number) => PAD_T + i * ROW_D + ROW_D / 2
  const coY = (i: number) => PAD_T + (coH < domH ? (domH - coH) / 2 : 0) + i * ROW_C + ROW_C / 2
  const roleY = (i: number) => PAD_T + (coH < domH ? (domH - coH) / 2 : 0) + roleTop + i * ROW_R + ROW_R / 2
  const curve = (x1: number, y1: number, x2: number, y2: number) => {
    const mx = (x1 + x2) / 2
    return `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`
  }
  const total = domains.reduce((a, d) => a + d.companies.length, 0)

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <FoldBtn on={open.size === domains.length && !hits} onClick={() => fold('all')}>
          모두 펼치기
        </FoldBtn>
        <FoldBtn on={false} onClick={() => fold('companies')}>
          기업까지
        </FoldBtn>
        <FoldBtn on={open.size === 0 && !hits} onClick={() => fold('domains')}>
          도메인만
        </FoldBtn>
        <FoldBtn
          on={false}
          onClick={() => {
            setPicked(null)
            setOpen(new Set([domains[0].name]))
          }}
        >
          화면 맞춤
        </FoldBtn>
        <span className="ml-auto text-xs text-[#999]">노드 클릭 = 펼침/접힘 · 회사 클릭 = 직군 · 검색 = 걸린 가지만</span>
      </div>

      <div className="mt-4 rounded-[30px] border border-[#e2e8ec] bg-white overflow-x-auto">
        <div className="relative mx-auto" style={{ width: X_ROLE + W_ROLE + 40, height }}>
          <svg className="absolute inset-0 pointer-events-none" width={X_ROLE + W_ROLE + 40} height={height} aria-hidden>
            {domains.map((d, i) => (
              <path key={d.name} d={curve(X_ROOT + W_ROOT, rootY, X_DOM, domY(i))} fill="none" stroke={d.color} strokeWidth={1.6} opacity={0.75} />
            ))}
            {cos.map(({ d, c }, j) => (
              <path key={d.name + (c?.name ?? '+')} d={curve(X_DOM + W_DOM, domY(domains.indexOf(d)), X_CO, coY(j))} fill="none" stroke={d.color} strokeWidth={1.4} opacity={0.6} />
            ))}
            {pickedCo &&
              roles.map((r, k) => (
                <path key={r.name} d={curve(X_CO + W_CO, coY(cos.indexOf(pickedCo)), X_ROLE, roleY(k))} fill="none" stroke={pickedCo.d.color} strokeWidth={1.4} opacity={0.6} />
              ))}
          </svg>

          {/* 뿌리 */}
          <div className="absolute rounded-2xl bg-[#272727] px-5 py-3 text-white" style={{ left: X_ROOT, top: rootY - 33, width: W_ROOT }}>
            <div className="text-lg font-bold leading-[26px]">채용 기업 맵</div>
            <div className="text-xs text-[#ccc] tabular-nums">
              {root.company_count ?? total}곳 · 공고 {root.total_jobs?.toLocaleString() ?? ''}건
            </div>
          </div>

          {/* 도메인 */}
          {domains.map((d, i) => {
            const on = isOpen(d)
            return (
              <button
                key={d.name}
                type="button"
                onClick={() => toggle(d.name)}
                aria-expanded={on}
                className="absolute flex items-center gap-2 h-10 rounded-[20px] border-2 bg-white px-4 text-left hover:shadow-[0_2px_8px_rgba(0,0,0,0.08)]"
                style={{ left: X_DOM, top: domY(i) - 20, width: W_DOM, borderColor: on ? d.color : `${d.color}88` }}
              >
                <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: d.color }} />
                <span className="min-w-0 truncate text-sm font-bold text-[#272727]">{d.name}</span>
                <span className="shrink-0 text-xs text-[#999]">{d.companies.length}개사</span>
                <span className="ml-auto text-base leading-none text-[#999]">{on ? '−' : '+'}</span>
              </button>
            )
          })}

          {/* 회사 */}
          {cos.map(({ d, c, rest }, j) =>
            !c ? (
              <button
                key={d.name + '+more'}
                type="button"
                onClick={() => setMore((s) => new Set(s).add(d.name))}
                className="absolute h-9 rounded-[18px] border border-dashed border-[#c4c4c4] bg-white px-4 text-left text-[13px] text-[#777] hover:border-[#272727] hover:text-[#272727]"
                style={{ left: X_CO, top: coY(j) - 18, width: W_CO }}
              >
                {d.name} +{rest}곳 더 보기
              </button>
            ) : (
            <button
              key={c.name + j}
              type="button"
              onClick={() => setPicked(picked === c.name ? null : c.name)}
              aria-pressed={picked === c.name}
              className={'absolute flex items-center gap-2.5 h-9 rounded-[18px] border bg-white px-3 text-left hover:border-[#999] ' + (picked === c.name ? 'border-[#272727]' : 'border-[#e2e8ec]')}
              style={{ left: X_CO, top: coY(j) - 18, width: W_CO }}
            >
              <span className="grid place-items-center w-6 h-6 rounded-md overflow-hidden shrink-0">
                <CompanyMark name={c.name} size={24} />
              </span>
              <span className="min-w-0 truncate text-sm font-medium text-[#272727]">{c.name}</span>
              <span className="ml-auto shrink-0 text-xs text-[#999] tabular-nums">{c.jobs}건</span>
            </button>
            ),
          )}

          {/* 직군 — 고른 회사 */}
          {pickedCo &&
            roles.map((r, k) => (
              <div
                key={r.name}
                className="absolute flex items-center h-8 rounded-2xl bg-[#f7f9fa] px-3 text-[13px] text-[#474747]"
                style={{ left: X_ROLE, top: roleY(k) - 16, width: W_ROLE }}
              >
                <span className="truncate">{r.name}</span>
                <span className="ml-auto text-xs text-[#999] tabular-nums">{r.n}건</span>
              </div>
            ))}
        </div>
      </div>

      {/* 데이터 개요 */}
      <section className="mt-6 rounded-[22px] bg-[#f7f9fa] px-6 py-5">
        <h3 className="text-[17px] font-bold text-[#272727]">📊 데이터 개요</h3>
        <ul className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-x-8 gap-y-2">
          {domains.map((d) => (
            <li key={d.name} className="flex items-center gap-2 text-sm text-[#474747]">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: d.color }} />
              <span className="truncate">{d.name}</span>
              <span className="ml-auto font-bold text-[#272727] tabular-nums">{d.companies.length}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

function FoldBtn({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        'h-8 px-4 rounded-2xl border text-[13px] font-medium ' +
        (on ? 'bg-(--color-accent) border-(--color-accent) text-white' : 'bg-white border-[#d8d8d8] text-[#272727] hover:border-[#272727]')
      }
    >
      {children}
    </button>
  )
}
