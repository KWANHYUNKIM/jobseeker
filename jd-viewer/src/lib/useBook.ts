import { useCallback, useEffect, useMemo, useState } from 'react'

// 책 — public/book/ 아래의 서가·차례·본문을 읽는다.
//
// 왜 낱말사전(useStudy)과 형식을 따로 뒀나:
//   백과사전의 단위는 **낱말 하나**였다. 어디서 들어와도 그 문서만 읽고 끝나야 하니
//   문서마다 정의·비교·지뢰·실습이 전부 들어 있는 자족적인 덩어리였고, 순서가 없었다.
//   책의 단위는 **절 하나**다. 앞 절을 읽었다는 전제로 쓰고, 다음 절로 이어진다.
//   그래서 여기에는 백과사전에 없던 두 가지가 있다 — 차례(순서)와 이전/다음(연결).
//
// 파일을 셋으로 쪼갠 이유:
//   index.json  서가. 책이 몇 권이고 각각 얼마나 찼는지. 가볍다.
//   toc.json    한 권의 차례 전체. 사이드바가 늘 들고 있어야 하므로 본문과 분리한다.
//   pages/*.json 절 하나의 본문. 열어 본 절만 받는다(한 절이 20~40KB 다).

export type BlockTone = 'why' | 'tip' | 'warn' | 'trap' | 'note' | 'interview'

export interface CodeSide {
  title: string
  md?: string
  lang?: string
  code?: string
  /** 이쪽이 '하지 말아야 할 쪽'인가. 비교 블록에서 빨간 테두리로 그린다 */
  bad?: boolean
}

/**
 * 본문은 마크다운 한 덩어리가 아니라 블록의 배열이다.
 *
 * 마크다운 한 덩어리로 두면 "이 코드가 만들어 내는 SQL"·"이건 함정이다"·"면접에서는
 * 이렇게 묻는다" 같은 것들이 전부 같은 회색 문단으로 흘러 버린다. 읽는 사람이
 * 훑을 때 걸려야 하는 자리가 시각적으로 걸리지 않는다. 블록으로 나누면 화면이
 * 그 자리를 다르게 그릴 수 있다.
 */
export type Block =
  | { type: 'prose'; md: string }
  | { type: 'heading'; text: string; id?: string }
  /** 코드. `bad` 면 '이렇게 쓰면 안 된다'는 예제로 그린다 */
  | { type: 'code'; lang?: string; file?: string; caption?: string; code: string; note?: string; bad?: boolean }
  /** JPA 책에서 가장 중요한 블록 — 위 코드가 **실제로 내보내는** SQL */
  | { type: 'sql'; caption?: string; sql: string; note?: string }
  | { type: 'callout'; tone: BlockTone; title?: string; md: string }
  | { type: 'table'; caption?: string; note?: string; columns: string[]; rows: string[][] }
  | { type: 'compare'; caption?: string; note?: string; left: CodeSide; right: CodeSide }
  | { type: 'steps'; caption?: string; items: { title: string; md?: string; lang?: string; code?: string }[] }
  /** 글로 설명하면 안 읽히는 것 — 영속성 컨텍스트 안의 상태 변화 같은 것 */
  | { type: 'figure'; caption?: string; ascii: string; note?: string }
  | { type: 'terms'; caption?: string; items: Term[] }

export interface Term {
  term: string
  en?: string
  what: string
}

export interface Drill {
  task: string
  /** 어디까지 갔으면 끝난 건지. 이게 없으면 실습이 아니라 숙제다 */
  done_when: string
  hint?: string
  minutes?: number
}

export interface Quiz {
  q: string
  a: string
}

export interface Source {
  title: string
  url: string
  publisher?: string
}

export interface Page {
  book: string
  id: string
  /** 차례에 찍히는 번호(`4.1`). 정렬 키가 아니라 표시용이다 */
  no: string
  chapter: number
  title: string
  summary: string
  minutes?: number
  /** 이 절을 덮을 때 할 수 있어야 하는 것 */
  goals?: string[]
  blocks: Block[]
  recap?: string[]
  drills?: Drill[]
  quiz?: Quiz[]
  terms?: Term[]
  sources?: Source[]
  updated_at: string
}

export type SectionStatus = 'done' | 'draft' | 'todo'

export interface TocSection {
  no: string
  id: string
  title: string
  summary?: string
  minutes?: number
  status: SectionStatus
}

export interface TocChapter {
  no: number
  title: string
  /** 이 장이 답하는 질문 한 줄. 차례만 읽어도 책의 논리가 보이게 하는 자리다 */
  goal?: string
  sections: TocSection[]
}

export interface BookToc {
  id: string
  title: string
  subtitle?: string
  blurb?: string
  /** 머리말 */
  preface?: string
  how_to_read?: string[]
  prereq?: string[]
  env?: { name: string; value: string; note?: string }[]
  /** 차례의 출처. 본문은 직접 쓰지만 뼈대는 남의 커리큘럼에서 왔으므로 밝힌다 */
  source?: { name: string; url?: string; note?: string }
  chapters: TocChapter[]
  updated_at: string
}

export interface ShelfBook {
  id: string
  title: string
  subtitle?: string
  blurb?: string
  emoji?: string
  chapters: number
  sections: number
  /** 실제로 본문이 쓰인 절 수. 차례만 있고 본문이 없는 절과 구분한다 */
  written: number
  status: 'writing' | 'done' | 'planned'
  updated_at: string
}

export interface Shelf {
  updated_at: string
  note?: string
  books: ShelfBook[]
}

// ── 로딩 ────────────────────────────────────────────────────────────────
// 결과에 '어느 주소의 것인지'를 함께 담는다. useStudy.ts 와 같은 이유다 —
// 절을 옮겨 다니는 화면에서 앞 절의 본문이 새 제목 밑에 한 프레임 보이면 눈에 걸린다.
function useJson<T>(path: string | null) {
  const [state, setState] = useState<{ path: string | null; data: T | null; error: string | null }>({
    path: null,
    data: null,
    error: null,
  })

  useEffect(() => {
    if (path === null) return
    let cancelled = false
    fetch(path)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status} - ${path}`)
        return r.json()
      })
      .then((d: T) => {
        if (!cancelled) setState({ path, data: d, error: null })
      })
      .catch((e) => {
        if (!cancelled) setState({ path, data: null, error: String(e) })
      })
    return () => {
      cancelled = true
    }
  }, [path])

  const fresh = state.path === path
  return {
    data: fresh ? state.data : null,
    loading: path !== null && !fresh,
    error: fresh ? state.error : null,
  }
}

export const useShelf = () => useJson<Shelf>('/book/index.json')
export const useToc = (bookId: string | null) => useJson<BookToc>(bookId ? `/book/${bookId}/toc.json` : null)
export const usePage = (bookId: string | null, pageId: string | null) =>
  useJson<Page>(bookId && pageId ? `/book/${bookId}/pages/${pageId}.json` : null)

// ── 차례를 한 줄로 펼치기 ───────────────────────────────────────────────
// 이전/다음은 장 경계를 넘어가야 한다(2장 마지막 절의 다음은 3장 첫 절이다).
// 그러려면 장·절 두 겹 구조를 한 줄로 펴 놓고 인덱스로 앞뒤를 잡는 게 가장 단순하다.
export interface FlatSection extends TocSection {
  chapter: number
  chapterTitle: string
}

export function flatten(toc: BookToc | null): FlatSection[] {
  if (!toc) return []
  return toc.chapters.flatMap((c) =>
    c.sections.map((s) => ({ ...s, chapter: c.no, chapterTitle: c.title })),
  )
}

export interface Neighbors {
  current: FlatSection | null
  prev: FlatSection | null
  next: FlatSection | null
  /** 몇 번째 절인지 / 전체 몇 절인지 — 진행 막대가 쓴다 */
  index: number
  total: number
}

export function neighbors(flat: FlatSection[], pageId: string | null): Neighbors {
  const i = pageId ? flat.findIndex((s) => s.id === pageId) : -1
  return {
    current: i >= 0 ? flat[i] : null,
    // 아직 본문이 없는 절로는 보내지 않는다 — 빈 페이지로 가는 '다음' 버튼은 고장으로 보인다.
    prev: i > 0 ? lastWritten(flat, i - 1, -1) : null,
    next: i >= 0 ? lastWritten(flat, i + 1, +1) : null,
    index: i,
    total: flat.length,
  }
}

function lastWritten(flat: FlatSection[], from: number, step: number): FlatSection | null {
  for (let i = from; i >= 0 && i < flat.length; i += step) {
    if (flat[i].status !== 'todo') return flat[i]
  }
  return null
}

// ── 읽은 자리 기억 ──────────────────────────────────────────────────────
// 나만 보는 책이라 서버에 둘 이유가 없다. 브라우저에 남기고, 없으면 없는 대로 돈다
// (시크릿 창·사이트 데이터 차단에서는 접근 자체가 throw 한다).
const readKey = (book: string) => `jd-book:${book}:read`
const lastKey = (book: string) => `jd-book:${book}:last`

function loadRead(book: string): Set<string> {
  try {
    const raw = localStorage.getItem(readKey(book))
    return new Set<string>(raw ? JSON.parse(raw) : [])
  } catch {
    return new Set()
  }
}

export function useReading(book: string | null) {
  const [read, setRead] = useState<Set<string>>(() => (book ? loadRead(book) : new Set()))

  // 책이 바뀌면 그 책의 기록을 다시 읽는다.
  const [prevBook, setPrevBook] = useState(book)
  if (book !== prevBook) {
    setPrevBook(book)
    setRead(book ? loadRead(book) : new Set())
  }

  const toggle = useCallback(
    (pageId: string) => {
      if (!book) return
      setRead((cur) => {
        const next = new Set(cur)
        if (next.has(pageId)) next.delete(pageId)
        else next.add(pageId)
        try {
          localStorage.setItem(readKey(book), JSON.stringify([...next]))
        } catch {
          /* 저장이 막혀 있어도 이번 세션 동안은 표시가 된다 */
        }
        return next
      })
    },
    [book],
  )

  return { read, toggle }
}

/** 마지막으로 연 절 — 서가에서 '이어 읽기'로 되돌아가는 자리 */
export function rememberLast(book: string, pageId: string): void {
  try {
    localStorage.setItem(lastKey(book), pageId)
  } catch {
    /* 무시 */
  }
}

export function recallLast(book: string): string | null {
  try {
    return localStorage.getItem(lastKey(book))
  } catch {
    return null
  }
}

export const STATUS_LABEL: Record<SectionStatus, string> = {
  done: '완성',
  draft: '초고',
  todo: '예정',
}

/** 절 목록 → 읽는 시간 합계(분). 차례에 "이 장 45분" 을 찍는 데 쓴다 */
export function totalMinutes(sections: TocSection[]): number {
  return sections.reduce((n, s) => n + (s.minutes ?? 0), 0)
}

export function useFlatToc(toc: BookToc | null): FlatSection[] {
  return useMemo(() => flatten(toc), [toc])
}
