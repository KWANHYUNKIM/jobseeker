// 용도 고르기 버튼의 그림. 외부 아이콘 묶음 없이 24×24 선 그림으로 직접 그렸다.
// 게임 셋은 같은 모니터에 해상도 글자만 바꿔 — 무엇이 다른지가 그림에서 바로 보이게.

const RES_TEXT: Record<string, string> = { 'game-fhd': 'FHD', 'game-qhd': 'QHD', 'game-4k': '4K' }

export function HardwareUseIcon({ useKey, className = '' }: { useKey: string; className?: string }) {
  const common = {
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.6,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    className,
    'aria-hidden': true,
  }
  const res = RES_TEXT[useKey]
  if (res)
    return (
      <svg {...common}>
        <rect x="2.5" y="3.5" width="19" height="13" rx="1.5" />
        <path d="M9 20.5h6M12 16.5v4" />
        <text
          x="12"
          y="12.4"
          textAnchor="middle"
          fontSize={res.length > 2 ? 5.6 : 6.4}
          fontWeight={700}
          fill="currentColor"
          stroke="none"
          fontFamily="system-ui, sans-serif"
        >
          {res}
        </text>
      </svg>
    )
  switch (useKey) {
    case 'office': // 문서
      return (
        <svg {...common}>
          <path d="M14 2.5H6.5a1.5 1.5 0 0 0-1.5 1.5v16a1.5 1.5 0 0 0 1.5 1.5h11a1.5 1.5 0 0 0 1.5-1.5V7.5z" />
          <path d="M14 2.5v5h5M8.5 12h7M8.5 15h7M8.5 18h4" />
        </svg>
      )
    case 'dev': // 터미널 창 안의 코드
      return (
        <svg {...common}>
          <rect x="2.5" y="4" width="19" height="16" rx="1.5" />
          <path d="M2.5 8h19M9 12l-2.5 2.5L9 17M15 12l2.5 2.5L15 17M12.8 11.5l-1.6 6" />
        </svg>
      )
    case 'llm': // 칩 위의 반짝임
      return (
        <svg {...common}>
          <rect x="5.5" y="5.5" width="13" height="13" rx="1.5" />
          <path d="M9 2.5v3M15 2.5v3M9 18.5v3M15 18.5v3M2.5 9h3M2.5 15h3M18.5 9h3M18.5 15h3" />
          <path d="M12 8.5l1 2.5 2.5 1-2.5 1-1 2.5-1-2.5-2.5-1 2.5-1z" />
        </svg>
      )
    case 'video': // 클래퍼보드
      return (
        <svg {...common}>
          <rect x="3" y="9" width="18" height="11.5" rx="1.5" />
          <path d="M3 9l1.2-4.2a1 1 0 0 1 1.2-.7l14.2 3.9" />
          <path d="M8.2 5.2L7 9M13 6.5L11.8 9M17.8 7.8L17 9M10 12.5v5l4.5-2.5z" />
        </svg>
      )
    default: // 모르는 용도 — 본체
      return (
        <svg {...common}>
          <rect x="6" y="2.5" width="12" height="19" rx="1.5" />
          <path d="M9 6.5h6M9 9.5h6" />
          <circle cx="12" cy="16" r="1.5" />
        </svg>
      )
  }
}
