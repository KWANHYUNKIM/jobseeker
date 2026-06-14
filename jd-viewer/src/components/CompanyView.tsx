import { useEffect, useMemo, useState } from 'react'
import { useCompanies } from '../lib/useCompanies'
import { useLearning, type LearningVideo } from '../lib/useLearning'
import { Loader, ErrorState, EmptyState, SidePanel, MobileBar } from './ui'
import { ROLE_COLORS } from '../lib/classify'
import type { CompanyStack, CareerGuide } from '../types'

const SIZE_COLOR: Record<string, string> = {
  대기업: '#f472b6',
  중견기업: '#fbbf24',
  중소기업: '#60a5fa',
}

const CAT_COLOR: Record<string, string> = {
  언어: '#c084fc',
  백엔드: '#60a5fa',
  프론트엔드: '#34d399',
  모바일: '#fbbf24',
  데이터베이스: '#22d3ee',
  '인프라/DevOps': '#fb923c',
  '펌웨어/임베디드': '#a78bfa',
  'AI/ML': '#f472b6',
  데이터: '#2dd4bf',
  '협업/도구': '#94a3b8',
  기타: '#6b7280',
}

const CAT_ORDER = [
  '언어', '백엔드', '프론트엔드', '모바일', '데이터베이스',
  '인프라/DevOps', '펌웨어/임베디드', 'AI/ML', '데이터', '협업/도구', '기타',
]

export function CompanyView({
  focusNorm,
  onStudyTech,
}: {
  focusNorm?: string | null
  onStudyTech?: (tech: string) => void
}) {
  const { companies, meta, loading, error } = useCompanies()
  const [query, setQuery] = useState('')
  const [selectedNorm, setSelectedNorm] = useState<string | null>(null)
  const [navOpen, setNavOpen] = useState(false)

  // 다른 탭(기술스택 확장)에서 회사를 지정해 들어오면 선택·검색 동기화
  useEffect(() => {
    if (!focusNorm) return
    setSelectedNorm(focusNorm)
    setQuery('')
  }, [focusNorm])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return companies
    return companies.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.domains.some((d) => d.name.toLowerCase().includes(q)) ||
        c.top_tech.some((t) => t.name.toLowerCase().includes(q)),
    )
  }, [companies, query])

  const selected = useMemo(
    () => companies.find((c) => c.norm === selectedNorm) ?? filtered[0] ?? null,
    [companies, selectedNorm, filtered],
  )

  if (loading) return <Loader label="회사 분석 데이터 불러오는 중…" />
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
      {/* 좌측: 회사 리스트 (모바일=드로어) */}
      <SidePanel side="left" desktopWidth="md:w-72" open={navOpen} onClose={() => setNavOpen(false)}>
        <div className="p-3 border-b border-(--color-border)">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="회사·기술·도메인 검색"
            className="w-full bg-(--color-bg) border border-(--color-border) rounded px-3 py-1.5 text-sm text-(--color-text) placeholder:text-(--color-muted) focus:border-(--color-accent) outline-none"
          />
          <div className="text-[11px] text-(--color-muted) mt-2">
            {filtered.length}개 회사 · 공고 {meta?.min_posting ?? 2}건 이상
          </div>
        </div>
        <div className="overflow-auto flex-1">
          {filtered.map((c) => {
            const active = selected?.norm === c.norm
            return (
              <button
                key={c.norm}
                onClick={() => {
                  setSelectedNorm(c.norm)
                  setNavOpen(false)
                }}
                className={`w-full text-left px-3 py-2.5 border-b border-(--color-border)/50 transition ${
                  active ? 'bg-(--color-accent)/15' : 'hover:bg-white/5'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm text-(--color-text) font-medium truncate">{c.name}</span>
                  <span
                    className="text-[10px] px-1.5 py-0.5 rounded-full shrink-0"
                    style={{ background: (SIZE_COLOR[c.size] ?? '#60a5fa') + '22', color: SIZE_COLOR[c.size] ?? '#60a5fa' }}
                  >
                    {c.size}
                  </span>
                  <span className="ml-auto text-[11px] text-(--color-muted) shrink-0">{c.posting_count}건</span>
                </div>
                <div className="text-[11px] text-(--color-muted) mt-1 truncate">
                  {c.domains[0]?.name ?? '도메인 미상'}
                  {c.top_tech[0] ? ` · ${c.top_tech.slice(0, 3).map((t) => t.name).join(', ')}` : ''}
                </div>
              </button>
            )
          })}
        </div>
      </SidePanel>

      {/* 우측: 회사 프로필 */}
      <main className="flex-1 min-w-0 overflow-auto">
        <MobileBar onMenu={() => setNavOpen(true)} label="회사 목록">
          {selected && <span className="ml-auto text-xs text-(--color-text) truncate">{selected.name}</span>}
        </MobileBar>
        {selected ? <CompanyProfile c={selected} onStudyTech={onStudyTech} /> : (
          <EmptyState title="회사를 선택하세요" hint="‘회사 목록’에서 회사를 고르면 기술스택·취업 가이드가 표시됩니다." />
        )}
      </main>
    </div>
  )
}

function CompanyProfile({ c, onStudyTech }: { c: CompanyStack; onStudyTech?: (tech: string) => void }) {
  const learning = useLearning()
  const maxRole = Math.max(1, ...Object.values(c.roles))
  return (
    <div className="p-6 max-w-4xl">
      {/* 헤더 */}
      <div className="flex items-center flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-(--color-text)">{c.name}</h1>
        <span
          className="text-xs px-2 py-0.5 rounded-full"
          style={{ background: (SIZE_COLOR[c.size] ?? '#60a5fa') + '22', color: SIZE_COLOR[c.size] ?? '#60a5fa' }}
        >
          {c.size}
        </span>
        <span className="text-xs text-(--color-muted)">채용공고 {c.posting_count}건</span>
        <span className="text-xs text-(--color-muted)">· {c.sites.join(', ')}</span>
        {c.homepage && (
          <a
            href={c.homepage}
            target="_blank"
            rel="noreferrer"
            className="ml-auto text-xs px-3 py-1 rounded border border-(--color-border) text-(--color-accent) hover:bg-(--color-accent)/10"
          >
            홈페이지 ↗
          </a>
        )}
      </div>

      {/* 요약 */}
      <p className="mt-3 text-sm text-(--color-text) leading-relaxed bg-(--color-panel) border border-(--color-border) rounded-lg p-3">
        {c.summary}
      </p>

      {/* 도메인 */}
      <Section title="도메인 (사업 영역)">
        {c.domains.length ? (
          <div className="flex flex-wrap gap-2">
            {c.domains.map((d) => (
              <span
                key={d.name}
                title={d.evidence.length ? `근거 키워드: ${d.evidence.join(', ')}` : undefined}
                className="text-sm px-3 py-1.5 rounded-lg bg-(--color-accent)/12 text-(--color-accent) border border-(--color-accent)/30"
              >
                {d.name}
                {d.evidence.length > 0 && (
                  <span className="text-[11px] text-(--color-muted) ml-1.5">{d.evidence.slice(0, 3).join(' · ')}</span>
                )}
              </span>
            ))}
          </div>
        ) : (
          <span className="text-sm text-(--color-muted)">추론된 도메인 없음</span>
        )}
      </Section>

      {/* 아키텍처 추론 */}
      <Section title="아키텍처 추론 (기술 조합 기반 예측)">
        {c.architecture.length ? (
          <div className="grid sm:grid-cols-2 gap-2">
            {c.architecture.map((a) => (
              <div key={a.label} className="bg-(--color-panel) border border-(--color-border) rounded-lg p-3">
                <div className="text-sm font-semibold text-(--color-text)">{a.label}</div>
                <div className="text-[12px] text-(--color-muted) mt-1 leading-relaxed">{a.why}</div>
              </div>
            ))}
          </div>
        ) : (
          <span className="text-sm text-(--color-muted)">추론된 아키텍처 없음</span>
        )}
      </Section>

      {/* 취업 가이드 */}
      {c.career_guide && (
        <CareerGuideBlock
          g={c.career_guide}
          videos={learning.resources}
          searchUrl={learning.searchUrl}
        />
      )}

      {/* 기술스택 (카테고리별) — 기술 클릭 시 학습 탭으로 점프 */}
      <Section title="기술스택 (채용공고 기반 · 기술 클릭 → 학습 커리큘럼)">
        <div className="space-y-3">
          {CAT_ORDER.filter((cat) => c.tech_categories[cat]?.length).map((cat) => (
            <div key={cat}>
              <div className="text-[11px] uppercase tracking-wider font-semibold mb-1.5" style={{ color: CAT_COLOR[cat] }}>
                {cat}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {c.tech_categories[cat].map((t) => {
                  const hasCurr = !!learning.curricula[t.name]
                  const hasVids = (learning.resources[t.name]?.length ?? 0) > 0
                  const studiable = !!onStudyTech && (hasCurr || hasVids)
                  return (
                    <button
                      key={t.name}
                      disabled={!studiable}
                      onClick={() => studiable && onStudyTech?.(t.name)}
                      title={
                        studiable
                          ? `${t.name} 학습 ${hasCurr ? '커리큘럼' : '영상'} 보기`
                          : `${t.name} (공고 ${t.count}건)`
                      }
                      className={`text-[13px] px-2.5 py-1 rounded-md border flex items-center gap-1.5 transition ${
                        studiable ? 'hover:brightness-125 cursor-pointer' : 'cursor-default'
                      }`}
                      style={{ borderColor: (CAT_COLOR[cat] ?? '#6b7280') + '55', background: (CAT_COLOR[cat] ?? '#6b7280') + '12' }}
                    >
                      <span className="text-(--color-text)">{t.name}</span>
                      <span className="text-[10px] text-(--color-muted)">{t.count}</span>
                      {hasCurr ? (
                        <span className="text-[10px]" title="학습 커리큘럼 있음">🗺️</span>
                      ) : hasVids ? (
                        <span className="text-[10px]" title="학습 영상 있음">📺</span>
                      ) : null}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* 직군 분포 */}
      <Section title="채용 직군 분포">
        <div className="space-y-1.5 max-w-md">
          {Object.entries(c.roles).map(([role, n]) => (
            <div key={role} className="flex items-center gap-2">
              <span className="text-xs text-(--color-muted) w-24 shrink-0 text-right">{role}</span>
              <div className="flex-1 h-4 bg-(--color-panel) rounded overflow-hidden">
                <div
                  className="h-full rounded"
                  style={{ width: `${(n / maxRole) * 100}%`, background: ROLE_COLORS[role] ?? '#6b7280' }}
                />
              </div>
              <span className="text-xs text-(--color-muted) w-8">{n}</span>
            </div>
          ))}
        </div>
      </Section>

      {/* 홈페이지 조사 (2차 보강) */}
      {(c.homepage_desc || (c.homepage_tech && c.homepage_tech.length > 0)) && (
        <Section title="홈페이지 조사 (자동 수집)">
          {c.homepage_desc && (
            <p className="text-sm text-(--color-text) leading-relaxed mb-2">{c.homepage_desc}</p>
          )}
          {c.homepage_tech && c.homepage_tech.length > 0 && (
            <div>
              <span className="text-[11px] text-(--color-muted)">홈페이지에서 감지된 기술: </span>
              <span className="text-[12px] text-(--color-muted)">{c.homepage_tech.join(', ')}</span>
            </div>
          )}
        </Section>
      )}

      {/* 공고 목록 */}
      <Section title="채용공고">
        <ul className="space-y-1">
          {c.postings.map((p, i) => (
            <li key={i}>
              <a
                href={p.url}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-(--color-accent) hover:underline"
              >
                {p.title || p.url}
              </a>
              <span className="text-[11px] text-(--color-muted) ml-2">{p.site}</span>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  )
}

function CareerGuideBlock({
  g,
  videos,
  searchUrl,
}: {
  g: CareerGuide
  videos: Record<string, LearningVideo[]>
  searchUrl: string
}) {
  const [openStage, setOpenStage] = useState<number | null>(null)
  // "{tech}+강의" 검색 URL — 큐레이션 영상이 없을 때의 폴백
  const ytSearch = (tech: string) =>
    searchUrl
      ? searchUrl.replace('{tech}', encodeURIComponent(tech))
      : `https://www.youtube.com/results?search_query=${encodeURIComponent(tech + ' 강의')}`
  // 한 단계의 기술들에서 큐레이션 영상(기술당 1개) 모으기 — 중복 제거
  const stageVideos = (techs: string[]): LearningVideo[] => {
    const out: LearningVideo[] = []
    const seen = new Set<string>()
    for (const t of techs) {
      const v = videos[t]?.[0]
      if (v && !seen.has(v.url)) {
        seen.add(v.url)
        out.push(v)
      }
    }
    return out
  }

  return (
    <Section title="🎯 취업 가이드 (채용 데이터 기반 추론)">
      <div className="space-y-4">
        {/* 원하는 인재상 */}
        {g.wants.length > 0 && (
          <div className="bg-(--color-panel) border border-(--color-border) rounded-lg p-3">
            <div className="text-[12px] font-semibold text-(--color-accent) mb-2">
              이런 사람을 원합니다
            </div>
            <ul className="space-y-1">
              {g.wants.map((w, i) => (
                <li key={i} className="text-[13px] text-(--color-text) leading-relaxed flex gap-2">
                  <span className="text-(--color-accent) shrink-0">✓</span>
                  <span>{w}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 공부 로드맵 */}
        {g.roadmap.length > 0 && (
          <div>
            <div className="text-[12px] font-semibold text-emerald-400 mb-2">
              공부 로드맵 — 이 회사 스택 기준으로 순서대로 (기술 클릭 → 유튜브 강의)
            </div>
            <ol className="relative border-l border-(--color-border) ml-2 space-y-3">
              {g.roadmap.map((s, i) => {
                const vids = stageVideos(s.techs)
                const open = openStage === i
                return (
                  <li key={i} className="ml-4">
                    <span className="absolute -left-[5px] mt-1.5 w-2.5 h-2.5 rounded-full bg-emerald-400" />
                    <div className="text-[13px] font-semibold text-(--color-text)">{s.stage}</div>
                    <div className="text-[12px] text-(--color-muted) mt-0.5">{s.goal}</div>
                    <div className="flex flex-wrap items-center gap-1 mt-1.5">
                      {s.techs.map((t) => (
                        <a
                          key={t}
                          href={ytSearch(t)}
                          target="_blank"
                          rel="noreferrer"
                          title={`유튜브에서 '${t} 강의' 검색`}
                          className="text-[11px] px-2 py-0.5 rounded-md bg-emerald-400/12 text-emerald-300 border border-emerald-400/25 hover:bg-emerald-400/25"
                        >
                          {t}
                          {videos[t]?.length ? ' 📺' : ''}
                        </a>
                      ))}
                      {vids.length > 0 && (
                        <button
                          onClick={() => setOpenStage(open ? null : i)}
                          className="text-[11px] px-2 py-0.5 rounded-md border border-sky-400/30 text-sky-300 hover:bg-sky-400/15"
                        >
                          {open ? '강의 접기 ▴' : `추천 강의 ${vids.length}개 ▾`}
                        </button>
                      )}
                    </div>
                    {open && vids.length > 0 && (
                      <div className="mt-2 grid sm:grid-cols-2 gap-2">
                        {vids.map((v) => (
                          <a
                            key={v.url}
                            href={v.url}
                            target="_blank"
                            rel="noreferrer"
                            className="flex gap-2 bg-(--color-panel) border border-(--color-border) rounded-lg p-1.5 hover:border-sky-400/40"
                          >
                            <img
                              src={v.thumbnail}
                              alt=""
                              loading="lazy"
                              className="w-20 h-12 object-cover rounded shrink-0"
                            />
                            <div className="min-w-0">
                              <div className="text-[12px] text-(--color-text) leading-snug line-clamp-2">
                                {v.title}
                              </div>
                              <div className="text-[10px] text-(--color-muted) mt-0.5 truncate">
                                {v.channel} · {v.length}
                              </div>
                            </div>
                          </a>
                        ))}
                      </div>
                    )}
                    {s.tips.length > 0 && (
                      <ul className="mt-1.5 space-y-0.5">
                        {s.tips.map((t, j) => (
                          <li key={j} className="text-[12px] text-(--color-muted) leading-relaxed">
                            · {t}
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                )
              })}
            </ol>
          </div>
        )}

        {/* 입사 후 업무 */}
        {g.tasks.length > 0 && (
          <div className="bg-(--color-panel) border border-(--color-border) rounded-lg p-3">
            <div className="text-[12px] font-semibold text-amber-400 mb-2">
              입사하면 이런 업무를 하게 됩니다 (추론)
            </div>
            <ul className="space-y-1">
              {g.tasks.map((t, i) => (
                <li key={i} className="text-[13px] text-(--color-text) leading-relaxed flex gap-2">
                  <span className="text-amber-400 shrink-0">▸</span>
                  <span>{t}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 추천 기술블로그 */}
        {g.study_blogs.length > 0 && (
          <div>
            <div className="text-[12px] font-semibold text-sky-400 mb-2">
              공부하면 좋은 기술블로그 (스택·도메인 매칭)
            </div>
            <ul className="space-y-1.5">
              {g.study_blogs.map((b, i) => (
                <li key={i} className="text-[13px] leading-snug">
                  <a
                    href={b.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sky-300 hover:underline"
                  >
                    {b.title}
                  </a>
                  <span className="text-[11px] text-(--color-muted) ml-1.5">
                    · {b.company}
                    {b.country ? ` (${b.country})` : ''}
                    {b.why ? ` · ${b.why}` : ''}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Section>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-5">
      <h2 className="text-sm font-semibold text-(--color-text) mb-2">{title}</h2>
      {children}
    </section>
  )
}
