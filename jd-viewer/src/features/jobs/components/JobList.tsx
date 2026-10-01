import { useMemo } from 'react'
import type { Job } from '../../../types'
import { classifyRoles, roleColor } from '../../../utils/classify'
import { placeOf, UNKNOWN_REGION } from '../utils/region'
import { usePaged, PAGE_SIZE_DENSE as PAGE_SIZE } from '../../../hooks/usePaged'
import { onLinkClick } from '../../../utils/navigation'
import { paths } from '../../../utils/urls'
import { EmptyState, TechTag, CompanyMark, Pagination } from '../../../components/ui'
import { postedOf, postedText, recruitBadge, type RecruitTone } from '../utils/recruit'

interface Props {
  jobs: Job[]
  /**
   * 서버가 이미 한 쪽으로 잘라 보낸 목록(공고 API)일 때. 있으면 `jobs` 가 곧 지금 쪽이고
   * 전체 건수와 쪽 번호는 여기서 온다. 없으면 예전처럼 `jobs` 전량을 화면에서 자른다.
   */
  server?: { page: number; total: number; onChange: (page: number) => void }
}


// 공고 제목은 목록 안에서 유일하게 '진짜 링크'다. 줄 전체를 <a> 로 감싸면 안에 든
// 원본 링크와 앵커가 겹쳐 잘못된 마크업이 되므로, 제목만 링크로 두고 줄 클릭은
// 그대로 살린다. 크롤러는 이 제목 링크를 따라 공고 상세로 들어온다.
export function JobList({ jobs, server }: Props) {
  const local = usePaged(jobs, PAGE_SIZE)
  const page = server ? server.page : local.page
  const setPage = server ? server.onChange : local.setPage
  const total = server ? server.total : jobs.length
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const start = page * PAGE_SIZE
  const slice = server ? jobs : local.slice

  const rows = useMemo(
    () =>
      slice.map((j) => ({
        job: j,
        // 공고 API 는 직군을 서버에서 계산해 보낸다(목록 응답엔 자격요건 본문이 없다).
        roles: j.roles ?? classifyRoles(j.title, j.tech_stack, j.qualifications || ''),
        place: placeText(j),
      })),
    [slice],
  )

  if (total === 0) {
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
        {rows.map(({ job: j, roles, place }, i) => {
          const to = paths.job(j)
          return (
            <li
              key={`${j.site}-${j.pid}-${j.idx}`}
              onClick={onLinkClick(to)}
              className="px-4 py-3 cursor-pointer transition hover:bg-(--hover)"
            >
              <div className="flex items-center gap-2 text-xs text-(--color-muted) mb-1">
                <span className="tabular-nums">{start + i + 1}</span>
                <CompanyMark name={j.company} size={16} />
                <span className="text-(--color-accent) truncate">{j.company}</span>
                <SizeBadge size={j.company_size} />
                <span className="ml-auto shrink-0 flex items-center gap-1.5">
                  <PostedText job={j} />
                  {place && <span>{place}</span>}
                  {j.career && <span>{j.career}</span>}
                </span>
              </div>
              <a href={to} onClick={onLinkClick(to)} className="block text-(--color-text) text-sm leading-snug line-clamp-2 mb-1.5">
                <StatusBadge job={j} />
                {j.title}
              </a>
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

      {/* 데스크톱: 표.
          여기에 overflow-x-auto 를 주면 이 div 가 sticky 의 기준(스크롤 조상)이 되어
          머리 줄이 바깥 main 을 따라 붙지 못하고 표와 같이 밀려 올라간다.
          가로가 넘칠 때는 바깥 main(overflow-auto)이 대신 받는다. */}
      <div className="hidden md:block">
        <table className="w-full text-sm border-collapse">
          <thead className="jd-panel-head sticky top-0 z-10">
            <tr className="text-left text-(--color-muted) font-medium">
              <th className="px-3 py-2 font-medium w-10">#</th>
              <th className="px-3 py-2 font-medium w-48">회사</th>
              <th className="px-3 py-2 font-medium">공고 제목</th>
              <th className="px-3 py-2 font-medium w-44">분류 직군</th>
              <th className="px-3 py-2 font-medium w-28">지역</th>
              <th className="px-3 py-2 font-medium w-24">경력</th>
              <th className="px-3 py-2 font-medium w-24">등록</th>
              <th className="px-3 py-2 font-medium w-80">기술스택</th>
              <th className="px-3 py-2 font-medium w-16">원본</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ job: j, roles, place }, i) => {
              const to = paths.job(j)
              return (
                <tr
                  key={`${j.site}-${j.pid}-${j.idx}`}
                  onClick={onLinkClick(to)}
                  className="border-b border-(--color-border) cursor-pointer transition hover:bg-(--hover)"
                >
                  <td className="px-3 py-2 text-(--color-muted) tabular-nums">{start + i + 1}</td>
                  <td className="px-3 py-2 text-(--color-muted) max-w-[12rem]" title={j.company}>
                    <span className="flex items-center gap-1.5 min-w-0">
                      <CompanyMark name={j.company} size={16} />
                      <span className="truncate">{j.company}</span>
                      <SizeBadge size={j.company_size} />
                    </span>
                  </td>
                  <td className="px-3 py-2 text-(--color-text)">
                    <a href={to} onClick={onLinkClick(to)} className="line-clamp-2 leading-snug hover:text-(--color-accent)">
                      <StatusBadge job={j} />
                      {j.title}
                    </a>
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
                  <td className="px-3 py-2 text-(--color-muted) text-xs" title={j.location || undefined}>
                    {place || '-'}
                  </td>
                  <td className="px-3 py-2 text-(--color-muted) text-xs">{j.career || '-'}</td>
                  <td className="px-3 py-2 text-(--color-muted) text-xs"><PostedText job={j} /></td>
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
        total={total}
        pageSize={PAGE_SIZE}
        onChange={setPage}
      />
    </div>
  )
}

// 모집 상태 배지. 마감 공고를 목록에서 지우지 않고 표시로 구분하는 이유는, 지운 순간
// "예전에 이런 자리가 있었다"가 사라지기 때문이다. 검색·색인·재공고 추적은 마감 공고를
// 계속 필요로 한다. 대신 기본 필터는 모집중만 보여주므로, 지원할 수 없는 자리를 모르고
// 클릭하는 일은 없다.
//
// 배지가 '마감' 하나였을 때는 모집중이 전부 같은 얼굴이었다. 마감일까지 아는 공고와,
// 원본에 마감 표기가 없어 그냥 열어 둔 공고가 구분되지 않았다 — 후자가 모집중의
// 절반을 넘는다. 무엇을 근거로 열려 있다고 말하는지를 배지가 말한다.
const TONE: Record<RecruitTone, string> = {
  closed: 'bg-(--color-muted)/20 text-(--color-muted) border-(--color-border)',
  urgent: 'bg-(--color-accent)/15 text-(--color-accent) border-(--color-accent)/40',
  open: 'bg-transparent text-(--color-muted) border-(--color-border)',
  always: 'bg-transparent text-(--color-muted) border-(--color-border)',
  unverified: 'bg-transparent text-(--color-muted) border-dashed border-(--color-border)',
}

function StatusBadge({ job }: { job: Job }) {
  const b = recruitBadge(job)
  if (!b) return null
  return (
    <span
      title={b.title}
      className={`mr-1.5 align-middle inline-block px-1.5 py-0.5 text-[10px] font-medium rounded border tabular-nums ${TONE[b.tone]}`}
    >
      {b.label}
    </span>
  )
}

// 등록일. 원본이 말한 값이 없으면 '처음 본 날' 로 대신하고, 그 사실을 title 로 밝힌다.
// 추정값을 확정값처럼 적으면 "9월 2일 등록" 이 사실은 "9월 2일에 우리가 처음 봤다" 가 된다.
function PostedText({ job }: { job: Job }) {
  const p = postedOf(job)
  if (!p) return <span className="text-(--color-muted)">-</span>
  return (
    <span
      className={p.estimated ? 'text-(--color-muted) opacity-70' : 'text-(--color-muted)'}
      title={p.estimated ? `원본에 등록일이 없어 처음 수집한 날로 대신했습니다 (${p.iso})` : `등록 ${p.iso}`}
    >
      {postedText(p.iso)}
      {p.estimated && '~'}
    </span>
  )
}

// 목록에 보일 근무지 — '서울 강남구' 처럼 시도+시군구까지만. 원본 주소는 title 로 남긴다.
function placeText(job: Job): string {
  const p = job.place ?? placeOf(job)
  if (p.region === UNKNOWN_REGION) return ''
  return p.district ? `${p.region} ${p.district}` : p.region
}

// 기업 규모 배지. 중소기업은 붙이지 않는다 — 열에 아홉이 그 값이라, 다 붙이면
// 배지가 아니라 배경이 된다. 눈에 띄어야 하는 건 그 나머지다.
function SizeBadge({ size }: { size?: Job['company_size'] }) {
  if (!size || size === '중소기업') return null
  return (
    <span
      className={`shrink-0 px-1 py-0.5 text-[10px] rounded border ${
        size === '대기업'
          ? 'border-(--color-accent)/50 text-(--color-accent)'
          : 'border-(--color-border) text-(--color-muted)'
      }`}
    >
      {size}
    </span>
  )
}
