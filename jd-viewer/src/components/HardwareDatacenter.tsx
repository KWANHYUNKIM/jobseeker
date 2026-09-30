import { Fragment, useEffect, useState } from 'react'
import { type HwData } from '../lib/hardware'
import { absUrl, useSeo } from '../lib/seo'
import { paths } from '../lib/urls'
import { NOINDEX } from './HardwarePrices'

// AI 데이터센터 — 회사별로 가진 칩과 거기서 나오는 성능 추정.
//
// 칩 수·전력은 공개 자료(public/hardware/datacenter.json, 출처 필수)다. 대부분 Epoch AI 의
// 추정(위성사진·공시)이거나 회사의 둥근 숫자라 화면에 '추정'·'공식'을 가른다.
// 성능은 한 가지 잣대로 센다 — H100 환산 대수(Epoch)에
//   · 연산: H100 한 장 FP8 1,979 TFLOPS(밀집, NVIDIA 공식)
//   · 토큰: H100 한 장이 Llama 2 70B 를 묶음 처리로 내는 초당 토큰(MLPerf v5.0)
// 을 곱한다. 블랙웰은 토큰으로 재면 연산비보다 더 나와서 이 방식은 낮게 잡는 쪽이다.
// Google 은 TPU 의 H100 환산 공식 값이 없어, 공개한 월간 처리 토큰을 거꾸로 셈한 하한만 싣는다.

interface Src {
  title: string
  url: string
}
interface Cluster {
  key: string
  company: string
  region?: string
  /** 사양비 환산에 쓰는 칩 이름(ratios 의 키). 섞인 칩이면 mix 로 나눠 적는다 */
  chip_key?: string | null
  mix?: { chip_key: string; count: number }[]
  /** 칩 수 대신 공시한 FP16 연산량(PFLOPS) — 통신사·SenseTime 처럼 이것만 밝힌 곳 */
  fp16_pflops?: number | null
  /** false 면 회사 합계에서 뺀다(다른 행의 부분 집합이거나 겹친다) */
  in_total?: boolean
  org: string
  name: string
  chip: string | null
  count: number | null
  h100eq: number | null
  mw: number | null
  status: 'operational' | 'planned' | 'past'
  as_of: string
  confidence: 'estimate' | 'official'
  note: string
  sources: Src[]
}
interface Chip {
  name: string
  hbm_gb: number | null
  bw_tbs: number | null
  fp8_tflops: number | null
  tdp_w: number | null
  llama70b_tps: number | null
  sources: Src[]
}
interface Usage {
  org: string
  claim: string
  value: number
  text: string
  as_of: string
  sources: Src[]
}
interface Ratio {
  name: string
  /** H100 대비 — FP8 밀집 비(없으면 BF16 밀집 비) */
  ratio: number
  basis: string
  sources: Src[]
}
interface National {
  scope: string
  claim: string
  as_of: string
  confidence: 'estimate' | 'official'
  sources: Src[]
}
interface Doc {
  updated_at: string
  ratios?: Ratio[]
  national?: National[]
  note: string
  basis: { h100_tps: number; h100_tps_text: string; h100eq_text: string }
  companies: { key: string; note: string }[]
  clusters: Cluster[]
  chips: Chip[]
  usage: Usage[]
}

const H100_FP8_TFLOPS = 1979
const USER_TPS = 25 // 한 사람에게 '말하는 속도보다 빠르게' 주는 초당 토큰(bench.json comfortable_tps 와 같은 값)
const MONTH_S = 30 * 86400

/** 큰 수를 한국식 단위로 — 12,340,000 → 1,234만 */
function kor(n: number | null | undefined, digits = 0): string {
  if (n == null || !Number.isFinite(n)) return '—'
  const units: [number, string][] = [
    [1e16, '경'],
    [1e12, '조'],
    [1e8, '억'],
    [1e4, '만'],
  ]
  for (const [v, u] of units) {
    if (Math.abs(n) >= v) {
      const x = n / v
      return `${x >= 100 ? Math.round(x).toLocaleString() : x.toFixed(x >= 10 ? 0 : 1)}${u}`
    }
  }
  return n.toFixed(digits)
}

interface Row {
  company: string
  region: string
  /** 이 회사 환산에 쓴 근거들 */
  methods: ('epoch' | 'spec' | 'flops')[]
  note: string
  live: Cluster[]
  planned: Cluster[]
  h100eq: number | null
  chips: number | null
  mw: number | null
  /** Google 처럼 환산 대신 실제 처리량으로 거꾸로 셈한 H100 수 */
  implied: { h100eq: number; from: Usage } | null
}

const H100_BF16_TFLOPS = 989

/** 데이터센터 하나의 H100 환산과 그 근거 */
function eqOf(c: Cluster, doc: Doc): { eq: number; by: 'epoch' | 'spec' | 'flops' } | null {
  if (c.h100eq != null) return { eq: c.h100eq, by: 'epoch' }
  const ratio = (k?: string | null) => (k ? doc.ratios?.find((x) => x.name === k)?.ratio : undefined)
  if (c.mix?.length) {
    const parts = c.mix.map((m) => (ratio(m.chip_key) != null ? m.count * ratio(m.chip_key)! : null))
    return parts.every((x) => x != null) ? { eq: parts.reduce((a, b) => a! + b!, 0)!, by: 'spec' } : null
  }
  const r = ratio(c.chip_key)
  if (r != null && c.count != null) return { eq: c.count * r, by: 'spec' }
  if (c.fp16_pflops != null) return { eq: (c.fp16_pflops * 1000) / H100_BF16_TFLOPS, by: 'flops' }
  return null
}
const BY: Record<'epoch' | 'spec' | 'flops', string> = { epoch: '출처가 밝힌 환산', spec: '칩 수 × 사양비', flops: '공시 연산 ÷ H100' }

const REGION: Record<string, string> = { US: '미국', CN: '중국', KR: '한국', JP: '일본', EU: '유럽', ME: '중동', IN: '인도', OTHER: '기타' }

function rows(doc: Doc): Row[] {
  const names = [...new Set(doc.clusters.map((x) => x.company))]
  const out = names.map((name): Row => {
    const c = doc.companies.find((x) => x.key === name) ?? { key: name, note: '' }
    const mine = doc.clusters.filter((x) => x.company === c.key)
    const live = mine.filter((x) => x.status === 'operational' && x.in_total !== false)
    const extra = mine.filter((x) => x.status === 'operational' && x.in_total === false)
    const planned = [...extra, ...mine.filter((x) => x.status !== 'operational')]
    const sum = (f: (x: Cluster) => number | null) => {
      const vs = live.map(f).filter((v): v is number => v != null)
      return vs.length ? vs.reduce((a, b) => a + b, 0) : null
    }
    const h100eq = sum((x) => eqOf(x, doc)?.eq ?? null)
    const methods = [...new Set(live.map((x) => eqOf(x, doc)?.by).filter((x): x is 'epoch' | 'spec' | 'flops' => !!x))]
    const use = doc.usage.find((u) => u.org === c.key && u.claim.startsWith('한 달에'))
    return {
      company: c.key,
      region: mine.find((x) => x.region)?.region ?? 'US',
      methods,
      note: c.note,
      live,
      planned,
      h100eq,
      chips: sum((x) => x.count),
      mw: sum((x) => x.mw),
      implied: h100eq == null && use ? { h100eq: use.value / MONTH_S / doc.basis.h100_tps, from: use } : null,
    }
  })
  // 환산값 → 칩 수 → 계획만 있는 회사 순
  const key = (r: Row) => r.h100eq ?? r.implied?.h100eq ?? 0
  return out.sort((a, b) => key(b) - key(a) || (b.chips ?? 0) - (a.chips ?? 0) || b.live.length - a.live.length)
}

function Sources({ xs }: { xs: Src[] }) {
  return (
    <span className="inline-flex flex-wrap gap-x-2">
      {xs.map((s) => (
        <a key={s.url} href={s.url} target="_blank" rel="noreferrer" className="text-(--color-sky-400) hover:underline">
          {s.title}
        </a>
      ))}
    </span>
  )
}

const Badge = ({ c }: { c: Cluster }) => (
  <span
    className={`text-[10px] px-1 rounded ${c.status === 'planned' ? 'bg-(--color-amber-400)/15 text-(--color-amber-400)' : c.confidence === 'estimate' ? 'bg-(--color-band) text-(--color-muted)' : 'bg-(--color-accent)/12 text-(--color-accent)'}`}
  >
    {c.status === 'planned' ? '계획' : c.status === 'past' ? '과거 목표' : c.confidence === 'estimate' ? '추정' : '공식'}
  </span>
)

export function HardwareDatacenter({ data }: { data: HwData }) {
  useSeo({
    title: 'AI 회사 데이터센터 비교',
    description: 'AI 회사별로 가진 GPU·TPU 수와 거기서 나오는 연산·토큰 처리량 추정',
    robots: NOINDEX,
    canonical: absUrl(paths.hardwareDatacenter()),
  })
  void data
  const [doc, setDoc] = useState<Doc | null | false>(null)
  const [open, setOpen] = useState<string | null>(null)
  const [region, setRegion] = useState<string>('')
  useEffect(() => {
    fetch('/hardware/datacenter.json')
      .then((r) => (r.ok ? r.json() : false))
      .then(setDoc)
      .catch(() => setDoc(false))
  }, [])
  if (doc === null) return <div className="p-8 text-sm text-(--color-muted)">불러오는 중…</div>
  if (doc === false) return <div className="p-8 text-sm text-(--color-muted)">데이터센터 자료를 준비하고 있다.</div>

  const all = rows(doc)
  const regions = [...new Set(all.map((r) => r.region))]
  const rs = all.filter((r) => !region || r.region === region)
  const tps = doc.basis.h100_tps
  const maxEq = Math.max(...rs.map((r) => r.h100eq ?? r.implied?.h100eq ?? 0), 1)

  return (
    <div className="max-w-[1400px] mx-auto p-4 flex flex-col gap-4">
      <header className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h1 className="text-lg font-bold">AI 회사 데이터센터 — 누가 얼마나 가졌고 얼마나 나오나</h1>
        <span className="text-xs text-(--color-muted)">공개 자료 {doc.updated_at} 기준 · 성능은 한 가지 잣대로 셈한 추정</span>
      </header>

      <div className="flex flex-wrap items-center gap-1.5 text-sm">
        {['', ...regions].map((k) => (
          <button
            key={k || 'all'}
            onClick={() => setRegion(k)}
            className={`px-2.5 py-1 rounded-md ${region === k ? 'bg-(--color-accent) text-(--color-on-accent) font-semibold' : 'bg-(--color-band) hover:bg-(--color-border-soft)'}`}
          >
            {k ? REGION[k] ?? k : '전체'} <span className="text-[10px] opacity-70">{k ? all.filter((r) => r.region === k).length : all.length}</span>
          </button>
        ))}
      </div>
      <div className="rounded-lg border border-(--color-border) bg-(--color-panel) overflow-x-auto">
        <table className="w-full text-sm min-w-[1100px]">
          <thead>
            <tr className="text-[11px] text-(--color-muted) text-left border-b border-(--color-border)">
              <th className="font-normal px-3 py-2">회사</th>
              <th className="font-normal px-3 py-2">가동 중인 칩</th>
              <th className="font-normal px-3 py-2 w-56">H100 환산</th>
              <th className="font-normal px-3 py-2 text-right">연산(FP8)</th>
              <th className="font-normal px-3 py-2 text-right">초당 토큰(70B 급)</th>
              <th className="font-normal px-3 py-2 text-right">하루 토큰</th>
              <th className="font-normal px-3 py-2 text-right">동시 응대 인원</th>
              <th className="font-normal px-3 py-2 text-right">전력(IT)</th>
              <th className="font-normal px-3 py-2">계획</th>
            </tr>
          </thead>
          <tbody>
            {rs.map((r) => {
              const eq = r.h100eq ?? r.implied?.h100eq ?? null
              const t = eq != null ? eq * tps : null
              const shown = open === r.company
              const chipTypes = [...new Set(r.live.map((c) => c.chip).filter(Boolean))].join(' · ')
              return (
                <Fragment key={r.company}>
                  <tr
                    className={`border-t border-(--color-border-soft) align-top cursor-pointer ${shown ? 'bg-(--color-accent)/6' : 'hover:bg-(--color-band)'}`}
                    onClick={() => setOpen(shown ? null : r.company)}
                  >
                    <td className="px-3 py-2">
                      <div className="font-semibold">
                        <span className="text-(--color-muted) mr-1">{shown ? '▾' : '▸'}</span>
                        {r.company}
                      </div>
                      <div className="text-[10px] text-(--color-faint)">
                        {REGION[r.region] ?? r.region} · 가동 {r.live.length}곳
                      </div>
                    </td>
                    <td className="px-3 py-2 text-xs">
                      {r.chips != null ? <b className="tabular-nums">{kor(r.chips)}장</b> : r.implied ? <span className="text-(--color-muted)">공개 수 없음</span> : '—'}
                      {chipTypes && <div className="text-[10px] text-(--color-muted)">{chipTypes}</div>}
                    </td>
                    <td className="px-3 py-2 tabular-nums">
                      {eq != null ? (
                        <>
                          <b>{kor(eq)}</b>
                          {r.implied && <span className="text-[10px] text-(--color-amber-400)"> 역산 하한</span>}
                          {r.methods.length > 0 && <div className="text-[10px] text-(--color-muted)">{r.methods.map((m) => BY[m]).join(' + ')}</div>}
                          <div className="h-1.5 rounded bg-(--color-band) mt-1">
                            <div
                              className={`h-full rounded ${r.implied ? 'bg-(--color-amber-400)/70' : 'bg-(--color-accent)'}`}
                              style={{ width: `${(eq / maxEq) * 100}%` }}
                            />
                          </div>
                        </>
                      ) : (
                        <span className="text-(--color-faint)">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{eq != null ? `${((eq * H100_FP8_TFLOPS) / 1e6).toFixed(eq * H100_FP8_TFLOPS >= 1e7 ? 0 : 1)} EFLOPS` : '—'}</td>
                    <td className="px-3 py-2 text-right tabular-nums font-semibold">{t != null ? kor(t) : '—'}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{t != null ? kor(t * 86400) : '—'}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{t != null ? `${kor(t / USER_TPS)}명` : '—'}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{r.mw != null ? (r.mw >= 1000 ? `${(r.mw / 1000).toFixed(2)}GW` : `${Math.round(r.mw)}MW`) : '—'}</td>
                    <td className="px-3 py-2 text-xs text-(--color-muted) max-w-72">
                      {r.planned
                        .filter((c) => c.status === 'planned')
                        .map((c) => `${c.name}${c.count ? ` ${kor(c.count)}장` : ''}${c.mw ? ` ${c.mw >= 1000 ? `${c.mw / 1000}GW` : `${c.mw}MW`}` : ''}`)
                        .join(' · ') || '—'}
                    </td>
                  </tr>
                  {shown && (
                    <tr className="bg-(--color-accent)/4">
                      <td colSpan={9} className="px-4 py-3">
                        <p className="text-xs text-(--color-muted) mb-2">{r.note}</p>
                        {r.implied && (
                          <p className="text-xs mb-2">
                            <b>역산:</b> {r.company} 는 {r.implied.from.as_of} 에 {r.implied.from.claim} {r.implied.from.text} 를 처리한다고 했다 — 초당{' '}
                            {kor(r.implied.from.value / MONTH_S)}토큰이다. H100 이 초당 {tps.toLocaleString()}토큰이면 <b>최소 {kor(r.implied.h100eq)}장</b>이 쉬지 않고
                            돌아야 나오는 양이다(학습용·여유분은 빠진 하한). <Sources xs={r.implied.from.sources} />
                          </p>
                        )}
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="text-[10px] text-(--color-muted) text-left">
                              <th className="font-normal py-1">데이터센터</th>
                              <th className="font-normal py-1">칩</th>
                              <th className="font-normal py-1 text-right">칩 수</th>
                              <th className="font-normal py-1 text-right">H100 환산</th>
                              <th className="font-normal py-1 text-right">초당 토큰</th>
                              <th className="font-normal py-1 text-right">전력</th>
                              <th className="font-normal py-1 pl-3">메모 · 출처</th>
                            </tr>
                          </thead>
                          <tbody>
                            {[...r.live, ...r.planned].map((c) => (
                              <tr key={c.key} className="border-t border-(--color-border-soft) align-top">
                                <td className="py-1.5 pr-2">
                                  <div className="font-medium">
                                    {c.name} <Badge c={c} />
                                    {c.status === 'operational' && c.in_total === false && (
                                      <span className="ml-1 text-[10px] px-1 rounded bg-(--color-band) text-(--color-faint)">합계 제외</span>
                                    )}
                                  </div>
                                  <div className="text-[10px] text-(--color-faint)">
                                    {c.org} · {c.as_of}
                                  </div>
                                </td>
                                <td className="py-1.5 pr-2">{c.chip ?? '—'}</td>
                                <td className="py-1.5 text-right tabular-nums">{c.count != null ? kor(c.count) : '—'}</td>
                                <td className="py-1.5 text-right tabular-nums">
                                  {(() => {
                                    const e = eqOf(c, doc)
                                    return e ? (
                                      <>
                                        {kor(e.eq)}
                                        <div className="text-[10px] text-(--color-faint)">{BY[e.by]}</div>
                                      </>
                                    ) : (
                                      '—'
                                    )
                                  })()}
                                </td>
                                <td className="py-1.5 text-right tabular-nums">{(() => { const e = eqOf(c, doc); return e ? kor(e.eq * tps) : '—' })()}</td>
                                <td className="py-1.5 text-right tabular-nums">{c.mw != null ? (c.mw >= 1000 ? `${c.mw / 1000}GW` : `${c.mw}MW`) : '—'}</td>
                                <td className="py-1.5 pl-3 max-w-[28rem]">
                                  <div className="text-(--color-muted)">{c.note}</div>
                                  <Sources xs={c.sources} />
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>

      {doc.national && doc.national.length > 0 && (
        <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4">
          <h2 className="text-sm font-semibold">나라·정부 단위</h2>
          <p className="text-[11px] text-(--color-muted) mb-2">위 회사 줄의 합이거나 겹치는 숫자라 표에 더하지 않고 따로 싣는다.</p>
          <ul className="text-xs flex flex-col gap-1.5">
            {doc.national.map((n) => (
              <li key={n.scope + n.as_of}>
                <b>{n.scope}</b> — {n.claim} <span className="text-(--color-faint)">({n.as_of} · {n.confidence === 'official' ? '공식' : '추정'})</span>{' '}
                <span className="text-[10px]">
                  <Sources xs={n.sources} />
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 text-xs flex flex-col gap-1.5">
        <h2 className="text-sm font-semibold">어떻게 셌나</h2>
        <p>
          <b>H100 환산</b> — {doc.basis.h100eq_text}
        </p>
        <p>
          <b>칩 수 × 사양비</b> — Epoch 환산이 없는 곳은 칩 수에 'H100 대비 공식 사양비'(FP8 밀집, FP8 이 없는 칩은 BF16)를 곱했다. 칩 구성이 섞였으면 칩마다 곱해 더한다. 칩 수만
          있고 기종을 모르면 환산하지 않는다(—). 연산량(FP16)만 공시한 곳은 그 값을 H100 BF16 {H100_BF16_TFLOPS} TFLOPS 로 나눴다. 사양비 표는 맨 아래에 있다.
        </p>
        <p>
          <b>합계</b> — 회사 줄은 가동 중인 것만 더한다. 다른 행의 일부이거나 겹치는 행은 '합계 제외'로 펼친 칸에만 보인다. 빌려 쓰는 칩은 쓰는 회사 쪽에 세서, 빌려주는 회사(CoreWeave 등)와 겹칠 수 있다.
        </p>
        <p>
          <b>연산</b> = H100 환산 × H100 한 장 FP8 {H100_FP8_TFLOPS.toLocaleString()} TFLOPS(밀집, NVIDIA 공식). 1 EFLOPS = 100만 TFLOPS.
        </p>
        <p>
          <b>초당 토큰</b> = H100 환산 × {tps.toLocaleString()} — {doc.basis.h100_tps_text}. 모두 70B 급 모델 하나만 돌린다고 친 값이고, 실제로는 학습·더 큰 모델에 나눠 쓴다.
        </p>
        <p>
          <b>동시 응대 인원</b> = 초당 토큰 ÷ {USER_TPS} — 한 사람에게 말하는 속도보다 빠르게(초당 {USER_TPS}토큰) 답을 준다고 칠 때 동시에 몇 명까지 되나.
        </p>
        <p className="text-(--color-muted)">{doc.note}</p>
      </section>

      {doc.ratios && doc.ratios.length > 0 && (
        <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4">
          <h2 className="text-sm font-semibold">칩 사양비 — H100 한 장을 1 로 두면</h2>
          <p className="text-[11px] text-(--color-muted) mb-2">
            FP8 밀집 성능 비(FP8 이 없는 칩은 BF16). 공식 사양을 확인하지 못한 칩(Huawei Ascend 910B · Baidu Kunlun P800 · Intel GPU Max 1550 · 자체 설계 칩)은 싣지 않아 그 데이터센터는 칩 수만 보인다.
          </p>
          <div className="grid gap-x-6 gap-y-1 sm:grid-cols-2 lg:grid-cols-3 text-xs">
            {doc.ratios.map((r) => (
              <div key={r.name} className="flex items-baseline gap-2 border-t border-(--color-border-soft) py-1">
                <b className="w-28 shrink-0">{r.name}</b>
                <span className="tabular-nums font-semibold w-12 shrink-0">×{r.ratio}</span>
                <span className="text-[10px] text-(--color-muted)">
                  {r.basis} · <Sources xs={r.sources} />
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4">
          <h2 className="text-sm font-semibold mb-2">칩 한 장 — 공식 사양과 MLPerf 토큰</h2>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[10px] text-(--color-muted) text-left">
                <th className="font-normal py-1">칩</th>
                <th className="font-normal py-1 text-right">메모리</th>
                <th className="font-normal py-1 text-right">대역폭</th>
                <th className="font-normal py-1 text-right">FP8(밀집)</th>
                <th className="font-normal py-1 text-right">70B 초당 토큰</th>
              </tr>
            </thead>
            <tbody>
              {doc.chips.map((c) => (
                <tr key={c.name} className="border-t border-(--color-border-soft)">
                  <td className="py-1.5">
                    {c.name}
                    <div className="text-[10px]">
                      <Sources xs={c.sources} />
                    </div>
                  </td>
                  <td className="py-1.5 text-right tabular-nums">{c.hbm_gb != null ? `${c.hbm_gb}GB` : '—'}</td>
                  <td className="py-1.5 text-right tabular-nums">{c.bw_tbs != null ? `${c.bw_tbs}TB/s` : '—'}</td>
                  <td className="py-1.5 text-right tabular-nums">{c.fp8_tflops != null ? `${c.fp8_tflops.toLocaleString()}T` : '—'}</td>
                  <td className="py-1.5 text-right tabular-nums">{c.llama70b_tps != null ? c.llama70b_tps.toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[10px] text-(--color-faint) mt-2">70B 초당 토큰은 MLPerf Inference Llama 2 70B 오프라인 결과를 GPU 수로 나눈 값(H100·H200 v5.0, B200·GB200 v5.1).</p>
        </section>
        <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4">
          <h2 className="text-sm font-semibold mb-2">실제로 처리한다고 밝힌 양</h2>
          <ul className="text-xs flex flex-col gap-1.5">
            {doc.usage.map((u) => (
              <li key={u.org + u.as_of}>
                <b>{u.org}</b> · {u.claim} <b>{u.text}</b> <span className="text-(--color-faint)">({u.as_of})</span>
                <div className="text-[10px]">
                  초당으로 치면 약 {kor(u.value / MONTH_S)}토큰 · <Sources xs={u.sources} />
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}
