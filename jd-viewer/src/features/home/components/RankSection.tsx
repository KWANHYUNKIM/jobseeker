import { useState } from 'react'
import { CompanyMark } from '../../../components/ui'
import { onLinkClick } from '../../../utils/navigation'
import { paths } from '../../../utils/urls'
import { fetchSection, type HomeJob, type HomeSection } from '../api'
import { careerOf, ddayLabel, ddayUrgent, scoreText } from '../utils'
import { RankRule } from './RankRule'

const FIRST = 6 // 1위 카드 + 다섯 줄 — 캐치형 카드 한 장의 높이(664)에 꼭 맞는다
const STEP = 10

/**
 * 순위 카드(캐치형 400×664) — 위 줄(`ranked`)은 '신입 인기 TOP 50', 아래 줄은 구역 이름만. 1위는 로고와 함께 큰 칸, 2위부터 번호 줄.
 * 더보기를 누르면 그때 50건을 받아 열 건씩 편다(첫 화면은 10건만 싣고 온다).
 */
export function RankSection({ s, ranked }: { s: HomeSection; ranked: boolean }) {
  const [all, setAll] = useState<HomeJob[] | null>(null)
  const [shown, setShown] = useState(FIRST)
  const [loading, setLoading] = useState(false)
  const jobs = all ?? s.jobs
  const max = Math.min(50, s.total)

  const more = async () => {
    if (shown >= Math.min(max, all?.length ?? max)) {
      setShown(FIRST)
      document.getElementById(`sec-${s.key}`)?.scrollIntoView({ block: 'start' })
      return
    }
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
  const done = shown >= Math.min(max, all?.length ?? max)

  return (
    <section
      id={`sec-${s.key}`}
      className="scroll-mt-28 flex flex-col min-h-[664px] rounded-[30px] border border-[#e2e8ec] bg-white px-[19px] pt-6 pb-[26px]"
    >
      <header className="flex items-baseline gap-[15px] px-3">
        <h3 className="text-xl font-bold leading-[29px] tracking-[-0.2px] text-[#272727]">
          {ranked ? (
            <>
              <span className="text-(--color-accent)">{s.title}</span> 인기 TOP {max}
            </>
          ) : (
            s.title
          )}
        </h3>
        <span className="shrink-0 text-[13px] tracking-[-0.13px] text-[#999] tabular-nums">{s.total.toLocaleString()}건 중</span>
      </header>
      {ranked && (
        <div className="mt-1 px-3">
          <RankRule kind="jobs" />
        </div>
      )}

      <Featured j={first} />

      <ol className="mt-[3px] flex flex-col">
        {rest.map((j, k) => (
          <RankRow key={j.site + j.pid} j={j} rank={k + 1} />
        ))}
      </ol>

      {(s.total > FIRST || shown > FIRST) && (
        <button
          type="button"
          onClick={more}
          disabled={loading}
          className="home-press mt-auto flex items-center justify-center gap-1.5 h-[38px] rounded-[30px] bg-[#272727] text-base font-medium tracking-[-0.16px] text-white disabled:opacity-60"
        >
          {loading ? '불러오는 중…' : done && shown > FIRST ? '접기' : '더보기'}
          <svg width="8" height="10" viewBox="0 0 8 10" fill="none" stroke="#fff" strokeWidth="1.5" strokeLinecap="round">
            <path d={done && shown > FIRST ? 'M1 7l3-3 3 3' : 'M2.5 1.5 6 5l-3.5 3.5'} />
          </svg>
        </button>
      )}
    </section>
  )
}

/** 1위 — 로고가 먼저 보이는 큰 칸. */
function Featured({ j }: { j: HomeJob }) {
  const to = paths.job(j)
  return (
    <a
      href={to}
      onClick={onLinkClick(to)}
      title={scoreText(j.score, j.score_parts) || undefined}
      className="home-press group mt-[29px] flex gap-10 min-h-[130px] rounded-[30px] border border-[#e2e8ec] pl-[25px] pr-[19px] pt-[15px] pb-3 hover:border-[#272727]"
    >
      <span className="mt-[19px] grid place-items-center w-16 h-16 shrink-0">
        <CompanyMark name={j.company} logo={j.logo} size={64} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-start gap-2">
          <span className="text-lg font-medium leading-[26px] tracking-[-0.09px] text-[#272727] truncate">{j.company}</span>
          <Dday d={j.dday} className="ml-auto mt-0.5" />
        </span>
        <span className="mt-px text-base leading-[22px] tracking-[-0.16px] text-[#666] line-clamp-2 group-hover:underline underline-offset-2">
          {j.title}
        </span>
        <span className="mt-2 inline-block rounded bg-(--color-accent-weak) px-1.5 text-sm leading-[22px] tracking-[-0.14px] text-(--color-accent)">
          {careerOf(j.career, j.career_bucket)}
        </span>
      </span>
    </a>
  )
}

function RankRow({ j, rank }: { j: HomeJob; rank: number }) {
  const to = paths.job(j)
  return (
    <li>
      <a href={to} onClick={onLinkClick(to)} title={scoreText(j.score, j.score_parts) || undefined} className="group flex items-center gap-[18px] h-[75.5px] pl-[18px] pr-0">
        <span className="w-3 shrink-0 flex flex-col items-center text-[#272727]">
          <span className="text-lg font-medium leading-[26px] tabular-nums">{rank}</span>
          <span className="-mt-1 text-xs leading-[18px]">—</span>
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-lg font-medium leading-[26px] tracking-[-0.09px] text-[#272727] truncate">{j.company}</span>
          <span className="block text-base leading-6 tracking-[-0.16px] text-[#666] truncate group-hover:text-[#272727]">{j.title}</span>
        </span>
        <Dday d={j.dday} className="w-[50px] text-right" />
      </a>
    </li>
  )
}

function Dday({ d, className = '' }: { d: number | null; className?: string }) {
  return (
    <span
      className={
        'shrink-0 text-sm leading-[21px] tracking-[-0.14px] tabular-nums ' +
        (ddayUrgent(d) && d != null && d <= 0 ? 'text-(--color-accent)' : 'text-[#999]') +
        ' ' +
        className
      }
    >
      {ddayLabel(d)}
    </span>
  )
}
