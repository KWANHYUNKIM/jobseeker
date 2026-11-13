import { onLinkClick } from '../../../utils/navigation'
import { paths } from '../../../utils/urls'

// 외주·프리 탭 안의 두 화면. 단가 분석은 목록 위에 얹지 않고 따로 둔다 —
// 목록은 "지금 들어갈 자리"를, 분석은 "몸값이 어떻게 매겨지나"를 보는 곳이라 읽는 방식이 다르다.
export function FreelanceNav({ current }: { current: 'list' | 'rates' }) {
  const item = (key: 'list' | 'rates', to: string, label: string) => (
    <a
      href={to}
      onClick={onLinkClick(to)}
      aria-current={current === key ? 'page' : undefined}
      className={
        'relative shrink-0 px-[22px] pb-[13px] text-[17px] leading-[25px] tracking-[-0.16px] ' +
        (current === key
          ? 'font-bold text-(--color-accent) after:absolute after:inset-x-0 after:-bottom-px after:h-[3px] after:bg-(--color-accent)'
          : 'font-medium text-[#777] hover:text-[#272727]')
      }
    >
      {label}
    </a>
  )
  return (
    <nav aria-label="외주·프리" className="flex border-b border-[#e2e2e2]">
      {item('list', paths.freelance(), '프로젝트 목록')}
      {item('rates', paths.freelanceRates(), '단가 분석')}
    </nav>
  )
}
