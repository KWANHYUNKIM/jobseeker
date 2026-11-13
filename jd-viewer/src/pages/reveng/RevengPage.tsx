import { RevengView } from '../../features/reveng/components/RevengView'

/** `/reveng/...` — 기업 기술 역설계. 목록(`/reveng`)은 캐치형 흰 바탕이라 여백 칸을 안 둔다. */
export function RevengPage({ seg }: { seg: string[] }) {
  return (
    <div key="reveng" className={'flex flex-1 min-h-0 jd-fade-in' + (seg.length && seg[0] !== 'docs' ? ' jd-canvas' : '')}>
      <RevengView seg={seg} />
    </div>
  )
}
