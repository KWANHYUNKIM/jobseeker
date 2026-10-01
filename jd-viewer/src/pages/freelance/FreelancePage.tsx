import { FreelanceRatesView } from '../../features/freelance/components/FreelanceRatesView'
import { FreelanceView } from '../../features/freelance/components/FreelanceView'

/** `/freelance` · `/freelance/rates` — 단가 분석은 목록 위에 얹지 않고 따로 뺀다. */
export function FreelancePage({ sub }: { sub: string | null }) {
  return sub === 'rates' ? <FreelanceRatesView /> : <FreelanceView />
}
