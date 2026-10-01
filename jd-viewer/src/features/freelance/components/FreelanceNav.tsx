import { onLinkClick } from '../../../utils/navigation'
import { paths } from '../../../utils/urls'

// 외주·프리 탭 안의 두 화면. 단가 분석은 목록 위에 얹지 않고 따로 둔다 —
// 목록은 "지금 들어갈 자리"를, 분석은 "몸값이 어떻게 매겨지나"를 보는 곳이라 읽는 방식이 다르다.
export function FreelanceNav({ current }: { current: 'list' | 'rates' }) {
  const item = (key: 'list' | 'rates', to: string, label: string) => (
    <a
      href={to}
      onClick={onLinkClick(to)}
      className={`px-3 py-1.5 text-sm rounded-md transition ${
        current === key
          ? 'bg-(--color-accent)/12 text-(--color-accent) font-semibold'
          : 'text-(--color-muted) hover:text-(--color-text)'
      }`}
    >
      {label}
    </a>
  )
  return (
    <div className="flex items-center gap-1 px-4 pt-2 pb-1 border-b border-(--color-border) bg-(--color-panel)">
      {item('list', paths.freelance(), '프로젝트 목록')}
      {item('rates', paths.freelanceRates(), '단가 분석')}
    </div>
  )
}
