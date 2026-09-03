import { OVERSEAS, UNKNOWN_REGION } from '../lib/region'

/**
 * 지역 칩 앞에 붙는 랜드마크 아이콘.
 *
 * **왜 인라인 SVG 인가.** 사진이나 외부 아이콘 URL 을 쓰면 세 가지가 따라온다 —
 * 19개 지역치를 어디선가 받아와야 하고(오프라인·사내망에서 깨진다), 랜드마크
 * 사진에는 저작권이 있고, 칩 하나에 14px 짜리 요청이 19개 붙는다. 그래서 각
 * 지역의 실루엣을 직접 그려 코드에 넣는다. 색은 currentColor 라 칩이 선택되면
 * 같이 반전된다.
 *
 * **14px 라는 제약.** 이 크기에서 살아남는 건 윤곽뿐이다. 세부를 넣으면 뭉개져서
 * 오히려 지저분해지므로, 각 지역을 알아볼 수 있는 가장 단순한 형태 하나만 남겼다
 * (첨성대의 병 모양, 광안대교의 현수선, 도담삼봉의 봉우리 셋처럼).
 */

const SHAPES: Record<string, React.ReactNode> = {
  // 63빌딩 — 위로 갈수록 좁아지는 판상형에 비스듬한 옥상
  서울: (
    <>
      <path d="M8 20.5V7.4l8-3.4v16.5z" />
      <path d="M4.5 20.5h15V22h-15z" />
    </>
  ),
  // 수원화성 — 여장(톱니)이 얹힌 성벽과 홍예문. 지붕만 그렸더니 그냥 집으로
  // 읽혀서, 성곽의 톱니를 살렸다.
  경기: (
    <>
      <path d="M2.4 6.6h2.9v3.4H2.4zM6.5 6.6h2.9v3.4H6.5zM10.6 6.6h2.9v3.4h-2.9zM14.7 6.6h2.9v3.4h-2.9zM18.8 6.6h2.8v3.4h-2.8z" />
      <path d="M2.4 10.4h19.2v2.1H2.4z" />
      <path d="M4 12.9h16v8.5h-5.1v-3.8a2.9 2.9 0 0 0-5.8 0v3.8H4z" />
    </>
  ),
  // 인천공항
  인천: (
    <path d="M21.5 13.6 13.6 12.3V6.4a1.6 1.6 0 0 0-3.2 0v5.9L2.5 13.6v1.9l7.9-.9v3.3l-2.3 1.3V20.6l4-.8 4 .8v-1.4l-2.3-1.3v-3.3l7.7.9z" />
  ),
  // 광안대교 — 주탑 둘과 현수선
  부산: (
    <>
      <path d="M5 4.5h1.7v14H5zM17.3 4.5H19v14h-1.7z" />
      <path
        d="M5.9 5.6c2.4 6.4 9.8 6.4 12.2 0"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path d="M1.5 13.2h21v1.8h-21z" />
    </>
  ),
  // 83타워 — 전망대가 부푼 탑
  대구: (
    <>
      <path d="M11.6 2.6h.8v3.2h-.8z" />
      <ellipse cx="12" cy="8.6" rx="4.2" ry="2.7" />
      <path d="M10.9 10.8h2.2v10.7h-2.2z" />
      <path d="M7.5 21.5h9V23h-9z" />
    </>
  ),
  // 무등산 서석대 — 평평한 정상 위에 선 주상절리 돌기둥. 강원(뾰족한 연봉)과
  // 헷갈리지 않도록 봉우리를 깎고 기둥을 굵게 세웠다.
  광주: (
    <>
      <path d="M0.8 21.2 7.4 12.2h9.2l6.6 9z" />
      <path d="M7.8 5.4h2v6.6h-2zM10.9 3.8h2.2v8.2h-2.2zM14.2 5.8h2v6.2h-2z" />
    </>
  ),
  // 한빛탑 — 가늘어지는 첨탑과 전망 링
  대전: (
    <>
      <path d="M10.5 21.4 11.5 2.6h1l1 18.8z" />
      <path d="M7.6 8.2h8.8v2.8H7.6z" />
      <path d="M5.8 21.4h12.4V23H5.8z" />
    </>
  ),
  // 조선소 골리앗 크레인
  울산: (
    <>
      <path d="M2 5.6h20v2.3H2z" />
      <path d="M4.4 8h2L4.2 21.4h-2zM17.6 8h2l2.2 13.4h-2z" />
      <path d="M11.6 8h.9v5.4h-.9z" />
      <path d="M10.2 13.2h3.7v2.6h-3.7z" />
    </>
  ),
  // 정부세종청사 — 길게 늘어선 물결 지붕. 이 건물의 유일한 특징이 그 곡선이라
  // 물결을 세게 줬다(약하게 그리면 그냥 막대가 된다).
  세종: (
    <path d="M1.2 21.4v-7.2c2.4-3.4 4.8 1.8 7.2-1.4s4.8-3.6 7.2-.8 4.6 1.2 6.2-1.2v10.6z" />
  ),
  // 설악산 — 날카로운 봉우리
  강원: (
    <path d="M0.8 21.2 7.4 9.4l3.2 5.1 3-4.7 3.1 5 1.7-2.6 4.8 9z" />
  ),
  // 도담삼봉 — 물 위의 세 봉우리
  충북: (
    <>
      <path d="M3.2 16.4 6.1 9.8l2.9 6.6zM9.4 16.4 13.4 6l4 10.4zM16.6 16.4l2.5-5.3 2.6 5.3z" />
      <path d="M1.5 18.2h21v1.5h-21zM4 21h16v1.4H4z" />
    </>
  ),
  // 정림사지 오층석탑
  충남: (
    <>
      <path d="M11.6 2.2h.8v2.4h-.8z" />
      <path d="M8.4 5h7.2v1.5H8.4zM7.8 8h8.4v1.5H7.8zM7.2 11h9.6v1.5H7.2zM6.6 14h10.8v1.5H6.6zM6 17h12v1.5H6z" />
      <path d="M4.6 20h14.8v1.6H4.6z" />
    </>
  ),
  // 전주 한옥 — 처마가 들린 지붕
  전북: (
    <>
      <path d="M1.6 12.6c3.4-4.6 6.4-6.8 10.4-6.8s7 2.2 10.4 6.8c-2.4-1.4-5.6-2.2-10.4-2.2s-8 .8-10.4 2.2z" />
      <path d="M4.6 14h1.8v7.4H4.6zM17.6 14h1.8v7.4h-1.8z" />
      <path d="M3.2 21.4h17.6V23H3.2z" />
    </>
  ),
  // 등대 — 남해의 밤바다
  전남: (
    <>
      <path d="M9.4 9.6h5.2l1.6 11.8H7.8z" />
      <path d="M9.8 6.6h4.4v2.2H9.8zM11.4 3.6h1.2v2.4h-1.2z" />
      <path d="M2.2 6.2 7.6 8l-.5 1.8-5.4-1.8zM21.8 6.2 16.4 8l.5 1.8 5.4-1.8z" />
      <path d="M1.6 21.4h20.8V23H1.6z" />
    </>
  ),
  // 첨성대 — 병 모양 실루엣
  경북: (
    <>
      {/* 창은 배경색으로 덮지 않고 evenodd 로 뚫는다 — 칩이 선택되면 배경이
          강조색으로 바뀌므로, 덮어 두면 그 자리만 다른 색으로 남는다. */}
      <path
        fillRule="evenodd"
        d="M8.2 20.6c-1.2-6.6.6-16 3.8-16s5 9.4 3.8 16zM10.9 10.4h2.2v2.4h-2.2z"
      />
      <path d="M6.6 20.6h10.8v1.8H6.6z" />
    </>
  ),
  // 거북선
  경남: (
    <>
      <path d="M2 14.8h20c-1.2 3.4-4.4 5-10 5s-8.8-1.6-10-5z" />
      <path d="M5.6 14.4a6.4 4.6 0 0 1 12.8 0z" />
      <path d="M7.6 8.6h1v1.8h-1zM11.5 7.8h1v2.2h-1zM15.4 8.6h1v1.8h-1z" />
      <path d="M1.2 12.4h2.6v1.6H1.2z" />
    </>
  ),
  // 돌하르방
  제주: (
    <>
      <path d="M7.4 6.2c0-1.4 2-2.4 4.6-2.4s4.6 1 4.6 2.4v1.2H7.4z" />
      <path
        fillRule="evenodd"
        d="M8.4 8.6h7.2v6.2a3.6 3.6 0 0 1-7.2 0zM10 10.4h1.3v1.4H10zM12.7 10.4H14v1.4h-1.3z"
      />
      <path d="M8.8 16.4h6.4l1 5H7.8z" />
    </>
  ),
  // 해외·원격 — 지구본
  [OVERSEAS]: (
    <>
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="1.7" />
      <ellipse cx="12" cy="12" rx="4" ry="9" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <path d="M3.4 12h17.2" fill="none" stroke="currentColor" strokeWidth="1.4" />
    </>
  ),
  // 정보없음 — 자리를 못 찾은 핀
  [UNKNOWN_REGION]: (
    <>
      <path
        d="M12 2.8c-3.5 0-6.3 2.7-6.3 6.1 0 4.5 6.3 12.3 6.3 12.3s6.3-7.8 6.3-12.3c0-3.4-2.8-6.1-6.3-6.1z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeDasharray="3 2.2"
      />
      <circle cx="12" cy="8.9" r="1.8" />
    </>
  ),
}

// 땅·돌·건물의 색. 밝은 배경에서 읽히고 강조색(teal)과 겹치지 않는 따뜻한 계열.
const REGION_COLOR = '#92400e' // amber-800

/** active 는 '칩이 선택된 상태'. 그때는 색을 빼고 칩 글자색(흰색)을 따른다. */
export function RegionIcon({
  region,
  size = 16,
  active = false,
}: {
  region: string
  size?: number
  active?: boolean
}) {
  const shape = SHAPES[region]
  if (!shape) return null
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
      className="shrink-0"
      style={active ? undefined : { color: REGION_COLOR }}
    >
      {shape}
    </svg>
  )
}
