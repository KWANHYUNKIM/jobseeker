import { useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useDomainDocs, useMarkdown, useRevengIndex, type DomainDoc, type IndexEntry } from '../hooks/useReveng'
import { usePaged, PAGE_SIZE_GRID as PAGE_SIZE } from '../../../hooks/usePaged'
import { CompanyTeardown } from './CompanyTeardown'
import { goBack, onLinkClick } from '../../../utils/navigation'
import { paths } from '../../../utils/urls'
import { absUrl, clip, useSeo } from '../../../utils/seo'
import { Loader, ErrorState, EmptyState, hits } from '../../../components/ui'
import { Pager } from '../../../components/Pager'
import { SiteFooter } from '../../../components/SiteFooter'

// 카드 3열 × 4줄. 회사가 계속 쌓이는 탭이라 한 화면에 다 밀어 넣으면 곧 통 스크롤이 된다.

// 기술 역설계 — 회사가 무엇으로 돈을 벌고, 그 돈이 어떤 도메인으로 쪼개지고,
// 각 기능이 어떻게 구현되고 서로 어떻게 이어지는지.
//
// 다른 탭들은 공고 데이터를 집계해 보여준다. 여기는 성격이 다르다 — 공개 자료를 읽고
// 사람이 재구성한 내용이라, 어디까지가 회사가 말한 것이고 어디부터가 추정인지를
// 화면이 항상 같이 보여줘야 한다. 그래서 신뢰도 뱃지가 이 탭의 1급 요소다.

/**
 * @param seg 주소에서 `reveng` 다음 세그먼트들. `['toss']` 는 회사 상세,
 *   `['docs', 'same-problem-three-answers']` 는 비교 문서다.
 */
export function RevengView({ seg = [] }: { seg?: string[] }) {
  const { data, loading, error } = useRevengIndex()
  const { data: domainDocs } = useDomainDocs()
  const [country, setCountry] = useState<string | null>(null)
  const [category, setCategory] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<'recent' | 'name'>('recent')
  // 무엇을 보고 있는지는 주소가 정한다. 회사 하나하나가 공유·색인 가능한 페이지다.
  const slug = seg[0] === 'docs' ? null : (seg[0] ?? null)
  const docSlug = seg[0] === 'docs' ? (seg[1] ?? null) : null

  const companies = useMemo(() => data?.companies ?? [], [data])
  const categories = useMemo(
    () => [...new Set(companies.map((c) => c.category))].sort(),
    [companies],
  )
  const countries = useMemo(
    () => [...new Set(companies.map((c) => c.country))].sort(),
    [companies],
  )
  const shown = useMemo(
    () =>
      companies.filter(
        (c) =>
          (!country || c.country === country) &&
          (!category || c.category === category) &&
          // 회사 이름만으로는 '메시징을 파는 곳' 같은 질문에 답할 수 없다.
          // 한 줄 요약과 분류까지 걸어야 주제로 찾는 것이 된다.
          hits(query, c.name, c.name_en, c.one_liner, c.category, c.slug),
      ).sort((a, b) =>
        sort === 'name' ? (a.name_en || a.name).localeCompare(b.name_en || b.name) : a.updated_at < b.updated_at ? 1 : a.updated_at > b.updated_at ? -1 : 0,
      ),
    [companies, country, category, query, sort],
  )
  // 훅이라 아래의 조기 반환들보다 위에 있어야 한다(호출 순서가 렌더마다 같아야 한다).
  const paged = usePaged(shown, PAGE_SIZE)

  // 회사·비교문서 상세의 제목은 여기서 단다. 색인 목록(index.json)에 제목과 한 줄
  // 요약이 이미 있으므로 상세 파일을 안 읽고도 메타를 만들 수 있다.
  const entry = slug ? companies.find((c) => c.slug === slug) : null
  const doc = docSlug ? domainDocs?.docs.find((d) => d.slug === docSlug) : null
  useSeo(
    entry
      ? {
          title: `${entry.name} 기술 역설계`,
          description: clip(`${entry.name}(${entry.name_en ?? ''}) 기술 역설계 — ${entry.one_liner ?? ''}`),
          canonical: absUrl(paths.revengCompany(entry.slug)),
        }
      : doc
        ? {
            title: doc.title,
            description: clip(doc.question ?? doc.title),
            canonical: absUrl(paths.revengDoc(doc.slug)),
          }
        : null,
  )

  if (slug) return <CompanyTeardown slug={slug} featureKey={seg[1] === 'f' ? (seg[2] ?? null) : null} onBack={() => goBack(paths.reveng())} />
  if (docSlug) {
    const doc = domainDocs?.docs.find((d) => d.slug === docSlug)
    if (doc) return <DomainDocView doc={doc} docs={domainDocs?.docs ?? []} companies={companies} />
  }
  if (loading) return <Loader label="역설계 데이터 불러오는 중…" />
  if (error)
    return (
      <ErrorState
        title="reveng/index.json 로드 실패"
        detail={error}
        hint={
          <>
            엔진이 아직 한 번도 안 돌았을 수 있습니다. 확인:{' '}
            <code className="text-(--color-text)">python engine/validate.py</code>
          </>
        }
      />
    )

  const done = companies.filter((c) => c.status === 'done').length
  const countOf = (pick: (c: IndexEntry) => string) =>
    companies.reduce<Record<string, number>>((m, c) => ((m[pick(c)] = (m[pick(c)] ?? 0) + 1), m), {})
  const byCountry = countOf((c) => c.country)
  const byCategory = countOf((c) => c.category)
  const countryLabel = (k: string) => data?.countries?.[k] ?? k
  // 칩은 두 곳 이상인 나라·분야만 — 한 곳짜리까지 늘어놓으면 줄이 넘쳐 고르기가 더 어렵다(검색으로 찾으면 된다).
  // 이번 달 깊게 판 회사 — 다 판(완료) 회사 가운데 가장 최근에 갱신된 셋
  const recent = [...companies].filter((c) => c.status === 'done').sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1)).slice(0, 3)

  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[43px] pb-[90px]">
        <h1 className="text-[28px] font-bold leading-10 tracking-[-0.6px] text-[#272727]">기술 역설계</h1>
        <p className="mt-1 text-base leading-6 tracking-[-0.16px] text-[#666]">
          비즈니스 모델 → 도메인 → 기능 구현 → 시스템 연결. 공개 자료만으로 재구성하고,{' '}
          <b className="font-bold text-(--color-accent)">회사가 직접 말한 것과 추정한 것을 구분</b>해 표시해요.
        </p>

        {companies.length === 0 ? (
          <EmptyState
            title="아직 공개된 회사가 없습니다"
            hint={
              <>
                엔진이 사이클을 돌면 여기에 쌓입니다. 대기열: <code className="text-(--color-text)">engine/state/QUEUE.md</code>
              </>
            }
          />
        ) : (
          <>
            <div className="mt-[27px] grid grid-cols-2 lg:grid-cols-4 gap-[14px]">
              <Stat label="분석한 회사" value={`${companies.length}곳`} accent />
              <Stat label="분석 완료" value={`${done}곳`} />
              <Stat label="나라" value={`${countries.length}개`} />
              <Stat label="갱신" value={data?.updated_at ?? '-'} />
            </div>

            <form role="search" onSubmit={(e) => e.preventDefault()} className="mt-[26px] flex gap-2.5">
              <label className="flex-1 min-w-0 flex items-center gap-2.5 h-[52px] rounded-[26px] border border-[#c4c4c4] pl-[23px] pr-5 focus-within:border-[#272727]">
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="#272727" strokeWidth="2" aria-hidden className="shrink-0">
                  <circle cx="8.5" cy="8.5" r="5.5" />
                  <path d="M12.5 12.5 16 16" strokeLinecap="round" />
                </svg>
                <input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="회사·서비스·기술로 찾아보세요"
                  aria-label="회사 검색"
                  className="flex-1 min-w-0 bg-transparent text-[15px] tracking-[-0.16px] text-[#272727] placeholder:text-[#999] outline-none"
                />
              </label>
              <button type="submit" className="shrink-0 w-[110px] h-[52px] rounded-[26px] border-2 border-(--color-accent) text-base font-bold text-(--color-accent) hover:bg-(--color-accent-weak)">
                검색
              </button>
            </form>

            <ChipRow label="나라">
              <FilterChip active={!country} count={companies.length} onClick={() => setCountry(null)}>
                전체
              </FilterChip>
              {[...countries].filter((k) => (byCountry[k] ?? 0) > 1 || k === country).sort((a, b) => (byCountry[b] ?? 0) - (byCountry[a] ?? 0)).map((k) => (
                <FilterChip key={k} active={country === k} count={byCountry[k] ?? 0} onClick={() => setCountry(country === k ? null : k)}>
                  {countryLabel(k)}
                </FilterChip>
              ))}
            </ChipRow>
            <ChipRow label="분야">
              <FilterChip active={!category} onClick={() => setCategory(null)}>
                전체
              </FilterChip>
              {[...categories].filter((k) => (byCategory[k] ?? 0) > 1 || k === category).sort((a, b) => (byCategory[b] ?? 0) - (byCategory[a] ?? 0)).map((k) => (
                <FilterChip key={k} active={category === k} count={byCategory[k] ?? 0} onClick={() => setCategory(category === k ? null : k)}>
                  {k}
                </FilterChip>
              ))}
            </ChipRow>

            {recent.length > 0 && (
              <section className="mt-[47px]">
                <h2 className="text-[22px] font-bold leading-8 tracking-[-0.22px] text-[#272727]">
                  이번 달 <span className="font-black text-(--color-accent)">깊게 판</span> 회사
                </h2>
                <div className="mt-5 grid md:grid-cols-3 gap-4">
                  {recent.map((c, i) => (
                    <FeatureCard key={c.slug} c={c} bg={FEATURE_BG[i % 3]} countryLabel={countryLabel(c.country)} />
                  ))}
                </div>
              </section>
            )}

            <section className="mt-[58px]">
              <div className="flex items-center justify-between pb-4 border-b-2 border-[#272727]">
                <h2 className="text-[22px] font-bold leading-8 tracking-[-0.22px] text-[#272727]">전체 회사</h2>
                <label className="relative inline-flex items-center h-9 rounded-md border border-[#d8d8d8] bg-white">
                  <select
                    aria-label="정렬"
                    value={sort}
                    onChange={(e) => setSort(e.target.value as 'recent' | 'name')}
                    className="appearance-none h-full bg-transparent pl-[15px] pr-[33px] text-sm tracking-[-0.16px] text-[#272727] outline-none cursor-pointer"
                  >
                    <option value="recent">최근 갱신순</option>
                    <option value="name">이름순</option>
                  </select>
                  <svg className="pointer-events-none absolute right-[14px]" width="10" height="8" viewBox="0 0 10 8" fill="none" stroke="#272727" strokeWidth="1.5" strokeLinecap="round" aria-hidden>
                    <path d="M1.5 2.5 5 6l3.5-3.5" />
                  </svg>
                </label>
              </div>
              <div data-reveng-top className="mt-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 scroll-mt-4">
                {paged.slice.map((c) => (
                  <CompanyCard key={c.slug} c={c} countryLabel={countryLabel(c.country)} />
                ))}
              </div>
              {shown.length === 0 ? (
                <p className="py-12 text-center text-sm text-[#999]">조건에 맞는 회사가 없어요.</p>
              ) : (
                <Pager page={paged.page} totalPages={paged.totalPages} onChange={paged.setPage} scrollTo="[data-reveng-top]" />
              )}
            </section>

            <section className="rounded-[30px] border border-[#e2e8ec] px-[35px] pt-[31px] pb-[31px]">
              <h2 className="text-xl font-bold leading-[29px] tracking-[-0.16px] text-[#272727]">이렇게 읽어요</h2>
              <ol className="mt-5 flex flex-col md:flex-row md:items-center gap-3">
                {(
                  [
                    ['비즈니스 모델', '누구에게 무엇을 팔아 돈을 버는가'],
                    ['도메인', '그 사업이 다루는 데이터와 규칙'],
                    ['기능 구현', '핵심 기능 3개를 골라 구현을 재구성'],
                    ['시스템 연결', '기능들이 어떤 구조로 이어지는가'],
                  ] as const
                ).map(([t, d], i) => (
                  <li key={t} className="contents">
                    {i > 0 && (
                      <span aria-hidden className="hidden md:block text-xl text-[#c4c4c4]">
                        →
                      </span>
                    )}
                    <div className="flex-1 min-h-[113px] rounded-[18px] bg-[#f7f9fa] px-5 pt-[21px] pb-4">
                      <div className="text-sm font-bold text-(--color-accent)">{i + 1}</div>
                      <div className="mt-1 text-[17px] font-bold leading-[25px] text-[#272727]">{t}</div>
                      <div className="mt-1 text-sm text-[#666]">{d}</div>
                    </div>
                  </li>
                ))}
              </ol>
              <div className="mt-[18px] flex flex-wrap gap-2">
                <span className="rounded bg-[#eaf8f0] px-[7px] text-[13px] leading-[22px] text-[#1e9e5a]">회사가 직접 말한 것</span>
                <span className="rounded bg-[#f1efff] px-[7px] text-[13px] leading-[22px] text-[#5b4fd6]">공개 자료로 추정한 것</span>
              </div>
            </section>

            {domainDocs && domainDocs.docs.length > 0 && (
              <section className="mt-[47px]">
                <h2 className="text-[22px] font-bold leading-8 tracking-[-0.22px] text-[#272727]">
                  도메인 비교 <span className="ml-2 text-sm font-normal text-[#999]">회사 페이지가 한 회사를 세로로 읽는다면, 여기는 한 문제를 가로로 읽어요</span>
                </h2>
                <div className="mt-5 grid sm:grid-cols-2 gap-4">
                  {domainDocs.docs.map((doc) => (
                    <a
                      key={doc.slug}
                      href={paths.revengDoc(doc.slug)}
                      onClick={onLinkClick(paths.revengDoc(doc.slug))}
                      className="block rounded-[24px] border border-[#e2e8ec] px-6 py-5 hover:border-[#999]"
                    >
                      <div className="text-[17px] font-bold text-[#272727]">{doc.title}</div>
                      {doc.question && <p className="mt-1.5 text-sm leading-relaxed text-[#666]">{doc.question}</p>}
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {doc.features.map((f) => (
                          <span key={f} className="rounded bg-[#f4f4f4] px-[7px] text-[13px] leading-[22px] text-[#474747]">
                            {f}
                          </span>
                        ))}
                      </div>
                    </a>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </div>
      <SiteFooter updated={data?.updated_at} sources="각 사 공개 자료(엔지니어링 블로그·발표·문서)" />
    </div>
  )
}

// CommonMark 의 강조 규칙은 '**"잘못됐을 때"**에' 처럼 닫는 별표 앞이 문장부호이고 뒤가 한글이면
// 강조로 안 본다(한국어 문서에서 흔하다). 링크 문법은 그 규칙이 없어서, 굵은 글을 '#strong' 링크로
// 바꿔 넘기고 a 렌더러가 다시 strong 으로 그린다. 코드 블록 안은 건드리지 않는다.
const STRONG = '#strong'
function strongAsLink(md: string): string {
  return md
    .split(/(```[\s\S]*?```)/)
    .map((part, i) => (i % 2 ? part : part.replace(/\*\*([^*\n]+?)\*\*/g, (_, x: string) => `[${x}](${STRONG})`)))
    .join('')
}

function DomainDocView({ doc, docs, companies }: { doc: DomainDoc; docs: DomainDoc[]; companies: IndexEntry[] }) {
  const { text, loading, error } = useMarkdown(`/reveng/domains/${doc.file}`)
  // 파일은 단독으로도 읽히도록 H1 과 '비교 대상' 인용을 갖고 있다. 화면에서는 위 띠가 둘을
  // 대신 보여주므로 첫 H1 과 바로 뒤 인용 한 덩어리를 걷어낸다.
  const raw = strongAsLink((text ?? '').replace(/\r\n/g, '\n'))
  const lead = raw.match(/^#\s.*\n+((?:>.*\n)+)/)
  const body = raw.replace(/^#\s.*\n+/, '').replace(/^(?:>.*\n)+/, '')
  const heads = useMemo(() => [...body.matchAll(/^##\s+(.+)$/gm)].map((m) => m[1].replace(/[*`]/g, '').trim()), [body])
  const others = useMemo(() => {
    const i = docs.findIndex((d) => d.slug === doc.slug)
    return [...docs.slice(i + 1), ...docs.slice(0, Math.max(i, 0))].slice(0, 2)
  }, [docs, doc.slug])
  const cards = doc.companies.map((slug) => {
    const c = companies.find((x) => x.slug === slug)
    const name = c?.name ?? slug
    // 인용의 '토스 `payment-approval`' 에서 그 회사의 첫 기능을 읽는다. 없으면 비워 둔다.
    const esc = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const feat = lead?.[1].match(new RegExp(esc + '\\s*`([^`]+)`'))?.[1] ?? ''
    return { slug, name, domain: c?.domain, feat }
  })
  const featOf = new Map(cards.map((c) => [c.name, c.feat]))
  const plain = (n: React.ReactNode): string => (Array.isArray(n) ? n.map(plain).join('') : typeof n === 'string' ? n : n && typeof n === 'object' && 'props' in n ? plain((n.props as { children?: React.ReactNode }).children) : '')
  const jump = (i: number) => document.getElementById(`doc-h-${i}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })

  return (
    <div data-scroll className="flex-1 min-h-0 overflow-y-auto bg-white">
      <div className="jd-container pt-11 pb-[90px]">
        <nav aria-label="경로" className="text-sm text-[#777]">
          <a href={paths.reveng()} onClick={onLinkClick(paths.reveng())} className="hover:text-[#272727]">
            기술 역설계
          </a>
          {' › 도메인 비교'}
        </nav>

        <header className="mt-5 rounded-[30px] bg-[#f7f9fa] px-[38px] pt-[38px] pb-[34px]">
          <span className="inline-block rounded bg-[#f67979] px-2 text-[13px] leading-[22px] font-medium text-white">도메인 비교 문서</span>
          <h1 className="mt-2 text-[34px] font-bold leading-[50px] tracking-[-0.6px] text-[#272727] break-keep">{doc.title}</h1>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {cards.map((c) => (
              <a
                key={c.slug}
                href={paths.revengCompany(c.slug)}
                onClick={onLinkClick(paths.revengCompany(c.slug))}
                className="flex items-center gap-3 h-[76px] rounded-[18px] bg-white px-4 hover:shadow-[0_2px_10px_rgba(0,0,0,0.06)]"
              >
                <CompanyLogo domain={c.domain} name={c.name} size={40} />
                <span className="min-w-0">
                  <span className="block truncate text-base font-bold leading-6 text-[#272727]">{c.name}</span>
                  {c.feat && <span className="block truncate text-xs text-[#888]">{c.feat}</span>}
                </span>
              </a>
            ))}
          </div>
          <p className="mt-5 text-sm text-[#666]">
            각 회사 페이지에서 <span className="rounded bg-[#eaf8f0] px-[7px] text-[13px] leading-[22px] text-[#1e9e5a]">확인</span> 으로 정리한 사실만
            엮었어요. 비교에서 나오는 해석은 <span className="rounded bg-[#f1efff] px-[7px] text-[13px] leading-[22px] text-[#5b4fd6]">추정</span> 으로
            표시했어요.
          </p>
        </header>

        <div className="mt-9 flex flex-col lg:flex-row gap-7 items-start">
          <article className="w-full lg:flex-1 min-w-0">
            {loading ? (
              <Loader label="비교 문서 불러오는 중…" />
            ) : error ? (
              <ErrorState title={`reveng/domains/${doc.file} 로드 실패`} detail={error} />
            ) : (
              <div className="blog-md reveng-doc">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    a: ({ href, children }) =>
                      href === STRONG ? <strong>{children}</strong> : <a href={href} target="_blank" rel="noreferrer noopener">{children}</a>,
                    h2: ({ children }) => <h2 id={`doc-h-${heads.indexOf(plain(children).trim())}`}>{children}</h2>,
                    // 표 머리의 '토스 `payment-approval`' 은 이름과 기능을 두 줄로 나눠 띠의 카드와 맞춘다.
                    th: ({ children }) => {
                      const parts = Array.isArray(children) ? children : [children]
                      const name = typeof parts[0] === 'string' ? parts[0].trim() : null
                      if (name && featOf.has(name))
                        return (
                          <th>
                            <span className="block">{name}</span>
                            <span className="block text-xs font-normal text-[#999]">{featOf.get(name)}</span>
                          </th>
                        )
                      return <th>{children}</th>
                    },
                  }}
                >
                  {body}
                </ReactMarkdown>
              </div>
            )}
          </article>

          <aside className="w-full lg:w-[348px] shrink-0 flex flex-col gap-4 lg:sticky lg:top-6">
            {heads.length > 0 && (
              <section className="rounded-[22px] border border-[#e2e8ec] bg-white px-[23px] pt-[23px] pb-4">
                <h3 className="text-[17px] font-bold text-[#272727]">이 문서의 차례</h3>
                <ol className="mt-3 flex flex-col gap-1">
                  {heads.map((h, i) => (
                    <li key={i}>
                      <button
                        type="button"
                        onClick={() => jump(i)}
                        className={'w-full text-left pl-3.5 py-1.5 text-sm ' + (i === 0 ? 'font-medium text-(--color-accent)' : 'text-[#666] hover:text-[#272727]')}
                      >
                        {h}
                      </button>
                    </li>
                  ))}
                </ol>
              </section>
            )}
            {others.length > 0 && (
              <section className="rounded-[22px] border border-[#e2e8ec] bg-white px-[23px] pt-[23px] pb-2">
                <h3 className="text-[17px] font-bold text-[#272727]">다른 도메인 비교</h3>
                <ul className="mt-2">
                  {others.map((d) => (
                    <li key={d.slug} className="border-b border-[#f1f3f5] last:border-0">
                      <a
                        href={paths.revengDoc(d.slug)}
                        onClick={onLinkClick(paths.revengDoc(d.slug))}
                        className="flex items-center gap-3 py-3.5 text-sm font-medium leading-5 text-[#272727] hover:underline underline-offset-2"
                      >
                        <span className="min-w-0 flex-1">{d.title}</span>
                        <svg width="8" height="10" viewBox="0 0 8 10" fill="none" stroke="#272727" strokeWidth="1.5" strokeLinecap="round" aria-hidden className="shrink-0">
                          <path d="M2.5 1.5 6 5l-3.5 3.5" />
                        </svg>
                      </a>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </aside>
        </div>
      </div>
      <SiteFooter sources="각 사 공개 자료(엔지니어링 블로그·발표·문서)" />
    </div>
  )
}

// 회사 로고. 도메인만 알면 되도록 파비콘 서비스를 쓴다 — 22개 회사의 로고 파일을
// 직접 받아 두면 저작권과 갱신을 우리가 떠안게 된다.
// 네트워크가 막히거나 도메인이 없으면 첫 글자 마크로 조용히 물러선다.
export function CompanyLogo({
  domain,
  name,
  size = 28,
}: {
  domain?: string
  name: string
  size?: number
}) {
  const [failed, setFailed] = useState(false)
  const box = { width: size, height: size }

  if (!domain || failed) {
    return (
      <span
        style={box}
        className="shrink-0 grid place-items-center rounded border border-(--color-border) bg-(--color-bg) text-(--color-muted) font-semibold"
        aria-hidden
      >
        <span style={{ fontSize: size * 0.45 }}>{name.slice(0, 1)}</span>
      </span>
    )
  }
  return (
    <img
      src={`https://www.google.com/s2/favicons?domain=${domain}&sz=64`}
      alt=""
      width={size}
      height={size}
      loading="lazy"
      onError={() => setFailed(true)}
      style={box}
      className="shrink-0 rounded border border-(--color-border) bg-(--color-bg) object-contain"
    />
  )
}

const FEATURE_BG = ['#fff1e8', '#eef3ff', '#eaf7f0']

/** 카드 머리 — 영문 이름을 크게, 다르면 원래 이름을 작게(데브시스터즈 · Devsisters). */
const titleOf = (c: IndexEntry) => c.name_en || c.name
const subOf = (c: IndexEntry) => (c.name_en && c.name_en !== c.name ? c.name : '')

function StatusPill({ done }: { done: boolean }) {
  return (
    <span
      className={'shrink-0 rounded px-[7px] text-[13px] leading-[22px] ' + (done ? 'bg-[#eaf8f0] text-[#1e9e5a]' : 'bg-[#eef4ff] text-[#3d6ae0]')}
      title={done ? '도메인이 모두 채워짐' : '아직 파는 중'}
    >
      {done ? '완료' : '진행 중'}
    </span>
  )
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className={'h-[108px] rounded-[20px] border px-[25px] pt-[21px] ' + (accent ? 'bg-(--color-accent-weak) border-[#ffd5d5]' : 'border-[#e2e8ec]')}>
      <div className="text-sm text-[#777]">{label}</div>
      <div className={'mt-1 text-[28px] font-bold leading-10 tracking-[-0.16px] tabular-nums ' + (accent ? 'text-(--color-accent)' : 'text-[#272727]')}>{value}</div>
    </div>
  )
}

function ChipRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mt-4 flex items-start gap-[28px]">
      <span className="shrink-0 pt-[7px] text-[15px] font-bold text-[#272727]">{label}</span>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  )
}

/** 이번 달 깊게 판 회사 — 색 바탕 큰 카드. */
function FeatureCard({ c, bg, countryLabel }: { c: IndexEntry; bg: string; countryLabel: string }) {
  const to = paths.revengCompany(c.slug)
  return (
    <a href={to} onClick={onLinkClick(to)} className="home-press flex flex-col h-[280px] rounded-[26px] px-7 pt-7 pb-6" style={{ background: bg }}>
      <span className="flex items-start gap-[14px]">
        <span className="grid place-items-center w-14 h-14 rounded-[14px] bg-white overflow-hidden shrink-0">
          <CompanyLogo domain={c.domain} name={c.name} size={56} />
        </span>
        <span className="min-w-0 flex-1 pt-[3px]">
          <span className="block text-xl font-bold leading-[29px] text-[#272727] truncate">{titleOf(c)}</span>
          <span className="block text-sm text-[#666]">
            {countryLabel} · {c.category}
          </span>
        </span>
        <span className="mt-4">
          <StatusPill done={c.status === 'done'} />
        </span>
      </span>
      <span className="mt-5 line-clamp-3 text-base leading-[25px] tracking-[-0.16px] text-[#272727]">{c.one_liner}</span>
      <span className="mt-auto flex justify-between text-[13px] text-[#777] tabular-nums">
        <span>기능 {c.features_done}개 분석</span>
        <span>{c.updated_at}</span>
      </span>
    </a>
  )
}

// 카드는 버튼이 아니라 링크다 — 회사마다 주소가 있어야 공유도 되고 색인도 된다.
function CompanyCard({ c, countryLabel }: { c: IndexEntry; countryLabel: string }) {
  const to = paths.revengCompany(c.slug)
  return (
    <a href={to} onClick={onLinkClick(to)} className="block h-[210px] rounded-3xl border border-[#e2e8ec] bg-white px-[25px] pt-[23px] hover:border-[#999] transition-colors">
      <div className="flex items-start gap-3">
        <span className="grid place-items-center w-12 h-12 rounded-xl overflow-hidden shrink-0">
          <CompanyLogo domain={c.domain} name={c.name} size={48} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-1.5 min-w-0">
            <span className="text-[17px] font-bold leading-[25px] text-[#272727] truncate">{titleOf(c)}</span>
            {subOf(c) && <span className="text-xs text-[#999] truncate">{subOf(c)}</span>}
          </div>
          <div className="mt-0.5 text-[13px] text-[#777]">
            {countryLabel} · {c.category} · 기능 {c.features_done}
          </div>
        </div>
        <span className="mt-[13px]">
          <StatusPill done={c.status === 'done'} />
        </span>
      </div>
      <p className="mt-[19px] line-clamp-3 text-sm leading-[22px] tracking-[-0.16px] text-[#474747]">{c.one_liner}</p>
    </a>
  )
}

function FilterChip({ active, count, onClick, children }: { active: boolean; count?: number; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={
        'inline-flex items-center gap-1.5 h-9 px-[17px] rounded-[18px] border text-sm font-medium tracking-[-0.3px] ' +
        (active ? 'bg-(--color-accent) border-(--color-accent) text-white' : 'bg-white border-[#d8d8d8] text-[#272727] hover:border-[#272727]')
      }
    >
      {children}
      {count != null && <span className={'text-xs font-normal tabular-nums ' + (active ? 'text-[#ffd9d9]' : 'text-[#999]')}>{count}</span>}
    </button>
  )
}
