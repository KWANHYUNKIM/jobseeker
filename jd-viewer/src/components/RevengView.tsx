import { useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useDomainDocs, useMarkdown, useRevengIndex, type IndexEntry } from '../lib/useReveng'
import { usePaged } from '../lib/usePaged'
import { CompanyTeardown } from './CompanyTeardown'
import { Loader, ErrorState, EmptyState, Pagination } from './ui'

// 카드 3열 × 4줄. 회사가 계속 쌓이는 탭이라 한 화면에 다 밀어 넣으면 곧 통 스크롤이 된다.
const PAGE_SIZE = 12

// 기술 역설계 — 회사가 무엇으로 돈을 벌고, 그 돈이 어떤 도메인으로 쪼개지고,
// 각 기능이 어떻게 구현되고 서로 어떻게 이어지는지.
//
// 다른 탭들은 공고 데이터를 집계해 보여준다. 여기는 성격이 다르다 — 공개 자료를 읽고
// 사람이 재구성한 내용이라, 어디까지가 회사가 말한 것이고 어디부터가 추정인지를
// 화면이 항상 같이 보여줘야 한다. 그래서 신뢰도 뱃지가 이 탭의 1급 요소다.

export function RevengView() {
  const { data, loading, error } = useRevengIndex()
  const { data: domainDocs } = useDomainDocs()
  const [slug, setSlug] = useState<string | null>(null)
  const [docSlug, setDocSlug] = useState<string | null>(null)
  const [country, setCountry] = useState<string | null>(null)
  const [category, setCategory] = useState<string | null>(null)

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
        (c) => (!country || c.country === country) && (!category || c.category === category),
      ),
    [companies, country, category],
  )
  // 훅이라 아래의 조기 반환들보다 위에 있어야 한다(호출 순서가 렌더마다 같아야 한다).
  const paged = usePaged(shown, PAGE_SIZE)

  if (slug) return <CompanyTeardown slug={slug} onBack={() => setSlug(null)} />
  if (docSlug) {
    const doc = domainDocs?.docs.find((d) => d.slug === docSlug)
    if (doc) return <DomainDocView file={doc.file} title={doc.title} onBack={() => setDocSlug(null)} />
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

  return (
    <div data-scroll className="flex flex-col flex-1 min-h-0 min-w-0 overflow-y-auto jd-panel">
      <header className="px-4 py-3 border-b border-(--color-border) bg-(--color-panel)/60">
        <h2 className="text-base font-semibold text-(--color-text)"><span className="jd-head jd-head-lg">기술 역설계</span></h2>
        <p className="text-xs text-(--color-muted) mt-0.5">
          비즈니스 모델 → 도메인 → 기능 구현 → 시스템 연결. 공개 자료만으로 재구성하고,
          회사가 직접 말한 것과 추정한 것을 구분해 표시합니다.
          {data?.updated_at && <span className="ml-1">· 갱신 {data.updated_at}</span>}
        </p>
      </header>

      {companies.length === 0 ? (
        <EmptyState
          title="아직 공개된 회사가 없습니다"
          hint={
            <>
              엔진이 사이클을 돌면 여기에 쌓입니다. 대기열:{' '}
              <code className="text-(--color-text)">engine/state/QUEUE.md</code>
            </>
          }
        />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-1.5 px-4 py-2 border-b border-(--color-border)">
            <FilterChip active={!country && !category} onClick={() => { setCountry(null); setCategory(null) }}>
              전체 {companies.length}
            </FilterChip>
            <span className="w-px h-4 bg-(--color-border) mx-1" />
            {countries.map((k) => (
              <FilterChip key={k} active={country === k} onClick={() => setCountry(country === k ? null : k)}>
                {data?.countries?.[k] ?? k}
              </FilterChip>
            ))}
            <span className="w-px h-4 bg-(--color-border) mx-1" />
            {categories.map((k) => (
              <FilterChip key={k} active={category === k} onClick={() => setCategory(category === k ? null : k)}>
                {k}
              </FilterChip>
            ))}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 p-4">
            {paged.slice.map((c) => (
              <CompanyCard key={c.slug} c={c} countryLabel={data?.countries?.[c.country] ?? c.country} onOpen={() => setSlug(c.slug)} />
            ))}
          </div>
          {shown.length === 0 ? (
            <p className="px-4 pb-4 text-sm text-(--color-muted)">조건에 맞는 회사가 없습니다.</p>
          ) : (
            // 아래에 비교 문서·도메인 목록이 이어지므로 바닥에 고정하지 않는다 —
            // 고정하면 그 절들 위에 계속 떠 있게 된다.
            <Pagination
              page={paged.page}
              totalPages={paged.totalPages}
              total={shown.length}
              pageSize={PAGE_SIZE}
              unit="곳"
              sticky={false}
              onChange={paged.setPage}
            />
          )}

          {domainDocs && domainDocs.docs.length > 0 && (
            <section className="px-4 pb-4">
              <h3 className="text-sm font-semibold text-(--color-text) mb-2">
                도메인 비교{' '}
                <span className="text-xs font-normal text-(--color-muted)">
                  회사 페이지가 한 회사를 세로로 읽는다면, 여기는 한 문제를 가로로 읽는다
                </span>
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {domainDocs.docs.map((doc) => (
                  <button
                    key={doc.slug}
                    onClick={() => setDocSlug(doc.slug)}
                    className="text-left rounded-lg border border-(--color-border) bg-(--color-panel) p-3 hover:border-(--color-accent) transition-colors"
                  >
                    <div className="text-sm font-medium text-(--color-text)">{doc.title}</div>
                    {doc.question && (
                      <p className="text-xs text-(--color-muted) mt-1 leading-relaxed">{doc.question}</p>
                    )}
                    <div className="flex flex-wrap gap-1 mt-2">
                      {doc.features.map((f) => (
                        <span
                          key={f}
                          className="text-xs px-1.5 py-0.5 rounded bg-(--color-bg) border border-(--color-border) text-(--color-muted)"
                        >
                          {f}
                        </span>
                      ))}
                    </div>
                  </button>
                ))}
              </div>
            </section>
          )}

          {data && data.domains.length > 0 && (
            <section className="px-4 pb-6">
              <h3 className="text-sm font-semibold text-(--color-text) mb-2">
                지금까지 나온 도메인{' '}
                <span className="text-xs font-normal text-(--color-muted)">
                  비교 문서가 아직 없는 축은 여기서 후보로 쌓인다
                </span>
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {data.domains.map((d) => (
                  <span
                    key={d}
                    className="px-2 py-0.5 rounded border border-(--color-border) text-xs text-(--color-muted)"
                  >
                    {d}
                  </span>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}

function DomainDocView({
  file,
  title,
  onBack,
}: {
  file: string
  title: string
  onBack: () => void
}) {
  const { text, loading, error } = useMarkdown(`/reveng/domains/${file}`)
  // 파일은 단독으로도 읽히도록 H1 을 갖고 있다. 화면에서는 헤더가 이미 제목을 보여주므로
  // 첫 H1 한 줄만 걷어낸다.
  const body = text?.replace(/^#\s.*\n/, '') ?? ''
  return (
    <div className="flex flex-col flex-1 min-h-0 min-w-0 overflow-y-auto">
      <header className="px-4 py-3 border-b border-(--color-border) bg-(--color-panel) sticky top-0 z-10">
        <button onClick={onBack} className="text-xs text-(--color-muted) hover:text-(--color-accent) mb-1">
          ← 회사 목록
        </button>
        <h2 className="text-lg font-semibold text-(--color-text)"><span className="jd-head">{title}</span></h2>
      </header>
      <div className="p-4 max-w-3xl">
        {loading ? (
          <Loader label="비교 문서 불러오는 중…" />
        ) : error ? (
          <ErrorState title={`reveng/domains/${file} 로드 실패`} detail={error} />
        ) : (
          <div className="blog-md text-sm text-(--color-text)">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
          </div>
        )}
      </div>
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

function CompanyCard({
  c,
  countryLabel,
  onOpen,
}: {
  c: IndexEntry
  countryLabel: string
  onOpen: () => void
}) {
  return (
    <button
      onClick={onOpen}
      className="text-left rounded-lg border border-(--color-border) bg-(--color-panel) p-3 hover:border-(--color-accent) transition-colors"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <CompanyLogo domain={c.domain} name={c.name} />
          <div className="min-w-0">
            <div className="font-semibold text-(--color-text) truncate">{c.name}</div>
            <div className="text-xs text-(--color-muted) truncate">{c.name_en}</div>
          </div>
        </div>
        <span
          className={
            'shrink-0 px-1.5 py-0.5 rounded text-xs border ' +
            (c.status === 'done'
              ? 'border-(--color-accent)/40 text-(--color-accent)'
              : 'border-(--color-border) text-(--color-muted)')
          }
          title={c.status === 'done' ? '도메인이 모두 채워짐' : '아직 파는 중'}
        >
          {c.status === 'done' ? '완료' : '진행 중'}
        </span>
      </div>
      <p className="text-xs text-(--color-muted) mt-2 line-clamp-2">{c.one_liner}</p>
      <div className="flex items-center gap-1.5 mt-2.5 text-xs text-(--color-muted)">
        <span className="px-1.5 py-0.5 rounded bg-(--color-bg) border border-(--color-border)">
          {countryLabel}
        </span>
        <span className="px-1.5 py-0.5 rounded bg-(--color-bg) border border-(--color-border)">
          {c.category}
        </span>
        <span className="ml-auto tabular-nums">기능 {c.features_done}</span>
      </div>
    </button>
  )
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={
        'px-2 py-0.5 rounded text-xs border transition-colors ' +
        (active
          ? 'border-(--color-accent) text-(--color-accent)'
          : 'border-(--color-border) text-(--color-muted) hover:text-(--color-text)')
      }
    >
      {children}
    </button>
  )
}
