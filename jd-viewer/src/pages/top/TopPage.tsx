import { TopBoard } from '../../features/home/components/TopBoard'

/** `/top/<구역>` — 메인 배너 한 장이 여는 인기 TOP 50(신입·경력·인턴…). */
export function TopPage({ sectionKey }: { sectionKey: string | null }) {
  return <TopBoard sectionKey={sectionKey ?? 'entry'} />
}
