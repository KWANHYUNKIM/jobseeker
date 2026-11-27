import type { ReactNode } from 'react'
import type { Count } from '../api'

// 취업후기 목록 화면의 부품 — Penpot「JD Viewer」35 취업후기(J03 캐치형 1920)의 값.
// 글자 두 색(본문 #272727 · 보조 #666), 콘텐츠 선 한 색 #eee, 컨트롤 테두리 #d8d8d8.
// 카드·회색 띠·막대를 쓰지 않는다 — 칸은 선으로 나누고, 숫자는 글자로 읽는다.
export const LINE = 'border-[#eeeeee]'

/** 모듈 — 16/700 제목 + 14 #666 노트. 상자 없이 선과 간격으로 묶는다. */
export function Section({ title, note, children, className = '' }: { title: ReactNode; note?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={className}>
      <h3 className="text-base font-bold leading-6 text-[#272727]">{title}</h3>
      {note && <p className="mt-0.5 text-sm leading-5 text-[#666]">{note}</p>}
      <div className="mt-4">{children}</div>
    </section>
  )
}

/** 이름 · 건수 · 비율 목록. 비율이 없으면 표본이 3건 미만이라 건수만 낸 것이다. */
export function Rows({
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
    <ul className={'border-t ' + LINE}>
      {xs.map(([label, n, pct]) => {
        const on = picked === label
        const body = (
          <>
            <span className={'flex-1 min-w-0 truncate text-left ' + (on ? 'font-bold' : '')}>{label}</span>
            <span className="w-14 shrink-0 text-right tabular-nums">{n.toLocaleString()}</span>
            <span className="w-12 shrink-0 text-right tabular-nums text-[#666]">{pct === undefined ? '' : pct < 1 ? '<1%' : `${pct}%`}</span>
          </>
        )
        const cls = 'flex w-full items-center gap-2 h-8 text-sm text-[#272727]'
        return (
          <li key={label} className={'border-b ' + LINE}>
            {onPick ? (
              <button type="button" onClick={() => onPick(label)} aria-pressed={on} className={cls + ' hover:underline underline-offset-2'}>
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

/** KPI 한 칸 — 숫자 32/500 + 단위 16. 상자 없이 칸 사이 세로선(부르는 쪽이 그린다). */
export function Kpi({ label, value, unit, sub }: { label: string; value: ReactNode; unit?: string; sub?: ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-sm leading-5 text-[#666]">{label}</div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-[32px] font-medium leading-10 tabular-nums text-[#272727]">{value}</span>
        {unit && <span className="text-base text-[#666]">{unit}</span>}
      </div>
      {sub && <div className="mt-1 text-sm leading-5 text-[#666]">{sub}</div>}
    </div>
  )
}

/** '이름 N · 이름 N' 글줄 — 표 칸 안에서 막대 대신 쓴다. */
export function Inline({ items, limit = 8, empty = '없음', pct = false, onPick }: { items: Count[]; limit?: number; empty?: string; pct?: boolean; onPick?: (label: string) => void }) {
  const xs = items.slice(0, limit)
  if (!xs.length) return <span>{empty}</span>
  return (
    <span>
      {xs.map(([label, n, p], i) => (
        <span key={label} className="whitespace-nowrap">
          {i > 0 && ' · '}
          {onPick ? (
            <button type="button" onClick={() => onPick(label)} className="hover:underline underline-offset-2">
              {label} {n.toLocaleString()}
            </button>
          ) : (
            <>
              {label} {n.toLocaleString()}
              {pct && p !== undefined && `(${p}%)`}
            </>
          )}
        </span>
      ))}
    </span>
  )
}

/** 경로 한 줄 — 단계를 글자와 화살표로 잇는다(칩 없음). */
export function PathLine({ steps }: { steps: string[] }) {
  if (!steps.length) return null
  return <p className="text-sm leading-5 text-[#272727]">{steps.join(' → ')}</p>
}

/** 둥근 테두리 버튼 — 다시 시도·쪽 넘김·더 보기. */
export function PillButton({ children, onClick, disabled }: { children: ReactNode; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="h-9 rounded-full border border-[#d8d8d8] px-5 text-sm font-medium text-[#272727] hover:border-[#272727] disabled:border-[#eeeeee] disabled:text-[#c4c4c4] disabled:hover:border-[#eeeeee]"
    >
      {children}
    </button>
  )
}

// ── 상세(StoryView)가 쓰는 부품 — 상세는 이번 시안 범위 밖이라 예전 모양 그대로 둔다 ──

export function Card({ title, note, children, className = '' }: { title: ReactNode; note?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={'rounded-xl border border-[#e6e6e6] bg-white p-5 ' + className}>
      <h3 className="text-[15px] font-bold text-[#272727]">{title}</h3>
      {note && <p className="mt-0.5 text-xs text-[#999] leading-relaxed">{note}</p>}
      <div className="mt-3">{children}</div>
    </section>
  )
}

/** 경로 한 줄 — 단계를 화살표로 잇는다. */
export function Steps({ steps }: { steps: string[] }) {
  if (!steps.length) return null
  return (
    <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[13px] text-[#555]">
      {steps.map((s, i) => (
        <li key={i} className="flex items-center gap-1.5">
          {i > 0 && <span aria-hidden className="text-[#bbb]">→</span>}
          <span className="rounded bg-[#f3f4f6] px-1.5 py-0.5">{s}</span>
        </li>
      ))}
    </ol>
  )
}
