import { FreelanceProjectView } from '../../features/freelance/components/FreelanceProjectView'
import { FreelanceRatesView } from '../../features/freelance/components/FreelanceRatesView'
import { FreelanceView } from '../../features/freelance/components/FreelanceView'

/**
 * `/freelance` · `/freelance/rates` · `/freelance/<사이트>-<번호>`.
 * 단가 분석은 목록 위에 얹지 않고 따로 뺀다. 프로젝트는 원본 사이트로 내보내지 않고 우리 화면에서 본문까지 읽는다.
 */
export function FreelancePage({ sub }: { sub: string | null }) {
  if (sub === 'rates') return <FreelanceRatesView />
  if (sub) return <FreelanceProjectView slug={sub} />
  return <FreelanceView />
}
