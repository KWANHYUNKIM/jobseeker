import { Fragment, useState } from 'react'
import { MODEL_COLUMNS, fmtSpec, groupOffers, useModels, type HwData, type Model, type Offer, type Part } from '../lib/hardware'

// 제품별 스펙 — 같은 칩을 얹은 제조사 제품들(ASUS ROG Astral · TUF · GIGABYTE GAMING OC …).
//
// 한 줄이 제품 하나다. 스펙은 제조사 공식 페이지에서 온 것이고(출처 링크), 가격은 그날 다나와
// 매물 중 그 제품 이름 규칙에 걸린 것들의 최저가다. 유통사가 여럿이면 누르면 펼쳐진다.
// 아직 스펙을 조사 안 한 매물도 숨기지 않는다 — 맨 아래 '스펙 조사 전' 으로 이름·가격만 보인다.

const CONF: Record<Model['confidence'], string> = { high: '공식', medium: '공식 외 출처', low: '추정' }

export function ModelTable({ data, part }: { data: HwData; part: Part }) {
  const models = useModels(part.id)
  const [open, setOpen] = useState<string | null>(null)
  const rec = data.prices[part.id]
  const offers = rec?.offers ?? []
  if (models == null) return null
  const cols = MODEL_COLUMNS[part.category] ?? []
  const { byModel, rest } = groupOffers(offers, models)
  // 케이스 급별로 들어가나 — GPU 길이만 본다(제품마다 다른 값이라 여기서야 말할 수 있다).
  const cases = data.parts.filter((p) => p.category === 'case')
  if (!models.length && !offers.length) return null
  const rows = models
    .map((m) => ({ m, os: byModel.get(m.id) ?? [] }))
    .sort((a, b) => (a.os[0]?.price ?? Infinity) - (b.os[0]?.price ?? Infinity))

  return (
    <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 flex flex-col gap-2">
      <div className="flex flex-wrap items-baseline gap-2">
        <h2 className="text-sm font-semibold">제품별 스펙</h2>
        <span className="text-xs text-(--color-muted)">
          스펙은 제조사 공식 페이지 · 가격은 {rec?.day ?? '—'} 다나와 매물 · 조사한 제품 {models.length}개
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-nosnippet>
          <thead>
            <tr className="text-[11px] text-(--color-muted) text-left border-b border-(--color-border)">
              <th className="font-normal px-2 py-2">제품</th>
              <th className="font-normal px-2 py-2 text-right">최저가</th>
              {cols.map((c) => (
                <th key={c.key} className="font-normal px-2 py-2 whitespace-nowrap">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ m, os }) => (
              <Fragment key={m.id}>
                <tr className="border-t border-(--color-border-soft) hover:bg-(--color-band) cursor-pointer" onClick={() => setOpen(open === m.id ? null : m.id)}>
                  <td className="px-2 py-1.5 min-w-52">
                    <div className="font-medium">
                      <span className="text-(--color-faint) mr-1">{open === m.id ? '▾' : '▸'}</span>
                      {m.name}
                    </div>
                    <div className="text-[10px] text-(--color-faint)">
                      {m.code} · {CONF[m.confidence]} {m.checked_at}
                    </div>
                  </td>
                  <td className="px-2 text-right tabular-nums whitespace-nowrap">
                    {os.length ? (
                      <>
                        <b>{os[0].price.toLocaleString()}원</b>
                        {os.length > 1 && <div className="text-[10px] text-(--color-faint)">유통 {os.length}곳</div>}
                      </>
                    ) : (
                      <span className="text-(--color-faint)">오늘 매물 없음</span>
                    )}
                  </td>
                  {cols.map((c) => (
                    <td key={c.key} className="px-2 whitespace-nowrap tabular-nums text-(--color-muted)">
                      {fmtSpec(m.specs[c.key] as string | number | boolean | null, c.unit)}
                    </td>
                  ))}
                </tr>
                {open === m.id && (
                  <tr className="bg-(--color-band)">
                    <td colSpan={cols.length + 2} className="px-4 py-3">
                      <ModelMore m={m} offers={os} cases={cases} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {rest.length > 0 && (
              <tr>
                <td colSpan={cols.length + 2} className="px-2 pt-4 pb-1 text-[11px] text-(--color-muted)">
                  스펙 조사 전 — 이름·가격만 ({rest.length})
                </td>
              </tr>
            )}
            {rest.map((o) => (
              <tr key={o.pcode} className="border-t border-(--color-border-soft)">
                <td className="px-2 py-1.5">
                  <a href={o.url} target="_blank" rel="noreferrer nofollow" className="hover:underline text-(--color-muted)">
                    {o.name}
                  </a>
                </td>
                <td className="px-2 text-right tabular-nums whitespace-nowrap">{o.price.toLocaleString()}원</td>
                <td colSpan={cols.length} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function ModelMore({ m, offers, cases }: { m: Model; offers: Offer[]; cases: Part[] }) {
  const len = Number(m.specs.length_mm)
  const bundle = m.specs.bundle as string[] | undefined
  return (
    <div className="grid gap-3 md:grid-cols-3 text-xs">
      <div className="flex flex-col gap-1">
        <div className="font-semibold text-(--color-muted)">판매처(유통사)</div>
        {offers.length ? (
          offers.map((o) => (
            <a key={o.pcode} href={o.url} target="_blank" rel="noreferrer nofollow" className="flex gap-2 hover:underline">
              <span className="truncate">{o.name}</span>
              <span className="ml-auto tabular-nums font-semibold">{o.price.toLocaleString()}원</span>
            </a>
          ))
        ) : (
          <span className="text-(--color-faint)">오늘 잡힌 매물이 없다</span>
        )}
      </div>
      <div className="flex flex-col gap-1">
        {len > 0 && (
          <>
            <div className="font-semibold text-(--color-muted)">케이스에 들어가나 (길이 {len}mm)</div>
            {cases.map((c) => {
              const max = Number(c.specs.max_gpu_mm)
              const ok = len <= max - 10
              return (
                <div key={c.id} className={ok ? '' : 'text-(--color-red-400)'}>
                  {ok ? '✓' : '✕'} {c.name} — 흔한 한도 {max}mm{!ok && ' · 상품별 확인 필요'}
                </div>
              )
            })}
          </>
        )}
        {bundle && bundle.length > 0 && (
          <>
            <div className="font-semibold text-(--color-muted) mt-2">구성품</div>
            <div>{bundle.join(' · ')}</div>
          </>
        )}
      </div>
      <div className="flex flex-col gap-1">
        <div className="font-semibold text-(--color-muted)">출처</div>
        {m.sources.map((s) => (
          <a key={s.url} href={s.url} target="_blank" rel="noreferrer" className="text-(--color-sky-400) hover:underline">
            {s.title}
          </a>
        ))}
        {m.note && <div className="text-(--color-faint) mt-1">{m.note}</div>}
      </div>
    </div>
  )
}
