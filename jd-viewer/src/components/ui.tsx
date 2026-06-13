// 모든 탭이 공유하는 상태 컴포넌트 — 로딩/에러/빈 화면을 일관되게 표시.
import type { ReactNode } from 'react'

export function Loader({ label = '불러오는 중…' }: { label?: string }) {
  return (
    <div className="flex flex-1 items-center justify-center p-12">
      <div className="flex items-center gap-3 text-sm text-(--color-muted)">
        <span className="jd-spinner" aria-hidden />
        <span>{label}</span>
      </div>
    </div>
  )
}

export function ErrorState({
  title,
  detail,
  hint,
}: {
  title: string
  detail?: string
  hint?: ReactNode
}) {
  return (
    <div className="flex flex-1 items-center justify-center p-12">
      <div className="max-w-md text-center">
        <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-red-500/12 text-red-400 text-xl">
          !
        </div>
        <h2 className="text-base font-semibold text-(--color-text)">{title}</h2>
        {detail && <p className="mt-1 text-sm text-red-400/90 break-words">{detail}</p>}
        {hint && <div className="mt-2 text-xs text-(--color-muted)">{hint}</div>}
      </div>
    </div>
  )
}

export function EmptyState({ title, hint }: { title: string; hint?: ReactNode }) {
  return (
    <div className="flex flex-1 items-center justify-center p-12">
      <div className="max-w-sm text-center">
        <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-(--color-bg) border border-(--color-border) text-(--color-muted) text-lg">
          ∅
        </div>
        <p className="text-sm text-(--color-muted)">{title}</p>
        {hint && <div className="mt-1.5 text-xs text-(--color-muted)/80">{hint}</div>}
      </div>
    </div>
  )
}
