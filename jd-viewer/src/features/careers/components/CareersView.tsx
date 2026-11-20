import { useState, type ReactNode } from 'react'
import { SiteFooter } from '../../../components/SiteFooter'
import { ErrorState, Loader } from '../../../components/ui'
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
import { Bars, Card, Chip, Stat, Steps } from './parts'
import { med } from '../utils/format'
import { StoryView } from './StoryView'

// 기술도서 › 취업 — 합격·이직·전환 후기를 연도·회사·회사 유형으로 잘라 본다.
// 원본 글은 DB(career_post)에 있고, 이 화면은 그 글에서 뽑은 구조화 값(스펙·경로·전형·서류)을 센다.
// 책장과 같이 혼자 보는 화면이라 색인하지 않는다.
const NOINDEX = 'noindex, nofollow'

const TABS = [
  ['year', '연도별'],
  ['type', '회사 유형별'],
  ['company', '회사별'],
  ['spec', '스펙'],
  ['moves', '이직·커리어'],
  ['paths', '경로·전형'],
  ['applied', '지원 결과'],
  ['docs', '서류·조언'],
  ['roster', '합격자 명단'],
  ['list', '후기 목록'],
] as const
type TabId = (typeof TABS)[number][0]

export function CareersView({ seg }: { seg: string[] }) {
  if (seg[0]) return <StoryView id={seg[0]} />
  return <Dashboard />
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
  const { data, error, loading } = useAsync((s) => fetchOverview(f, s), fkey)

  useSeo({ title: '취업 — 합격·이직 후기', description: '혼자 보는 취업 자료', robots: NOINDEX, canonical: absUrl(paths.careers()) })

  const set = (k: string, v: string | null) => setQuery(k, v)
  const toggle = (k: string, v: string) => set(k, f[k as keyof Filters] === v ? null : v)

  if (!data && loading) return <Loader label="후기 세는 중…" />
  if (!data)
    return (
      <ErrorState
        title="커리어 후기를 못 읽었다"
        detail={error ?? ''}
        hint={
          <>
            뷰어 API <code>/api/careers</code> 가 DB(019)를 읽는다. 적재: <code>python -m store.ingest.careers</code>
          </>
        }
      />
    )

  const o = data
  const filtered = Object.keys(o.filters).length > 0
  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[43px] pb-[90px]">
        <nav className="text-sm text-[#999]">
          <a href={paths.wiki()} onClick={onLinkClick(paths.wiki())} className="hover:text-[#272727]">
            기술도서
          </a>
          <span className="mx-1.5">›</span>
          <span className="text-[#555]">취업</span>
        </nav>
        <h1 className="mt-2 text-[28px] font-bold leading-10 tracking-[-0.6px] text-[#272727]">취업 — 합격·이직 후기</h1>
        <p className="mt-1 text-base leading-6 text-[#666]">
          개발자 합격·이직·전환 후기 {o.total.posts.toLocaleString()}편을 모아 경험담 {o.total.counted.toLocaleString()}건으로 정리했다.
          원문은 DB 에 보관한다(열쇠가 있어야 열린다). 글쓴이 이름·아이디는 저장하지 않는다.
        </p>

        <div className="mt-[27px] grid grid-cols-2 lg:grid-cols-4 gap-[14px]">
          <Stat label={filtered ? '고른 경험담' : '경험담'} value={o.n.toLocaleString()} sub={filtered ? `전체 ${o.total.counted.toLocaleString()}` : undefined} />
          <Stat label="경력직 이직·전환" value={o.moves.n.toLocaleString()} sub={`경력 중앙값 ${med(o.spec.years_before.median, '년')}`} />
          <Stat label="스펙을 밝힌 사람" value={o.spec.with_spec.toLocaleString()} sub={`학점 중앙값 ${med(o.spec.gpa.median)} / 4.5`} />
          <Stat label="회사" value={o.companies.length.toLocaleString()} sub={`교육과정 ${o.programs.length}곳`} />
        </div>

        <FilterBar o={o} f={f} toggle={toggle} set={set} />

        <div role="tablist" className="mt-8 flex overflow-x-auto no-scrollbar border-b border-[#e2e2e2]">
          {TABS.map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              onClick={() => set('tab', id === 'year' ? null : id)}
              className={
                'relative shrink-0 px-[16px] pb-[12px] text-[15px] ' +
                (tab === id
                  ? 'font-bold text-(--color-accent) after:absolute after:inset-x-0 after:-bottom-px after:h-[3px] after:bg-(--color-accent)'
                  : 'font-medium text-[#777] hover:text-[#272727]')
              }
            >
              {label}
            </button>
          ))}
        </div>

        <div className={'mt-8 ' + (loading ? 'opacity-60 transition-opacity' : '')}>
          {tab === 'year' && <ByYear o={o} pick={(y) => toggle('year', String(y))} />}
          {tab === 'type' && <ByType o={o} pickType={(t) => toggle('type', t)} pickCompany={(c) => set('company', c)} />}
          {tab === 'company' && <ByCompany o={o} f={f} pick={(c) => toggle('company', c)} />}
          {tab === 'spec' && <SpecPanel s={o.spec} />}
          {tab === 'moves' && <Moves o={o} pickOrigin={(v) => toggle('origin', v)} pickType={(v) => toggle('type', v)} />}
          {tab === 'paths' && <PathsPanel o={o} />}
          {tab === 'applied' && <Applied o={o} />}
          {tab === 'docs' && <Docs o={o} />}
          {tab === 'roster' && <RosterPanel />}
          {tab === 'list' && <StoryListPanel f={f} fkey={fkey} />}
        </div>
      </div>
      <SiteFooter />
    </div>
  )
}

// ── 거르기 ──────────────────────────────────────────────────────────────

function FilterBar({ o, f, toggle, set }: { o: Overview; f: Filters; toggle: (k: string, v: string) => void; set: (k: string, v: string | null) => void }) {
  const [q, setQ] = useState(f.q ?? '')
  const row = (label: string, k: keyof Filters, items: Count[] | [number, number][]) => (
    <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-1">
      <span className="shrink-0 w-[64px] text-[13px] font-semibold text-[#888]">{label}</span>
      <Chip on={!f[k]} onClick={() => set(k, null)}>
        전체
      </Chip>
      {items.map(([v, n]) => (
        <Chip key={String(v)} on={f[k] === String(v)} onClick={() => toggle(k, String(v))}>
          {v} <span className="opacity-60 tabular-nums">{n}</span>
        </Chip>
      ))}
    </div>
  )
  const company = f.company && (o.companies.find((c) => c.key === f.company)?.name ?? o.programs.find((p) => p.key === f.company)?.name ?? f.company)
  return (
    <div className="mt-8 flex flex-col gap-1 rounded-xl border border-[#eee] p-4">
      {row('연도', 'year', o.facets.years)}
      {row('회사 유형', 'type', o.facets.types)}
      {row('경력', 'level', o.facets.levels)}
      {row('종류', 'kind', o.facets.kinds)}
      {row('직무', 'role', o.facets.roles)}
      <div className="flex flex-wrap items-center gap-2 pt-2">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            set('q', q.trim() || null)
          }}
          className="flex gap-2"
        >
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="제목·회사·기술 검색"
            className="w-[220px] rounded-lg border border-[#ddd] px-3 py-1.5 text-sm"
          />
          <button type="submit" className="rounded-lg bg-[#272727] px-3 py-1.5 text-sm text-white">
            찾기
          </button>
        </form>
        {company && (
          <Chip on onClick={() => set('company', null)}>
            회사: {company} ✕
          </Chip>
        )}
        {f.origin && (
          <Chip on onClick={() => set('origin', null)}>
            출발지: {f.origin} ✕
          </Chip>
        )}
        {f.q && (
          <Chip on onClick={() => (setQ(''), set('q', null))}>
            “{f.q}” ✕
          </Chip>
        )}
        {Object.keys(o.filters).length > 0 && (
          <button
            type="button"
            className="text-[13px] text-[#999] underline"
            onClick={() => {
              const tab = new URLSearchParams(window.location.search).get('tab')
              navigate(paths.careers() + (tab ? `?tab=${tab}` : ''), { replace: true })
              setQ('')
            }}
          >
            모두 지우기
          </button>
        )}
      </div>
    </div>
  )
}

// ── 연도별 ──────────────────────────────────────────────────────────────

const first = (xs: Count[], n = 3) => xs.slice(0, n).map((x) => x[0]).join(', ') || '—'
const pctOf = (xs: Count[], label: string) => {
  const x = xs.find((v) => v[0] === label)
  return x ? (x[2] !== undefined ? `${x[2]}%` : `${x[1]}건`) : '—'
}

function ByYear({ o, pick }: { o: Overview; pick: (y: number) => void }) {
  const max = Math.max(1, ...o.by_year.map((y) => y.n))
  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm text-[#888]">
        연도는 글에 밝힌 사건 연도이고, 밝히지 않은 글은 게시 연도로 셌다. 줄을 누르면 그해만 본다.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[980px] text-sm">
          <thead className="text-left text-[13px] text-[#999] border-b border-[#e6e6e6]">
            <tr>
              {['연도', '경험담', '신입', '경력', '자격증', '어학', '알고리즘', '학점', '나이', '경력(년)', '간 곳'].map((h) => (
                <th key={h} className="py-2 pr-3 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {o.by_year.map((y) => (
              <tr key={y.year} onClick={() => pick(y.year)} className="border-b border-[#f2f2f2] hover:bg-[#fafafa] cursor-pointer align-top">
                <td className="py-2.5 pr-3 font-bold tabular-nums">{y.year}</td>
                <td className="py-2.5 pr-3 w-[160px]">
                  <div className="flex items-center gap-2">
                    <span className="tabular-nums w-10">{y.n}</span>
                    <span className="h-2 rounded bg-(--color-accent)/60" style={{ width: `${(80 * y.n) / max}px` }} />
                  </div>
                </td>
                <td className="py-2.5 pr-3 tabular-nums">{pctOf(y.levels, '신입')}</td>
                <td className="py-2.5 pr-3 tabular-nums">{pctOf(y.levels, '경력')}</td>
                <td className="py-2.5 pr-3">{first(y.certs)}</td>
                <td className="py-2.5 pr-3">{first(y.language, 2)}</td>
                <td className="py-2.5 pr-3">{first(y.algorithm, 2)}</td>
                <td className="py-2.5 pr-3 tabular-nums">{y.gpa.n ? `${y.gpa.median} (${y.gpa.n})` : '—'}</td>
                <td className="py-2.5 pr-3 tabular-nums">{y.age.n ? `${y.age.median} (${y.age.n})` : '—'}</td>
                <td className="py-2.5 pr-3 tabular-nums">{y.years_before.n ? `${y.years_before.median} (${y.years_before.n})` : '—'}</td>
                <td className="py-2.5 pr-3">{first(y.types.filter((t) => t[0] !== '미분류'), 3)}</td>
              </tr>
            ))}
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
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {o.by_type.map((t) => (
        <Card
          key={t.type}
          title={
            <button type="button" onClick={() => pickType(t.type)} className="hover:text-(--color-accent)">
              {t.type} <span className="text-[#aaa] font-medium tabular-nums">{t.n}</span>
            </button>
          }
          note={`신입 ${pctOf(t.levels, '신입')} · 경력 ${pctOf(t.levels, '경력')} · 학점 ${med(t.gpa.median)} · 나이 ${med(t.age.median)} · 경력 ${med(t.years_before.median, '년')}`}
        >
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h4 className="text-xs font-semibold text-[#999] mb-1.5">회사</h4>
              <Bars items={t.companies} limit={8} onPick={(c) => pickCompany(keyOf(c))} empty="이름을 밝힌 곳 없음" />
            </div>
            <div>
              <h4 className="text-xs font-semibold text-[#999] mb-1.5">자격증</h4>
              <Bars items={t.certs} limit={6} />
              <h4 className="text-xs font-semibold text-[#999] mt-3 mb-1.5">학력</h4>
              <Bars items={t.education} limit={4} />
            </div>
          </div>
        </Card>
      ))}
    </div>
  )
}

function ByCompany({ o, f, pick }: { o: Overview; f: Filters; pick: (key: string) => void }) {
  return (
    <div className="flex flex-col gap-6">
      {f.company && <SpecPanel s={o.spec} />}
      <Card title="회사" note="회사 이름을 밝힌 경험담. 누르면 그 회사만 보고, 다른 탭도 그 회사로 바뀐다.">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-1.5">
          {o.companies.map((c) => (
            <button
              key={c.key}
              type="button"
              onClick={() => pick(c.key)}
              className={
                'flex items-baseline justify-between gap-2 rounded-lg border px-3 py-2 text-left text-sm ' +
                (f.company === c.key ? 'border-(--color-accent) bg-(--color-accent)/5' : 'border-[#eee] hover:border-[#bbb]')
              }
            >
              <span className="truncate">
                {c.name}
                <span className="block text-[11px] text-[#aaa]">{c.type}</span>
              </span>
              <span className="tabular-nums text-[#888]">{c.n}</span>
            </button>
          ))}
        </div>
      </Card>
      <Card title="교육과정·동아리" note="회사가 아니라 부트캠프·동아리·교육과정 선발 후기.">
        <div className="flex flex-wrap gap-1.5">
          {o.programs.map((p) => (
            <Chip key={p.key} on={f.company === p.key} onClick={() => pick(p.key)}>
              {p.name} <span className="opacity-60">{p.n}</span>
            </Chip>
          ))}
        </div>
      </Card>
      {f.company && <StoryListPanel f={f} fkey={`company:${f.company}`} />}
    </div>
  )
}

// ── 스펙 ───────────────────────────────────────────────────────────────

function SpecPanel({ s }: { s: Spec }) {
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-[14px]">
        <Stat label="경험담" value={s.n.toLocaleString()} sub={`스펙을 밝힌 글 ${s.with_spec.toLocaleString()}`} />
        <Stat label="학점 중앙값(4.5)" value={med(s.gpa.median)} sub={`숫자로 밝힌 ${s.gpa.n}명`} />
        <Stat label="나이 중앙값" value={med(s.age.median, '세')} sub={`밝힌 ${s.age.n}명`} />
        <Stat label="그 전 경력 중앙값" value={med(s.years_before.median, '년')} sub={`경력자 ${s.years_before.n}명`} />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <Card title="학력" note="원문에 근거가 없으면 '확인되지 않음'.">
          <Bars items={s.education} />
        </Card>
        <Card title="학점(4.5 환산)">
          <Bars items={s.gpa.bands} empty="숫자로 밝힌 사람 없음" />
        </Card>
        <Card title="경력 구분">
          <Bars items={s.levels} />
        </Card>
        <Card title="자격증">
          <Bars items={s.certs} limit={12} />
        </Card>
        <Card title="어학">
          <Bars items={s.language} />
        </Card>
        <Card title="알고리즘" note="백준 티어·프로그래머스 레벨로 묶었다.">
          <Bars items={s.algorithm} />
        </Card>
        <Card title="대외활동">
          <Bars items={s.activities} limit={12} />
        </Card>
        <Card title="인턴">
          <Bars items={s.internships} />
        </Card>
        <Card title="수상">
          <Bars items={s.awards} />
        </Card>
        <Card title="기술 스택">
          <Bars items={s.stack} limit={14} />
        </Card>
        <Card title="거쳐 온 교육과정">
          <Bars items={s.programs} />
        </Card>
      </div>
    </div>
  )
}

// ── 이직·커리어 ─────────────────────────────────────────────────────────

function Moves({ o, pickOrigin, pickType }: { o: Overview; pickOrigin: (v: string) => void; pickType: (v: string) => void }) {
  const m = o.moves
  const origins = m.origins.map((x) => x[0]).filter((x) => x !== '확인되지 않음').slice(0, 10)
  const types = [...new Set(m.matrix.map((x) => x.type))].slice(0, 9)
  const cell = (a: string, b: string) => m.matrix.find((x) => x.origin === a && x.type === b)?.n ?? 0
  const cmax = Math.max(1, ...m.matrix.filter((x) => x.origin !== '확인되지 않음').map((x) => x.n))
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-[#888]">
        경력직(경력·이직·직무전환, 그 전 경력이 있는 글) {m.n.toLocaleString()}건. 출발지는 전환 문장과 경로 앞부분에서 읽었다.
      </p>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="어디서 떠나 왔나" note="누르면 그 출발지만 본다.">
          <Bars items={m.origins} onPick={pickOrigin} picked={o.filters.origin} limit={14} />
        </Card>
        <Card title="어떤 전환이었나">
          <Bars items={m.transitions} />
        </Card>
        <Card title="몇 년 차에 옮겼나" note="그 전 경력 구간별 · 간 곳의 유형">
          <ul className="flex flex-col gap-2 text-sm">
            {m.years.map((y) => (
              <li key={y.band}>
                <div className="flex justify-between">
                  <span className="font-semibold">{y.band}</span>
                  <span className="tabular-nums text-[#888]">{y.n}</span>
                </div>
                <div className="text-xs text-[#999]">{y.types.filter((t) => t[0] !== '미분류').map((t) => `${t[0]} ${t[1]}`).join(' · ') || '—'}</div>
              </li>
            ))}
          </ul>
        </Card>
      </div>
      <Card title="출발지 → 간 곳(회사 유형)" note="칸의 숫자는 경험담 수. 유형을 누르면 그 유형만 본다.">
        <div className="overflow-x-auto">
          <table className="text-sm min-w-[720px]">
            <thead>
              <tr>
                <th />
                {types.map((t) => (
                  <th key={t} className="px-2 pb-2 text-[12px] font-medium text-[#888]">
                    <button type="button" onClick={() => pickType(t)} className="hover:text-(--color-accent)">
                      {t}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {origins.map((a) => (
                <tr key={a}>
                  <th className="pr-3 py-1 text-left text-[13px] font-semibold text-[#555] whitespace-nowrap">{a}</th>
                  {types.map((b) => {
                    const v = cell(a, b)
                    return (
                      <td key={b} className="p-0.5">
                        <div
                          className="h-8 w-16 rounded flex items-center justify-center tabular-nums text-[13px]"
                          style={{ background: v ? `color-mix(in srgb, var(--color-accent) ${12 + (70 * v) / cmax}%, white)` : '#f7f7f7', color: v / cmax > 0.5 ? 'white' : '#444' }}
                        >
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
      </Card>
      <Card title="경력직이 간 회사">
        <div className="flex flex-wrap gap-1.5">
          {m.destinations.map((d) => (
            <span key={d.company} className="rounded-full bg-[#f3f4f6] px-2.5 py-1 text-[13px]">
              {d.company} <span className="text-[#999]">{d.type}</span> <span className="tabular-nums text-[#777]">{d.n}</span>
            </span>
          ))}
        </div>
      </Card>
      <Card title="이직 경로" note="경로가 두 단계 이상 적힌 경력직 경험담 — 최근 것부터. 누르면 그 글의 정리와 원문.">
        <ul className="flex flex-col divide-y divide-[#f0f0f0]">
          {m.examples.map((s) => (
            <StoryRow key={s.id} s={s} />
          ))}
        </ul>
      </Card>
    </div>
  )
}

function StoryRow({ s }: { s: StoryBrief }) {
  const to = paths.careersStory(s.id)
  return (
    <li className="py-3">
      <a href={to} onClick={onLinkClick(to)} className="group block">
        <div className="flex flex-wrap items-baseline gap-x-2 text-sm">
          <span className="font-semibold text-[#272727] group-hover:text-(--color-accent)">{s.company ?? '회사 밝히지 않음'}</span>
          <span className="text-[#999]">
            {[s.company_type, s.year, s.kind, s.role !== '기타' ? s.role : null, s.level, s.years_before ? `경력 ${s.years_before}년` : null, s.origin && s.origin !== '확인되지 않음' ? `${s.origin}에서` : null]
              .filter(Boolean)
              .join(' · ')}
          </span>
        </div>
        {s.summary && <p className="mt-1 text-[13px] text-[#555] leading-relaxed">{s.summary}</p>}
        <div className="mt-1.5">
          <Steps steps={s.steps} />
        </div>
      </a>
    </li>
  )
}

// ── 경로·전형 ───────────────────────────────────────────────────────────

function PathsPanel({ o }: { o: Overview }) {
  const p = o.paths
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <Card title="거쳐 온 길" note="경로 단계에 나온 갈래(한 글에 여럿).">
        <Bars items={p.tags} />
      </Card>
      <Card title="준비 방법" note={`준비 기간 중앙값 ${med(p.prep_months.median, '개월')} (${p.prep_months.n}명)`}>
        <Bars items={p.prep} limit={12} />
      </Card>
      <Card title="면접 단계">
        <Bars items={p.interviews} />
      </Card>
      <Card title="코딩테스트" className="md:col-span-2 lg:col-span-3">
        <Bars items={p.coding_test} />
      </Card>
    </div>
  )
}

// ── 지원 결과 ───────────────────────────────────────────────────────────

function Applied({ o }: { o: Overview }) {
  return (
    <Card title="같이 지원한 곳 — 붙고 떨어진 자리" note="경험담에 함께 적힌 다른 지원처. 떨어진 단계는 밝힌 것만.">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[600px] text-sm">
          <thead className="text-left text-[13px] text-[#999] border-b border-[#e6e6e6]">
            <tr>
              <th className="py-2 pr-3 font-medium">회사</th>
              <th className="py-2 pr-3 font-medium">합격</th>
              <th className="py-2 pr-3 font-medium">탈락</th>
              <th className="py-2 pr-3 font-medium">주로 떨어진 단계</th>
            </tr>
          </thead>
          <tbody>
            {o.applied.map((a) => (
              <tr key={a.company} className="border-b border-[#f2f2f2]">
                <td className="py-2 pr-3 font-semibold">{a.company}</td>
                <td className="py-2 pr-3 tabular-nums text-emerald-700">{a.pass}</td>
                <td className="py-2 pr-3 tabular-nums text-rose-700">{a.fail}</td>
                <td className="py-2 pr-3 text-[#666]">{a.stages.map((s) => `${s[0]} ${s[1]}`).join(' · ') || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

// ── 서류·조언 ───────────────────────────────────────────────────────────

function VoiceList({ xs }: { xs: Voice[] }) {
  if (!xs.length) return <p className="text-sm text-[#aaa]">없음</p>
  return (
    <ul className="flex flex-col gap-2 text-[13px] leading-relaxed">
      {xs.map((v, i) => {
        const to = paths.careersStory(v.id)
        return (
          <li key={i}>
            <a href={to} onClick={onLinkClick(to)} className="hover:text-(--color-accent)">
              {v.t}
              <span className="ml-1.5 text-[#aaa]">{[v.company, v.year].filter(Boolean).join(' · ')}</span>
            </a>
          </li>
        )
      })}
    </ul>
  )
}

function Docs({ o }: { o: Overview }) {
  const d = o.docs
  const sec = (title: string, xs: Count[], note?: ReactNode) => (
    <Card title={title} note={note}>
      <Bars items={xs} limit={12} />
    </Card>
  )
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {sec('이력서에서 한 것', d.resume_points)}
        {sec('포트폴리오에서 한 것', d.portfolio_points)}
        {sec('포트폴리오에 넣은 프로젝트', d.portfolio_projects)}
        {sec('자기소개서에서 한 것', d.cover_letter_points)}
        {sec('자기소개서 문항', d.cover_letter_questions)}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="붙은 이유로 꼽은 것">
          <VoiceList xs={o.voices.factors} />
        </Card>
        <Card title="해 주는 말">
          <VoiceList xs={o.voices.advice} />
        </Card>
        <Card title="나온 면접 질문">
          <VoiceList xs={o.voices.questions} />
        </Card>
      </div>
    </div>
  )
}

// ── 합격자 명단 ─────────────────────────────────────────────────────────

function RosterPanel() {
  const { data, error, loading } = useAsync((s) => fetchRoster(s), 'roster')
  if (loading && !data) return <Loader label="명단 여는 중…" />
  if (!data) return <p className="text-sm text-rose-700">{error}</p>
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-[#888]">
        학원·학과·부트캠프가 올린 '합격자 명단' 카드 {data.posts}장에서 읽은 {data.people.toLocaleString()}명(IT 쪽만). 이름은 읽지도 저장하지도 않았다.
        연도·회사 거르기는 이 탭에 걸리지 않는다.
      </p>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="연도">
          <Bars items={data.years.map(([y, n]) => [String(y), n] as Count)} />
        </Card>
        <Card title="출신 학교" className="lg:col-span-2">
          <Bars items={data.schools} limit={20} />
        </Card>
      </div>
      <Card title="합격처별">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="text-left text-[13px] text-[#999] border-b border-[#e6e6e6]">
              <tr>
                {['합격처', '인원', '전공자', '학교', '전공', '연도'].map((h) => (
                  <th key={h} className="py-2 pr-3 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.orgs.map((g) => (
                <tr key={g.org} className="border-b border-[#f2f2f2] align-top">
                  <td className="py-2 pr-3 font-semibold">
                    {g.org}
                    {g.type && <span className="block text-[11px] text-[#aaa] font-normal">{g.type}</span>}
                  </td>
                  <td className="py-2 pr-3 tabular-nums">{g.n}</td>
                  <td className="py-2 pr-3 tabular-nums">{g.n ? `${Math.round((100 * g.cs) / g.n)}%` : '—'}</td>
                  <td className="py-2 pr-3 text-[#555]">{first(g.schools, 5)}</td>
                  <td className="py-2 pr-3 text-[#555]">{first(g.majors, 3)}</td>
                  <td className="py-2 pr-3 tabular-nums text-[#777]">{g.years.map(([y, n]) => `${y}(${n})`).join(' ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
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
  if (!data) return error ? <p className="text-sm text-rose-700">{error}</p> : <Loader label="목록 여는 중…" />
  const pages = Math.ceil(data.n / 40)
  return (
    <Card title={`후기 ${data.n.toLocaleString()}건`} note="누르면 정리한 값과 원문(열쇠가 있을 때).">
      <ul className="flex flex-col divide-y divide-[#f0f0f0]">
        {data.items.map((s) => (
          <StoryRow key={s.id} s={s} />
        ))}
      </ul>
      {pages > 1 && (
        <div className="mt-4 flex items-center justify-center gap-3 text-sm">
          <button type="button" disabled={page === 0} onClick={() => setPage(page - 1)} className="px-3 py-1 rounded border border-[#ddd] disabled:opacity-40">
            이전
          </button>
          <span className="tabular-nums text-[#888]">
            {page + 1} / {pages}
          </span>
          <button type="button" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)} className="px-3 py-1 rounded border border-[#ddd] disabled:opacity-40">
            다음
          </button>
        </div>
      )}
    </Card>
  )
}
