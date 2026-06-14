import { useEffect, useMemo, useState } from 'react'
import { useCompanies } from '../lib/useCompanies'
import {
  useLearning,
  type LearningVideo,
  type LearningStage,
  type Curriculum,
} from '../lib/useLearning'
import {
  buildExpansionIndex,
  CAT_ORDER,
  CAT_COLOR,
  type TechNode,
} from '../lib/expansion'
import { Loader, ErrorState, EmptyState, SidePanel, MobileBar } from './ui'

const SIZE_COLOR: Record<string, string> = {
  대기업: '#f472b6',
  중견기업: '#fbbf24',
  중소기업: '#60a5fa',
}

const COMPANY_LIMIT = 60
const COOC_LIMIT = 14

export function ExpansionView({
  onOpenCompany,
  focusTech,
}: {
  onOpenCompany?: (norm: string) => void
  focusTech?: { tech: string; n: number } | null
}) {
  const { companies, loading, error } = useCompanies()
  const learning = useLearning()
  const [query, setQuery] = useState('')
  const [selectedTech, setSelectedTech] = useState<string | null>(null)
  const [navOpen, setNavOpen] = useState(false)

  // 다른 탭(회사 뷰)에서 "이 기술 공부하기"로 들어오면 해당 기술을 선택.
  useEffect(() => {
    if (focusTech?.tech) setSelectedTech(focusTech.tech)
  }, [focusTech])

  const index = useMemo(() => buildExpansionIndex(companies), [companies])

  const tech = useMemo(() => {
    if (selectedTech && index.categoryOf[selectedTech]) return selectedTech
    return index.techs[0]?.name ?? null
  }, [selectedTech, index])

  if (loading) return <Loader label="기술스택 데이터 불러오는 중…" />
  if (error)
    return (
      <ErrorState
        title="company_stacks.json 로드 실패"
        detail={error}
        hint={<>생성: <code className="text-(--color-text)">python3 jd-viewer/bin/build_company_stacks.py</code></>}
      />
    )

  return (
    <div className="flex flex-1 min-h-0 min-w-0">
      <TechSidebar
        index={index}
        query={query}
        setQuery={setQuery}
        selected={tech}
        onSelect={(t) => {
          setSelectedTech(t)
          setNavOpen(false)
        }}
        open={navOpen}
        onClose={() => setNavOpen(false)}
      />
      <main className="flex-1 min-w-0 overflow-auto">
        <MobileBar onMenu={() => setNavOpen(true)} label="기술 목록">
          {tech && <span className="ml-auto text-xs text-(--color-text) truncate">{tech}</span>}
        </MobileBar>
        {tech ? (
          <TechPanel
            tech={tech}
            index={index}
            videos={learning.resources[tech] ?? []}
            curriculum={learning.curricula[tech] ?? null}
            searchUrl={learning.searchUrl}
            learningLoading={learning.loading}
            onSelectTech={setSelectedTech}
            onOpenCompany={onOpenCompany}
          />
        ) : (
          <EmptyState title="기술을 선택하세요" hint="좌측에서 기술을 고르면 함께 쓰는 스택·학습 경로가 표시됩니다." />
        )}
      </main>
    </div>
  )
}

function TechSidebar({
  index,
  query,
  setQuery,
  selected,
  onSelect,
  open,
  onClose,
}: {
  index: ReturnType<typeof buildExpansionIndex>
  query: string
  setQuery: (v: string) => void
  selected: string | null
  onSelect: (t: string) => void
  open: boolean
  onClose: () => void
}) {
  const q = query.trim().toLowerCase()
  const cats = CAT_ORDER.filter((c) => index.byCategory[c]?.length)

  return (
    <SidePanel side="left" desktopWidth="md:w-64" open={open} onClose={onClose}>
      <div className="p-3 border-b border-(--color-border)">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="기술 검색 (예: React)"
          className="w-full bg-(--color-bg) border border-(--color-border) rounded px-3 py-1.5 text-sm text-(--color-text) placeholder:text-(--color-muted) focus:border-(--color-accent) outline-none"
        />
        <div className="text-[11px] text-(--color-muted) mt-2">
          {index.techs.length}개 기술 · {index.totalCompanies}개 회사
        </div>
      </div>
      <div className="overflow-auto flex-1 py-1">
        {cats.map((cat) => {
          const items = index.byCategory[cat].filter((t) => !q || t.name.toLowerCase().includes(q))
          if (!items.length) return null
          return (
            <div key={cat} className="mb-1">
              <div
                className="px-3 pt-2 pb-1 text-[10px] uppercase tracking-wider font-semibold"
                style={{ color: CAT_COLOR[cat] }}
              >
                {cat}
              </div>
              {items.map((t) => {
                const active = t.name === selected
                return (
                  <button
                    key={t.name}
                    onClick={() => onSelect(t.name)}
                    className={`w-full text-left px-3 py-1.5 flex items-center gap-2 transition ${
                      active ? 'bg-(--color-accent)/15' : 'hover:bg-white/5'
                    }`}
                  >
                    <span className="text-[13px] text-(--color-text) truncate">{t.name}</span>
                    <span className="ml-auto text-[11px] text-(--color-muted) shrink-0">{t.companyCount}</span>
                  </button>
                )
              })}
            </div>
          )
        })}
      </div>
    </SidePanel>
  )
}

function TechPanel({
  tech,
  index,
  videos,
  curriculum,
  searchUrl,
  learningLoading,
  onSelectTech,
  onOpenCompany,
}: {
  tech: string
  index: ReturnType<typeof buildExpansionIndex>
  videos: LearningVideo[]
  curriculum: Curriculum | null
  searchUrl: string
  learningLoading: boolean
  onSelectTech: (t: string) => void
  onOpenCompany?: (norm: string) => void
}) {
  const cat = index.categoryOf[tech] ?? '기타'
  const color = CAT_COLOR[cat] ?? '#6b7280'
  const node = index.techs.find((t) => t.name === tech) as TechNode | undefined
  const companies = index.companiesByTech[tech] ?? []
  const cooc = (index.coocByTech[tech] ?? []).slice(0, COOC_LIMIT)
  const maxConf = Math.max(0.0001, ...cooc.map((c) => c.confidence))
  const shown = companies.slice(0, COMPANY_LIMIT)

  return (
    <div className="p-6 max-w-5xl">
      {/* 헤더 */}
      <div className="flex items-center flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-(--color-text)">{tech}</h1>
        <span
          className="text-xs px-2 py-0.5 rounded-full"
          style={{ background: color + '22', color }}
        >
          {cat}
        </span>
        <span className="text-xs text-(--color-muted)">
          {node?.companyCount ?? 0}개 회사 · 공고 {node?.postingCount ?? 0}건
        </span>
      </div>

      {/* 확장 추천 */}
      <Section
        title="함께 자주 쓰는 기술 (확장 추천)"
        hint="이 기술을 쓰는 회사에서 유난히 자주 함께 등장하는 기술 — 다음 학습 후보"
      >
        {cooc.length ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {cooc.map((c) => {
              const cc = CAT_COLOR[c.category] ?? '#6b7280'
              return (
                <button
                  key={c.name}
                  onClick={() => onSelectTech(c.name)}
                  className="text-left bg-(--color-panel) border border-(--color-border) rounded-lg p-2.5 hover:border-(--color-accent)/60 transition"
                >
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ background: cc }} />
                    <span className="text-sm text-(--color-text) font-medium truncate">{c.name}</span>
                    <span className="ml-auto text-[11px] text-(--color-muted) shrink-0">{c.coCount}곳</span>
                  </div>
                  <div className="mt-1.5 h-1.5 bg-(--color-bg) rounded overflow-hidden">
                    <div
                      className="h-full rounded"
                      style={{ width: `${(c.confidence / maxConf) * 100}%`, background: cc }}
                    />
                  </div>
                  <div className="text-[10px] text-(--color-muted) mt-1">
                    동반율 {(c.confidence * 100).toFixed(0)}% · 연관도 {c.lift.toFixed(1)}x
                  </div>
                </button>
              )
            })}
          </div>
        ) : (
          <span className="text-sm text-(--color-muted)">동시출현 데이터가 충분하지 않습니다.</span>
        )}
      </Section>

      {/* 세부 주제 커리큘럼 — 무엇을 어떤 순서로 공부할지 */}
      {curriculum && (
        <Section
          title={`${tech} 학습 커리큘럼`}
          hint="이 기술에서 꼭 짚어야 할 주제를 공부 순서대로 — 각 주제별 추천 강의"
        >
          <div className="text-[12px] text-(--color-text) leading-relaxed bg-(--color-accent)/8 border border-(--color-accent)/30 rounded-lg px-3 py-2.5 mb-4">
            <span className="font-semibold text-(--color-accent)">이렇게 공부하세요 </span>
            {curriculum.guide}
          </div>
          <ol className="space-y-4">
            {curriculum.topics.map((t, i) => (
              <li key={t.topic} className="relative pl-7">
                <span className="absolute left-0 top-0 flex items-center justify-center w-5 h-5 rounded-full bg-(--color-accent) text-black text-[11px] font-bold">
                  {i + 1}
                </span>
                <div className="flex items-baseline flex-wrap gap-x-2">
                  <span className="text-sm font-semibold text-(--color-text)">{t.topic}</span>
                  <span className="text-[11px] text-(--color-muted)">{t.note}</span>
                </div>
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 mt-2">
                  {t.videos.map((v) => (
                    <VideoCard key={v.url} v={v} accent="#a78bfa" showStage={false} />
                  ))}
                </div>
              </li>
            ))}
          </ol>
        </Section>
      )}

      {/* 추천 학습 경로 (YouTube) — 단계별 폭넓은 추천 */}
      <Section
        title={curriculum ? `${tech} 그 외 추천 강의` : `${tech} 학습 로드맵`}
        hint="유튜브 강의를 단계로 나눈 경로 — 위에서부터 순서대로 보면 됩니다"
      >
        {learningLoading ? (
          <span className="text-sm text-(--color-muted)">학습 영상 로딩 중…</span>
        ) : videos.length ? (
          <>
            <PathGuide videos={videos} />
            <div className="space-y-5 mt-3">
              {STAGES.map((st) => {
                const items = videos.filter((v) => v.stage === st.key)
                if (!items.length) return null
                return (
                  <div key={st.key}>
                    <div className="flex items-baseline gap-2 mb-2">
                      <span
                        className="text-xs font-bold px-2 py-0.5 rounded-full"
                        style={{ background: st.color + '22', color: st.color }}
                      >
                        {st.key}
                      </span>
                      <span className="text-[11px] text-(--color-muted)">{st.desc}</span>
                    </div>
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                      {items.map((v) => (
                        <VideoCard key={v.url} v={v} accent={st.color} />
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
            {searchUrl && (
              <a
                href={searchUrl.replace('{tech}', encodeURIComponent(tech))}
                target="_blank"
                rel="noreferrer"
                className="inline-block text-[11px] text-(--color-accent) hover:underline mt-3"
              >
                유튜브에서 ‘{tech} 강의’ 더 보기 →
              </a>
            )}
          </>
        ) : (
          <div className="text-sm text-(--color-muted)">
            수집된 학습 영상이 없습니다.
            {searchUrl && (
              <>
                {' '}
                <a
                  href={searchUrl.replace('{tech}', encodeURIComponent(tech))}
                  target="_blank"
                  rel="noreferrer"
                  className="text-(--color-accent) hover:underline"
                >
                  유튜브에서 직접 검색 →
                </a>
              </>
            )}
          </div>
        )}
      </Section>

      {/* 이 기술을 쓰는 회사 */}
      <Section title={`이 기술을 쓰는 회사 (${companies.length}곳)`}>
        {shown.length ? (
          <>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-1.5">
              {shown.map((c) => {
                const sc = SIZE_COLOR[c.size] ?? '#60a5fa'
                return (
                  <button
                    key={c.norm}
                    onClick={() => onOpenCompany?.(c.norm)}
                    className="text-left bg-(--color-panel) border border-(--color-border) rounded-md px-2.5 py-1.5 hover:border-(--color-accent)/60 transition"
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="text-[13px] text-(--color-text) truncate">{c.name}</span>
                      <span
                        className="text-[9px] px-1 py-0.5 rounded-full shrink-0"
                        style={{ background: sc + '22', color: sc }}
                      >
                        {c.size}
                      </span>
                      <span className="ml-auto text-[10px] text-(--color-muted) shrink-0">{c.count}건</span>
                    </div>
                    {c.domains[0] && (
                      <div className="text-[10px] text-(--color-muted) truncate mt-0.5">{c.domains[0]}</div>
                    )}
                  </button>
                )
              })}
            </div>
            {companies.length > COMPANY_LIMIT && (
              <div className="text-[11px] text-(--color-muted) mt-2">
                외 {companies.length - COMPANY_LIMIT}개 회사 (공고 많은 순 상위 {COMPANY_LIMIT}개 표시)
              </div>
            )}
          </>
        ) : (
          <span className="text-sm text-(--color-muted)">해당 기술을 쓰는 회사가 없습니다.</span>
        )}
      </Section>
    </div>
  )
}

const STAGES: { key: LearningStage; color: string; desc: string }[] = [
  { key: '입문', color: '#34d399', desc: '왜 쓰는지·개념부터 — 여기서 출발' },
  { key: '핵심', color: '#60a5fa', desc: '문법·핵심 기능을 손에 익히기' },
  { key: '실전', color: '#fb923c', desc: '프로젝트·실무·배포로 마무리' },
]

// 보유한 단계로 "이렇게 공부하세요" 방향성 한 줄 생성
function PathGuide({ videos }: { videos: LearningVideo[] }) {
  const present = STAGES.filter((s) => videos.some((v) => v.stage === s.key))
  if (!present.length) return null
  return (
    <div className="text-xs text-(--color-text) bg-(--color-panel) border border-(--color-border) rounded-lg px-3 py-2">
      <span className="text-(--color-muted)">추천 순서 </span>
      {present.map((s, i) => (
        <span key={s.key}>
          <span className="font-semibold" style={{ color: s.color }}>
            {s.key}
          </span>
          {i < present.length - 1 && <span className="text-(--color-muted)"> → </span>}
        </span>
      ))}
      <span className="text-(--color-muted)"> 순으로, 위에서부터 보면 됩니다.</span>
    </div>
  )
}

function VideoCard({
  v,
  accent,
  showStage = true,
}: {
  v: LearningVideo
  accent: string
  showStage?: boolean
}) {
  return (
    <a
      href={v.url}
      target="_blank"
      rel="noreferrer"
      className="group bg-(--color-panel) border border-(--color-border) rounded-lg overflow-hidden hover:border-(--color-accent)/60 transition"
    >
      <div className="relative aspect-video bg-(--color-bg)">
        <img src={v.thumbnail} alt="" loading="lazy" className="w-full h-full object-cover" />
        {showStage && (
          <span
            className="absolute top-1 left-1 text-[10px] font-bold px-1.5 py-0.5 rounded"
            style={{ background: accent, color: '#0b0b0b' }}
          >
            {v.stage}
          </span>
        )}
        {v.length && (
          <span className="absolute bottom-1 right-1 text-[10px] px-1 py-0.5 rounded bg-black/80 text-(--color-text)">
            {v.length}
          </span>
        )}
      </div>
      <div className="p-2.5">
        <div className="text-[13px] text-(--color-text) font-medium leading-snug line-clamp-2 group-hover:text-(--color-accent)">
          {v.title}
        </div>
        <div className="text-[11px] text-(--color-muted) mt-1.5 truncate">{v.channel}</div>
        <div className="text-[10px] text-(--color-muted) mt-0.5">
          {formatViews(v.views)}
          {v.published && ` · ${v.published}`}
        </div>
      </div>
    </a>
  )
}

function formatViews(n: number): string {
  if (!n) return '조회수 —'
  if (n >= 10000) return `조회수 ${(n / 10000).toFixed(1).replace(/\.0$/, '')}만회`
  return `조회수 ${n.toLocaleString()}회`
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="mt-6">
      <h2 className="text-sm font-semibold text-(--color-text)">{title}</h2>
      {hint && <p className="text-[11px] text-(--color-muted) mb-2 mt-0.5">{hint}</p>}
      {!hint && <div className="mb-2" />}
      {children}
    </section>
  )
}
