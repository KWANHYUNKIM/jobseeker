import { useState, type ReactNode } from 'react'
import type { RoleInsight, RoleInsightsFile } from '../hooks/useRoleInsights'
import { useTrends } from '../hooks/useTrends'
import { Loader, ErrorState } from '../../../components/ui'
import type { TrendMover } from '../../../types'

/**
 * 직군 분석(캐치형 09) — 직군 칩, 지금 보는 직군 띠(숫자 넷), 주요 기술스택(1~3위 칸 + 막대),
 * 관련 산업·요구 경력·학력, 우대사항·자격요건 TOP 10, 어제보다 많이·덜 찾는 기술.
 */
export function RoleInsights({ data, loading, error }: { data: RoleInsightsFile | null; loading: boolean; error: string | null }) {
  const { data: trends } = useTrends()
  const [role, setRole] = useState<string | null>(null)

  if (loading) return <Loader label="직군 인사이트 불러오는 중…" />
  if (error)
    return (
      <ErrorState
        title="role_insights.json 로드 실패"
        detail={error}
        hint={
          <>
            생성: <code className="text-(--color-text)">python bin/build_role_insights.py</code> (jd-viewer)
          </>
        }
      />
    )
  if (!data || data.roles.length === 0) return <div className="p-8 text-(--color-muted)">직군 데이터가 없습니다.</div>

  // '기타' 는 어느 직군에도 안 걸린 공고의 묶음이라 고를 거리가 아니다.
  const roles = data.roles.filter((r) => r.role !== '기타')
  const sel = roles.find((r) => r.role === role) ?? roles[0] ?? data.roles[0]
  const share = data.total_jobs ? Math.round((sel.count / data.total_jobs) * 1000) / 10 : 0
  const topYears = [...sel.years].sort((a, b) => b.count - a.count)[0]

  return (
    <div>
      {/* 직군 칩 */}
      <div className="flex flex-wrap gap-2">
        {roles.map((r) => {
          const on = r.role === sel.role
          return (
            <button
              key={r.role}
              type="button"
              aria-pressed={on}
              onClick={() => setRole(r.role)}
              className={
                'inline-flex items-center gap-1.5 h-9 px-[17px] rounded-[18px] border text-sm font-medium tracking-[-0.3px] ' +
                (on ? 'bg-(--color-accent) border-(--color-accent) text-white' : 'bg-white border-[#d8d8d8] text-[#272727] hover:border-[#272727]')
              }
            >
              {r.role}
              <span className={'text-xs font-normal tabular-nums ' + (on ? 'text-[#ffd9d9]' : 'text-[#999]')}>{r.count}</span>
            </button>
          )
        })}
      </div>

      {/* 지금 보는 직군 */}
      <section className="mt-[26px] flex flex-col lg:flex-row lg:items-center gap-6 rounded-[30px] bg-[#272727] px-10 py-[34px]">
        <div className="min-w-0 flex-1">
          <div className="text-sm text-[#bbb]">지금 보고 있는 직군</div>
          <h2 className="mt-0.5 text-[32px] font-bold leading-[47px] tracking-[-0.6px] text-white">{sel.role} 개발자</h2>
          <div className="mt-[5px] text-[15px] text-[#ccc] tabular-nums">
            공고 {sel.count.toLocaleString()}건 기준 · 전체 {data.total_jobs.toLocaleString()}건 중 {share}%
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-[10px] lg:w-[710px] shrink-0">
          <Mini label="가장 많은 산업" value={sel.industries[0]?.name ?? '-'} />
          <Mini label="가장 많은 경력" value={topYears?.name ?? '-'} />
          <Mini label="1위 기술" value={sel.tech[0] ? `${sel.tech[0].name} ${sel.tech[0].count}건` : '-'} />
          <Mini label="1위 우대사항" value={sel.preferences[0]?.kw ?? '-'} />
        </div>
      </section>

      <div className="mt-5 grid lg:grid-cols-2 gap-5 items-start">
        <Card title="주요 기술스택" sub="공고에서 가장 많이 요구된 기술">
          <div className="grid grid-cols-3 gap-2">
            {sel.tech.slice(0, 3).map((t, i) => (
              <div key={t.name} className="h-[113px] rounded-[18px] bg-(--color-accent-weak) px-4 pt-5">
                <div className="text-[13px] font-bold text-(--color-accent)">{i + 1}</div>
                <div className="mt-1 text-xl font-bold leading-[29px] text-[#272727] truncate">{t.name}</div>
                <div className="mt-[3px] text-sm text-[#666] tabular-nums">{t.count}건</div>
              </div>
            ))}
          </div>
          <Bars items={sel.tech.slice(3, 16).map((t) => ({ label: t.name, n: t.count }))} labelW={112} strong={6} className="mt-[22px]" />
        </Card>

        <div className="flex flex-col gap-5">
          <Card title="관련 산업" sub="이 직군이 주로 속한 도메인">
            <Bars items={sel.industries.slice(0, 8).map((x) => ({ label: x.name, n: x.count }))} labelW={182} />
          </Card>
          <div className="grid sm:grid-cols-2 gap-5">
            <Card title="요구 경력" sub="경력 분포">
              <Bars items={sel.years.map((x) => ({ label: x.name, n: x.count }))} labelW={72} />
            </Card>
            <Card title="학력" sub="언급된 학력 요건">
              <Bars items={sel.education.map((x) => ({ label: x.name, n: x.count }))} labelW={112} />
            </Card>
          </div>
        </div>

        <Card title={<>우대사항 <span className="font-black text-(--color-accent)">TOP 10</span></>} sub="preferences 키워드 빈도">
          <Bars items={sel.preferences.slice(0, 10).map((x) => ({ label: x.kw, n: x.count }))} labelW={182} strong={10} />
        </Card>
        <Card title={<>자격요건 <span className="font-black text-(--color-accent)">TOP 10</span></>} sub="qualifications 키워드 빈도">
          <Bars items={sel.qualifications.slice(0, 10).map((x) => ({ label: x.kw, n: x.count }))} labelW={182} strong={10} />
        </Card>
      </div>

      {trends && (trends.movers.up.length > 0 || trends.movers.down.length > 0) && (
        <section className="mt-[50px]">
          <h2 className="text-[22px] font-bold leading-8 tracking-[-0.22px] text-[#272727]">
            어제보다 <span className="font-black text-(--color-accent)">많이 찾는</span> 기술
          </h2>
          <p className="mt-0.5 text-[15px] text-[#666]">
            {trends.days.length > 1 ? `${trends.days[trends.days.length - 2].date} → ` : ''}
            {trends.span.to} · 전체 공고 중 언급 비중 변화
          </p>
          <div className="mt-5 grid lg:grid-cols-2 gap-5">
            <MoverCard up items={trends.movers.up.slice(0, 6)} />
            <MoverCard up={false} items={trends.movers.down.slice(0, 6)} />
          </div>
        </section>
      )}

      <p className="mt-[34px] text-xs leading-relaxed text-[#999]">
        ※ 잡 리스트({data.total_jobs.toLocaleString()}건)를 직군으로 멀티라벨 분류 후 집계. 우대사항·자격요건은 자유텍스트에서 키워드 사전으로
        추출한 등장 빈도라 실제 문장과 다를 수 있습니다.
      </p>
    </div>
  )
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="h-[82px] rounded-2xl bg-white/8 px-[18px] pt-4">
      <div className="text-[13px] text-[#bbb]">{label}</div>
      <div className="mt-1.5 text-[17px] font-bold leading-[25px] text-white truncate">{value}</div>
    </div>
  )
}

function Card({ title, sub, children }: { title: ReactNode; sub?: string; children: ReactNode }) {
  return (
    <section className="rounded-[30px] border border-[#e2e8ec] bg-white px-[31px] pt-[29px] pb-[31px]">
      <h3 className="text-xl font-bold leading-[29px] tracking-[-0.16px] text-[#272727]">{title}</h3>
      {sub && <p className="mt-1 text-sm text-[#999]">{sub}</p>}
      <div className="mt-[17px]">{children}</div>
    </section>
  )
}

/** 가로 막대 — 앞의 `strong` 개는 진한 분홍, 나머지는 옅은 분홍. 값은 오른쪽 끝에. */
function Bars({ items, labelW, strong = 99, className = '' }: { items: { label: string; n: number }[]; labelW: number; strong?: number; className?: string }) {
  if (items.length === 0) return <div className="text-sm text-[#999]">데이터 없음</div>
  const max = Math.max(...items.map((i) => i.n), 1)
  return (
    <ul className={'flex flex-col gap-[10px] ' + className}>
      {items.map((it, i) => (
        <li key={it.label} className="flex items-center">
          <span className="shrink-0 text-sm text-[#474747] truncate" style={{ width: labelW }} title={it.label}>
            {it.label}
          </span>
          <span className="flex-1 h-[14px] rounded-[7px] bg-[#f1f3f5] overflow-hidden">
            <span className="block h-full rounded-[7px]" style={{ width: `${(it.n / max) * 100}%`, background: i < strong ? '#f67979' : '#f9b4b4' }} />
          </span>
          <span className="w-[46px] shrink-0 text-right text-sm font-medium text-[#272727] tabular-nums">{it.n}</span>
        </li>
      ))}
    </ul>
  )
}

function MoverCard({ up, items }: { up: boolean; items: TrendMover[] }) {
  const color = up ? 'text-(--color-accent)' : 'text-[#4f7cf0]'
  return (
    <section className="rounded-[30px] border border-[#e2e8ec] bg-white px-[31px] pt-[27px] pb-5">
      <h3 className={'text-lg font-bold ' + color}>{up ? '▲ 오르는 기술' : '▼ 내리는 기술'}</h3>
      <ul className="mt-2">
        {items.map((m) => (
          <li key={m.tech} className="flex items-center gap-3 h-[52px] border-b border-[#eef1f3] last:border-b-0">
            <span className="flex-1 min-w-0 truncate text-base font-bold text-[#272727]">{m.tech}</span>
            <span className="text-[15px] text-[#666] tabular-nums">
              {m.from_pct.toFixed(1)}% → <b className="font-bold text-[#272727]">{m.to_pct.toFixed(1)}%</b>
            </span>
            <span className={'w-[86px] text-right text-base font-bold tabular-nums ' + color}>
              {up ? '▲' : '▼'} {Math.abs(m.delta).toFixed(2)}%p
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}

export type { RoleInsight }
