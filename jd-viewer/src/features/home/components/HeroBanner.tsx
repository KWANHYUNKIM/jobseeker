import { useState, type ReactNode } from 'react'
import { CompanyMark } from '../../../components/ui'
import { onLinkClick } from '../../../utils/navigation'
import { paths } from '../../../utils/urls'
import { companyLogoUrl, safeLogoUrl } from '../../../utils/companyMark'
import type { HomeBoard } from '../api'

/** 첫 줄 — 왼쪽 바로가기 넷, 오른쪽 남색 배너(넘겨 보는 판). 캐치형 1920 의 y=156~437. */
export function HeroRow({ d }: { d: HomeBoard }) {
  return (
    <div className="flex flex-col lg:flex-row gap-6">
      <QuickLinks />
      <Banner d={d} />
    </div>
  )
}

const LINKS: { to: string; title: string; note: string; icon: ReactNode }[] = [
  {
    to: paths.calendar(),
    title: '실시간 모집캘린더',
    note: '주요 공채 마감 일정 한 눈에',
    icon: (
      <svg viewBox="0 0 34 34" width="34" height="34">
        <rect x="4" y="7" width="26" height="23" rx="4" fill="#ffd66b" />
        <rect x="4" y="7" width="26" height="8" rx="4" fill="#f45757" />
        <rect x="10" y="3" width="3" height="8" rx="1.5" fill="#272727" />
        <rect x="21" y="3" width="3" height="8" rx="1.5" fill="#272727" />
        <rect x="9" y="19" width="5" height="4" rx="1" fill="#fff" />
        <rect x="17" y="19" width="5" height="4" rx="1" fill="#fff" />
      </svg>
    ),
  },
  {
    to: paths.reposts(),
    title: '다시 열린 재공고',
    note: '놓친 회사, 다시 지원하기',
    icon: (
      <svg viewBox="0 0 34 34" width="34" height="34" fill="none">
        <circle cx="17" cy="17" r="13" fill="#7fb6ff" />
        <path d="M11 19a6 6 0 1 0 2-6.5" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" />
        <path d="M13 9v4h4" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    to: paths.companies(),
    title: '기업 기술스택',
    note: '회사별로 쓰는 기술 비교',
    icon: (
      <svg viewBox="0 0 34 34" width="34" height="34" fill="none">
        <path d="M17 5 30 12 17 19 4 12Z" fill="#8b7cf6" />
        <path d="M4 18l13 7 13-7" stroke="#b8aeff" strokeWidth="3" strokeLinejoin="round" />
        <path d="M4 23l13 7 13-7" stroke="#d9d3ff" strokeWidth="3" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    to: paths.mindmap(),
    title: '커리어 마인드맵',
    note: '직무별 성장 경로 한눈에',
    icon: (
      <svg viewBox="0 0 34 34" width="34" height="34" fill="none">
        <path d="M9 10l8 7m0 0 8-7M17 17l-8 8m8-8 8 8" stroke="#2bb673" strokeWidth="2" />
        <circle cx="17" cy="17" r="5" fill="#2bb673" />
        <circle cx="6.5" cy="7.5" r="3.5" fill="#9fe3be" />
        <circle cx="28.5" cy="8.5" r="3.5" fill="#9fe3be" />
        <circle cx="7.5" cy="26.5" r="3.5" fill="#9fe3be" />
        <circle cx="27.5" cy="26.5" r="3.5" fill="#9fe3be" />
      </svg>
    ),
  },
]

function QuickLinks() {
  return (
    <nav aria-label="바로가기" className="shrink-0 lg:w-[240px] lg:h-[281px] rounded-[30px] bg-[#f7f9fa] px-[22px] py-[28px] grid grid-cols-2 lg:grid-cols-1 gap-y-[23px] gap-x-4">
      {LINKS.map((l) => (
        <a key={l.to} href={l.to} onClick={onLinkClick(l.to)} className="group flex items-center gap-3">
          <span className="shrink-0">{l.icon}</span>
          <span className="min-w-0">
            <span className="block text-base font-medium leading-6 tracking-[-0.8px] text-[#272727] group-hover:text-(--color-accent)">{l.title}</span>
            <span className="block -mt-0.5 text-xs leading-[17px] tracking-[-0.6px] text-[#474747]">{l.note}</span>
          </span>
        </a>
      ))}
    </nav>
  )
}

/** 로고 타일 여섯 칸의 자리(배너 오른쪽·위에서 잰 거리) — 캐치형 보드 그대로. */
const TILE_AT: [number, number][] = [
  [320, 104],
  [232, 42],
  [224, 152],
  [136, 90],
  [56, 34],
  [56, 160],
]

type Slide = { kicker: string; head: [string, string]; tags: [string, string]; logos: { name: string; logo: string | null }[] }

/** 넘겨 보는 판 — 첫 장은 전체 숫자, 다음 장들은 순위 구역(신입·경력·인턴…) 하나씩. */
function slidesOf(d: HomeBoard): Slide[] {
  const sizes = Object.fromEntries(d.facets.sizes.map((s) => [s.name, s.n]))
  const entry = d.sections.find((s) => s.key === 'entry')?.total ?? d.totals.entry
  const first: Slide = {
    kicker: '오늘 개발자를 찾는 회사',
    head: [`모집중인 IT 공고 ${d.totals.jobs.toLocaleString()}건,`, '큰 곳부터 보여드려요'],
    tags: [
      `#회사 ${d.totals.companies.toLocaleString()}곳 #신입 지원 가능 ${entry.toLocaleString()}건`,
      `#대기업 ${sizes['대기업'] ?? 0} · 중견 ${sizes['중견기업'] ?? 0} · 중소 ${sizes['중소기업'] ?? 0} · 해외 ${sizes['해외 기업'] ?? 0}`,
    ],
    logos: distinctLogos([...d.spotlight, ...d.companies]),
  }
  const rest = d.sections
    .filter((s) => !s.key.startsWith('ind:') && s.key !== 'today')
    .map((s): Slide => {
      const cos = [...new Map(s.jobs.map((j) => [j.company, { name: j.company, logo: j.logo }])).values()]
      return {
        kicker: `${s.title} 공고 모아보기`,
        head: [`${s.title} 공고 ${s.total.toLocaleString()}건,`, '인기 순으로 골라봤어요'],
        tags: [`#${s.title} #TOP ${Math.min(50, s.total)}`, cos.slice(0, 3).map((c) => `#${c.name}`).join(' ')],
        logos: distinctLogos(cos),
      }
    })
  return [first, ...rest]
}

/** 로고 타일 여섯 — 같은 그림(토스·토스증권·토스뱅크…)이 겹치지 않게 한 번씩만. */
function distinctLogos(cos: { name: string; logo: string | null }[]): { name: string; logo: string | null }[] {
  // 계열사(카카오페이 → 카카오, 토스증권 → 토스)는 로고가 같거나 비슷해서 목록에 있는 모회사 하나로 접는다.
  const rootOf = (c: { name: string }) =>
    cos.filter((o) => c.name.startsWith(o.name)).sort((x, y) => x.name.length - y.name.length)[0] ?? c
  const seen = new Set<string>()
  const out: { name: string; logo: string | null }[] = []
  for (const c0 of cos) {
    const c = rootOf(c0)
    const key = safeLogoUrl(c.logo) || companyLogoUrl(c.name) || c.name
    if (seen.has(key) || seen.has(c.name)) continue
    seen.add(key)
    seen.add(c.name)
    out.push({ name: c.name, logo: c.logo })
    if (out.length === 6) break
  }
  return out
}

function Banner({ d }: { d: HomeBoard }) {
  const slides = slidesOf(d)
  const [i, setI] = useState(0)
  const s = slides[i % slides.length]
  const go = (k: number) => setI((n) => (n + k + slides.length) % slides.length)
  return (
    <section
      aria-roledescription="carousel"
      aria-label="오늘의 채용"
      className="relative flex-1 min-w-0 h-[281px] overflow-hidden rounded-[30px] bg-[#000b4b] text-white"
    >
      <div className="absolute left-6 sm:left-[94px] top-[47px] right-6">
        <p className="text-lg font-bold leading-[26px] tracking-[-0.18px]">{s.kicker}</p>
        <h2 className="-mt-[5px] text-[24px] sm:text-[32px] font-bold leading-[1.19] tracking-[-1.6px]">
          {s.head[0]}
          <br />
          {s.head[1]}
        </h2>
        <p className="mt-[12px] text-sm sm:text-base font-medium leading-6 tracking-[-0.16px]">
          {s.tags[0]}
          <br />
          {s.tags[1]}
        </p>
      </div>
      <div aria-hidden className="hidden xl:block">
        {s.logos.map((c, k) => (
          <span
            key={c.name}
            style={{ right: TILE_AT[k][0], top: TILE_AT[k][1] }}
            className="absolute grid place-items-center w-[76px] h-[76px] rounded-[22px] bg-white shadow-[0_10px_24px_rgba(0,0,0,0.35)]"
          >
            <CompanyMark name={c.name} logo={c.logo} size={46} />
          </span>
        ))}
      </div>
      <Arrow side="left" onClick={() => go(-1)} />
      <Arrow side="right" onClick={() => go(1)} />
      <span className="absolute right-8 bottom-8 h-[25px] px-3 rounded-full bg-white/14 text-xs leading-[25px] tabular-nums">
        {i + 1} / {slides.length} +
      </span>
    </section>
  )
}

function Arrow({ side, onClick }: { side: 'left' | 'right'; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={side === 'left' ? '이전' : '다음'}
      className={`absolute top-[127px] ${side === 'left' ? 'left-8' : 'right-8'} w-7 h-7 rounded-full bg-white/18 grid place-items-center hover:bg-white/30`}
    >
      <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="#fff" strokeWidth="1.6" strokeLinecap="round">
        <path d={side === 'left' ? 'M6.5 1.5 3 5l3.5 3.5' : 'M3.5 1.5 7 5 3.5 8.5'} />
      </svg>
    </button>
  )
}
