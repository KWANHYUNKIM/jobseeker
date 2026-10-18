import { CompanyMark } from '../../../components/ui'
import type { HomeCompany } from '../api'
import { careerRange, ddayLabel, ddayUrgent, SIZE_SHORT } from '../utils'

/**
 * 회사 카드 — 로고가 맨 위에 크게, 그다음 이름·규모·업종, 그 회사가 찾는 경력 폭과 공고 제목.
 * 캐치 첫 화면의 카드 순서(로고 → 회사 → 공고)를 따랐다. 누르면 오른쪽 패널에 그 회사의 IT 공고.
 */
export function CompanyCard({ c, active, onOpen }: { c: HomeCompany; active: boolean; onOpen: () => void }) {
  const range = careerRange(c.career_from, c.career_to)
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-pressed={active}
      className={
        'group text-left flex flex-col gap-3 p-4 rounded-xl border bg-(--color-panel) transition ' +
        'hover:border-(--color-accent) hover:shadow-[0_4px_16px_rgba(0,0,0,0.06)] ' +
        (active ? 'border-(--color-accent) ring-2 ring-(--color-accent)/25' : 'border-(--color-border)')
      }
    >
      <div className="flex items-start justify-between gap-2">
        <span className="grid place-items-center w-14 h-14 rounded-lg border border-(--color-border-soft) bg-white overflow-hidden">
          <CompanyMark name={c.name} logo={c.logo} size={40} />
        </span>
        <span
          className={
            'text-xs font-semibold tabular-nums ' +
            (ddayUrgent(c.soonest_dday) ? 'text-(--color-red-400)' : 'text-(--color-faint)')
          }
        >
          {ddayLabel(c.soonest_dday)}
        </span>
      </div>

      <div className="min-w-0">
        <div className="flex items-center gap-1.5 min-w-0">
          <h3 className="font-bold text-[15px] text-(--color-text) truncate">{c.name}</h3>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-1 text-[11px]">
          <span
            className={
              'px-1.5 py-0.5 rounded font-semibold ' +
              (c.size === '대기업'
                ? 'bg-(--color-accent) text-(--color-on-accent)'
                : c.size === '중견기업'
                  ? 'bg-(--color-accent-weak) text-(--color-accent-deep)'
                  : 'bg-(--color-band) text-(--color-muted)')
            }
          >
            {SIZE_SHORT[c.size] ?? c.size}
          </span>
          {c.industry !== '기타' && (
            <span className="px-1.5 py-0.5 rounded bg-(--color-band) text-(--color-muted)">{c.industry}</span>
          )}
          {c.new_7d > 0 && (
            <span className="px-1.5 py-0.5 rounded text-(--color-accent-deep) bg-(--color-accent-weak)">
              새 공고 {c.new_7d}
            </span>
          )}
        </div>
      </div>

      <ul className="flex flex-col gap-1 min-h-[2.6rem]">
        {c.titles.slice(0, 2).map((t) => (
          <li key={t.site + t.pid} className="text-[13px] leading-snug text-(--color-muted) line-clamp-1">
            {t.title}
          </li>
        ))}
      </ul>

      <div className="mt-auto pt-3 border-t border-(--color-border-soft) flex items-center gap-2 text-xs">
        <span className="font-semibold text-(--color-text) tabular-nums">IT 공고 {c.active}</span>
        {range && <span className="text-(--color-muted)">· {range}</span>}
        {c.entry > 0 && (
          <span className="ml-auto shrink-0 px-1.5 py-0.5 rounded border border-(--color-accent)/40 text-(--color-accent-deep)">
            신입 {c.entry}
          </span>
        )}
      </div>
    </button>
  )
}
