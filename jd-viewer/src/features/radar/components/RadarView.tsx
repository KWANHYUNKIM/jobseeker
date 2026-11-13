import { useEffect, useMemo, useRef, useState } from 'react'
import { goBack, navigate, onLinkClick } from '../../../utils/navigation'
import { paths } from '../../../utils/urls'
import { absUrl, clip, useSeo } from '../../../utils/seo'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useRadar } from '../hooks/useRadar'
import { ArchitectureDiagram } from '../../../components/ArchitectureDiagram'
import { Loader, ErrorState, CompanyMark } from '../../../components/ui'
import { Pager } from '../../../components/Pager'
import { SiteFooter } from '../../../components/SiteFooter'
import { usePaged, PAGE_SIZE_GRID as PAGE_SIZE } from '../../../hooks/usePaged'
import type {
  Debate,
  DeepDiveSection,
  DomainGroup,
  Interview,
  RadarCompany,
  RadarFile,
  RadarTechCount,
} from '../../../types'

const COUNTRY_LABEL: Record<string, string> = {
  US: '🇺🇸 미국',
  KR: '🇰🇷 한국',
  IN: '🇮🇳 인도',
  JP: '🇯🇵 일본',
  GB: '🇬🇧 영국',
  DE: '🇩🇪 독일',
  SG: '🇸🇬 싱가포르',
  CN: '🇨🇳 중국',
}

const STACK_LABEL: Record<string, string> = {
  backend: '백엔드',
  frontend: '프론트엔드',
  data: '데이터',
  infra: '인프라/DevOps',
}

export function RadarView({ companyKey }: { companyKey?: string | null }) {
  const { data, loading, error } = useRadar()
  const [mode, setMode] = useState<'company' | 'domain'>('company')
  const [query, setQuery] = useState('')
  const [country, setCountry] = useState<string | null>(null)
  const [domain, setDomain] = useState<string | null>(null)
  const [langs, setLangs] = useState<Set<string>>(new Set())
  const [flags, setFlags] = useState<Set<string>>(new Set())
  const [sort, setSort] = useState<'default' | 'name' | 'country'>('default')

  // 매 렌더마다 새 배열이 되면 아래 useMemo 들이 전부 다시 돈다(회사 100곳 × 필터).
  const companies = useMemo(() => data?.companies ?? [], [data])

  // 도메인 뷰에서 회사 이름을 클릭하면 상세를 연다
  const byName = useMemo(() => {
    const m = new Map<string, RadarCompany>()
    for (const c of companies) m.set(c.name, c)
    return m
  }, [companies])

  // 회사 상세는 주소(/radar/<key>)가 단일 출처다 — 딥링크·공유·새로고침·뒤로가기가
  // 전부 같은 경로 하나로 해결된다. 열고 닫는 건 주소를 바꾸는 일이고, 무엇이 열려
  // 있는지는 주소에서 파생된다.
  const openCompany = (c: RadarCompany) => navigate(paths.radarCompany(c.key))
  const closeCompany = () => goBack(paths.radar())
  const selected = useMemo(
    () => (companyKey ? (companies.find((c) => c.key === companyKey) ?? null) : null),
    [companies, companyKey],
  )

  // 회사 상세의 제목·설명은 이 뷰가 단다 — 레이더 데이터를 들고 있는 게 여기뿐이다.
  useSeo(
    companyKey && selected
      ? {
          title: `${selected.name} 기술스택·아키텍처`,
          description: clip(
            `${selected.name}(${selected.domain})의 기술스택과 아키텍처. 언어: ${selected.languages.join(', ')}. ${selected.summary ?? ''}`,
          ),
          canonical: absUrl(paths.radarCompany(selected.key)),
        }
      : null,
  )

  const langCount = useMemo(() => {
    const c = new Map<string, number>()
    for (const co of companies) for (const l of co.languages) c.set(l, (c.get(l) ?? 0) + 1)
    return [...c.entries()].sort((a, b) => b[1] - a[1])
  }, [companies])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    const list = companies.filter((c) => {
      if (country && c.country !== country) return false
      if (domain && c.domain !== domain) return false
      if (langs.size && !c.languages.some((l) => langs.has(l))) return false
      if (flags.has('debate') && !c.debate) return false
      if (flags.has('interview') && !c.interview) return false
      if (flags.has('github') && !c.github?.repos?.length) return false
      if (flags.has('refined') && c.research_status !== 'llm-refined') return false
      if (q) {
        // 이름·도메인·기술뿐 아니라 '왜' 설명과 심화 해설 본문까지 훑어
        // "이벤트 소싱", "샤딩" 같은 개념으로도 회사를 찾을 수 있게 한다.
        const hay = [
          c.name, c.domain, c.summary, c.why_language, c.why_architecture,
          c.languages.join(' '),
          c.stack.backend.join(' '), c.stack.frontend.join(' '),
          c.stack.data.join(' '), c.stack.infra.join(' '),
          c.architecture.join(' '),
          (c.deep_dive ?? []).map((s) => `${s.topic} ${s.body}`).join(' '),
        ].join(' ').toLowerCase()
        if (!hay.includes(q)) return false
      }
      return true
    })
    if (sort === 'name') list.sort((a, b) => a.name.localeCompare(b.name))
    else if (sort === 'country')
      list.sort((a, b) => a.country.localeCompare(b.country) || a.name.localeCompare(b.name))
    return list
  }, [companies, query, country, domain, langs, flags, sort])
  const paged = usePaged(filtered, PAGE_SIZE)

  const toggleLang = (name: string) => {
    const next = new Set(langs)
    if (next.has(name)) next.delete(name)
    else next.add(name)
    setLangs(next)
  }

  if (loading) return <Loader label="기술 스택 레이더 불러오는 중…" />
  if (error)
    return (
      <ErrorState
        title="company_tech_radar.json 로드 실패"
        detail={error}
        hint={<>생성: <code className="text-(--color-text)">python bin/build_company_tech_radar.py --init seed_*.json</code> (jd-viewer)</>}
      />
    )

  const githubCount = companies.filter((c) => c.github?.repos?.length).length
  const anyFilter = query.trim() !== '' || country !== null || domain !== null || langs.size > 0

  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[43px] pb-[90px]">
        <h1 className="text-[28px] font-bold leading-10 tracking-[-0.6px] text-[#272727]">
          글로벌 IT 기업 <span className="font-black text-(--color-accent)">{data?.total ?? companies.length}곳</span> 기술 레이더
        </h1>
        <p className="mt-1 text-base leading-6 tracking-[-0.16px] text-[#666]">
          언어·기술스택·아키텍처 다이어그램·기술 심화·전형까지, 회사 하나를 끝까지 파고들어요.
          {data?.generated_at ? ` 갱신 ${data.generated_at.slice(0, 10)}` : ''}
        </p>

        {/* 블로그 글 ↔ 기업 100 — 기술 블로그 화면과 오가는 탭 */}
        <nav className="mt-[34px] flex border-b border-[#e2e2e2]">
          <a href={paths.blog()} onClick={onLinkClick(paths.blog())} className="shrink-0 px-[22px] pb-[13px] text-[17px] font-medium text-[#777] hover:text-[#272727]">
            블로그 글
          </a>
          <span aria-current="page" className="relative shrink-0 px-[22px] pb-[13px] text-[17px] font-bold text-(--color-accent) after:absolute after:inset-x-0 after:-bottom-px after:h-[3px] after:bg-(--color-accent)">
            기업 100 (레이더)
          </span>
        </nav>

        <div className="mt-[26px] grid grid-cols-2 lg:grid-cols-4 gap-[14px]">
          <RadarStat label="회사" value={`${data?.total ?? companies.length}곳`} accent />
          <RadarStat label="나라" value={`${data?.countries.length ?? 0}개국`} />
          <RadarStat label="도메인" value={`${data?.domains.length ?? 0}개`} />
          <RadarStat label="공개 코드" value={`${githubCount}곳`} />
        </div>

        <RadarChipRow label="국가">
          <Chip active={country === null} count={companies.length} onClick={() => setCountry(null)}>
            전체
          </Chip>
          {(data?.countries ?? []).map((c) => (
            <Chip key={c.code} active={country === c.code} onClick={() => setCountry(country === c.code ? null : c.code!)}>
              {COUNTRY_LABEL[c.code!] ?? c.code}
              <span className={country === c.code ? 'text-[#ffd9d9]' : 'text-[#999]'}>{c.count}</span>
            </Chip>
          ))}
          <span className="ml-auto flex gap-2">
            <Chip outline active={mode === 'company'} onClick={() => setMode('company')}>
              회사별
            </Chip>
            <Chip outline active={mode === 'domain'} onClick={() => setMode('domain')}>
              도메인별
            </Chip>
          </span>
        </RadarChipRow>
        <RadarChipRow label="도메인">
          <Chip active={domain === null} onClick={() => setDomain(null)}>
            전체
          </Chip>
          {/* 칩은 큰 도메인 열한 개까지(고른 것은 늘 남긴다) — 서른여섯 개를 다 늘어놓으면 네 줄이 된다. 나머지는 '도메인별' 보기에서 본다. */}
          {(data?.domains ?? []).filter((d, i) => i < 11 || d.name === domain).map((d) => (
            <Chip key={d.name} active={domain === d.name} onClick={() => setDomain(domain === d.name ? null : d.name!)}>
              {d.name}
              <span className={domain === d.name ? 'text-[#ffd9d9]' : 'text-[#999]'}>{d.count}</span>
            </Chip>
          ))}
        </RadarChipRow>
        <RadarChipRow label="언어">
          {langCount.slice(0, 12).map(([name, n]) => (
            <Chip key={name} active={langs.has(name)} onClick={() => toggleLang(name)}>
              {name}
              <span className={langs.has(name) ? 'text-[#ffd9d9]' : 'text-[#999]'}>{n}</span>
            </Chip>
          ))}
        </RadarChipRow>
        {anyFilter && (
          <div className="mt-3 flex items-center gap-3 text-sm text-[#666]">
            {query.trim() && (
              <span className="rounded bg-[#f4f4f4] px-2 leading-[26px]">
                검색: {query}
                <button type="button" onClick={() => setQuery('')} aria-label="검색어 지우기" className="ml-1.5 text-[#999] hover:text-[#272727]">
                  ✕
                </button>
              </span>
            )}
            <span className="tabular-nums">{filtered.length}곳</span>
            <button
              type="button"
              onClick={() => {
                setQuery('')
                setCountry(null)
                setDomain(null)
                setLangs(new Set())
                setFlags(new Set())
              }}
              className="text-(--color-accent) hover:underline"
            >
              필터 초기화
            </button>
          </div>
        )}

        {mode === 'domain' ? (
          <div className="mt-[50px] rounded-[30px] border border-[#e2e8ec] overflow-hidden flex">
            <DomainView
              data={data}
              onOpenCompany={(name) => {
                const c = byName.get(name)
                if (c) openCompany(c)
              }}
              onPickTech={(tech) => {
                setMode('company')
                setQuery(tech)
              }}
            />
          </div>
        ) : (
          <section className="mt-[50px]">
            <div className="flex items-center justify-between pb-4 border-b-2 border-[#272727]">
              <h2 className="text-[22px] font-bold leading-8 tracking-[-0.22px] text-[#272727]">회사별 기술 스택 · 아키텍처</h2>
              <label className="relative inline-flex items-center h-9 rounded-md border border-[#d8d8d8] bg-white">
                <select
                  aria-label="정렬"
                  value={sort}
                  onChange={(e) => setSort(e.target.value as 'default' | 'name' | 'country')}
                  className="appearance-none h-full bg-transparent pl-[15px] pr-[33px] text-sm text-[#272727] outline-none cursor-pointer"
                >
                  <option value="default">기본순</option>
                  <option value="name">이름순</option>
                  <option value="country">국가순</option>
                </select>
                <svg className="pointer-events-none absolute right-[14px]" width="10" height="8" viewBox="0 0 10 8" fill="none" stroke="#272727" strokeWidth="1.5" strokeLinecap="round" aria-hidden>
                  <path d="M1.5 2.5 5 6l3.5-3.5" />
                </svg>
              </label>
            </div>
            <div data-radar-top className="mt-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 scroll-mt-4">
              {paged.slice.map((c) => (
                <CompanyCard key={c.key} company={c} onPickLang={toggleLang} onOpen={openCompany} />
              ))}
            </div>
            {filtered.length === 0 ? (
              <p className="py-12 text-center text-sm text-[#999]">조건에 맞는 회사가 없어요.</p>
            ) : (
              <Pager page={paged.page} totalPages={paged.totalPages} onChange={paged.setPage} scrollTo="[data-radar-top]" />
            )}
          </section>
        )}
      </div>
      <SiteFooter updated={data?.generated_at} sources="각 사 엔지니어링 블로그·공개 저장소·발표 자료" />

      {selected && (() => {
        // 현재 필터 목록 안에서 이전/다음 회사로 이동(딥링크 유지). 목록 밖이면 비활성.
        const idx = filtered.findIndex((c) => c.key === selected.key)
        return (
          <RadarDetail
            company={selected}
            onClose={closeCompany}
            position={idx >= 0 ? { cur: idx + 1, total: filtered.length } : null}
            onPrev={idx > 0 ? () => openCompany(filtered[idx - 1]) : undefined}
            onNext={idx >= 0 && idx < filtered.length - 1 ? () => openCompany(filtered[idx + 1]) : undefined}
            onFilterLang={(l) => {
              setMode('company')
              setLangs(new Set([l]))
              closeCompany()
            }}
            onSearch={(q) => {
              setMode('company')
              setQuery(q)
              closeCompany()
            }}
          />
        )
      })()}
    </div>
  )
}

function RadarStat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className={'h-[108px] rounded-[20px] border px-[25px] pt-[21px] ' + (accent ? 'bg-(--color-accent-weak) border-[#ffd5d5]' : 'border-[#e2e8ec]')}>
      <div className="text-sm text-[#777]">{label}</div>
      <div className={'mt-1 text-[28px] font-bold leading-10 tracking-[-0.16px] tabular-nums ' + (accent ? 'text-(--color-accent)' : 'text-[#272727]')}>{value}</div>
    </div>
  )
}

function RadarChipRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mt-4 flex items-start gap-4">
      <span className="w-11 shrink-0 pt-[7px] text-[15px] font-bold text-[#272727]">{label}</span>
      <div className="flex-1 flex flex-wrap items-center gap-2">{children}</div>
    </div>
  )
}

/** 회사 카드(캐치형 15) — 로고·이름·나라·도메인·AI 갱신, 한 줄 요약, 언어 칩, 자료 알약. */
function CompanyCard({
  company,
  onPickLang,
  onOpen,
}: {
  company: RadarCompany
  onPickLang: (s: string) => void
  onOpen: (c: RadarCompany) => void
}) {
  const to = paths.radarCompany(company.key)
  const pills: string[] = []
  if (company.diagram) pills.push('구조도')
  if (company.deep_dive?.length) pills.push(`심화 ${company.deep_dive.length}`)
  if (company.debate) pills.push('토론')
  if (company.interview) pills.push('전형')
  if (company.github?.repos?.length) pills.push(`⌥ 코드 ${company.github.repos.length}`)
  return (
    <div className="flex flex-col min-h-[268px] rounded-3xl border border-[#e2e8ec] bg-white px-[25px] pt-[25px] pb-[21px] hover:border-[#999] transition-colors">
      <a
        href={to}
        onClick={(e) => {
          if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return
          e.preventDefault()
          onOpen(company)
        }}
        className="group block"
      >
        <span className="flex items-start gap-3">
          <span className="grid place-items-center w-[52px] h-[52px] rounded-[14px] overflow-hidden shrink-0">
            <CompanyMark name={company.name} size={52} />
          </span>
          <span className="min-w-0 flex-1 pt-0.5">
            <span className="block text-[19px] font-bold leading-[27px] text-[#272727] truncate group-hover:underline underline-offset-2">{company.name}</span>
            <span className="block text-[13px] text-[#777]">
              {COUNTRY_LABEL[company.country] ?? company.country} · {company.domain}
            </span>
          </span>
          {company.research_status === 'llm-refined' && (
            <span className="mt-3.5 shrink-0 rounded bg-[#eaf8f0] px-[7px] text-[13px] leading-[22px] text-[#1e9e5a]">AI 갱신</span>
          )}
        </span>
        {company.summary && <span className="mt-[17px] line-clamp-2 text-[15px] leading-[23px] text-[#474747]">{company.summary}</span>}
      </a>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {company.languages.slice(0, 5).map((l) => (
          <button key={l} type="button" onClick={() => onPickLang(l)} className="rounded bg-[#f1efff] px-[7px] text-[13px] leading-[22px] text-[#5b4fd6] hover:underline">
            {l}
          </button>
        ))}
      </div>
      {pills.length > 0 && (
        <div className="mt-auto pt-[18px] grid grid-cols-4 gap-1.5">
          {pills.slice(0, 4).map((p) => (
            <span key={p} className="h-8 rounded-2xl bg-[#f7f9fa] text-center text-[13px] leading-8 text-[#474747] truncate">
              {p}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

// ── 도메인별 보기: 산업 도메인 전체 + 도메인별 공통 기술스택 ──────────────
function DomainView({
  data,
  onOpenCompany,
  onPickTech,
}: {
  data: RadarFile | null
  onOpenCompany: (name: string) => void
  onPickTech: (tech: string) => void
}) {
  const groups = data?.domain_groups ?? []
  if (groups.length === 0) {
    return (
      <div className="flex-1 overflow-auto p-8 text-(--color-muted)">
        도메인 집계가 없습니다.{' '}
        <code className="text-(--color-text)">python bin/build_company_tech_radar.py</code> 로 재생성하세요.
      </div>
    )
  }
  return (
    <div className="flex-1 min-h-0 overflow-auto">
      {/* 도메인 빠른 이동 */}
      <div className="px-5 py-3 border-b border-(--color-border) flex flex-wrap gap-1.5">
        {groups.map((g) => (
          <a
            key={g.name}
            href={`#domain-${encodeURIComponent(g.name)}`}
            className="px-2 py-0.5 text-xs rounded bg-(--color-bg) border border-(--color-border) text-(--color-muted) hover:border-(--color-accent) hover:text-(--color-accent)"
          >
            {g.name} <span className="opacity-60">{g.count}</span>
          </a>
        ))}
      </div>

      <div className="grid grid-cols-1 2xl:grid-cols-2 gap-4 p-5">
        {groups.map((g) => (
          <DomainCard key={g.name} group={g} onOpenCompany={onOpenCompany} onPickTech={onPickTech} />
        ))}
      </div>
    </div>
  )
}

const DOMAIN_STACK_LABEL: Record<keyof DomainGroup['stack'], string> = {
  backend: '백엔드',
  frontend: '프론트엔드',
  data: '데이터',
  infra: '인프라/DevOps',
}

function DomainCard({
  group,
  onOpenCompany,
  onPickTech,
}: {
  group: DomainGroup
  onOpenCompany: (name: string) => void
  onPickTech: (tech: string) => void
}) {
  const stackKeys = (['backend', 'frontend', 'data', 'infra'] as const).filter(
    (k) => group.stack[k]?.length > 0,
  )
  return (
    <section
      id={`domain-${encodeURIComponent(group.name)}`}
      className="scroll-mt-4 rounded-lg border border-(--color-border) bg-(--color-panel) p-5 flex flex-col gap-4"
    >
      <div>
        <div className="flex items-baseline gap-2">
          <h3 className="text-lg font-semibold text-(--color-text)">{group.name}</h3>
          <span className="text-xs text-(--color-accent)">{group.count}개사</span>
        </div>
        {group.subdomains.length > 0 && (
          <p className="mt-0.5 text-xs text-(--color-muted)">
            세부: {group.subdomains.join(' · ')}
          </p>
        )}
      </div>

      {group.languages.length > 0 && (
        <DomainRow label="주요 언어">
          {group.languages.map((t) => (
            <TechTag key={t.name} item={t} accent onClick={() => onPickTech(t.name)} />
          ))}
        </DomainRow>
      )}

      {group.architecture.length > 0 && (
        <DomainRow label="아키텍처 패턴">
          {group.architecture.map((t) => (
            <TechTag key={t.name} item={t} onClick={() => onPickTech(t.name)} />
          ))}
        </DomainRow>
      )}

      <div className="flex flex-col gap-2.5">
        <div className="text-xs font-medium text-(--color-muted)">공통 기술스택</div>
        {stackKeys.map((k) => (
          <div key={k} className="flex gap-3">
            <div className="w-24 shrink-0 text-xs text-(--color-muted) pt-1">
              {DOMAIN_STACK_LABEL[k]}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {group.stack[k].map((t) => (
                <TechTag key={t.name} item={t} onClick={() => onPickTech(t.name)} />
              ))}
            </div>
          </div>
        ))}
      </div>

      <DomainRow label={`회사 (${group.companies.length})`}>
        {group.companies.map((name) => (
          <button
            key={name}
            onClick={() => onOpenCompany(name)}
            className="px-2 py-0.5 text-xs rounded bg-(--color-bg) border border-(--color-border) text-(--color-muted) hover:border-(--color-accent) hover:text-(--color-accent)"
          >
            {name}
          </button>
        ))}
      </DomainRow>
    </section>
  )
}

function DomainRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs font-medium text-(--color-muted) mb-2">{label}</div>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  )
}

// 기술 태그 — 빈도(몇 개사가 쓰는지)를 작은 숫자로 함께 표시. onClick 주면 클릭 가능.
function TechTag({
  item,
  accent,
  onClick,
}: {
  item: RadarTechCount
  accent?: boolean
  onClick?: () => void
}) {
  const cls = `inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded border ${
    accent
      ? 'bg-(--color-accent)/15 text-(--color-accent) border-(--color-accent)/40'
      : 'bg-(--color-bg) text-(--color-text) border-(--color-border)'
  } ${onClick ? 'hover:border-(--color-accent) hover:text-(--color-accent)' : ''}`
  const inner = (
    <>
      {item.name}
      {item.count > 1 && <span className="opacity-50 tabular-nums">{item.count}</span>}
    </>
  )
  return onClick ? (
    <button className={cls} onClick={onClick} title={`${item.name} 쓰는 회사 검색`}>
      {inner}
    </button>
  ) : (
    <span className={cls}>{inner}</span>
  )
}

function RadarDetail({
  company,
  onClose,
  position,
  onPrev,
  onNext,
  onFilterLang,
  onSearch,
}: {
  company: RadarCompany
  onClose: () => void
  position?: { cur: number; total: number } | null
  onPrev?: () => void
  onNext?: () => void
  onFilterLang?: (lang: string) => void
  onSearch?: (q: string) => void
}) {
  const stackEntries = (['backend', 'frontend', 'data', 'infra'] as const)
    .map((k) => [k, company.stack[k]] as const)
    .filter(([, v]) => v && v.length > 0)

  const scrollRef = useRef<HTMLDivElement>(null)
  const [copied, setCopied] = useState(false)

  // ESC 로 닫기, ←/→ 로 이전·다음 회사 이동 + 배경 스크롤 잠금
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      else if (e.key === 'ArrowLeft' && onPrev) onPrev()
      else if (e.key === 'ArrowRight' && onNext) onNext()
    }
    window.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [onClose, onPrev, onNext])

  // 회사가 바뀌면(이전/다음 이동·딥링크) 모달 내용을 맨 위로 스크롤
  useEffect(() => {
    scrollRef.current?.scrollTo(0, 0)
  }, [company.key])

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <div
        ref={scrollRef}
        role="dialog"
        aria-modal="true"
        aria-label={`${company.name} 기술 상세`}
        className="w-[min(1040px,96vw)] h-full overflow-auto bg-(--color-panel) border-l border-(--color-border) p-6 flex flex-col gap-5 jd-slide-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-xs text-(--color-muted) mb-1">
              <span>{COUNTRY_LABEL[company.country] ?? company.country}</span>
              <span className="px-1.5 rounded bg-(--color-bg) border border-(--color-border)">
                {company.domain}
              </span>
              {company.research_status === 'llm-refined' && (
                <span className="px-1.5 rounded bg-(--color-accent)/15 text-(--color-accent) border border-(--color-accent)/40">
                  AI 갱신 {company.updated_at}
                </span>
              )}
            </div>
            <h2 className="text-xl font-semibold text-(--color-text)">{company.name}</h2>
            {company.summary && <p className="mt-1 text-sm text-(--color-muted)">{company.summary}</p>}
          </div>
          <div className="ml-auto shrink-0 flex items-center gap-1">
            {position && (
              <span className="text-xs text-(--color-muted) tabular-nums mr-1">
                {position.cur}/{position.total}
              </span>
            )}
            <button
              onClick={() => {
                navigator.clipboard?.writeText(window.location.href).then(
                  () => {
                    setCopied(true)
                    window.setTimeout(() => setCopied(false), 1500)
                  },
                  () => {},
                )
              }}
              title="이 회사 링크 복사"
              className="h-7 px-2 flex items-center rounded border border-(--color-border) text-xs text-(--color-muted) hover:border-(--color-accent) hover:text-(--color-accent)"
            >
              {copied ? '복사됨' : '링크 복사'}
            </button>
            <NavBtn onClick={onPrev} title="이전 회사 (←)">‹</NavBtn>
            <NavBtn onClick={onNext} title="다음 회사 (→)">›</NavBtn>
            <button
              onClick={onClose}
              title="닫기 (Esc)"
              className="ml-1 text-(--color-muted) hover:text-(--color-text) text-lg leading-none px-1"
            >
              ✕
            </button>
          </div>
        </div>

        <Section title="주요 언어">
          <div className="flex flex-wrap gap-1.5">
            {company.languages.map((l) => (
              <button
                key={l}
                onClick={() => onFilterLang?.(l)}
                title={`${l} 쓰는 회사 보기`}
                className="px-2 py-0.5 text-xs rounded border bg-(--color-accent)/15 text-(--color-accent) border-(--color-accent)/40 hover:bg-(--color-accent)/25"
              >
                {l}
              </button>
            ))}
          </div>
        </Section>

        <Section title="아키텍처">
          <div className="flex flex-wrap gap-1.5">
            {company.architecture.map((a) => (
              <button
                key={a}
                onClick={() => onSearch?.(a)}
                title={`"${a}" 검색`}
                className="px-2 py-0.5 text-xs rounded border bg-(--color-bg) text-(--color-text) border-(--color-border) hover:border-(--color-accent) hover:text-(--color-accent)"
              >
                {a}
              </button>
            ))}
          </div>
        </Section>

        {company.diagram && (
          <Section title="아키텍처 다이어그램 (노드별 기술스택)">
            <ArchitectureDiagram code={company.diagram} idKey={company.key} />
          </Section>
        )}

        <Section title="기술 스택">
          <div className="flex flex-col gap-2.5">
            {stackEntries.map(([k, items]) => (
              <div key={k} className="flex gap-3">
                <div className="w-20 shrink-0 text-xs text-(--color-muted) pt-1">{STACK_LABEL[k]}</div>
                <div className="flex flex-wrap gap-1.5">
                  {items.map((t) => (
                    <Tag key={t}>{t}</Tag>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Section>

        <Section title="왜 이 언어인가">
          <p className="text-sm text-(--color-text) leading-relaxed">{company.why_language}</p>
        </Section>

        <Section title="왜 이 아키텍처인가">
          <p className="text-sm text-(--color-text) leading-relaxed">{company.why_architecture}</p>
        </Section>

        {company.deep_dive && company.deep_dive.length > 0 && (
          <Section title={`기술 심화 — 어떻게 작동하는가 (${company.deep_dive.length})`}>
            <div className="flex flex-col gap-2">
              {company.deep_dive.map((s, i) => (
                <DeepDive key={s.topic + i} section={s} defaultOpen={i < 2} />
              ))}
            </div>
          </Section>
        )}

        {company.debate && (
          <Section title="아키텍처 토론 — 설계자 ↔ 검토자 + 정리자">
            <DebateView debate={company.debate} idKey={company.key} />
          </Section>
        )}

        {company.interview && (
          <Section title="채용 전형 (지원 가이드)">
            <InterviewView interview={company.interview} />
          </Section>
        )}

        {company.github && (company.github.repos?.length || company.github.org) && (
          <Section title="공개 GitHub 코드">
            {company.github.org && (
              <a
                href={company.github.org}
                target="_blank"
                rel="noreferrer"
                className="inline-block mb-2 text-sm text-(--color-accent) hover:underline break-all"
              >
                {company.github.org.replace('https://github.com/', '@')} ↗
              </a>
            )}
            <ul className="flex flex-col gap-2">
              {(company.github.repos ?? []).map((r) => (
                <li
                  key={r.url}
                  className="rounded border border-(--color-border) bg-(--color-bg) px-3 py-2"
                >
                  <div className="flex items-center gap-2">
                    <a
                      href={r.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm font-medium text-(--color-text) hover:text-(--color-accent) hover:underline break-all"
                    >
                      {r.name}
                    </a>
                    {r.lang && (
                      <span className="text-xs text-(--color-muted) shrink-0">{r.lang}</span>
                    )}
                    {typeof r.stars === 'number' && (
                      <span className="ml-auto text-xs text-(--color-muted) shrink-0">
                        ★ {r.stars >= 1000 ? `${(r.stars / 1000).toFixed(1)}k` : r.stars}
                      </span>
                    )}
                  </div>
                  {r.desc && <p className="mt-0.5 text-xs text-(--color-muted)">{r.desc}</p>}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {company.sources.length > 0 && (
          <Section title="출처">
            <ul className="flex flex-col gap-1">
              {company.sources.map((s) => (
                <li key={s}>
                  <a
                    href={s}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm text-(--color-accent) hover:underline break-all"
                  >
                    {s} ↗
                  </a>
                </li>
              ))}
            </ul>
          </Section>
        )}
      </div>
    </div>
  )
}

const ROLE_META: Record<string, { label: string; align: string; color: string }> = {
  architect: { label: '설계자', align: 'items-start', color: 'border-(--color-accent)/40 bg-(--color-accent)/10' },
  critic: { label: '검토자', align: 'items-end', color: 'border-amber-500/40 bg-amber-500/10' },
  synthesizer: { label: '정리자', align: 'items-center', color: 'border-(--color-border) bg-(--color-bg)' },
}

function InterviewView({ interview }: { interview: Interview }) {
  return (
    <div className="flex flex-col gap-4">
      {interview.difficulty && (
        <div className="text-xs text-(--color-muted)">
          예상 난이도 <span className="text-(--color-text) font-medium">{interview.difficulty}</span>
          <span className="ml-2 opacity-70">· 공개 채용 절차·일반 패턴 기반 가이드</span>
        </div>
      )}

      {/* 전형 단계 타임라인 */}
      <ol className="flex flex-col">
        {interview.process.map((s, i) => (
          <li key={i} className="flex gap-3 pb-3 last:pb-0">
            <div className="flex flex-col items-center">
              <div className="w-6 h-6 rounded-full bg-(--color-accent) text-(--color-on-accent) text-xs font-bold flex items-center justify-center shrink-0">
                {i + 1}
              </div>
              {i < interview.process.length - 1 && (
                <div className="w-px flex-1 bg-(--color-border) my-1" />
              )}
            </div>
            <div className="min-w-0 pb-1">
              <div className="flex flex-wrap items-center gap-x-2 text-sm font-medium text-(--color-text)">
                {s.name}
                {s.duration && <span className="text-xs text-(--color-muted) font-normal">⏱ {s.duration}</span>}
                {s.format && <span className="text-xs text-(--color-muted) font-normal">· {s.format}</span>}
              </div>
              {s.detail && <p className="mt-0.5 text-sm text-(--color-muted)">{s.detail}</p>}
            </div>
          </li>
        ))}
      </ol>

      {interview.focus.length > 0 && (
        <div>
          <div className="text-xs font-medium text-(--color-muted) mb-2">이 회사가 보는 것</div>
          <div className="flex flex-wrap gap-1.5">
            {interview.focus.map((f) => (
              <Tag key={f} accent>
                {f}
              </Tag>
            ))}
          </div>
        </div>
      )}

      {interview.tips.length > 0 && (
        <div>
          <div className="text-xs font-medium text-(--color-muted) mb-2">준비 팁</div>
          <ul className="flex flex-col gap-1.5">
            {interview.tips.map((t, i) => (
              <li key={i} className="text-sm text-(--color-text) flex gap-2">
                <span className="text-(--color-accent) shrink-0">✓</span>
                <span>{t}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {interview.reviews && interview.reviews.length > 0 && (
        <div>
          <div className="text-xs font-medium text-(--color-muted) mb-2">
            공개 면접 후기 ({interview.reviews.length})
          </div>
          <ul className="flex flex-col gap-2">
            {interview.reviews.map((rv) => (
              <li
                key={rv.url}
                className="rounded border border-(--color-border) bg-(--color-bg) px-3 py-2"
              >
                <div className="flex items-center gap-2">
                  <a
                    href={rv.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm font-medium text-(--color-text) hover:text-(--color-accent) hover:underline break-all"
                  >
                    {rv.title} ↗
                  </a>
                  {rv.source && (
                    <span className="ml-auto shrink-0 text-[11px] text-(--color-muted)">
                      {rv.source}
                      {rv.date ? ` · ${rv.date}` : ''}
                    </span>
                  )}
                </div>
                {rv.summary && <p className="mt-0.5 text-xs text-(--color-muted)">{rv.summary}</p>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {interview.sources.length > 0 && (
        <p className="text-[11px] text-(--color-muted)">출처: {interview.sources.join(' · ')}</p>
      )}
    </div>
  )
}

function DebateView({ debate, idKey }: { debate: Debate; idKey: string }) {
  const [tab, setTab] = useState(0)
  const archs = debate.architectures ?? []
  // 합의 결론이 어떤 후보(변형 A/B/…)를 반영했는지 — 탭에 '채택' 표시로 연결
  const verdictText = `${debate.verdict?.chosen ?? ''} ${debate.verdict?.rationale ?? ''}`
  const isChosen = (name: string) => {
    // 후보의 변형 글자(A/B/…)를 verdict 가 "변형 A" 또는 "(A)" 형태로 언급했는지
    const m = name.match(/변형\s*([A-Z])/)
    if (!m) return false
    const L = m[1]
    return verdictText.includes(`변형 ${L}`) || verdictText.includes(`변형${L}`) || verdictText.includes(`(${L})`)
  }
  return (
    <div className="flex flex-col gap-4">
      {/* 1) 아키텍처 후보 (탭) */}
      {archs.length > 0 && (
        <div className="rounded border border-(--color-border) bg-(--color-bg) p-3">
          <div className="flex flex-wrap gap-1.5 mb-3">
            {archs.map((a, i) => (
              <button
                key={i}
                onClick={() => setTab(i)}
                className={`px-2.5 py-1 text-xs rounded border transition ${
                  tab === i
                    ? 'bg-(--color-accent) text-(--color-on-accent) border-(--color-accent) font-medium'
                    : 'bg-(--color-panel) text-(--color-text) border-(--color-border) hover:border-(--color-accent)'
                }`}
              >
                {isChosen(a.name) && <span title="합의에 반영된 후보">✓ </span>}
                {a.name}
              </button>
            ))}
          </div>
          {archs[tab] && (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-(--color-text) leading-relaxed">{archs[tab].summary}</p>
              {archs[tab].diagram && (
                <ArchitectureDiagram code={archs[tab].diagram!} idKey={`${idKey}-arch${tab}`} />
              )}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="text-xs font-medium text-(--color-accent) mb-1">장점</div>
                  <ul className="flex flex-col gap-1">
                    {archs[tab].pros.map((p, i) => (
                      <li key={i} className="text-xs text-(--color-muted) flex gap-1">
                        <span className="text-(--color-accent)">+</span> {p}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <div className="text-xs font-medium text-amber-400 mb-1">단점·리스크</div>
                  <ul className="flex flex-col gap-1">
                    {archs[tab].cons.map((c, i) => (
                      <li key={i} className="text-xs text-(--color-muted) flex gap-1">
                        <span className="text-amber-400">−</span> {c}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 2) 토론 전사 (대화) */}
      {debate.transcript?.length > 0 && (
        <div>
          <div className="text-xs font-medium text-(--color-muted) mb-2">
            토론 전사 ({debate.rounds}라운드 · {debate.transcript.length}턴)
          </div>
          <div className="flex flex-col gap-2.5">
            {debate.transcript.map((t, i) => {
              const meta = ROLE_META[t.role] ?? ROLE_META.synthesizer
              return (
                <div key={i} className={`flex flex-col ${meta.align}`}>
                  <div className={`max-w-[88%] rounded-lg border px-3 py-2 ${meta.color}`}>
                    <div className="text-[11px] font-medium text-(--color-muted) mb-1">
                      {meta.label} · R{t.round}
                    </div>
                    <div className="blog-md text-sm text-(--color-text)">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{t.text}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* 3) 합의 결론 */}
      {debate.verdict && (
        <div className="rounded border border-(--color-accent)/40 bg-(--color-accent)/5 p-3 flex flex-col gap-2">
          <div className="text-xs font-medium text-(--color-accent)">
            합의 결론 — {debate.verdict.chosen}
          </div>
          {debate.verdict.rationale && (
            <div className="blog-md text-sm text-(--color-text)">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{debate.verdict.rationale}</ReactMarkdown>
            </div>
          )}
          {debate.verdict.key_insights?.length > 0 && (
            <div>
              <div className="text-xs font-medium text-(--color-muted) mb-1">핵심 인사이트</div>
              <ul className="flex flex-col gap-1">
                {debate.verdict.key_insights.map((k, i) => (
                  <li key={i} className="text-xs text-(--color-text) flex gap-1">
                    <span className="text-(--color-accent)">›</span> {k}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {debate.verdict.open_questions?.length > 0 && (
            <div>
              <div className="text-xs font-medium text-(--color-muted) mb-1">열린 질문</div>
              <ul className="flex flex-col gap-1">
                {debate.verdict.open_questions.map((q, i) => (
                  <li key={i} className="text-xs text-(--color-muted) flex gap-1">
                    <span className="text-amber-400">?</span> {q}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function DeepDive({ section, defaultOpen }: { section: DeepDiveSection; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="rounded border border-(--color-border) bg-(--color-bg)">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm font-medium text-(--color-text) hover:text-(--color-accent)"
      >
        <span className="text-(--color-muted)">{open ? '▾' : '▸'}</span>
        {section.topic}
      </button>
      {open && (
        <div className="blog-md px-4 pb-4 pt-1 text-(--color-text)">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{section.body}</ReactMarkdown>
        </div>
      )}
    </div>
  )
}

function NavBtn({
  onClick,
  title,
  children,
}: {
  onClick?: () => void
  title: string
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      disabled={!onClick}
      title={title}
      className="w-7 h-7 flex items-center justify-center rounded border border-(--color-border) text-(--color-text) text-lg leading-none hover:border-(--color-accent) hover:text-(--color-accent) disabled:opacity-30 disabled:hover:border-(--color-border) disabled:hover:text-(--color-text) disabled:cursor-default"
    >
      {children}
    </button>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs font-medium text-(--color-muted) mb-2">{title}</div>
      {children}
    </div>
  )
}

function Tag({ children, accent }: { children: React.ReactNode; accent?: boolean }) {
  return (
    <span
      className={`px-2 py-0.5 text-xs rounded border ${
        accent
          ? 'bg-(--color-accent)/15 text-(--color-accent) border-(--color-accent)/40'
          : 'bg-(--color-bg) text-(--color-text) border-(--color-border)'
      }`}
    >
      {children}
    </span>
  )
}

function Chip({
  active,
  onClick,
  count,
  outline,
  children,
}: {
  active: boolean
  onClick: () => void
  /** 칩 뒤의 건수 */
  count?: number
  /** 켜졌을 때 칠하지 않고 붉은 테두리만(보기 전환 단추) */
  outline?: boolean
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={
        'inline-flex items-center gap-1.5 h-9 px-[17px] rounded-[18px] border text-sm font-medium tracking-[-0.3px] ' +
        (active
          ? outline
            ? 'bg-white border-(--color-accent) text-(--color-accent)'
            : 'bg-(--color-accent) border-(--color-accent) text-white'
          : 'bg-white border-[#d8d8d8] text-[#272727] hover:border-[#272727]')
      }
    >
      {children}
      {count != null && <span className={'text-xs font-normal tabular-nums ' + (active && !outline ? 'text-[#ffd9d9]' : 'text-[#999]')}>{count}</span>}
    </button>
  )
}
