import { useMemo, useState } from 'react'
import { tierOf, won, type HwData } from '../utils/hardware'
import { analyze, perfOf, perfRanks, PERF_USES, usePrebuilt, valueRanks, type Analysis, type PerfRank, type PerfUse, type Prebuilt } from '../utils/prebuilt'
import { onLinkClick } from '../../../utils/navigation'
import { absUrl, useSeo } from '../../../utils/seo'
import { paths } from '../../../utils/urls'
import { NOINDEX, PriceChart } from './HardwarePrices'
import { TierBadge } from './HardwareView'
import { Loader } from '../../../components/ui'

// 완제품 조립PC — 누가 설계해 파는 조립PC 를 부품으로 뜯어 본다(lib/prebuilt.ts 머리말).
// 목록: 가격·구성·부품값 대비·가성비 순위·예상 fps. 상세: 부품별 값, 잘한 점·아쉬운 점, 가격 추이.
// 성능 우선: 돈보다 성능이 먼저인 일(사업용 렌더·빌드·AI)을 위해 가격을 빼고 용도별 성능으로 줄 세운다.
// 가격이 실리는 화면이라 색인하지 않는다.

type SortKey = 'value' | 'price' | 'premium' | 'fps'

const MODES = [
  ['value', '가성비 우선'],
  ['perf', '성능 우선'],
] as const

export function HardwarePrebuilt({ data, itemKey }: { data: HwData; itemKey: string | null }) {
  const pb = usePrebuilt()
  if (!pb) return <Loader label="완제품 불러오는 중…" />
  if (itemKey) {
    const it = pb.items.find((x) => x.key === itemKey)
    return it ? <Detail data={data} item={it} all={pb.items} /> : <div className="p-8 text-sm text-(--color-muted)">없는 상품입니다: {itemKey}</div>
  }
  return <List data={data} items={pb.items} day={pb.day} />
}

function List({ data, items, day }: { data: HwData; items: Prebuilt[]; day: string | null }) {
  useSeo({ title: '완제품 조립PC 분석', description: '시중 조립PC 를 부품으로 뜯어 부품값·균형·가성비를 봅니다.', robots: NOINDEX, canonical: absUrl(paths.hardwarePrebuilt()) })
  const [sort, setSort] = useState<SortKey>('value')
  const [q, setQ] = useState('')
  const [mode, setMode] = useState<'value' | 'perf'>('value')
  const [use, setUse] = useState<PerfUse>('game-qhd')
  const ranks = useMemo(() => valueRanks(items, data), [items, data])
  const today = useMemo(() => items.filter((it) => it.last_seen === day), [items, day])
  const perf = useMemo(() => perfRanks(today, data, use), [today, data, use])
  const rows = useMemo(() => {
    const xs = items
      .filter((it) => it.last_seen === day && (!q || it.name.toLowerCase().includes(q.toLowerCase())))
      .map((it) => ({ it, a: analyze(it, data), r: ranks.get(it.key) }))
    const inf = (v: number | null | undefined) => v ?? Infinity
    xs.sort((x, y) =>
      sort === 'price' ? x.it.price - y.it.price
      : sort === 'premium' ? inf(x.a.premiumPct) - inf(y.a.premiumPct)
      : sort === 'fps' ? (y.a.qhdFps ?? 0) - (x.a.qhdFps ?? 0)
      : inf(x.r?.rank) - inf(y.r?.rank),
    )
    return xs
  }, [items, data, ranks, sort, q, day])
  const perfRows = useMemo(
    () =>
      today
        .filter((it) => perf.has(it.key) && (!q || it.name.toLowerCase().includes(q.toLowerCase())))
        .map((it) => ({ it, p: perf.get(it.key)! }))
        .sort((x, y) => x.p.rank - y.p.rank),
    [today, perf, q],
  )
  const useDef = PERF_USES.find((u) => u.key === use)!
  const th = (k: SortKey, label: string) => (
    <button onClick={() => setSort(k)} className={sort === k ? 'text-(--color-accent) font-semibold' : 'hover:text-(--color-text)'}>
      {label}
      {sort === k && ' ↓'}
    </button>
  )
  return (
    <div className="max-w-[1500px] mx-auto p-4 flex flex-col gap-4">
      <header className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h1 className="text-lg font-bold">완제품 조립PC 분석</h1>
        <span className="text-xs text-(--color-muted)">
          누가 설계해 파는 조립PC 를 부품으로 뜯어, 부품값 합계·균형·예상 성능으로 가성비를 본다 · {day ?? '—'} 기준 {rows.length}개
        </span>
      </header>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <div className="inline-flex rounded-md border border-(--color-border) overflow-hidden" role="tablist">
          {MODES.map(([k, label]) => (
            <button
              key={k}
              role="tab"
              aria-selected={mode === k}
              onClick={() => setMode(k)}
              className={`px-3 py-1 ${mode === k ? 'bg-(--color-accent) text-(--color-on-accent) font-semibold' : 'bg-(--color-panel) hover:bg-(--color-band)'}`}
            >
              {label}
            </button>
          ))}
        </div>
        {mode === 'perf' &&
          PERF_USES.map((u) => (
            <button
              key={u.key}
              onClick={() => setUse(u.key)}
              className={`px-2.5 py-1 rounded-md ${u.key === use ? 'bg-(--color-text) text-(--color-panel) font-semibold' : 'bg-(--color-band) hover:bg-(--color-border-soft)'}`}
            >
              {u.label}
            </button>
          ))}
      </div>
      {mode === 'perf' && <PerfTop rows={perfRows} useDef={useDef} total={today.length} />}
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="이름·부품으로 찾기 (예: 5070, 9800X3D)" className="border border-(--color-border) rounded px-2 py-1 bg-(--color-panel) w-72" />
        <span className="text-xs text-(--color-muted)">
          {mode === 'value'
            ? '가성비 = 예상 QHD 평균 fps 1 당 가격(낮을수록 좋다) · 원가 = 같은 날 부품 최저가 합계 · 남기는 돈 = 판매가 − 원가'
            : `성능 = ${useDef.plain} · 가격은 줄 세우는 데 쓰지 않는다(같은 성능이면 싼 쪽이 위)`}
        </span>
      </div>
      {mode === 'perf' ? (
        <PerfTable rows={perfRows} data={data} useDef={useDef} />
      ) : (
      <div className="rounded-lg border border-(--color-border) bg-(--color-panel) overflow-x-auto">
        <table className="w-full text-sm min-w-[1200px]" data-nosnippet>
          <thead>
            <tr className="text-[11px] text-(--color-muted) text-left border-b border-(--color-border)">
              <th className="font-normal px-3 py-2">{th('value', '가성비 순위')}</th>
              <th className="font-normal px-3 py-2">상품</th>
              <th className="font-normal px-3 py-2">CPU · 그래픽</th>
              <th className="font-normal px-3 py-2">메모리 · SSD</th>
              <th className="font-normal px-3 py-2 text-right">{th('price', '가격')}</th>
              <th className="font-normal px-3 py-2 text-right">원가(부품값)</th>
              <th className="font-normal px-3 py-2 text-right">{th('premium', '남기는 돈')}</th>
              <th className="font-normal px-3 py-2 text-right">{th('fps', 'QHD 예상')}</th>
              <th className="font-normal px-3 py-2">의견</th>
              <th className="font-normal px-3 py-2">판매처</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ it, a, r }) => (
              <tr key={it.key} className="border-t border-(--color-border-soft) hover:bg-(--color-band)">
                <td className="px-3 py-2 tabular-nums">{r ? <b>{r.rank}</b> : <span className="text-(--color-faint)">—</span>}{r && <span className="text-[10px] text-(--color-faint)"> / {r.of}</span>}</td>
                <td className="px-3 py-2 max-w-80">
                  <a href={paths.hardwarePrebuiltItem(it.key)} onClick={onLinkClick(paths.hardwarePrebuiltItem(it.key))} className="font-medium hover:underline">
                    {it.name}
                  </a>
                  <div className="text-[10px] text-(--color-faint)">{it.source === 'naver' ? `네이버 · ${it.mall ?? ''}` : '다나와'}{it.comp?.purpose && ` · ${it.comp.purpose}`}</div>
                </td>
                <td className="px-3 py-2 text-xs">
                  <PartTag part={a.cpu} text={it.comp?.cpu} data={data} />
                  <PartTag part={a.gpu} text={it.comp?.gpu} data={data} />
                </td>
                <td className="px-3 py-2 text-xs text-(--color-muted)">
                  {it.comp?.ram_gb ? `${it.comp.ram_type ?? ''} ${it.comp.ram_gb}GB` : '—'}
                  <br />
                  {it.comp?.storage_gb ? (it.comp.storage_gb >= 1000 ? `${it.comp.storage_gb / 1000}TB` : `${it.comp.storage_gb}GB`) : '—'}
                </td>
                <td className="px-3 py-2 text-right font-bold tabular-nums">{won(it.price)}</td>
                <td className="px-3 py-2 text-right tabular-nums text-(--color-muted)">{a.sum != null ? won(a.sum) : '—'}</td>
                <td className={`px-3 py-2 text-right tabular-nums ${a.premiumPct == null ? 'text-(--color-faint)' : a.premiumPct >= 25 ? 'text-(--color-red-400)' : a.premiumPct <= 10 ? 'text-(--color-accent) font-semibold' : ''}`}>
                  {a.premium == null ? (
                    '계산 불가'
                  ) : (
                    <>
                      {a.premium >= 0 ? '+' : '−'}
                      {won(Math.abs(a.premium))}
                      <div className="text-[10px] font-normal text-(--color-muted)">
                        마진율 {Math.round(a.marginPct ?? 0)}% · 원가 대비 {(a.premiumPct ?? 0) >= 0 ? '+' : ''}
                        {Math.round(a.premiumPct ?? 0)}%
                      </div>
                    </>
                  )}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{a.qhdFps ?? '—'}</td>
                <td className="px-3 py-2 text-xs text-(--color-muted)">{it.rating ? `★ ${it.rating.avg.toFixed(1)} (${it.rating.count})` : '—'}</td>
                <td className="px-3 py-2 text-xs whitespace-nowrap">
                  <a href={it.url} target="_blank" rel="noreferrer nofollow" className="text-(--color-sky-400) hover:underline">
                    {it.source === 'naver' ? (it.mall ?? '네이버') : '다나와'} ↗
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      )}
      <p className="text-[11px] text-(--color-faint)">
        구성은 상품 페이지의 부품 모델명만 뽑았다. 사용자 의견은 별점·리뷰 수만 싣고 글은 원문에서 본다. 부품값 합계는 같은 날 우리가 받은 부품 최저가로 다시 맞춘 값이고, 표기가 없는 칸(쿨러·SSD 제조사 등)은 가정을 상세에 적었다.
      </p>
    </div>
  )
}

function PartTag({ part, text, data }: { part: ReturnType<typeof analyze>['cpu']; text?: string | null; data: HwData }) {
  if (!text) return <div className="text-(--color-faint)">—</div>
  if (!part) return <div className="text-(--color-amber-400)" title="우리 부품 목록에 아직 없다 — 조사 대기">{text} ?</div>
  const t = tierOf(part, data.categories)
  return (
    <div className="flex items-center gap-1">
      {t && <span className="text-[10px] font-bold text-(--color-accent)">{t.tier}</span>}
      {part.name}
    </div>
  )
}

function Detail({ data, item, all }: { data: HwData; item: Prebuilt; all: Prebuilt[] }) {
  useSeo({ title: `${item.name} 분석`, description: `${item.name} 부품 구성·부품값·가성비 분석`, robots: NOINDEX, canonical: absUrl(paths.hardwarePrebuiltItem(item.key)) })
  const a = analyze(item, data)
  const r = valueRanks(all, data).get(item.key)
  const hist = item.history.map((h) => ({ d: h.d, min: h.price, median: h.price, n: 1 }))
  return (
    <div className="max-w-[1300px] mx-auto p-4 flex flex-col gap-4">
      <a href={paths.hardwarePrebuilt()} onClick={onLinkClick(paths.hardwarePrebuilt())} className="text-xs text-(--color-accent) hover:underline">
        ← 완제품 목록
      </a>
      <header className="flex flex-wrap items-baseline gap-3">
        <h1 className="text-xl font-bold">{item.name}</h1>
        <a href={item.url} target="_blank" rel="noreferrer nofollow" className="text-xs text-(--color-sky-400) hover:underline">
          {item.source === 'naver' ? (item.mall ?? '네이버') : '다나와'} 판매 페이지 ↗{item.rating ? ` · ★ ${item.rating.avg.toFixed(1)} 리뷰 ${item.rating.count}건` : ' · 상품의견은 원문에서'}
        </a>
      </header>
      <div className="grid gap-3 sm:grid-cols-4" data-nosnippet>
        <Stat label="판매가" value={won(item.price)} sub={item.offer_count ? `판매처 ${item.offer_count}곳` : undefined} />
        <Stat label="원가(부품값 합계)" value={a.sum != null ? won(a.sum) : '계산 불가'} sub={a.unknown.length ? '목록에 없는 부품 제외' : '같은 날 부품 최저가 기준'} />
        <Stat
          label="남기는 돈"
          value={a.premium != null ? `${a.premium >= 0 ? '+' : '−'}${won(Math.abs(a.premium))}` : '—'}
          sub={a.premium != null ? `마진율 ${Math.round(a.marginPct ?? 0)}% · 원가 대비 ${(a.premiumPct ?? 0) >= 0 ? '+' : ''}${Math.round(a.premiumPct ?? 0)}%` : undefined}
        />
        <Stat label="가성비 순위" value={r ? `${r.rank} / ${r.of}` : '—'} sub={r ? `QHD 예상 ${a.qhdFps}fps · fps 당 ${Math.round(r.wonPerFps).toLocaleString()}원` : undefined} />
      </div>
      <PerfPanel data={data} item={item} all={all} />
      {a.sum != null && <PriceSplit item={item} a={a} />}
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4">
          <h2 className="text-sm font-semibold mb-2">왜 이런 값인가</h2>
          {a.errors.length > 0 && (
            <div className="mb-2 text-sm text-(--color-red-400)">
              {a.errors.map((e) => (
                <div key={e}>✕ 표기된 구성끼리 호환 안 됨 — {e}</div>
              ))}
            </div>
          )}
          <ul className="flex flex-col gap-1.5 text-sm">
            {a.good.map((g) => (
              <li key={g}>
                <span className="text-(--color-accent) font-bold mr-1">＋</span>
                {g}
              </li>
            ))}
            {a.bad.map((b) => (
              <li key={b}>
                <span className="text-(--color-red-400) font-bold mr-1">－</span>
                {b}
              </li>
            ))}
          </ul>
          <p className="text-[11px] text-(--color-faint) mt-3">잘한 점·아쉬운 점은 부품값·급·전력·용량으로 계산한 규칙이다. 설계자의 의도나 사용 후기는 원문에서 확인한다.</p>
        </section>
        <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4" data-nosnippet>
          <h2 className="text-sm font-semibold mb-2">부품으로 뜯어 보면</h2>
          <table className="w-full text-sm">
            <tbody>
              {a.lines.map((l) => {
                const t = l.part ? tierOf(l.part, data.categories) : null
                return (
                  <tr key={l.label} className="border-t border-(--color-border-soft)">
                    <td className="py-1.5 text-xs text-(--color-muted) w-20">{l.label}</td>
                    <td className="py-1.5">
                      <div className="flex items-center gap-1.5">
                        {t && <TierBadge tier={t.tier} />}
                        {l.part ? (
                          <a href={paths.hardwarePart(l.part.id)} onClick={onLinkClick(paths.hardwarePart(l.part.id))} className="hover:underline">
                            {l.part.name}
                          </a>
                        ) : (
                          <span className="text-(--color-muted)">—</span>
                        )}
                      </div>
                      {l.note && <div className="text-[10px] text-(--color-faint)">{l.note}</div>}
                    </td>
                    <td className="py-1.5 text-right tabular-nums">{l.price != null ? won(l.price) : '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {item.comp && (
            <p className="text-[11px] text-(--color-faint) mt-2">
              판매 표기: {[item.comp.cpu, item.comp.gpu, item.comp.chipset && `${item.comp.chipset} 보드`, item.comp.ram_gb && `${item.comp.ram_type} ${item.comp.ram_gb}GB`, item.comp.psu_w && `${item.comp.psu_w}W`, item.comp.case, item.comp.os]
                .filter(Boolean)
                .join(' · ')}
            </p>
          )}
        </section>
      </div>
      <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4" data-nosnippet>
        <h2 className="text-sm font-semibold mb-2">가격 추이</h2>
        <PriceChart history={hist} height={160} />
      </section>
    </div>
  )
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-(--color-border) bg-(--color-panel) p-3">
      <div className="text-[11px] text-(--color-muted)">{label}</div>
      <div className="text-xl font-bold tabular-nums">{value}</div>
      {sub && <div className="text-[11px] text-(--color-faint)">{sub}</div>}
    </div>
  )
}

// 판매가는 이렇게 나뉜다 — 부품별 원가 칸(회색 진하기) + 남기는 돈(강조색). 한 줄 막대라 합이 곧 판매가다.
// 남기는 돈이 음수(부품값보다 싸다)면 원가 칸들이 막대를 다 채우고, 그 사실을 범례에 적는다.
function PriceSplit({ item, a }: { item: Prebuilt; a: Analysis }) {
  const [tip, setTip] = useState<string | null>(null)
  const lines = a.lines.filter((l) => l.price)
  const total = Math.max(item.price, a.sum ?? 0)
  const pct = (v: number) => `${(v / total) * 100}%`
  const margin = a.premium ?? 0
  const grey = (i: number) => `color-mix(in srgb, var(--color-muted) ${70 - (i % 2) * 25}%, var(--color-panel))`
  return (
    <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4" data-nosnippet>
      <div className="flex flex-wrap items-baseline gap-2 mb-2">
        <h2 className="text-sm font-semibold">판매가 {won(item.price)} 는 이렇게 나뉜다</h2>
        <span className="text-xs text-(--color-muted)">{tip ?? '칸에 마우스를 올리면 부품과 값이 나온다'}</span>
      </div>
      <div className="flex h-8 w-full gap-[2px]" role="img" aria-label={`원가 ${won(a.sum)} + 남기는 돈 ${won(margin)}`}>
        {lines.map((l, i) => (
          <div
            key={l.label}
            className="h-full first:rounded-l-[4px]"
            style={{ width: pct(l.price!), background: grey(i) }}
            onMouseEnter={() => setTip(`${l.label} ${l.part?.name ?? ''} · ${won(l.price)}${l.note ? ` (${l.note})` : ''}`)}
            onMouseLeave={() => setTip(null)}
          />
        ))}
        {margin > 0 && (
          <div
            className="h-full rounded-r-[4px] bg-(--color-accent)"
            style={{ width: pct(margin) }}
            onMouseEnter={() => setTip(`남기는 돈 ${won(margin)} — 판매가의 ${Math.round(a.marginPct ?? 0)}%`)}
            onMouseLeave={() => setTip(null)}
          />
        )}
      </div>
      <div className="flex flex-wrap justify-between gap-2 text-[11px] text-(--color-muted) mt-1">
        <span>
          <span className="inline-block w-2.5 h-2.5 rounded-sm align-middle mr-1" style={{ background: grey(0) }} />
          원가 {won(a.sum)} (부품 {lines.length}칸)
        </span>
        <span>
          <span className="inline-block w-2.5 h-2.5 rounded-sm align-middle mr-1 bg-(--color-accent)" />
          남기는 돈 {margin >= 0 ? won(margin) : `−${won(-margin)} (부품값보다 싸다)`}
        </span>
      </div>
      <p className="text-[11px] text-(--color-faint) mt-2">
        원가는 같은 날 소비자가 살 수 있는 부품 최저가의 합이다. 조립 업체의 실제 매입가는 이보다 낮을 수 있어 실제로 남는 돈은 더 클 수 있고,
        남기는 돈 안에서 조립·검수·A/S·배송·결제 수수료가 나간다. 표기가 없는 칸(쿨러·SSD 제조사 등)은 아래 표에 가정을 적었다.
      </p>
    </section>
  )
}

// ── 성능 우선 ────────────────────────────────────────────────────────

type PerfRow = { it: Prebuilt; p: PerfRank }
type UseDef = (typeof PERF_USES)[number]

function ItemLink({ it, className = 'hover:underline' }: { it: { key: string; name: string }; className?: string }) {
  return (
    <a href={paths.hardwarePrebuiltItem(it.key)} onClick={onLinkClick(paths.hardwarePrebuiltItem(it.key))} className={className}>
      {it.name}
    </a>
  )
}

/** 한 단계 위 — '성능 +x% 에 +y원' 또는 '더 빠른데 y원 싸다' */
const stepText = (gainPct: number, extra: number) =>
  extra >= 0 ? `성능 +${Math.round(gainPct)}% 에 +${won(extra)}` : `${Math.round(gainPct)}% 더 빠른데 ${won(-extra)} 싸다`

/** 맨 위 요약 — 성능 1위와, 1위의 90% 이상을 가장 싸게 내는 것 */
function PerfTop({ rows, useDef, total }: { rows: PerfRow[]; useDef: UseDef; total: number }) {
  if (!rows.length) return <div className="text-sm text-(--color-muted)">이 용도로 잴 수 있는 완제품이 없다.</div>
  const top = rows[0]
  const near = rows.filter((r) => r.p.rel >= 90).sort((x, y) => x.it.price - y.it.price)[0]
  return (
    <section className="rounded-lg border border-(--color-accent)/40 bg-(--color-panel) p-4 flex flex-col gap-2" data-nosnippet>
      <div className="text-xs text-(--color-muted)">
        {useDef.label} 성능 1위 — 잴 수 있는 {rows.length}개 중
        {total > rows.length && ` (나머지 ${total - rows.length}개는 그래픽카드·CPU 를 몰라 뺐다)`}
      </div>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <ItemLink it={top.it} className="text-lg font-bold hover:underline" />
        <span className="text-lg font-bold tabular-nums text-(--color-accent)">{top.p.score.display}</span>
        <span className="tabular-nums">{won(top.it.price)}</span>
      </div>
      <p className="text-sm">
        <span className="text-(--color-muted)">천장: </span>
        {top.p.score.bottleneck}
      </p>
      {near && near.it.key !== top.it.key && (
        <p className="text-sm">
          <span className="text-(--color-muted)">1위의 90% 이상을 가장 싸게: </span>
          <ItemLink it={near.it} /> — {near.p.score.display}({Math.round(near.p.rel)}%) · {won(near.it.price)}
          <span className="text-(--color-muted)"> · 1위보다 {won(top.it.price - near.it.price)} 싸다</span>
        </p>
      )}
    </section>
  )
}

function PerfBar({ rel }: { rel: number }) {
  return (
    <div className="h-1.5 w-full rounded bg-(--color-band) mt-1">
      <div className="h-full rounded bg-(--color-accent)" style={{ width: `${Math.max(2, Math.min(100, rel))}%` }} />
    </div>
  )
}

function PerfTable({ rows, data, useDef }: { rows: PerfRow[]; data: HwData; useDef: UseDef }) {
  return (
    <div className="rounded-lg border border-(--color-border) bg-(--color-panel) overflow-x-auto">
      <table className="w-full text-sm min-w-[1100px]" data-nosnippet>
        <thead>
          <tr className="text-[11px] text-(--color-muted) text-left border-b border-(--color-border)">
            <th className="font-normal px-3 py-2">성능 순위</th>
            <th className="font-normal px-3 py-2">상품</th>
            <th className="font-normal px-3 py-2">CPU · 그래픽</th>
            <th className="font-normal px-3 py-2 w-40">
              {useDef.label} ({useDef.unit})
            </th>
            <th className="font-normal px-3 py-2">천장 — 여기가 막는다</th>
            <th className="font-normal px-3 py-2">한 단계 위로</th>
            <th className="font-normal px-3 py-2 text-right">가격</th>
            <th className="font-normal px-3 py-2">판매처</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ it, p }) => (
            <tr key={it.key} className="border-t border-(--color-border-soft) hover:bg-(--color-band) align-top">
              <td className="px-3 py-2 tabular-nums">
                <b>{p.rank}</b>
                <span className="text-[10px] text-(--color-faint)"> / {p.of}</span>
              </td>
              <td className="px-3 py-2 max-w-72">
                <ItemLink it={it} className="font-medium hover:underline" />
              </td>
              <td className="px-3 py-2 text-xs">
                <PartTag part={p.score.cpu} text={it.comp?.cpu ?? p.score.cpu?.name} data={data} />
                <PartTag part={p.score.gpu} text={it.comp?.gpu ?? p.score.gpu?.name} data={data} />
                {p.score.fromName && <div className="text-[10px] text-(--color-amber-400)">구성표 없음 — 상품 이름에서 읽음</div>}
              </td>
              <td className="px-3 py-2 tabular-nums">
                <b>{p.score.display}</b> <span className="text-[10px] text-(--color-muted)">{Math.round(p.rel)}%</span>
                <PerfBar rel={p.rel} />
              </td>
              <td className="px-3 py-2 text-xs text-(--color-muted) max-w-72">{p.score.bottleneck}</td>
              <td className="px-3 py-2 text-xs max-w-64">
                {p.next ? (
                  <>
                    <b className={p.next.extra < 0 ? 'text-(--color-red-400)' : ''}>{stepText(p.next.gainPct, p.next.extra)}</b>
                    <div className="text-[10px] text-(--color-faint) truncate">
                      <ItemLink it={p.next} />
                    </div>
                  </>
                ) : (
                  <span className="text-(--color-faint)">이 목록의 천장</span>
                )}
              </td>
              <td className="px-3 py-2 text-right font-bold tabular-nums">{won(it.price)}</td>
              <td className="px-3 py-2 text-xs whitespace-nowrap">
                <a href={it.url} target="_blank" rel="noreferrer nofollow" className="text-(--color-sky-400) hover:underline">
                  {it.source === 'naver' ? (it.mall ?? '네이버') : '다나와'} ↗
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-[11px] text-(--color-faint) px-3 py-2">
        성능은 부품의 성능 지수로 계산한 추정이다(bench.json 의 식). '한 단계 위로'는 이보다 5% 넘게 빠른 완제품 중 가장 싼 것 — 성능 몇 % 에 얼마를 더
        내는지다. 빨간 글씨(더 빠른데 싸다)가 붙은 제품은, 성능만 보면 이 제품을 살 이유가 없다.
      </p>
    </div>
  )
}

/** 상세 — 용도마다 이 기계의 성능·순위·천장·한 단계 위 */
function PerfPanel({ data, item, all }: { data: HwData; item: Prebuilt; all: Prebuilt[] }) {
  const per = useMemo(() => {
    const day = all.reduce((m, x) => (x.last_seen > m ? x.last_seen : m), '')
    const today = all.filter((x) => x.last_seen === day || x.key === item.key)
    return PERF_USES.map((u) => ({ u, r: perfRanks(today, data, u.key).get(item.key) ?? null }))
  }, [all, data, item.key])
  if (per.every((x) => !x.r)) return null
  return (
    <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4" data-nosnippet>
      <div className="flex flex-wrap items-baseline gap-2 mb-2">
        <h2 className="text-sm font-semibold">성능 — 돈보다 성능이 먼저일 때</h2>
        <span className="text-xs text-(--color-muted)">가격을 빼고 용도별 성능만으로 오늘 완제품 목록에서 몇 위인가</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {per.map(({ u, r }) => (
          <div key={u.key} className="rounded-md border border-(--color-border-soft) p-3 flex flex-col gap-1">
            <div className="text-[11px] text-(--color-muted)">{u.label}</div>
            {r ? (
              <>
                <div className="flex items-baseline gap-2">
                  <span className="text-lg font-bold tabular-nums">{r.score.display}</span>
                  <span className="text-xs text-(--color-muted) tabular-nums">
                    {r.rank} / {r.of}위 · 1위의 {Math.round(r.rel)}%
                  </span>
                </div>
                <PerfBar rel={r.rel} />
                <p className="text-xs">
                  <span className="text-(--color-muted)">천장: </span>
                  {r.score.bottleneck}
                </p>
                <p className="text-xs">
                  {r.next ? (
                    <>
                      <span className="text-(--color-muted)">한 단계 위: </span>
                      <ItemLink it={r.next} /> — {stepText(r.next.gainPct, r.next.extra)}
                    </>
                  ) : (
                    <span className="text-(--color-accent) font-semibold">이 목록에서 가장 빠르다</span>
                  )}
                </p>
              </>
            ) : (
              <p className="text-xs text-(--color-faint)">{perfOf(item, data, u.key).bottleneck ?? '잴 수 없다'}</p>
            )}
          </div>
        ))}
      </div>
      <p className="text-[11px] text-(--color-faint) mt-2">
        {PERF_USES.map((u) => `${u.label}: ${u.plain}`).join(' · ')}. 부품 성능 지수로 잰 추정이다.
      </p>
    </section>
  )
}
