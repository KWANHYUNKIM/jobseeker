import { useMemo, useState } from 'react'
import { tierOf, won, type HwData } from '../lib/hardware'
import { analyze, usePrebuilt, valueRanks, type Prebuilt } from '../lib/prebuilt'
import { onLinkClick } from '../lib/router'
import { absUrl, useSeo } from '../lib/seo'
import { paths } from '../lib/urls'
import { NOINDEX, PriceChart } from './HardwarePrices'
import { TierBadge } from './HardwareView'
import { Loader } from './ui'

// 완제품 조립PC — 누가 설계해 파는 조립PC 를 부품으로 뜯어 본다(lib/prebuilt.ts 머리말).
// 목록: 가격·구성·부품값 대비·가성비 순위·예상 fps. 상세: 부품별 값, 잘한 점·아쉬운 점, 가격 추이.
// 가격이 실리는 화면이라 색인하지 않는다.

type SortKey = 'value' | 'price' | 'premium' | 'fps'

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
  const ranks = useMemo(() => valueRanks(items, data), [items, data])
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
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="이름·부품으로 찾기 (예: 5070, 9800X3D)" className="border border-(--color-border) rounded px-2 py-1 bg-(--color-panel) w-72" />
        <span className="text-xs text-(--color-muted)">가성비 = 예상 QHD 평균 fps 1 당 가격(낮을수록 좋다) · 부품값 대비 = 부품을 따로 샀을 때보다 얼마나 비싼가</span>
      </div>
      <div className="rounded-lg border border-(--color-border) bg-(--color-panel) overflow-x-auto">
        <table className="w-full text-sm min-w-[1000px]" data-nosnippet>
          <thead>
            <tr className="text-[11px] text-(--color-muted) text-left border-b border-(--color-border)">
              <th className="font-normal px-3 py-2">{th('value', '가성비 순위')}</th>
              <th className="font-normal px-3 py-2">상품</th>
              <th className="font-normal px-3 py-2">CPU · 그래픽</th>
              <th className="font-normal px-3 py-2">메모리 · SSD</th>
              <th className="font-normal px-3 py-2 text-right">{th('price', '가격')}</th>
              <th className="font-normal px-3 py-2 text-right">{th('premium', '부품값 대비')}</th>
              <th className="font-normal px-3 py-2 text-right">{th('fps', 'QHD 예상')}</th>
              <th className="font-normal px-3 py-2">의견</th>
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
                <td className={`px-3 py-2 text-right tabular-nums ${a.premiumPct == null ? 'text-(--color-faint)' : a.premiumPct >= 25 ? 'text-(--color-red-400)' : a.premiumPct <= 10 ? 'text-(--color-accent) font-semibold' : ''}`}>
                  {a.premiumPct == null ? '계산 불가' : `${a.premiumPct >= 0 ? '+' : ''}${Math.round(a.premiumPct)}%`}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{a.qhdFps ?? '—'}</td>
                <td className="px-3 py-2 text-xs text-(--color-muted)">{it.rating ? `★ ${it.rating.avg.toFixed(1)} (${it.rating.count})` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
          원문 보기{item.rating ? ` · ★ ${item.rating.avg.toFixed(1)} 리뷰 ${item.rating.count}건` : ' · 상품의견은 원문에서'}
        </a>
      </header>
      <div className="grid gap-3 sm:grid-cols-4" data-nosnippet>
        <Stat label="판매가" value={won(item.price)} sub={item.offer_count ? `판매처 ${item.offer_count}곳` : undefined} />
        <Stat label="부품값 합계(추정)" value={a.sum != null ? won(a.sum) : '계산 불가'} sub={a.unknown.length ? '목록에 없는 부품 제외' : '같은 날 최저가 기준'} />
        <Stat
          label="조립 프리미엄"
          value={a.premium != null ? `${a.premium >= 0 ? '+' : ''}${won(Math.abs(a.premium)).replace('원', '')}원` : '—'}
          sub={a.premiumPct != null ? `${a.premiumPct >= 0 ? '+' : ''}${Math.round(a.premiumPct)}% — 조립·검수·A/S·배송값` : undefined}
        />
        <Stat label="가성비 순위" value={r ? `${r.rank} / ${r.of}` : '—'} sub={r ? `QHD 예상 ${a.qhdFps}fps · fps 당 ${Math.round(r.wonPerFps).toLocaleString()}원` : undefined} />
      </div>
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
