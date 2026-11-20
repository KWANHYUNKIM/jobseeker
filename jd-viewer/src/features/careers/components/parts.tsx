import type { ReactNode } from 'react'
import type { Count } from '../api'

/** 막대 목록 — [이름, 건수, 비율?]. 비율이 없으면 표본이 3건 미만이라 건수만 낸 것이다. */
export function Bars({
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
  if (!xs.length) return <p className="text-sm text-[#aaa]">{empty}</p>
  const max = Math.max(...xs.map((x) => x[1]))
  return (
    <ul className="flex flex-col gap-1.5">
      {xs.map(([label, n, pct]) => {
        const on = picked === label
        const body = (
          <>
            <span className="relative z-10 flex-1 min-w-0 truncate text-left">{label}</span>
            <span className="relative z-10 shrink-0 tabular-nums text-[#888]">
              {n.toLocaleString()}
              {pct !== undefined && <span className="ml-1 text-[#bbb]">{pct}%</span>}
            </span>
            <span
              aria-hidden
              className={'absolute inset-y-0 left-0 rounded ' + (on ? 'bg-(--color-accent)/25' : 'bg-(--color-accent)/10')}
              style={{ width: `${Math.max(3, (100 * n) / max)}%` }}
            />
          </>
        )
        const cls = 'relative flex items-center gap-3 px-2 py-1 text-sm text-[#333] rounded overflow-hidden w-full'
        return (
          <li key={label}>
            {onPick ? (
              <button type="button" onClick={() => onPick(label)} className={cls + ' hover:ring-1 hover:ring-(--color-accent)/40'}>
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

export function Card({ title, note, children, className = '' }: { title: ReactNode; note?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={'rounded-xl border border-[#e6e6e6] bg-white p-5 ' + className}>
      <h3 className="text-[15px] font-bold text-[#272727]">{title}</h3>
      {note && <p className="mt-0.5 text-xs text-[#999] leading-relaxed">{note}</p>}
      <div className="mt-3">{children}</div>
    </section>
  )
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="rounded-xl bg-[#f6f7f9] px-5 py-4">
      <div className="text-[13px] text-[#888]">{label}</div>
      <div className="mt-1 text-[24px] font-bold tabular-nums text-[#272727] leading-8">{value}</div>
      {sub && <div className="text-xs text-[#aaa] mt-0.5">{sub}</div>}
    </div>
  )
}

export function Chip({ on, children, onClick }: { on?: boolean; children: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      className={
        'shrink-0 rounded-full border px-3 py-1 text-[13px] ' +
        (on ? 'border-(--color-accent) bg-(--color-accent) text-white font-semibold' : 'border-[#ddd] text-[#555] hover:border-[#999]')
      }
    >
      {children}
    </button>
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

