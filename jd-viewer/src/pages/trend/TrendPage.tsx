import { TrendView } from '../../features/trend/components/TrendView'
import { navigate } from '../../utils/navigation'
import { paths } from '../../utils/urls'

/** `/trend?tech=<기술>` — 개발 트렌드. */
export function TrendPage({ focusTech }: { focusTech: string | null }) {
  return (
    <div key="trend" className="flex flex-1 min-h-0 jd-fade-in jd-canvas">
      <TrendView onOpenCompany={(slug) => navigate(paths.company(slug))} focusTech={focusTech} />
    </div>
  )
}
