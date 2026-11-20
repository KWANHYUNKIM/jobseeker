import { useCallback, useState, type ReactNode } from 'react'
import { SiteFooter } from '../../../components/SiteFooter'
import { DomainMap, type MindmapSummary } from './DomainMap'
import { TreeView } from './TreeView'
import { PathwayView } from './PathwayView'

type View = 'cluster' | 'tree' | 'pathway'

/**
 * 커리어 마인드맵(캐치형 04) — 제목·설명, 보기 단추 셋(클러스터·트리·이동 경로), 회사 검색.
 * 클러스터는 사업 도메인 원 그림(DomainMap), 트리는 도메인 → 회사 → 직군(TreeView), 이동 경로는 JD 군집(PathwayView).
 */
export function CareerMap() {
  // ?view=tree|pathway 로 바로 그 보기를 연다(주소로 공유·새로고침해도 같은 보기)
  const [view, setView] = useState<View>(() => {
    const v = new URLSearchParams(window.location.search).get('view')
    return v === 'tree' || v === 'pathway' ? v : 'cluster'
  })
  const [query, setQuery] = useState('')
  const [sum, setSum] = useState<MindmapSummary | null>(null)
  const onSummary = useCallback((s: MindmapSummary) => setSum(s), [])

  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[47px] pb-[240px]">
        <h1 className="text-[28px] font-bold leading-10 tracking-[-0.6px] text-[#272727]">커리어 마인드맵</h1>
        <p className="mt-1 text-base leading-6 tracking-[-0.16px] text-[#666]">
          {view === 'tree' ? (
            '누가 어떤 직군을 뽑고 있는지 — 도메인 → 회사 → 직군 순서로 펼쳐 보세요.'
          ) : view === 'pathway' ? (
            '공고 내용 임베딩 군집 — 지금 자리에서 어디로 갈 수 있고, 가려면 무엇이 비는지 보여 드려요.'
          ) : (
            <>
              누가 어떤 직군을 뽑고 있는지 — 채용 기업{' '}
              <b className="font-bold text-(--color-accent)">{sum ? `${sum.companies.toLocaleString()}곳` : '…'}</b>을 사업 도메인{' '}
              {sum?.domains ?? '…'}개로 묶었어요. 공고 {sum ? sum.jobs.toLocaleString() : '…'}건 기준
            </>
          )}
        </p>

        <div className="mt-[23px] flex flex-wrap items-center gap-2">
          <ViewButton on={view === 'cluster'} onClick={() => setView('cluster')}>
            ◉ 클러스터
          </ViewButton>
          <ViewButton on={view === 'tree'} onClick={() => setView('tree')}>
            ⊟ 트리
          </ViewButton>
          <ViewButton on={view === 'pathway'} onClick={() => setView('pathway')}>
            ⇄ 이동 경로
          </ViewButton>
          <label className="ml-auto flex items-center gap-2 w-full sm:w-[280px] h-10 rounded-[20px] border border-[#c4c4c4] pl-[17px] pr-4 focus-within:border-[#272727]">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="#272727" strokeWidth="2" aria-hidden className="shrink-0">
              <circle cx="8.5" cy="8.5" r="5.5" />
              <path d="M12.5 12.5 16 16" strokeLinecap="round" />
            </svg>
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="회사 검색"
              aria-label="회사 검색"
              className="flex-1 min-w-0 bg-transparent text-sm tracking-[-0.16px] text-[#272727] placeholder:text-[#999] outline-none"
            />
        </label>
        </div>

        <div className="mt-[22px]">
          {view === 'cluster' ? (
            <DomainMap query={query} onSummary={onSummary} />
          ) : view === 'tree' ? (
            <TreeView query={query} />
          ) : (
            <PathwayView query={query} />
          )}
        </div>
      </div>
      <SiteFooter jobs={sum?.jobs} companies={sum?.companies} />
    </div>
  )
}

function ViewButton({ on, onClick, children }: { on: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      className={
        'h-9 px-[17px] rounded-[18px] border text-sm font-medium tracking-[-0.3px] ' +
        (on ? 'bg-(--color-accent) border-(--color-accent) text-white' : 'bg-white border-[#d8d8d8] text-[#272727] hover:border-[#272727]')
      }
    >
      {children}
    </button>
  )
}
