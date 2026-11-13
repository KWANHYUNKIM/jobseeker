import { useState } from 'react'
import { useTrends } from '../hooks/useTrends'
import { useTechRelations } from '../hooks/useTechRelations'
import { ExpansionView } from './ExpansionView'
import { RoleInsights } from './RoleInsights'
import { RelationsView } from './RelationsView'
import { useRoleInsights } from '../hooks/useRoleInsights'
import { LearningView } from './LearningView'
import { Loader, ErrorState } from '../../../components/ui'
import { SiteFooter } from '../../../components/SiteFooter'

type TrendMode = 'trend' | 'relations' | 'learn' | 'paths'

export function TrendView({
  onOpenCompany,
  focusTech,
}: {
  onOpenCompany?: (norm: string) => void
  /** 주소(`/trend?tech=React`)로 지정된 기술. 있으면 학습·확장 모드로 연다. */
  focusTech?: string | null
} = {}) {
  const { data, loading, error } = useTrends()
  const { data: rel } = useTechRelations()
  // 직군 분석의 데이터 — 머리 설명의 공고 수도 여기서 온다(트렌드 파일의 그날 수와 기준이 다르다).
  const roleInsights = useRoleInsights()
  // ?mode=relations|learn|paths 로 바로 그 보기를 연다(주소로 공유·새로고침해도 같은 보기)
  const [mode, setMode] = useState<TrendMode>(() => {
    const m = new URLSearchParams(window.location.search).get('mode')
    return m === 'relations' || m === 'learn' || m === 'paths' ? m : 'trend'
  })

  // "이 기술 공부하기"로 진입하면 학습·확장 모드로 전환.
  // effect 대신 렌더 중 조정 — effect 에서 setState 하면 전환 전 모드가 한 프레임 보인다.
  const [prevFocus, setPrevFocus] = useState(focusTech)
  if (focusTech !== prevFocus) {
    setPrevFocus(focusTech)
    if (focusTech) setMode('learn')
  }

  const latest = data?.days[data.days.length - 1]




  const total = roleInsights.data?.total_jobs
  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[43px] pb-[90px]">
        <h1 className="text-[28px] font-bold leading-10 tracking-[-0.6px] text-[#272727]">개발 트렌드</h1>
        <p className="mt-1 text-base leading-6 tracking-[-0.16px] text-[#666]">
          {mode === 'trend' ? (
            <>
              잡 리스트 <b className="font-bold text-(--color-accent)">{total ? `${total.toLocaleString()}건` : '…'}</b>을 직군으로 나눠 산업·경력·학력·기술·우대사항을
              한눈에 보여 드려요.
            </>
          ) : mode === 'relations' ? (
            '함께 쓰이는 기술(스택 레이어)과 어디서·왜 쓰이는지'
          ) : mode === 'learn' ? (
            '기술 선택 → 함께 쓰는 기술 확장 추천 + 학습 커리큘럼'
          ) : (
            '우대사항이 요구하는 것 → 읽을 기술 블로그 글 + 돈 주고 볼 만한 강의'
          )}
        </p>

        {/* 모드 전환 — 밑줄 탭 */}
        <div role="tablist" className="mt-[34px] flex overflow-x-auto no-scrollbar border-b border-[#e2e2e2]">
          {(
            [
              ['trend', '직군 분석'],
              ['relations', '기술 관계·맥락'],
              ['learn', '학습·확장'],
              ['paths', '요구사항 → 학습'],
            ] as const
          ).map(([k, label]) => (
            <ModeBtn key={k} active={mode === k} onClick={() => setMode(k)}>
              {label}
            </ModeBtn>
          ))}
        </div>

        <div className="mt-[22px]">
      {mode === 'paths' ? (
        <Framed>
          <LearningView />
        </Framed>
      ) : mode === 'learn' ? (
        <Framed>
          <ExpansionView onOpenCompany={onOpenCompany} focusTech={focusTech} />
        </Framed>
      ) : mode === 'trend' ? (
        <RoleInsights data={roleInsights.data} loading={roleInsights.loading} error={roleInsights.error} />
      ) : loading ? (
        <Loader label="개발 트렌드 불러오는 중…" />
      ) : error ? (
        <ErrorState
          title="trends.json 로드 실패"
          detail={error}
          hint={
            <>
              생성: <code className="text-(--color-text)">python bin/build_trends.py</code> (jd-viewer)
            </>
          }
        />
      ) : !data || !latest ? (
        <div className="p-8 text-(--color-muted)">트렌드 데이터가 없습니다.</div>
      ) : (
        <RelationsView data={data} rel={rel} />
      )}
        </div>
      </div>
      <SiteFooter updated={data?.generated_at} />
    </div>
  )
}

/** 직군 분석 밖의 세 보기는 안쪽에서 스크롤하는 두 칸짜리라 높이를 정한 카드에 담는다. */
function Framed({ children }: { children: React.ReactNode }) {
  return <div className="relative flex h-[780px] rounded-[30px] border border-[#e2e8ec] overflow-hidden">{children}</div>
}

function ModeBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={
        'relative shrink-0 px-[22px] pb-[13px] text-[17px] leading-[25px] tracking-[-0.16px] ' +
        (active
          ? 'font-bold text-(--color-accent) after:absolute after:inset-x-0 after:-bottom-px after:h-[3px] after:bg-(--color-accent)'
          : 'font-medium text-[#777] hover:text-[#272727]')
      }
    >
      {children}
    </button>
  )
}
