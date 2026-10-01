import { CompanyView } from '../../features/companies/components/CompanyView'
import { navigate } from '../../utils/navigation'
import { paths } from '../../utils/urls'

/** `/companies` · `/companies/<슬러그>` — 기업 기술스택. */
export function CompaniesPage({ slug }: { slug: string | null }) {
  return (
    <div key="companies" className="flex flex-1 min-h-0 jd-fade-in jd-canvas">
      <CompanyView
        selectedSlug={slug}
        onSelectCompany={(s) => navigate(paths.company(s))}
        onStudyTech={(tech) => navigate(paths.trend(tech))}
      />
    </div>
  )
}
