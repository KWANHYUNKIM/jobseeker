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
  전체: '진행 중인 모든 프로젝트',
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
  const evidence = useMemo(() => (cell?.ids ?? []).map((id) => byId.get(id)).filter((p): p is Project => !!p), [cell, byId])
  const allIds = useMemo(() => GRADES.flatMap((g) => cur.table[g]?.['전체']?.ids ?? []), [cur])

  return (
    <div className="flex flex-col gap-[50px]">
      <section>
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-[22px] font-bold leading-8 tracking-[-0.22px] text-[#272727]">
            현재 단가표 <span className="ml-2 text-sm font-normal text-[#999]">월 단가 · 만원</span>
          </h2>
          <button
            type="button"
            className="ml-auto h-9 px-4 rounded-[18px] border border-(--color-accent) text-sm font-medium text-(--color-accent) hover:bg-(--color-accent-weak)"
            onClick={() =>
              download(`외주단가_원자료_${cur.until}.csv`, toCsv(allIds.map((id) => byId.get(id)).filter((p): p is Project => !!p), (p) => p.grade ?? ''))
            }
          >
            원자료 CSV ({allIds.length}건) 내려받기
          </button>
        </div>
        <p className="mt-1 text-base text-[#666]">칸을 누르면 그 숫자를 만든 프로젝트가 아래에 나와요 — 원문 링크와 등급을 어떻게 정했는지까지.</p>

        <div className="mt-5 overflow-x-auto rounded-[22px] border border-[#e2e8ec]">
          <table className="w-full min-w-[720px] border-collapse">
            <thead>
              <tr className="bg-[#f7f9fa]">
                <th className="w-[100px] px-6 py-4 text-left text-sm font-bold text-[#272727]">등급</th>
                {cur.cols.map((c) => (
                  <th key={c} className="px-6 py-4 text-left">
                    <div className="text-sm font-bold text-[#272727]">{c}</div>
                    <div className="text-xs font-normal text-[#999]">{COL_HINT[c]}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {GRADES.map((g) => (
                <tr key={g} className="border-t border-[#eef1f3]">
                  <td className="px-6 text-[15px] font-bold text-[#272727]">{g}</td>
                  {cur.cols.map((c) => {
                    const s = cur.table[g]?.[c]
                    const on = pick?.grade === g && pick.col === c
                    if (!s)
                      return (
                        <td key={c} className="px-6 py-5 text-sm text-[#bbb]">
                          자료 없음
                        </td>
                      )
                    const weak = s.n < 3
                    return (
                      <td key={c} className="p-2">
                        <button
                          type="button"
                          onClick={() => setPick({ grade: g, col: c })}
                          className={'w-full rounded-lg px-4 py-3 text-left transition ' + (on ? 'shadow-[inset_0_0_0_2px_#f45757] bg-(--color-accent-weak)' : 'hover:bg-[#f7f9fa]')}
                          title="눌러서 이 숫자를 만든 프로젝트 보기"
                        >
                          <div className={'tabular-nums ' + (on ? 'text-(--color-accent)' : weak ? 'text-[#999]' : 'text-[#272727]')}>
                            <span className="text-[26px] font-bold leading-[37px]">{s.median.toLocaleString()}</span>
                            <span className="ml-0.5 text-[13px]">만원</span>
                          </div>
                          <div className="text-xs text-[#999] tabular-nums">
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
        <p className="mt-3 text-[13px] text-[#999]">
          기준: {cur.since} ~ {cur.until}(최근 {cur.days}일 안에 목록에서 본 자리) · 상주·원격 월 단가 · 올라올 때 단가
        </p>
      </section>

      {pick && cell && (
        <section>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-[22px] font-bold leading-8 tracking-[-0.22px] text-[#272727]">
              근거 —{' '}
              <span className="font-black text-(--color-accent)">
                {pick.grade} · {pick.col}
              </span>
              <span className="ml-3 text-sm font-normal text-[#999]">
                {evidence.length}건 · 중앙값 {cell.median.toLocaleString()}만원 · 단가 낮은 순
              </span>
            </h2>
            <button
              type="button"
              className="ml-auto h-9 px-4 rounded-[18px] border border-[#d8d8d8] text-sm text-[#272727] hover:border-[#272727]"
              onClick={() => download(`외주단가_${pick.grade}_${pick.col}_${cur.until}.csv`, toCsv(evidence, () => pick.grade))}
            >
              이 칸 CSV
            </button>
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[900px] border-collapse text-sm">
              <thead>
                <tr className="border-y border-[#272727] text-left text-[13px] text-[#474747]">
                  <th className="px-3 py-3 font-medium">월 단가</th>
                  <th className="px-3 font-medium">프로젝트</th>
                  <th className="px-3 font-medium">등급을 정한 근거</th>
                  <th className="px-3 font-medium">분야 · 직무</th>
                  <th className="px-3 font-medium">출처</th>
                  <th className="px-3 font-medium">등록</th>
                  <th className="px-3 font-medium">상태</th>
                </tr>
              </thead>
              <tbody>
                {evidence.map((p) => (
                  <tr key={p.id} className="border-b border-[#eef1f3]">
                    <td className="px-3 py-3 whitespace-nowrap tabular-nums">
                      <b className="text-base font-bold text-(--color-accent)">{Math.round(firstMonthly(p) ?? 0).toLocaleString()}</b>
                      <span className="text-xs text-[#999]">만원</span>
                    </td>
                    <td className="px-3 max-w-[340px]">
                      <a href={p.url} target="_blank" rel="noopener noreferrer" className="block truncate font-medium text-[#272727] hover:underline underline-offset-2">
                        {p.title}
                      </a>
                    </td>
                    <td className="px-3">
                      <span
                        className={
                          'inline-block whitespace-nowrap rounded px-[7px] text-xs leading-[22px] ' +
                          (p.grade_basis === '표기' ? 'bg-[#eaf8f0] text-[#1e9e5a]' : 'bg-[#eef4ff] text-[#3d6ae0]')
                        }
                      >
                        {p.grade_basis === '표기' ? '원본에 적힌 등급' : `경력으로 추정 (${p.career})`}
                      </span>
                    </td>
                    <td className="px-3 whitespace-nowrap text-[#474747]">
                      {p.domain} · {p.role ?? '—'}
                    </td>
                    <td className="px-3 whitespace-nowrap text-[#474747]">{SITE_KO[p.site] ?? p.site}</td>
                    <td className="px-3 whitespace-nowrap text-[#474747] tabular-nums">{p.posted_date ?? `${p.first_seen_at.slice(0, 10)}*`}</td>
                    <td className="px-3">
                      <span className={'whitespace-nowrap rounded px-[7px] text-xs leading-[22px] ' + (p.status === 'closed' ? 'bg-[#f4f4f4] text-[#999]' : 'bg-(--color-accent-weak) text-(--color-accent)')}>
                        {p.status === 'closed' ? '마감' : '모집중'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-[#999]">
            * 등록일을 주지 않는 곳은 우리가 처음 본 날이에요. 마감된 자리도 넣어요 — 단가는 올라올 때 정해지고 사람을 구했다고 바뀌지 않아요.
          </p>
        </section>
      )}
    </div>
  )
}
