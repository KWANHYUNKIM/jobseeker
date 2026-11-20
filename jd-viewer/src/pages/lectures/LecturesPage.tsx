import { LecturesView } from '../../features/lectures/components/LecturesView'

/** `/lectures` — 강의 노트 목록, `/lectures/<영상 id>` — 노트 한 편. */
export function LecturesPage({ seg }: { seg: string[] }) {
  return (
    <div key="lectures" className="flex flex-1 min-h-0 jd-fade-in">
      <LecturesView seg={seg} />
    </div>
  )
}
