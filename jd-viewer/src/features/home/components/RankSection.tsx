import { useState } from 'react'
import { CompanyMark } from '../../../components/ui'
import { onLinkClick } from '../../../utils/navigation'
import { paths } from '../../../utils/urls'
import { fetchSection, type HomeJob, type HomeSection } from '../api'
import { careerOf, ddayLabel, ddayUrgent } from '../utils'

const STEP = 15
const FIRST = 7   // 1위 카드 + 여섯 줄 — 구역 셋이 한 줄에 나란히 서도 한 화면에 들어온다

/**
 * 순위 구역 하나 — 'OO 인기 TOP 50'. 1위는 로고와 함께 크게, 2위부터는 번호 붙은 줄.
 * 처음엔 7건, 더보기를 누르면 그때 50건을 받아 15건씩 더 편다(첫 화면은 10건만 싣고 온다).
 */
export function RankSection({ s }: { s: HomeSection }) {
  const [all, setAll] = useState<HomeJob[] | null>(null)
  const [shown, setShown] = useState(FIRST)
  const [loading, setLoading] = useState(false)
  const jobs = all ?? s.jobs
  const max = Math.min(50, s.total)

  const more = async () => {
    if (!all) {
      setLoading(true)
      try {
        setAll((await fetchSection(s.key)).jobs)
      } finally {
        setLoading(false)
      }
    }
    setShown((n) => Math.min(n + STEP, 50))
  }

  const [first, ...rest] = jobs.slice(0, shown)
  if (!first) return null

  return (
    <section id={`sec-${s.key}`} className="scroll-mt-28 flex flex-col rounded-2xl border border-(--color-border) bg-(--color-panel) p-4 sm:p-5">
      <header className="flex items-baseline justify-between gap-2 mb-3">
        <h3 className="text-[17px] sm:text-lg font-extrabold tracking-[-0.02em] text-(--color-text)">
          {s.lead} TOP {max}
        </h3>
        <span className="shrink-0 text-xs text-(--color-faint) tabular-nums">{s.total.toLocaleString()}건 중</span>
      </header>

      <Featured j={first} />

      <ol className="mt-2 flex flex-col">
        {rest.map((j, k) => (
          <RankRow key={j.site + j.pid} j={j} rank={k + 2} fresh={k + 2 > FIRST} />
        ))}
      </ol>

      {(shown < Math.min(max, all?.length ?? max) || shown > FIRST) && (
        <div className="mt-auto pt-3 flex gap-2">
          {shown < Math.min(max, all?.length ?? max) && (
            <button
              type="button"
              onClick={more}
              disabled={loading}
              className="home-press flex-1 py-2.5 rounded-xl border border-(--color-border) text-sm font-semibold text-(--color-text) hover:border-(--color-text) disabled:opacity-60"
            >
              {loading ? '불러오는 중…' : `더보기 (${shown}/${max})`}
            </button>
          )}
          {shown > FIRST && (
            <button
              type="button"
              onClick={() => {
                setShown(FIRST)
                document.getElementById(`sec-${s.key}`)?.scrollIntoView({ block: 'start' })
              }}
              className="home-press px-4 py-2.5 rounded-xl text-sm text-(--color-muted) hover:text-(--color-text)"
            >
              접기
            </button>
          )}
        </div>
      )}
    </section>
  )
}

/** 1위 — 캐치의 큰 카드처럼 로고가 먼저 보이게. */
function Featured({ j }: { j: HomeJob }) {
  const to = paths.job(j)
  return (
    <a
      href={to}
      onClick={onLinkClick(to)}
      className="home-press group flex items-center gap-3.5 p-3 rounded-xl border border-(--color-border-soft) bg-(--color-band) hover:border-(--color-accent)"
    >
      <span className="grid place-items-center w-16 h-16 shrink-0 rounded-xl bg-white border border-(--color-border-soft) overflow-hidden">
        <CompanyMark name={j.company} logo={j.logo} size={44} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          <span className="text-[15px] font-bold text-(--color-text) truncate">{j.company}</span>
          <Dday d={j.dday} className="ml-auto" />
        </span>
        <span className="mt-0.5 block text-[13.5px] leading-snug text-(--color-text) line-clamp-2 group-hover:underline underline-offset-2">
          {j.title}
        </span>
        <span className="mt-1 block text-[12px] text-(--color-faint)">{careerOf(j.career, j.career_bucket)}</span>
      </span>
    </a>
  )
}

function RankRow({ j, rank, fresh }: { j: HomeJob; rank: number; fresh: boolean }) {
  const to = paths.job(j)
  return (
    <li className={fresh ? 'home-rise' : ''} style={{ ['--i' as string]: rank % 15 }}>
      <a href={to} onClick={onLinkClick(to)} className="group flex items-start gap-3 px-1.5 py-2.5 rounded-lg hover:bg-(--color-band)">
        <span
          className={
            'w-6 shrink-0 text-center text-[15px] font-extrabold tabular-nums leading-6 ' +
            (rank <= 3 ? 'text-(--color-accent)' : 'text-(--color-faint)')
          }
        >
          {rank}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="text-[13.5px] font-bold text-(--color-text) truncate">{j.company}</span>
            <Dday d={j.dday} className="ml-auto" />
          </span>
          <span className="block text-[13.5px] leading-snug text-(--color-muted) line-clamp-1 group-hover:text-(--color-text)">
            {j.title}
          </span>
        </span>
      </a>
    </li>
  )
}

function Dday({ d, className = '' }: { d: number | null; className?: string }) {
  return (
    <span
      className={
        'shrink-0 text-xs font-bold tabular-nums ' +
        (ddayUrgent(d) ? 'text-(--color-red-400)' : 'text-(--color-faint)') +
        ' ' +
        className
      }
    >
      {ddayLabel(d)}
    </span>
  )
}
