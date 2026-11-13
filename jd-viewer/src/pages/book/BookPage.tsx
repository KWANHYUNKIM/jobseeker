import { BookView } from '../../features/book/components/BookView'

/** `/wiki/...` — 기술도서(책장). 제목·noindex 는 BookView 가 단다. 서가(`/wiki`)는 캐치형 흰 바탕이라 여백 칸을 안 둔다. */
export function BookPage({ seg }: { seg: string[] }) {
  return (
    <div key="book" className={'flex flex-1 min-h-0 jd-fade-in' + (seg.length ? ' jd-canvas' : '')}>
      <BookView seg={seg} />
    </div>
  )
}
