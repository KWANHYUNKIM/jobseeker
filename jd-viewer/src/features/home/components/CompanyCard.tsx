import type { ReactNode } from 'react'
import { CompanyMark } from '../../../components/ui'
import { onLinkClick } from '../../../utils/navigation'
import { ddayLabel, ddayUrgent } from '../utils'

/** 칸 순서대로 돌려 쓰는 머리 기호 — 캐치형 카드의 '💼 이번 주 +63 · 금융' 칩. */
export const PICK_ICONS = ['💼', '🔥', '📌', '👀']

/**
 * 캐치형 회사 카드(308×242) — 로고, 오른쪽 위 D-day, 회색 칩, 회사 이름, 대표 공고 제목 두 줄.
 * `onOpen` 이면 단추(회사 패널을 연다), `href` 면 공고로 가는 링크다.
 */
export function PickCard({
  name,
  logo,
  dday,
  chip,
  title,
  active,
  onOpen,
  href,
}: {
  name: string
  logo: string | null
  dday: number | null
  chip: ReactNode
  title: string
  active?: boolean
  onOpen?: () => void
  href?: string
}) {
  const body = (
    <>
      <div className="flex items-start justify-between pl-[17px]">
        <span className="grid place-items-center w-[58px] h-[58px]">
          <CompanyMark name={name} logo={logo} size={58} />
        </span>
        <span
          className={
            'mt-[18px] text-base font-medium tracking-[-0.32px] leading-6 tabular-nums ' +
            (ddayUrgent(dday) ? 'text-(--color-accent)' : 'text-[#999]')
          }
        >
          {ddayLabel(dday)}
        </span>
      </div>
      <span className="mt-[27px] self-start max-w-full truncate rounded bg-[#f4f4f4] px-1.5 text-sm leading-[21px] tracking-[-0.14px] text-[#474747]">
        {chip}
      </span>
      <span className="mt-[10px] block truncate text-[19px] font-medium leading-[27px] tracking-[-0.38px] text-[#272727]">{name}</span>
      <span className="mt-px line-clamp-2 text-base leading-[22px] tracking-[-0.32px] text-[#272727]">{title}</span>
    </>
  )
  const cls =
    'home-press flex flex-col text-left h-[242px] rounded-[18px] border bg-white pt-[29px] pl-[21px] pr-[21px] ' +
    'shadow-[8px_8px_1px_rgba(0,0,0,0.1)] hover:border-[#272727] focus-visible:outline-2 focus-visible:outline-(--color-accent) ' +
    (active ? 'border-(--color-accent)' : 'border-[#b7b7b7]')
  if (href) {
    return (
      <a href={href} onClick={onLinkClick(href)} className={cls}>
        {body}
      </a>
    )
  }
  return (
    <button type="button" onClick={onOpen} aria-pressed={active} className={cls}>
      {body}
    </button>
  )
}
