import { BookView } from '../../features/book/components/BookView'

/** `/wiki/...` — 기술도서(책장). 제목·noindex 는 BookView 가 단다. */
export function BookPage({ seg }: { seg: string[] }) {
  return (
    <div key="book" className="flex flex-1 min-h-0 jd-fade-in jd-canvas">
      <BookView seg={seg} />
    </div>
  )
}
