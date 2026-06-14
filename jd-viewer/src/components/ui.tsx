// 모든 탭이 공유하는 상태 컴포넌트 — 로딩/에러/빈 화면을 일관되게 표시.
import { useEffect, type ReactNode } from 'react'

// 반응형 사이드 패널.
// - 데스크톱(md+): 일반 정적 컬럼으로 표시(기존 레이아웃 유지)
// - 모바일(<md): off-canvas 드로어로 접힘 — 햄버거 버튼으로 열고 배경/ESC 로 닫음
// desktopWidth 는 반드시 리터럴 문자열로 전달(JIT 가 스캔할 수 있도록): 예) "md:w-72"
export function SidePanel({
  side = 'left',
  desktopWidth = 'md:w-72',
  open,
  onClose,
  className = '',
  children,
}: {
  side?: 'left' | 'right'
  desktopWidth?: string
  open: boolean
  onClose: () => void
  className?: string
  children: ReactNode
}) {
  // 모바일 드로어가 열렸을 때만 배경 스크롤 잠금 + ESC 닫기
  useEffect(() => {
    if (!open) return
    if (window.matchMedia('(min-width: 768px)').matches) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [open, onClose])

  const closed = side === 'left' ? '-translate-x-full' : 'translate-x-full'
  const edge = side === 'left' ? 'left-0 border-r' : 'right-0 border-l'

  return (
    <>
      {open && (
        <div
          className="md:hidden fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
          onClick={onClose}
          aria-hidden
        />
      )}
      <aside
        className={
          `fixed inset-y-0 ${edge} z-50 w-[84%] max-w-xs flex flex-col ` +
          `bg-(--color-panel) border-(--color-border) transition-transform duration-200 ` +
          `${open ? 'translate-x-0' : closed} ` +
          `md:static md:z-auto md:translate-x-0 md:max-w-none md:shrink-0 ${desktopWidth} ${className}`
        }
      >
        {children}
      </aside>
    </>
  )
}

// 모바일 전용 상단 바 — 드로어를 여는 햄버거 버튼을 본문 위에 고정 표시.
export function MobileBar({
  onMenu,
  label,
  children,
}: {
  onMenu: () => void
  label: string
  children?: ReactNode
}) {
  return (
    <div className="md:hidden sticky top-0 z-20 flex items-center gap-2 px-3 py-2 border-b border-(--color-border) bg-(--color-panel)/95 backdrop-blur supports-[backdrop-filter]:bg-(--color-panel)/80">
      <button
        onClick={onMenu}
        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded border border-(--color-border) text-sm text-(--color-text) hover:border-(--color-accent)"
      >
        <span className="text-base leading-none">☰</span>
        {label}
      </button>
      {children}
    </div>
  )
}

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
