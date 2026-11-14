import { useEffect, useRef, useState } from 'react'
import { CompanyMark } from '../../../components/ui'
import { onLinkClick } from '../../../utils/navigation'
import { paths } from '../../../utils/urls'
import { fetchHomeCompany, type HomeCompanyDetail } from '../api'
import { careerRange, SIZE_SHORT } from '../utils'
import { JobLine } from './JobLine'

const FIRST = 10 // 처음 펼칠 때 보이는 공고 수 — 나머지는 '더 보기'

/**
 * 카드 아래로 펼치는 칸 — 고른 회사가 지금 구하는 IT 공고 전부.
 *
 * 예전에는 오른쪽에 패널을 띄웠다. 화면 오른쪽을 덮고 목록이 옆으로 밀려서, 카드를 누른 자리에서
 * 바로 이어 보도록 바꿨다. 부르는 쪽이 카드 그리드 안에 `col-span-full` 로 이 칸을 누른 카드 바로
 * 뒤에 꽂고 그리드를 `grid-flow-dense` 로 두면, 같은 줄의 나머지 카드는 제자리를 지키고 이 칸이
 * 그 줄 아래로 들어간다.
 */
export function CompanyPanel({ slug, onClose }: { slug: string; onClose: () => void }) {
  const [d, setD] = useState<HomeCompanyDetail | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [bucket, setBucket] = useState<string>('')
  const [all, setAll] = useState(false)
  const box = useRef<HTMLElement>(null)

  useEffect(() => {
    // 회사가 바뀌면 부르는 쪽이 key 로 칸을 새로 띄운다 — 여기서 상태를 비울 일이 없다.
    const ctl = new AbortController()
    fetchHomeCompany(slug, { signal: ctl.signal })
      .then(setD)
      .catch((e: Error) => e.name !== 'AbortError' && setErr(e.message))
    return () => ctl.abort()
  }, [slug])

  useEffect(() => {
    // 펼친 칸이 화면 밖이면 보이는 데까지만 굴린다(이미 보이면 그대로).
    box.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const c = d?.company
  const jobs = d ? (bucket ? d.jobs.filter((j) => j.career_bucket === bucket) : d.jobs) : []
  const shown = all ? jobs : jobs.slice(0, FIRST)
  const listTo = c ? `/jobs?q=${encodeURIComponent(c.name)}` : '/jobs'

  return (
    <section
      ref={box}
      aria-label={c ? `${c.name} 공고` : '회사 공고'}
      className="home-unfold col-span-full scroll-mt-20 rounded-[22px] border-2 border-[#272727] bg-white px-5 sm:px-7 pt-6 pb-5"
    >
      <div className="flex items-start gap-4">
        <span className="grid place-items-center w-14 h-14 shrink-0 rounded-xl border border-[#e2e8ec] bg-white overflow-hidden">
          {c ? <CompanyMark name={c.name} logo={c.logo} size={40} /> : null}
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="text-[20px] font-bold leading-7 tracking-[-0.2px] text-[#272727] truncate">{c?.name ?? (err ? '불러오지 못함' : '…')}</h3>
          {c && (
            <div className="mt-1.5 flex flex-wrap gap-1 text-[12px]">
              <Tag>{SIZE_SHORT[c.size] ?? c.size}</Tag>
              {c.industry !== '기타' && <Tag>{c.industry}</Tag>}
              <Tag strong>IT 공고 {c.active}건</Tag>
              {careerRange(c.career_from, c.career_to) && <Tag>{careerRange(c.career_from, c.career_to)}</Tag>}
            </div>
          )}
        </div>
        <div className="shrink-0 flex items-center gap-2">
          {c && (
            <a
              href={paths.company(slug)}
              onClick={onLinkClick(paths.company(slug))}
              className="hidden sm:inline-flex items-center h-8 px-3.5 rounded-2xl border border-[#d8d8d8] text-[13px] text-[#474747] hover:border-[#272727]"
            >
              회사 정보
            </a>
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label="접기"
            className="inline-flex items-center gap-1 h-8 px-3 rounded-2xl text-[13px] text-[#666] hover:bg-[#f4f4f4]"
          >
            접기
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden>
              <path d="M1.5 6.5 5 3l3.5 3.5" />
            </svg>
          </button>
        </div>
      </div>

      {d && d.careers.length > 1 && (
        <div className="mt-4 flex gap-1.5 overflow-x-auto no-scrollbar">
          <Chip on={!bucket} onClick={() => setBucket('')}>
            전체 {d.jobs.length}
          </Chip>
          {d.careers.map((x) => (
            <Chip key={x.bucket} on={bucket === x.bucket} onClick={() => setBucket(x.bucket)}>
              {x.bucket === '신입/무관' ? '신입' : x.bucket === '정보없음' ? '경력 미표기' : x.bucket} {x.n}
            </Chip>
          ))}
        </div>
      )}

      <div className="mt-3 border-t border-[#e2e2e2] pt-2">
        {err && (
          <p className="p-3 text-sm leading-relaxed text-[#666]">
            이 회사 공고 목록을 지금 불러올 수 없어요(뷰어 API 응답 없음). 아래 링크의 잡 리스트에서 같은 회사 공고를 볼 수 있어요.
          </p>
        )}
        {!d && !err && <p className="p-3 text-sm text-[#999]">불러오는 중…</p>}
        <div className="grid md:grid-cols-2 gap-x-4">
          {shown.map((j) => (
            <JobLine key={j.site + j.pid} j={j} showCompany={false} />
          ))}
        </div>
      </div>

      {(c || err) && (
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-[#f1f3f5] pt-3">
          {jobs.length > FIRST ? (
            <button type="button" onClick={() => setAll((v) => !v)} className="text-[13px] font-medium text-[#272727] hover:text-(--color-accent)">
              {all ? '처음 10건만 보기' : `공고 ${jobs.length - FIRST}건 더 보기`}
            </button>
          ) : (
            <span />
          )}
          <a href={listTo} onClick={onLinkClick(listTo)} className="text-[13px] text-(--color-accent) hover:underline">
            잡 리스트에서 이 회사만 보기 ›
          </a>
        </div>
      )}
    </section>
  )
}

function Tag({ children, strong }: { children: React.ReactNode; strong?: boolean }) {
  return (
    <span className={'px-1.5 py-0.5 rounded-md ' + (strong ? 'bg-(--color-accent-weak) text-(--color-accent-deep) font-semibold' : 'bg-[#f4f4f4] text-[#666]')}>
      {children}
    </span>
  )
}

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        'shrink-0 h-8 px-3.5 rounded-2xl text-[13px] border transition ' +
        (on ? 'border-[#272727] bg-[#272727] text-white' : 'border-[#d8d8d8] text-[#474747] hover:border-[#272727]')
      }
    >
      {children}
    </button>
  )
}
