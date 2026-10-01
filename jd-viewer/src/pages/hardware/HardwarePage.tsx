import { HardwareView } from '../../features/hardware/components/HardwareView'

/** `/hardware/...` — PC 하드웨어. 하위 화면(조립·비교·가격)의 제목·noindex 는 HardwareView 가 단다. */
export function HardwarePage({ seg }: { seg: string[] }) {
  return (
    <div key="hardware" className="flex flex-1 min-h-0 jd-fade-in jd-canvas">
      <HardwareView seg={seg} />
    </div>
  )
}
