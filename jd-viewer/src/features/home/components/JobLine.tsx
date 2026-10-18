import { CompanyMark } from '../../../components/ui'
import { onLinkClick } from '../../../utils/navigation'
import { paths } from '../../../utils/urls'
import type { HomeJob } from '../api'
import { careerOf, ddayLabel, ddayUrgent } from '../utils'

/** 공고 한 줄 — 신입·경력 목록과 회사 패널이 같이 쓴다. 누르면 공고 상세(`/jobs/<키>`). */
export function JobLine({ j, showCompany = true }: { j: HomeJob; showCompany?: boolean }) {
  const to = paths.job(j)
  const place = [j.region, j.district].filter(Boolean).join(' ')
  return (
    <a
      href={to}
      onClick={onLinkClick(to)}
      className="flex items-start gap-3 px-3 py-2.5 rounded-lg hover:bg-(--color-band) transition"
    >
      {showCompany && (
        <span className="grid place-items-center w-9 h-9 shrink-0 rounded-md border border-(--color-border-soft) bg-white overflow-hidden">
          <CompanyMark name={j.company} logo={j.logo} size={26} />
        </span>
      )}
      <span className="min-w-0 flex-1">
        {showCompany && <span className="block text-xs font-semibold text-(--color-text)">{j.company}</span>}
        <span className="block text-[13.5px] leading-snug text-(--color-text) line-clamp-2">{j.title}</span>
        <span className="mt-1 flex flex-wrap gap-x-2 gap-y-0.5 text-[11.5px] text-(--color-faint)">
          <span>{careerOf(j.career, j.career_bucket)}</span>
          {place && <span>{place}</span>}
          {j.roles.slice(0, 2).map((r) => (
            <span key={r} className="text-(--color-muted)">#{r}</span>
          ))}
        </span>
      </span>
      <span
        className={
          'shrink-0 text-xs tabular-nums font-semibold ' +
          (ddayUrgent(j.dday) ? 'text-(--color-red-400)' : 'text-(--color-faint)')
        }
      >
        {ddayLabel(j.dday)}
      </span>
    </a>
  )
}
