import { useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Md } from './Md'
import { Loader, ErrorState } from './ui'
import { navigate, onLinkClick } from '../lib/router'
import { absUrl, clip, useSeo } from '../lib/seo'
import { paths } from '../lib/urls'
import {
  neighbors,
  normEnv,
  normList,
  rememberLast,
  sourceLabel,
  totalMinutes,
  useFlatToc,
  useLastRead,
  usePage,
  useReading,
  useShelf,
  useToc,
  type Block,
  type BookToc,
  type Drill,
  type Page,
  type Quiz,
  type SectionStatus,
  type ShelfBook,
  type ShelfTrack,
  type Term,
  type TocChapter,
} from '../lib/useBook'

// 책 — 위키독스처럼 '차례가 있는 한 권' 을 읽는 화면.
//
// 이 화면이 앞의 백과사전과 다른 점은 딱 하나다: **순서가 있다.**
// 그래서 화면 구성도 통째로 다르다.
//   - 왼쪽에 차례가 상주한다. 지금 어디쯤인지가 늘 보여야 한다.
//   - 본문 아래에 이전/다음이 있다. 책은 검색해서 오는 게 아니라 이어서 읽는 것이다.
//   - 읽은 절을 기억한다(브라우저에만). 며칠에 걸쳐 읽는 물건이라 자리를 잃으면 안 된다.
//
// 그리고 이 책은 색인시키지 않는다 — 아래 useSeo 가 전부 noindex 를 건다.
// 남 보라고 쓰는 글이 아니라서, 검색에 걸려 봐야 좋을 게 없다.
const NOINDEX = 'noindex, nofollow'

export function BookView({ seg }: { seg: string[] }) {
  const bookId = seg[0] ?? null
  const pageId = seg[1] ?? null

  if (!bookId) return <Shelf />
  if (!pageId) return <Cover bookId={bookId} />
  return <Reader bookId={bookId} pageId={pageId} />
}

// ── 서가 ────────────────────────────────────────────────────────────────
// 책이 열 권을 넘어가면서 카드를 한 줄로 늘어놓는 것만으로는 안 됐다.
// 「스프링 DB 2편」 다음에 「Practical Testing」 이 오는 이유가 화면에 안 보이고,
// 도커·쿠버네티스처럼 스프링과 아무 상관 없는 책이 같은 줄에 섞이기 시작했다.
// 그래서 서가에도 왼쪽 차례를 뒀다 — 갈래(track)로 묶고, 갈래마다 얼마나 찼는지를 같이 보인다.
function Shelf() {
  const { data, loading, error } = useShelf()
  const [track, setTrack] = useState<string | null>(null)

  useSeo({ title: '내 책장', description: '혼자 읽으려고 쓰는 책들', robots: NOINDEX, canonical: absUrl(paths.wiki()) })

  const groups = useMemo(() => shelfGroups(data), [data])

  if (loading) return <Loader label="책장 여는 중…" />
  if (error || !data)
    return (
      <ErrorState
        title="book/index.json 을 못 읽었다"
        detail={error ?? ''}
        hint={<>경로: <code className="text-(--color-text)">jd-viewer/public/book/index.json</code></>}
      />
    )

  // 고른 갈래가 사라졌으면(파일이 바뀌었으면) 전체로 되돌린다
  const picked = groups.some((g) => g.id === track) ? track : null
  const shown = picked ? groups.filter((g) => g.id === picked) : groups
  const all = tally(data.books)

  return (
    <div className="flex flex-1 min-h-0">
      <ShelfNav groups={groups} all={all} picked={picked} onPick={setTrack} />

      <div className="flex-1 min-w-0 overflow-y-auto p-4 sm:p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-2xl font-bold text-(--color-text) tracking-tight">내 책장</h1>
          {data.note && <p className="text-sm text-(--color-muted) mt-1.5 leading-relaxed">{data.note}</p>}
          <div className="mt-2 text-xs text-(--color-muted) tabular-nums">
            {data.books.length}권 · {all.sections}절 · 본문 {all.written}절
          </div>

          {/* 모바일에는 왼쪽 차례가 없다. 가로로 훑는 칩으로 대신한다 */}
          <div className="lg:hidden mt-4 -mx-4 px-4 flex gap-2 overflow-x-auto pb-1">
            <TrackChip label="전체" count={data.books.length} on={picked === null} onClick={() => setTrack(null)} />
            {groups.map((g) => (
              <TrackChip
                key={g.id}
                label={`${g.emoji ?? ''} ${g.label}`.trim()}
                count={g.books.length}
                on={picked === g.id}
                onClick={() => setTrack(g.id)}
              />
            ))}
          </div>

          <div className="mt-6 flex flex-col gap-8">
            {shown.map((g) => (
              <section key={g.id}>
                <div className="flex items-baseline gap-2">
                  <h2 className="text-sm font-bold text-(--color-text)">
                    {g.emoji && <span className="mr-1.5">{g.emoji}</span>}
                    {g.label}
                  </h2>
                  <span className="text-[11px] text-(--color-muted) tabular-nums">
                    {g.books.length}권 · {g.written}/{g.sections}절
                  </span>
                </div>
                {g.note && <p className="text-xs text-(--color-muted) mt-1 leading-relaxed">{g.note}</p>}
                <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {g.books.map((b) => (
                    <BookCard key={b.id} book={b} />
                  ))}
                </div>
              </section>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

interface ShelfGroup extends ShelfTrack {
  books: ShelfBook[]
  sections: number
  written: number
}

function tally(books: ShelfBook[]) {
  return {
    sections: books.reduce((n, b) => n + b.sections, 0),
    written: books.reduce((n, b) => n + b.written, 0),
  }
}

/**
 * 갈래별로 묶는다. 갈래에 안 적힌 책은 버리지 않고 맨 뒤 '그 밖의' 로 모은다 —
 * 새 책을 넣고 track 을 안 적었다고 서가에서 사라지면 그게 더 나쁜 고장이다.
 */
function shelfGroups(shelf: ReturnType<typeof useShelf>['data']): ShelfGroup[] {
  if (!shelf) return []
  const tracks = shelf.tracks ?? []
  const groups: ShelfGroup[] = tracks
    .map((t) => {
      const books = shelf.books.filter((b) => b.track === t.id)
      return { ...t, books, ...tally(books) }
    })
    .filter((g) => g.books.length > 0)

  const known = new Set(tracks.map((t) => t.id))
  const rest = shelf.books.filter((b) => !b.track || !known.has(b.track))
  if (rest.length) groups.push({ id: '_rest', label: '그 밖의', books: rest, ...tally(rest) })
  return groups
}

function ShelfNav({
  groups,
  all,
  picked,
  onPick,
}: {
  groups: ShelfGroup[]
  all: { sections: number; written: number }
  picked: string | null
  onPick: (id: string | null) => void
}) {
  return (
    <aside className="hidden lg:flex flex-col w-60 shrink-0 border-r border-(--color-border) bg-(--color-panel) overflow-y-auto">
      <div className="px-4 py-3 border-b border-(--color-border)">
        <div className="text-[13px] font-bold text-(--color-text)">서가</div>
        <div className="mt-2 flex items-center gap-2 text-[11px] text-(--color-muted)">
          <div className="flex-1 h-1 rounded-full bg-(--color-band) overflow-hidden">
            <div className="h-full bg-(--color-accent)" style={{ width: `${pctOf(all.written, all.sections)}%` }} />
          </div>
          <span className="tabular-nums shrink-0">
            {all.written}/{all.sections}
          </span>
        </div>
      </div>

      <nav className="py-2">
        <TrackRow label="전체" emoji="📚" count={groups.reduce((n, g) => n + g.books.length, 0)} pct={pctOf(all.written, all.sections)} on={picked === null} onClick={() => onPick(null)} />
        {groups.map((g) => (
          <TrackRow
            key={g.id}
            label={g.label}
            emoji={g.emoji}
            count={g.books.length}
            pct={pctOf(g.written, g.sections)}
            on={picked === g.id}
            onClick={() => onPick(g.id)}
          >
            {g.books.map((b) => (
              <a
                key={b.id}
                href={paths.book(b.id)}
                onClick={onLinkClick(paths.book(b.id))}
                className="flex gap-1.5 pl-9 pr-3 py-1 text-xs leading-snug text-(--color-muted) hover:text-(--color-text) hover:bg-(--hover)"
                title={b.subtitle}
              >
                <span className="min-w-0 flex-1 truncate">{b.title}</span>
                {b.status === 'writing' && <span className="text-(--color-accent) shrink-0 text-[10px]">쓰는 중</span>}
              </a>
            ))}
          </TrackRow>
        ))}
      </nav>
    </aside>
  )
}

function pctOf(a: number, b: number) {
  return b ? Math.round((a / b) * 100) : 0
}

function TrackRow({
  label,
  emoji,
  count,
  pct,
  on,
  onClick,
  children,
}: {
  label: string
  emoji?: string
  count: number
  pct: number
  on: boolean
  onClick: () => void
  children?: React.ReactNode
}) {
  return (
    <div>
      <button
        onClick={onClick}
        className={`w-full text-left px-4 py-1.5 flex items-baseline gap-2 border-l-2 transition ${
          on
            ? 'border-(--color-accent) bg-(--color-accent-weak) text-(--color-accent-deep) font-semibold'
            : 'border-transparent text-(--color-text) hover:bg-(--hover)'
        }`}
      >
        <span className="shrink-0 text-xs w-4">{emoji}</span>
        <span className="text-xs leading-snug min-w-0 flex-1">{label}</span>
        <span className="text-[10px] text-(--color-muted) tabular-nums shrink-0">{count}권</span>
        <span className="text-[10px] text-(--color-faint) tabular-nums shrink-0 w-8 text-right">{pct}%</span>
      </button>
      {on && children}
    </div>
  )
}

function TrackChip({ label, count, on, onClick }: { label: string; count: number; on: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`shrink-0 px-3 py-1.5 text-xs rounded-full border transition ${
        on
          ? 'border-(--color-accent) bg-(--color-accent-weak) text-(--color-accent-deep) font-semibold'
          : 'border-(--color-border) text-(--color-muted)'
      }`}
    >
      {label} <span className="tabular-nums opacity-70">{count}</span>
    </button>
  )
}

function BookCard({ book }: { book: ShelfBook }) {
  const to = paths.book(book.id)
  const last = useLastRead(book.id)

  const pct = pctOf(book.written, book.sections)

  return (
    <div className="rounded-lg border border-(--color-border) bg-(--color-panel) p-5 flex flex-col">
      <a href={to} onClick={onLinkClick(to)} className="group">
        <div className="text-3xl leading-none">{book.emoji ?? '📘'}</div>
        <h2 className="mt-3 text-lg font-bold text-(--color-text) group-hover:text-(--color-accent) transition leading-snug">
          {book.title}
        </h2>
        {book.subtitle && <div className="text-sm text-(--color-muted) mt-1">{book.subtitle}</div>}
        {book.blurb && <p className="text-sm text-(--color-text) mt-3 leading-relaxed">{book.blurb}</p>}
      </a>

      <div className="mt-4 pt-3 border-t border-(--color-border-soft) text-xs text-(--color-muted)">
        <div className="flex items-center gap-2">
          <span className="tabular-nums">
            {book.chapters}장 · {book.sections}절
          </span>
          <span className="text-(--color-faint)">·</span>
          <span className="tabular-nums">
            본문 {book.written}/{book.sections}
          </span>
          <span className="ml-auto tabular-nums text-(--color-accent) font-medium">{pct}%</span>
        </div>
        <div className="mt-1.5 h-1 rounded-full bg-(--color-band) overflow-hidden">
          <div className="h-full bg-(--color-accent)" style={{ width: `${pct}%` }} />
        </div>
      </div>

      <div className="mt-3 flex gap-2">
        <a
          href={to}
          onClick={onLinkClick(to)}
          className="px-3 py-1.5 text-xs font-medium rounded-md border border-(--color-border) text-(--color-text) hover:border-(--color-accent) transition"
        >
          차례 보기
        </a>
        {last && (
          <a
            href={paths.bookPage(book.id, last)}
            onClick={onLinkClick(paths.bookPage(book.id, last))}
            className="px-3 py-1.5 text-xs font-medium rounded-md bg-(--color-accent) text-(--color-on-accent) hover:bg-(--color-accent-deep) transition"
          >
            이어 읽기 →
          </a>
        )}
      </div>
    </div>
  )
}

// ── 표지 · 차례 ─────────────────────────────────────────────────────────
function Cover({ bookId }: { bookId: string }) {
  const { data: toc, loading, error } = useToc(bookId)
  const { read } = useReading(bookId)
  const last = useLastRead(bookId)

  useSeo(
    toc
      ? { title: `${toc.title} — 차례`, description: clip(toc.blurb), robots: NOINDEX, canonical: absUrl(paths.book(bookId)) }
      : null,
  )

  if (loading) return <Loader label="차례 불러오는 중…" />
  if (error || !toc)
    return (
      <ErrorState
        title={`${bookId} 의 차례를 못 읽었다`}
        detail={error ?? ''}
        hint={<>경로: <code className="text-(--color-text)">public/book/{bookId}/toc.json</code></>}
      />
    )

  const firstWritten = toc.chapters.flatMap((c) => c.sections).find((s) => s.status !== 'todo')
  // 앞 여덟 권은 배열로, 뒤 두 권은 한 문단짜리 문자열로 썼다. 여기서 한 모양으로 만든다
  const howToRead = normList(toc.how_to_read)
  const prereq = normList(toc.prereq)
  const env = normEnv(toc.env)
  const startAt = last ?? firstWritten?.id ?? null

  return (
    <div className="flex-1 min-h-0 overflow-y-auto">
      <div className="max-w-3xl mx-auto p-4 sm:p-8 pb-20">
        <a href={paths.wiki()} onClick={onLinkClick(paths.wiki())} className="text-xs text-(--color-muted) hover:text-(--color-text)">
          ← 책장
        </a>

        {/* 표지 */}
        <header className="mt-4 rounded-lg border border-(--color-border) bg-(--color-panel) p-6 sm:p-8">
          <h1 className="text-3xl font-bold text-(--color-text) tracking-tight leading-tight">{toc.title}</h1>
          {toc.subtitle && <div className="mt-2 text-base text-(--color-muted)">{toc.subtitle}</div>}
          {toc.blurb && <p className="mt-4 text-[15px] text-(--color-text) leading-relaxed">{toc.blurb}</p>}

          {startAt && (
            <a
              href={paths.bookPage(bookId, startAt)}
              onClick={onLinkClick(paths.bookPage(bookId, startAt))}
              className="mt-6 inline-block px-4 py-2 text-sm font-semibold rounded-md bg-(--color-accent) text-(--color-on-accent) hover:bg-(--color-accent-deep) transition"
            >
              {last ? '이어 읽기 →' : '처음부터 읽기 →'}
            </a>
          )}
          <div className="mt-4 text-xs text-(--color-muted)">{toc.updated_at} 갱신</div>
        </header>

        {toc.preface && (
          <section className="mt-8">
            <SectionTitle>머리말</SectionTitle>
            <div className="book-md mt-3 text-(--color-text)">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{toc.preface}</ReactMarkdown>
            </div>
          </section>
        )}

        {howToRead.length > 0 && (
          <section className="mt-8">
            <SectionTitle>읽는 법</SectionTitle>
            <ul className="mt-3 flex flex-col gap-2">
              {howToRead.map((h, i) => (
                <li key={i} className="text-sm text-(--color-text) leading-relaxed flex gap-2.5">
                  <span className="text-(--color-accent) font-semibold tabular-nums shrink-0">{i + 1}</span>
                  <span>
                    <Md>{h}</Md>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {(prereq.length > 0 || env.length > 0) && (
          <section className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-4">
            {prereq.length > 0 && (
              <div>
                <SectionTitle>알고 있어야 하는 것</SectionTitle>
                <ul className="mt-3 flex flex-col gap-1.5">
                  {prereq.map((p, i) => (
                    <li key={i} className="text-sm text-(--color-text) leading-relaxed">
                      · <Md>{p}</Md>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {env.length > 0 && (
              <div>
                <SectionTitle>실습 환경</SectionTitle>
                <dl className="mt-3 flex flex-col gap-1.5">
                  {env.map((e) => (
                    <div key={e.name || e.value} className="text-sm">
                      {e.name && <dt className="inline text-(--color-muted)">{e.name} </dt>}
                      <dd className="inline text-(--color-text) font-medium">{e.value}</dd>
                      {e.note && <div className="text-xs text-(--color-faint) leading-relaxed">{e.note}</div>}
                    </div>
                  ))}
                </dl>
              </div>
            )}
          </section>
        )}

        {/* 차례 */}
        <section className="mt-10">
          <SectionTitle>차례</SectionTitle>
          <div className="mt-4 flex flex-col gap-6">
            {toc.chapters.map((c) => (
              <ChapterBlock key={c.no} bookId={bookId} chapter={c} read={read} />
            ))}
          </div>
        </section>

        {toc.source && (
          <footer className="mt-12 pt-5 border-t border-(--color-border) text-xs text-(--color-muted) leading-relaxed">
            <span className="text-(--color-text) font-medium">차례 출처 </span>
            {toc.source.url ? (
              <a href={toc.source.url} target="_blank" rel="noreferrer noopener" className="text-(--color-accent) hover:underline">
                {sourceLabel(toc.source)}
              </a>
            ) : (
              sourceLabel(toc.source)
            )}
            {toc.source.note && <div className="mt-1">{toc.source.note}</div>}
          </footer>
        )}
      </div>
    </div>
  )
}

function ChapterBlock({ bookId, chapter, read }: { bookId: string; chapter: TocChapter; read: Set<string> }) {
  const mins = totalMinutes(chapter.sections)
  return (
    <div className="rounded-lg border border-(--color-border) bg-(--color-panel) overflow-hidden">
      <div className="px-4 py-3 bg-(--color-band) border-b border-(--color-border-soft)">
        <div className="flex items-baseline gap-2.5">
          <span className="text-xs font-bold text-(--color-accent) tabular-nums shrink-0">{chapter.no}장</span>
          <h3 className="text-[15px] font-bold text-(--color-text)">{chapter.title}</h3>
          {mins > 0 && <span className="ml-auto text-[11px] text-(--color-muted) tabular-nums shrink-0">{mins}분</span>}
        </div>
        {chapter.goal && <p className="text-xs text-(--color-muted) mt-1 leading-relaxed">{chapter.goal}</p>}
      </div>
      <ol>
        {chapter.sections.map((s) => {
          const done = s.status !== 'todo'
          const to = paths.bookPage(bookId, s.id)
          const inner = (
            <>
              <span className="text-xs text-(--color-faint) tabular-nums shrink-0 w-8">{s.no}</span>
              <span className="min-w-0 flex-1">
                <span className={`text-sm ${done ? 'text-(--color-text) font-medium' : 'text-(--color-faint)'}`}>
                  {s.title}
                </span>
                {s.summary && <span className="block text-xs text-(--color-muted) mt-0.5 leading-relaxed">{s.summary}</span>}
              </span>
              <span className="shrink-0 flex items-center gap-2">
                {read.has(s.id) && <span className="text-(--color-accent) text-xs">✓</span>}
                <StatusTag status={s.status} />
              </span>
            </>
          )
          return (
            <li key={s.id} className="border-b border-(--color-border-soft) last:border-b-0">
              {done ? (
                <a href={to} onClick={onLinkClick(to)} className="flex gap-2.5 px-4 py-2.5 hover:bg-(--hover) transition">
                  {inner}
                </a>
              ) : (
                <div className="flex gap-2.5 px-4 py-2.5 cursor-not-allowed" title="아직 안 쓴 절">
                  {inner}
                </div>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

// ── 본문 ────────────────────────────────────────────────────────────────
function Reader({ bookId, pageId }: { bookId: string; pageId: string }) {
  const { data: toc } = useToc(bookId)
  const { data: page, loading, error } = usePage(bookId, pageId)
  const flat = useFlatToc(toc)
  const nav = useMemo(() => neighbors(flat, pageId), [flat, pageId])
  const { read, toggle } = useReading(bookId)
  const [tocOpen, setTocOpen] = useState(false)

  // 절이 바뀌면 모바일 차례 서랍을 닫는다. 효과가 아니라 렌더 중에 조정하는 이유는
  // 이 파일의 다른 곳과 같다 — 효과로 미루면 새 절 위에 서랍이 한 프레임 남는다.
  const [prevPage, setPrevPage] = useState(pageId)
  if (pageId !== prevPage) {
    setPrevPage(pageId)
    setTocOpen(false)
  }

  useEffect(() => {
    rememberLast(bookId, pageId)
    // 절을 옮기면 맨 위에서 시작해야 한다. 스크롤이 남아 있으면 새 절의 중간부터 보인다.
    document.querySelector('[data-book-scroll]')?.scrollTo({ top: 0 })
  }, [bookId, pageId])

  useSeo(
    page
      ? {
          title: `${page.no} ${page.title}`,
          description: clip(page.summary),
          robots: NOINDEX,
          canonical: absUrl(paths.bookPage(bookId, pageId)),
        }
      : null,
  )

  return (
    <div className="flex flex-1 min-h-0">
      <TocSidebar
        bookId={bookId}
        toc={toc}
        current={pageId}
        read={read}
        open={tocOpen}
        onClose={() => setTocOpen(false)}
      />

      <main data-book-scroll className="flex-1 min-w-0 overflow-y-auto">
        {/* 모바일 상단 바 — 차례를 열 유일한 통로 */}
        <div className="lg:hidden sticky top-0 z-10 flex items-center gap-2 px-4 h-11 border-b border-(--color-border) bg-(--color-panel)">
          <button onClick={() => setTocOpen(true)} className="text-xs font-medium text-(--color-text) px-2 py-1 rounded border border-(--color-border)">
            ☰ 차례
          </button>
          <span className="text-xs text-(--color-muted) truncate">{toc?.title}</span>
        </div>

        {loading ? (
          <Loader label="본문 불러오는 중…" />
        ) : error || !page ? (
          <ErrorState
            title="아직 안 쓴 절이다"
            detail={error ?? ''}
            hint={
              <a href={paths.book(bookId)} onClick={onLinkClick(paths.book(bookId))} className="text-(--color-accent) underline">
                차례로 돌아가기
              </a>
            }
          />
        ) : (
          <article className="max-w-3xl mx-auto px-4 sm:px-8 py-6 sm:py-10 pb-24">
            <PageBody page={page} bookId={bookId} />

            {/* 읽음 표시 + 이전/다음 */}
            <div className="mt-12 pt-6 border-t border-(--color-border)">
              <button
                onClick={() => toggle(pageId)}
                className={`w-full py-2.5 text-sm font-medium rounded-md border transition ${
                  read.has(pageId)
                    ? 'border-(--color-accent) bg-(--color-accent-weak) text-(--color-accent-deep)'
                    : 'border-(--color-border) text-(--color-muted) hover:border-(--color-accent) hover:text-(--color-text)'
                }`}
              >
                {read.has(pageId) ? '✓ 읽음' : '읽음으로 표시'}
              </button>

              <div className="mt-4 grid grid-cols-2 gap-3">
                {nav.prev ? (
                  <NavLink book={bookId} to={nav.prev.id} dir="prev" no={nav.prev.no} title={nav.prev.title} />
                ) : (
                  <span />
                )}
                {nav.next ? (
                  <NavLink book={bookId} to={nav.next.id} dir="next" no={nav.next.no} title={nav.next.title} />
                ) : (
                  <span />
                )}
              </div>
            </div>
          </article>
        )}
      </main>
    </div>
  )
}

function NavLink({ book, to, dir, no, title }: { book: string; to: string; dir: 'prev' | 'next'; no: string; title: string }) {
  const href = paths.bookPage(book, to)
  return (
    <a
      href={href}
      onClick={onLinkClick(href)}
      className={`rounded-md border border-(--color-border) bg-(--color-panel) p-3 hover:border-(--color-accent) transition ${
        dir === 'next' ? 'text-right col-start-2' : ''
      }`}
    >
      <div className="text-[11px] text-(--color-muted)">{dir === 'prev' ? '← 이전' : '다음 →'}</div>
      <div className="text-sm font-medium text-(--color-text) mt-0.5 leading-snug">
        <span className="text-(--color-faint) tabular-nums mr-1">{no}</span>
        {title}
      </div>
    </a>
  )
}

function TocSidebar({
  bookId,
  toc,
  current,
  read,
  open,
  onClose,
}: {
  bookId: string
  toc: BookToc | null
  current: string
  read: Set<string>
  open: boolean
  onClose: () => void
}) {
  const flat = useFlatToc(toc)
  const doneCount = flat.filter((s) => read.has(s.id)).length
  const pct = flat.length ? Math.round((doneCount / flat.length) * 100) : 0
  const currentChapter = flat.find((s) => s.id === current)?.chapter ?? 1

  const body = (
    <>
      <div className="px-4 py-3 border-b border-(--color-border)">
        <a href={paths.book(bookId)} onClick={onLinkClick(paths.book(bookId))} className="block group">
          <div className="text-[13px] font-bold text-(--color-text) group-hover:text-(--color-accent) leading-snug">
            {toc?.title ?? '…'}
          </div>
        </a>
        <div className="mt-2 flex items-center gap-2 text-[11px] text-(--color-muted)">
          <div className="flex-1 h-1 rounded-full bg-(--color-band) overflow-hidden">
            <div className="h-full bg-(--color-accent)" style={{ width: `${pct}%` }} />
          </div>
          <span className="tabular-nums shrink-0">
            {doneCount}/{flat.length}
          </span>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto py-2">
        {(toc?.chapters ?? []).map((c) => (
          <details key={c.no} open={c.no === currentChapter} className="group">
            <summary className="px-4 py-1.5 cursor-pointer list-none flex items-baseline gap-2 hover:bg-(--hover)">
              <span className="text-[11px] text-(--color-faint) tabular-nums shrink-0 w-6">{c.no}장</span>
              <span className="text-xs font-semibold text-(--color-text) leading-snug">{c.title}</span>
            </summary>
            <ul className="pb-1">
              {c.sections.map((s) => {
                const on = s.id === current
                const to = paths.bookPage(bookId, s.id)
                const cls = `flex gap-1.5 pl-[3.25rem] pr-3 py-1 text-xs leading-snug border-l-2 ${
                  on
                    ? 'border-(--color-accent) bg-(--color-accent-weak) text-(--color-accent-deep) font-semibold'
                    : 'border-transparent'
                }`
                if (s.status === 'todo')
                  return (
                    <li key={s.id} className={`${cls} text-(--color-faint)`} title="아직 안 쓴 절">
                      <span className="tabular-nums shrink-0">{s.no}</span>
                      <span className="min-w-0">{s.title}</span>
                    </li>
                  )
                return (
                  <li key={s.id}>
                    <a
                      href={to}
                      onClick={onLinkClick(to)}
                      className={`${cls} ${on ? '' : 'text-(--color-muted) hover:text-(--color-text) hover:bg-(--hover)'}`}
                    >
                      <span className="tabular-nums shrink-0">{s.no}</span>
                      <span className="min-w-0 flex-1">{s.title}</span>
                      {read.has(s.id) && <span className="text-(--color-accent) shrink-0">✓</span>}
                    </a>
                  </li>
                )
              })}
            </ul>
          </details>
        ))}
      </nav>
    </>
  )

  return (
    <>
      <aside className="hidden lg:flex flex-col w-72 shrink-0 border-r border-(--color-border) bg-(--color-panel)">{body}</aside>
      {open && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div className="w-72 max-w-[85%] bg-(--color-panel) flex flex-col shadow-xl">{body}</div>
          <div className="flex-1 bg-black/30" onClick={onClose} />
        </div>
      )}
    </>
  )
}

// ── 절 하나 ─────────────────────────────────────────────────────────────
function PageBody({ page, bookId }: { page: Page; bookId: string }) {
  return (
    <>
      <div className="text-xs text-(--color-muted)">
        <a href={paths.book(bookId)} onClick={onLinkClick(paths.book(bookId))} className="hover:text-(--color-accent)">
          차례
        </a>
        <span className="mx-1.5 text-(--color-faint)">›</span>
        <span>{page.chapter}장</span>
      </div>

      <h1 className="mt-2 text-[26px] sm:text-3xl font-bold text-(--color-text) tracking-tight leading-tight">
        <span className="text-(--color-accent) tabular-nums mr-2">{page.no}</span>
        {page.title}
      </h1>
      <p className="mt-3 text-[15px] text-(--color-muted) leading-relaxed">{page.summary}</p>
      <div className="mt-2 text-xs text-(--color-faint)">
        {page.minutes ? `읽는 데 약 ${page.minutes}분 · ` : ''}
        {page.updated_at}
      </div>

      {!!page.goals?.length && (
        <div className="mt-6 rounded-lg border border-(--color-accent)/35 bg-(--color-accent-weak)/50 p-4">
          <div className="text-xs font-bold text-(--color-accent-deep)">이 절을 덮을 때 할 수 있어야 하는 것</div>
          <ul className="mt-2 flex flex-col gap-1.5">
            {page.goals.map((g, i) => (
              <li key={i} className="text-sm text-(--color-text) leading-relaxed flex gap-2">
                <span className="text-(--color-accent) shrink-0">□</span>
                <span>
                  <Md>{g}</Md>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-2">
        {page.blocks.map((b, i) => (
          <BlockView key={i} block={b} />
        ))}
      </div>

      {!!page.recap?.length && (
        <section className="mt-12">
          <BigTitle>정리</BigTitle>
          <ul className="mt-3 flex flex-col gap-2">
            {page.recap.map((r, i) => (
              <li key={i} className="text-sm text-(--color-text) leading-relaxed flex gap-2.5">
                <span className="text-(--color-accent) font-bold shrink-0 tabular-nums">{i + 1}</span>
                <span>
                  <Md>{r}</Md>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!!page.drills?.length && <Drills drills={page.drills} />}
      {!!page.quiz?.length && <QuizList quiz={page.quiz} />}
      {!!page.terms?.length && <Terms terms={page.terms} />}

      {!!page.sources?.length && (
        <section className="mt-10 pt-5 border-t border-(--color-border)">
          <div className="text-xs font-semibold text-(--color-muted)">참고한 자료</div>
          <ul className="mt-2 flex flex-col gap-1">
            {page.sources.map((s, i) => (
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
    </>
  )
}

function Drills({ drills }: { drills: Drill[] }) {
  return (
    <section className="mt-10">
      <BigTitle>손으로 해 볼 것</BigTitle>
      <p className="text-xs text-(--color-muted) mt-1">읽어서 아는 것과 쳐 봐서 아는 것의 간격이 유난히 큰 기술이다</p>
      <ol className="mt-4 flex flex-col gap-3">
        {drills.map((d, i) => (
          <li key={i} className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4">
            <div className="flex items-baseline gap-2.5">
              <span className="text-xs font-bold text-(--color-accent) tabular-nums shrink-0">{i + 1}</span>
              <span className="text-sm font-medium text-(--color-text) flex-1 leading-relaxed">
                <Md>{d.task}</Md>
              </span>
              {d.minutes ? <span className="text-[11px] text-(--color-faint) shrink-0">~{d.minutes}분</span> : null}
            </div>
            <div className="mt-2.5 pl-6 text-xs leading-relaxed">
              <div className="text-(--color-muted)">
                <span className="text-(--color-text) font-semibold">끝난 지점 </span>
                <Md>{d.done_when}</Md>
              </div>
              {d.hint && (
                <div className="text-(--color-muted) mt-1">
                  <span className="text-(--color-text) font-semibold">힌트 </span>
                  <Md>{d.hint}</Md>
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}

function QuizList({ quiz }: { quiz: Quiz[] }) {
  return (
    <section className="mt-10">
      <BigTitle>스스로 확인</BigTitle>
      <p className="text-xs text-(--color-muted) mt-1">답을 먼저 떠올리고 펼친다. 못 떠오르면 그 부분을 다시 읽는다</p>
      <div className="mt-4 flex flex-col gap-2">
        {quiz.map((q, i) => (
          <details key={i} className="rounded-md border border-(--color-border) bg-(--color-panel) overflow-hidden">
            <summary className="px-4 py-3 cursor-pointer list-none flex gap-2.5 hover:bg-(--hover)">
              <span className="text-(--color-accent) font-bold shrink-0">?</span>
              <span className="text-sm text-(--color-text) font-medium leading-relaxed">
                <Md>{q.q}</Md>
              </span>
            </summary>
            <div className="px-4 pb-3.5 pl-11 text-sm text-(--color-text) leading-relaxed border-t border-(--color-border-soft) pt-3">
              <Md>{q.a}</Md>
            </div>
          </details>
        ))}
      </div>
    </section>
  )
}

function Terms({ terms }: { terms: Term[] }) {
  return (
    <section className="mt-10">
      <BigTitle>이 절의 낱말</BigTitle>
      <dl className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {terms.map((t, i) => (
          <div key={i} className="rounded-md border border-(--color-border) bg-(--color-panel) p-3">
            <dt className="text-sm font-semibold text-(--color-text)">
              {t.term}
              {t.en && <span className="text-xs text-(--color-faint) font-normal ml-1.5">{t.en}</span>}
            </dt>
            <dd className="text-xs text-(--color-muted) mt-1 leading-relaxed">
              <Md>{t.what}</Md>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

// ── 블록 ────────────────────────────────────────────────────────────────
const TONE: Record<string, { label: string; cls: string; bar: string }> = {
  why: { label: '왜', cls: 'border-(--color-accent)/40 bg-(--color-accent-weak)/40', bar: 'text-(--color-accent-deep)' },
  tip: { label: '팁', cls: 'border-(--color-border) bg-(--color-band)', bar: 'text-(--color-text)' },
  note: { label: '참고', cls: 'border-(--color-border) bg-(--color-band)', bar: 'text-(--color-text)' },
  warn: { label: '주의', cls: 'border-amber-400/45 bg-amber-400/8', bar: 'text-amber-500' },
  trap: { label: '함정', cls: 'border-red-400/45 bg-red-400/8', bar: 'text-red-500' },
  interview: { label: '면접', cls: 'border-sky-400/45 bg-sky-400/8', bar: 'text-sky-400' },
}

function BlockView({ block: b }: { block: Block }) {
  switch (b.type) {
    case 'heading':
      return (
        <h2 id={b.id} className="mt-10 mb-1 text-xl font-bold text-(--color-text) tracking-tight scroll-mt-16">
          {b.text}
        </h2>
      )

    case 'prose':
      return (
        <div className="book-md mt-4 text-(--color-text)">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{b.md}</ReactMarkdown>
        </div>
      )

    case 'code':
      return <CodeBlock lang={b.lang} file={b.file} caption={b.caption} code={b.code} note={b.note} bad={b.bad} />

    case 'sql':
      return <CodeBlock lang={b.lang ?? 'sql'} caption={b.caption ?? '실제로 나가는 SQL'} code={b.sql} note={b.note} sql />

    case 'callout': {
      const t = TONE[b.tone] ?? TONE.note
      return (
        <aside className={`mt-5 rounded-lg border p-4 ${t.cls}`}>
          <div className={`text-xs font-bold ${t.bar}`}>
            {t.label}
            {b.title && <span className="text-(--color-text) ml-2">{b.title}</span>}
          </div>
          <div className="book-md book-md-tight mt-2 text-(--color-text)">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{b.md}</ReactMarkdown>
          </div>
        </aside>
      )
    }

    case 'table':
      return (
        <figure className="mt-6">
          {b.caption && <figcaption className="text-sm font-semibold text-(--color-text) mb-1.5">{b.caption}</figcaption>}
          <div className="overflow-x-auto rounded-lg border border-(--color-border)">
            <table className="w-full text-sm border-collapse">
              <thead className="bg-(--color-band)">
                <tr>
                  {b.columns.map((c, i) => (
                    <th key={i} className="text-left font-semibold text-(--color-muted) px-3 py-2 whitespace-nowrap text-xs">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {b.rows.map((row, i) => (
                  <tr key={i} className="border-t border-(--color-border-soft) align-top">
                    {row.map((cell, k) => (
                      <td key={k} className={`px-3 py-2 leading-relaxed ${k === 0 ? 'text-(--color-text)' : 'text-(--color-muted)'}`}>
                        <Md>{cell}</Md>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {b.note && <p className="text-xs text-(--color-faint) mt-1.5 leading-relaxed"><Md>{b.note}</Md></p>}
        </figure>
      )

    case 'compare': {
      // 한쪽이 `bad` 로 표시된 비교만 ✓/✗ 를 붙인다. 그냥 나란히 놓고 보는 비교
      // (객체의 참조 vs 테이블의 외래 키)에 둘 다 ✓ 를 달면 둘 다 정답이라는
      // 뜻이 되어 버려서, 무엇을 말하려는 그림인지가 흐려진다.
      const graded = Boolean(b.left.bad || b.right.bad)
      return (
        <figure className="mt-6">
          {b.caption && <figcaption className="text-sm font-semibold text-(--color-text) mb-2">{b.caption}</figcaption>}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {[b.left, b.right].map((side, i) => (
              <div
                key={i}
                className={`rounded-lg border p-3 ${
                  side.bad ? 'border-red-400/45 bg-red-400/5' : 'border-(--color-border) bg-(--color-panel)'
                }`}
              >
                <div className={`text-xs font-bold ${side.bad ? 'text-red-500' : 'text-(--color-accent-deep)'}`}>
                  {graded ? (side.bad ? '✗ ' : '✓ ') : ''}
                  {side.title}
                </div>
                {side.code && <Pre lang={side.lang} code={side.code} className="mt-2" />}
                {side.md && (
                  <p className="text-xs text-(--color-muted) mt-2 leading-relaxed">
                    <Md>{side.md}</Md>
                  </p>
                )}
              </div>
            ))}
          </div>
          {b.note && <p className="text-xs text-(--color-faint) mt-1.5 leading-relaxed"><Md>{b.note}</Md></p>}
        </figure>
      )
    }

    case 'steps':
      return (
        <div className="mt-6">
          {b.caption && <div className="text-sm font-semibold text-(--color-text) mb-2">{b.caption}</div>}
          <ol className="flex flex-col gap-3">
            {b.items.map((it, i) => (
              <li key={i} className="rounded-lg border border-(--color-border) bg-(--color-panel) p-3.5">
                <div className="flex items-baseline gap-2.5">
                  <span className="w-5 h-5 shrink-0 rounded-full bg-(--color-accent) text-(--color-on-accent) text-[11px] font-bold flex items-center justify-center tabular-nums">
                    {i + 1}
                  </span>
                  <span className="text-sm font-semibold text-(--color-text) leading-snug">{it.title}</span>
                </div>
                {it.md && (
                  <div className="book-md book-md-tight mt-1.5 ml-7.5 text-(--color-text)">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{it.md}</ReactMarkdown>
                  </div>
                )}
                {it.code && <Pre lang={it.lang} code={it.code} className="mt-2 ml-7.5" />}
              </li>
            ))}
          </ol>
        </div>
      )

    case 'figure':
      return (
        <figure className="mt-6">
          {b.caption && <figcaption className="text-sm font-semibold text-(--color-text) mb-1.5">{b.caption}</figcaption>}
          <div className="rounded-lg border border-(--color-border) bg-(--color-band) p-4 overflow-x-auto">
            <pre className="book-ascii">{b.ascii}</pre>
          </div>
          {b.note && <p className="text-xs text-(--color-faint) mt-1.5 leading-relaxed"><Md>{b.note}</Md></p>}
        </figure>
      )

    case 'terms':
      return (
        <div className="mt-6">
          {b.caption && <div className="text-sm font-semibold text-(--color-text) mb-2">{b.caption}</div>}
          <Terms terms={b.items} />
        </div>
      )

    default:
      return null
  }
}

function CodeBlock({
  lang,
  file,
  caption,
  code,
  note,
  bad,
  sql,
}: {
  lang?: string
  file?: string
  caption?: string
  code: string
  note?: string
  bad?: boolean
  sql?: boolean
}) {
  return (
    <figure className="mt-5">
      {caption && (
        <figcaption className={`text-sm font-semibold mb-1.5 ${sql ? 'text-(--color-accent-deep)' : 'text-(--color-text)'}`}>
          {sql && <span className="text-xs font-bold mr-1.5">→</span>}
          {caption}
        </figcaption>
      )}
      <div className={`rounded-lg border overflow-hidden ${bad ? 'border-red-400/50' : 'border-(--color-border)'}`}>
        {(file || bad) && (
          <div
            className={`px-3 py-1.5 text-[11px] font-medium border-b flex items-center gap-2 ${
              bad ? 'bg-red-400/8 border-red-400/30 text-red-500' : 'bg-(--color-band) border-(--color-border-soft) text-(--color-muted)'
            }`}
          >
            {bad && <span className="font-bold">✗ 이렇게 하면 안 된다</span>}
            {file && <span className="font-mono">{file}</span>}
            <span className="ml-auto uppercase tracking-wide text-(--color-faint)">{lang}</span>
          </div>
        )}
        <Pre lang={lang} code={code} plain />
      </div>
      {note && <p className="text-xs text-(--color-faint) mt-1.5 leading-relaxed"><Md>{note}</Md></p>}
    </figure>
  )
}

function Pre({ lang, code, className = '', plain }: { lang?: string; code: string; className?: string; plain?: boolean }) {
  return (
    <pre className={`book-code ${plain ? 'book-code-plain' : ''} ${className}`}>
      <code>{highlight(code, lang)}</code>
    </pre>
  )
}

// ── 아주 작은 문법 강조 ─────────────────────────────────────────────────
// 하이라이터 라이브러리를 넣지 않는 이유: 이 책에 나오는 언어가 java·sql·xml 셋뿐이고,
// 필요한 구분도 다섯 가지(주석·문자열·애노테이션·키워드·숫자)뿐이다. 그 다섯 개 때문에
// 수백 KB 짜리 의존성을 더하고 CSP·테마 문제를 떠안을 이유가 없다.
//
// 정확한 파서가 아니다. 문자열 안의 키워드처럼 틀릴 수 있는 경우가 있지만,
// **읽기를 도우려는 것이지 검사하려는 것이 아니므로** 그 정도 오차는 감수한다.
const JAVA_KW =
  'public|private|protected|abstract|class|interface|enum|extends|implements|new|return|void|static|final|if|else|for|while|do|switch|case|break|continue|try|catch|finally|throw|throws|import|package|null|true|false|this|super|instanceof|int|long|boolean|double|float|char|byte|short|var'
const SQL_KW =
  'SELECT|FROM|WHERE|INSERT|INTO|VALUES|UPDATE|SET|DELETE|JOIN|LEFT|RIGHT|INNER|OUTER|FULL|ON|AND|OR|NOT|NULL|IS|ORDER|GROUP|HAVING|BY|AS|CREATE|TABLE|ALTER|DROP|ADD|PRIMARY|KEY|FOREIGN|REFERENCES|DISTINCT|LIMIT|OFFSET|EXISTS|IN|BETWEEN|LIKE|CASE|WHEN|THEN|ELSE|END|COUNT|SUM|AVG|MIN|MAX|UNION|ALL'

function rulesFor(lang?: string): RegExp | null {
  const l = (lang ?? '').toLowerCase()
  if (l === 'java')
    return new RegExp(
      `(?<cm>\\/\\/[^\\n]*|\\/\\*[\\s\\S]*?\\*\\/)|(?<st>"(?:\\\\.|[^"\\\\])*")|(?<an>@\\w+)|(?<kw>\\b(?:${JAVA_KW})\\b)|(?<nu>\\b\\d+[LlFfDd]?\\b)`,
      'g',
    )
  if (l === 'sql')
    return new RegExp(`(?<cm>--[^\\n]*)|(?<st>'(?:''|[^'])*')|(?<kw>\\b(?:${SQL_KW})\\b)|(?<nu>\\b\\d+\\b)`, 'gi')
  if (l === 'xml' || l === 'html')
    return new RegExp(`(?<cm><!--[\\s\\S]*?-->)|(?<st>"[^"]*")|(?<kw><\\/?[\\w:.-]+|\\/?>)`, 'g')
  // 오간 HTTP 를 날것으로 싣는 책(스프링 MVC)이 있어서 넣었다.
  // 헤더 이름을 `an` 으로 칠하는 것은 어노테이션과 같은 자리 — 줄 맨 앞의 이름표라는 점이 같다.
  if (l === 'http')
    return new RegExp(
      `(?<cm>^#[^\\n]*)|(?<kw>^(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\\b|HTTP\\/[\\d.]+)|(?<an>^[A-Za-z][\\w-]*(?=:\\s))|(?<nu>\\b[1-5]\\d{2}\\b)`,
      'gm',
    )
  return null
}

const CLS: Record<string, string> = { cm: 'tk-cm', st: 'tk-st', an: 'tk-an', kw: 'tk-kw', nu: 'tk-nu' }

function highlight(code: string, lang?: string): React.ReactNode {
  const re = rulesFor(lang)
  if (!re) return code

  const out: React.ReactNode[] = []
  let last = 0
  let i = 0
  for (const m of code.matchAll(re)) {
    const at = m.index ?? 0
    if (at > last) out.push(code.slice(last, at))
    const key = Object.keys(m.groups ?? {}).find((k) => m.groups?.[k] !== undefined)
    out.push(
      <span key={i++} className={key ? CLS[key] : undefined}>
        {m[0]}
      </span>,
    )
    last = at + m[0].length
  }
  if (last < code.length) out.push(code.slice(last))
  return out
}

// ── 부스러기 ────────────────────────────────────────────────────────────
function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="text-sm font-bold text-(--color-muted) tracking-wide">{children}</h2>
}

function BigTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-lg font-bold text-(--color-text) border-b-2 border-(--color-accent) pb-1.5 inline-block">
      {children}
    </h2>
  )
}

const STATUS_STYLE: Record<SectionStatus, string> = {
  done: 'border-(--color-accent)/40 bg-(--color-accent-weak) text-(--color-accent-deep)',
  draft: 'border-amber-400/40 bg-amber-400/10 text-amber-500',
  todo: 'border-(--color-border) bg-(--color-band) text-(--color-faint)',
}

function StatusTag({ status }: { status: SectionStatus }) {
  if (status === 'done') return null
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border shrink-0 ${STATUS_STYLE[status]}`}>
      {status === 'draft' ? '초고' : '예정'}
    </span>
  )
}

/** 서가로 들어가는 짧은 링크 — 다른 화면에서 쓴다 */
export function BookLink({ bookId, label }: { bookId: string; label: string }) {
  return (
    <button onClick={() => navigate(paths.book(bookId))} className="text-xs text-(--color-accent) hover:underline">
      {label} →
    </button>
  )
}
