import type { ReactNode } from 'react'
import type { Count } from '../api'
import { pctText } from '../utils/format'

// 취업후기 화면 부품 — 캐치형 시안(J03)의 문법 하나로 모든 탭을 그린다.
// 상자(카드)·막대·회색 면 없이 1px #EEEEEE 선과 글자 위계로 나눈다. 글자색은 #272727(본문)·#666(보조) 둘.

/** 이름 · 건수 · 비율 목록 — 비율이 없으면 표본이 3건 미만이라 건수만 낸 것이다. */
export function CountList({
  items,
  empty = '없음',
  onPick,
  picked,
  limit = 10,
}: {
  items: Count[] | undefined
  empty?: string
  onPick?: (label: string) => void
  picked?: string
  limit?: number
}) {
  const xs = (items ?? []).slice(0, limit)
  if (!xs.length) return <p className="text-sm text-[#666]">{empty}</p>
  return (
    <ul className="border-t border-[#EEEEEE]">
      {xs.map(([label, n, pct]) => {
        const on = picked === label
        const body = (
          <>
            <span className={'min-w-0 flex-1 break-keep text-left ' + (on ? 'font-bold' : '')}>{label}</span>
            <span className="w-14 shrink-0 text-right tabular-nums">{n.toLocaleString()}</span>
            <span className="w-12 shrink-0 text-right tabular-nums text-[#666]">{pctText(n, pct) ?? ''}</span>
          </>
        )
        const cls = 'flex w-full items-center gap-3 border-b border-[#EEEEEE] py-2.5 text-sm text-[#272727]'
        return (
          <li key={label}>
            {onPick ? (
              <button type="button" onClick={() => onPick(label)} aria-pressed={on} className={cls + ' hover:bg-[#FAFAFA]'}>
                {body}
              </button>
            ) : (
              <div className={cls}>{body}</div>
            )}
          </li>
        )
      })}
    </ul>
  )
}

/** 모듈 — 제목 16/700 + 아래 한 줄 설명 14 #666. 상자 없이 바닥에 둔다. */
export function Section({ title, note, children, className = '' }: { title: ReactNode; note?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={className}>
      <h3 className="text-[16px] font-bold leading-6 text-[#272727]">{title}</h3>
      {note && <p className="mt-0.5 text-sm leading-5 text-[#666]">{note}</p>}
      <div className="mt-4">{children}</div>
    </section>
  )
}

/** KPI 줄 — 위 1px 선, 칸 사이 세로선, 숫자 32/500 + 단위 16. */
export function KpiRow({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-2 border-t border-[#EEEEEE] lg:grid-cols-4">{children}</div>
}

export function Kpi({ label, value, unit, sub }: { label: string; value: ReactNode; unit?: string; sub?: ReactNode }) {
  return (
    <div className="px-0 pt-6 lg:[&:not(:first-child)]:border-l lg:[&:not(:first-child)]:border-[#EEEEEE] lg:[&:not(:first-child)]:pl-6">
      <div className="text-sm text-[#666]">{label}</div>
      <div className="mt-1 flex items-baseline gap-1.5">
        <span className="text-[32px] font-medium leading-10 tabular-nums text-[#272727]">{value}</span>
        {unit && <span className="text-[16px] text-[#666]">{unit}</span>}
      </div>
      {sub && <div className="mt-1 text-sm text-[#666]">{sub}</div>}
    </div>
  )
}

/** 고르는 알약 — 기본 1px #E2E2E2 · 400, 고름 1px #272727 · 700. */
export function Chip({ on, children, onClick }: { on?: boolean; children: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      className={
        'h-9 shrink-0 rounded-full border px-4 text-sm text-[#272727] ' +
        (on ? 'border-[#272727] font-bold' : 'border-[#E2E2E2] hover:border-[#272727]')
      }
    >
      {children}
    </button>
  )
}

/** 경로 한 줄 — 단계를 ' → ' 로 잇는다(칩 없음). */
export function Steps({ steps }: { steps: string[] }) {
  if (!steps.length) return null
  return <p className="break-keep text-sm leading-5 text-[#272727]">{steps.join(' → ')}</p>
}

/** 표 — 머리 14/500 #666, 행선 1px #EEEEEE, 단어 중간에서 끊지 않는다. */
export function Table({ head, children, minWidth = 980 }: { head: ReactNode[]; children: ReactNode; minWidth?: number }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full break-keep text-sm text-[#272727]" style={{ minWidth }}>
        <thead className="text-left">
          <tr className="border-b border-[#EEEEEE]">
            {head.map((h, i) => (
              <th key={i} className="whitespace-nowrap py-2.5 pr-4 font-medium text-[#666]">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}

/** 표 칸 목록 — 항목 하나는 끊지 않고 항목 사이(', ' · ' · ')에서만 줄을 바꾼다. */
export function Items({ xs, sep = ', ', empty = '—' }: { xs: string[]; sep?: string; empty?: string }) {
  if (!xs.length) return <>{empty}</>
  return (
    <>
      {xs.map((x, i) => (
        <span key={i}>
          {i > 0 && sep}
          <span className="whitespace-nowrap">{x}</span>
        </span>
      ))}
    </>
  )
}
