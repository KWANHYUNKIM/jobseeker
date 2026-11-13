import { useEffect, useMemo, useState } from 'react'
import { useCompanies } from '../../../hooks/useCompanies'
import {
  useLearning,
  type LearningVideo,
  type LearningStage,
  type Curriculum,
} from '../../../hooks/useLearning'
import {
  buildExpansionIndex,
  CAT_ORDER,
  type TechNode,
  type CompanyRef,
} from '../utils/expansion'
import { Loader, ErrorState, EmptyState, CompanyMark } from '../../../components/ui'
import { Pager } from '../../../components/Pager'
import { usePaged, PAGE_SIZE } from '../../../hooks/usePaged'

// 회사 칸은 3열 격자의 작은 칩이라 10개면 세 줄 남짓이다 — 10줄이 되게 곱한다
const COMPANY_PAGE = PAGE_SIZE * 3
// usePaged 는 배열이 바뀌면 1쪽으로 되돌린다 — 렌더마다 새 [] 를 주면 끝없이 되돌린다
const NO_COMPANIES: CompanyRef[] = []

export function ExpansionView({
  onOpenCompany,
  focusTech,
}: {
  onOpenCompany?: (slug: string) => void
  /** 주소(`/trend?tech=React`)로 지정된 기술. */
  focusTech?: string | null
}) {
  const { companies, loading, error, slugOf } = useCompanies()
  const learning = useLearning()
  const [selectedTech, setSelectedTech] = useState<string | null>(null)

  // 다른 탭(회사 뷰)에서 "이 기술 공부하기"로 들어오면 해당 기술을 선택.
  useEffect(() => {
    if (focusTech) setSelectedTech(focusTech)
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
    <div className="grid gap-6 lg:grid-cols-[380px_minmax(0,1fr)] items-start">
      <TechSidebar index={index} selected={tech} onSelect={setSelectedTech} />
      <main className="min-w-0">
        {tech ? (
          <TechPanel
            tech={tech}
            index={index}
            videos={learning.resources[tech] ?? []}
            curriculum={learning.curricula[tech] ?? null}
            searchUrl={learning.searchUrl}
            learningLoading={learning.loading}
            onSelectTech={setSelectedTech}
            onOpenCompany={(norm) => onOpenCompany?.(slugOf(norm))}
          />
        ) : (
          <EmptyState title="기술을 선택하세요" hint="왼쪽에서 기술을 고르면 함께 쓰는 스택·학습 경로가 표시됩니다." />
        )}
      </main>
    </div>
  )
}

const CHIP_CAP = 6 // 분류마다 처음 보이는 기술 수

function TechSidebar({
  index,
  selected,
  onSelect,
}: {
  index: ReturnType<typeof buildExpansionIndex>
  selected: string | null
  onSelect: (t: string) => void
}) {
  const [more, setMore] = useState<Set<string>>(new Set())
  const cats = CAT_ORDER.filter((c) => index.byCategory[c]?.length)
  return (
    <aside className="rounded-[30px] border border-[#e2e8ec] bg-white px-[21px] pt-[23px] pb-6 flex flex-col gap-[22px]">
      {cats.map((cat) => {
        const all = index.byCategory[cat]
        const open = more.has(cat)
        const items = open ? all : all.filter((t, i) => i < CHIP_CAP || t.name === selected)
        return (
          <div key={cat}>
            <div className="text-sm font-bold text-[#272727]">{cat}</div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {items.map((t) => {
                const on = t.name === selected
                return (
                  <button
                    key={t.name}
                    type="button"
                    aria-pressed={on}
                    onClick={() => onSelect(t.name)}
                    className={
                      'inline-flex items-center gap-1.5 h-8 px-[13px] rounded-[18px] border text-[13px] font-medium tracking-[-0.3px] ' +
                      (on ? 'bg-(--color-accent) border-(--color-accent) text-white' : 'bg-white border-[#d8d8d8] text-[#272727] hover:border-[#272727]')
                    }
                  >
                    {t.name}
                    <span className={'text-xs font-normal tabular-nums ' + (on ? 'text-[#ffd9d9]' : 'text-[#999]')}>{t.companyCount}</span>
                  </button>
                )
              })}
              {all.length > CHIP_CAP && (
                <button
                  type="button"
                  onClick={() => setMore((s) => {
                    const n = new Set(s)
                    if (n.has(cat)) n.delete(cat)
                    else n.add(cat)
                    return n
                  })}
                  className="h-8 px-2 text-[13px] text-[#999] hover:text-[#272727]"
                >
                  {open ? '접기' : `+${all.length - CHIP_CAP}`}
                </button>
              )}
            </div>
          </div>
        )
      })}
    </aside>
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
  /** 회사 이름(norm)을 넘긴다 — 주소 슬러그로 바꾸는 건 목록을 든 바깥의 몫이다. */
  onOpenCompany?: (norm: string) => void
}) {
  const cat = index.categoryOf[tech] ?? '기타'
  const node = index.techs.find((t) => t.name === tech) as TechNode | undefined
  const companies = index.companiesByTech[tech] ?? NO_COMPANIES
  const cooc = (index.coocByTech[tech] ?? []).slice(0, 9)
  const maxConf = Math.max(0.0001, ...cooc.map((c) => c.confidence))
  const paged = usePaged(companies, COMPANY_PAGE)

  return (
    <div className="flex flex-col gap-[34px]">
      <section className="rounded-[26px] bg-[#272727] px-[30px] pt-[26px] pb-6 text-white">
        <div className="text-[13px] text-[#bbb]">선택한 기술 · {cat}</div>
        <h2 className="mt-0.5 text-[32px] font-bold leading-[47px]">{tech}</h2>
        <p className="mt-1 text-[15px] text-[#ddd]">
          <b className="font-bold text-[#ff9a9a]">{node?.companyCount ?? 0}개 회사</b> · 공고 {node?.postingCount ?? 0}건에서 써요
        </p>
      </section>

      <Section title="함께 자주 쓰는 기술" hint="이 기술을 쓰는 회사에서 유난히 자주 함께 나오는 기술 — 다음 학습 후보">
        {cooc.length ? (
          <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-2.5">
            {cooc.map((c) => (
              <button
                key={c.name}
                type="button"
                onClick={() => onSelectTech(c.name)}
                className="text-left min-h-[119px] rounded-[18px] border border-[#e2e8ec] bg-white px-[19px] pt-[17px] pb-3.5 hover:border-[#999]"
              >
                <div className="text-[17px] font-bold leading-[25px] text-[#272727] truncate">{c.name}</div>
                <div className="text-[13px] text-[#888] tabular-nums">{c.coCount}곳</div>
                <div className="mt-2 h-1.5 rounded-[3px] bg-[#f1f3f5] overflow-hidden">
                  <div className="h-full rounded-[3px] bg-[#f67979]" style={{ width: `${(c.confidence / maxConf) * 100}%` }} />
                </div>
                <div className="mt-2 text-xs text-[#666] tabular-nums">
                  동반율 {(c.confidence * 100).toFixed(0)}% · 연관도 <b className="font-bold text-(--color-accent)">{c.lift.toFixed(1)}x</b>
                </div>
              </button>
            ))}
          </div>
        ) : (
          <span className="text-sm text-[#999]">동시출현 데이터가 충분하지 않아요.</span>
        )}
      </Section>

      {/* 세부 주제 커리큘럼 — 무엇을 어떤 순서로 공부할지 */}
      {curriculum && (
        <Section title={`${tech} 학습 커리큘럼`} hint="공부 순서대로 · 주제별 추천 강의">
          <div className="rounded-2xl bg-[#f7f9fa] px-5 py-4 text-sm leading-[22px] text-[#474747]">
            <b className="mr-2 font-bold text-(--color-accent)">이렇게 공부하세요</b>
            {curriculum.guide}
          </div>
          <ol className="mt-3 flex flex-col gap-2.5">
            {curriculum.topics.map((t, i) => {
              const v = t.videos[0]
              return (
                <li key={t.topic} className="flex flex-col md:flex-row md:items-center gap-4 min-h-[84px] rounded-[18px] border border-[#e2e8ec] px-[19px] py-3.5">
                  <div className="flex items-center gap-3 md:w-[240px] shrink-0">
                    <span className="grid place-items-center w-[34px] h-[34px] rounded-full bg-[#272727] text-base font-bold text-white shrink-0">{i + 1}</span>
                    <span className="min-w-0">
                      <span className="block text-base font-bold text-[#272727]">{t.topic}</span>
                      <span className="block text-[13px] text-[#888] truncate">{t.note}</span>
                    </span>
                  </div>
                  {v && (
                    <a href={v.url} target="_blank" rel="noreferrer" className="group flex-1 min-w-0 flex items-center gap-3">
                      <span className="relative w-24 h-[54px] shrink-0 rounded-[10px] overflow-hidden bg-[#3a3a3a]">
                        <img src={v.thumbnail} alt="" loading="lazy" className="w-full h-full object-cover" />
                        {v.length && <span className="absolute bottom-1 right-1 rounded-[3px] bg-black/70 px-1 text-[10px] text-white">{v.length}</span>}
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium text-[#272727] group-hover:underline underline-offset-2">{v.title}</span>
                        <span className="block truncate text-xs text-[#999]">
                          {v.channel} · {formatViews(v.views)}
                        </span>
                      </span>
                    </a>
                  )}
                  {t.videos.length > 1 && <span className="shrink-0 text-xs text-[#999]">+{t.videos.length - 1}편</span>}
                </li>
              )
            })}
          </ol>
        </Section>
      )}

      {/* 단계별 그 밖의 강의 */}
      <Section title={curriculum ? `${tech} 그 외 추천 강의` : `${tech} 학습 로드맵`} hint="유튜브 강의를 입문 → 핵심 → 실전 단계로 나눈 경로">
        {learningLoading ? (
          <span className="text-sm text-[#999]">학습 영상 불러오는 중…</span>
        ) : videos.length ? (
          <div className="flex flex-col gap-5">
            {STAGES.map((st) => {
              const items = videos.filter((v) => v.stage === st.key)
              if (!items.length) return null
              return (
                <div key={st.key}>
                  <div className="flex items-baseline gap-2">
                    <span className="rounded px-[7px] text-[13px] font-bold leading-[22px]" style={{ background: st.color + '22', color: st.color }}>
                      {st.key}
                    </span>
                    <span className="text-xs text-[#999]">{st.desc}</span>
                  </div>
                  <div className="mt-2 grid sm:grid-cols-2 xl:grid-cols-3 gap-3">
                    {items.map((v) => (
                      <VideoCard key={v.url} v={v} />
                    ))}
                  </div>
                </div>
              )
            })}
            {searchUrl && (
              <a href={searchUrl.replace('{tech}', encodeURIComponent(tech))} target="_blank" rel="noreferrer" className="text-[13px] text-(--color-accent) hover:underline">
                유튜브에서 ‘{tech} 강의’ 더 보기 →
              </a>
            )}
          </div>
        ) : (
          <div className="text-sm text-[#999]">
            수집된 학습 영상이 없어요.
            {searchUrl && (
              <>
                {' '}
                <a href={searchUrl.replace('{tech}', encodeURIComponent(tech))} target="_blank" rel="noreferrer" className="text-(--color-accent) hover:underline">
                  유튜브에서 직접 검색 →
                </a>
              </>
            )}
          </div>
        )}
      </Section>

      {/* 이 기술을 쓰는 회사 */}
      <Section title={`이 기술을 쓰는 회사`} hint={`${companies.length}곳`}>
        {paged.slice.length ? (
          <>
            <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-2">
              {paged.slice.map((c) => (
                <button
                  key={c.norm}
                  type="button"
                  onClick={() => onOpenCompany?.(c.norm)}
                  className="flex items-center gap-2.5 rounded-[14px] border border-[#e2e8ec] bg-white px-3 py-2.5 text-left hover:border-[#999]"
                >
                  <span className="grid place-items-center w-7 h-7 rounded-lg overflow-hidden shrink-0">
                    <CompanyMark name={c.name} size={28} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-[#272727]">{c.name}</span>
                    <span className="block truncate text-xs text-[#999]">
                      {c.size}
                      {c.domains[0] ? ` · ${c.domains[0]}` : ''}
                    </span>
                  </span>
                  <span className="shrink-0 text-xs text-[#999] tabular-nums">{c.count}건</span>
                </button>
              ))}
            </div>
            <Pager page={paged.page} totalPages={paged.totalPages} onChange={paged.setPage} />
          </>
        ) : (
          <span className="text-sm text-[#999]">이 기술을 쓰는 회사가 없어요.</span>
        )}
      </Section>
    </div>
  )
}

const STAGES: { key: LearningStage; color: string; desc: string }[] = [
  { key: '입문', color: '#2bb673', desc: '왜 쓰는지·개념부터 — 여기서 출발' },
  { key: '핵심', color: '#4f7cf0', desc: '문법·핵심 기능을 손에 익히기' },
  { key: '실전', color: '#f2a93b', desc: '프로젝트·실무·배포로 마무리' },
]

function VideoCard({ v }: { v: LearningVideo }) {
  return (
    <a href={v.url} target="_blank" rel="noreferrer" className="group rounded-[14px] border border-[#e2e8ec] bg-white overflow-hidden hover:border-[#999]">
      <div className="relative aspect-video bg-[#3a3a3a]">
        <img src={v.thumbnail} alt="" loading="lazy" className="w-full h-full object-cover" />
        {v.length && <span className="absolute bottom-1 right-1 rounded-[3px] bg-black/70 px-1 text-[10px] text-white">{v.length}</span>}
      </div>
      <div className="p-3">
        <div className="text-[13px] font-medium leading-snug text-[#272727] line-clamp-2 group-hover:underline underline-offset-2">{v.title}</div>
        <div className="mt-1.5 truncate text-[11px] text-[#999]">
          {v.channel} · {formatViews(v.views)}
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
    <section>
      <h3 className="flex flex-wrap items-baseline gap-x-[15px]">
        <span className="text-[19px] font-bold text-[#272727]">{title}</span>
        {hint && <span className="text-[13px] text-[#999]">{hint}</span>}
      </h3>
      <div className="mt-[18px]">{children}</div>
    </section>
  )
}
