import { useEffect, useRef, useState } from 'react'
import type { Count, Filters, Overview } from '../api'

// 거르기 한 줄 — 축 다섯 개(연도·회사 유형·경력·종류·직무)를 드롭다운 알약으로, 오른쪽에 검색.
// 예전에는 칩 54개가 다섯 줄로 탭 위 250px 를 차지했다. 건수는 펼친 목록에 그대로 있다.

type Axis = { key: 'year' | 'type' | 'level' | 'kind' | 'role'; label: string; items: Count[] }

const Chevron = () => (
  <svg aria-hidden width="10" height="6" viewBox="0 0 10 6" fill="none" stroke="currentColor" strokeWidth="1.6">
    <path d="M1 1l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)
const Cross = () => (
  <svg aria-hidden width="9" height="9" viewBox="0 0 9 9" fill="none" stroke="currentColor" strokeWidth="1.6">
    <path d="M1 1l7 7M8 1L1 8" strokeLinecap="round" />
  </svg>
)
const Check = () => (
  <svg aria-hidden width="12" height="9" viewBox="0 0 12 9" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M1 4.5l3.5 3.5L11 1" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)
export const SearchIcon = () => (
  <svg aria-hidden width="16" height="16" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="8" cy="8" r="6" />
    <path d="M12.5 12.5 16.5 16.5" strokeLinecap="round" />
  </svg>
)

const PILL = 'inline-flex h-9 shrink-0 items-center gap-2 rounded-full border px-4 text-sm font-medium whitespace-nowrap'

function AxisPill({ axis, value, onPick, disabled }: { axis: Axis; value?: string; onPick: (v: string | null) => void; disabled?: boolean }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const off = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false)
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', off)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('mousedown', off)
      document.removeEventListener('keydown', esc)
    }
  }, [open])
  const pick = (v: string | null) => {
    onPick(v)
    setOpen(false)
  }
  return (
    <div ref={ref} className="relative">
      {value ? (
        <span className={PILL + ' border-[#272727] text-[#272727] font-bold pr-3'}>
          <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-haspopup="listbox">
            {axis.label} · {value}
          </button>
          <button type="button" aria-label={`${axis.label} 거르기 지우기`} onClick={() => pick(null)} className="p-1">
            <Cross />
          </button>
        </span>
      ) : (
        <button
          type="button"
          disabled={disabled}
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-haspopup="listbox"
          className={PILL + ' border-[#d8d8d8] text-[#272727] hover:border-[#272727] disabled:text-[#c4c4c4] disabled:hover:border-[#d8d8d8]'}
        >
          {axis.label} 전체 <Chevron />
        </button>
      )}
      {open && (
        <ul
          role="listbox"
          className="absolute left-0 top-[44px] z-20 max-h-[420px] min-w-[240px] overflow-auto rounded-xl border border-[#d8d8d8] bg-white py-2"
        >
          {[['전체', null] as const, ...axis.items.map(([v, n]) => [v, n] as const)].map(([v, n]) => {
            const on = v === '전체' ? !value : value === String(v)
            return (
              <li key={String(v)}>
                <button
                  type="button"
                  role="option"
                  aria-selected={on}
                  onClick={() => pick(v === '전체' ? null : String(v))}
                  className={'flex w-full items-center gap-2 px-4 h-8 text-sm text-[#272727] hover:bg-[#f7f9fa] ' + (on ? 'font-bold' : '')}
                >
                  <span className="w-3 shrink-0">{on && <Check />}</span>
                  <span className="flex-1 text-left whitespace-nowrap">{v}</span>
                  {n !== null && <span className={'tabular-nums ' + (on ? '' : 'text-[#666]')}>{n.toLocaleString()}</span>}
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

/** 축에 없는 거르기(회사·출발지·검색어)는 고른 알약으로만 보인다. */
function Picked({ label, onClear }: { label: string; onClear: () => void }) {
  return (
    <span className={PILL + ' border-[#272727] text-[#272727] font-bold pr-3'}>
      {label}
      <button type="button" aria-label={`${label} 지우기`} onClick={onClear} className="p-1">
        <Cross />
      </button>
    </span>
  )
}

export function FilterBar({
  o,
  f,
  set,
  clearAll,
  disabled,
}: {
  o: Overview | null
  f: Filters
  set: (k: string, v: string | null) => void
  clearAll: () => void
  disabled?: boolean
}) {
  const [q, setQ] = useState(f.q ?? '')
  const [prevQ, setPrevQ] = useState(f.q)
  if (prevQ !== f.q) {
    setPrevQ(f.q)
    setQ(f.q ?? '')
  }
  const fc = o?.facets
  const axes: Axis[] = [
    { key: 'year', label: '연도', items: (fc?.years ?? []).map(([y, n]) => [String(y), n] as Count) },
    { key: 'type', label: '회사 유형', items: fc?.types ?? [] },
    { key: 'level', label: '경력', items: fc?.levels ?? [] },
    { key: 'kind', label: '종류', items: fc?.kinds ?? [] },
    { key: 'role', label: '직무', items: fc?.roles ?? [] },
  ]
  const company = f.company && o && (o.companies.find((c) => c.key === f.company)?.name ?? o.programs.find((p) => p.key === f.company)?.name ?? f.company)
  const any = (Object.keys(f) as (keyof Filters)[]).some((k) => f[k])
  return (
    <div className="flex items-center gap-2">
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
        {axes.map((a) => (
          <AxisPill key={a.key} axis={a} value={f[a.key]} onPick={(v) => set(a.key, v)} disabled={disabled} />
        ))}
        {company && <Picked label={`회사 · ${company}`} onClear={() => set('company', null)} />}
        {f.origin && <Picked label={`출발지 · ${f.origin}`} onClear={() => set('origin', null)} />}
        {f.q && <Picked label={`“${f.q}”`} onClear={() => set('q', null)} />}
        {any && (
          <button type="button" onClick={clearAll} className="ml-2 text-sm text-[#272727] underline underline-offset-4">
            모두 지우기
          </button>
        )}
      </div>
      <form
        role="search"
        onSubmit={(e) => {
          e.preventDefault()
          set('q', q.trim() || null)
        }}
        className="flex h-9 w-[280px] shrink-0 items-center rounded-full border border-[#d8d8d8] pl-5 pr-3 focus-within:border-[#272727]"
      >
        <input
          value={q}
          disabled={disabled}
          onChange={(e) => setQ(e.target.value)}
          placeholder="제목·회사·기술 검색"
          aria-label="제목·회사·기술 검색"
          className="min-w-0 flex-1 bg-transparent text-sm text-[#272727] placeholder:text-[#666] outline-none"
        />
        <button type="submit" aria-label="검색" disabled={disabled} className="p-1 text-[#272727] disabled:text-[#c4c4c4]">
          <SearchIcon />
        </button>
      </form>
    </div>
  )
}
