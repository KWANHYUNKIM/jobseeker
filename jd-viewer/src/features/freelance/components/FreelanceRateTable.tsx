import { useMemo, useState } from 'react'
import { GRADES, SITE_KO, firstMonthly, type Analysis, type Grade, type Project } from '../utils/freelance'

// 현재 단가표 — 단가 분석의 첫 화면.
//
// 숫자만 보여 주면 믿을 근거가 없다. 칸을 누르면 그 숫자를 만든 프로젝트가 아래에 그대로
// 펼쳐지고(원문 링크·단가·등급을 어떻게 정했는지), CSV 로 내려받아 직접 다시 셀 수 있다.
// 칸의 프로젝트 목록은 분석 모듈이 표를 셀 때 쓴 id 그대로다 — 화면이 따로 거르지 않는다.

type Cur = NonNullable<Analysis['current']>
type Pick = { grade: Grade; col: string }

const COL_HINT: Record<string, string> = {
  전체: '모든 월 단가 프로젝트',
  SI: '구축·차세대·고도화',
  SM: '운영·유지보수',
}

function csvCell(v: unknown): string {
  const s = v == null ? '' : String(v)
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

function toCsv(rows: Project[], label: (p: Project) => string): string {
  const head = ['등급', '등급근거', '경력표기', '유형', '분야', '직무', '월단가(만원,올라올때)', '현재단가', '출처', '제목', '지역', '등록일', '처음본날', '마지막본날', '상태', '원문']
  const lines = rows.map((p) =>
    [
      label(p),
      p.grade_basis,
      p.career,
      p.work_type,
      p.domain,
      p.role,
      firstMonthly(p),
      p.budget ? `${p.budget.min ?? ''}~${p.budget.max ?? ''}` : '',
      SITE_KO[p.site] ?? p.site,
      p.title,
      p.location,
      p.posted_date,
      p.first_seen_at.slice(0, 10),
      p.last_seen_at.slice(0, 10),
      p.status === 'closed' ? '마감' : '모집중',
      p.url,
    ]
      .map(csvCell)
      .join(','),
  )
  return '﻿' + [head.join(','), ...lines].join('\n') // BOM — 엑셀이 한글을 깨지 않게
}

function download(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

export function CurrentRateTable({ cur, projects }: { cur: Cur; projects: Project[] }) {
  const [pick, setPick] = useState<Pick | null>({ grade: '고급', col: '전체' })
  const byId = useMemo(() => new Map(projects.map((p) => [p.id, p])), [projects])
  const cell = pick ? cur.table[pick.grade]?.[pick.col] : null
  const evidence = useMemo(
    () => (cell?.ids ?? []).map((id) => byId.get(id)).filter((p): p is Project => !!p),
    [cell, byId],
  )
  const allIds = useMemo(
    () => GRADES.flatMap((g) => cur.table[g]?.['전체']?.ids ?? []),
    [cur],
  )

  return (
    <div className="flex flex-col gap-4">
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-separate border-spacing-1">
          <thead>
            <tr className="text-xs text-(--color-muted)">
              <th className="text-left font-normal px-2">등급</th>
              {cur.cols.map((c) => (
                <th key={c} className="font-normal px-2 text-center" title={COL_HINT[c]}>
                  {c}
                  <div className="text-[10px] opacity-70">{COL_HINT[c]}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {GRADES.map((g) => (
              <tr key={g}>
                <td className="px-2 font-semibold text-(--color-text)">{g}</td>
                {cur.cols.map((c) => {
                  const s = cur.table[g]?.[c]
                  const on = pick?.grade === g && pick.col === c
                  if (!s)
                    return (
                      <td key={c} className="text-center text-xs text-(--color-muted)/60 rounded-md border border-dashed border-(--color-border) py-3">
                        자료 없음
                      </td>
                    )
                  const weak = s.n < 3
                  return (
                    <td key={c} className="p-0">
                      <button
                        onClick={() => setPick({ grade: g, col: c })}
                        className={`w-full rounded-md border px-3 py-2 text-center transition ${
                          on
                            ? 'border-(--color-accent) bg-(--color-accent)/10 ring-1 ring-(--color-accent)'
                            : 'border-(--color-border) hover:border-(--color-accent)'
                        }`}
                        title="눌러서 이 숫자를 만든 프로젝트 보기"
                      >
                        <div className={`text-lg font-bold tabular-nums ${weak ? 'text-(--color-muted)' : 'text-(--color-text)'}`}>
                          {s.median.toLocaleString()}
                          <span className="text-xs font-normal">만원</span>
                        </div>
                        <div className="text-[11px] text-(--color-muted) tabular-nums">
                          {s.p25.toLocaleString()}~{s.p75.toLocaleString()} · {s.n}건{weak ? ' · 표본 부족' : ''}
                        </div>
                      </button>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs text-(--color-muted)">
        <span>
          기준: {cur.since} ~ {cur.until} (최근 {cur.days}일 안에 목록에서 본 자리) · 상주·원격 월 단가 · 올라올 때 단가
        </span>
        <button
          className="ml-auto px-2.5 py-1 rounded border border-(--color-border) hover:border-(--color-accent) text-(--color-text)"
          onClick={() =>
            download(
              `외주단가_원자료_${cur.until}.csv`,
              toCsv(allIds.map((id) => byId.get(id)).filter((p): p is Project => !!p), (p) => p.grade ?? ''),
            )
          }
        >
          표 전체 원자료 CSV ({allIds.length}건)
        </button>
      </div>

      {pick && cell && (
        <section className="rounded-lg border border-(--color-border) bg-(--color-bg)/40">
          <div className="flex flex-wrap items-baseline gap-2 px-3 py-2 border-b border-(--color-border)">
            <h3 className="text-sm font-semibold text-(--color-text)">
              근거 — {pick.grade} · {pick.col}
            </h3>
            <span className="text-xs text-(--color-muted)">
              {evidence.length}건 · 중앙값 {cell.median.toLocaleString()}만원 (단가 낮은 순)
            </span>
            <button
              className="ml-auto text-xs text-(--color-accent) hover:underline"
              onClick={() => download(`외주단가_${pick.grade}_${pick.col}_${cur.until}.csv`, toCsv(evidence, () => pick.grade))}
            >
              이 칸 CSV
            </button>
          </div>
          <div className="max-h-[420px] overflow-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-(--color-panel) text-(--color-muted)">
                <tr>
                  <th className="text-right font-normal px-2 py-1">월 단가</th>
                  <th className="text-left font-normal px-2">프로젝트</th>
                  <th className="text-left font-normal px-2">등급을 정한 근거</th>
                  <th className="text-left font-normal px-2">분야 · 직무</th>
                  <th className="text-left font-normal px-2">출처</th>
                  <th className="text-left font-normal px-2">등록</th>
                  <th className="text-left font-normal px-2">상태</th>
                </tr>
              </thead>
              <tbody>
                {evidence.map((p) => (
                  <tr key={p.id} className="border-t border-(--color-border) align-top">
                    <td className="text-right px-2 py-1 tabular-nums font-semibold text-(--color-text)">
                      {Math.round(firstMonthly(p) ?? 0).toLocaleString()}
                    </td>
                    <td className="px-2 py-1">
                      <a href={p.url} target="_blank" rel="noopener noreferrer" className="text-(--color-text) hover:text-(--color-accent)">
                        {p.title}
                      </a>
                    </td>
                    <td className="px-2 py-1 text-(--color-muted)">
                      {p.grade_basis === '표기' ? '원본에 적힌 등급' : `경력으로 추정 (${p.career})`}
                    </td>
                    <td className="px-2 py-1 text-(--color-muted)">
                      {p.domain} · {p.role ?? '—'}
                    </td>
                    <td className="px-2 py-1 text-(--color-muted)">{SITE_KO[p.site] ?? p.site}</td>
                    <td className="px-2 py-1 text-(--color-muted) tabular-nums">{p.posted_date ?? `${p.first_seen_at.slice(0, 10)}*`}</td>
                    <td className="px-2 py-1 text-(--color-muted)">{p.status === 'closed' ? '마감' : '모집중'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="px-3 py-1.5 text-[11px] text-(--color-muted) border-t border-(--color-border)">
            * 등록일을 주지 않는 곳은 우리가 처음 본 날입니다. 마감된 자리도 넣습니다 — 단가는 올라올 때 정해지고 사람을
            구했다고 바뀌지 않습니다.
          </p>
        </section>
      )}
    </div>
  )
}
