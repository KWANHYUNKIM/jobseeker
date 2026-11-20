import { useEffect, useState } from 'react'
import { CompanyMark, ErrorState, Loader } from '../../../components/ui'
import { goBack, onLinkClick } from '../../../utils/navigation'
import { absUrl, useSeo } from '../../../utils/seo'
import { paths } from '../../../utils/urls'
import { fetchSection, type HomeJob, type HomeSection } from '../api'
import { BANNER_ART } from '../banner'
import { careerOf, ddayLabel, ddayUrgent } from '../utils'

/**
 * `/top/<구역>` — 메인 배너 한 장(신입·경력·인턴…)을 누르면 들어오는 화면. 그 구역의 인기 TOP 50 을
 * 한 줄씩 다 편다(메인의 순위 카드는 여섯 줄만 보이고 더보기로 연다). 머리는 배너와 같은 그림이다.
 */
export function TopBoard({ sectionKey }: { sectionKey: string }) {
  // 받은 결과를 구역 키와 같이 둔다 — 다른 구역으로 넘어가면 키가 달라 지난 결과가 안 보인다.
  const [got, setGot] = useState<{ key: string; s?: HomeSection; err?: string } | null>(null)
  const s = got?.key === sectionKey ? (got.s ?? null) : null
  const err = got?.key === sectionKey ? (got.err ?? null) : null

  useEffect(() => {
    const ctl = new AbortController()
    fetchSection(sectionKey, { signal: ctl.signal })
      .then((x) => setGot({ key: sectionKey, s: x }))
      .catch((e: Error) => e.name !== 'AbortError' && setGot({ key: sectionKey, err: e.message }))
    return () => ctl.abort()
  }, [sectionKey])

  const top = s ? Math.min(50, s.total) : 50
  useSeo(
    s
      ? {
          title: `${s.title} 개발자 공고 인기 TOP ${top}`,
          description: `지금 모집중인 ${s.title} IT·개발자 공고 ${s.total.toLocaleString()}건 가운데 인기 순으로 ${top}건을 골랐습니다.`,
          canonical: absUrl(paths.top(sectionKey)),
        }
      : null,
  )

  if (err && !s) {
    return (
      <ErrorState
        title="이 구역의 공고를 불러오지 못했습니다"
        detail={err}
        hint={
          <a href={paths.home()} onClick={onLinkClick(paths.home())} className="text-(--color-accent) underline">
            메인으로 가기
          </a>
        }
      />
    )
  }
  if (!s) return <Loader label="인기 공고 고르는 중…" />

  const art = BANNER_ART[s.key] ?? BANNER_ART.all
  const jobs = s.jobs.slice(0, 50)

  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[38px] pb-[70px]">
        <header
          className="relative h-[200px] sm:h-[240px] overflow-hidden rounded-[30px] bg-[#000b4b] bg-cover bg-right"
          style={{ backgroundImage: `url(${art.img})`, color: art.fg }}
        >
          <button
            type="button"
            onClick={() => goBack(paths.home())}
            className={`absolute left-6 top-5 h-[26px] px-3 rounded-full text-xs font-medium ${art.fg === '#fff' ? 'bg-white/18 hover:bg-white/30' : 'bg-black/10 hover:bg-black/20'}`}
          >
            ‹ 메인으로
          </button>
          <div className="absolute left-6 sm:left-[9%] top-[30%] right-6 sm:right-[40%]">
            <p className="text-lg font-bold leading-[26px] tracking-[-0.18px]">{s.title} 공고 모아보기</p>
            <h1 className="mt-0.5 text-[24px] sm:text-[32px] font-bold leading-[1.19] tracking-[-1.6px]">
              {s.title} 인기 TOP {top}
            </h1>
            <p className="mt-2.5 text-sm sm:text-base font-medium leading-6 tracking-[-0.16px] opacity-90">
              모집중 {s.total.toLocaleString()}건 중 인기 순
            </p>
          </div>
        </header>

        {jobs.length === 0 ? (
          <p className="mt-10 text-center text-[#999]">지금 이 구역에 모집중인 공고가 없습니다.</p>
        ) : (
          <ol className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-x-6 border-t border-[#e2e8ec] lg:border-t-0">
            {jobs.map((j, k) => (
              <TopRow key={j.site + j.pid} j={j} rank={k + 1} />
            ))}
          </ol>
        )}

        {s.total > jobs.length && (
          <div className="mt-8 text-center">
            <a
              href={paths.jobs()}
              onClick={onLinkClick(paths.jobs())}
              className="home-press inline-flex items-center h-[38px] px-6 rounded-[30px] bg-[#272727] text-base font-medium tracking-[-0.16px] text-white"
            >
              잡 리스트에서 {s.total.toLocaleString()}건 전부 거르기
            </a>
          </div>
        )}
      </div>
    </div>
  )
}

function TopRow({ j, rank }: { j: HomeJob; rank: number }) {
  const to = paths.job(j)
  const place = [j.region, j.district].filter(Boolean).join(' ')
  return (
    <li className="border-b border-[#e2e8ec]">
      <a href={to} onClick={onLinkClick(to)} className="group flex items-center gap-4 py-4 px-2 hover:bg-[#f7f9fa]">
        <span
          className={`w-7 shrink-0 text-center text-lg font-bold tabular-nums ${rank <= 3 ? 'text-(--color-accent)' : 'text-[#272727]'}`}
        >
          {rank}
        </span>
        <span className="grid place-items-center w-11 h-11 shrink-0 rounded-lg border border-[#e2e8ec] bg-white overflow-hidden">
          <CompanyMark name={j.company} logo={j.logo} size={32} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-base font-medium leading-6 tracking-[-0.09px] text-[#272727] truncate">{j.company}</span>
          <span className="block text-[15px] leading-[22px] tracking-[-0.16px] text-[#666] truncate group-hover:text-[#272727] group-hover:underline underline-offset-2">
            {j.title}
          </span>
          <span className="mt-1 flex flex-wrap gap-x-2 text-xs text-[#999]">
            <span className="text-(--color-accent)">{careerOf(j.career, j.career_bucket)}</span>
            {place && <span>{place}</span>}
            {j.roles.slice(0, 2).map((r) => (
              <span key={r}>#{r}</span>
            ))}
          </span>
        </span>
        <span
          className={`shrink-0 w-[60px] text-right text-sm tabular-nums ${ddayUrgent(j.dday) ? 'text-(--color-accent)' : 'text-[#999]'}`}
        >
          {ddayLabel(j.dday)}
        </span>
      </a>
    </li>
  )
}
