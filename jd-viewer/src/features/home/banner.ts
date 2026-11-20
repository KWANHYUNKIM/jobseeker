/** 메인 배너(HeroBanner)와 구역 TOP 50 머리(TopBoard)가 같이 쓴다. 장마다 배경 그림과 글자색 — 그림은 오른쪽에 그려져 있고 왼쪽은 글자 자리로 비어 있다(1440×432). */
export const BANNER_ART: Record<string, { img: string; fg: string }> = {
  all: { img: '/home/banner/all.jpg', fg: '#fff' },
  entry: { img: '/home/banner/entry.jpg', fg: '#0b3b2c' },
  experienced: { img: '/home/banner/experienced.jpg', fg: '#fff' },
  intern: { img: '/home/banner/intern.jpg', fg: '#fff' },
  midsmall: { img: '/home/banner/midsmall.jpg', fg: '#fff' },
  overseas: { img: '/home/banner/overseas.jpg', fg: '#fff' },
}
