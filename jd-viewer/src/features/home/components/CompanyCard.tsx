import { CompanyMark } from '../../../components/ui'
import type { HomeCompany } from '../api'
import { careerRange, ddayLabel, ddayUrgent, SIZE_SHORT } from '../utils'

const SIZE_STYLE: Record<string, string> = {
  대기업: 'bg-(--color-accent) text-(--color-on-accent)',
  중견기업: 'bg-(--color-accent-weak) text-(--color-accent-deep)',
  '해외 기업': 'bg-[#e8eefb] text-[#1f4fa8]',
  중소기업: 'bg-(--color-band) text-(--color-muted)',
}

/**
 * 회사 카드 — 로고 → 이름·규모·업종 → 최근 공고 → 공고 수와 경력 폭.
 * 휴대폰에서는 가로 한 줄(로고 왼쪽)로 눕혀 한 화면에 더 많은 회사가 들어오게 하고,
 * sm 이상에서 캐치처럼 로고가 위에 크게 서는 세로 카드가 된다.
 * `i` 는 칸을 바꿨을 때 카드가 차례로 자리 잡는 순서(앞 12장까지만 늦춘다).
 */
export function CompanyCard({ c, i, active, onOpen }: { c: HomeCompany; i: number; active: boolean; onOpen: () => void }) {
  const range = careerRange(c.career_from, c.career_to)
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-pressed={active}
      style={{ ['--i' as string]: i }}
      className={
        'home-rise home-press group text-left flex sm:flex-col gap-3 p-3.5 sm:p-4 rounded-2xl border bg-(--color-panel) ' +
        'hover:border-(--color-accent) hover:shadow-[0_6px_20px_-8px_rgba(0,105,92,0.35)] focus-visible:outline-2 focus-visible:outline-(--color-accent) ' +
        (active ? 'border-(--color-accent) ring-2 ring-(--color-accent)/25' : 'border-(--color-border)')
      }
    >
      <div className="flex sm:items-start sm:justify-between gap-2 shrink-0">
        <span className="grid place-items-center w-12 h-12 sm:w-14 sm:h-14 rounded-xl border border-(--color-border-soft) bg-white overflow-hidden">
          <CompanyMark name={c.name} logo={c.logo} size={36} />
        </span>
        <span
          className={
            'hidden sm:inline text-xs font-bold tabular-nums ' +
            (ddayUrgent(c.soonest_dday) ? 'text-(--color-red-400)' : 'text-(--color-faint)')
          }
        >
          {ddayLabel(c.soonest_dday)}
        </span>
      </div>

      <div className="min-w-0 flex-1 flex flex-col">
        <div className="flex items-center gap-2 min-w-0">
          <h3 className="font-bold text-[15px] sm:text-base leading-tight text-(--color-text) truncate">{c.name}</h3>
          <span
            className={
              'sm:hidden ml-auto shrink-0 text-[11px] font-bold tabular-nums ' +
              (ddayUrgent(c.soonest_dday) ? 'text-(--color-red-400)' : 'text-(--color-faint)')
            }
          >
            {ddayLabel(c.soonest_dday)}
          </span>
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-1 text-[11.5px]">
          <span className={'px-1.5 py-0.5 rounded-md font-semibold ' + (SIZE_STYLE[c.size] ?? SIZE_STYLE['중소기업'])}>
            {SIZE_SHORT[c.size] ?? c.size}
          </span>
          {c.industry !== '기타' && (
            <span className="px-1.5 py-0.5 rounded-md bg-(--color-band) text-(--color-muted)">{c.industry}</span>
          )}
          {c.new_7d > 0 && (
            <span className="px-1.5 py-0.5 rounded-md font-semibold text-[#b4380b] bg-[#fdeee6]">이번 주 +{c.new_7d}</span>
          )}
        </div>

        <ul className="mt-2.5 flex flex-col gap-1 sm:min-h-[2.75rem]">
          {c.titles.slice(0, 2).map((t, k) => (
            <li
              key={t.site + t.pid}
              className={'text-[13.5px] leading-snug text-(--color-muted) line-clamp-1 ' + (k ? 'hidden sm:block' : '')}
            >
              {t.title}
            </li>
          ))}
        </ul>

        <div className="mt-3 pt-2.5 sm:mt-auto border-t border-(--color-border-soft) flex items-center gap-2 text-[12.5px]">
          <span className="font-bold text-(--color-text) tabular-nums">공고 {c.active}</span>
          {range && <span className="text-(--color-muted)">{range}</span>}
          {c.entry > 0 && (
            <span className="ml-auto shrink-0 px-1.5 py-0.5 rounded-md border border-(--color-accent)/40 text-(--color-accent-deep) font-semibold">
              신입 {c.entry}
            </span>
          )}
        </div>
      </div>
    </button>
  )
}
