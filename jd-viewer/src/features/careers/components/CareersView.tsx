import { Fragment, useState } from 'react'
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
  type Filters,
  type Overview,
  type Spec,
  type StoryBrief,
  type Voice,
} from '../api'
import { useAsync } from '../hooks/useAsync'
import { gpa, med } from '../utils/format'
import { FilterBar } from './FilterBar'
import { Inline, Kpi, LINE, PathLine, PillButton, Rows, Section } from './parts'
import { StoryView } from './StoryView'

// 학습 › 취업후기 — 합격·이직·전환 후기를 연도·회사·회사 유형으로 잘라 본다.
// 원본 글은 DB(career_post)에 있고, 이 화면은 그 글에서 뽑은 구조화 값(스펙·경로·전형·서류)을 센다.
// 혼자 보는 화면이라 색인하지 않는다(robots Disallow /careers).
//
// 모양은 Penpot「JD Viewer」35 취업후기(J03 · 캐치형 1920)를 따른다. 가장 먼저 볼 것은 연도별 표다 —
// 거르기를 한 줄로 줄여 표를 첫 화면 안으로 올렸고, 카드·막대·회색 상자를 걷고 선과 글자로 칸을 나눴다.
const NOINDEX = 'noindex, nofollow'

// 탭 11개를 세 묶음으로 — 모아 보기 / 사람·과정 / 기록. 묶음 사이에 세로선.
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
// 거르기가 걸리지 않는 탭 — 거르기 줄을 보이면 걸리는 줄 안다.
const NO_FILTER: TabId[] = ['roster']

export function CareersView({ seg }: { seg: string[] }) {
  if (seg[0]) return <StoryView id={seg[0]} />
  return <Dashboard />
}

const stamp = (iso: string | null) => (iso ? iso.slice(0, 16).replace('T', ' ') : '—')

function Dashboard() {
  const { query } = useRoute()
  const setQuery = useSetQuery()
  const [attempt, setAttempt] = useState(0)
  const f: Filters = {}
  for (const k of FILTER_KEYS) {
    const v = query.get(k)
    if (v) f[k] = v
  }
  const tab = (TABS.find(([id]) => id === query.get('tab'))?.[0] ?? 'year') as TabId
  const fkey = FILTER_KEYS.map((k) => f[k] ?? '').join('|')
  const { data, error, loading } = useAsync((s) => fetchOverview(f, s), `${fkey}#${attempt}`)

  useSeo({ title: '취업후기', description: '혼자 보는 취업 자료', robots: NOINDEX, canonical: absUrl(paths.careers()) })

  const set = (k: string, v: string | null) => setQuery(k, v)
  const toggle = (k: string, v: string) => set(k, f[k as keyof Filters] === v ? null : v)
  const clearAll = () => navigate(paths.careers() + (tab !== 'year' ? `?tab=${tab}` : ''), { replace: true })

  if (!data && loading) return <Loader label="후기 세는 중…" />

  const o = data
  const filtered = !!o && Object.keys(o.filters).length > 0
  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[43px] pb-[120px]">
        <header className="flex items-start justify-between gap-6">
          <div>
            <h1 className="text-[28px] font-bold leading-10 tracking-[-0.6px] text-[#272727]">취업후기</h1>
            <p className="mt-1 text-base leading-6 text-[#666]">
              {o ? `개발자 합격·이직·전환 후기 ${o.total.posts.toLocaleString()}편을 모아 경험담으로 정리했다.` : '개발자 합격·이직·전환 후기를 모아 경험담으로 정리했다.'}
            </p>
            <p className="mt-2 text-sm leading-5 text-[#666]">원문은 DB에 보관한다(열쇠가 있어야 열린다). 글쓴이 이름·아이디는 저장하지 않는다.</p>
          </div>
          {o && <span className="mt-3 shrink-0 text-sm text-[#666] tabular-nums">기준 {stamp(o.updated_at)}</span>}
        </header>

        {o && (
          <div className={'mt-10 grid grid-cols-2 lg:grid-cols-4 border-t pt-6 ' + LINE}>
            {[
              <Kpi key="n" label={filtered ? '고른 경험담' : '경험담'} value={o.n.toLocaleString()} unit="건" sub={filtered ? `전체 ${o.total.counted.toLocaleString()}` : undefined} />,
              <Kpi key="m" label="경력직 이직·전환" value={o.moves.n.toLocaleString()} unit="건" sub={`그 전 경력이 있는 글 · 경력 중앙값 ${med(o.spec.years_before.median, '년')}`} />,
              <Kpi key="s" label="스펙을 밝힌 사람" value={o.spec.with_spec.toLocaleString()} unit="명" sub={`학점 중앙값 ${gpa(o.spec.gpa.median)} / 4.5`} />,
              <Kpi key="c" label="회사" value={o.companies.length.toLocaleString()} unit="곳" sub={`교육과정 ${o.programs.length}곳`} />,
            ].map((k, i) => (
              <div key={i} className={i === 0 ? 'pr-6' : 'border-l px-6 ' + LINE}>
                {k}
              </div>
            ))}
          </div>
        )}

        {!NO_FILTER.includes(tab) && (
          <div className="mt-14">
            <FilterBar o={o} f={f} set={set} clearAll={clearAll} disabled={!o} />
          </div>
        )}

        <div role="tablist" className={'mt-8 flex items-center overflow-x-auto no-scrollbar border-b ' + LINE}>
          {TAB_GROUPS.map((group, gi) => (
            <Fragment key={gi}>
              {gi > 0 && <span aria-hidden className="mr-8 h-4 w-px shrink-0 bg-[#eeeeee]" />}
              {group.map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={tab === id}
                  onClick={() => set('tab', id === 'year' ? null : id)}
                  className={
                    'relative mr-8 shrink-0 pb-3 text-base ' +
                    (tab === id
                      ? 'font-bold text-[#272727] after:absolute after:inset-x-0 after:-bottom-px after:h-[2px] after:bg-[#272727]'
                      : 'font-medium text-[#666] hover:text-[#272727]')
                  }
                >
                  {label}
                </button>
              ))}
            </Fragment>
          ))}
        </div>

        <div className={'mt-8 ' + (loading ? 'opacity-60 transition-opacity' : '')}>
          {!o ? (
            <LoadError error={error ?? ''} retry={() => setAttempt((a) => a + 1)} />
          ) : tab === 'roster' ? (
            <RosterPanel />
          ) : o.n === 0 ? (
            <>
              {tab === 'year' && <YearHead />}
              <Empty clearAll={clearAll} />
            </>
          ) : (
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
          )}
        </div>
      </div>
      <SiteFooter />
    </div>
  )
}

// ── 상태 ────────────────────────────────────────────────────────────────

function Empty({ clearAll }: { clearAll: () => void }) {
  return (
    <div className="py-16 text-center">
      <p className="text-base font-bold text-[#272727]">고른 조건에 맞는 경험담이 없다.</p>
      <button type="button" onClick={clearAll} className="mt-2 text-sm text-[#272727] underline underline-offset-4">
        모두 지우기
      </button>
    </div>
  )
}

function LoadError({ error, retry }: { error: string; retry: () => void }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="py-16 flex flex-col items-center gap-4 text-center">
      <p className="text-base font-bold text-[#272727]">취업후기를 불러오지 못했다</p>
      <PillButton onClick={retry}>다시 시도</PillButton>
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} className="text-sm text-[#666]">
        자세히 {open ? '▴' : '▾'}
      </button>
      {open && (
        <div className="max-w-[640px] text-sm leading-6 text-[#666]">
          <p className="text-[#c01a10]">{error || '응답이 없다'}</p>
          <p>
            뷰어 API <code>/api/careers</code> 가 DB(019)를 읽는다. 적재: <code>python -m store.ingest.careers</code>
          </p>
        </div>
      )}
    </div>
  )
}

// ── 표 공통 ─────────────────────────────────────────────────────────────

const TH = 'h-10 pr-4 text-left align-middle text-sm font-medium text-[#666] whitespace-nowrap'
const TD = 'py-[14px] pr-4 align-top text-sm leading-5 text-[#272727] break-keep'

// ── 연도별 ──────────────────────────────────────────────────────────────

const first = (xs: Count[], n = 3) => xs.slice(0, n).map((x) => x[0]).join(', ') || '—'
/** 신입·경력 칸 — '건수 (비율)', 표본이 3건 미만이면 건수만. */
const countPct = (xs: Count[], label: string) => {
  const x = xs.find((v) => v[0] === label)
  return x ? (x[2] !== undefined ? `${x[1].toLocaleString()} (${x[2]}%)` : x[1].toLocaleString()) : '—'
}
const pctOf = (xs: Count[], label: string) => {
  const x = xs.find((v) => v[0] === label)
  return x ? (x[2] !== undefined ? `${x[2]}%` : `${x[1]}건`) : '—'
}
const YEAR_COLS = ['연도', '경험담', '신입', '경력', '자격증', '어학', '알고리즘', '학점', '나이', '그 전 경력(년)', '간 곳']
// 시안 실측 열 폭(합 1256) — 글이 긴 칸(자격증·어학·알고리즘·간 곳)은 두 줄까지 접힌다.
const YEAR_W = [80, 64, 88, 80, 200, 152, 168, 72, 64, 104, 184]
const YearCols = () => (
  <colgroup>
    {YEAR_W.map((w, i) => (
      <col key={i} style={{ width: w }} />
    ))}
  </colgroup>
)

function YearNote() {
  return (
    <div className="text-sm leading-6 text-[#666]">
      <p>연도는 글에 밝힌 사건 연도이고, 밝히지 않은 글은 게시 연도로 셌다. 줄을 누르면 그해만 본다.</p>
      <p>신입·경력은 건수(비율)이고, 경험담이 3건 미만인 해는 건수만 쓴다. 연도 미상은 연도 값이 없는 경험담으로, 건수만 있다.</p>
    </div>
  )
}

function YearHead() {
  return (
    <div className="flex flex-col gap-6">
      <YearNote />
      <table className="w-full table-fixed">
        <YearCols />
        <thead className={'border-b ' + LINE}>
          <tr>
            {YEAR_COLS.map((h) => (
              <th key={h} className={TH}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
      </table>
    </div>
  )
}

function ByYear({ o, pick }: { o: Overview; pick: (y: number) => void }) {
  const unknown = o.n - o.by_year.reduce((a, y) => a + y.n, 0)
  const opt = (v: { n: number; median: number | null }, fixed = false) =>
    v.n && v.median !== null ? `${fixed ? v.median.toFixed(1) : v.median} (${v.n})` : '—'
  return (
    <div className="flex flex-col gap-6">
      <YearNote />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1256px] table-fixed">
          <YearCols />
          <thead className={'border-b ' + LINE}>
            <tr>
              {YEAR_COLS.map((h) => (
                <th key={h} className={TH}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {o.by_year.map((y) => (
              <tr key={y.year} onClick={() => pick(y.year)} className={'border-b cursor-pointer hover:bg-[#f7f9fa] ' + LINE}>
                <td className={TD + ' font-medium tabular-nums'}>{y.year}</td>
                <td className={TD + ' tabular-nums'}>{y.n.toLocaleString()}</td>
                <td className={TD + ' tabular-nums whitespace-nowrap'}>{countPct(y.levels, '신입')}</td>
                <td className={TD + ' tabular-nums whitespace-nowrap'}>{countPct(y.levels, '경력')}</td>
                <td className={TD}>{first(y.certs)}</td>
                <td className={TD}>{first(y.language, 2)}</td>
                <td className={TD}>{first(y.algorithm, 2)}</td>
                <td className={TD + ' tabular-nums whitespace-nowrap'}>{opt(y.gpa, true)}</td>
                <td className={TD + ' tabular-nums whitespace-nowrap'}>{opt(y.age)}</td>
                <td className={TD + ' tabular-nums whitespace-nowrap'}>{opt(y.years_before)}</td>
                <td className={TD}>{first(y.types.filter((t) => t[0] !== '미분류'), 3)}</td>
              </tr>
            ))}
            {unknown > 0 && (
              <tr className={'border-b ' + LINE}>
                <td className={TD + ' font-medium whitespace-nowrap'}>연도 미상</td>
                <td className={TD + ' tabular-nums'}>{unknown.toLocaleString()}</td>
                <td colSpan={9} />
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {o.by_year.length === 1 && <SpecPanel s={o.by_year[0]} />}
    </div>
  )
}

// ── 회사 유형·회사 ──────────────────────────────────────────────────────

function ByType({ o, pickType, pickCompany }: { o: Overview; pickType: (t: string) => void; pickCompany: (key: string) => void }) {
  const keyOf = (name: string) => o.companies.find((c) => c.name === name)?.key ?? name
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[1180px]">
        <thead className={'border-b ' + LINE}>
          <tr>
            {['회사 유형', '신입 · 경력', '학점 · 나이 · 경력', '회사', '자격증', '학력'].map((h) => (
              <th key={h} className={TH}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {o.by_type.map((t) => (
            <tr key={t.type} className={'border-b ' + LINE}>
              <td className={TD + ' w-[150px] py-5'}>
                <button type="button" onClick={() => pickType(t.type)} className="text-left font-medium hover:underline underline-offset-2">
                  {t.type}
                </button>
                <div className="text-[#666] tabular-nums">{t.n.toLocaleString()}건</div>
              </td>
              <td className={TD + ' w-[102px] py-5 whitespace-nowrap tabular-nums'}>
                <div>신입 {pctOf(t.levels, '신입')}</div>
                <div>경력 {pctOf(t.levels, '경력')}</div>
              </td>
              <td className={TD + ' w-[126px] py-5 whitespace-nowrap tabular-nums'}>
                <div>학점 {gpa(t.gpa.median)}</div>
                <div>나이 {med(t.age.median)}</div>
                <div>경력 {med(t.years_before.median, '년')}</div>
              </td>
              <td className={TD + ' py-5'}>
                <Inline items={t.companies} limit={8} empty="회사 밝히지 않음" onPick={(c) => pickCompany(keyOf(c))} />
              </td>
              <td className={TD + ' w-[250px] py-5'}>
                <Inline items={t.certs} limit={6} />
              </td>
              <td className={TD + ' w-[236px] py-5'}>
                <Inline items={t.education} limit={4} pct />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** 이름(14/500) · 보조 줄(14 #666) · 건수 — 5열 격자 한 칸. 회사별·경력직이 간 회사가 같이 쓴다. */
function GridCell({ name, sub, n, on, onClick }: { name: string; sub?: string | null; n: number; on?: boolean; onClick?: () => void }) {
  const body = (
    <>
      <span className="min-w-0 flex-1 text-left">
        <span className={'block truncate ' + (on ? 'font-bold' : 'font-medium')}>{name}</span>
        {sub && <span className="block truncate text-[#666]">{sub}</span>}
      </span>
      <span className="shrink-0 tabular-nums">{n.toLocaleString()}</span>
    </>
  )
  const cls = 'flex w-full items-start gap-3 py-2 pr-6 text-sm leading-5 text-[#272727]'
  return (
    <li className={'border-b ' + LINE}>
      {onClick ? (
        <button type="button" onClick={onClick} aria-pressed={on} className={cls + ' hover:underline underline-offset-2'}>
          {body}
        </button>
      ) : (
        <div className={cls}>{body}</div>
      )}
    </li>
  )
}

function ByCompany({ o, f, pick }: { o: Overview; f: Filters; pick: (key: string) => void }) {
  return (
    <div className="flex flex-col gap-12">
      {f.company && <SpecPanel s={o.spec} />}
      <Section title="회사" note="회사 이름을 밝힌 경험담. 누르면 그 회사만 보고, 다른 탭도 그 회사로 바뀐다.">
        <ul className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-x-6">
          {o.companies.map((c) => (
            <GridCell key={c.key} name={c.name} sub={c.type} n={c.n} on={f.company === c.key} onClick={() => pick(c.key)} />
          ))}
        </ul>
      </Section>
      <Section title="교육과정·동아리" note="회사가 아니라 부트캠프·동아리·교육과정 선발 후기.">
        <ul className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-x-6">
          {o.programs.map((p) => (
            <GridCell key={p.key} name={p.name} n={p.n} on={f.company === p.key} onClick={() => pick(p.key)} />
          ))}
        </ul>
      </Section>
      {f.company && <StoryListPanel f={f} fkey={`company:${f.company}`} />}
    </div>
  )
}

// ── 스펙 ───────────────────────────────────────────────────────────────

function SpecPanel({ s }: { s: Spec }) {
  const items: [string, Count[] | undefined, string?, number?][] = [
    ['학력', s.education, "원문에 근거가 없으면 '확인되지 않음'."],
    ['학점(4.5 환산)', s.gpa.bands],
    ['경력 구분', s.levels],
    ['자격증', s.certs, undefined, 12],
    ['어학', s.language],
    ['알고리즘', s.algorithm, '백준 티어·프로그래머스 레벨로 묶었다.'],
    ['대외활동', s.activities, undefined, 12],
    ['인턴', s.internships],
    ['수상', s.awards],
    ['기술 스택', s.stack, undefined, 14],
    ['거쳐 온 교육과정', s.programs],
  ]
  return (
    <div className="flex flex-col gap-12">
      <div className={'grid grid-cols-2 lg:grid-cols-4 border-t pt-6 ' + LINE}>
        {[
          <Kpi key="n" label="경험담" value={s.n.toLocaleString()} unit="건" sub={`스펙을 밝힌 글 ${s.with_spec.toLocaleString()}`} />,
          <Kpi key="g" label="학점 중앙값(4.5)" value={gpa(s.gpa.median)} sub={`숫자로 밝힌 ${s.gpa.n}명`} />,
          <Kpi key="a" label="나이 중앙값" value={med(s.age.median)} unit={s.age.median === null ? undefined : '세'} sub={`밝힌 ${s.age.n}명`} />,
          <Kpi key="y" label="그 전 경력 중앙값" value={med(s.years_before.median)} unit={s.years_before.median === null ? undefined : '년'} sub={`경력자 ${s.years_before.n}명`} />,
        ].map((k, i) => (
          <div key={i} className={i === 0 ? 'pr-6' : 'border-l px-6 ' + LINE}>
            {k}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-12 gap-y-10">
        {items.map(([title, xs, note, limit]) => (
          <Section key={title} title={title} note={note}>
            <Rows items={xs} limit={limit} empty={title.startsWith('학점') ? '숫자로 밝힌 사람 없음' : '없음'} />
          </Section>
        ))}
      </div>
    </div>
  )
}

// ── 이직·커리어 ─────────────────────────────────────────────────────────

/** 매트릭스 칸 — 남색 네 단계(데이터 전용 색), 글자는 늘 본문색. */
const shade = (r: number) => (r >= 0.6 ? '#B9B6DE' : r >= 0.3 ? '#D3D1EC' : r >= 0.1 ? '#E6E5F4' : '#F3F2FA')

function Moves({ o, pickOrigin, pickType }: { o: Overview; pickOrigin: (v: string) => void; pickType: (v: string) => void }) {
  const m = o.moves
  const [all, setAll] = useState(false)
  const origins = m.origins.map((x) => x[0]).filter((x) => x !== '확인되지 않음').slice(0, 10)
  const cell = (a: string, b: string) => m.matrix.find((x) => x.origin === a && x.type === b)?.n ?? 0
  // 값이 하나도 없는 유형은 뺀다(빈 열은 읽을 것이 없다).
  const types = [...new Set(m.matrix.map((x) => x.type))].filter((t) => origins.some((a) => cell(a, t) > 0)).slice(0, 9)
  const cmax = Math.max(1, ...m.matrix.filter((x) => x.origin !== '확인되지 않음').map((x) => x.n))
  const examples = all ? m.examples : m.examples.slice(0, 10)
  return (
    <div className="flex flex-col gap-16">
      <div className="flex flex-col gap-8">
        <p className="text-sm text-[#666]">
          경력직(경력·이직·직무전환, 그 전 경력이 있는 글) {m.n.toLocaleString()}건. 출발지는 전환 문장과 경로 앞부분에서 읽었다.
        </p>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-x-12 gap-y-10">
          <Section title="어디서 떠나 왔나" note={`비율 = 경력직 ${m.n.toLocaleString()}건 대비. 누르면 그 출발지만 본다.`}>
            <Rows items={m.origins} onPick={pickOrigin} picked={o.filters.origin} limit={14} />
          </Section>
          <Section title="어떤 전환이었나" note={`비율 = 경험담 ${o.n.toLocaleString()}건 대비`}>
            <Rows items={m.transitions} />
          </Section>
          <Section title="몇 년 차에 옮겼나" note="그 전 경력 구간별 · 간 곳의 유형">
            <ul className={'border-t ' + LINE}>
              {m.years.map((y) => (
                <li key={y.band} className={'border-b py-2 text-sm leading-5 ' + LINE}>
                  <div className="flex justify-between">
                    <span className="font-medium">{y.band}</span>
                    <span className="tabular-nums">{y.n.toLocaleString()}</span>
                  </div>
                  <div className="text-[#666]">
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
      </div>

      <Section title="출발지 → 간 곳(회사 유형)" note="칸의 숫자는 경험담 수. 유형을 누르면 그 유형만 본다. 값이 하나도 없는 유형은 뺐다.">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] table-fixed border-separate border-spacing-1">
            <thead>
              <tr>
                <th className="w-[160px]" />
                {types.map((t) => (
                  <th key={t} className="h-8 text-center text-sm font-normal text-[#666]">
                    <button type="button" onClick={() => pickType(t)} className="hover:text-[#272727] hover:underline underline-offset-2">
                      {t}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {origins.map((a) => (
                <tr key={a}>
                  <th className="pr-3 text-left text-sm font-medium text-[#272727] whitespace-nowrap">
                    <button type="button" onClick={() => pickOrigin(a)} className="hover:underline underline-offset-2">
                      {a}
                    </button>
                  </th>
                  {types.map((b) => {
                    const v = cell(a, b)
                    return (
                      <td key={b} className="h-8 text-center text-sm tabular-nums text-[#272727]" style={{ background: v ? shade(v / cmax) : undefined }}>
                        {v || ''}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="경력직이 간 회사" note={`회사 이름을 밝힌 경력직 경험담(교육과정 제외), 많은 순 ${m.destinations.length}곳`}>
        <ul className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-x-6">
          {m.destinations.map((d) => (
            <GridCell key={d.company} name={d.company} sub={d.type} n={d.n} />
          ))}
        </ul>
      </Section>

      <Section title="이직 경로" note="경로가 두 단계 이상 적힌 경력직 경험담. 최근 것부터. 누르면 그 글의 정리와 원문.">
        <ul className={'border-t ' + LINE}>
          {examples.map((s) => (
            <StoryRow key={s.id} s={s} />
          ))}
        </ul>
        {!all && m.examples.length > 10 && (
          <div className="mt-6">
            <PillButton onClick={() => setAll(true)}>이직 경로 {m.examples.length - 10}건 더 보기</PillButton>
          </div>
        )}
      </Section>
    </div>
  )
}

const Chevron = () => (
  <svg aria-hidden width="8" height="14" viewBox="0 0 8 14" fill="none" stroke="#666" strokeWidth="1.6" className="shrink-0">
    <path d="M1 1l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)

/** 후기 한 줄 — 정리 한 줄(16/500) · 메타(14 #666) · 경로(14). */
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
    <li className={'border-b ' + LINE}>
      <a href={to} onClick={onLinkClick(to)} className="group flex items-center gap-6 py-5">
        <div className="min-w-0 flex-1">
          <p className="text-base font-medium leading-6 text-[#272727] group-hover:underline underline-offset-2">{s.summary || s.title || s.company || '정리 없음'}</p>
          <p className="mt-1 text-sm leading-5 text-[#666]">{meta}</p>
          <div className="mt-2">
            <PathLine steps={s.steps} />
          </div>
        </div>
        <Chevron />
      </a>
    </li>
  )
}

// ── 경로·전형 ───────────────────────────────────────────────────────────

function PathsPanel({ o }: { o: Overview }) {
  const p = o.paths
  return (
    <div className="flex flex-col gap-12">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-12 gap-y-10">
        <Section title="거쳐 온 길" note="경로 단계에 나온 갈래(한 글에 여럿).">
          <Rows items={p.tags} />
        </Section>
        <Section title="준비 방법" note={`준비 기간 중앙값 ${med(p.prep_months.median, '개월')} (${p.prep_months.n}명)`}>
          <Rows items={p.prep} limit={12} />
        </Section>
        <Section title="면접 단계">
          <Rows items={p.interviews} />
        </Section>
      </div>
      <Section title="코딩테스트">
        <Rows items={p.coding_test} />
      </Section>
    </div>
  )
}

// ── 지원 결과 ───────────────────────────────────────────────────────────

function Applied({ o }: { o: Overview }) {
  return (
    <Section title="같이 지원한 곳, 붙고 떨어진 자리" note="경험담에 함께 적힌 다른 지원처. 떨어진 단계는 밝힌 것만.">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px]">
          <thead className={'border-b ' + LINE}>
            <tr>
              {['회사', '합격', '탈락', '주로 떨어진 단계'].map((h) => (
                <th key={h} className={TH}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {o.applied.map((a) => (
              <tr key={a.company} className={'border-b ' + LINE}>
                <td className={TD + ' font-medium'}>{a.company}</td>
                <td className={TD + ' w-[96px] tabular-nums'}>{a.pass}</td>
                <td className={TD + ' w-[96px] tabular-nums'}>{a.fail}</td>
                <td className={TD + ' text-[#666]'}>{a.stages.map((s) => `${s[0]} ${s[1]}`).join(' · ') || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  )
}

// ── 서류·조언 ───────────────────────────────────────────────────────────

function VoiceList({ xs }: { xs: Voice[] }) {
  if (!xs.length) return <p className="text-sm text-[#666]">없음</p>
  return (
    <ul className={'border-t ' + LINE}>
      {xs.map((v, i) => {
        const to = paths.careersStory(v.id)
        const meta = [v.company, v.year].filter(Boolean).join(' · ')
        return (
          <li key={i} className={'border-b ' + LINE}>
            <a href={to} onClick={onLinkClick(to)} className="block py-3 text-sm leading-5 text-[#272727] hover:underline underline-offset-2">
              {v.t}
              {meta && <span className="block text-[#666]">{meta}</span>}
            </a>
          </li>
        )
      })}
    </ul>
  )
}

function Docs({ o }: { o: Overview }) {
  const d = o.docs
  const docs: [string, Count[]][] = [
    ['이력서에서 한 것', d.resume_points],
    ['포트폴리오에서 한 것', d.portfolio_points],
    ['포트폴리오에 넣은 프로젝트', d.portfolio_projects],
    ['자기소개서에서 한 것', d.cover_letter_points],
    ['자기소개서 문항', d.cover_letter_questions],
  ]
  return (
    <div className="flex flex-col gap-12">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-12 gap-y-10">
        {docs.map(([title, xs]) => (
          <Section key={title} title={title}>
            <Rows items={xs} limit={12} />
          </Section>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-x-12 gap-y-10">
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
  if (!data) return <p className="text-sm text-[#c01a10]">{error}</p>
  return (
    <div className="flex flex-col gap-12">
      <p className="text-sm leading-6 text-[#666]">
        학원·학과·부트캠프가 올린 '합격자 명단' 카드 {data.posts}장에서 읽은 {data.people.toLocaleString()}명(IT 쪽만). 이름은 읽지도 저장하지도 않았다.
        연도·회사 거르기는 이 탭에 걸리지 않는다.
      </p>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-x-12 gap-y-10">
        <Section title="연도">
          <Rows items={data.years.map(([y, n]) => [String(y), n] as Count)} />
        </Section>
        <Section title="출신 학교" className="lg:col-span-2">
          <Rows items={data.schools} limit={20} />
        </Section>
      </div>
      <Section title="합격처별">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px]">
            <thead className={'border-b ' + LINE}>
              <tr>
                {['합격처', '인원', '전공자', '학교', '전공', '연도'].map((h) => (
                  <th key={h} className={TH}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.orgs.map((g) => (
                <tr key={g.org} className={'border-b ' + LINE}>
                  <td className={TD}>
                    <span className="font-medium">{g.org}</span>
                    {g.type && <span className="block text-[#666]">{g.type}</span>}
                  </td>
                  <td className={TD + ' tabular-nums'}>{g.n}</td>
                  <td className={TD + ' tabular-nums'}>{g.n ? `${Math.round((100 * g.cs) / g.n)}%` : '—'}</td>
                  <td className={TD}>{first(g.schools, 5)}</td>
                  <td className={TD}>{first(g.majors, 3)}</td>
                  <td className={TD + ' tabular-nums text-[#666]'}>{g.years.map(([y, n]) => `${y}(${n})`).join(' ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  )
}

// ── 후기 목록 ───────────────────────────────────────────────────────────

function StoryListPanel({ f, fkey }: { f: Filters; fkey: string }) {
  const [page, setPage] = useState(0)
  const [prevKey, setPrevKey] = useState(fkey)
  if (prevKey !== fkey) {
    setPrevKey(fkey)
    setPage(0)
  }
  const { data, error } = useAsync((s) => fetchStories(f, page * 40, s), `${fkey}#${page}`)
  if (!data) return error ? <p className="text-sm text-[#c01a10]">{error}</p> : <Loader label="목록 여는 중…" />
  const pages = Math.ceil(data.n / 40)
  return (
    <Section title={`후기 ${data.n.toLocaleString()}건`} note="누르면 정리한 값과 원문(열쇠가 있을 때).">
      <ul className={'border-t ' + LINE}>
        {data.items.map((s) => (
          <StoryRow key={s.id} s={s} />
        ))}
      </ul>
      {pages > 1 && (
        <div className="mt-8 flex items-center justify-center gap-4 text-sm">
          <PillButton disabled={page === 0} onClick={() => setPage(page - 1)}>
            이전
          </PillButton>
          <span className="tabular-nums text-[#272727]">
            {page + 1} / {pages}
          </span>
          <PillButton disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>
            다음
          </PillButton>
        </div>
      )}
    </Section>
  )
}
