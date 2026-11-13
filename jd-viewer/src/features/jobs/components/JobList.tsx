import { useEffect, useMemo, useState } from 'react'
import type { Job } from '../../../types'
import { classifyRoles } from '../../../utils/classify'
import { placeOf, UNKNOWN_REGION } from '../utils/region'
import { usePaged, PAGE_SIZE_DENSE as PAGE_SIZE } from '../../../hooks/usePaged'
import { onLinkClick } from '../../../utils/navigation'
import { paths } from '../../../utils/urls'
import { EmptyState } from '../../../components/ui'
import { daysUntil } from '../utils/recruit'

interface Props {
  jobs: Job[]
  /**
   * 서버가 이미 한 쪽으로 잘라 보낸 목록(공고 API)일 때. 있으면 `jobs` 가 곧 지금 쪽이고
   * 전체 건수와 쪽 번호는 여기서 온다. 없으면 예전처럼 `jobs` 전량을 화면에서 자른다.
   */
  server?: { page: number; total: number; onChange: (page: number) => void }
  /** 수집된 공고 자체가 없다(첫 크롤 전). 이때 "필터를 줄이라" 는 엉뚱한 안내다. */
  noData?: boolean
}

/** 마감까지 이만큼 남으면 줄을 붉게 칠하고 '지원 서두르기' 를 단다. */
const HURRY_DAYS = 14

/**
 * 공고 목록(캐치형 잡 리스트) — 한 공고가 한 줄: 회사 | 제목·직군·기술 | 경력·지역·출처 | 마감 | 별.
 * 마감이 2주 안이면 줄 전체를 옅은 분홍으로 칠한다. 공고 제목은 목록 안에서 유일한 '진짜 링크'다 —
 * 줄 전체를 <a> 로 감싸면 안의 별 단추와 겹쳐 잘못된 마크업이 되므로 제목만 링크로 두고
 * 줄 클릭은 그대로 살린다. 크롤러는 이 제목 링크를 따라 공고 상세로 들어온다.
 */
export function JobList({ jobs, server, noData }: Props) {
  const local = usePaged(jobs, PAGE_SIZE)
  const page = server ? server.page : local.page
  const setPage = server ? server.onChange : local.setPage
  const total = server ? server.total : jobs.length
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const slice = server ? jobs : local.slice
  const stars = useStars()

  const rows = useMemo(
    () =>
      slice.map((j) => ({
        job: j,
        // 공고 API 는 직군을 서버에서 계산해 보낸다(목록 응답엔 자격요건 본문이 없다).
        roles: j.roles ?? classifyRoles(j.title, j.tech_stack, j.qualifications || ''),
        place: placeText(j),
        left: j.status === 'closed' ? null : daysUntil(j.deadline_date),
      })),
    [slice],
  )

  if (total === 0 && noData) {
    return <EmptyState title="아직 수집된 공고가 없습니다" hint="크롤링이 돌고 있으면 첫 회차가 끝나는 대로 여기에 공고가 뜹니다." />
  }
  if (total === 0) {
    return <EmptyState title="조건에 맞는 공고가 없습니다" hint="필터를 줄이거나 검색어를 바꿔보세요." />
  }

  return (
    <div className="flex flex-col">
      <ul>
        {rows.map(({ job: j, roles, place, left }) => {
          const to = paths.job(j)
          const hurry = left != null && left >= 0 && left <= HURRY_DAYS
          const key = `${j.site}-${j.pid}`
          return (
            <li
              key={`${key}-${j.idx}`}
              onClick={onLinkClick(to)}
              className={
                'group cursor-pointer flex flex-col md:flex-row md:items-center gap-2 md:gap-0 border-b px-4 md:px-0 py-4 md:py-0 ' +
                (hurry ? 'bg-[#feecec]/93 border-(--color-accent) md:min-h-[130px]' : 'border-[#e2e2e2] hover:bg-[#fafafa] md:min-h-[117px]') +
                (j.status === 'closed' ? ' opacity-60' : '')
              }
            >
              <div className="md:w-[226px] md:shrink-0 md:pl-5 min-w-0">
                <div className="text-lg leading-[26px] tracking-[-0.16px] text-[#272727] truncate">{companyText(j.company)}</div>
                <div className="text-sm leading-[21px] tracking-[-0.16px] text-[#666]">{j.company_size ?? ''}</div>
                {hurry && <div className="mt-[5px] text-[11px] leading-4 text-[#f89a9a]">마감 임박</div>}
              </div>
              <div className="md:w-[640px] md:shrink-0 md:pl-5 md:pr-6 min-w-0">
                {hurry && (
                  <span className="mb-[6px] inline-block rounded bg-[#f67979] px-[7px] text-[13px] leading-[22px] tracking-[-0.13px] text-white tabular-nums">
                    ⏰ {left === 0 ? '오늘 마감' : `D-${left} 마감`}
                  </span>
                )}
                <a
                  href={to}
                  onClick={onLinkClick(to)}
                  className="block text-lg font-medium leading-[26px] tracking-[-0.16px] text-[#272727] line-clamp-1 group-hover:underline underline-offset-2"
                >
                  {j.title}
                </a>
                <div className="mt-1.5 text-[15px] leading-[21px] tracking-[-0.16px] truncate">
                  <span className="text-[#474747]">{roles.length ? roles.join(' · ') : '기타'}</span>
                  {j.tech_stack?.length > 0 && <span className="text-[#999]"> | {j.tech_stack.slice(0, 5).join(', ')}</span>}
                </div>
              </div>
              <ul className="md:w-[200px] md:shrink-0 md:pl-5 flex md:flex-col gap-x-4 gap-y-[3px] text-sm leading-[21px] tracking-[-0.16px] text-[#474747]">
                <Meta icon="career">{j.career || '경력 무관'}</Meta>
                <Meta icon="place">{place || '지역 미표기'}</Meta>
                <Meta icon="site">{sourceText(j)}</Meta>
              </ul>
              <Deadline job={j} left={left} hurry={hurry} />
              <div className="hidden md:flex md:w-[50px] md:shrink-0">
                <StarButton on={stars.has(key)} onClick={() => stars.toggle(key)} />
              </div>
            </li>
          )
        })}
      </ul>
      <Pager page={page} totalPages={totalPages} onChange={setPage} />
    </div>
  )
}

function Meta({ icon, children }: { icon: 'career' | 'place' | 'site'; children: React.ReactNode }) {
  return (
    <li className="flex items-center gap-[7px] min-w-0">
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="#474747" strokeWidth="1.3" aria-hidden className="shrink-0">
        {icon === 'career' && (
          <>
            <circle cx="7" cy="7" r="5.5" />
            <path d="M7 4v3.2l2 1.2" strokeLinecap="round" />
          </>
        )}
        {icon === 'place' && (
          <>
            <path d="M7 12.5s4-3.6 4-6.6a4 4 0 0 0-8 0c0 3 4 6.6 4 6.6Z" />
            <circle cx="7" cy="5.8" r="1.5" />
          </>
        )}
        {icon === 'site' && (
          <>
            <rect x="1.5" y="4" width="11" height="8" rx="1.5" />
            <path d="M5 4V2.5h4V4" />
          </>
        )}
      </svg>
      <span className="truncate">{children}</span>
    </li>
  )
}

/** 마감 칸 — 2주 안이면 붉은 '지원 서두르기' 알약 + 날짜 + D-day, 아니면 날짜·D-day 또는 상시/채용시. */
function Deadline({ job, left, hurry }: { job: Job; left: number | null; hurry: boolean }) {
  const date = job.deadline_date ? `~${job.deadline_date.slice(5, 7)}/${job.deadline_date.slice(8, 10)}` : null
  return (
    <div className="md:w-[140px] md:shrink-0 flex md:flex-col items-center gap-x-2 gap-y-[2px] text-[13px] leading-[19px] tracking-[-0.16px] text-[#272727] tabular-nums">
      {job.status === 'closed' ? (
        <span className="text-[#999]">마감</span>
      ) : left != null && left >= 0 ? (
        <>
          {hurry && <span className="mb-[4px] h-[25px] px-[10px] rounded-[13px] bg-(--color-accent) text-xs leading-[25px] text-white">지원 서두르기</span>}
          {date && <span>{date}</span>}
          <span className="font-medium text-(--color-accent)">{left === 0 ? '오늘 마감' : `D-${left}`}</span>
        </>
      ) : (
        <span>{job.status_source === 'always_open' ? '상시' : '채용시'}</span>
      )}
    </div>
  )
}

function StarButton({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-label={on ? '관심 공고에서 빼기' : '관심 공고로 담기'}
      aria-pressed={on}
      onClick={(e) => {
        e.stopPropagation()
        e.preventDefault()
        onClick()
      }}
      className="w-6 h-6 grid place-items-center"
    >
      <svg width="24" height="24" viewBox="0 0 24 24" fill={on ? '#f45757' : 'none'} stroke={on ? '#f45757' : '#c4c4c4'} strokeWidth="1.5" strokeLinejoin="round">
        <path d="M12 3.5l2.6 5.3 5.8.8-4.2 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.2-4.1 5.8-.8Z" />
      </svg>
    </button>
  )
}

const STAR_KEY = 'jd-stars'

/** 관심 공고(별) — 이 브라우저에만 남는 편의 기능이다. 저장소가 막혀 있으면 이번 방문 동안만 기억한다. */
function useStars() {
  const [set, setSet] = useState<Set<string>>(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem(STAR_KEY) || '[]') as string[])
    } catch {
      return new Set()
    }
  })
  useEffect(() => {
    try {
      localStorage.setItem(STAR_KEY, JSON.stringify([...set]))
    } catch {
      /* 저장소가 막힌 브라우저 — 기억만 못 할 뿐 동작은 같다 */
    }
  }, [set])
  return {
    has: (k: string) => set.has(k),
    toggle: (k: string) =>
      setSet((s) => {
        const n = new Set(s)
        if (n.has(k)) n.delete(k)
        else n.add(k)
        return n
      }),
  }
}

/** 쪽 번호 — ‹ 1 2 3 4 5 6 7 … 61 ›. 지금 쪽은 검은 동그라미. */
function Pager({ page, totalPages, onChange }: { page: number; totalPages: number; onChange: (p: number) => void }) {
  if (totalPages <= 1) return null
  const go = (p: number) => {
    onChange(Math.max(0, Math.min(totalPages - 1, p)))
    document.querySelector('[data-jobs-top]')?.scrollIntoView({ block: 'start' })
  }
  // 앞 일곱 쪽(지금 쪽이 넘어가면 지금 쪽 둘레 일곱) + 마지막 쪽.
  const from = Math.max(0, Math.min(page - 3, totalPages - 7))
  const nums = Array.from({ length: Math.min(7, totalPages) }, (_, k) => from + k)
  const last = totalPages - 1
  return (
    <nav aria-label="쪽" className="mt-[34px] mb-[90px] flex items-center justify-center gap-[6px] text-sm text-[#666] tabular-nums">
      <PageBtn onClick={() => go(page - 1)} label="이전 쪽">‹</PageBtn>
      {from > 0 && (
        <>
          <PageBtn onClick={() => go(0)}>1</PageBtn>
          <span className="w-[34px] text-center">…</span>
        </>
      )}
      {nums.map((p) => (
        <PageBtn key={p} on={p === page} onClick={() => go(p)}>
          {p + 1}
        </PageBtn>
      ))}
      {nums[nums.length - 1] < last && (
        <>
          <span className="w-[34px] text-center">…</span>
          <PageBtn onClick={() => go(last)}>{last + 1}</PageBtn>
        </>
      )}
      <PageBtn onClick={() => go(page + 1)} label="다음 쪽">›</PageBtn>
    </nav>
  )
}

function PageBtn({ on, onClick, label, children }: { on?: boolean; onClick: () => void; label?: string; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-current={on ? 'page' : undefined}
      className={'w-[34px] h-[34px] rounded-full ' + (on ? 'bg-[#272727] font-bold text-white' : 'hover:text-[#272727]')}
    >
      {children}
    </button>
  )
}

// 회사 이름의 법인 표기 — '(주)펄어비스' → '펄어비스'. 목록에서는 이름만 읽힌다.
function companyText(name: string): string {
  return name.replace(/\(주\)|㈜|주식회사/g, '').trim() || name
}

// 출처 — 보드 이름만('gamejob:dev' → 'gamejob'), 보드가 없으면 사이트 이름.
function sourceText(j: Job): string {
  return j.source_board ? j.source_board.split(/[.:]/)[0] : j.site
}

// 목록에 보일 근무지 — 시도만('서울'). 시군구까지 적으면 메타 칸이 넘친다.
function placeText(job: Job): string {
  const p = job.place ?? placeOf(job)
  return p.region === UNKNOWN_REGION ? '' : p.region
}
