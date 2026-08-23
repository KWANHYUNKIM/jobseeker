import { useMemo } from 'react'
import type { Job } from '../types'
import { classifyRoles, roleColor } from '../lib/classify'
import { usePaged } from '../lib/usePaged'
import { EmptyState, TechTag, CompanyMark, Pagination } from './ui'

interface Props {
  jobs: Job[]
  selected: Job | null
  onSelect: (j: Job) => void
}

const PAGE_SIZE = 20

export function JobList({ jobs, selected, onSelect }: Props) {
  const { page, setPage, totalPages, start, slice } = usePaged(jobs, PAGE_SIZE)

  const rows = useMemo(
    () =>
      slice.map((j) => ({
        job: j,
        roles: classifyRoles(j.title, j.tech_stack, j.qualifications || ''),
      })),
    [slice],
  )

  if (jobs.length === 0) {
    return (
      <EmptyState
        title="조건에 맞는 공고가 없습니다"
        hint="필터를 줄이거나 검색어를 바꿔보세요."
      />
    )
  }

  return (
    <div className="flex flex-col">
      {/* 모바일: 카드 리플로우 (표는 좁은 화면에서 잘리므로) */}
      <ul className="md:hidden divide-y divide-(--color-border)">
        {rows.map(({ job: j, roles }, i) => {
          const active = selected?.site === j.site && selected?.pid === j.pid
          return (
            <li
              key={`${j.site}-${j.pid}-${j.idx}`}
              onClick={() => onSelect(j)}
              className={'px-4 py-3 cursor-pointer transition ' + (active ? 'bg-(--color-accent)/15' : 'hover:bg-(--hover)')}
            >
              <div className="flex items-center gap-2 text-xs text-(--color-muted) mb-1">
                <span className="tabular-nums">{start + i + 1}</span>
                <span className="px-1.5 py-0.5 rounded bg-(--color-bg) border border-(--color-border)">{j.site}</span>
                <CompanyMark name={j.company} size={16} />
                <span className="text-(--color-accent) truncate">{j.company}</span>
                {j.career && <span className="ml-auto shrink-0">{j.career}</span>}
              </div>
              <div className="text-(--color-text) text-sm leading-snug line-clamp-2 mb-1.5">
                {j.status === 'closed' && <ClosedBadge reason={j.closed_reason} />}
                {j.title}
              </div>
              {roles.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-1.5">
                  {roles.map((r) => (
                    <span key={r} className="text-[10px] px-1.5 py-0.5 rounded border"
                      style={{ borderColor: roleColor(r), color: roleColor(r) }}>{r}</span>
                  ))}
                </div>
              )}
              <div className="flex flex-wrap items-center gap-1">
                {(j.tech_stack || []).slice(0, 6).map((t) => (
                  <TechTag key={t} tech={t} />
                ))}
                {j.tech_stack && j.tech_stack.length > 6 && (
                  <span className="text-[10px] text-(--color-muted)">+{j.tech_stack.length - 6}</span>
                )}
                {j.url && (
                  <a href={j.url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}
                    className="ml-auto shrink-0 text-xs px-2 py-0.5 rounded border border-(--color-border) text-(--color-muted) hover:text-(--color-accent) hover:border-(--color-accent)">원본 ↗</a>
                )}
              </div>
            </li>
          )
        })}
      </ul>

      {/* 데스크톱: 표 */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead className="jd-panel-head sticky top-0 z-10">
            <tr className="text-left text-(--color-muted) font-medium">
              <th className="px-3 py-2 font-medium w-10">#</th>
              <th className="px-3 py-2 font-medium w-20">사이트</th>
              <th className="px-3 py-2 font-medium w-48">회사</th>
              <th className="px-3 py-2 font-medium">공고 제목</th>
              <th className="px-3 py-2 font-medium w-44">분류 직군</th>
              <th className="px-3 py-2 font-medium w-24">경력</th>
              <th className="px-3 py-2 font-medium w-80">기술스택</th>
              <th className="px-3 py-2 font-medium w-16">원본</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ job: j, roles }, i) => {
              const active = selected?.site === j.site && selected?.pid === j.pid
              return (
                <tr
                  key={`${j.site}-${j.pid}-${j.idx}`}
                  onClick={() => onSelect(j)}
                  className={
                    'border-b border-(--color-border) cursor-pointer transition ' +
                    (active ? 'bg-(--color-accent)/15' : 'hover:bg-(--hover)')
                  }
                >
                  <td className="px-3 py-2 text-(--color-muted) tabular-nums">{start + i + 1}</td>
                  <td className="px-3 py-2">
                    <span className="text-xs px-1.5 py-0.5 rounded bg-(--color-bg) text-(--color-muted) border border-(--color-border)">
                      {j.site}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-(--color-muted) max-w-[12rem]" title={j.company}>
                    <span className="flex items-center gap-1.5 min-w-0">
                      <CompanyMark name={j.company} size={16} />
                      <span className="truncate">{j.company}</span>
                    </span>
                  </td>
                  <td className="px-3 py-2 text-(--color-text)">
                    <div className="line-clamp-2 leading-snug">
                      {j.status === 'closed' && <ClosedBadge reason={j.closed_reason} />}
                      {j.title}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {roles.map((r) => (
                        <span
                          key={r}
                          className="text-[10px] px-1.5 py-0.5 rounded border"
                          style={{ borderColor: roleColor(r), color: roleColor(r) }}
                        >
                          {r}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-(--color-muted) text-xs">{j.career || '-'}</td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {(j.tech_stack || []).slice(0, 8).map((t) => (
                        <TechTag key={t} tech={t} />
                      ))}
                      {j.tech_stack && j.tech_stack.length > 8 && (
                        <span className="text-[10px] text-(--color-muted)">
                          +{j.tech_stack.length - 8}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    {j.url && (
                      <a
                        href={j.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="text-xs px-2 py-1 rounded border border-(--color-border) text-(--color-muted) hover:text-(--color-accent) hover:border-(--color-accent)"
                        title="원본 공고 새 창으로 열기"
                      >
                        ↗
                      </a>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <Pagination
        page={page}
        totalPages={totalPages}
        total={jobs.length}
        pageSize={PAGE_SIZE}
        onChange={setPage}
      />
    </div>
  )
}

// 마감 배지. 마감 공고를 목록에서 지우지 않고 표시로 구분하는 이유는, 지운 순간
// "예전에 이런 자리가 있었다"가 사라지기 때문이다. 검색·색인·재공고 추적은 마감 공고를
// 계속 필요로 한다. 대신 기본 필터는 모집중만 보여주므로, 지원할 수 없는 자리를 모르고
// 클릭하는 일은 없다.
function ClosedBadge({ reason }: { reason?: string }) {
  return (
    <span
      title={reason || '마감'}
      className="mr-1.5 align-middle inline-block px-1.5 py-0.5 text-[10px] font-medium rounded bg-(--color-muted)/20 text-(--color-muted) border border-(--color-border)"
    >
      마감
    </span>
  )
}
