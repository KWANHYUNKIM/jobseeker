import { useGuide, won, type Category, type Guide, type HwData, type Offer, type Part } from '../lib/hardware'

// 조립 목록의 부품 한 줄 아래 — '가장 싸게 지금 바로 사는 곳'.
//
// 다나와 매물은 그 상품 페이지로 바로 간다(오늘 우리가 받은 최저가). 네이버쇼핑·쿠팡은 같은 이름의
// 검색 결과로 이어진다 — 우리가 긁지 않고 링크만 건다. CPU 는 병행(국내 정식 A/S 없음)을 빼고 정품
// 중 최저가다(priceOf 와 같은 기준). 인기 1위(다나와 인기상품순)가 최저가와 다르면 한 줄 더 보인다.
// 메인보드·파워·쿨러·케이스는 급(級) 부품이라 최저가 매물은 '그 급에서 가장 싼 제품'이다.

/** 급 부품 — 최저가 제품을 사기 전에 제품 페이지에서 볼 것 */
const GRADE: Partial<Record<Category, string>> = {
  mainboard: '보드 규격(ATX·M-ATX)과 메모리 슬롯 수',
  psu: '길이와 케이블(모듈러 여부·그래픽카드 전원 단자)',
  cooler: '높이(케이스 한도)와 소켓 지원',
  case: '그래픽카드 길이·쿨러 높이 한도와 기본 팬 수',
}

function pool(p: Part, offers: Offer[]): Offer[] {
  if (p.category !== 'cpu') return offers
  const official = offers.filter((o) => o.name.includes('정품') && !o.name.includes('병행'))
  return official.length ? official : offers
}

function searchName(name: string, guide: Guide | null): string {
  let q = name.replace(/\(÷\d+\)/, '')
  for (const d of guide?.distributors ?? []) for (const a of [d.name, ...(d.aliases ?? [])]) q = q.replace(a, '')
  return q.replace(/\s+/g, ' ').trim()
}

// 판매처 표시 — 각 사이트가 공개한 파비콘(public/brands/). 받은 곳:
//   danawa.png  img.danawa.com/new/danawa_main/v1/img/danawa_favicon.ico (다나와 첫 화면이 거는 아이콘)
//   naver.png   www.naver.com/favicon.ico (네이버쇼핑 전용 아이콘은 작아 알아보기 어려워 네이버 N 을 쓴다)
//   coupang.png image7.coupangcdn.com/image/coupang/favicon/v2/favicon.ico (쿠팡 첫 화면은 봇 차단이라 이미지 CDN)
// 어느 가게로 가는 링크인지 알리는 데만 쓴다.
const SHOP_ICON: Record<string, string> = { 다나와: '/brands/danawa.png', 네이버쇼핑: '/brands/naver.png', 쿠팡: '/brands/coupang.png' }

export function ShopLink({ shop, url, label, strong }: { shop: string; url: string; label?: string; strong?: boolean }) {
  const icon = SHOP_ICON[shop]
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer nofollow"
      title={`${shop}에서 보기`}
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded px-1 py-0.5 hover:bg-(--color-band) ${strong ? 'font-semibold text-(--color-accent)' : 'text-(--color-muted)'}`}
    >
      {icon && <img src={icon} alt="" width={14} height={14} className="w-3.5 h-3.5 rounded-[3px]" loading="lazy" />}
      {label ?? shop}
    </a>
  )
}

function Links({ o, guide }: { o: Offer; guide: Guide | null }) {
  const q = encodeURIComponent(searchName(o.name, guide))
  return (
    <span className="inline-flex flex-wrap items-center gap-x-1">
      <ShopLink shop="다나와" url={o.url} label="다나와에서 사기" strong />
      <ShopLink shop="네이버쇼핑" url={`https://search.shopping.naver.com/search/all?query=${q}`} />
      <ShopLink shop="쿠팡" url={`https://www.coupang.com/np/search?q=${q}`} />
    </span>
  )
}

export function BuyRow({ data, part }: { data: HwData; part: Part }) {
  const guide = useGuide()
  const rec = data.prices[part.id]
  const offers = pool(part, rec?.offers ?? [])
  if (!offers.length) {
    return (
      <div className="col-start-2 col-span-2 text-[11px] text-(--color-faint)">
        오늘 받은 매물이 없다 ·{' '}
        <a
          href={`https://search.danawa.com/dsearch.php?query=${encodeURIComponent(part.price_query?.q ?? part.name)}`}
          target="_blank"
          rel="noreferrer nofollow"
          className="hover:underline"
        >
          다나와에서 찾기 ↗
        </a>
      </div>
    )
  }
  const cheapest = [...offers].sort((a, b) => a.price - b.price)[0]
  const popular = offers.some((o) => o.rank != null) ? [...offers].sort((a, b) => (a.rank ?? 1e9) - (b.rank ?? 1e9) || a.price - b.price)[0] : null
  const kit = /\(÷(\d+)\)/.exec(cheapest.name)
  const qty = part.category === 'ram' ? 2 : 1
  return (
    <div className="col-start-2 col-span-2 text-[11px] flex flex-col gap-0.5" data-nosnippet>
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span className="text-(--color-muted)">최저가</span>
        <span className="truncate max-w-[22rem]" title={cheapest.name}>
          {cheapest.name.replace(/\s*\(÷\d+\)/, '')}
        </span>
        <b className="tabular-nums">{won(kit ? cheapest.price * Number(kit[1]) : cheapest.price)}</b>
        {qty > 1 && !kit && <span className="text-(--color-amber-400)">× {qty}개 담기</span>}
        {kit && <span className="text-(--color-muted)">({kit[1]}장 세트 — 한 번 담으면 된다)</span>}
        <Links o={cheapest} guide={guide} />
      </div>
      {popular && popular.pcode !== cheapest.pcode && (
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className="text-(--color-muted)">인기 1위</span>
          <span className="truncate max-w-[22rem]" title={popular.name}>
            {popular.name.replace(/\s*\(÷\d+\)/, '')}
          </span>
          <span className="tabular-nums">
            {won(popular.price)} <span className="text-(--color-faint)">(+{won(popular.price - cheapest.price)})</span>
          </span>
          <Links o={popular} guide={guide} />
        </div>
      )}
      {GRADE[part.category] && (
        <div className="text-(--color-faint)">
          {part.name} 급에서 가장 싼 제품이다 — 사기 전에 {GRADE[part.category]}을 제품 페이지에서 본다.
        </div>
      )}
    </div>
  )
}
