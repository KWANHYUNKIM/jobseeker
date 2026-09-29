import { Fragment, useState } from 'react'
import {
  MODEL_COLUMNS,
  distributorOf,
  fmtSpec,
  formOf,
  groupOffers,
  notesFor,
  useGuide,
  useModels,
  type Distributor,
  type HwData,
  type Model,
  type Offer,
  type Part,
} from '../lib/hardware'
import { CardDrawing } from './HardwareCharts'

// 제품별 스펙 — 같은 칩을 얹은 제조사 제품들(ASUS ROG Astral · TUF · GIGABYTE GAMING OC …).
//
// 한 줄이 제품 하나다. 스펙은 제조사 공식 페이지에서 온 것이고(출처 링크), 가격은 그날 다나와
// 매물 중 그 제품 이름 규칙에 걸린 것들의 최저가다. 유통사가 여럿이면 누르면 펼쳐진다.
// 아직 스펙을 조사 안 한 매물도 숨기지 않는다 — 맨 아래 '스펙 조사 전' 으로 이름·가격만 보인다.

const CONF: Record<Model['confidence'], string> = { high: '공식', medium: '공식 외 출처', low: '추정' }

export function ModelTable({ data, part }: { data: HwData; part: Part }) {
  const models = useModels(part.id)
  const guide = useGuide()
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
                    <div className="flex items-center gap-2">
                      {m.image ? (
                        <img src={m.image.url} alt={m.name} loading="lazy" referrerPolicy="no-referrer" className="w-12 h-12 object-contain rounded bg-white shrink-0" />
                      ) : (
                        <span className="w-12 h-12 shrink-0 rounded bg-(--color-band) grid place-items-center text-[9px] text-(--color-faint)">사진 없음</span>
                      )}
                      <div className="font-medium">
                        <span className="text-(--color-faint) mr-1">{open === m.id ? '▾' : '▸'}</span>
                        {m.name}
                      </div>
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
                      <ModelMore m={m} offers={os} cases={cases} dists={guide?.distributors ?? []} />
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

function ModelMore({ m, offers, cases, dists }: { m: Model; offers: Offer[]; cases: Part[]; dists: Distributor[] }) {
  const len = Number(m.specs.length_mm)
  const bundle = m.specs.bundle as string[] | undefined
  return (
    <div className="grid gap-3 md:grid-cols-3 text-xs">
      <div className="flex flex-col gap-1">
        <div className="font-semibold text-(--color-muted)">판매처(유통사)</div>
        {offers.length ? (
          offers.map((o) => (
            <div key={o.pcode} className="flex items-center gap-2">
              <a href={o.url} target="_blank" rel="noreferrer nofollow" className="truncate hover:underline">
                {o.name}
              </a>
              <DistChip d={distributorOf(o.name, dists)} />
              <span className="ml-auto tabular-nums font-semibold whitespace-nowrap">{o.price.toLocaleString()}원</span>
            </div>
          ))
        ) : (
          <span className="text-(--color-faint)">오늘 잡힌 매물이 없다</span>
        )}
      </div>
      <div className="flex flex-col gap-1">
        {m.image && (
          <figure className="mb-2">
            <img src={m.image.url} alt={m.name} loading="lazy" referrerPolicy="no-referrer" className="w-full max-w-[320px] rounded bg-white" />
            <figcaption className="text-[10px] text-(--color-faint)">
              사진: <a href={m.image.page} target="_blank" rel="noreferrer" className="hover:underline">{m.image.credit} 공식 페이지</a>
            </figcaption>
          </figure>
        )}
        {len > 0 && <CardDrawing specs={m.specs} />}
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
        {(m.durability?.fan_bearing || (m.durability?.notes ?? []).length > 0) && (
          <>
            <div className="font-semibold text-(--color-muted)">내구성</div>
            {m.durability?.fan_bearing && <div>팬 베어링: {m.durability.fan_bearing}</div>}
            {(m.durability?.notes ?? []).map((n) => (
              <div key={n}>· {n}</div>
            ))}
          </>
        )}
        <div className="font-semibold text-(--color-muted) mt-1">출처</div>
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

function DistChip({ d }: { d: Distributor | null }) {
  if (!d) return null
  return (
    <span
      className="shrink-0 px-1.5 py-0.5 rounded bg-(--color-panel) border border-(--color-border-soft) text-[10px] text-(--color-muted)"
      title={[d.service, d.parallel_import_service].filter(Boolean).join(' · ')}
    >
      {d.name}
      {d.warranty_years ? ` · 보증 ${d.warranty_years}년` : ''}
    </span>
  )
}

// CPU 는 제품(보드 파트너)이 없다 — 같은 칩이 판매 형태로 갈린다. 형태마다 박스·쿨러·보증·A/S 가
// 다르고 가격도 다르다. 병행은 싸지만 국내 정식 A/S 가 없다는 걸 가격 옆에 같이 둔다.
export function SaleForms({ data, part }: { data: HwData; part: Part }) {
  const guide = useGuide()
  const offers = data.prices[part.id]?.offers ?? []
  if (!guide || !offers.length) return null
  const rows = offers.map((o) => ({ o, f: formOf(o.name, guide.forms) }))
  const used = guide.forms.filter((f) => rows.some((r) => r.f?.key === f.key))
  return (
    <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline gap-2">
        <h2 className="text-sm font-semibold">판매 형태별 가격</h2>
        <span className="text-xs text-(--color-muted)">같은 칩이다. 박스·쿨러·보증·A/S 가 다르다 · 조립 견적은 정품 최저가로 계산한다</span>
      </div>
      <table className="w-full text-sm" data-nosnippet>
        <thead>
          <tr className="text-[11px] text-(--color-muted) text-left border-b border-(--color-border)">
            <th className="font-normal px-2 py-2">형태</th>
            <th className="font-normal px-2 py-2 text-right">가격</th>
            <th className="font-normal px-2 py-2">박스</th>
            <th className="font-normal px-2 py-2">보증</th>
            <th className="font-normal px-2 py-2">A/S</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ o, f }) => (
            <tr key={o.pcode} className="border-t border-(--color-border-soft)">
              <td className="px-2 py-1.5">
                <a href={o.url} target="_blank" rel="noreferrer nofollow" className="hover:underline font-medium">
                  {f?.label ?? '모름'}
                </a>
                {f && !f.official && <span className="ml-1 text-[10px] text-(--color-red-400)">국내 정식 A/S 없음</span>}
              </td>
              <td className="px-2 text-right tabular-nums font-semibold">{o.price.toLocaleString()}원</td>
              <td className="px-2 text-(--color-muted)">{f?.box == null ? '—' : f.box ? '있음' : '없음'}</td>
              <td className="px-2 text-(--color-muted)">{f?.warranty_years ? `${f.warranty_years}년` : '—'}</td>
              <td className="px-2 text-(--color-muted) text-xs">{f?.service ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="grid gap-2 sm:grid-cols-2 text-xs">
        {used.map((f) => (
          <div key={f.key} className="rounded-md bg-(--color-band) p-2.5">
            <div className="font-semibold">{f.label}</div>
            <div className="mt-0.5">{f.plain}</div>
            {f.cooler && <div className="mt-0.5 text-(--color-muted)">쿨러: {f.cooler}</div>}
            <div className="mt-1 flex flex-wrap gap-x-2">
              {f.sources.map((s) => (
                <a key={s.url} href={s.url} target="_blank" rel="noreferrer" className="text-(--color-sky-400) hover:underline">
                  {s.title}
                </a>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

// 알아 둘 것 — 이 부품(또는 이 분류)에 걸린 내구성·주의 메모. 출처가 있는 것만 싣는다.
export function DurabilityNotes({ part }: { part: Part }) {
  const guide = useGuide()
  if (!guide) return null
  const notes = notesFor(part, guide.durability)
  if (!notes.length) return null
  return (
    <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 flex flex-col gap-2">
      <h2 className="text-sm font-semibold">알아 둘 것 — 내구성·주의</h2>
      {notes.map((n) => (
        <div key={n.key} className="text-sm flex gap-2">
          <span
            className={`shrink-0 h-fit px-1.5 py-0.5 rounded text-[10px] font-semibold ${
              n.level === '주의' ? 'bg-(--color-red-400)/12 text-(--color-red-400)' : 'bg-(--color-band) text-(--color-muted)'
            }`}
          >
            {n.level}
          </span>
          <div>
            <b>{n.title}</b> — {n.plain}
            {n.sources.map((s, i) => (
              <a key={s.url} href={s.url} target="_blank" rel="noreferrer" className="text-xs text-(--color-sky-400) hover:underline ml-1">
                [{i + 1}]
              </a>
            ))}
          </div>
        </div>
      ))}
    </section>
  )
}
