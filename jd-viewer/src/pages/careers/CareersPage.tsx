import { CareersView } from '../../features/careers/components/CareersView'

/** `/careers/...` — 학습 › 취업후기. 합격·이직 후기(정본 DB). 제목·noindex 는 CareersView 가 단다. */
export function CareersPage({ seg }: { seg: string[] }) {
  return (
    <div key="careers" className="flex flex-1 min-h-0 jd-fade-in">
      <CareersView seg={seg} />
    </div>
  )
}
