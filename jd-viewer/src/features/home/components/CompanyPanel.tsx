import { useEffect, useState } from 'react'
import { CompanyMark } from '../../../components/ui'
import { onLinkClick } from '../../../utils/navigation'
import { fetchHomeCompany, type HomeCompanyDetail } from '../api'
import { careerRange, SIZE_SHORT } from '../utils'
import { JobLine } from './JobLine'

/**
 * 오른쪽 패널 — 고른 회사가 지금 구하는 IT 공고 전부. 카드 목록은 그대로 둔 채 옆에 연다
 * (목록을 갈아끼우면 다른 회사로 옮겨 갈 때마다 스크롤이 처음으로 돌아간다).
 */
export function CompanyPanel({ slug, onClose }: { slug: string; onClose: () => void }) {
  const [d, setD] = useState<HomeCompanyDetail | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [bucket, setBucket] = useState<string>('')

  useEffect(() => {
    // 회사가 바뀌면 부르는 쪽이 key 로 패널을 새로 띄운다 — 여기서 상태를 비울 일이 없다.
    const ctl = new AbortController()
    fetchHomeCompany(slug, { signal: ctl.signal })
      .then(setD)
      .catch((e: Error) => e.name !== 'AbortError' && setErr(e.message))
    return () => ctl.abort()
  }, [slug])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const c = d?.company
  const jobs = d ? (bucket ? d.jobs.filter((j) => j.career_bucket === bucket) : d.jobs) : []
  const listTo = c ? `/jobs?q=${encodeURIComponent(c.name)}` : '/jobs'

  return (
    <aside
      className="fixed inset-0 z-40 md:inset-auto md:top-14 md:right-0 md:bottom-0 md:w-[460px] flex flex-col bg-(--color-panel) md:border-l border-(--color-border) shadow-[-12px_0_32px_rgba(0,0,0,0.08)] jd-slide-in"
      aria-label="회사 공고"
    >
      <div className="flex items-start gap-3 p-5 border-b border-(--color-border-soft)">
        <span className="grid place-items-center w-14 h-14 shrink-0 rounded-lg border border-(--color-border-soft) bg-white overflow-hidden">
          {c ? <CompanyMark name={c.name} logo={c.logo} size={40} /> : null}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-bold text-(--color-text) truncate">{c?.name ?? (err ? '불러오지 못함' : '…')}</h2>
          {c && (
            <p className="mt-0.5 text-xs text-(--color-muted)">
              {SIZE_SHORT[c.size] ?? c.size}
              {c.industry !== '기타' && ` · ${c.industry}`} · IT 공고 {c.active}건
              {careerRange(c.career_from, c.career_to) && ` · ${careerRange(c.career_from, c.career_to)}`}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="닫기"
          className="shrink-0 w-8 h-8 grid place-items-center rounded-md text-(--color-muted) hover:bg-(--color-band)"
        >
          ✕
        </button>
      </div>

      {d && d.careers.length > 1 && (
        <div className="flex gap-1.5 px-5 py-3 overflow-x-auto no-scrollbar border-b border-(--color-border-soft)">
          <Chip on={!bucket} onClick={() => setBucket('')}>전체 {d.jobs.length}</Chip>
          {d.careers.map((x) => (
            <Chip key={x.bucket} on={bucket === x.bucket} onClick={() => setBucket(x.bucket)}>
              {x.bucket === '신입/무관' ? '신입' : x.bucket === '정보없음' ? '경력 미표기' : x.bucket} {x.n}
            </Chip>
          ))}
        </div>
      )}

      <div data-scroll className="flex-1 min-h-0 overflow-auto p-2">
        {err && <p className="p-4 text-sm text-(--color-red-400)">{err}</p>}
        {!d && !err && <p className="p-4 text-sm text-(--color-faint)">불러오는 중…</p>}
        {jobs.map((j) => (
          <JobLine key={j.site + j.pid} j={j} showCompany={false} />
        ))}
      </div>

      {c && (
        <div className="p-3 border-t border-(--color-border-soft) text-right">
          <a href={listTo} onClick={onLinkClick(listTo)} className="text-xs text-(--color-accent) hover:underline">
            잡 리스트에서 필터로 보기 →
          </a>
        </div>
      )}
    </aside>
  )
}

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        'shrink-0 px-2.5 py-1 rounded-full text-xs border transition ' +
        (on
          ? 'bg-(--color-text) text-(--color-panel) border-(--color-text)'
          : 'border-(--color-border) text-(--color-muted) hover:border-(--color-text)')
      }
    >
      {children}
    </button>
  )
}
