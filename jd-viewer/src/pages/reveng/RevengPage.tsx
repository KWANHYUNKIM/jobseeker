import { RevengView } from '../../features/reveng/components/RevengView'

/** `/reveng/...` — 기업 기술 역설계. */
export function RevengPage({ seg }: { seg: string[] }) {
  return (
    <div key="reveng" className="flex flex-1 min-h-0 jd-fade-in jd-canvas">
      <RevengView seg={seg} />
    </div>
  )
}
