import { useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Md, MdBlock } from './Md'
import { Loader, ErrorState, EmptyState, SearchInput, TechIcon, hits } from './ui'
import { goBack, navigate, onLinkClick } from '../lib/router'
import { absUrl, clip, useSeo } from '../lib/seo'
import { paths } from '../lib/urls'
import {
  LEVEL_LABEL,
  useArticle,
  useStudyIndex,
  type Article,
  type Category,
  type Confidence,
  type IndexEntry,
  type Source,
  type Table as WikiTable,
} from '../lib/useStudy'

// 기술 백과사전 — study-engine 이 사이클마다 쌓는 문서를 읽는 화면.
//
// 왜 `기술 관계·맥락` 옆에 붙였나: 관계 화면은 "Python 이 공고 2,648건에 나오고 AWS 와
// 36% 함께 쓰인다"까지 말하고 멈춘다. 거기서 한 칸 더 들어간 자리(그래서 그게 뭔데,
// 언제 그것 대신 저것인데)가 이 문서다. 그래서 둘은 같은 탭 안의 이웃 모드이고,
// 관계 상세에서 문서가 있는 기술이면 바로 이쪽으로 넘어간다.

const CONF_LABEL: Record<Confidence, string> = {
  confirmed: '출처 확인',
  inferred: '추론',
  unknown: '미확인',
}

const KIND_LABEL: Record<WikiTable['kind'], string> = {
  pinmap: '핀·포트',
  register: '레지스터',
  spec: '스펙',
  compare: '비교',
  glossary: '표',
}

export function WikiView({ slug }: { slug: string | null }) {
  const { data: index, loading, error } = useStudyIndex()

  if (slug) return <ArticleView slug={slug} index={index} />
  if (loading) return <Loader label="백과사전 불러오는 중…" />
  if (error)
    return (
      <ErrorState
        title="study/index.json 로드 실패"
        detail={error}
        hint={
          <>
            생성: <code className="text-(--color-text)">study-engine/PROMPT.md</code> 사이클 (
            <code className="text-(--color-text)">/studywiki</code>)
          </>
        }
      />
    )
  return <ArticleList index={index} />
}

// ── 목록 ────────────────────────────────────────────────────────────────
function ArticleList({ index }: { index: ReturnType<typeof useStudyIndex>['data'] }) {
  const [query, setQuery] = useState('')
  const [cat, setCat] = useState<Category | null>(null)

  const cats = index?.categories ?? {}
  const counts = useMemo(() => {
    const m = new Map<string, number>()
    for (const a of index?.articles ?? []) m.set(a.category, (m.get(a.category) ?? 0) + 1)
    return m
  }, [index])

  const shown = useMemo(() => {
    const all = index?.articles ?? []
    return all
      .filter((a) => (cat ? a.category === cat : true))
      .filter((a) => hits(query, a.title, a.one_liner, a.aliases.join(' ')))
      .sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1))
  }, [index, cat, query])

  return (
    <div className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-6">
      <div className="max-w-5xl mx-auto">
        <h2 className="text-lg font-semibold text-(--color-text)">기술 백과사전</h2>
        <p className="text-xs text-(--color-muted) mt-0.5 mb-3">
          공부하다 막히는 낱말 하나를, 그 낱말만 읽어도 끝까지 이해되게. 모든 문서는 실제 공고
          문장(<span className="text-(--color-text)">근거</span>)과 손으로 해 볼 것(
          <span className="text-(--color-text)">실습</span>)으로 끝난다.
        </p>

        <SearchInput value={query} onChange={setQuery} placeholder="낱말 검색 (예: 저항, ATmega, 멱등성)" className="mb-3" />

        <div className="flex flex-wrap gap-1.5 mb-4">
          <CatChip on={cat === null} onClick={() => setCat(null)}>
            전체 {index?.articles.length ?? 0}
          </CatChip>
          {Object.entries(cats)
            .filter(([k]) => counts.get(k))
            .map(([k, label]) => (
              <CatChip key={k} on={cat === k} onClick={() => setCat(k as Category)}>
                {label} {counts.get(k)}
              </CatChip>
            ))}
        </div>

        {shown.length === 0 ? (
          <EmptyState
            title="아직 이 낱말의 문서가 없다"
            hint={<>대기열은 <code className="text-(--color-text)">study-engine/state/QUEUE.md</code> 에 있다.</>}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {shown.map((a) => (
              <Card key={a.slug} a={a} label={cats[a.category] ?? a.category} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function Card({ a, label }: { a: IndexEntry; label: string }) {
  const to = paths.wikiArticle(a.slug)
  return (
    <a
      href={to}
      onClick={onLinkClick(to)}
      className="rounded border border-(--color-border) bg-(--color-panel) p-3 hover:border-(--color-accent) transition block"
    >
      <div className="flex items-baseline gap-2 flex-wrap">
        <span className="text-sm font-semibold text-(--color-text)">{a.title}</span>
        <Tag>{label}</Tag>
        <Tag>{LEVEL_LABEL[a.level]}</Tag>
        {a.status === 'in_progress' && <Tag accent>쓰는 중</Tag>}
      </div>
      <p className="text-xs text-(--color-muted) mt-1.5 leading-relaxed line-clamp-3">{a.one_liner}</p>
      <div className="text-[11px] text-(--color-muted) mt-2">
        절 {a.sections} · 실습 {a.drills} · {a.updated_at}
      </div>
    </a>
  )
}

// ── 문서 ────────────────────────────────────────────────────────────────
function ArticleView({ slug, index }: { slug: string; index: ReturnType<typeof useStudyIndex>['data'] }) {
  const { data: doc, loading, error } = useArticle(slug)
  const known = useMemo(() => new Set((index?.articles ?? []).map((a) => a.slug)), [index])

  useSeo(
    doc
      ? {
          title: `${doc.title} — 개발자 기술 백과사전`,
          description: clip(`${doc.one_liner} ${doc.summary}`),
          canonical: absUrl(paths.wikiArticle(doc.slug)),
        }
      : null,
  )

  if (loading) return <Loader label="문서 불러오는 중…" />
  if (error || !doc)
    return (
      <ErrorState
        title={`${slug} 문서를 못 읽었다`}
        detail={error ?? ''}
        hint={<>목록으로: <a href={paths.wiki()} onClick={onLinkClick(paths.wiki())} className="text-(--color-accent)">기술 백과사전</a></>}
      />
    )

  const cats = index?.categories ?? {}
  return (
    <div className="flex-1 min-h-0 overflow-y-auto">
      <article className="max-w-3xl mx-auto p-4 sm:p-6 pb-16">
        <button onClick={() => goBack(paths.wiki())} className="text-xs text-(--color-muted) hover:text-(--color-text) mb-3">
          ← 백과사전
        </button>

        <h1 className="text-2xl font-bold text-(--color-text) tracking-tight">{doc.title}</h1>
        {doc.title_en && <div className="text-sm text-(--color-muted) mt-0.5">{doc.title_en}</div>}
        <div className="flex flex-wrap items-center gap-1.5 mt-2">
          <Tag>{cats[doc.category] ?? doc.category}</Tag>
          <Tag>{LEVEL_LABEL[doc.level]}</Tag>
          {doc.status === 'in_progress' && <Tag accent>쓰는 중</Tag>}
          <span className="text-[11px] text-(--color-muted)">{doc.updated_at} 갱신</span>
        </div>

        <p className="mt-4 text-[15px] leading-relaxed text-(--color-text) font-medium">
          <Md>{doc.one_liner}</Md>
        </p>
        <MdBlock className="mt-3 text-sm leading-relaxed text-(--color-text)">{doc.summary}</MdBlock>

        <MarketStrip doc={doc} />
        <Toc doc={doc} />

        {(doc.sections ?? []).map((s) => (
          <section key={s.id} id={s.id} className="mt-8 scroll-mt-16">
            <h2 className="text-lg font-semibold text-(--color-text) border-b border-(--color-border) pb-1.5">
              {s.heading}
            </h2>
            <div className="blog-md mt-3 text-sm text-(--color-text)">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{s.body}</ReactMarkdown>
            </div>
            <Sources conf={s.confidence} sources={s.sources} />
          </section>
        ))}

        {(doc.tables ?? []).map((t) => (
          <section key={t.id} id={t.id} className="mt-8 scroll-mt-16">
            <h2 className="text-lg font-semibold text-(--color-text) flex items-baseline gap-2">
              {t.caption}
              <Tag>{KIND_LABEL[t.kind]}</Tag>
            </h2>
            {t.note && (
              <p className="text-xs text-(--color-muted) mt-1 leading-relaxed">
                <Md>{t.note}</Md>
              </p>
            )}
            <div className="mt-2 overflow-x-auto rounded border border-(--color-border)">
              <table className="w-full text-xs">
                <thead className="bg-(--color-panel)">
                  <tr>
                    {t.columns.map((c) => (
                      <th key={c} className="text-left font-medium text-(--color-muted) px-2.5 py-1.5 whitespace-nowrap">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {t.rows.map((row, i) => (
                    <tr key={i} className="border-t border-(--color-border)">
                      {row.map((cell, k) => (
                        <td key={k} className={`px-2.5 py-1.5 align-top ${k === 0 ? 'text-(--color-text) font-medium whitespace-nowrap' : 'text-(--color-text)'}`}>
                          <Md>{cell}</Md>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Sources conf={t.confidence} sources={t.sources} />
          </section>
        ))}

        {!!doc.when_to_use?.length && (
          <section id="when" className="mt-8 scroll-mt-16">
            <h2 className="text-lg font-semibold text-(--color-text)">언제 무엇을 고르나</h2>
            <p className="text-xs text-(--color-muted) mt-0.5">막히는 지점은 '무엇'이 아니라 '언제 그것'이다</p>
            <div className="flex flex-col gap-3 mt-3">
              {doc.when_to_use.map((u, i) => (
                <div key={i} className="rounded border border-(--color-border) bg-(--color-panel) p-3">
                  <div className="text-xs text-(--color-muted)">{u.situation}</div>
                  <div className="flex flex-wrap items-baseline gap-2 mt-1.5">
                    <span className="text-sm font-semibold text-(--color-accent)">{u.pick}</span>
                    <span className="text-xs text-(--color-muted)">대신</span>
                    <span className="text-sm text-(--color-text) line-through decoration-(--color-muted)/60">{u.over}</span>
                  </div>
                  <MdBlock className="text-sm text-(--color-text) mt-2 leading-relaxed">{u.why}</MdBlock>
                  <div className="text-xs text-(--color-muted) mt-2">
                    <span className="text-(--color-text) font-medium">대가 </span>
                    <Md>{u.tradeoff}</Md>
                  </div>
                  <Sources conf={u.confidence} sources={u.sources} />
                </div>
              ))}
            </div>
          </section>
        )}

        {!!doc.pitfalls?.length && (
          <section id="pitfalls" className="mt-8 scroll-mt-16">
            <h2 className="text-lg font-semibold text-(--color-text)">지뢰</h2>
            <p className="text-xs text-(--color-muted) mt-0.5">처음 쓰는 사람이 반드시 한 번은 밟는 것들</p>
            <div className="flex flex-col gap-2.5 mt-3">
              {doc.pitfalls.map((p, i) => (
                <div key={i} className="rounded border border-(--color-border) bg-(--color-bg) p-3">
                  <div className="text-sm font-semibold text-(--color-text)">
                    <Md>{p.trap}</Md>
                  </div>
                  <MdBlock className="text-sm text-(--color-text) mt-1.5 leading-relaxed">{p.why}</MdBlock>
                  <div className="text-sm text-(--color-text) mt-2 pl-2.5 border-l-2 border-(--color-accent)">
                    <Md>{p.fix}</Md>
                  </div>
                  <Sources sources={p.sources} />
                </div>
              ))}
            </div>
          </section>
        )}

        {!!doc.drills?.length && (
          <section id="drills" className="mt-8 scroll-mt-16">
            <h2 className="text-lg font-semibold text-(--color-text)">손으로 해 볼 것</h2>
            <p className="text-xs text-(--color-muted) mt-0.5">읽기로 끝나는 문서를 이 백과사전은 완성으로 치지 않는다</p>
            <ol className="flex flex-col gap-2.5 mt-3">
              {doc.drills.map((d, i) => (
                <li key={i} className="rounded border border-(--color-border) bg-(--color-panel) p-3">
                  <div className="flex items-baseline gap-2">
                    <span className="text-xs text-(--color-muted) tabular-nums">{i + 1}</span>
                    <span className="text-sm font-medium text-(--color-text) flex-1">
                      <Md>{d.task}</Md>
                    </span>
                    {d.hours ? <span className="text-[11px] text-(--color-muted) whitespace-nowrap">~{d.hours}시간</span> : null}
                  </div>
                  <div className="text-xs text-(--color-muted) mt-2 pl-6">
                    <span className="text-(--color-text) font-medium">끝난 지점 </span>
                    <Md>{d.done_when}</Md>
                  </div>
                  <div className="text-xs text-(--color-muted) mt-1 pl-6">
                    <span className="text-(--color-text) font-medium">왜 </span>
                    <Md>{d.why}</Md>
                  </div>
                  {d.needs && (
                    <div className="text-xs text-(--color-muted) mt-1 pl-6">
                      <span className="text-(--color-text) font-medium">준비물 </span>
                      <Md>{d.needs}</Md>
                    </div>
                  )}
                  {d.no_hardware && (
                    <div className="text-xs text-(--color-muted) mt-1 pl-6">
                      <span className="text-(--color-text) font-medium">장비가 없으면 </span>
                      <Md>{d.no_hardware}</Md>
                    </div>
                  )}
                </li>
              ))}
            </ol>
          </section>
        )}

        {!!doc.checks?.length && (
          <section id="checks" className="mt-8 scroll-mt-16">
            <h2 className="text-lg font-semibold text-(--color-text)">스스로 확인</h2>
            <p className="text-xs text-(--color-muted) mt-0.5">답할 수 있으면 이 문서는 넘어가도 된다 (답은 본문에 있다)</p>
            <ul className="flex flex-col gap-1.5 mt-3">
              {doc.checks.map((c, i) => (
                <li key={i} className="text-sm text-(--color-text) flex gap-2">
                  <span className="text-(--color-accent)">?</span>
                  <span>
                    <Md>{c}</Md>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {!!doc.terms?.length && (
          <section id="terms" className="mt-8 scroll-mt-16">
            <h2 className="text-lg font-semibold text-(--color-text)">이 문서의 낱말</h2>
            <dl className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
              {doc.terms.map((t, i) => (
                <div key={i} className="rounded border border-(--color-border) bg-(--color-bg) p-2.5">
                  <dt className="text-sm font-medium text-(--color-text)">
                    {t.term}
                    {t.en && <span className="text-xs text-(--color-muted) font-normal ml-1.5">{t.en}</span>}
                  </dt>
                  <dd className="text-xs text-(--color-muted) mt-1 leading-relaxed">
                    <Md>{t.what}</Md>
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        )}

        {!!doc.evidence?.length && (
          <section id="evidence" className="mt-8 scroll-mt-16">
            <h2 className="text-lg font-semibold text-(--color-text)">실제로 이렇게 쓰인다</h2>
            <p className="text-xs text-(--color-muted) mt-0.5">공고·기술블로그·표준 문서에 이 낱말이 박힌 문장</p>
            <div className="flex flex-col gap-2.5 mt-3">
              {doc.evidence.map((e, i) => (
                <div key={i} className="rounded border border-(--color-border) bg-(--color-panel) p-3">
                  <blockquote className="text-sm text-(--color-text) pl-2.5 border-l-2 border-(--color-border)">
                    {e.quote}
                  </blockquote>
                  <div className="text-xs text-(--color-muted) mt-2">
                    <Md>{e.what_it_shows}</Md>
                  </div>
                  <a
                    href={e.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="text-[11px] text-(--color-accent) hover:underline mt-1.5 inline-block"
                  >
                    {e.where ?? e.url} ↗
                  </a>
                </div>
              ))}
            </div>
          </section>
        )}

        {!!doc.related?.length && (
          <section id="related" className="mt-8 scroll-mt-16">
            <h2 className="text-lg font-semibold text-(--color-text)">이어지는 문서</h2>
            <ul className="flex flex-col gap-1.5 mt-3">
              {doc.related.map((r) => {
                const exists = known.has(r.slug)
                const to = paths.wikiArticle(r.slug)
                return (
                  <li key={r.slug} className="text-sm">
                    {exists ? (
                      <a href={to} onClick={onLinkClick(to)} className="text-(--color-accent) hover:underline font-medium">
                        {r.slug}
                      </a>
                    ) : (
                      // 끊긴 링크는 숨기지 않는다 — 그게 이 엔진의 다음 대기열이다.
                      <span className="text-(--color-muted) font-medium" title="아직 쓰지 않은 문서 (대기열)">
                        {r.slug} <span className="text-[11px]">· 아직 없음</span>
                      </span>
                    )}
                    <span className="text-(--color-muted)"> — </span>
                    <span className="text-(--color-text)">
                      <Md>{r.how}</Md>
                    </span>
                  </li>
                )
              })}
            </ul>
          </section>
        )}

        {!!doc.open_questions?.length && (
          <section className="mt-8">
            <h2 className="text-sm font-semibold text-(--color-muted)">못 채운 것</h2>
            <ul className="mt-2 flex flex-col gap-1.5">
              {doc.open_questions.map((q, i) => (
                <li key={i} className="text-xs text-(--color-muted) leading-relaxed">
                  · <Md>{q}</Md>
                </li>
              ))}
            </ul>
          </section>
        )}

        {!!doc.sources?.length && (
          <section className="mt-6 pt-4 border-t border-(--color-border)">
            <h2 className="text-sm font-semibold text-(--color-muted)">1차 자료</h2>
            <ul className="mt-2 flex flex-col gap-1">
              {doc.sources.map((s, i) => (
                <li key={i} className="text-xs">
                  <a href={s.url} target="_blank" rel="noreferrer noopener" className="text-(--color-accent) hover:underline">
                    {s.title}
                  </a>
                  {s.publisher && <span className="text-(--color-muted)"> · {s.publisher}</span>}
                </li>
              ))}
            </ul>
          </section>
        )}
      </article>
    </div>
  )
}

/** 수요 — tech_relations.json 에서 옮겨 온 숫자. 이 문서가 채용 데이터에 못 박힌 자리다 */
function MarketStrip({ doc }: { doc: Article }) {
  const m = doc.market
  if (!m) return null
  const to = paths.trend(m.tech)
  return (
    <div className="mt-4 rounded border border-(--color-border) bg-(--color-panel) p-3">
      <div className="flex items-baseline gap-2 flex-wrap">
        <TechIcon tech={m.tech} size={14} />
        <span className="text-sm font-semibold text-(--color-text)">공고 {m.postings.toLocaleString()}건</span>
        <span className="text-xs text-(--color-muted)">전체의 {m.pct_jobs}%</span>
        {m.layer && <Tag>{m.layer}</Tag>}
        <a href={to} onClick={onLinkClick(to)} className="text-[11px] text-(--color-accent) hover:underline ml-auto">
          기술 관계에서 보기 →
        </a>
      </div>
      {!!m.with?.length && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {m.with.map((w) => (
            <span key={w.name} className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] rounded border border-(--color-border) bg-(--color-bg) text-(--color-text)">
              {w.name}
              <span className="text-(--color-muted)">{w.pct}%</span>
            </span>
          ))}
        </div>
      )}
      <div className="text-[11px] text-(--color-muted) mt-2">{m.as_of} 기준 공고 데이터</div>
    </div>
  )
}

function Toc({ doc }: { doc: Article }) {
  const items = [
    ...(doc.sections ?? []).map((s) => ({ id: s.id, label: s.heading })),
    ...(doc.tables ?? []).map((t) => ({ id: t.id, label: t.caption })),
    ...(doc.when_to_use?.length ? [{ id: 'when', label: '언제 무엇을 고르나' }] : []),
    ...(doc.pitfalls?.length ? [{ id: 'pitfalls', label: '지뢰' }] : []),
    ...(doc.drills?.length ? [{ id: 'drills', label: '손으로 해 볼 것' }] : []),
    ...(doc.checks?.length ? [{ id: 'checks', label: '스스로 확인' }] : []),
    ...(doc.evidence?.length ? [{ id: 'evidence', label: '실제로 이렇게 쓰인다' }] : []),
  ]
  if (items.length < 3) return null
  return (
    <nav className="mt-4 rounded border border-(--color-border) bg-(--color-bg) p-3">
      <div className="text-[11px] font-medium text-(--color-muted) mb-1.5">목차</div>
      <ol className="flex flex-wrap gap-x-3 gap-y-1">
        {items.map((it, i) => (
          <li key={it.id} className="text-xs">
            <span className="text-(--color-muted) tabular-nums mr-1">{i + 1}</span>
            <a href={`#${it.id}`} className="text-(--color-text) hover:text-(--color-accent)">
              {it.label}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  )
}

function Sources({ conf, sources }: { conf?: Confidence; sources?: Source[] }) {
  if (!conf && !sources?.length) return null
  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-(--color-muted)">
      {conf && <span className="px-1.5 py-0.5 rounded border border-(--color-border) bg-(--color-bg)">{CONF_LABEL[conf]}</span>}
      {(sources ?? []).map((s, i) => (
        <a key={i} href={s.url} target="_blank" rel="noreferrer noopener" className="text-(--color-accent) hover:underline">
          {s.title}
        </a>
      ))}
    </div>
  )
}

function Tag({ children, accent }: { children: React.ReactNode; accent?: boolean }) {
  return (
    <span
      className={`text-[11px] px-1.5 py-0.5 rounded border ${
        accent
          ? 'border-(--color-accent)/40 bg-(--color-accent)/15 text-(--color-accent)'
          : 'border-(--color-border) bg-(--color-bg) text-(--color-muted)'
      }`}
    >
      {children}
    </span>
  )
}

function CatChip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-2.5 py-1 text-xs rounded-full border transition ${
        on
          ? 'border-(--color-accent) bg-(--color-accent)/15 text-(--color-accent)'
          : 'border-(--color-border) bg-(--color-bg) text-(--color-muted) hover:text-(--color-text)'
      }`}
    >
      {children}
    </button>
  )
}

/** 관계 화면(TrendView)에서 문서가 있는 기술일 때 띄우는 줄. 없으면 아무것도 안 그린다. */
export function WikiLink({ entry }: { entry: IndexEntry | null }) {
  if (!entry) return null
  const to = paths.wikiArticle(entry.slug)
  return (
    <button
      onClick={() => navigate(to)}
      className="mt-3 w-full text-left rounded border border-(--color-accent)/40 bg-(--color-accent)/10 p-3 hover:bg-(--color-accent)/15 transition"
    >
      <div className="text-xs text-(--color-accent) font-medium">백과사전 · {entry.title}</div>
      <div className="text-sm text-(--color-text) mt-1 leading-relaxed">{entry.one_liner}</div>
      <div className="text-[11px] text-(--color-muted) mt-1.5">
        절 {entry.sections} · 실습 {entry.drills} · 읽으러 가기 →
      </div>
    </button>
  )
}
