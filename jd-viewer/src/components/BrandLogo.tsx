// 헤더 로고 — devgonggo 까치(시안 1번). 지금은 겨울판: 산타 모자를 쓴 까치가 날갯짓하고 단풍잎·눈송이가
// 흩날리는 5초 반복 영상(끝과 처음이 같은 장면이라 끊김 없이 돈다). 철이 지나면 WINTER 를 false 로.
//
// 영상은 832×416 에 로고가 가운데 있고 둘레가 비어 있다 — 상자로 잘라 로고 부분만 보인다(CROP).
// 바탕이 아주 옅은 회색(251,253,251)이라 흰 헤더 위에서 상자가 보이지 않게 살짝 밝힌다.
// 움직임 줄이기를 켠 사람에게는 멈춘 그림(brand-logo.png)을 보인다.

const WINTER = true
const VIDEO = { src: '/brand-logo-winter.mp4', w: 832, h: 416 }
const CROP = { x: 60, y: 64, w: 712, h: 266 } // 눈송이가 움직이는 범위까지 넉넉히
const HEIGHT = 62 // 헤더(70px) 안의 로고 높이

const still = typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

export function BrandLogo() {
  if (!WINTER || still) {
    return <img src="/brand-logo.png" alt="devgonggo" width={174} height={56} style={{ height: HEIGHT, width: 'auto' }} decoding="async" />
  }
  const s = HEIGHT / CROP.h
  return (
    <span role="img" aria-label="devgonggo" className="relative block overflow-hidden" style={{ width: Math.round(CROP.w * s), height: HEIGHT }}>
      <video
        src={VIDEO.src}
        autoPlay
        muted
        loop
        playsInline
        aria-hidden
        className="absolute max-w-none pointer-events-none"
        style={{ left: -CROP.x * s, top: -CROP.y * s, width: VIDEO.w * s, height: VIDEO.h * s, filter: 'brightness(1.02)' }}
      />
    </span>
  )
}
