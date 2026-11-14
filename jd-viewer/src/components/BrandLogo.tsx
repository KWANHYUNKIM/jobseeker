// 헤더 로고 — devgonggo 까치(시안 1번). 지금은 겨울판: 산타 모자를 쓴 까치가 날갯짓하고 단풍잎·눈송이가
// 흩날리는 5초 영상. 철이 지나면 WINTER 를 false 로.
//
// 계속 돌면 시선을 너무 빼앗는다(사용자 지적) — 그래서 **처음 들어왔을 때 한 번만** 재생하고 멈춘다.
// 같은 탭에서 다시 들어오면(새로고침·다른 주소) 재생하지 않고 첫 장면에 서 있다. 영상의 끝과 처음이
// 같은 장면이라 멈춘 모습은 어느 쪽이든 같다. 움직임 줄이기를 켠 사람은 처음부터 멈춰 있다.
//
// 영상은 832×416 에 로고가 가운데 있고 둘레가 비어 있다 — 상자로 잘라 로고 부분만 보인다(CROP).
// 바탕이 아주 옅은 회색(251,253,251)이라 흰 헤더 위에서 상자가 보이지 않게 살짝 밝힌다.

const WINTER = true
const VIDEO = { src: '/brand-logo-winter.mp4', poster: '/brand-logo-winter.jpg', w: 832, h: 416 } // 포스터 = 첫 장면(멈춰 있을 때 보인다)
const CROP = { x: 60, y: 64, w: 712, h: 266 } // 눈송이가 움직이는 범위까지 넉넉히
const HEIGHT = 62 // 헤더(70px) 안의 로고 높이
const SEEN_KEY = 'brand-logo-played'

const reduced = typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/** 이 탭에서 처음이면 true 를 돌려주고 '봤다' 로 적는다. 저장소를 못 쓰면(사생활 모드 등) 재생하지 않는다. */
function firstVisit(): boolean {
  try {
    if (sessionStorage.getItem(SEEN_KEY)) return false
    sessionStorage.setItem(SEEN_KEY, '1')
    return true
  } catch {
    return false
  }
}
// 모듈이 읽힐 때 한 번만 정한다 — 헤더가 다시 그려져도 다시 재생하지 않는다.
const play = WINTER && !reduced && typeof window !== 'undefined' && firstVisit()

export function BrandLogo() {
  if (!WINTER) {
    return <img src="/brand-logo.png" alt="devgonggo" width={174} height={56} style={{ height: HEIGHT, width: 'auto' }} decoding="async" />
  }
  const s = HEIGHT / CROP.h
  return (
    <span role="img" aria-label="devgonggo" className="relative block overflow-hidden" style={{ width: Math.round(CROP.w * s), height: HEIGHT }}>
      <video
        src={VIDEO.src}
        poster={VIDEO.poster}
        autoPlay={play}
        muted
        playsInline
        preload={play ? 'auto' : 'none'}
        aria-hidden
        className="absolute max-w-none pointer-events-none"
        style={{ left: -CROP.x * s, top: -CROP.y * s, width: VIDEO.w * s, height: VIDEO.h * s, filter: 'brightness(1.02)' }}
      />
    </span>
  )
}
