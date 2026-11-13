import { useEffect, useMemo, useState } from 'react'
import { useCalendar } from '../hooks/useCalendar'
import { getJson } from '../../../api/client'
import { Loader, ErrorState, CompanyMark } from '../../../components/ui'
import { SiteFooter } from '../../../components/SiteFooter'
import { classifyRoles } from '../../../utils/classify'
import { onLinkClick } from '../../../utils/navigation'
import { paths } from '../../../utils/urls'
import { plainCompany } from '../../../utils/companyName'
import type { CalendarItem } from '../../../types'

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']
const LIST_STEP = 7

function iso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
/** '11.14 (토)' */
function md(ds: string): string {
  const d = new Date(ds + 'T00:00:00')
  return `${d.getMonth() + 1}.${String(d.getDate()).padStart(2, '0')} (${WEEKDAYS[d.getDay()]})`
}

type FilterKey = 'all' | 'big' | 'entry' | 'be' | 'ai' | 'fe'
const FILTERS: { key: FilterKey; label: string }[] = [
  { key: 'all', label: '전체' },
  { key: 'big', label: '대기업' },
  { key: 'entry', label: '신입 가능' },
  { key: 'be', label: '백엔드' },
  { key: 'ai', label: 'AI/ML' },
  { key: 'fe', label: '프론트엔드' },
]
const ROLE_OF: Partial<Record<FilterKey, string>> = { be: '백엔드', ai: 'AI/ML', fe: '프론트엔드' }

/** 회사 규모 색인(company_meta.json) — 캘린더 항목에는 규모가 없어 '대기업' 칩이 여기서 판정한다. */
function useCompanySizes(): Record<string, string> {
  const [sizes, setSizes] = useState<Record<string, string>>({})
  useEffect(() => {
    getJson<{ sizes: Record<string, string> }>('/company_meta.json')
      .then((m) => setSizes(m.sizes ?? {}))
      .catch(() => {})
  }, [])
  return sizes
}

/**
 * 모집 캘린더(캐치형 06) — 달 이동·오늘·조건 칩·범례, 7칸 달력(날마다 회사 셋까지 '끝'(마감)·'시'(시작) 표시와
 * '+N건 더보기'), 그 아래 고른 날(처음엔 오늘) 마감 공고와 이번 주 날짜별 마감 막대.
 */
export function CalendarView() {
  const { data, loading, error } = useCalendar()
  const sizes = useCompanySizes()
  const today = new Date()
  const todayIso = iso(today)
  const [cursor, setCursor] = useState({ y: today.getFullYear(), m: today.getMonth() }) // m: 0-indexed
  const [selected, setSelected] = useState<string>(todayIso)
  const [filter, setFilter] = useState<FilterKey>('all')
  const [shown, setShown] = useState(LIST_STEP)

  const items = useMemo(() => {
    const role = ROLE_OF[filter]
    return (data?.items ?? []).filter((it) => {
      if (filter === 'big') return sizes[it.company] === '대기업'
      if (filter === 'entry') return /신입|무관/.test(it.career ?? '')
      if (role) return classifyRoles(it.title, it.tech_stack ?? [], '').includes(role)
      return true
    })
  }, [data, filter, sizes])

  // 날짜 → 그날 마감 / 그날 시작
  const { ends, starts } = useMemo(() => {
    const ends = new Map<string, CalendarItem[]>()
    const starts = new Map<string, CalendarItem[]>()
    for (const it of items) {
      if (it.deadline) ends.set(it.deadline, [...(ends.get(it.deadline) ?? []), it])
      if (it.start && !it.start_estimated) starts.set(it.start, [...(starts.get(it.start) ?? []), it])
    }
    return { ends, starts }
  }, [items])

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
  const daysInMonth = new Date(y, m + 1, 0).getDate()
  const cells: (number | null)[] = [...Array(first.getDay()).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => i + 1)]
  while (cells.length % 7 !== 0) cells.push(null)
  let monthClose = 0
  for (let d = 1; d <= daysInMonth; d++) monthClose += ends.get(iso(new Date(y, m, d)))?.length ?? 0

  const move = (delta: number) => {
    const nd = new Date(y, m + delta, 1)
    setCursor({ y: nd.getFullYear(), m: nd.getMonth() })
  }
  const pickDay = (ds: string) => {
    setSelected(ds)
    setShown(LIST_STEP)
  }

  const extracted = (data?.dated ?? 0) + (data?.always_open ?? 0)
  const cutoff = data?.generated_at ? data.generated_at.slice(0, 10) : todayIso
  const dayList = ends.get(selected) ?? []
  const week = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(today)
    d.setDate(d.getDate() + 1 + i)
    const ds = iso(d)
    return { ds, n: ends.get(ds)?.length ?? 0 }
  })
  const weekMax = Math.max(1, ...week.map((w) => w.n))
  const dleft = (ds: string) => Math.round((new Date(ds + 'T00:00:00').getTime() - new Date(todayIso + 'T00:00:00').getTime()) / 86400000)

  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[43px] pb-[110px]">
        <h1 className="text-[28px] font-bold leading-10 tracking-[-0.6px] text-[#272727]">모집 캘린더</h1>
        <p className="mt-1 text-base leading-6 tracking-[-0.16px] text-[#666]">
          마감일이 적힌 공고 <b className="font-bold text-(--color-accent)">{extracted.toLocaleString()}건</b>을 달력에 모았어요. 전체{' '}
          {data?.total ?? 0}건 중 기간 추출 {extracted}건{data?.generated_at ? ` · 갱신 ${data.generated_at.slice(0, 10)}` : ''}
        </p>

        <div className="mt-[25px] flex flex-wrap items-center gap-x-1.5 gap-y-2">
          <RoundBtn label="이전 달" onClick={() => move(-1)}>
            ‹
          </RoundBtn>
          <span className="mx-[14px] text-[26px] font-bold leading-[37px] tracking-[-0.4px] text-[#272727] tabular-nums">
            {y}. {String(m + 1).padStart(2, '0')}
          </span>
          <RoundBtn label="다음 달" onClick={() => move(1)}>
            ›
          </RoundBtn>
          <Pill
            on={false}
            className="ml-2 mr-4"
            onClick={() => {
              setCursor({ y: today.getFullYear(), m: today.getMonth() })
              pickDay(todayIso)
            }}
          >
            오늘
          </Pill>
          {FILTERS.map((f) => (
            <Pill key={f.key} on={filter === f.key} onClick={() => setFilter(f.key)}>
              {f.label}
            </Pill>
          ))}
          <span className="ml-auto flex items-center gap-[5px] text-[13px] text-[#666]">
            <span className="w-2.5 h-2.5 rounded-[3px] bg-[#4f7cf0]" /> 시작
            <span className="ml-[13px] w-2.5 h-2.5 rounded-[3px] bg-(--color-accent)" /> 마감
            <span className="ml-[13px]">이 달 마감</span>
            <b className="font-bold text-(--color-accent) tabular-nums">{monthClose}건</b>
          </span>
        </div>

        {/* 달력 */}
        <div className="mt-[27px] overflow-x-auto">
          <div className="min-w-[840px] grid grid-cols-7">
            {WEEKDAYS.map((w, i) => (
              <div
                key={w}
                className={'h-[45px] border-b border-[#e2e2e2] text-center text-[15px] font-bold leading-[45px] ' + (i === 0 ? 'text-(--color-accent)' : i === 6 ? 'text-[#4f7cf0]' : 'text-[#474747]')}
              >
                {w}
              </div>
            ))}
            {cells.map((day, i) => {
              if (day === null) return <div key={i} className="h-[150px] bg-[#f7f9fa] border-b border-[#eee]" />
              const ds = iso(new Date(y, m, day))
              const e = ends.get(ds) ?? []
              const s = starts.get(ds) ?? []
              // 데이터를 만든 날보다 앞선 날은 비워 둔다 — 마감이 지난 공고는 캘린더에서 빠졌고,
              // 지난 시작일만 남으면 일정처럼 읽힌다. 기준이 오늘이 아니라 갱신일인 것은 갱신 뒤 하루이틀
              // 동안에도 그 사이 마감을 보여 주기 위해서다.
              const rows = ds < cutoff ? [] : [...e.map((it) => ({ it, end: true })), ...s.map((it) => ({ it, end: false }))]
              const isToday = ds === todayIso
              const isSel = ds === selected
              const wd = i % 7
              return (
                <div
                  key={i}
                  className={
                    'relative h-[150px] px-3 pt-[10px] border-b border-[#eee] ' +
                    (isToday ? 'bg-[#fff7f7] shadow-[inset_0_0_0_2px_#f45757]' : isSel ? 'shadow-[inset_0_0_0_2px_#272727]' : '')
                  }
                >
                  <button type="button" onClick={() => pickDay(ds)} className="flex items-center gap-1.5" aria-label={`${m + 1}월 ${day}일 마감 공고 보기`}>
                    <span className={'text-[15px] font-bold leading-[21px] tabular-nums ' + (wd === 0 ? 'text-(--color-accent)' : wd === 6 ? 'text-[#4f7cf0]' : 'text-[#272727]')}>
                      {day}
                    </span>
                    {isToday && <span className="h-5 px-[7px] rounded-[10px] bg-(--color-accent) text-[11px] font-medium leading-5 text-white">오늘</span>}
                  </button>
                  <ul className="mt-[7px] flex flex-col gap-[3px]">
                    {rows.slice(0, 3).map(({ it, end }, k) => (
                      <li key={k} className="flex items-center gap-[5px] min-w-0">
                        <span className={'shrink-0 grid place-items-center w-[18px] h-[18px] rounded text-[10px] text-white ' + (end ? 'bg-(--color-accent)' : 'bg-[#4f7cf0]')}>
                          {end ? '끝' : '시'}
                        </span>
                        <a href={it.url} target="_blank" rel="noreferrer" title={it.title} className="truncate text-[13px] leading-[19px] text-[#272727] hover:underline">
                          {plainCompany(it.company)}
                        </a>
                      </li>
                    ))}
                  </ul>
                  {rows.length > 3 && (
                    <button type="button" onClick={() => pickDay(ds)} className="mt-[3px] text-xs text-[#999] hover:text-[#272727]">
                      +{rows.length - 3}건 더보기
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* 아래 두 칸 */}
        <div className="mt-[47px] flex flex-col lg:flex-row gap-6 items-start">
          <section className="w-full lg:w-[712px] shrink-0 rounded-[30px] border border-[#e2e8ec] px-[29px] pt-[26px] pb-[27px]">
            <div className="flex items-baseline justify-between gap-2 pb-[14px] border-b-2 border-[#272727]">
              <h2 className="text-xl font-bold leading-[29px] tracking-[-0.2px] text-[#272727]">
                {selected === todayIso ? '오늘' : md(selected)} <span className="font-black text-(--color-accent)">마감</span>되는 공고
              </h2>
              <span className="text-sm text-[#777] tabular-nums">
                {md(selected).replace(' ', '')} · {dayList.length}건
              </span>
            </div>
            <ul>
              {dayList.slice(0, shown).map((it) => {
                const left = dleft(selected)
                return (
                  <li key={it.url} className="border-b border-[#eef1f3]">
                    <a href={it.url} target="_blank" rel="noreferrer" className="group flex items-center gap-[14px] min-h-[71px] pl-0.5">
                      <span className="grid place-items-center w-10 h-10 rounded-[10px] overflow-hidden shrink-0">
                        <CompanyMark name={it.company} size={40} />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm leading-[21px] text-[#666] truncate">{plainCompany(it.company)}</span>
                        <span className="block text-base font-medium leading-6 tracking-[-0.16px] text-[#272727] truncate group-hover:underline underline-offset-2">{it.title}</span>
                      </span>
                      <span className="shrink-0 rounded bg-[#f67979] px-[7px] text-[13px] leading-[22px] text-white tabular-nums">
                        {left <= 0 ? '오늘 마감' : `D-${left}`}
                      </span>
                    </a>
                  </li>
                )
              })}
              {dayList.length === 0 && <li className="py-12 text-center text-sm text-[#999]">이날 마감되는 공고가 없어요.</li>}
            </ul>
            {dayList.length > LIST_STEP && (
              <button
                type="button"
                onClick={() => setShown((n) => (n >= dayList.length ? LIST_STEP : dayList.length))}
                className="mt-[19px] w-full inline-flex items-center justify-center gap-2 h-11 rounded-[30px] bg-[#272727] text-base font-medium text-white hover:bg-black"
              >
                {shown >= dayList.length ? '접기' : `${selected === todayIso ? '오늘' : md(selected)} 마감 전체 보기`}
                <svg width="8" height="10" viewBox="0 0 8 10" fill="none" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" aria-hidden>
                  <path d="M2.5 1.5 6 5l-3.5 3.5" />
                </svg>
              </button>
            )}
          </section>

          <section className="flex-1 min-w-0 w-full rounded-[30px] border border-[#e2e8ec] px-[29px] pt-[26px] pb-[29px]">
            <div className="flex items-baseline justify-between gap-2 pb-[14px] border-b-2 border-[#272727]">
              <h2 className="text-xl font-bold leading-[29px] tracking-[-0.2px] text-[#272727]">이번 주 마감 일정</h2>
              <span className="text-sm text-[#777] tabular-nums">
                {md(week[0].ds).split(' ')[0]} ~ {md(week[6].ds).split(' ')[0]}
              </span>
            </div>
            <ul className="mt-5 flex flex-col gap-[14px]">
              {week.map((w) => (
                <li key={w.ds}>
                  <button type="button" onClick={() => pickDay(w.ds)} className="w-full flex items-center text-left">
                    <span className={'w-[106px] shrink-0 text-[15px] leading-[21px] tabular-nums ' + (w.ds === selected ? 'font-bold text-[#272727]' : 'text-[#474747]')}>{md(w.ds)}</span>
                    <span className="flex-1 h-4 rounded-lg bg-[#f1f3f5] overflow-hidden">
                      <span className="block h-full rounded-lg bg-[#f67979]" style={{ width: `${(w.n / weekMax) * 100}%` }} />
                    </span>
                    <span className="w-[57px] shrink-0 text-right text-[15px] font-medium text-[#272727] tabular-nums">{w.n}건</span>
                  </button>
                </li>
              ))}
            </ul>
            <p className="mt-[23px] rounded-[14px] bg-[#f7f9fa] px-[18px] py-4 text-sm leading-[21px] text-[#666]">
              <b className="mr-[5px] font-bold text-(--color-accent)">TIP</b>
              마감 표기가 없는 공고 {Math.max(0, (data?.total ?? 0) - extracted).toLocaleString()}건은{' '}
              <a href={paths.jobs()} onClick={onLinkClick(paths.jobs())} className="underline underline-offset-2 hover:text-[#272727]">
                잡 리스트
              </a>
              에서 확인할 수 있어요.
            </p>
          </section>
        </div>
      </div>
      <SiteFooter updated={data?.generated_at} jobs={data?.total} />
    </div>
  )
}

function RoundBtn({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" aria-label={label} onClick={onClick} className="w-[34px] h-[34px] rounded-full border border-[#d8d8d8] text-lg leading-none text-[#474747] hover:border-[#272727]">
      {children}
    </button>
  )
}

function Pill({ on, onClick, className = '', children }: { on: boolean; onClick: () => void; className?: string; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={
        'h-[34px] px-[14px] rounded-[18px] border text-[13px] font-medium tracking-[-0.3px] ' +
        (on ? 'bg-(--color-accent) border-(--color-accent) text-white' : 'bg-white border-[#d8d8d8] text-[#272727] hover:border-[#272727]') +
        ' ' +
        className
      }
    >
      {children}
    </button>
  )
}
