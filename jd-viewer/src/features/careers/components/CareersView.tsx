import { useEffect, useRef, useState, type ReactNode } from 'react'
import { SiteFooter } from '../../../components/SiteFooter'
import { Loader } from '../../../components/ui'
import { navigate, onLinkClick, useRoute, useSetQuery } from '../../../utils/navigation'
import { absUrl, useSeo } from '../../../utils/seo'
import { paths } from '../../../utils/urls'
import {
  FILTER_KEYS,
  fetchOverview,
  fetchRoster,
  fetchStories,
  type Count,
  type FilterKey,
  type Filters,
  type Overview,
  type Spec,
  type StoryBrief,
  type Voice,
} from '../api'
import { useAsync } from '../hooks/useAsync'
import { Chip, CountList, Items, Kpi, KpiRow, Section, Steps, Table } from './parts'
import { med, pctText } from '../utils/format'
import { StoryView } from './StoryView'
import { PrepGuide } from '../../prep/components/PrepGuide'

// 학습 › 취업후기 — 합격·이직·전환 후기를 연도·회사·회사 유형으로 잘라 본다.
// 원본 글은 DB(career_post)에 있고, 이 화면은 그 글에서 뽑은 구조화 값(스펙·경로·전형·서류)을 센다.
// 혼자 보는 화면이라 색인하지 않는다(robots Disallow /careers).
//
// 모양은 캐치형 시안 J03(Penpot JD Viewer · 35 취업후기)을 따른다. 어느 탭을 눌러도 틀이 그대로다 —
// 제목·KPI·거르기 줄·탭 줄은 늘 같은 자리에 있고 바뀌는 것은 탭 내용뿐이다(거르기가 안 걸리는 탭은 줄을 숨기지
// 않고 잠근다 — 숨기면 탭 줄이 위로 튄다). 불러오는 중·실패도 같은 틀 안의 내용 칸에서만 보인다.
const NOINDEX = 'noindex, nofollow'

/** 탭 세 묶음 — 모아 보기 / 사람·과정 / 기록. */
const TAB_GROUPS = [
  [
    ['year', '연도별'],
    ['type', '회사 유형별'],
    ['company', '회사별'],
  ],
  [
    ['spec', '스펙'],
    ['moves', '이직·커리어'],
    ['paths', '경로·전형'],
    ['prep', '전형별 준비'],
  ],
  [
    ['applied', '지원 결과'],
    ['docs', '서류·조언'],
    ['roster', '합격자 명단'],
    ['list', '후기 목록'],
  ],
] as const
const TABS = TAB_GROUPS.flat()
type TabId = (typeof TABS)[number][0]
/** 연도·회사 거르기가 걸리지 않는 탭 — 거르기 줄을 잠근다. */
const UNFILTERED: TabId[] = ['prep', 'roster']

export function CareersView({ seg }: { seg: string[] }) {
  if (seg[0]) return <StoryView id={seg[0]} />
  return <Dashboard />
}

const stamp = (iso: string | null | undefined) => {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function Dashboard() {
  const { query } = useRoute()
  const setQuery = useSetQuery()
  const f: Filters = {}
  for (const k of FILTER_KEYS) {
    const v = query.get(k)
    if (v) f[k] = v
  }
  const tab = (TABS.find(([id]) => id === query.get('tab'))?.[0] ?? 'year') as TabId
  const fkey = FILTER_KEYS.map((k) => f[k] ?? '').join('|')
  const [retry, setRetry] = useState(0)
  const { data, error, loading } = useAsync((s) => fetchOverview(f, s), `${fkey}#${retry}`)

  useSeo({ title: '취업후기', description: '혼자 보는 취업 자료', robots: NOINDEX, canonical: absUrl(paths.careers()) })

  const set = (k: string, v: string | null) => setQuery(k, v)
  const toggle = (k: string, v: string) => set(k, f[k as keyof Filters] === v ? null : v)
  const o = data
  const locked = UNFILTERED.includes(tab)

  let body: ReactNode
  if (tab === 'prep') body = <PrepGuide />
  else if (tab === 'roster') body = <RosterPanel />
  else if (!o && loading) body = <Loader label="후기 세는 중…" />
  else if (!o) body = <LoadError detail={error ?? ''} onRetry={() => setRetry((n) => n + 1)} />
  else if (o.n === 0 && tab !== 'list')
    body = (
      <p className="border-t border-[#EEEEEE] py-16 text-sm text-[#666]">
        고른 조건에 맞는 경험담이 없다. 거르기를 줄이거나{' '}
        <button type="button" className="text-[#272727] underline" onClick={() => navigate(paths.careers() + (tab === 'year' ? '' : `?tab=${tab}`), { replace: true })}>
          모두 지우기
        </button>
        로 처음부터 본다.
      </p>
    )
  else
    body = (
      <>
        {tab === 'year' && <ByYear o={o} pick={(y) => toggle('year', String(y))} />}
        {tab === 'type' && <ByType o={o} pickType={(t) => toggle('type', t)} pickCompany={(c) => set('company', c)} />}
        {tab === 'company' && <ByCompany o={o} f={f} pick={(c) => toggle('company', c)} />}
        {tab === 'spec' && <SpecPanel s={o.spec} />}
        {tab === 'moves' && <Moves o={o} pickOrigin={(v) => toggle('origin', v)} pickType={(v) => toggle('type', v)} />}
        {tab === 'paths' && <PathsPanel o={o} />}
        {tab === 'applied' && <Applied o={o} />}
        {tab === 'docs' && <Docs o={o} />}
        {tab === 'list' && <StoryListPanel f={f} fkey={fkey} />}
      </>
    )

  const filtered = !!o && Object.keys(o.filters).length > 0
  const at = stamp(o?.updated_at)
  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[43px] pb-[120px]">
        <div className="flex items-start justify-between gap-6">
          <div>
            <h1 className="text-[28px] font-bold leading-10 tracking-[-0.6px] text-[#272727]">취업후기</h1>
            <p className="mt-1 text-base leading-6 text-[#666]">
              개발자 합격·이직·전환 후기{o ? ` ${o.total.posts.toLocaleString()}편` : ''}을 모아 경험담으로 정리했다.
            </p>
            <p className="mt-2 text-sm leading-5 text-[#666]">원문은 DB에 보관한다(열쇠가 있어야 열린다). 글쓴이 이름·아이디는 저장하지 않는다.</p>
          </div>
          {at && <p className="shrink-0 pt-3 text-sm text-[#666] tabular-nums">기준 {at}</p>}
        </div>

        <div className="mt-8 min-h-[129px]">
          {o && (
            <KpiRow>
              <Kpi label={filtered ? '고른 경험담' : '경험담'} value={o.n.toLocaleString()} unit="건" sub={filtered ? `전체 ${o.total.counted.toLocaleString()}` : undefined} />
              <Kpi label="경력직 이직·전환" value={o.moves.n.toLocaleString()} unit="건" sub={`그 전 경력이 있는 글 · 경력 중앙값 ${med(o.spec.years_before.median, '년')}`} />
              <Kpi label="스펙을 밝힌 사람" value={o.spec.with_spec.toLocaleString()} unit="명" sub={`학점 중앙값 ${med(o.spec.gpa.median)} / 4.5`} />
              <Kpi label="회사" value={o.companies.length.toLocaleString()} unit="곳" sub={`교육과정 ${o.programs.length}곳`} />
            </KpiRow>
          )}
        </div>

        {/* 잠긴 탭의 안내는 흐름 밖에 둔다 — 탭 줄이 어느 탭에서나 같은 자리에 있게 */}
        <div className="relative">
          <FilterBar o={o} f={f} toggle={toggle} set={set} locked={locked || !o} />
          {locked && <p className="absolute left-0 top-full mt-1.5 text-sm text-[#666]">이 탭에는 연도·회사 거르기가 걸리지 않는다.</p>}
        </div>

        <div role="tablist" className="mt-8 flex items-center overflow-x-auto no-scrollbar border-b border-[#EEEEEE]">
          {TAB_GROUPS.map((g, gi) => (
            <div key={gi} className="flex shrink-0 items-center">
              {gi > 0 && <span aria-hidden className="mx-3 h-4 w-px bg-[#EEEEEE]" />}
              {g.map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={tab === id}
                  onClick={() => set('tab', id === 'year' ? null : id)}
                  className={
                    'relative shrink-0 px-4 pb-3 pt-1 text-[16px] first:pl-0 ' +
                    (tab === id
                      ? 'font-bold text-[#272727] after:absolute after:inset-x-4 after:-bottom-px after:h-[2px] after:bg-[#272727] first:after:left-0'
                      : 'font-medium text-[#666] hover:text-[#272727]')
                  }
                >
                  {label}
                </button>
              ))}
            </div>
          ))}
        </div>

        <div className={'mt-8 ' + (o && loading ? 'opacity-60 transition-opacity' : '')}>{body}</div>
      </div>
      <SiteFooter />
    </div>
  )
}

// ── 불러오기 실패 — 틀은 그대로, 내용 칸에서만 ─────────────────────────

function LoadError({ detail, onRetry }: { detail: string; onRetry: () => void }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border-t border-[#EEEEEE] py-16">
      <h2 className="text-[16px] font-bold text-[#272727]">취업후기를 불러오지 못했다</h2>
      <p className="mt-1 text-sm text-[#666]">뷰어 API 가 응답하지 않는다. 잠시 뒤 다시 시도한다.</p>
      <div className="mt-4 flex items-center gap-4">
        <button type="button" onClick={onRetry} className="h-9 rounded-full border border-[#D8D8D8] px-4 text-sm font-medium text-[#272727] hover:border-[#272727]">
          다시 시도
        </button>
        <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} className="text-sm text-[#666] underline">
          자세히 {open ? '⌃' : '⌄'}
        </button>
      </div>
      {open && (
        <div className="mt-3 text-sm leading-6 text-[#666]">
          {detail && <p>{detail} (/api/careers)</p>}
          <p>
            뷰어 API <code>/api/careers</code> 가 DB(019)를 읽는다. 적재: <code>python -m store.ingest.careers</code>
          </p>
        </div>
      )}
    </div>
  )
}

// ── 거르기 — 한 줄: 축 다섯 개 드롭다운 + 검색 ─────────────────────────

const AXES: [FilterKey, string, keyof Overview['facets']][] = [
  ['year', '연도', 'years'],
  ['type', '회사 유형', 'types'],
  ['level', '경력', 'levels'],
  ['kind', '종류', 'kinds'],
  ['role', '직무', 'roles'],
]

function FilterBar({
  o,
  f,
  toggle,
  set,
  locked,
}: {
  o: Overview | null
  f: Filters
  toggle: (k: string, v: string) => void
  set: (k: string, v: string | null) => void
  locked: boolean
}) {
  const [q, setQ] = useState(f.q ?? '')
  const [open, setOpen] = useState<FilterKey | null>(null)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(null)
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(null)
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', esc)
    }
  }, [open])

  const company = f.company && o && (o.companies.find((c) => c.key === f.company)?.name ?? o.programs.find((p) => p.key === f.company)?.name ?? f.company)
  const any = FILTER_KEYS.some((k) => f[k])
  const pill = 'flex h-9 shrink-0 items-center gap-1.5 rounded-full border px-4 text-sm text-[#272727]'
  return (
    <div ref={ref} className={'mt-10 flex flex-wrap items-center gap-2 ' + (locked ? 'pointer-events-none opacity-40' : '')} aria-disabled={locked}>
      {AXES.map(([k, label, facet]) => {
        const v = f[k]
        const items = (o?.facets[facet] ?? []) as (Count | [number, number])[]
        return (
          <div key={k} className="relative">
            <div className={pill + (v ? ' border-[#272727] font-bold' : ' border-[#D8D8D8] hover:border-[#272727]')}>
              <button type="button" aria-haspopup="listbox" aria-expanded={open === k} onClick={() => setOpen(open === k ? null : k)} className="flex items-center gap-1.5">
                {v ? `${label} · ${v}` : `${label} 전체`}
                {!v && <Caret />}
              </button>
              {v && (
                <button type="button" aria-label={`${label} 거르기 지우기`} onClick={() => set(k, null)} className="-mr-1 px-1">
                  ×
                </button>
              )}
            </div>
            {open === k && (
              <ul role="listbox" className="absolute left-0 top-[calc(100%+8px)] z-20 max-h-[360px] w-[240px] overflow-auto rounded-lg border border-[#D8D8D8] bg-white py-2">
                {[['전체', null] as [string, number | null], ...items.map(([x, n]) => [String(x), n] as [string, number])].map(([x, n]) => {
                  const on = n === null ? !v : v === x
                  return (
                    <li key={x}>
                      <button
                        type="button"
                        role="option"
                        aria-selected={on}
                        onClick={() => {
                          if (n === null) set(k, null)
                          else toggle(k, x)
                          setOpen(null)
                        }}
                        className={'flex w-full items-center gap-2 px-4 py-1.5 text-left text-sm text-[#272727] hover:bg-[#FAFAFA] ' + (on ? 'font-bold' : '')}
                      >
                        <span className="w-3 shrink-0">{on ? '✓' : ''}</span>
                        <span className="flex-1 break-keep">{x}</span>
                        {n !== null && <span className={'tabular-nums ' + (on ? '' : 'text-[#666]')}>{n.toLocaleString()}</span>}
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        )
      })}
      {company && (
        <div className={pill + ' border-[#272727] font-bold'}>
          회사 · {company}
          <button type="button" aria-label="회사 거르기 지우기" onClick={() => set('company', null)} className="-mr-1 px-1">
            ×
          </button>
        </div>
      )}
      {f.origin && (
        <div className={pill + ' border-[#272727] font-bold'}>
          출발지 · {f.origin}
          <button type="button" aria-label="출발지 거르기 지우기" onClick={() => set('origin', null)} className="-mr-1 px-1">
            ×
          </button>
        </div>
      )}
      {any && (
        <button
          type="button"
          className="ml-1 text-sm text-[#272727] underline"
          onClick={() => {
            const tab = new URLSearchParams(window.location.search).get('tab')
            navigate(paths.careers() + (tab ? `?tab=${tab}` : ''), { replace: true })
            setQ('')
          }}
        >
          모두 지우기
        </button>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          set('q', q.trim() || null)
        }}
        className="ml-auto flex h-9 w-[280px] items-center rounded-full border border-[#D8D8D8] pl-4 pr-2 focus-within:border-[#272727]"
      >
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="제목·회사·기술 검색" className="min-w-0 flex-1 bg-transparent text-sm text-[#272727] outline-none placeholder:text-[#666]" />
        <button type="submit" aria-label="찾기" className="p-1 text-[#272727]">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-3.5-3.5" />
          </svg>
        </button>
      </form>
    </div>
  )
}

function Caret() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden>
      <path d="m6 9 6 6 6-6" />
    </svg>
  )
}

// ── 연도별 ──────────────────────────────────────────────────────────────

const names = (xs: Count[], n = 3) => <Items xs={xs.slice(0, n).map((x) => x[0])} />
/** 신입·경력 칸 — '건수 (비율)', 표본이 3건 미만이라 비율이 없으면 건수만. */
const countPct = (xs: Count[], label: string) => {
  const x = xs.find((v) => v[0] === label)
  if (!x) return '—'
  const p = pctText(x[1], x[2])
  return p ? `${x[1].toLocaleString()} (${p})` : x[1].toLocaleString()
}
const medN = (m: { n: number; median: number | null }) => (m.n ? `${m.median} (${m.n})` : '—')

function ByYear({ o, pick }: { o: Overview; pick: (y: number) => void }) {
  const unknown = o.n - o.by_year.reduce((a, y) => a + y.n, 0)
  return (
    <div>
      <p className="text-sm leading-6 text-[#666]">
        연도는 글에 밝힌 사건 연도이고, 밝히지 않은 글은 게시 연도로 셌다. 줄을 누르면 그해만 본다.
        <br />
        신입·경력은 건수(비율)이고, 경험담이 3건 미만인 해는 건수만 쓴다. 연도 미상은 연도 값이 없는 경험담으로, 건수만 있다.
      </p>
      <div className="mt-6">
        <Table head={['연도', '경험담', '신입', '경력', '자격증', '어학', '알고리즘', '학점', '나이', '그 전 경력(년)', '간 곳']} minWidth={1180}>
          {o.by_year.map((y) => (
            <tr key={y.year} onClick={() => pick(y.year)} className="cursor-pointer border-b border-[#EEEEEE] align-top hover:bg-[#FAFAFA]">
              <td className="py-3 pr-4 font-medium tabular-nums">{y.year}</td>
              <td className="py-3 pr-4 tabular-nums">{y.n.toLocaleString()}</td>
              <td className="whitespace-nowrap py-3 pr-4 tabular-nums">{countPct(y.levels, '신입')}</td>
              <td className="whitespace-nowrap py-3 pr-4 tabular-nums">{countPct(y.levels, '경력')}</td>
              <td className="w-[200px] py-3 pr-4">{names(y.certs)}</td>
              <td className="w-[150px] py-3 pr-4">{names(y.language, 2)}</td>
              <td className="w-[170px] py-3 pr-4">{names(y.algorithm, 2)}</td>
              <td className="whitespace-nowrap py-3 pr-4 tabular-nums">{medN(y.gpa)}</td>
              <td className="whitespace-nowrap py-3 pr-4 tabular-nums">{medN(y.age)}</td>
              <td className="whitespace-nowrap py-3 pr-4 tabular-nums">{medN(y.years_before)}</td>
              <td className="w-[180px] py-3 pr-4">{names(y.types.filter((t) => t[0] !== '미분류'), 3)}</td>
            </tr>
          ))}
          {unknown > 0 && (
            <tr className="border-b border-[#EEEEEE]">
              <td className="whitespace-nowrap py-3 pr-4 font-medium">연도 미상</td>
              <td className="py-3 pr-4 tabular-nums">{unknown.toLocaleString()}</td>
              <td colSpan={9} />
            </tr>
          )}
        </Table>
      </div>
      {o.by_year.length === 1 && (
        <div className="mt-16">
          <SpecPanel s={o.by_year[0]} />
        </div>
      )}
    </div>
  )
}

// ── 회사 유형·회사 ──────────────────────────────────────────────────────

const counted = (xs: Count[], n: number, pct = false, empty = '—') => (
  <Items
    sep=" · "
    empty={empty}
    xs={xs.slice(0, n).map(([label, k, p]) => {
      const t = pct ? pctText(k, p) : null
      return `${label} ${k.toLocaleString()}${t ? `(${t})` : ''}`
    })}
  />
)
const share = (xs: Count[], label: string) => {
  const x = xs.find((v) => v[0] === label)
  return x ? (pctText(x[1], x[2]) ?? `${x[1]}건`) : '—'
}

function ByType({ o, pickType, pickCompany }: { o: Overview; pickType: (t: string) => void; pickCompany: (key: string) => void }) {
  const keyOf = (name: string) => o.companies.find((c) => c.name === name)?.key ?? name
  return (
    <div>
      <p className="text-sm text-[#666]">유형 이름을 누르면 그 유형만, 회사 이름을 누르면 그 회사만 본다.</p>
      <div className="mt-6">
        <Table head={['회사 유형', '신입 · 경력', '학점 · 나이 · 경력', '회사', '자격증', '학력']} minWidth={1180}>
          {o.by_type.map((t) => (
            <tr key={t.type} className="border-b border-[#EEEEEE] align-top">
              <td className="w-[140px] py-4 pr-4">
                <button type="button" onClick={() => pickType(t.type)} className="text-left font-medium hover:underline">
                  {t.type}
                </button>
                <div className="text-[#666] tabular-nums">{t.n.toLocaleString()}건</div>
              </td>
              <td className="w-[100px] whitespace-nowrap py-4 pr-4 tabular-nums">
                신입 {share(t.levels, '신입')}
                <br />
                경력 {share(t.levels, '경력')}
              </td>
              <td className="w-[120px] whitespace-nowrap py-4 pr-4 tabular-nums">
                학점 {med(t.gpa.median)}
                <br />
                나이 {med(t.age.median)}
                <br />
                경력 {med(t.years_before.median, '년')}
              </td>
              <td className="py-4 pr-4">
                {t.companies.length ? (
                  t.companies.slice(0, 8).map(([c, k], i) => (
                    <span key={c}>
                      {i > 0 && ' · '}
                      <button type="button" onClick={() => pickCompany(keyOf(c))} className="whitespace-nowrap hover:underline">
                        {c} {k}
                      </button>
                    </span>
                  ))
                ) : (
                  <span className="text-[#666]">회사 밝히지 않음</span>
                )}
              </td>
              <td className="w-[240px] py-4 pr-4">{counted(t.certs, 6, false, '없음')}</td>
              <td className="w-[240px] py-4 pr-4">{counted(t.education, 4, true)}</td>
            </tr>
          ))}
        </Table>
      </div>
    </div>
  )
}

function ByCompany({ o, f, pick }: { o: Overview; f: Filters; pick: (key: string) => void }) {
  const cell = (on: boolean) =>
    'flex items-baseline justify-between gap-2 border-b border-[#EEEEEE] py-2.5 text-left text-sm text-[#272727] hover:bg-[#FAFAFA] ' + (on ? 'font-bold' : '')
  return (
    <div className="flex flex-col gap-16">
      {f.company && <SpecPanel s={o.spec} />}
      <Section title="회사" note="회사 이름을 밝힌 경험담. 누르면 그 회사만 보고, 다른 탭도 그 회사로 바뀐다.">
        <div className="grid grid-cols-2 gap-x-8 border-t border-[#EEEEEE] sm:grid-cols-3 lg:grid-cols-5">
          {o.companies.map((c, i) => (
            <button key={`${c.key}|${c.type ?? ''}|${i}`} type="button" onClick={() => pick(c.key)} aria-pressed={f.company === c.key} className={cell(f.company === c.key)}>
              <span className="min-w-0 break-keep">
                {c.name}
                <span className="block font-normal text-[#666]">{c.type}</span>
              </span>
              <span className="tabular-nums">{c.n}</span>
            </button>
          ))}
        </div>
      </Section>
      <Section title="교육과정·동아리" note="회사가 아니라 부트캠프·동아리·교육과정 선발 후기.">
        <div className="flex flex-wrap gap-2">
          {o.programs.map((p, i) => (
            <Chip key={`${p.key}|${i}`} on={f.company === p.key} onClick={() => pick(p.key)}>
              {p.name} <span className="tabular-nums text-[#666]">{p.n}</span>
            </Chip>
          ))}
        </div>
      </Section>
      {f.company && <StoryListPanel f={f} fkey={`company:${f.company}`} />}
    </div>
  )
}

// ── 스펙 ───────────────────────────────────────────────────────────────

function SpecPanel({ s }: { s: Spec }) {
  return (
    <div className="flex flex-col gap-12">
      <KpiRow>
        <Kpi label="경험담" value={s.n.toLocaleString()} unit="건" sub={`스펙을 밝힌 글 ${s.with_spec.toLocaleString()}`} />
        <Kpi label="학점 중앙값" value={med(s.gpa.median)} unit="/ 4.5" sub={`숫자로 밝힌 ${s.gpa.n}명`} />
        <Kpi label="나이 중앙값" value={med(s.age.median)} unit="세" sub={`밝힌 ${s.age.n}명`} />
        <Kpi label="그 전 경력 중앙값" value={med(s.years_before.median)} unit="년" sub={`경력자 ${s.years_before.n}명`} />
      </KpiRow>
      <div className="grid grid-cols-1 gap-x-12 gap-y-12 md:grid-cols-2 lg:grid-cols-3">
        <Section title="학력" note="원문에 근거가 없으면 '확인되지 않음'.">
          <CountList items={s.education} />
        </Section>
        <Section title="학점(4.5 환산)">
          <CountList items={s.gpa.bands} empty="숫자로 밝힌 사람 없음" />
        </Section>
        <Section title="경력 구분">
          <CountList items={s.levels} />
        </Section>
        <Section title="자격증">
          <CountList items={s.certs} limit={12} />
        </Section>
        <Section title="어학">
          <CountList items={s.language} />
        </Section>
        <Section title="알고리즘" note="백준 티어·프로그래머스 레벨로 묶었다.">
          <CountList items={s.algorithm} />
        </Section>
        <Section title="대외활동">
          <CountList items={s.activities} limit={12} />
        </Section>
        <Section title="인턴">
          <CountList items={s.internships} />
        </Section>
        <Section title="수상">
          <CountList items={s.awards} />
        </Section>
        <Section title="기술 스택">
          <CountList items={s.stack} limit={14} />
        </Section>
        <Section title="거쳐 온 교육과정">
          <CountList items={s.programs} />
        </Section>
      </div>
    </div>
  )
}

// ── 이직·커리어 ─────────────────────────────────────────────────────────

/** 이직 매트릭스 칸 — 남색 한 색의 연한 4단계(값이 클수록 진하게), 글자는 늘 #272727. */
const heat = (v: number, max: number) => {
  if (!v) return 'transparent'
  const r = v / max
  return r >= 0.6 ? '#B9B6DE' : r >= 0.3 ? '#D3D1EC' : r >= 0.1 ? '#E6E5F4' : '#F3F2FA'
}

function Moves({ o, pickOrigin, pickType }: { o: Overview; pickOrigin: (v: string) => void; pickType: (v: string) => void }) {
  const m = o.moves
  const [more, setMore] = useState(false)
  const origins = m.origins.map((x) => x[0]).filter((x) => x !== '확인되지 않음').slice(0, 10)
  const cell = (a: string, b: string) => m.matrix.find((x) => x.origin === a && x.type === b)?.n ?? 0
  // 값이 하나도 없는 유형(열)은 뺀다
  const types = [...new Set(m.matrix.map((x) => x.type))].filter((t) => origins.some((a) => cell(a, t) > 0)).slice(0, 9)
  const cmax = Math.max(1, ...m.matrix.filter((x) => x.origin !== '확인되지 않음').map((x) => x.n))
  const examples = more ? m.examples : m.examples.slice(0, 10)
  return (
    <div className="flex flex-col gap-16">
      <p className="text-sm text-[#666]">
        경력직(경력·이직·직무전환, 그 전 경력이 있는 글) {m.n.toLocaleString()}건. 출발지는 전환 문장과 경로 앞부분에서 읽었다.
      </p>
      <div className="grid grid-cols-1 gap-x-12 gap-y-12 lg:grid-cols-3">
        <Section title="어디서 떠나 왔나" note={`비율 = 경력직 ${m.n.toLocaleString()}건 대비. 누르면 그 출발지만 본다.`}>
          <CountList items={m.origins} onPick={pickOrigin} picked={o.filters.origin} limit={14} />
        </Section>
        <Section title="어떤 전환이었나" note={`비율 = 경험담 ${o.n.toLocaleString()}건 대비`}>
          <CountList items={m.transitions} />
        </Section>
        <Section title="몇 년 차에 옮겼나" note="그 전 경력 구간별 · 간 곳의 유형">
          <ul className="border-t border-[#EEEEEE]">
            {m.years.map((y) => (
              <li key={y.band} className="border-b border-[#EEEEEE] py-2.5 text-sm">
                <div className="flex justify-between text-[#272727]">
                  <span className="font-medium">{y.band}</span>
                  <span className="tabular-nums">{y.n}</span>
                </div>
                <div className="break-keep text-[#666]">
                  {y.types
                    .filter((t) => t[0] !== '미분류')
                    .map((t) => `${t[0]} ${t[1]}`)
                    .join(' · ') || '—'}
                </div>
              </li>
            ))}
          </ul>
        </Section>
      </div>
      <Section title="출발지 → 간 곳(회사 유형)" note="칸의 숫자는 경험담 수. 유형을 누르면 그 유형만 본다. 값이 하나도 없는 유형은 뺐다.">
        <div className="overflow-x-auto">
          <table className="min-w-[720px] w-full break-keep text-sm text-[#272727]">
            <thead>
              <tr>
                <th />
                {types.map((t) => (
                  <th key={t} className="px-1 pb-2 font-medium text-[#666]">
                    <button type="button" onClick={() => pickType(t)} className="hover:text-[#272727] hover:underline">
                      {t}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {origins.map((a) => (
                <tr key={a}>
                  <th className="whitespace-nowrap py-0.5 pr-4 text-left font-medium">{a}</th>
                  {types.map((b) => {
                    const v = cell(a, b)
                    return (
                      <td key={b} className="p-0.5">
                        <div className="flex h-8 items-center justify-center rounded tabular-nums" style={{ background: heat(v, cmax) }}>
                          {v || ''}
                        </div>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
      <Section title="경력직이 간 회사" note="회사 이름을 밝힌 경력직 경험담(교육과정 제외), 많은 순 30곳">
        <div className="grid grid-cols-2 gap-x-8 border-t border-[#EEEEEE] sm:grid-cols-3 lg:grid-cols-5">
          {m.destinations.map((d) => (
            <div key={`${d.company}|${d.type ?? ''}`} className="flex items-baseline justify-between gap-2 border-b border-[#EEEEEE] py-2.5 text-sm">
              <span className="min-w-0 break-keep text-[#272727]">
                {d.company}
                <span className="block text-[#666]">{d.type ?? '—'}</span>
              </span>
              <span className="tabular-nums">{d.n}</span>
            </div>
          ))}
        </div>
      </Section>
      <Section title="이직 경로" note="경로가 두 단계 이상 적힌 경력직 경험담. 최근 것부터. 누르면 그 글의 정리와 원문.">
        <ul className="border-t border-[#EEEEEE]">
          {examples.map((s) => (
            <StoryRow key={s.id} s={s} />
          ))}
        </ul>
        {m.examples.length > 10 && (
          <button type="button" onClick={() => setMore((v) => !v)} className="mt-6 h-9 rounded-full border border-[#D8D8D8] px-4 text-sm font-medium text-[#272727] hover:border-[#272727]">
            {more ? '접기' : `이직 경로 ${m.examples.length - 10}건 더 보기`}
          </button>
        )}
      </Section>
    </div>
  )
}

/** 후기 한 줄 — 제목은 정리 한 줄, 아래에 메타(빈 회사는 여기서 한 번만), 그 아래 경로. 끝에 ›. */
function StoryRow({ s }: { s: StoryBrief }) {
  const to = paths.careersStory(s.id)
  const meta = [
    s.company ?? '회사 밝히지 않음',
    s.company_type,
    s.year,
    s.kind,
    s.role !== '기타' ? s.role : null,
    s.level,
    s.years_before ? `경력 ${s.years_before}년` : null,
    s.origin && s.origin !== '확인되지 않음' ? `${s.origin}에서` : null,
  ]
    .filter(Boolean)
    .join(' · ')
  return (
    <li className="border-b border-[#EEEEEE]">
      <a href={to} onClick={onLinkClick(to)} className="group flex items-center gap-6 py-5 hover:bg-[#FAFAFA]">
        <div className="min-w-0 flex-1">
          <p className="break-keep text-[16px] font-medium leading-6 text-[#272727] group-hover:underline">{s.summary ?? s.title ?? meta}</p>
          <p className="mt-1 break-keep text-sm text-[#666]">{meta}</p>
          {s.steps.length > 0 && (
            <div className="mt-1">
              <Steps steps={s.steps} />
            </div>
          )}
        </div>
        <span aria-hidden className="shrink-0 pr-2 text-[18px] text-[#666]">
          ›
        </span>
      </a>
    </li>
  )
}

// ── 경로·전형 ───────────────────────────────────────────────────────────

function PathsPanel({ o }: { o: Overview }) {
  const p = o.paths
  return (
    <div className="grid grid-cols-1 gap-x-12 gap-y-12 md:grid-cols-2 lg:grid-cols-3">
      <Section title="거쳐 온 길" note="경로 단계에 나온 갈래(한 글에 여럿).">
        <CountList items={p.tags} />
      </Section>
      <Section title="준비 방법" note={`준비 기간 중앙값 ${med(p.prep_months.median, '개월')} (${p.prep_months.n}명)`}>
        <CountList items={p.prep} limit={12} />
      </Section>
      <Section title="면접 단계">
        <CountList items={p.interviews} />
      </Section>
      <Section title="코딩테스트" className="md:col-span-2 lg:col-span-3">
        <CountList items={p.coding_test} />
      </Section>
    </div>
  )
}

// ── 지원 결과 ───────────────────────────────────────────────────────────

function Applied({ o }: { o: Overview }) {
  return (
    <Section title="같이 지원한 곳 — 붙고 떨어진 자리" note="경험담에 함께 적힌 다른 지원처. 떨어진 단계는 밝힌 것만.">
      <Table head={['회사', '합격', '탈락', '주로 떨어진 단계']} minWidth={600}>
        {o.applied.map((a, i) => (
          <tr key={`${a.company}|${i}`} className="border-b border-[#EEEEEE]">
            <td className="py-3 pr-4 font-medium">{a.company}</td>
            <td className="py-3 pr-4 tabular-nums">{a.pass}</td>
            <td className="py-3 pr-4 tabular-nums">{a.fail}</td>
            <td className="py-3 pr-4 text-[#666]">{a.stages.map((s) => `${s[0]} ${s[1]}`).join(' · ') || '—'}</td>
          </tr>
        ))}
      </Table>
    </Section>
  )
}

// ── 서류·조언 ───────────────────────────────────────────────────────────

function VoiceList({ xs }: { xs: Voice[] }) {
  if (!xs.length) return <p className="text-sm text-[#666]">없음</p>
  return (
    <ul className="border-t border-[#EEEEEE]">
      {xs.map((v, i) => {
        const to = paths.careersStory(v.id)
        return (
          <li key={`${v.id}|${i}`} className="border-b border-[#EEEEEE]">
            <a href={to} onClick={onLinkClick(to)} className="block py-2.5 text-sm leading-6 text-[#272727] hover:underline">
              {v.t}
              <span className="ml-1.5 text-[#666]">{[v.company, v.year].filter(Boolean).join(' · ')}</span>
            </a>
          </li>
        )
      })}
    </ul>
  )
}

function Docs({ o }: { o: Overview }) {
  const d = o.docs
  const sec = (title: string, xs: Count[]) => (
    <Section title={title}>
      <CountList items={xs} limit={12} />
    </Section>
  )
  return (
    <div className="flex flex-col gap-16">
      <div className="grid grid-cols-1 gap-x-12 gap-y-12 md:grid-cols-2 lg:grid-cols-3">
        {sec('이력서에서 한 것', d.resume_points)}
        {sec('포트폴리오에서 한 것', d.portfolio_points)}
        {sec('포트폴리오에 넣은 프로젝트', d.portfolio_projects)}
        {sec('자기소개서에서 한 것', d.cover_letter_points)}
        {sec('자기소개서 문항', d.cover_letter_questions)}
      </div>
      <div className="grid grid-cols-1 gap-x-12 gap-y-12 lg:grid-cols-3">
        <Section title="붙은 이유로 꼽은 것">
          <VoiceList xs={o.voices.factors} />
        </Section>
        <Section title="해 주는 말">
          <VoiceList xs={o.voices.advice} />
        </Section>
        <Section title="나온 면접 질문">
          <VoiceList xs={o.voices.questions} />
        </Section>
      </div>
    </div>
  )
}

// ── 합격자 명단 ─────────────────────────────────────────────────────────

function RosterPanel() {
  const { data, error, loading } = useAsync((s) => fetchRoster(s), 'roster')
  if (loading && !data) return <Loader label="명단 여는 중…" />
  if (!data) return <LoadError detail={error ?? ''} onRetry={() => window.location.reload()} />
  return (
    <div className="flex flex-col gap-16">
      <p className="text-sm text-[#666]">
        학원·학과·부트캠프가 올린 '합격자 명단' 카드 {data.posts}장에서 읽은 {data.people.toLocaleString()}명(IT 쪽만). 이름은 읽지도 저장하지도 않았다.
      </p>
      <div className="grid grid-cols-1 gap-x-12 gap-y-12 lg:grid-cols-3">
        <Section title="연도">
          <CountList items={data.years.map(([y, n]) => [String(y), n] as Count)} />
        </Section>
        <Section title="출신 학교" className="lg:col-span-2">
          <CountList items={data.schools} limit={20} />
        </Section>
      </div>
      <Section title="합격처별">
        <Table head={['합격처', '인원', '전공자', '학교', '전공', '연도']} minWidth={720}>
          {data.orgs.map((g, i) => (
            <tr key={`${g.org}|${i}`} className="border-b border-[#EEEEEE] align-top">
              <td className="py-3 pr-4 font-medium">
                {g.org}
                {g.type && <span className="block font-normal text-[#666]">{g.type}</span>}
              </td>
              <td className="py-3 pr-4 tabular-nums">{g.n}</td>
              <td className="py-3 pr-4 tabular-nums">{g.n ? `${Math.round((100 * g.cs) / g.n)}%` : '—'}</td>
              <td className="py-3 pr-4">{names(g.schools, 5)}</td>
              <td className="py-3 pr-4">{names(g.majors, 3)}</td>
              <td className="py-3 pr-4 tabular-nums text-[#666]">{g.years.map(([y, n]) => `${y}(${n})`).join(' ')}</td>
            </tr>
          ))}
        </Table>
      </Section>
    </div>
  )
}

// ── 후기 목록 ───────────────────────────────────────────────────────────

function StoryListPanel({ f, fkey }: { f: Filters; fkey: string }) {
  const [page, setPage] = useState(0)
  const [retry, setRetry] = useState(0)
  const [prevKey, setPrevKey] = useState(fkey)
  if (prevKey !== fkey) {
    setPrevKey(fkey)
    setPage(0)
  }
  const { data, error } = useAsync((s) => fetchStories(f, page * 40, s), `${fkey}#${page}#${retry}`)
  if (!data) return error ? <LoadError detail={error} onRetry={() => setRetry((n) => n + 1)} /> : <Loader label="목록 여는 중…" />
  const pages = Math.ceil(data.n / 40)
  return (
    <Section title={`후기 ${data.n.toLocaleString()}건`} note="누르면 정리한 값과 원문(열쇠가 있을 때).">
      {data.items.length ? (
        <ul className="border-t border-[#EEEEEE]">
          {data.items.map((s) => (
            <StoryRow key={s.id} s={s} />
          ))}
        </ul>
      ) : (
        <p className="border-t border-[#EEEEEE] py-16 text-sm text-[#666]">고른 조건에 맞는 후기가 없다.</p>
      )}
      {pages > 1 && (
        <div className="mt-8 flex items-center justify-center gap-4 text-sm">
          <button type="button" disabled={page === 0} onClick={() => setPage(page - 1)} className="h-9 rounded-full border border-[#D8D8D8] px-4 text-[#272727] disabled:opacity-40">
            이전
          </button>
          <span className="tabular-nums text-[#666]">
            {page + 1} / {pages}
          </span>
          <button type="button" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)} className="h-9 rounded-full border border-[#D8D8D8] px-4 text-[#272727] disabled:opacity-40">
            다음
          </button>
        </div>
      )}
    </Section>
  )
}
