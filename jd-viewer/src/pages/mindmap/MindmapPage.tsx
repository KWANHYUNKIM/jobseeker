import { CareerMap } from '../../features/career/components/CareerMap'

/** `/mindmap` — 커리어 마인드맵. */
export function MindmapPage() {
  return (
    <div key="mindmap" className="flex flex-1 min-h-0 relative jd-fade-in jd-canvas">
      <CareerMap />
    </div>
  )
}
