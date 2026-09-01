// 모든 탭이 공유하는 상태 컴포넌트 — 로딩/에러/빈 화면을 일관되게 표시.
import { useEffect, useState, type ReactNode } from 'react'
import { techIconUrl } from '../lib/techIcon'
import { companyLogoUrl, companyMarkColor, companyInitial } from '../lib/companyMark'

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

// ── 키워드 검색 ─────────────────────────────────────────────
// 탭마다 검색을 따로 만들면 생김새도 지우기 버튼 유무도 제각각이 된다. 데이터가
// 달라도 "치면 걸러진다"는 약속은 같아야 해서 입력칸만 여기서 공유한다.
// 무엇을 검색어에 걸지(회사명·제목·기술…)는 탭마다 다르므로 각 뷰가 정한다.
export function SearchInput({
  value,
  onChange,
  placeholder = '키워드 검색',
  className = '',
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  className?: string
}) {
  return (
    <div className={'relative min-w-0 ' + className}>
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className="w-full pl-3 pr-7 py-1.5 text-sm rounded bg-(--color-bg) border border-(--color-border) text-(--color-text) placeholder:text-(--color-muted) focus:border-(--color-accent) focus:outline-none"
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange('')}
          aria-label="검색어 지우기"
          className="absolute right-1.5 top-1/2 -translate-y-1/2 px-1 text-xs text-(--color-muted) hover:text-(--color-accent)"
        >
          ✕
        </button>
      )}
    </div>
  )
}

/** 검색어를 여러 칸에 한 번에 건다. 대소문자·앞뒤 공백은 여기서 흡수한다. */
export function hits(query: string, ...fields: (string | null | undefined)[]): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return fields.some((f) => f && f.toLowerCase().includes(q))
}

// ── 페이지네이션 ─────────────────────────────────────────────
// 목록 탭(잡 리스트·기술 블로그·기술 역설계)이 공유한다. 왼쪽 필터 바는 길어서 스크롤이
// 자연스럽지만, 오른쪽 본문까지 끝없이 스크롤되면 몇 번째를 보고 있는지가 사라진다.
//
// 기본값이 `sticky bottom-0` 인 이유: 페이지 버튼이 목록 끝에만 있으면 그 버튼을 누르려고
// 다시 스크롤해야 한다 — 스크롤을 없애려고 넣은 장치가 스크롤을 요구하게 된다.
export function Pagination({
  page,
  totalPages,
  total,
  pageSize,
  unit = '건',
  sticky = true,
  onChange,
}: {
  page: number
  totalPages: number
  total: number
  pageSize: number
  unit?: string
  sticky?: boolean
  onChange: (p: number) => void
}) {
  // 페이지를 넘겼는데 스크롤이 그대로면 새 페이지의 중간부터 보인다. 스크롤 컨테이너는
  // 탭마다 다르므로(App 의 main, BlogView 의 main, RevengView 의 바깥 div) DOM 에서
  // [data-scroll] 을 거슬러 찾는다 — 각 탭이 자기 스크롤 요소에 그 표시를 달아 둔다.
  const go = (p: number, el: HTMLElement | null) => {
    const next = Math.max(0, Math.min(totalPages - 1, p))
    if (next === page) return
    onChange(next)
    el?.closest<HTMLElement>('[data-scroll]')?.scrollTo({ top: 0 })
  }

  // 페이지 번호 윈도우: 현재 페이지 ±3
  const start = Math.max(0, Math.min(totalPages - 7, page - 3))
  const end = Math.min(totalPages, start + 7)
  const nums = []
  for (let i = start; i < end; i++) nums.push(i)

  return (
    <div
      className={
        'flex flex-wrap items-center justify-between gap-2 px-4 py-3 border-t border-(--color-border) bg-(--color-panel) ' +
        (sticky ? 'sticky bottom-0 z-10' : '')
      }
    >
      <div className="text-xs text-(--color-muted)">
        총 <span className="text-(--color-text)">{total.toLocaleString()}</span>
        {unit} · 페이지 <span className="text-(--color-text)">{page + 1}</span> / {totalPages} (
        {pageSize}개씩)
      </div>
      <div className="flex items-center gap-1">
        <PgBtn onClick={(e) => go(0, e.currentTarget)} disabled={page === 0}>«</PgBtn>
        <PgBtn onClick={(e) => go(page - 1, e.currentTarget)} disabled={page === 0}>‹</PgBtn>
        {nums.map((n) => (
          <PgBtn key={n} onClick={(e) => go(n, e.currentTarget)} active={n === page}>
            {n + 1}
          </PgBtn>
        ))}
        <PgBtn onClick={(e) => go(page + 1, e.currentTarget)} disabled={page >= totalPages - 1}>›</PgBtn>
        <PgBtn onClick={(e) => go(totalPages - 1, e.currentTarget)} disabled={page >= totalPages - 1}>»</PgBtn>
      </div>
    </div>
  )
}

function PgBtn({
  children,
  onClick,
  disabled,
  active,
}: {
  children: ReactNode
  onClick: (e: React.MouseEvent<HTMLButtonElement>) => void
  disabled?: boolean
  active?: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={
        'min-w-[2rem] px-2 py-1 text-xs rounded border transition ' +
        (active
          ? 'bg-(--color-accent) text-(--color-on-accent) border-(--color-accent) font-medium'
          : disabled
            ? 'border-(--color-border) text-(--color-muted)/50 cursor-not-allowed'
            : 'border-(--color-border) text-(--color-text) hover:border-(--color-accent)')
      }
    >
      {children}
    </button>
  )
}

// ── 기술 태그 ────────────────────────────────────────────────
// 목록에서 스택을 훑을 때 글자만 있으면 전부 같은 무게로 보인다. 아는 로고가
// 하나 붙으면 거기서부터 읽게 되므로, 아이콘이 있는 기술만 앞에 작게 붙인다.
// 아이콘이 없거나 못 받아오면 지금까지처럼 글자 태그 그대로다.
/**
 * 기술 로고 하나. 매핑에 없거나 못 받아오면 null 을 그린다 —
 * 부르는 쪽은 아이콘이 있는지 없는지 신경 쓰지 않아도 된다.
 */
export function TechIcon({ tech, size = 12 }: { tech: string; size?: number }) {
  const url = techIconUrl(tech)
  const [failed, setFailed] = useState(false)
  if (!url || failed) return null
  return (
    <img
      src={url}
      alt=""
      width={size}
      height={size}
      loading="lazy"
      onError={() => setFailed(true)}
      style={{ width: size, height: size }}
      className="shrink-0 object-contain"
    />
  )
}

export function TechTag({
  tech,
  size = 12,
  className = 'text-[10px] px-1.5 py-0.5 rounded bg-(--color-bg) border border-(--color-border) text-(--color-muted)',
}: {
  tech: string
  size?: number
  className?: string
}) {
  return (
    <span className={'inline-flex items-center gap-1 ' + className}>
      <TechIcon tech={tech} size={size} />
      {tech}
    </span>
  )
}

// ── 회사 마크 ────────────────────────────────────────────────
// 공고에 나오는 회사는 2천 곳 가까이 되는데 크롤 데이터에 로고가 없다.
// 아는 회사는 로고를, 나머지는 이름에서 뽑은 색의 글자 마크를 쓴다 — 로고가
// 없다고 자리를 비워 두면 목록이 들쭉날쭉해져서 오히려 읽기 어려워진다.
export function CompanyMark({ name, size = 18 }: { name: string; size?: number }) {
  const url = companyLogoUrl(name)
  const [failed, setFailed] = useState(false)
  const box = { width: size, height: size }

  if (url && !failed) {
    return (
      <img
        src={url}
        alt=""
        width={size}
        height={size}
        loading="lazy"
        onError={() => setFailed(true)}
        style={box}
        className="shrink-0 rounded-sm object-contain bg-white"
      />
    )
  }
  return (
    <span
      style={{ ...box, background: companyMarkColor(name), fontSize: size * 0.5 }}
      className="shrink-0 grid place-items-center rounded-sm font-semibold text-white leading-none"
      aria-hidden
    >
      {companyInitial(name)}
    </span>
  )
}
