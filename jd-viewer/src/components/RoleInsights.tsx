import { useState } from 'react'
import { useRoleInsights, type RoleInsight } from '../lib/useRoleInsights'
import { Loader, ErrorState } from './ui'

// 직군(수식어)별 산업·경력·학력·우대사항·자격요건을 한눈에.
export function RoleInsights() {
  const { data, loading, error } = useRoleInsights()
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
  if (!data || data.roles.length === 0)
    return <div className="p-8 text-(--color-muted)">직군 데이터가 없습니다.</div>

  const sel = data.roles.find((r) => r.role === role) ?? data.roles[0]

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-auto p-4 sm:p-5 gap-4 jd-fade-in">
      {/* 직군 선택 버튼 */}
      <div className="flex flex-wrap gap-1.5">
        {data.roles.map((r) => {
          const on = r.role === sel.role
          return (
            <button
              key={r.role}
              onClick={() => setRole(r.role)}
              className={
                'px-2.5 py-1 rounded text-xs font-medium border transition ' +
                (on
                  ? 'bg-(--color-accent) text-(--color-on-accent) border-(--color-accent)'
                  : 'border-(--color-border) text-(--color-muted) hover:text-(--color-text) hover:border-(--color-accent)')
              }
            >
              {r.role} <span className="opacity-60 tabular-nums">{r.count}</span>
            </button>
          )
        })}
      </div>

      {/* 헤더 */}
      <div className="flex items-baseline gap-2 flex-wrap">
        <h2 className="text-lg font-semibold text-(--color-text)">{sel.role} 개발자</h2>
        <span className="text-xs text-(--color-muted)">
          공고 {sel.count.toLocaleString()}건 기준 · 전체 {data.total_jobs.toLocaleString()}건 중 · 우대/자격은 키워드 등장 빈도
        </span>
      </div>

      {/* 산업 · 경력 · 학력 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <Card title="관련 산업" sub="이 직군이 주로 속한 도메인">
          <RankBar items={sel.industries.map((x) => ({ label: x.name, count: x.count }))} />
        </Card>
        <Card title="경력" sub="요구 경력 분포">
          {sel.career.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-2">
              {sel.career.map((c) => (
                <span
                  key={c.name}
                  className="text-[11px] px-1.5 py-0.5 rounded bg-(--color-bg) border border-(--color-border) text-(--color-text)"
                >
                  {c.name} <span className="text-(--color-muted) tabular-nums">{c.count}</span>
                </span>
              ))}
            </div>
          )}
          <RankBar items={sel.years.map((x) => ({ label: x.name, count: x.count }))} />
        </Card>
        <Card title="학력" sub="언급된 학력 요건">
          <RankBar items={sel.education.map((x) => ({ label: x.name, count: x.count }))} />
        </Card>
      </div>

      {/* 기술스택 */}
      <Card title="주요 기술스택" sub="공고에서 가장 많이 요구된 기술">
        <div className="flex flex-wrap gap-1.5">
          {sel.tech.map((t) => (
            <span
              key={t.name}
              className="text-[11px] px-2 py-0.5 rounded bg-(--color-accent)/12 text-(--color-accent) border border-(--color-accent)/25"
            >
              {t.name} <span className="opacity-60 tabular-nums">{t.count}</span>
            </span>
          ))}
        </div>
      </Card>

      {/* 우대사항 · 자격요건 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <Card title="우대사항 (자주 등장)" sub="preferences 키워드 빈도">
          <RankBar items={sel.preferences.map((x) => ({ label: x.kw, count: x.count }))} />
        </Card>
        <Card title="자격요건 (자주 등장)" sub="qualifications 키워드 빈도">
          <RankBar items={sel.qualifications.map((x) => ({ label: x.kw, count: x.count }))} />
        </Card>
      </div>

      <p className="text-[11px] text-(--color-muted) leading-relaxed">
        ※ 내 잡 리스트({data.total_jobs.toLocaleString()}건)를 직군으로 멀티라벨 분류 후 집계. 우대사항·자격요건은 자유텍스트에서
        키워드 사전으로 추출한 등장 빈도라 실제 문장과 다를 수 있습니다.
      </p>
    </div>
  )
}

function Card({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-3">
      <div className="mb-2">
        <h3 className="text-sm font-semibold text-(--color-text)">{title}</h3>
        {sub && <p className="text-[11px] text-(--color-muted)">{sub}</p>}
      </div>
      {children}
    </section>
  )
}

function RankBar({ items }: { items: { label: string; count: number }[] }) {
  if (items.length === 0) return <div className="text-xs text-(--color-muted)">데이터 없음</div>
  const max = Math.max(...items.map((i) => i.count), 1)
  return (
    <ul className="flex flex-col gap-1">
      {items.map((it) => (
        <li key={it.label} className="flex items-center gap-2">
          <span className="w-28 sm:w-36 text-xs text-(--color-text) truncate" title={it.label}>
            {it.label}
          </span>
          <span className="flex-1 h-1.5 rounded bg-(--color-bg) overflow-hidden">
            <span className="block h-full bg-(--color-accent)" style={{ width: `${(it.count / max) * 100}%` }} />
          </span>
          <span className="w-9 text-right text-xs text-(--color-muted) tabular-nums">{it.count}</span>
        </li>
      ))}
    </ul>
  )
}

export type { RoleInsight }
