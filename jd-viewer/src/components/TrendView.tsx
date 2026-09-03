import { useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useTrends } from '../lib/useTrends'
import { useTechRelations } from '../lib/useTechRelations'
import { ExpansionView } from './ExpansionView'
import { RoleInsights } from './RoleInsights'
import { LearningView } from './LearningView'
import { WikiView, WikiLink } from './WikiView'
import { articleByTech, useStudyIndex } from '../lib/useStudy'
import { Loader, ErrorState, TechIcon, SearchInput, hits } from './ui'
import { navigate } from '../lib/router'
import { paths } from '../lib/urls'
import type { TechRelation, TrendDay } from '../types'
import type { IndexEntry } from '../lib/useStudy'

type TrendMode = 'trend' | 'relations' | 'learn' | 'paths' | 'wiki'

function pct(d: TrendDay, t: string): number {
  return d.total ? Math.round((1000 * (d.tech[t] ?? 0)) / d.total) / 10 : 0
}

export function TrendView({
  onOpenCompany,
  focusTech,
  wiki,
}: {
  onOpenCompany?: (norm: string) => void
  /** 주소(`/trend?tech=React`)로 지정된 기술. 있으면 학습·확장 모드로 연다. */
  focusTech?: string | null
  /** 주소가 `/wiki` 계열이면 백과사전 모드. `slug` 가 있으면 그 문서를 연다. */
  wiki?: { slug: string | null } | null
} = {}) {
  const { data, loading, error } = useTrends()
  const { data: rel } = useTechRelations()
  const { data: studyIndex } = useStudyIndex()
  const [mode, setMode] = useState<TrendMode>(wiki ? 'wiki' : 'trend')
  const [relTech, setRelTech] = useState<string | null>(null)
  const [query, setQuery] = useState('')

  // "이 기술 공부하기"로 진입하면 학습·확장 모드로 전환.
  // effect 대신 렌더 중 조정 — effect 에서 setState 하면 전환 전 모드가 한 프레임 보인다.
  const [prevFocus, setPrevFocus] = useState(focusTech)
  if (focusTech !== prevFocus) {
    setPrevFocus(focusTech)
    if (focusTech) setMode('learn')
  }

  // 주소가 백과사전(`/wiki`, `/wiki/<slug>`)이면 그 모드로. 반대로 다른 탭에서 돌아오면
  // 원래 모드로 되돌린다 — 모드가 주소와 어긋나면 뒤로가기가 엉뚱한 화면을 연다.
  const onWiki = Boolean(wiki)
  const [prevWiki, setPrevWiki] = useState(onWiki)
  if (onWiki !== prevWiki) {
    setPrevWiki(onWiki)
    setMode(onWiki ? 'wiki' : 'trend')
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

  return (
    <div className="flex flex-col flex-1 min-h-0 min-w-0">
      {/* 모드 전환 */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-(--color-border) bg-(--color-panel)/60">
        <div className="inline-flex rounded-md border border-(--color-border) overflow-hidden">
          <ModeBtn active={mode === 'trend'} onClick={() => setMode('trend')}>직군 분석</ModeBtn>
          <ModeBtn active={mode === 'relations'} onClick={() => setMode('relations')}>기술 관계·맥락</ModeBtn>
          <ModeBtn active={mode === 'learn'} onClick={() => setMode('learn')}>학습·확장</ModeBtn>
          <ModeBtn active={mode === 'paths'} onClick={() => setMode('paths')}>요구사항 → 학습</ModeBtn>
          <ModeBtn active={mode === 'wiki'} onClick={() => { setMode('wiki'); navigate(paths.wiki()) }}>백과사전</ModeBtn>
        </div>
        <span className="text-xs text-(--color-muted)">
          {mode === 'trend'
            ? '직군별 산업·경력·학력·우대사항·자격요건 한눈에'
            : mode === 'relations'
              ? '함께 쓰이는 기술(스택 레이어)과 어디서·왜 쓰이는지'
              : mode === 'learn'
                ? '기술 선택 → 함께 쓰는 기술 확장 추천 + 학습 커리큘럼'
                : mode === 'wiki'
                  ? '낱말 하나를 끝까지 — 왜 생겼나 · 언제 그것 대신 저것 · 손으로 해 볼 것'
                  : '우대사항이 요구하는 것 → 읽을 기술 블로그 글 + 돈 주고 볼 만한 강의'}
        </span>
      </div>

      {mode === 'wiki' ? (
        <WikiView slug={wiki?.slug ?? null} />
      ) : mode === 'paths' ? (
        <LearningView />
      ) : mode === 'learn' ? (
        <div className="flex flex-1 min-h-0 min-w-0">
          <ExpansionView onOpenCompany={onOpenCompany} focusTech={focusTech} />
        </div>
      ) : mode === 'trend' ? (
        <RoleInsights />
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
              <RelationDetail t={detail} wiki={articleByTech(studyIndex, detail.name)} />
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
      )}
    </div>
  )
}

function RelationDetail({ t, wiki }: { t: TechRelation; wiki: IndexEntry | null }) {
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

      {/* 관계·맥락은 '무엇과 함께 얼마나'까지다. 그 다음 줄(그래서 그게 뭔데)은 백과사전에 있다 */}
      <WikiLink entry={wiki} />

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
    <button onClick={onClick} className={`px-3 py-1 text-xs font-medium transition ${active ? 'bg-(--color-accent) text-(--color-on-accent)' : 'bg-(--color-bg) text-(--color-muted) hover:text-(--color-text)'}`}>
      {children}
    </button>
  )
}
