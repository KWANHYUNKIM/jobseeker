import { roleColor } from '../lib/classify'
import { CAREER_BUCKETS, COMPANY_SIZES, type CompanySize } from '../types'

/**
 * 직군·기업규모·경력 칩에 붙는 그림. 지역은 랜드마크라 성격이 달라
 * RegionIcon.tsx 에 따로 있고, 그리는 방식(인라인 SVG, currentColor, 16px)은 같다.
 *
 * **지역과 다른 점.** 랜드마크는 '그 지역다움'을 담으면 됐지만 여기는 축마다 순서나
 * 크기가 있다 — 경력은 낮은 데서 높은 데로 가고, 기업 규모는 작은 데서 큰 데로 간다.
 * 그래서 이 둘은 개별 그림이 아니라 **한 가지 형태를 키워 가며** 그린다. 칩을 하나씩
 * 읽지 않고 줄을 훑는 것만으로 순서가 보여야 하기 때문이다.
 *
 * 직군은 순서가 없으므로 각각 그 일을 상징하는 형태를 쓴다.
 */

// ── 직군 ──────────────────────────────────────────────────────
// classify.ts 의 ROLE_COLORS 와 같은 12종. 여기 없는 이름이 와도 그냥 그림이 없을 뿐이다.
const ROLE_SHAPES: Record<string, React.ReactNode> = {
  // 서버 랙 — 3단, 각 단에 표시등 구멍
  백엔드: (
    <path
      fillRule="evenodd"
      d="M2.6 3.6h18.8v5.2H2.6zM4.6 5.4h1.7v1.6H4.6zM2.6 9.4h18.8v5.2H2.6zM4.6 11.2h1.7v1.6H4.6zM2.6 15.2h18.8v5.2H2.6zM4.6 17h1.7v1.6H4.6z"
    />
  ),
  // 브라우저 창 — 주소줄과 화면
  프론트엔드: (
    <path
      fillRule="evenodd"
      d="M2.2 3.8h19.6v16.4H2.2zM4.2 8.6h15.6v9.6H4.2zM4.4 5.4h1.5v1.5H4.4zM6.8 5.4h1.5v1.5H6.8zM9.2 5.4h1.5v1.5H9.2z"
    />
  ),
  // 창 + 랙 — 위아래 둘 다 만진다
  풀스택: (
    <path
      fillRule="evenodd"
      d="M2.6 2.8h18.8v8.4H2.6zM4.6 6.4h14.8v2.8H4.6zM2.6 13h18.8v3.4H2.6zM4.4 14.1h1.6v1.2H4.4zM2.6 17.4h18.8v3.4H2.6zM4.4 18.5h1.6v1.2H4.4z"
    />
  ),
  // 휴대폰
  모바일: (
    <path
      fillRule="evenodd"
      d="M6.2 2.2h11.6v19.6H6.2zM8 5.4h8v11.4H8zM10.2 18.4h3.6v1.4h-3.6z"
    />
  ),
  // 노드 그래프 — 층 사이를 잇는 연결
  'AI/ML': (
    <>
      <path
        d="M6 6.2 18 12M6 17.8 18 12M6 6.2v11.6"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <circle cx="6" cy="6.2" r="2.8" />
      <circle cx="6" cy="17.8" r="2.8" />
      <circle cx="18" cy="12" r="3.2" />
    </>
  ),
  // 데이터베이스 원통
  데이터: (
    <>
      <ellipse cx="12" cy="5.4" rx="8.2" ry="3.2" />
      <path d="M3.8 8.4c0 1.8 3.7 3.2 8.2 3.2s8.2-1.4 8.2-3.2v3.4c0 1.8-3.7 3.2-8.2 3.2s-8.2-1.4-8.2-3.2z" />
      <path d="M3.8 14.6c0 1.8 3.7 3.2 8.2 3.2s8.2-1.4 8.2-3.2V18c0 1.8-3.7 3.2-8.2 3.2S3.8 19.8 3.8 18z" />
    </>
  ),
  // 무한 루프 — DevOps 가 스스로 쓰는 기호
  'DevOps/인프라': (
    <path
      d="M7.4 8.2a3.8 3.8 0 1 0 0 7.6c3.8 0 5.4-7.6 9.2-7.6a3.8 3.8 0 1 1 0 7.6c-3.8 0-5.4-7.6-9.2-7.6z"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
    />
  ),
  // 마이크로칩 — 다리 달린 사각형
  '펌웨어/임베디드': (
    <>
      <path fillRule="evenodd" d="M6.4 6.4h11.2v11.2H6.4zM9 9h6v6H9z" />
      <path d="M8.4 2.6h1.6v3.2H8.4zM11.2 2.6h1.6v3.2h-1.6zM14 2.6h1.6v3.2H14zM8.4 18.2h1.6v3.2H8.4zM11.2 18.2h1.6v3.2h-1.6zM14 18.2h1.6v3.2H14zM2.6 8.4h3.2V10H2.6zM2.6 11.2h3.2v1.6H2.6zM2.6 14h3.2v1.6H2.6zM18.2 8.4h3.2V10h-3.2zM18.2 11.2h3.2v1.6h-3.2zM18.2 14h3.2v1.6h-3.2z" />
    </>
  ),
  // 방패와 열쇠구멍
  보안: (
    <path
      fillRule="evenodd"
      d="M12 1.8 20.8 5v6.4c0 5.2-3.7 9.1-8.8 10.6-5.1-1.5-8.8-5.4-8.8-10.6V5zM12 8.4a2.1 2.1 0 0 0-1 3.9V15h2v-2.7a2.1 2.1 0 0 0-1-3.9z"
    />
  ),
  // 게임패드
  게임: (
    <path
      fillRule="evenodd"
      d="M6.6 6.4h10.8a5.4 5.4 0 0 1 0 10.8c-1.9 0-2.6-1-3.5-2h-3.8c-.9 1-1.6 2-3.5 2a5.4 5.4 0 0 1 0-10.8zM7.4 9.4v1.7H5.7v1.7h1.7v1.7h1.7v-1.7h1.7v-1.7H9.1V9.4zM15.6 10a1.2 1.2 0 1 0 0 2.4 1.2 1.2 0 0 0 0-2.4zM18 12.4a1.2 1.2 0 1 0 0 2.4 1.2 1.2 0 0 0 0-2.4z"
    />
  ),
  // 돋보기 안의 체크 — 찾아서 통과시킨다
  QA: (
    <>
      <circle cx="10.4" cy="10.4" r="7" fill="none" stroke="currentColor" strokeWidth="2.1" />
      <path d="m15.6 15.6 5.4 5.4" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
      <path d="m7.2 10.6 2.4 2.4 4.2-4.6" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  // 나머지 — 더 있다는 표시
  기타: (
    <>
      <circle cx="5.2" cy="12" r="2.3" />
      <circle cx="12" cy="12" r="2.3" />
      <circle cx="18.8" cy="12" r="2.3" />
    </>
  ),
}

// ── 기업 규모 ─────────────────────────────────────────────────
// 같은 '건물' 형태를 키운다. 동 수와 높이가 함께 늘어 줄을 훑으면 순서가 보인다.
const SIZE_SHAPES: Record<CompanySize, React.ReactNode> = {
  대기업: (
    <path
      fillRule="evenodd"
      d="M2 9h5.6v12.4H2zM3.4 11h2.8v1.6H3.4zM3.4 14.2h2.8v1.6H3.4zM9.2 2.6h5.6v18.8H9.2zM10.6 5h2.8v1.6h-2.8zM10.6 8.2h2.8v1.6h-2.8zM10.6 11.4h2.8V13h-2.8zM16.4 6.6H22v14.8h-5.6zM17.8 9h2.8v1.6h-2.8zM17.8 12.2h2.8v1.6h-2.8z"
    />
  ),
  중견기업: (
    <path
      fillRule="evenodd"
      d="M3.6 11.4h7.2v10H3.6zM5.4 13.6h3.6v1.6H5.4zM12.6 6.6h7.8v14.8h-7.8zM14.4 9h4.2v1.6h-4.2zM14.4 12.2h4.2v1.6h-4.2z"
    />
  ),
  중소기업: (
    <path
      fillRule="evenodd"
      d="M6.6 10.4h10.8v11h-10.8zM8.8 13h2.4v1.8H8.8zM12.8 13h2.4v1.8h-2.4zM8.8 16.6h2.4v1.8H8.8zM12.8 16.6h2.4v1.8h-2.4z"
    />
  ),
}

// ── 경력 ──────────────────────────────────────────────────────
// 5칸 눈금. 채운 칸은 오름차순 계단이고 빈 칸은 바닥에 낮게 남아 '전체 중 어디쯤'을
// 보여준다. 채운 것만 그리면 신입과 정보없음이 둘 다 '거의 빈 그림'이 되어 헷갈린다.
const CAREER_LEVEL: Record<string, number> = {
  '신입/무관': 1,
  '1-2년': 2,
  '3-4년': 3,
  '5-7년': 4,
  '8년+': 5,
  정보없음: 0,
}

function Bars({ level }: { level: number }) {
  const W = 3.2
  const GAP = 1.5
  return (
    <>
      {[0, 1, 2, 3, 4].map((i) => {
        const filled = i < level
        const h = filled ? 4.6 + i * 3.7 : 1.8
        return (
          <rect
            key={i}
            x={1.9 + i * (W + GAP)}
            y={21.4 - h}
            width={W}
            height={h}
            rx="0.7"
            opacity={filled ? 1 : 0.32}
          />
        )
      })}
    </>
  )
}

// ── 색 ────────────────────────────────────────────────────────
// 앱은 밝은 테마 하나뿐이다(index.css: color-scheme light, 패널 #ffffff).
// 그냥 두면 아이콘이 --color-muted(#4a515e)를 물려받아 흰 바탕에서 힘이 없다.
// 축마다 짙은 색을 하나씩 주면 그룹이 눈에 먼저 들어오고, 칩이 선택되면(강조색
// 배경) 색을 떼어 흰 글자와 같이 반전시킨다 — 색을 유지하면 되레 안 보인다.
const SIZE_COLOR = '#3730a3' // indigo-800 — 건물
const CAREER_COLOR = '#166534' // green-800 — 단계가 올라간다

// ── 공통 껍데기 ───────────────────────────────────────────────
function Svg({
  size,
  color,
  children,
}: {
  size: number
  /** 안 주면 currentColor 를 그대로 쓴다(선택된 칩에서 흰색이 되도록). */
  color?: string
  children: React.ReactNode
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
      className="shrink-0"
      style={color ? { color } : undefined}
    >
      {children}
    </svg>
  )
}

/** active 는 '칩이 선택된 상태'. 그때는 색을 빼고 칩 글자색(흰색)을 따른다. */
export function RoleIcon({
  role,
  size = 16,
  active = false,
}: {
  role: string
  size?: number
  active?: boolean
}) {
  const shape = ROLE_SHAPES[role]
  // 직군 색은 classify.ts 가 이미 갖고 있다 — 목록의 직군 태그와 같은 색을 써야
  // 사이드바에서 고른 것과 표에 뜬 것이 같은 것임을 색만 보고도 알 수 있다.
  return shape ? <Svg size={size} color={active ? undefined : roleColor(role)}>{shape}</Svg> : null
}

export function SizeIcon({
  size: name,
  px = 16,
  active = false,
}: {
  size: CompanySize
  px?: number
  active?: boolean
}) {
  const shape = SIZE_SHAPES[name]
  return shape ? <Svg size={px} color={active ? undefined : SIZE_COLOR}>{shape}</Svg> : null
}

export function CareerIcon({
  career,
  size = 16,
  active = false,
}: {
  career: string
  size?: number
  active?: boolean
}) {
  const level = CAREER_LEVEL[career]
  if (level === undefined) return null
  return (
    <Svg size={size} color={active ? undefined : CAREER_COLOR}>
      <Bars level={level} />
    </Svg>
  )
}

// 눈으로 확인할 때 쓰는 목록. 값이 늘면 여기부터 비어 보이므로 누락을 빨리 알아챈다.
export const ICON_COVERAGE = {
  roles: Object.keys(ROLE_SHAPES),
  sizes: COMPANY_SIZES.filter((s) => s in SIZE_SHAPES),
  careers: CAREER_BUCKETS.filter((c) => c in CAREER_LEVEL),
}
