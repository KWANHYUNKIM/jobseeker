import { CalendarView } from '../../features/calendar/components/CalendarView'

/** `/calendar` — 모집 캘린더. */
export function CalendarPage() {
  return (
    <div key="calendar" className="flex flex-1 min-h-0 jd-fade-in jd-canvas">
      <CalendarView />
    </div>
  )
}
