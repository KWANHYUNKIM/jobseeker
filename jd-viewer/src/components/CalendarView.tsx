import { useMemo, useState } from 'react'
import { useCalendar } from '../lib/useCalendar'
import { Loader, ErrorState, SearchInput, hits } from './ui'
import type { CalendarItem } from '../types'

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']
const SITE_LABEL: Record<string, string> = {
  wanted: '원티드', jumpit: '점핏', jobkorea: '잡코리아', saramin: '사람인', dev: '데보션',
}

function iso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// 마감 건수에 따른 히트맵 단계
function heatClass(n: number): string {
  if (n === 0) return ''
  if (n <= 2) return 'bg-(--color-accent)/10'
  if (n <= 5) return 'bg-(--color-accent)/20'
  if (n <= 10) return 'bg-(--color-accent)/35'
  return 'bg-(--color-accent)/55'
}

export function CalendarView() {
  const { data, loading, error } = useCalendar()
  const today = new Date()
  const todayIso = iso(today)
  const [cursor, setCursor] = useState({ y: today.getFullYear(), m: today.getMonth() }) // m: 0-indexed
  const [selected, setSelected] = useState<string | null>(null)
  const [query, setQuery] = useState('')

  // 검색은 달력 자체에 건다 — 목록만 거르면 히트맵은 여전히 전체 건수로 칠해져
  // '이 회사 마감이 언제 몰려 있나' 를 볼 수가 없다.
  const items = useMemo(
    () =>
      (data?.items ?? []).filter((it) =>
        hits(query, it.company, it.title, SITE_LABEL[it.site] ?? it.site, it.career),
      ),
    [data, query],
  )

  // 마감일 → 공고 목록
  const byDate = useMemo(() => {
    const map = new Map<string, CalendarItem[]>()
    for (const it of items) {
      if (!it.deadline) continue
      if (!map.has(it.deadline)) map.set(it.deadline, [])
      map.get(it.deadline)!.push(it)
    }
    return map
  }, [items])

  // 마감 임박(오늘 이후 14일)
  const upcoming = useMemo(() => {
    const out: { date: string; items: CalendarItem[] }[] = []
    for (let i = 0; i < 21; i++) {
      const d = new Date(today)
      d.setDate(d.getDate() + i)
      const key = iso(d)
      const items = byDate.get(key)
      if (items?.length) out.push({ date: key, items })
    }
    return out
  }, [byDate]) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <Loader label="모집 캘린더 불러오는 중…" />
  if (error)
    return (
      <ErrorState
        title="job_calendar.json 로드 실패"
        detail={error}
        hint={<>생성: <code className="text-(--color-text)">python bin/build_calendar.py</code> (jd-viewer)</>}
      />
    )

  const { y, m } = cursor
  const first = new Date(y, m, 1)
  const startPad = first.getDay()
  const daysInMonth = new Date(y, m + 1, 0).getDate()
  const monthLabel = `${y}년 ${m + 1}월`

  // 이 달 마감 건수
  let monthClose = 0
  for (let d = 1; d <= daysInMonth; d++) monthClose += byDate.get(iso(new Date(y, m, d)))?.length ?? 0

  const cells: (number | null)[] = [
    ...Array(startPad).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ]
  while (cells.length % 7 !== 0) cells.push(null)

  const move = (delta: number) => {
    const nd = new Date(y, m + delta, 1)
    setCursor({ y: nd.getFullYear(), m: nd.getMonth() })
  }

  const selItems = selected ? byDate.get(selected) ?? [] : null

  return (
    <div className="flex flex-col md:flex-row flex-1 min-h-0 min-w-0 overflow-y-auto md:overflow-hidden">
      {/* 캘린더 */}
      <div className="flex-1 min-w-0 md:overflow-auto p-4 sm:p-5 flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-3 text-xs text-(--color-muted)">
          <SearchInput
            value={query}
            onChange={setQuery}
            placeholder="회사·공고·사이트 검색"
            className="w-full sm:w-72"
          />
          {query ? (
            <span>
              <b className="text-(--color-text)">{items.length}</b>건이 걸렸다 (마감일 표기{' '}
              {data?.dated ?? 0}건 중)
            </span>
          ) : (
            <span>
              마감일 표기 <b className="text-(--color-text)">{data?.dated ?? 0}</b>건 · 상시채용{' '}
              <b className="text-(--color-text)">{data?.always_open ?? 0}</b>건
              {' · '}전체 {data?.total ?? 0}건 중 기간 추출 {(data?.dated ?? 0) + (data?.always_open ?? 0)}건
            </span>
          )}
          {data?.generated_at && <span className="ml-auto">갱신 {data.generated_at.slice(0, 10)}</span>}
        </div>

        <div className="flex items-center gap-2">
          <button onClick={() => move(-1)} className="px-2 py-1 rounded border border-(--color-border) text-(--color-text) hover:border-(--color-accent)">‹</button>
          <div className="text-lg font-semibold text-(--color-text) min-w-32 text-center">{monthLabel}</div>
          <button onClick={() => move(1)} className="px-2 py-1 rounded border border-(--color-border) text-(--color-text) hover:border-(--color-accent)">›</button>
          <button
            onClick={() => setCursor({ y: today.getFullYear(), m: today.getMonth() })}
            className="px-2.5 py-1 text-xs rounded border border-(--color-border) text-(--color-muted) hover:border-(--color-accent) hover:text-(--color-accent)"
          >
            오늘
          </button>
          <span className="ml-auto text-xs text-(--color-muted)">이 달 마감 {monthClose}건</span>
        </div>

        <div className="grid grid-cols-7 gap-1">
          {WEEKDAYS.map((w, i) => (
            <div key={w} className={`text-center text-xs py-1 ${i === 0 ? 'text-red-400' : i === 6 ? 'text-blue-400' : 'text-(--color-muted)'}`}>
              {w}
            </div>
          ))}
          {cells.map((day, i) => {
            if (day === null) return <div key={i} />
            const ds = iso(new Date(y, m, day))
            const items = byDate.get(ds)
            const n = items?.length ?? 0
            const isToday = ds === todayIso
            const isPast = ds < todayIso
            const isSel = ds === selected
            return (
              <button
                key={i}
                onClick={() => n > 0 && setSelected(isSel ? null : ds)}
                disabled={n === 0}
                className={`relative aspect-square rounded border p-1.5 flex flex-col text-left transition ${heatClass(n)} ${
                  isSel ? 'border-(--color-accent)' : 'border-(--color-border)'
                } ${n > 0 ? 'hover:border-(--color-accent) cursor-pointer' : 'cursor-default'} ${isPast ? 'opacity-50' : ''}`}
              >
                <span className={`text-xs ${isToday ? 'text-(--color-accent) font-bold' : 'text-(--color-text)'}`}>
                  {day}
                  {isToday && <span className="ml-1 text-[9px]">오늘</span>}
                </span>
                {n > 0 && (
                  <span className="mt-auto text-[11px] font-medium text-(--color-text)">마감 {n}</span>
                )}
              </button>
            )
          })}
        </div>
        <p className="text-[11px] text-(--color-muted)">
          ※ 공고 본문의 접수/모집기간·마감 표기를 파싱한 결과입니다. 상시·수시채용 등 마감일이 없는 공고는 캘린더에 표시되지 않습니다.
        </p>
      </div>

      {/* 우측(모바일=하단): 선택일 또는 마감 임박 */}
      <aside className="w-full md:w-96 shrink-0 md:overflow-auto border-t md:border-t-0 md:border-l border-(--color-border) bg-(--color-panel) p-4">
        {selItems ? (
          <>
            <div className="flex items-center gap-2 mb-3">
              <h3 className="text-sm font-semibold text-(--color-text)">{selected} 마감 ({selItems.length})</h3>
              <button onClick={() => setSelected(null)} className="ml-auto text-xs text-(--color-muted) hover:text-(--color-accent)">전체보기</button>
            </div>
            <JobList items={selItems} />
          </>
        ) : (
          <>
            <h3 className="text-sm font-semibold text-(--color-text) mb-1">마감 임박</h3>
            <p className="text-xs text-(--color-muted) mb-3">앞으로 3주 내 마감되는 공고. 날짜를 누르면 그날 마감만 봅니다.</p>
            {upcoming.length === 0 && <p className="text-sm text-(--color-muted)">임박한 마감이 없습니다.</p>}
            <div className="flex flex-col gap-3">
              {upcoming.map(({ date, items }) => {
                const dd = Math.round((new Date(date).getTime() - new Date(todayIso).getTime()) / 86400000)
                return (
                  <div key={date}>
                    <button onClick={() => setSelected(date)} className="text-xs font-medium text-(--color-accent) hover:underline mb-1">
                      {date} · {dd === 0 ? 'D-DAY' : `D-${dd}`} · {items.length}건
                    </button>
                    <JobList items={items.slice(0, 4)} />
                    {items.length > 4 && (
                      <button onClick={() => setSelected(date)} className="text-[11px] text-(--color-muted) hover:text-(--color-accent)">+{items.length - 4}건 더</button>
                    )}
                  </div>
                )
              })}
            </div>
          </>
        )}
      </aside>
    </div>
  )
}

function JobList({ items }: { items: CalendarItem[] }) {
  return (
    <ul className="flex flex-col gap-2">
      {items.map((it, i) => (
        <li key={it.url + i} className="rounded border border-(--color-border) bg-(--color-bg) px-3 py-2">
          <div className="flex items-center gap-2 text-[11px] text-(--color-muted) mb-0.5">
            <span className="text-(--color-accent)">{it.company}</span>
            <span>{SITE_LABEL[it.site] ?? it.site}</span>
            {it.career && <span className="ml-auto">{it.career}</span>}
          </div>
          <a href={it.url} target="_blank" rel="noreferrer" className="text-sm text-(--color-text) hover:text-(--color-accent) hover:underline">
            {it.title} ↗
          </a>
          {it.start && (
            <div className="mt-0.5 text-[11px] text-(--color-muted)">모집 {it.start} ~ {it.deadline ?? '채용시'}</div>
          )}
        </li>
      ))}
    </ul>
  )
}
