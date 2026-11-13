import { useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useTrends } from '../hooks/useTrends'
import { useTechRelations } from '../hooks/useTechRelations'
import { ExpansionView } from './ExpansionView'
import { RoleInsights } from './RoleInsights'
import { useRoleInsights } from '../hooks/useRoleInsights'
import { LearningView } from './LearningView'
import { Loader, ErrorState, TechIcon, SearchInput, hits } from '../../../components/ui'
import { SiteFooter } from '../../../components/SiteFooter'
import type { TechRelation, TrendDay } from '../../../types'

type TrendMode = 'trend' | 'relations' | 'learn' | 'paths'

function pct(d: TrendDay, t: string): number {
  return d.total ? Math.round((1000 * (d.tech[t] ?? 0)) / d.total) / 10 : 0
}

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
  const [mode, setMode] = useState<TrendMode>('trend')
  const [relTech, setRelTech] = useState<string | null>(null)
  const [query, setQuery] = useState('')

  // "이 기술 공부하기"로 진입하면 학습·확장 모드로 전환.
  // effect 대신 렌더 중 조정 — effect 에서 setState 하면 전환 전 모드가 한 프레임 보인다.
  const [prevFocus, setPrevFocus] = useState(focusTech)
  if (focusTech !== prevFocus) {
    setPrevFocus(focusTech)
    if (focusTech) setMode('learn')
  }

  const latest = data?.days[data.days.length - 1]
  const ranking = useMemo(() => {
    if (!latest) return []
    return (data?.tracked ?? [])
      .map((t) => ({ tech: t, count: latest.tech[t] ?? 0, pct: pct(latest, t) }))
      .sort((a, b) => b.count - a.count)
      .map((r, i) => ({ ...r, rank: i + 1 }))
  }, [data, latest])

  // 순위표는 28위에서 자른다. 그런데 검색은 대개 **잘려 나간 아래쪽**을 찾는 일이라
  // (내가 쓰는 기술이 몇 위인가), 검색어가 있으면 자르지 않는다. 순위 번호는
  // 자르기 전 순위를 그대로 들고 다녀서 '43위' 처럼 제자리 숫자가 보인다.
  const rankShown = useMemo(() => {
    const found = ranking.filter((r) => hits(query, r.tech))
    return query.trim() ? found : found.slice(0, 28)
  }, [ranking, query])

  const relByName = useMemo(() => {
    const m = new Map<string, TechRelation>()
    for (const t of rel?.techs ?? []) m.set(t.name, t)
    return m
  }, [rel])

  const maxPct = Math.max(...ranking.map((r) => r.pct), 1)
  const activeTech = relTech ?? ranking[0]?.tech
  const detail = activeTech ? relByName.get(activeTech) : undefined

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
        <Framed>
        <div className="flex flex-col md:flex-row flex-1 min-h-0 overflow-y-auto md:overflow-hidden">
          {/* 좌: 현재 수요 순위 */}
          <aside className="w-full md:w-80 shrink-0 md:overflow-auto border-b md:border-b-0 md:border-r border-(--color-border) bg-(--color-panel) p-4">
            <h3 className="text-sm font-semibold text-(--color-text)">현재 기술 수요</h3>
            <p className="text-xs text-(--color-muted) mb-2">
              {latest.date} · 공고 {latest.total.toLocaleString()}건 중 언급 비중. 클릭=관계·맥락 보기
            </p>
            <SearchInput value={query} onChange={setQuery} placeholder="기술 검색" className="mb-2" />
            {query && (
              <p className="text-[11px] text-(--color-muted) mb-2">
                추적 {ranking.length}개 중 <b className="text-(--color-text)">{rankShown.length}개</b>
              </p>
            )}
            <ul className="flex flex-col gap-1">
              {rankShown.map((r) => {
                const on = r.tech === activeTech
                return (
                  <li key={r.tech}>
                    <button
                      onClick={() => setRelTech(r.tech)}
                      className={`w-full flex items-center gap-2 px-2 py-1 rounded text-left ${on ? 'bg-(--color-accent)/15' : 'hover:bg-(--color-bg)'}`}
                    >
                      <span className="w-5 text-xs text-(--color-muted) tabular-nums">{r.rank}</span>
                      <TechIcon tech={r.tech} size={14} />
                      <span className="w-28 text-sm text-(--color-text) truncate">{r.tech}</span>
                      <span className="flex-1 h-1.5 rounded bg-(--color-bg) overflow-hidden">
                        <span className="block h-full bg-(--color-accent)" style={{ width: `${(r.pct / maxPct) * 100}%` }} />
                      </span>
                      <span className="w-10 text-right text-xs text-(--color-muted) tabular-nums">{r.pct}%</span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </aside>

          {/* 우: 관계·맥락 */}
          <main className="flex-1 min-w-0 md:overflow-auto p-4 sm:p-5 flex flex-col gap-5">
            {detail ? (
              <RelationDetail t={detail} />
            ) : (
              <p className="text-(--color-muted)">관계 데이터를 불러오는 중…</p>
            )}
            {rel?.domains && rel.domains.length > 0 && (
              <div>
                <h2 className="text-lg font-semibold text-(--color-text) mb-1">도메인별 인사이트</h2>
                <p className="text-xs text-(--color-muted) mb-3">어떤 산업·도메인에서 어떤 기술을 왜 쓰는지</p>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                  {rel.domains.map((d) => (
                    <div key={d.domain} className="rounded border border-(--color-border) bg-(--color-bg) p-3">
                      <div className="text-sm font-semibold text-(--color-text) mb-1">{d.domain}</div>
                      <div className="flex flex-wrap gap-1 mb-2">
                        {d.techs.map((t) => (
                          <span key={t} className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[11px] rounded bg-(--color-accent)/15 text-(--color-accent)">
                            <TechIcon tech={t} size={12} />
                            {t}
                          </span>
                        ))}
                      </div>
                      <div className="blog-md text-sm text-(--color-text)">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{d.why}</ReactMarkdown>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </main>
        </div>
        </Framed>
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

function RelationDetail({ t }: { t: TechRelation }) {
  // 함께 쓰는 기술을 레이어별로 묶기
  const byLayer = useMemo(() => {
    const m = new Map<string, typeof t.related>()
    for (const r of t.related) {
      if (!m.has(r.layer)) m.set(r.layer, [])
      m.get(r.layer)!.push(r)
    }
    return [...m.entries()]
  }, [t])

  return (
    <div>
      <div className="flex items-baseline gap-2 flex-wrap">
        <h2 className="text-xl font-semibold text-(--color-text)">{t.name}</h2>
        <span className="text-xs px-1.5 py-0.5 rounded bg-(--color-bg) border border-(--color-border) text-(--color-muted)">{t.layer}</span>
        <span className="text-xs text-(--color-muted)">전체 공고의 {t.pct_jobs}% · {t.count.toLocaleString()}건</span>
      </div>

      {t.context && (
        <div className="blog-md mt-2 text-sm text-(--color-text)">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{t.context}</ReactMarkdown>
        </div>
      )}

      <div className="mt-4">
        <div className="text-xs font-medium text-(--color-muted) mb-2">함께 쓰이는 기술 (스택 레이어별 · {t.name} 공고 중 비율)</div>
        <div className="flex flex-col gap-2">
          {byLayer.map(([layer, items]) => (
            <div key={layer} className="flex gap-3">
              <div className="w-24 shrink-0 text-xs text-(--color-muted) pt-1">{layer}</div>
              <div className="flex flex-wrap gap-1.5">
                {items.map((r) => (
                  <span key={r.name} className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded border border-(--color-border) bg-(--color-bg) text-(--color-text)">
                    {r.name}<span className="text-(--color-muted)">{r.pct}%</span>
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
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
