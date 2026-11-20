import { SiteFooter } from '../../../components/SiteFooter'
import { useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Md } from '../../../components/Md'
import { Loader, ErrorState } from '../../../components/ui'
import { navigate, onLinkClick } from '../../../utils/navigation'
import { absUrl, clip, useSeo } from '../../../utils/seo'
import { paths } from '../../../utils/urls'
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
} from '../hooks/useBook'

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
// 책이 열 권을 넘어가면서 카드를 한 줄로 늘어놓는 것만으로는 안 됐다 — 갈래(track)로 묶는다.
// 캐치형(Penpot 10 기술도서): 숫자 칸 넷, 갈래 밑줄 탭, 갈래마다 머리줄 + 4열 책 카드(갈래 색 표지).
function Shelf() {
  const { data, loading, error } = useShelf()
  const [track, setTrack] = useState<string | null>(null)

  useSeo({ title: '기술도서', description: '혼자 읽으려고 쓰는 책들', robots: NOINDEX, canonical: absUrl(paths.wiki()) })

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
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[43px] pb-[90px]">
        <h1 className="text-[28px] font-bold leading-10 tracking-[-0.6px] text-[#272727]">기술도서</h1>
        {data.note && <p className="mt-1 text-base leading-6 tracking-[-0.16px] text-[#666]">{data.note}</p>}

        <div className="mt-[27px] grid grid-cols-2 lg:grid-cols-4 gap-[14px]">
          <ShelfStat label="책" value={`${data.books.length}권`} />
          <ShelfStat label="절" value={`${all.sections.toLocaleString()}절`} />
          <ShelfStat label="완성" value={`${pctOf(all.written, all.sections)}%`} accent />
          <ShelfStat label="트랙" value={`${groups.length}개`} />
        </div>

        {/* 갈래 탭 */}
        <div role="tablist" className="mt-[42px] flex overflow-x-auto no-scrollbar border-b border-[#e2e2e2]">
          <ShelfTab on={picked === null} label="전체" count={data.books.length} onClick={() => setTrack(null)} />
          {groups.map((g) => (
            <ShelfTab
              key={g.id}
              on={picked === g.id}
              label={`${g.emoji ?? ''} ${g.label}`.trim()}
              count={g.books.length}
              onClick={() => setTrack(g.id)}
            />
          ))}
        </div>

        <div className="mt-12 flex flex-col gap-[50px]">
          {shown.map((g) => {
            const tone = TRACK_TONE[groups.indexOf(g) % TRACK_TONE.length]
            return (
              <section key={g.id}>
                <div className="flex flex-wrap items-baseline gap-x-[14px] gap-y-1 pb-[17px] border-b-2 border-[#272727]">
                  <h2 className="text-[22px] font-bold leading-8 tracking-[-0.22px] text-[#272727]">
                    {g.emoji && <span className="mr-1.5">{g.emoji}</span>}
                    {g.label}
                  </h2>
                  <span className="text-[15px] text-[#999] tabular-nums">
                    {g.books.length}권 · {g.sections}절
                  </span>
                  {g.note && <span className="text-[15px] text-[#666]">{g.note}</span>}
                </div>
                <div className="mt-[22px] grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  {g.books.map((b) => (
                    <BookCard key={b.id} book={b} tone={tone} track={g.label} />
                  ))}
                </div>
              </section>
            )
          })}
        </div>
      </div>
      <SiteFooter />
    </div>
  )
}

/** 갈래 색 — 서가에 적힌 갈래 순서대로(기반 지식·스프링·데이터 접근·실전 프로젝트·품질과 보안·인프라와 배포). */
const TRACK_TONE: { bg: string; fg: string }[] = [
  { bg: '#eef1ff', fg: '#3d5afe' },
  { bg: '#eaf8f0', fg: '#2bb673' },
  { bg: '#fff3e8', fg: '#f2994a' },
  { bg: '#f3eeff', fg: '#8b5cf6' },
  { bg: '#fff0f0', fg: '#f45757' },
  { bg: '#e8f6fd', fg: '#0ea5e9' },
  { bg: '#f4f4f4', fg: '#64748b' },
]

function ShelfStat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className={'h-[108px] rounded-[20px] border px-[25px] pt-[21px] ' + (accent ? 'bg-(--color-accent-weak) border-[#ffd5d5]' : 'border-[#e2e8ec]')}>
      <div className="text-sm text-[#777]">{label}</div>
      <div className={'mt-1 text-[28px] font-bold leading-10 tracking-[-0.16px] tabular-nums ' + (accent ? 'text-(--color-accent)' : 'text-[#272727]')}>{value}</div>
    </div>
  )
}

function ShelfTab({ on, label, count, onClick }: { on: boolean; label: string; count: number; onClick: () => void }) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={on}
      onClick={onClick}
      className={
        'relative shrink-0 px-[18px] pb-[13px] text-base leading-6 tracking-[-0.16px] ' +
        (on ? 'font-bold text-(--color-accent) after:absolute after:inset-x-0 after:-bottom-px after:h-[3px] after:bg-(--color-accent)' : 'font-medium text-[#777] hover:text-[#272727]')
      }
    >
      {label}
      <span className={'ml-1.5 text-[13px] tabular-nums text-[#aaa] ' + (on ? 'font-bold' : 'font-medium')}>{count}</span>
    </button>
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

function pctOf(a: number, b: number) {
  return b ? Math.round((a / b) * 100) : 0
}

function BookCard({ book, tone, track }: { book: ShelfBook; tone: { bg: string; fg: string }; track: string }) {
  const to = paths.book(book.id)
  const last = useLastRead(book.id)
  const pct = pctOf(book.written, book.sections)

  return (
    <div className="rounded-3xl border border-[#e2e8ec] bg-white p-[15px] flex flex-col hover:border-[#999] transition">
      <a href={to} onClick={onLinkClick(to)} className="group flex flex-col">
        <span className="h-[150px] rounded-2xl px-5 pt-3 flex flex-col" style={{ background: tone.bg }}>
          <span className="text-[54px] leading-[79px]" aria-hidden>
            {book.emoji ?? '📘'}
          </span>
          <span className="mt-auto mb-4 text-[13px] font-bold" style={{ color: tone.fg }}>
            {track}
          </span>
        </span>
        <span className="mt-4 px-1.5 block text-lg font-bold leading-[26px] tracking-[-0.3px] text-[#272727] truncate group-hover:underline underline-offset-2">
          {book.title}
        </span>
        {book.subtitle && <span className="mt-1 px-1.5 block text-sm text-(--color-accent) truncate">{book.subtitle}</span>}
        {book.blurb && <span className="mt-2 px-1.5 line-clamp-3 text-sm leading-[21px] text-[#666]">{book.blurb}</span>}
      </a>
      <div className="mt-auto px-1.5 pt-4">
        <div className="flex items-center gap-2 text-[13px] text-[#777] tabular-nums">
          <span>
            {book.chapters}장 · {book.sections}절
          </span>
          {last && (
            <a href={paths.bookPage(book.id, last)} onClick={onLinkClick(paths.bookPage(book.id, last))} className="font-medium hover:underline" style={{ color: tone.fg }}>
              이어 읽기 →
            </a>
          )}
          <span className="ml-auto font-bold" style={{ color: tone.fg }}>
            {pct}%
          </span>
        </div>
        <div className="mt-2 h-1.5 rounded-[3px] bg-[#f1f3f5] overflow-hidden">
          <div className="h-full rounded-[3px]" style={{ width: `${pct}%`, background: tone.fg }} />
        </div>
      </div>
    </div>
  )
}

// ── 표지 · 차례 ─────────────────────────────────────────────────────────
// 캐치형(Penpot 24 도서 차례) — 회색 띠에 책 표지(갈래 색)·제목·부제·소개·읽기 단추,
// 아래 왼쪽은 장마다 접고 펴는 차례, 오른쪽은 머리말·읽는 법·알고 있어야 하는 것·실습 환경 칸.
const OPEN_FIRST = 4 // 처음 펴 두는 장 수

function Cover({ bookId }: { bookId: string }) {
  const { data: toc, loading, error } = useToc(bookId)
  const { data: shelf } = useShelf()
  const { read } = useReading(bookId)
  const last = useLastRead(bookId)
  const [open, setOpen] = useState<Set<string> | null>(null)

  useSeo(
    toc
      ? { title: `${toc.title} — 차례`, description: clip(toc.blurb), robots: NOINDEX, canonical: absUrl(paths.book(bookId)) }
      : null,
  )

  const groups = useMemo(() => shelfGroups(shelf), [shelf])

  if (loading) return <Loader label="차례 불러오는 중…" />
  if (error || !toc)
    return (
      <ErrorState
        title={`${bookId} 의 차례를 못 읽었다`}
        detail={error ?? ''}
        hint={<>경로: <code className="text-(--color-text)">public/book/{bookId}/toc.json</code></>}
      />
    )

  const book = shelf?.books.find((b) => b.id === bookId)
  const gi = groups.findIndex((g) => g.books.some((b) => b.id === bookId))
  const group = gi >= 0 ? groups[gi] : null
  const tone = TRACK_TONE[(gi >= 0 ? gi : 0) % TRACK_TONE.length]
  const sections = toc.chapters.flatMap((c) => c.sections)
  const written = sections.filter((s) => s.status !== 'todo').length
  const firstWritten = sections.find((s) => s.status !== 'todo')
  const lastNo = last ? sections.find((s) => s.id === last)?.no : null
  // 앞 여덟 권은 배열로, 뒤 두 권은 한 문단짜리 문자열로 썼다. 여기서 한 모양으로 만든다
  const howToRead = normList(toc.how_to_read)
  const prereq = normList(toc.prereq)
  const env = normEnv(toc.env)
  const envChips = env.flatMap((e) => (e.name ? [`${e.name} ${e.value}`] : e.value.split(/,\s*|·\s*/))).map((s) => s.trim()).filter(Boolean)
  const isOpen = (no: string, i: number) => (open ? open.has(no) : i < OPEN_FIRST)
  const toggle = (no: string) =>
    setOpen((cur) => {
      const base = cur ?? new Set(toc.chapters.slice(0, OPEN_FIRST).map((c) => String(c.no)))
      const n = new Set(base)
      if (n.has(no)) n.delete(no)
      else n.add(no)
      return n
    })

  return (
    <div data-scroll className="flex-1 min-h-0 overflow-y-auto bg-white">
      <div className="jd-container pt-11 pb-[90px]">
        <nav aria-label="경로" className="text-sm text-[#777]">
          <a href={paths.wiki()} onClick={onLinkClick(paths.wiki())} className="hover:text-[#272727]">
            기술도서
          </a>
          {group && ` › ${group.label}`}
        </nav>

        {/* 표지 띠 */}
        <header className="mt-5 flex flex-col md:flex-row gap-[34px] rounded-[30px] bg-[#f7f9fa] p-[34px]">
          <div className="shrink-0 w-[220px] h-[290px] rounded-[18px] px-7 pt-7 pb-6 flex flex-col shadow-[6px_8px_0_rgba(0,0,0,0.06)]" style={{ background: tone.bg }}>
            <span className="text-[70px] leading-[100px]" aria-hidden>
              {book?.emoji ?? '📘'}
            </span>
            {group && (
              <span className="mt-auto text-sm font-bold" style={{ color: tone.fg }}>
                {group.label}
              </span>
            )}
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="text-[32px] font-bold leading-[47px] tracking-[-0.6px] text-[#272727]">{toc.title}</h1>
            {toc.subtitle && <div className="mt-1 text-lg text-(--color-accent)">{toc.subtitle}</div>}
            {toc.blurb && <p className="mt-4 max-w-[780px] text-base leading-[26px] text-[#474747]">{toc.blurb}</p>}
            <div className="mt-4 flex flex-wrap gap-x-[17px] text-sm text-[#777] tabular-nums">
              <span>
                {toc.chapters.length}장 · {sections.length}절
              </span>
              <span>
                본문 {written}/{sections.length} · {pctOf(written, sections.length)}%
              </span>
              {toc.updated_at && <span>{toc.updated_at} 갱신</span>}
            </div>
            <div className="mt-5 flex flex-wrap gap-2.5">
              {firstWritten && (
                <a
                  href={paths.bookPage(bookId, firstWritten.id)}
                  onClick={onLinkClick(paths.bookPage(bookId, firstWritten.id))}
                  className="inline-flex items-center gap-2 h-11 px-6 rounded-md bg-(--color-accent) text-base font-medium text-white hover:bg-(--color-accent-deep)"
                >
                  처음부터 읽기
                  <svg width="8" height="10" viewBox="0 0 8 10" fill="none" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" aria-hidden>
                    <path d="M2.5 1.5 6 5l-3.5 3.5" />
                  </svg>
                </a>
              )}
              {last && (
                <a
                  href={paths.bookPage(bookId, last)}
                  onClick={onLinkClick(paths.bookPage(bookId, last))}
                  className="inline-flex items-center h-11 px-[17px] rounded-[18px] border border-[#d8d8d8] bg-white text-sm font-medium text-[#272727] hover:border-[#272727]"
                >
                  이어 읽기{lastNo ? ` · ${lastNo}` : ''}
                </a>
              )}
            </div>
          </div>
        </header>

        <div className="mt-10 flex flex-col lg:flex-row gap-7 items-start">
          {/* 차례 */}
          <section className="w-full lg:flex-1 min-w-0">
            <h2 className="pb-3.5 border-b-2 border-[#272727] text-[22px] font-bold leading-8 text-[#272727]">차례</h2>
            <ol>
              {toc.chapters.map((c, i) => (
                <ChapterBlock key={c.no} bookId={bookId} chapter={c} read={read} open={isOpen(String(c.no), i)} onToggle={() => toggle(String(c.no))} />
              ))}
            </ol>
            {toc.source && (
              <p className="mt-6 text-xs leading-relaxed text-[#999]">
                <b className="font-medium text-[#666]">차례 출처 </b>
                {toc.source.url ? (
                  <a href={toc.source.url} target="_blank" rel="noreferrer noopener" className="hover:underline">
                    {sourceLabel(toc.source)}
                  </a>
                ) : (
                  sourceLabel(toc.source)
                )}
                {toc.source.note && <span className="block mt-1">{toc.source.note}</span>}
              </p>
            )}
          </section>

          {/* 오른쪽 칸 */}
          <aside className="w-full lg:w-[348px] shrink-0 flex flex-col gap-4">
            {toc.preface && (
              <SideCard title="머리말">
                <p className="line-clamp-6 text-sm leading-[22px] text-[#666]">{plainMd(toc.preface)}</p>
              </SideCard>
            )}
            {howToRead.length > 0 && (
              <SideCard title="읽는 법">
                <div className="flex flex-col gap-1.5 text-sm leading-[22px] text-[#666] line-clamp-4">
                  {howToRead.map((h, i) => (
                    <p key={i}>
                      <Md>{h}</Md>
                    </p>
                  ))}
                </div>
              </SideCard>
            )}
            {prereq.length > 0 && (
              <SideCard title="알고 있어야 하는 것">
                <div className="flex flex-col gap-1.5 text-sm leading-[22px] text-[#666] line-clamp-4">
                  {prereq.map((p, i) => (
                    <p key={i}>
                      <Md>{p}</Md>
                    </p>
                  ))}
                </div>
              </SideCard>
            )}
            {envChips.length > 0 && (
              <div className="rounded-[22px] bg-[#f3f6f8] px-[22px] pt-[22px] pb-5">
                <h3 className="text-[17px] font-bold text-[#272727]">실습 환경</h3>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {envChips.map((e) => (
                    <span key={e} className="rounded bg-white/80 px-[7px] text-[13px] leading-[22px] text-[#474747]">
                      {e}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </aside>
        </div>
      </div>
      <SiteFooter />
    </div>
  )
}

function SideCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-[22px] border border-[#e2e8ec] bg-white px-[23px] pt-[23px] pb-5">
      <h3 className="text-[17px] font-bold text-[#272727]">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  )
}

/** 마크다운 기호를 걷어 낸 글 — 칸 안에서 몇 줄로 줄여 보일 때 */
function plainMd(md: string): string {
  return md
    .replace(/```[\s\S]*?```/g, '')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/\[(.*?)\]\(.*?\)/g, '$1')
    .replace(/[*_#>]/g, '')
    .replace(/\s*\n+\s*/g, ' ')
    .trim()
}

function ChapterBlock({
  bookId,
  chapter,
  read,
  open,
  onToggle,
}: {
  bookId: string
  chapter: TocChapter
  read: Set<string>
  open: boolean
  onToggle: () => void
}) {
  const mins = totalMinutes(chapter.sections)
  return (
    <li className="border-b border-[#e2e8ec] py-5">
      <button type="button" onClick={onToggle} aria-expanded={open} className="w-full flex items-start gap-4 text-left">
        <span className="shrink-0 mt-0.5 grid place-items-center h-[30px] min-w-[52px] px-3 rounded-[15px] bg-[#272727] text-[13px] font-bold text-white tabular-nums">
          {chapter.no}장
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[19px] font-bold leading-[27px] text-[#272727]">{chapter.title}</span>
          {open && chapter.goal && <span className="block text-sm text-[#888]">{chapter.goal}</span>}
        </span>
        <span className="shrink-0 mt-1.5 text-[13px] text-[#999] tabular-nums">{open ? (mins > 0 ? `${mins}분` : '') : '펼치기 +'}</span>
      </button>
      {open && (
        <ol className="mt-2 pl-[68px]">
          {chapter.sections.map((s) => {
            const done = s.status !== 'todo'
            const to = paths.bookPage(bookId, s.id)
            const inner = (
              <>
                <span className={'w-[50px] shrink-0 text-sm font-bold tabular-nums ' + (done ? 'text-(--color-accent)' : 'text-[#c4c4c4]')}>{s.no}</span>
                <span className={'w-[276px] shrink-0 truncate text-base font-medium ' + (done ? 'text-[#272727]' : 'text-[#bbb]')}>{s.title}</span>
                <span className="hidden md:block min-w-0 flex-1 truncate text-sm text-[#777]">{s.summary}</span>
                {read.has(s.id) && <span className="shrink-0 text-xs text-(--color-accent)">✓</span>}
                {!done && <StatusTag status={s.status} />}
              </>
            )
            return (
              <li key={s.id}>
                {done ? (
                  <a href={to} onClick={onLinkClick(to)} className="group flex items-center gap-0 h-12 rounded-lg hover:bg-[#f7f9fa] [&>span:nth-child(2)]:group-hover:underline">
                    {inner}
                  </a>
                ) : (
                  <div className="flex items-center h-12 cursor-not-allowed" title="아직 안 쓴 절">
                    {inner}
                  </div>
                )}
              </li>
            )
          })}
        </ol>
      )}
    </li>
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
    <div data-book-scroll className="flex-1 min-h-0 overflow-y-auto bg-white">
      <div className="jd-container pt-[30px] pb-[90px] flex gap-10 items-start">
        <TocSidebar bookId={bookId} toc={toc} current={pageId} read={read} open={tocOpen} onClose={() => setTocOpen(false)} />

        <main className="flex-1 min-w-0">
          {/* 좁은 화면 — 차례를 여는 단추 */}
          <div className="lg:hidden mb-4 flex items-center gap-2">
            <button type="button" onClick={() => setTocOpen(true)} className="h-9 px-4 rounded-[18px] border border-[#d8d8d8] text-sm font-medium text-[#272727]">
              ☰ 차례
            </button>
            <span className="text-sm text-[#999] truncate">{toc?.title}</span>
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
            <article className="book-reader max-w-[880px]">
              <PageBody page={page} bookId={bookId} bookTitle={toc?.title} />

              {/* 읽음 표시 + 이전/다음 */}
              <div className="mt-14 flex flex-wrap items-center gap-3">
                {nav.prev && <NavLink book={bookId} to={nav.prev.id} dir="prev" no={nav.prev.no} title={nav.prev.title} />}
                <button
                  type="button"
                  onClick={() => toggle(pageId)}
                  aria-pressed={read.has(pageId)}
                  className={
                    'mx-auto h-11 px-5 rounded-[22px] border text-sm font-medium ' +
                    (read.has(pageId) ? 'border-(--color-accent) bg-(--color-accent-weak) text-(--color-accent)' : 'border-[#d8d8d8] text-[#666] hover:border-[#272727]')
                  }
                >
                  {read.has(pageId) ? '✓ 읽음' : '읽음으로 표시'}
                </button>
                {nav.next && <NavLink book={bookId} to={nav.next.id} dir="next" no={nav.next.no} title={nav.next.title} />}
              </div>
            </article>
          )}
        </main>
      </div>
      <SiteFooter />
    </div>
  )
}

function NavLink({ book, to, dir, no, title }: { book: string; to: string; dir: 'prev' | 'next'; no: string; title: string }) {
  const href = paths.bookPage(book, to)
  return (
    <a
      href={href}
      onClick={onLinkClick(href)}
      title={title}
      className={
        'inline-flex items-center gap-1.5 h-11 max-w-[320px] px-5 rounded-[22px] text-[15px] font-medium ' +
        (dir === 'next' ? 'bg-[#272727] text-white hover:bg-black' : 'border border-[#d8d8d8] text-[#272727] hover:border-[#272727]')
      }
    >
      {dir === 'prev' && <span aria-hidden>‹</span>}
      <span className="truncate">
        <span className="tabular-nums mr-1">{no}</span>
        {title}
      </span>
      {dir === 'next' && <span aria-hidden>›</span>}
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
    <div className="rounded-3xl border border-[#e2e8ec] bg-white px-[21px] pt-6 pb-5">
      <a href={paths.book(bookId)} onClick={onLinkClick(paths.book(bookId))} className="block text-base font-bold leading-6 text-[#272727] hover:underline underline-offset-2">
        {toc?.title ?? '…'}
      </a>
      <div className="mt-3 h-1.5 rounded-[3px] bg-[#f1f3f5] overflow-hidden">
        <div className="h-full bg-(--color-accent)" style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-1.5 text-xs text-[#999] tabular-nums">
        {doneCount} / {flat.length}절 읽음
      </div>
      <nav className="mt-5 flex flex-col gap-1">
        {(toc?.chapters ?? []).map((c) => {
          const cur = c.no === currentChapter
          return (
            <div key={c.no}>
              {cur ? (
                <div className="py-2 text-sm font-bold text-[#272727]">
                  {c.no}장 {c.title}
                </div>
              ) : (
                <a
                  href={paths.bookPage(bookId, c.sections.find((s) => s.status !== 'todo')?.id ?? c.sections[0]?.id ?? '')}
                  onClick={onLinkClick(paths.bookPage(bookId, c.sections.find((s) => s.status !== 'todo')?.id ?? c.sections[0]?.id ?? ''))}
                  className="block py-2.5 text-sm font-medium text-[#666] hover:text-[#272727] truncate"
                >
                  {c.no}장 {c.title}
                </a>
              )}
              {cur && (
                <ul className="mb-2 flex flex-col gap-0.5">
                  {c.sections.map((s) => {
                    const on = s.id === current
                    const to = paths.bookPage(bookId, s.id)
                    const cls = 'flex gap-3 h-[34px] items-center rounded-[10px] px-2.5 text-sm ' + (on ? 'bg-(--color-accent-weak) font-medium text-(--color-accent)' : 'text-[#474747]')
                    if (s.status === 'todo')
                      return (
                        <li key={s.id} className={cls + ' text-[#c4c4c4]'} title="아직 안 쓴 절">
                          <span className="w-7 shrink-0 tabular-nums text-[#c4c4c4]">{s.no}</span>
                          <span className="truncate">{s.title}</span>
                        </li>
                      )
                    return (
                      <li key={s.id}>
                        <a href={to} onClick={onLinkClick(to)} className={cls + (on ? '' : ' hover:bg-[#f7f9fa]')}>
                          <span className="w-7 shrink-0 tabular-nums text-[#999]">{s.no}</span>
                          <span className="min-w-0 flex-1 truncate">{s.title}</span>
                          {read.has(s.id) && <span className="shrink-0 text-xs text-(--color-accent)">✓</span>}
                        </a>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          )
        })}
      </nav>
    </div>
  )

  return (
    <>
      <aside className="hidden lg:block w-[300px] shrink-0 sticky top-4 max-h-[calc(100dvh-10rem)] overflow-y-auto">{body}</aside>
      {open && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div className="w-[300px] max-w-[85%] overflow-y-auto bg-white p-3 shadow-xl">{body}</div>
          <div className="flex-1 bg-black/30" onClick={onClose} />
        </div>
      )}
    </>
  )
}

// ── 절 하나 ─────────────────────────────────────────────────────────────
function PageBody({ page, bookId, bookTitle }: { page: Page; bookId: string; bookTitle?: string }) {
  return (
    <>
      <nav aria-label="경로" className="text-sm text-[#777]">
        <a href={paths.wiki()} onClick={onLinkClick(paths.wiki())} className="hover:text-[#272727]">
          기술도서
        </a>
        {' › '}
        <a href={paths.book(bookId)} onClick={onLinkClick(paths.book(bookId))} className="hover:text-[#272727]">
          {bookTitle ?? '차례'}
        </a>
        {' › '}
        {page.chapter}장
      </nav>

      <div className="mt-5 text-base font-bold text-(--color-accent) tabular-nums">{page.no}</div>
      <h1 className="mt-1 text-[36px] font-bold leading-[52px] tracking-[-0.8px] text-[#272727]">{page.title}</h1>
      <p className="mt-2.5 text-[19px] leading-[27px] text-[#474747]">{page.summary}</p>
      <div className="mt-2 text-[13px] text-[#999]">
        {page.minutes ? `읽는 데 약 ${page.minutes}분 · ` : ''}
        {page.updated_at}
      </div>

      {!!page.goals?.length && (
        <div className="mt-[27px] rounded-[20px] bg-[#f7f9fa] px-[26px] py-[22px]">
          <div className="text-[15px] font-bold text-[#272727]">이 절을 덮을 때 할 수 있어야 하는 것</div>
          <ul className="mt-3 flex flex-col gap-1.5">
            {page.goals.map((g, i) => (
              <li key={i} className="text-base text-[#272727] leading-[26px] flex gap-2.5">
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
          <BlockView key={i} block={b} anchor={anchorOf(b, i)} />
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

// 소제목 id 가 없는 절도 있다 — 순번으로 채운다
function anchorOf(b: Block, i: number) {
  return b.type === 'heading' ? (b.id ?? `sec-${i}`) : undefined
}

// 넓은 화면 오른쪽의 '이 절에서'. 지금 읽는 소제목을 따라 불이 옮겨 간다.
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

function BlockView({ block: b, anchor }: { block: Block; anchor?: string }) {
  switch (b.type) {
    case 'heading':
      return (
        <h2 id={anchor} className="mt-11 mb-1 text-[23px] font-bold leading-[34px] tracking-[-0.4px] text-[#272727] scroll-mt-16">
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
          <div className="overflow-x-auto">
            <table className="w-full text-[15px] border-collapse">
              <thead className="bg-[#fafafa]">
                <tr className="border-b border-[#e2e2e2]">
                  {b.columns.map((c, i) => (
                    <th key={i} className="text-left font-bold text-[#272727] px-3 py-4 whitespace-nowrap">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {b.rows.map((row, i) => (
                  <tr key={i} className="border-b border-[#e2e2e2] align-top">
                    {row.map((cell, k) => (
                      <td key={k} className={`px-3 py-[15px] leading-relaxed ${k === 0 ? 'font-bold text-[#272727]' : 'text-[#474747]'}`}>
                        {/* 절 번호만 적힌 칸(8.10 · 9.2·9.8)은 분홍 칩으로 — 책 안의 다른 절을 가리킨다 */}
                        {/^[\d.·,\s~–-]+$/.test(cell.trim()) ? (
                          <span className="rounded bg-(--color-accent-weak) px-[7px] text-[13px] leading-[22px] text-(--color-accent) tabular-nums whitespace-nowrap">{cell}</span>
                        ) : (
                          <Md>{cell}</Md>
                        )}
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
                className={`rounded-[20px] px-6 py-5 ${
                  graded ? (side.bad ? 'bg-(--color-accent-weak)' : 'bg-[#eaf8f0]') : 'border border-[#e2e8ec] bg-white'
                }`}
              >
                <div className={`text-base font-bold ${graded ? (side.bad ? 'text-(--color-accent)' : 'text-[#1e9e5a]') : 'text-[#272727]'}`}>
                  {graded ? (side.bad ? '✗ ' : '✓ ') : ''}
                  {side.title}
                </div>
                {side.code && <Pre lang={side.lang} code={side.code} className="mt-2" />}
                {side.md && (
                  <p className="text-[15px] text-[#272727] mt-2 leading-[24px]">
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

    case 'image':
      return (
        <figure className="mt-6">
          {b.caption && <figcaption className="text-sm font-semibold text-(--color-text) mb-1.5">{b.caption}</figcaption>}
          <div className="rounded-lg border border-(--color-border) bg-white p-3 flex justify-center">
            <img
              src={b.src}
              alt={b.alt}
              loading="lazy"
              decoding="async"
              className="max-w-full h-auto"
              style={b.width ? { width: b.width } : undefined}
            />
          </div>
          {(b.note || b.credit) && (
            <p className="text-xs text-(--color-faint) mt-1.5 leading-relaxed">
              {b.note && <Md>{b.note}</Md>}
              {b.credit && <span className="block">출처: <Md>{b.credit}</Md></span>}
            </p>
          )}
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
      <div className={`rounded-[20px] overflow-hidden bg-[#272727] ${bad ? 'ring-2 ring-red-400/70' : ''}`}>
        {(file || bad) && (
          <div
            className={`px-3 py-1.5 text-[11px] font-medium border-b flex items-center gap-2 ${
              bad ? 'bg-red-500/20 border-white/10 text-[#ffb4b4]' : 'bg-white/5 border-white/10 text-[#bbb]'
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
