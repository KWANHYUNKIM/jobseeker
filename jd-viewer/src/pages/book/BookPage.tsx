import { BookView } from '../../features/book/components/BookView'
import { CareersView } from '../../features/careers/components/CareersView'

/** `/wiki/...` — 기술도서(책장). 제목·noindex 는 BookView 가 단다. 서가·차례·본문 모두 캐치형 흰 바탕이라 여백 칸을 안 둔다.
 *  `/wiki/careers/...` 는 책이 아니라 취업(합격·이직 후기) 화면이다 — 책장의 '취업' 탭이 여기로 온다. */
export function BookPage({ seg }: { seg: string[] }) {
  if (seg[0] === 'careers')
    return (
      <div key="careers" className="flex flex-1 min-h-0 jd-fade-in">
        <CareersView seg={seg.slice(1)} />
      </div>
    )
  return (
    <div key="book" className="flex flex-1 min-h-0 jd-fade-in">
      <BookView seg={seg} />
    </div>
  )
}
