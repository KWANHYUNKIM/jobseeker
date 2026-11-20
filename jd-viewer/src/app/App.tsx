import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useJobBoardContext } from '../features/jobs/hooks/useJobBoard'
import { navigate, onLinkClick, useRoute } from '../utils/navigation'
import { paths } from '../utils/urls'
import { Providers } from './providers'
import { RouteView, tabOf, type Tab } from './router'
import { BrandLogo } from '../components/BrandLogo'

/** 앱 껍데기 — 위쪽 메뉴(두 단)와, 주소에 맞는 페이지(app/router.tsx). */
function App() {
  return (
    <Providers>
      <div className="flex flex-col h-screen">
        <TopNav />
        <RouteView />
      </div>
    </Providers>
  )
}

/**
 * 메뉴는 두 단이다(Penpot「JD Viewer」캐치형) — 위 막대는 묶음(채용공고·기업정보·커리어·
 * 학습·외주·프리·PC 하드웨어), 아래 막대는 지금 묶음 안의 화면들. 탭(Tab)과 주소는 그대로다.
 */
type Item = { tab: Tab; label: string; to: () => string; also?: Tab[] }
const GROUPS: { label: string; items: Item[] }[] = [
  {
    label: '채용공고',
    items: [
      { tab: 'home', label: '기업별 채용', to: paths.home, also: ['top'] },
      { tab: 'jobs', label: '잡 리스트', to: paths.jobs },
      { tab: 'calendar', label: '모집 캘린더', to: paths.calendar },
      { tab: 'reposts', label: '재공고', to: paths.reposts },
    ],
  },
  {
    label: '기업정보',
    items: [
      { tab: 'companies', label: '기업 기술스택', to: paths.companies },
      { tab: 'radar', label: '기술 레이더', to: paths.radar },
      { tab: 'reveng', label: '기술 역설계', to: paths.reveng },
      { tab: 'lectures', label: '강의 노트', to: paths.lectures },
    ],
  },
  {
    label: '커리어',
    items: [
      { tab: 'mindmap', label: '커리어 마인드맵', to: paths.mindmap },
      { tab: 'trend', label: '개발 트렌드', to: () => paths.trend() },
    ],
  },
  {
    label: '학습',
    items: [
      { tab: 'blog', label: '기술 블로그', to: paths.blog },
      { tab: 'book', label: '기술도서', to: paths.wiki },
    ],
  },
  {
    label: '외주·프리',
    items: [
      { tab: 'freelance', label: '외주·프리', to: paths.freelance },
      { tab: 'alba', label: 'IT 알바', to: paths.alba },
    ],
  },
  { label: 'PC 하드웨어', items: [{ tab: 'hardware', label: 'PC 하드웨어', to: paths.hardware }] },
]

const isOn = (it: Item, tab: Tab) => it.tab === tab || !!it.also?.includes(tab)

function TopNav() {
  const tab = tabOf(useRoute())
  const { countsReady, totalCount, filteredCount, filter, setFilter } = useJobBoardContext()
  const group = GROUPS.find((g) => g.items.some((it) => isOn(it, tab))) ?? GROUPS[0]
  const [menu, setMenu] = useState(false)
  const [q, setQ] = useState(filter.query)
  // 잡 리스트 안에서 검색어가 바뀌면 머리의 검색칸도 따라간다.
  useEffect(() => setQ(filter.query), [filter.query])

  // 머리의 검색은 잡 리스트 검색이다 — 검색어를 걸고 잡 리스트로 간다.
  const onSearch = (e: FormEvent) => {
    e.preventDefault()
    const v = q.trim()
    setFilter((f) => ({ ...f, query: v }))
    navigate(paths.jobs() + (v ? `?q=${encodeURIComponent(v)}` : ''))
  }

  return (
    <header className="sticky top-0 z-30 bg-white">
      <nav className="relative z-10 h-[70px] border-b border-[#dcdcdc] shadow-[0_2px_8px_rgba(0,0,0,0.06)]">
        <div className="jd-container h-full flex items-center gap-5 lg:gap-0">
          <a
            href="/"
            onClick={onLinkClick('/')}
            aria-label="devgonggo 홈"
            className="flex items-center shrink-0 select-none"
          >
            <BrandLogo />
          </a>
          <button
            type="button"
            aria-label="전체 메뉴"
            aria-expanded={menu}
            onClick={() => setMenu((v) => !v)}
            className="shrink-0 lg:ml-[29px] w-[18px] h-[14px] flex flex-col justify-between"
          >
            <span className="block h-[2px] w-[18px] bg-[#272727]" />
            <span className="block h-[2px] w-[18px] bg-[#272727]" />
            <span className="block h-[2px] w-[13px] bg-[#272727]" />
          </button>
          <div className="hidden md:flex items-center gap-[39px] lg:ml-[34px] min-w-0 overflow-x-auto no-scrollbar">
            {GROUPS.map((g) => (
              <a
                key={g.label}
                href={g.items[0].to()}
                onClick={onLinkClick(g.items[0].to())}
                className={`shrink-0 whitespace-nowrap text-base font-medium leading-6 transition ${
                  g === group ? 'text-(--color-accent)' : 'text-[#272727] hover:text-(--color-accent)'
                }`}
              >
                {g.label}
              </a>
            ))}
          </div>
          <form
            onSubmit={onSearch}
            className="hidden xl:flex ml-auto shrink-0 items-center w-[220px] h-[30px] rounded-full border border-[#474747] pl-[15px] pr-[10px]"
          >
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="회사·직무·기술 검색"
              aria-label="회사·직무·기술 검색"
              className="flex-1 min-w-0 bg-transparent text-xs text-[#272727] placeholder:text-[#999] outline-none"
            />
            <button type="submit" aria-label="검색" className="shrink-0">
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="#272727" strokeWidth="2">
                <circle cx="8.5" cy="8.5" r="5.5" />
                <path d="M12.5 12.5 16 16" strokeLinecap="round" />
              </svg>
            </button>
          </form>
          {/* 첫 응답 전에는 0 이 아니라 '…' — 0건은 "공고가 없다" 로 읽힌다. */}
          <span className="hidden sm:inline-flex ml-auto xl:ml-[10px] shrink-0 items-center h-[30px] px-[13px] rounded-2xl border border-[#272727] text-[13px] text-[#272727] tabular-nums whitespace-nowrap">
            공고 {countsReady ? totalCount.toLocaleString() : '…'}건
          </span>
          <span className="ml-auto sm:ml-[9px] shrink-0 inline-flex items-center h-[30px] px-[13px] rounded-2xl bg-(--color-navy) border border-(--color-navy) text-[13px] text-white tabular-nums whitespace-nowrap">
            필터 {countsReady ? filteredCount.toLocaleString() : '…'}건
          </span>
        </div>
        {menu && <AllMenu tab={tab} onClose={() => setMenu(false)} />}
      </nav>
      <div className="h-12 border-b border-[#eeeeee] bg-white">
        <div className="jd-container h-full flex items-center overflow-x-auto no-scrollbar">
          {/* 아래 막대는 햄버거 오른쪽 줄에서 시작한다(디자인의 x=490). */}
          <div className="flex items-center lg:ml-[158px]">
            {group.items.map((it, i) => (
              <span key={it.tab} className="flex items-center shrink-0">
                {i > 0 && <span aria-hidden className="mx-[12px] w-[3px] h-[3px] rounded-full bg-[#c4c4c4]" />}
                <SubLink active={isOn(it, tab)} to={it.to()}>
                  {it.label}
                </SubLink>
              </span>
            ))}
          </div>
        </div>
      </div>
    </header>
  )
}

/** 햄버거를 누르면 펼쳐지는 전체 메뉴 — 묶음별로 모든 화면을 한 번에 보인다(좁은 화면의 메뉴이기도 하다). */
function AllMenu({ tab, onClose }: { tab: Tab; onClose: () => void }) {
  return (
    <div className="absolute inset-x-0 top-full z-40 border-b border-[#dcdcdc] bg-white shadow-[0_8px_16px_rgba(0,0,0,0.06)]">
      <div className="jd-container grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-6 py-6">
        {GROUPS.map((g) => (
          <div key={g.label}>
            <div className="text-[15px] font-bold text-[#272727] mb-2">{g.label}</div>
            <ul className="space-y-1.5">
              {g.items.map((it) => (
                <li key={it.tab}>
                  <a
                    href={it.to()}
                    onClick={(e) => {
                      onClose()
                      onLinkClick(it.to())(e)
                    }}
                    className={`text-sm ${isOn(it, tab) ? 'text-(--color-accent) font-medium' : 'text-[#666] hover:text-[#272727]'}`}
                  >
                    {it.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}

// 메뉴는 진짜 링크다. 크롤러는 onClick 을 따라가지 않는다 — href 가 있어야 다음 페이지를 본다.
function SubLink({ active, to, children }: { active: boolean; to: string; children: ReactNode }) {
  return (
    <a
      href={to}
      onClick={onLinkClick(to)}
      className={`whitespace-nowrap text-sm font-medium leading-[21px] transition ${
        active ? 'text-(--color-accent)' : 'text-[#666] hover:text-[#272727]'
      }`}
    >
      {children}
    </a>
  )
}

export default App
