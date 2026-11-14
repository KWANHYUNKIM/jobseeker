import { useState, type ReactNode } from 'react'
import { onLinkClick } from '../../../utils/navigation'
import { paths } from '../../../utils/urls'
import type { HomeBoard } from '../api'

/** 첫 줄 — 왼쪽 바로가기 넷, 오른쪽 남색 배너(넘겨 보는 판, 장마다 배경 그림). 캐치형 1920 의 y=156~437. */
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

/** 장마다 배경 그림과 글자색 — 그림은 오른쪽에 그려져 있고 왼쪽은 글자 자리로 비어 있다(1440×432). */
const ART: Record<string, { img: string; fg: string }> = {
  all: { img: '/home/banner/all.jpg', fg: '#fff' },
  entry: { img: '/home/banner/entry.jpg', fg: '#0b3b2c' },
  experienced: { img: '/home/banner/experienced.jpg', fg: '#fff' },
  intern: { img: '/home/banner/intern.jpg', fg: '#fff' },
  midsmall: { img: '/home/banner/midsmall.jpg', fg: '#fff' },
  overseas: { img: '/home/banner/overseas.jpg', fg: '#fff' },
}

type Slide = { key: string; kicker: string; head: [string, string]; tag: string }

/** 넘겨 보는 판 — 첫 장은 전체 숫자, 다음 장들은 순위 구역(신입·경력·인턴…) 하나씩. */
function slidesOf(d: HomeBoard): Slide[] {
  const entry = d.sections.find((s) => s.key === 'entry')?.total ?? d.totals.entry
  const first: Slide = {
    key: 'all',
    kicker: '오늘 개발자를 찾는 회사',
    head: [`모집중인 IT 공고 ${d.totals.jobs.toLocaleString()}건,`, '큰 곳부터 보여드려요'],
    tag: `#회사 ${d.totals.companies.toLocaleString()}곳 #신입 지원 가능 ${entry.toLocaleString()}건`,
  }
  const rest = d.sections
    .filter((s) => !s.key.startsWith('ind:') && s.key !== 'today')
    .map((s): Slide => ({
      key: s.key,
      kicker: `${s.title} 공고 모아보기`,
      head: [`${s.title} 공고 ${s.total.toLocaleString()}건,`, '인기 순으로 골라봤어요'],
      tag: `#${s.title} #TOP ${Math.min(50, s.total)}`,
    }))
  return [first, ...rest]
}

function Banner({ d }: { d: HomeBoard }) {
  const slides = slidesOf(d)
  const [i, setI] = useState(0)
  const s = slides[i % slides.length]
  const go = (k: number) => setI((n) => (n + k + slides.length) % slides.length)
  const art = ART[s.key] ?? ART.all
  const dark = art.fg !== '#fff'
  return (
    <section
      aria-roledescription="carousel"
      aria-label="오늘의 채용"
      className="relative flex-1 min-w-0 h-[281px] overflow-hidden rounded-[30px] bg-[#000b4b] bg-cover bg-right"
      style={{ backgroundImage: `url(${art.img})`, color: art.fg }}
    >
      <div className="absolute left-6 sm:left-[9%] top-[16%] right-6 sm:right-[40%]">
        <p className="text-lg font-bold leading-[26px] tracking-[-0.18px]">{s.kicker}</p>
        <h2 className="mt-0.5 text-[24px] sm:text-[32px] font-bold leading-[1.19] tracking-[-1.6px]">
          {s.head[0]}
          <br />
          {s.head[1]}
        </h2>
        <p className="mt-2.5 text-sm sm:text-base font-medium leading-6 tracking-[-0.16px] opacity-90">{s.tag}</p>
      </div>
      <Arrow side="left" dark={dark} onClick={() => go(-1)} />
      <Arrow side="right" dark={dark} onClick={() => go(1)} />
      <span className={`absolute right-[3%] bottom-[9%] h-[25px] px-3 rounded-full ${dark ? 'bg-black/10' : 'bg-white/14'} text-xs leading-[25px] tabular-nums`}>
        {i + 1} / {slides.length}
      </span>
      {/* 다음 장 그림을 미리 받아 둔다 — 넘길 때 깜빡이지 않게 */}
      <link rel="prefetch" as="image" href={(ART[slides[(i + 1) % slides.length].key] ?? ART.all).img} />
    </section>
  )
}

function Arrow({ side, dark, onClick }: { side: 'left' | 'right'; dark: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={side === 'left' ? '이전' : '다음'}
      className={`absolute top-[127px] ${side === 'left' ? 'left-8' : 'right-8'} w-7 h-7 rounded-full ${dark ? 'bg-black/10 hover:bg-black/20' : 'bg-white/18 hover:bg-white/30'} grid place-items-center`}
    >
      <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
        <path d={side === 'left' ? 'M6.5 1.5 3 5l3.5 3.5' : 'M3.5 1.5 7 5 3.5 8.5'} />
      </svg>
    </button>
  )
}
