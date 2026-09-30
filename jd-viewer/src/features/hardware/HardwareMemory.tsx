import { offerMatches, priceOf, useGuide, useModels, won, type Build, type Guide, type HwData, type Model, type Offer, type Part } from './hardware'

// 조립 화면 — 메인보드를 고르면 메모리 슬롯이 어떻게 차는지 보인다.
//
// 메인보드 부품은 칩셋 단위(B850)라 슬롯 수는 제품마다 다르다. 규격으로 보통 값을 말하고
// (ATX 4개 · M-ATX 2~4개 · ITX 2개) 사기 전에 제품 사양을 보라고 적는다.
// 최대 용량·채널·꽂은 개수별 속도는 CPU 제조사 공식 사양이다(guide.json memory_platforms).
// 조립 계산은 메모리를 늘 두 장(듀얼 채널)으로 친다(buildTotal).

interface MemoryPlatform {
  socket: string
  mem: string
  channels: number
  max_gb: number
  /** 꽂은 개수("2"·"4") → 공식 최대 속도. null 이면 제조사 표에 없다 */
  speed: Record<string, string | null>
  basis: string
  sources: { title: string; url: string }[]
}

const STICKS = 2

/** 보드 규격 → 보통의 메모리 슬롯 수 */
function slotsOf(forms: string): { min: number; max: number; text: string } {
  const f = forms.toUpperCase()
  const atx = /(^|[^-])ATX/.test(f.replace(/M-ATX|E-ATX/g, ''))
  const matx = f.includes('M-ATX')
  const itx = f.includes('ITX')
  const min = itx ? 2 : matx ? 2 : 4
  const max = atx || matx ? 4 : 2
  const parts = [atx && 'ATX 4개', matx && 'M-ATX 2~4개', itx && 'ITX 2개'].filter(Boolean)
  return { min, max, text: parts.join(' · ') }
}

const mts = (s: string | null | undefined) => Number(/(\d{4})/.exec(s ?? '')?.[1] ?? 0)

/** 제품 스펙의 dimm_slots("4 · DDR5 최대 256GB") → 4 */
const slotCount = (m: Model) => Number(/^(\d+)/.exec(String(m.specs.dimm_slots ?? ''))?.[1] ?? 0) || null

/** 조사한 보드 제품(hw-engine 이 채운 models/<보드 id>.json)으로 오늘 매물의 실제 슬롯 수를 본다 */
function useBoardSlots(data: HwData, mb: Part) {
  const models = useModels(mb.id) ?? []
  const offers = data.prices[mb.id]?.offers ?? []
  const withSlots = models.filter((m) => slotCount(m))
  const priced = (m: Model) => {
    const os = offers.filter((o) => offerMatches(o, m)).sort((a, b) => a.price - b.price)
    return os[0] ?? null
  }
  const cheapestOffer = [...offers].sort((a, b) => a.price - b.price)[0] ?? null
  const cheapestModel = cheapestOffer ? (models.find((m) => offerMatches(cheapestOffer, m)) ?? null) : null
  const four = withSlots
    .filter((m) => slotCount(m) === 4)
    .map((m) => ({ m, o: priced(m) }))
    .filter((x): x is { m: Model; o: Offer } => !!x.o)
    .sort((a, b) => a.o.price - b.o.price)[0]
  const counts = withSlots.reduce<Record<number, number>>((acc, m) => ((acc[slotCount(m)!] = (acc[slotCount(m)!] ?? 0) + 1), acc), {})
  return { models, withSlots, cheapestOffer, cheapestModel, four, counts }
}

export function MemorySlots({ data, build }: { data: HwData; build: Build }) {
  const byId = new Map(data.parts.map((p) => [p.id, p]))
  const mb = build.mainboard ? byId.get(build.mainboard) : undefined
  if (!mb) return null
  return <MemorySlotsFor data={data} build={build} mb={mb} />
}

function MemorySlotsFor({ data, build, mb }: { data: HwData; build: Build; mb: Part }) {
  const guide = useGuide() as (Guide & { memory_platforms?: MemoryPlatform[] }) | null
  const byId = new Map(data.parts.map((p) => [p.id, p]))
  const board = useBoardSlots(data, mb)
  const cpu = build.cpu ? byId.get(build.cpu) : undefined
  const ram = build.ram ? byId.get(build.ram) : undefined
  const socket = String(cpu?.specs.socket ?? mb.specs.socket)
  const plat = guide?.memory_platforms?.find((m) => m.socket === socket)
  // 최저가 보드의 실제 슬롯 수를 알면 그것으로, 모르면 규격으로 짐작한다
  const guess = slotsOf(String(mb.specs.forms ?? 'ATX'))
  const known = board.cheapestModel ? slotCount(board.cheapestModel) : null
  const slots = known ? { min: known, max: known, text: guess.text } : guess
  const per = ram ? Number(ram.specs.capacity_gb) : null
  const total = per ? per * STICKS : null
  const speed = ram ? Number(ram.specs.speed_mts) : null
  const official2 = mts(plat?.speed['2'])
  const four = plat?.speed['4'] ?? null
  // 처음부터 큰 장 두 개 — 같은 종류에서 용량이 두 배인 것
  const bigger: { p: Part; price: number } | null = (() => {
    if (!ram || !per) return null
    const p = data.parts
      .filter((x) => x.category === 'ram' && x.specs.type === ram.specs.type && Number(x.specs.capacity_gb) === per * 2)
      .map((x) => ({ p: x, price: priceOf(x, data.prices) }))
      .filter((x): x is { p: Part; price: number } => x.price != null)
      .sort((a, b) => a.price - b.price)[0]
    return p ?? null
  })()
  const ramPrice = ram ? priceOf(ram, data.prices) : null

  return (
    <section className="rounded-md border border-(--color-border-soft) p-3 text-sm flex flex-col gap-1.5">
      <div className="flex flex-wrap items-baseline gap-2">
        <h3 className="font-semibold">메모리 슬롯 — {mb.name}</h3>
        {plat && (
          <span className="text-[11px] text-(--color-muted)">
            {socket} · {plat.mem} · {plat.channels}채널 · 최대 {plat.max_gb}GB
          </span>
        )}
      </div>

      {/* 슬롯 그림 — 채운 칸과 빈 칸 */}
      <div className="flex items-center gap-2">
        <div className="flex gap-1" aria-label={`슬롯 ${slots.max}개 중 ${ram ? STICKS : 0}개 사용`}>
          {Array.from({ length: slots.max }, (_, i) => {
            const used = !!ram && i < STICKS
            const maybe = i >= slots.min
            return (
              <span
                key={i}
                className={`w-5 h-9 rounded-sm border ${used ? 'bg-(--color-accent) border-(--color-accent)' : maybe ? 'border-dashed border-(--color-border)' : 'border-(--color-border)'}`}
                title={used ? `${per}GB` : maybe ? 'M-ATX 는 없을 수 있다' : '빈 슬롯'}
              />
            )
          })}
        </div>
        <div className="text-xs">
          {ram ? (
            <>
              <b>
                {per}GB × {STICKS}장 = {total}GB
              </b>{' '}
              — 듀얼 채널({STICKS}장)은 가장 빠른 구성이다. 보드 설명서의 권장 슬롯(보통 A2·B2)에 꽂는다.
            </>
          ) : (
            '메모리를 고르면 나온다'
          )}
        </div>
      </div>

      <ul className="text-xs flex flex-col gap-1">
        <li>
          <span className="text-(--color-muted)">슬롯 수: </span>
          {known && board.cheapestModel ? (
            <>
              오늘 최저가 보드 <b>{board.cheapestModel.name}</b> 는 <b>{known}개</b>다(제조사 사양).
            </>
          ) : (
            <>이 칩셋 보드는 {String(mb.specs.forms ?? '')} 로 나온다 — 보통 {guess.text}. </>
          )}{' '}
          {board.withSlots.length > 0 && (
            <span className="text-(--color-muted)">
              조사한 {mb.name} 보드 {board.withSlots.length}종 중{' '}
              {Object.entries(board.counts)
                .sort((a, b) => Number(b[0]) - Number(a[0]))
                .map(([n, c]) => `${n}슬롯 ${c}종`)
                .join(' · ')}
              .
            </span>
          )}
          {!known && ' 같은 칩셋이라도 제품마다 다르니 사기 전에 제품 사양의 DIMM 슬롯 수를 본다.'}
        </li>
        {known === 2 && board.four && (
          <li className="text-(--color-amber-400)">
            <span className="text-(--color-muted)">늘릴 계획이면: </span>
            최저가 보드는 슬롯이 2개라 더 꽂을 자리가 없다. 4슬롯 중 가장 싼 {board.four.m.name}{' '}
            <a href={board.four.o.url} target="_blank" rel="noreferrer nofollow" className="text-(--color-accent) hover:underline">
              {won(board.four.o.price)} ↗
            </a>
            {board.cheapestOffer && ` (+${won(board.four.o.price - board.cheapestOffer.price)})`}.
          </li>
        )}
        {ram && per && total && slots.max > STICKS && (
          <li>
            <span className="text-(--color-muted)">나중에 늘리면: </span>
            빈 슬롯 {slots.max - STICKS}개에 같은 메모리 {slots.max - STICKS}장을 더 꽂아 {per * slots.max}GB
            {ramPrice != null && ` (+${won(ramPrice * (slots.max - STICKS))})`}.{' '}
            {four ? (
              <span className="text-(--color-amber-400)">
                단, 4장이면 공식 속도가 {four} 로 내려간다{speed ? `(지금 ${speed.toLocaleString()} → 약 ${mts(four).toLocaleString()})` : ''}.
              </span>
            ) : (
              <span className="text-(--color-amber-400)">4장 속도는 제조사 표에 없다 — 보통 2장보다 낮아지니 보드의 메모리 지원 목록(QVL)을 본다.</span>
            )}
          </li>
        )}
        {bigger && per && (
          <li>
            <span className="text-(--color-muted)">늘릴 생각이면: </span>
            처음부터 {per * 2}GB × 2장({per * 4}GB)으로 사면 {won(bigger.price * 2)}
            {ramPrice != null && ` (지금보다 +${won((bigger.price - ramPrice) * 2)})`} — 속도를 지키고 슬롯도 남는다.
          </li>
        )}
        {plat && (
          <li>
            <span className="text-(--color-muted)">최대: </span>
            {plat.max_gb}GB{slots.max === 4 ? ` — 4장이면 장당 ${plat.max_gb / 4}GB` : ` — 2장이면 장당 ${plat.max_gb / 2}GB`}
            {slots.max === 2 && ' (슬롯 2개 보드는 여기까지다)'}.
          </li>
        )}
        {ram && speed && official2 > 0 && speed > official2 && (
          <li>
            <span className="text-(--color-muted)">속도: </span>
            CPU 공식 보장은 {plat?.speed['2']}이다. {speed.toLocaleString()} 으로 쓰려면 바이오스에서 {String(ram.specs.profile ?? 'XMP/EXPO')} 프로필을 켠다 — 안 켜면{' '}
            {ram.specs.default_mts ? `${Number(ram.specs.default_mts).toLocaleString()}` : '기본 속도'} 로 돈다.
          </li>
        )}
      </ul>
      {plat && (
        <p className="text-[10px] text-(--color-faint)">
          {plat.basis} ·{' '}
          {plat.sources.map((s) => (
            <a key={s.url} href={s.url} target="_blank" rel="noreferrer" className="hover:underline">
              {s.title}
            </a>
          ))}
        </p>
      )}
    </section>
  )
}
