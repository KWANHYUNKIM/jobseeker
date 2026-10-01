import { useMemo, useState } from 'react'
import {
  CATEGORY_ORDER,
  RES_LABEL,
  planBuild,
  buildTotal,
  checkBuild,
  conflictsOf,
  estimateBuildMin,
  estimateFps,
  estimateImageSec,
  estimateLlm,
  fpsWord,
  priceOf,
  tierOf,
  tpsWord,
  useHardware,
  won,
  type Build,
  type Category,
  type HwData,
  type Part,
  type Res,
} from '../utils/hardware'
import { onLinkClick } from '../../../utils/navigation'
import { absUrl, useSeo } from '../../../utils/seo'
import { paths, TAB_SEO } from '../../../utils/urls'
import { allowedBy, buildFacets, optionStates, type Picked } from '../utils/hwFacets'
import { FacetPanel } from './HardwareFacets'
import { HardwareParts } from './HardwareParts'
import { HardwareUseIcon } from './HardwareUseIcon'
import { PrebuiltPicks } from './HardwarePicks'
import { HardwarePrebuilt } from './HardwarePrebuilt'
import { HardwarePrices } from './HardwarePrices'
import { HardwareDatacenter } from './HardwareDatacenter'
import { ErrorState, Loader } from '../../../components/ui'
import { AiUses, DevUses, VideoSim } from './HardwareWorkloads'
import { MemorySlots } from './HardwareMemory'
import { BuyRow } from './HardwareBuy'

// PC 부품 — 기술 역설계가 "그 회사가 무엇으로 만들어졌나"라면 여기는 "내 책상 위 기계가 무엇으로
// 만들어졌나"다. 화면 셋:
//   /hardware          조립·시뮬레이션 — 용도와 예산을 고르면 조합과 '그래서 뭐가 되나'가 나온다
//   /hardware/parts    부품 비교 — 전문가용. 등급·스펙·원/성능으로 줄 세우고 골라 나란히 본다
//   /hardware/prices   가격 추이 — 매일 찍는 다나와 최저가. 색인하지 않는다(가격 DB 를 다시 싣지 않는다)
//   /hardware/datacenter AI 데이터센터 — 회사별 칩 수·성능 추정·금액·시장 조사(공개 자료 + 한 가지 잣대)

type Sub = 'build' | 'parts' | 'prices' | 'prebuilt' | 'datacenter'

export function HardwareNav({ current }: { current: Sub }) {
  const item = (key: Sub, to: string, label: string) => (
    <a
      href={to}
      onClick={onLinkClick(to)}
      className={`px-3 py-1.5 text-sm rounded-md transition ${
        current === key ? 'bg-(--color-accent)/12 text-(--color-accent) font-semibold' : 'text-(--color-muted) hover:text-(--color-text)'
      }`}
    >
      {label}
    </a>
  )
  return (
    <div className="flex items-center gap-1 px-4 pt-2 pb-1 border-b border-(--color-border) bg-(--color-panel)">
      {item('build', paths.hardware(), '조립·성능 예측')}
      {item('parts', paths.hardwareParts(), '부품 비교')}
      {item('prebuilt', paths.hardwarePrebuilt(), '완제품 분석')}
      {item('prices', paths.hardwarePrices(), '가격 추이')}
      {item('datacenter', paths.hardwareDatacenter(), 'AI 데이터센터')}
    </div>
  )
}

export function HardwareView({ seg }: { seg: string[] }) {
  const { data, error } = useHardware()
  const sub: Sub = seg[0] === 'parts' ? 'parts' : seg[0] === 'prices' ? 'prices' : seg[0] === 'prebuilt' ? 'prebuilt' : seg[0] === 'datacenter' ? 'datacenter' : 'build'
  if (error) return <ErrorState title="부품 데이터를 불러오지 못했습니다" detail={error} hint={<>public/hardware/parts.json 이 있는지 확인하세요.</>} />
  if (!data) return <Loader label="부품 데이터 불러오는 중…" />
  return (
    <div className="flex flex-col flex-1 min-h-0 min-w-0">
      <HardwareNav current={sub} />
      <main data-scroll className="flex-1 min-h-0 overflow-auto jd-panel">
        {sub === 'parts' ? (
          <HardwareParts data={data} partId={seg[1] ?? null} />
        ) : sub === 'prebuilt' ? (
          <HardwarePrebuilt data={data} itemKey={seg[1] ?? null} />
        ) : sub === 'prices' ? (
          <HardwarePrices data={data} />
        ) : sub === 'datacenter' ? (
          <HardwareDatacenter data={data} />
        ) : (
          <Builder data={data} />
        )}
      </main>
    </div>
  )
}

// ── 조립 ─────────────────────────────────────────────────────────────

const SAVED_KEY = 'hw.builds.v1'
interface Saved {
  name: string
  build: Build
  at: string
}

function loadSaved(): Saved[] {
  try {
    return JSON.parse(localStorage.getItem(SAVED_KEY) ?? '[]')
  } catch {
    return []
  }
}

function storeSaved(xs: Saved[]) {
  try {
    localStorage.setItem(SAVED_KEY, JSON.stringify(xs))
  } catch {
    /* 사생활 보호 모드 — 저장 없이 쓴다 */
  }
}

// 조합은 고른 금액을 채운다(planBuild). 100만원 아래로는 지금 부품값으로 켜지는 조합이 안 나온다.
const BUDGETS = [1_500_000, 2_000_000, 3_000_000, 4_000_000, 5_000_000, 6_000_000, 10_000_000, 12_000_000]

/** 이 부품을 사러 갈 곳 — 가격을 매긴 그 매물(CPU 는 정품 최저가). 매물이 없으면 이름으로 검색한다 */
function buyUrl(p: Part, data: HwData): string {
  const offers = data.prices[p.id]?.offers ?? []
  const pool = p.category === 'cpu' ? offers.filter((o) => o.name.includes('정품') && !o.name.includes('병행')) : []
  const o = [...(pool.length ? pool : offers)].sort((a, b) => a.price - b.price)[0]
  return o?.url ?? `https://search.danawa.com/dsearch.php?query=${encodeURIComponent(p.price_query?.q ?? p.name)}`
}

function Builder({ data }: { data: HwData }) {
  useSeo({ title: TAB_SEO.hardware.title, description: TAB_SEO.hardware.desc, canonical: absUrl(paths.hardware()) })
  const [useKey, setUseKey] = useState((data.uses.find((u) => u.key === 'game-qhd') ?? data.uses[0]).key)
  const [budget, setBudget] = useState(3_000_000)
  const use = data.uses.find((u) => u.key === useKey) ?? data.uses[0]
  const [plan, setPlan] = useState(() => planBuild(budget, use, data))
  const [build, setBuild] = useState<Build>(plan.build)
  const [copied, setCopied] = useState(false)
  const [saved, setSaved] = useState<Saved[]>(loadSaved)
  // 왼쪽 조건 필터 — 체크한 조건 안에서만 조합을 짠다(hwFacets.ts 머리말).
  const facets = useMemo(() => buildFacets(data), [data])
  const [picked, setPicked] = useState<Picked>({})
  const states = useMemo(() => optionStates(facets, picked, data), [facets, picked, data])
  // 용도·예산·조건을 바꾸면 추천을 다시 짠다. 손으로 고친 부품은 그 뒤에 다시 고친다.
  const replan = (nextUse: string, nextBudget: number, nextPicked: Picked) => {
    setUseKey(nextUse)
    setBudget(nextBudget)
    setPicked(nextPicked)
    const { allow, noGpu } = allowedBy(facets, nextPicked, data)
    const next = planBuild(nextBudget, data.uses.find((u) => u.key === nextUse) ?? data.uses[0], data, { allow, noGpu })
    setPlan(next)
    setBuild(next.build)
  }
  const choose = (nextUse: string, nextBudget: number) => replan(nextUse, nextBudget, picked)
  const toggle = (facet: string, value: string) => {
    const cur = picked[facet] ?? []
    replan(useKey, budget, { ...picked, [facet]: cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value] })
  }

  const byId = useMemo(() => new Map(data.parts.map((p) => [p.id, p])), [data.parts])
  const checks = checkBuild(build, data.parts)
  const { total, missing } = buildTotal(build, data.parts, data.prices)
  const gpu = build.gpu ? byId.get(build.gpu) : undefined
  const cpu = build.cpu ? byId.get(build.cpu) : undefined
  const ram = build.ram ? byId.get(build.ram) : undefined
  const errors = checks.filter((c) => c.level === 'error').length
  // 조건에 맞는 부품이 없어 비운 칸 — 조건끼리 부딪쳤거나 너무 좁게 골랐다
  const noGpu = allowedBy(facets, picked, data).noGpu || !!use.no_gpu
  const REQUIRED: Category[] = ['cpu', 'mainboard', 'ram', 'ssd', 'psu', 'cooler', 'case', ...(noGpu ? [] : (['gpu'] as Category[]))]
  const empty = REQUIRED.filter((c) => !build[c]).map((c) => data.categories.find((d) => d.key === c)?.name ?? c)

  const save = () => {
    const name = `${use.name} · ${won(total)}`
    const next = [{ name, build, at: new Date().toISOString().slice(0, 10) }, ...saved].slice(0, 12)
    setSaved(next)
    storeSaved(next)
  }

  return (
    <div className="max-w-[1600px] mx-auto p-4 flex flex-col gap-4">
      <header className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h1 className="text-lg font-bold text-(--color-text)">PC 조립 · 성능 예측</h1>
        <span className="text-xs text-(--color-muted)">
          용도와 예산을 고르면 부품 조합과 "그래서 무엇이 얼마나 돌아가나"를 보여 준다. 숫자는 추정이고 근거를 같이 적었다.
        </span>
        {data.priceDay && <span className="text-xs text-(--color-muted) ml-auto">가격 {data.priceDay} 다나와 최저가</span>}
      </header>

      <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 flex flex-col gap-3">
        <div className="flex flex-wrap gap-2">
          {data.uses.map((u) => (
            <button
              key={u.key}
              onClick={() => choose(u.key, u.budget ?? budget)}
              className={`px-3 py-2 rounded-lg border text-left transition flex items-center gap-2.5 ${
                u.key === useKey ? 'border-(--color-accent) bg-(--color-accent)/10' : 'border-(--color-border) hover:border-(--color-muted)'
              }`}
            >
              <HardwareUseIcon
                useKey={u.key}
                className={`w-8 h-8 shrink-0 ${u.key === useKey ? 'text-(--color-accent)' : 'text-(--color-muted)'}`}
              />
              <div>
                <div className="text-sm font-semibold text-(--color-text)">{u.name}</div>
                <div className="text-[11px] text-(--color-muted)">{u.plain}</div>
              </div>
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-(--color-muted)">예산</span>
          {BUDGETS.map((b) => (
            <button
              key={b}
              onClick={() => choose(useKey, b)}
              className={`px-2.5 py-1 rounded-md text-sm tabular-nums ${
                b === budget ? 'bg-(--color-accent) text-(--color-on-accent) font-semibold' : 'bg-(--color-band) text-(--color-text) hover:bg-(--color-border-soft)'
              }`}
            >
              {won(b)}
            </button>
          ))}
          <input
            type="range"
            min={1_000_000}
            max={13_000_000}
            step={100_000}
            value={budget}
            onChange={(e) => choose(useKey, Number(e.target.value))}
            className="flex-1 min-w-40 accent-(--color-accent)"
            aria-label="예산"
          />
          <span className="text-sm font-semibold tabular-nums w-20 text-right">{won(budget)}</span>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] 2xl:grid-cols-[minmax(0,6fr)_minmax(0,5fr)_minmax(0,4fr)] items-start">
        <FacetPanel facets={facets} picked={picked} states={states} onToggle={toggle} onReset={() => replan(useKey, budget, {})} />
        <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 flex flex-col gap-3 min-w-0">
          <div className="flex items-baseline gap-2">
            <h2 className="text-base font-bold">부품 조합</h2>
            <span className="ml-auto text-lg font-bold tabular-nums" data-nosnippet>
              {won(total)}
            </span>
          </div>
          <div className="text-[11px] text-(--color-muted) -mt-2 text-right" data-nosnippet>
            {total > budget ? `예산보다 ${won(total - budget)} 많다` : `예산 안 · ${won(budget - total)} 남음`}
            {missing.length > 0 && ` · 가격 모름 ${missing.length}개 제외`}
          </div>
          {build === plan.build && plan.stretched && (
            <div className="rounded-md border border-(--color-border) bg-(--color-band) px-3 py-2 text-xs text-(--color-muted)">
              예산 안에서는 {won(plan.stretched.within)}짜리까지만 짜진다(부품 급이 띄엄띄엄이다) — {won(budget)}대로 보고 한 급 위를 넣었다.
            </div>
          )}
          {build === plan.build && !plan.stretched && total < budget * 0.9 && (
            <div className="rounded-md border border-(--color-border) bg-(--color-band) px-3 py-2 text-xs text-(--color-muted)">
              {plan.next
                ? `${won(budget - total)} 남겼다 — 이 용도에서 더 빨라지는 다음 급은 ${won(plan.next.cost)}부터다.`
                : `이 용도에서는 이보다 돈을 더 써도 빨라지지 않는다 — 가장 빠른 부품까지 다 넣었다.`}
            </div>
          )}
          {build === plan.build && plan.next && (
            <button
              onClick={() => choose(useKey, Math.ceil(plan.next!.cost / 100_000) * 100_000)}
              className="text-left rounded-md border border-(--color-accent)/40 px-3 py-2 text-xs hover:bg-(--color-accent)/8"
            >
              <b className="text-(--color-accent)">한 단계 위 ↑</b> {won(plan.next.cost)} — {[plan.next.gpu, plan.next.cpu].filter(Boolean).join(' + ')} ·{' '}
              {use.key.startsWith('game') ? '예상 fps' : '성능'} +{Math.round(plan.next.gainPct)}%
            </button>
          )}
          {empty.length > 0 && (
            <div role="alert" className="rounded-md border border-(--color-red-400) bg-(--color-red-400)/8 px-3 py-2 text-sm text-(--color-red-400)">
              <b>{empty.join(' · ')} 을(를) 못 골랐다</b> — 왼쪽에서 고른 조건에 맞는 부품이 없다. 빨갛게 표시된 조건을 풀면 다시 짠다.
            </div>
          )}
          {errors > 0 && (
            <div role="alert" className="rounded-md border border-(--color-red-400) bg-(--color-red-400)/8 px-3 py-2 text-sm text-(--color-red-400)">
              <b>호환 안 됨 {errors}건</b> — 이대로는 조립이 안 된다. 빨간 칸을 바꾸면 풀린다.
            </div>
          )}
          <div className="flex flex-col divide-y divide-(--color-border-soft)">
            {CATEGORY_ORDER.map((cat) => (
              <PartPicker key={cat} cat={cat} data={data} build={build} onChange={(id) => setBuild({ ...build, [cat]: id || undefined })} />
            ))}
          </div>
          <MemorySlots data={data} build={build} />
          <ul className="flex flex-col gap-1 text-sm">
            {checks.map((c, i) => (
              <li key={i} className={c.level === 'error' ? 'text-(--color-red-400)' : c.level === 'warn' ? 'text-(--color-amber-400)' : 'text-(--color-muted)'}>
                {c.level === 'error' ? '✕' : c.level === 'warn' ? '!' : '✓'} {c.text}
              </li>
            ))}
          </ul>
          <BuyList
            data={data}
            build={build}
            total={total}
            copied={copied}
            onCopy={() => {
              const lines = CATEGORY_ORDER.filter((c) => build[c]).map((c) => {
                const p = byId.get(build[c]!)!
                const pr = priceOf(p, data.prices)
                const name = data.categories.find((d) => d.key === c)?.name ?? c
                const price = pr != null ? won(pr * (c === 'ram' ? 2 : 1)) : '가격 모름'
                return [name, `${p.name}${c === 'ram' ? ' ×2' : ''}`, price, buyUrl(p, data)].join('\t')
              })
              const text = [`${use.name} 조합 · 합계 ${won(total)}`, ...lines].join('\n')
              navigator.clipboard?.writeText(text).then(() => {
                setCopied(true)
                setTimeout(() => setCopied(false), 1500)
              }, () => {})
            }}
          />
          <div className="flex flex-wrap gap-2 items-center">
            <button onClick={save} className="px-3 py-1.5 text-sm rounded-md bg-(--color-accent) text-(--color-on-accent) font-semibold disabled:opacity-50" disabled={errors > 0 || empty.length > 0}>
              이 조합 저장
            </button>
            <span className="text-[11px] text-(--color-muted)">이 브라우저에만 저장된다</span>
          </div>
          {saved.length > 0 && (
            <div className="flex flex-col gap-1">
              <div className="text-xs font-semibold text-(--color-muted)">저장한 조합</div>
              {saved.map((s, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <button className="text-(--color-accent) hover:underline truncate" onClick={() => setBuild(s.build)}>
                    {s.name}
                  </button>
                  <span className="text-[11px] text-(--color-faint)">{s.at}</span>
                  <span className="ml-auto text-xs tabular-nums" data-nosnippet>
                    지금 {won(buildTotal(s.build, data.parts, data.prices).total)}
                  </span>
                  <button
                    className="text-xs text-(--color-faint) hover:text-(--color-red-400)"
                    onClick={() => {
                      const next = saved.filter((_, j) => j !== i)
                      setSaved(next)
                      storeSaved(next)
                    }}
                    aria-label="삭제"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
        {/* 같은 용도·예산의 완제품 — 넓은 화면에선 조합 옆, 좁으면 조합 아래 */}
        <div className="lg:col-span-2 2xl:col-span-1">
          <PrebuiltPicks data={data} use={use} budget={budget} build={build} buildCost={total} />
        </div>
      </div>

      <div className="flex flex-col gap-4 min-w-0">
          {errors > 0 && (
            <div className="rounded-md border border-(--color-red-400) bg-(--color-panel) px-3 py-2 text-sm text-(--color-red-400)">
              지금 조합은 조립이 안 된다 — 아래 숫자는 호환 문제를 고쳤다고 치고 계산한 값이다.
            </div>
          )}
          {/* 고른 용도의 성능이 맨 위 — 영상·개발·AI 는 게임 fps 보다 '이 일이 되나'가 먼저다 */}
          {(() => {
            const game = gpu ? <GameSim key={use.res} data={data} gpu={gpu} cpu={cpu ?? null} defaultRes={use.res} /> : null
            const ai = gpu ? <AiSim data={data} gpu={gpu} ram={ram} /> : null
            const dev = cpu ? <DevSim data={data} cpu={cpu} ram={ram} /> : null
            const video = gpu ? <VideoSim data={data} gpu={gpu} cpu={cpu} ram={ram} /> : null
            const lead = use.key === 'video' ? video : use.key === 'dev' ? dev : use.key === 'llm' ? ai : game
            const rest = [game, ai, dev, video].filter((x) => x && x !== lead)
            return (
              <>
                {!gpu && <div className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 text-sm text-(--color-muted)">그래픽카드가 없다(내장 그래픽) — 게임·AI·영상 예측은 그래픽카드를 고르면 나온다.</div>}
                {lead}
                <div className="grid gap-4 xl:grid-cols-2 items-start">
                  {rest.map((x, i) => (
                    <div key={i} className={`min-w-0 ${x === game ? 'xl:col-span-2' : ''}`}>
                      {x}
                    </div>
                  ))}
                </div>
              </>
            )
          })()}
      </div>
    </div>
  )
}

// 구입 목록 — 조합을 그대로 사러 간다. 각 줄은 가격을 매긴 그 매물(다나와)로 바로 간다.
// 복사하면 '분류 · 부품 · 가격 · 링크' 가 탭으로 나뉘어 붙는다(스프레드시트·메신저에 그대로 붙는다).
function BuyList({ data, build, total, copied, onCopy }: { data: HwData; build: Build; total: number; copied: boolean; onCopy: () => void }) {
  const byId = new Map(data.parts.map((p) => [p.id, p]))
  const rows = CATEGORY_ORDER.filter((c) => build[c] && byId.has(build[c]!)).map((c) => ({ c, p: byId.get(build[c]!)! }))
  if (!rows.length) return null
  return (
    <details className="rounded-md border border-(--color-border-soft)" open>
      <summary className="cursor-pointer px-3 py-2 text-sm font-semibold flex items-baseline gap-2">
        이 조합 사러 가기
        <span className="text-[11px] font-normal text-(--color-muted)">부품마다 오늘 최저가 매물로 연결</span>
      </summary>
      <ul className="px-3 pb-2 flex flex-col gap-1 text-xs">
        {rows.map(({ c, p }) => {
          const pr = priceOf(p, data.prices)
          return (
            <li key={c} className="flex items-baseline gap-2">
              <span className="w-14 shrink-0 text-(--color-muted)">{data.categories.find((d) => d.key === c)?.name ?? c}</span>
              <a href={buyUrl(p, data)} target="_blank" rel="noopener noreferrer nofollow" className="truncate text-(--color-accent) hover:underline">
                {p.name}
                {c === 'ram' && ' ×2'} ↗
              </a>
              <span className="ml-auto tabular-nums shrink-0" data-nosnippet>
                {pr != null ? won(pr * (c === 'ram' ? 2 : 1)) : '—'}
              </span>
            </li>
          )
        })}
      </ul>
      <div className="px-3 pb-2 flex items-center gap-2">
        <button onClick={onCopy} className="px-2.5 py-1 text-xs rounded-md bg-(--color-band) hover:bg-(--color-border-soft)">
          {copied ? '복사했다 ✓' : '목록 복사'}
        </button>
        <span className="text-[11px] text-(--color-muted)" data-nosnippet>
          합계 {won(total)} · 급(級) 부품은 같은 급의 인기 제품으로 간다
        </span>
      </div>
    </details>
  )
}

// 고르는 목록 — 지금 조합에 넣었을 때 '안 된다'가 생기는 후보는 이유를 달고 아래로 내린다.
// 고를 수는 있게 둔다(무엇이 왜 안 되는지 직접 보는 것도 배우는 일이다). 골랐으면 그 칸이 빨개진다.
function PartPicker({ cat, data, build, onChange }: { cat: Category; data: HwData; build: Build; onChange: (id: string) => void }) {
  const def = data.categories.find((c) => c.key === cat)
  const value = build[cat]
  const opts = data.parts
    .filter((p) => p.category === cat)
    .map((p) => ({ p, why: conflictsOf(cat, p.id, build, data.parts) }))
  const okOpts = opts.filter((o) => !o.why.length)
  const badOpts = opts.filter((o) => o.why.length)
  const cur = opts.find((o) => o.p.id === value)
  const tier = cur ? tierOf(cur.p, data.categories) : null
  const price = cur ? priceOf(cur.p, data.prices) : null
  const bad = !!cur?.why.length
  const label = (p: Part) => {
    const pr = priceOf(p, data.prices)
    return `${p.name} ${pr != null ? `· ${won(pr)}` : '· 가격 모름'}`
  }
  return (
    <div className={`py-2 grid grid-cols-[5.5rem_minmax(0,1fr)_auto] items-center gap-x-2 gap-y-1 ${bad ? 'bg-(--color-red-400)/6 -mx-2 px-2 rounded' : ''}`}>
      <div className="text-xs font-semibold text-(--color-muted)" title={def?.why}>
        {def?.name ?? cat}
      </div>
      <div className="min-w-0 flex items-center gap-2">
        {tier && <TierBadge tier={tier.tier} />}
        <select
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={bad}
          className={`min-w-0 flex-1 bg-transparent text-sm text-(--color-text) border rounded px-1.5 py-1 ${
            bad ? 'border-(--color-red-400)' : 'border-(--color-border-soft)'
          }`}
        >
          <option value="">{cat === 'hdd' ? '없음' : '고르기'}</option>
          {okOpts.map(({ p }) => (
            <option key={p.id} value={p.id}>
              {label(p)}
            </option>
          ))}
          {badOpts.length > 0 && (
            <optgroup label="✕ 지금 조합과 호환 안 됨">
              {badOpts.map(({ p, why }) => (
                <option key={p.id} value={p.id}>
                  ✕ {p.name} — {why[0].split(' — ')[0]}
                </option>
              ))}
            </optgroup>
          )}
        </select>
      </div>
      <div className="text-sm tabular-nums text-right w-20" data-nosnippet>
        {price != null ? won(price * (cat === 'ram' ? 2 : 1)) : '—'}
        {cat === 'ram' && price != null && <div className="text-[10px] text-(--color-faint)">두 장</div>}
      </div>
      {cur && !bad && <BuyRow data={data} part={cur.p} />}
      {bad && (
        <div className="col-start-2 col-span-2 text-xs text-(--color-red-400)">
          {cur!.why.map((w) => (
            <div key={w}>✕ {w}</div>
          ))}
        </div>
      )}
    </div>
  )
}

export function TierBadge({ tier }: { tier: string }) {
  const shade: Record<string, number> = { S: 100, A: 80, B: 58, C: 38, D: 22 }
  const s = shade[tier] ?? 30
  return (
    <span
      className="inline-flex items-center justify-center w-6 h-6 rounded text-xs font-bold shrink-0"
      style={{
        background: `color-mix(in srgb, var(--color-accent) ${s}%, var(--color-panel))`,
        color: s >= 58 ? 'var(--color-on-accent)' : 'var(--color-text)',
      }}
      title={`${tier} 등급`}
    >
      {tier}
    </span>
  )
}

function Tone({ tone, children }: { tone: 'good' | 'ok' | 'bad'; children: React.ReactNode }) {
  const c = tone === 'good' ? 'text-(--color-accent)' : tone === 'ok' ? 'text-(--color-text)' : 'text-(--color-red-400)'
  return <span className={c}>{children}</span>
}

function GameSim({ data, gpu, cpu, defaultRes }: { data: HwData; gpu: Part; cpu: Part | null; defaultRes: Res }) {
  // 용도가 바뀌면 key 가 바뀌어 새로 그려진다 — 해상도는 그 용도의 기본값에서 다시 시작한다.
  const [res, setRes] = useState<Res>(defaultRes)
  const rows = data.bench.games.map((g) => ({ g, e: estimateFps(g, res, gpu, cpu) }))
  const max = Math.max(...rows.map((r) => Math.min(r.e.fps, 400)), 60)
  return (
    <div className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline gap-2">
        <h2 className="text-base font-bold">게임은 얼마나 돌아가나</h2>
        <div className="ml-auto inline-flex rounded-md border border-(--color-border) overflow-hidden">
          {(Object.keys(RES_LABEL) as Res[]).map((r) => (
            <button key={r} onClick={() => setRes(r)} className={`px-2.5 py-1 text-xs ${r === res ? 'bg-(--color-accent) text-(--color-on-accent) font-semibold' : 'text-(--color-muted)'}`}>
              {RES_LABEL[r]}
            </button>
          ))}
        </div>
      </div>
      <div className="flex flex-col gap-1.5">
        {rows.map(({ g, e }) => {
          const w = fpsWord(e.fps)
          return (
            <div key={g.key} className="grid grid-cols-[8.5rem_minmax(0,1fr)_3.5rem] sm:grid-cols-[10rem_minmax(0,1fr)_3.5rem_13rem] items-center gap-2 text-sm">
              <div className="min-w-0">
                <div className="truncate font-medium">{g.name}</div>
                <div className="text-[10px] text-(--color-faint) truncate">{g.preset}</div>
              </div>
              <div className="relative h-4 rounded bg-(--color-band)">
                <div className="absolute inset-y-0 left-0 rounded bg-(--color-accent)/70" style={{ width: `${(Math.min(e.fps, 400) / max) * 100}%` }} />
                <div className="absolute inset-y-0 w-px bg-(--color-text)/40" style={{ left: `${(60 / max) * 100}%` }} title="60fps" />
              </div>
              <div className="text-right font-bold tabular-nums">{e.fps}</div>
              <div className="hidden sm:block text-xs">
                <Tone tone={w.tone}>{w.word}</Tone>
                {e.bound === 'cpu' && <span className="text-(--color-faint)"> · CPU 가 천장</span>}
                {e.vramShort > 0 && <span className="text-(--color-red-400)"> · VRAM {e.vramShort}GB 부족</span>}
              </div>
            </div>
          )
        })}
      </div>
      <details className="text-xs text-(--color-muted)">
        <summary className="cursor-pointer">어떻게 계산했나</summary>
        <p className="mt-1">{data.bench.model}</p>
        <p className="mt-1">
          {gpu.name} 성능 지수 {gpu.perf.index}
          {cpu && ` · ${cpu.name} 게임 지수 ${cpu.perf.index}`}. 세로선은 60fps. 기준값은 아직 {data.bench.games.every((g) => g.confidence === 'seed') ? '초기 추정값이라 실측 리뷰로 바꾸는 중이다' : '리뷰 실측에서 잡았다'}.
        </p>
      </details>
    </div>
  )
}

function AiSim({ data, gpu, ram }: { data: HwData; gpu: Part; ram?: Part }) {
  const ramBw = ram ? Number(ram.specs.dual_bandwidth_gbs) : null
  const img = estimateImageSec(data.bench, gpu, data.parts)
  const vram = Number(gpu.specs.vram_gb)
  return (
    <div className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 flex flex-col gap-3">
      <div className="flex items-baseline gap-2">
        <h2 className="text-base font-bold">AI 는 얼마나 돌아가나</h2>
        <span className="text-xs text-(--color-muted)">
          VRAM {vram}GB · 대역폭 {Number(gpu.specs.bandwidth_gbs).toLocaleString()}GB/s · {String(gpu.specs.stack)}
        </span>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[11px] text-(--color-muted) text-left">
            <th className="font-normal pb-1">언어 모델(4비트 양자화)</th>
            <th className="font-normal pb-1 text-right">토큰/초</th>
            <th className="font-normal pb-1 pl-3 hidden sm:table-cell">체감</th>
          </tr>
        </thead>
        <tbody>
          {data.bench.llm.models.map((m) => {
            const e = estimateLlm(data.bench, m, gpu, ramBw)
            const w = tpsWord(data.bench, e.tps)
            return (
              <tr key={m.key} className="border-t border-(--color-border-soft)">
                <td className="py-1.5">
                  <div className="font-medium">{m.name}</div>
                  <div className="text-[10px] text-(--color-faint)">
                    {m.size_gb}GB · {m.plain}
                  </div>
                </td>
                <td className="text-right font-bold tabular-nums">{e.tps >= 10 ? Math.round(e.tps) : e.tps.toFixed(1)}</td>
                <td className="pl-3 text-xs hidden sm:table-cell">
                  <Tone tone={w.tone}>{w.word}</Tone>
                  {!e.fits && <div className="text-[10px] text-(--color-faint)">{e.note}</div>}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <div className="grid sm:grid-cols-2 gap-3 text-sm">
        <div className="rounded-lg bg-(--color-band) p-3">
          <div className="text-[11px] text-(--color-muted)">{data.bench.image.name}</div>
          <div className="text-xl font-bold tabular-nums">{img == null ? '못 돌린다' : `${img.toFixed(1)}초 / 장`}</div>
          {img == null && <div className="text-[11px] text-(--color-faint)">VRAM {data.bench.image.min_vram_gb}GB 이상 필요</div>}
        </div>
        <div className="rounded-lg bg-(--color-band) p-3">
          <div className="text-[11px] text-(--color-muted)">미세조정(학습)</div>
          <ul className="text-xs flex flex-col gap-0.5 mt-1">
            {data.bench.finetune.map((f) => (
              <li key={f.key}>
                <Tone tone={vram >= f.vram_gb ? 'good' : 'bad'}>{vram >= f.vram_gb ? '✓' : '✕'}</Tone> {f.name}
                <span className="text-(--color-faint)"> · {f.vram_gb}GB</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <details className="text-xs text-(--color-muted)">
        <summary className="cursor-pointer">어떻게 계산했나</summary>
        <p className="mt-1">{data.bench.llm.model}</p>
        <p className="mt-1">
          효율 {data.bench.llm.efficiency} · 소프트웨어 보정 {String(gpu.specs.stack)} {data.bench.llm.stack_factor[String(gpu.specs.stack)] ?? 0.8}(CUDA = 1).
          넘친 부분은 메모리 {ram ? `${ram.name} 두 장(${ramBw}GB/s)` : '60GB/s 가정'}에서 읽는다.
        </p>
        <p className="mt-1">{data.bench.image.model}</p>
      </details>
      <AiUses data={data} gpu={gpu} ram={ram} />
    </div>
  )
}

function DevSim({ data, cpu, ram }: { data: HwData; cpu: Part; ram?: Part }) {
  const mins = estimateBuildMin(data.bench, cpu)
  const gb = ram ? Number(ram.specs.capacity_gb) * 2 : null
  return (
    <div className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 flex flex-col gap-2">
      <h2 className="text-base font-bold">개발 작업은</h2>
      <div className="grid sm:grid-cols-2 gap-3 text-sm">
        <div className="rounded-lg bg-(--color-band) p-3">
          <div className="text-[11px] text-(--color-muted)">{data.bench.dev.name}</div>
          <div className="text-xl font-bold tabular-nums">약 {mins < 10 ? mins.toFixed(1) : Math.round(mins)}분</div>
          <div className="text-[11px] text-(--color-faint)">
            {cpu.name} 멀티 지수 {cpu.perf.multi} · {cpu.specs.cores}코어 {cpu.specs.threads}스레드
          </div>
        </div>
        <div className="rounded-lg bg-(--color-band) p-3">
          <div className="text-[11px] text-(--color-muted)">메모리 {gb ?? '—'}GB 로 동시에 띄우는 것</div>
          <div className="text-xs mt-1">
            {gb == null
              ? '메모리를 고르면 나온다'
              : gb >= 64
                ? 'IDE 여러 개 + 도커 컨테이너 10개 이상 + 로컬 쿠버네티스까지 여유'
                : gb >= 32
                  ? 'IDE 두어 개 + 도커 컨테이너 몇 개 + 브라우저 탭 많이 — 대부분의 개발에 충분'
                  : 'IDE 하나 + 브라우저. 도커를 여러 개 띄우면 스왑이 난다'}
          </div>
        </div>
      </div>
      <DevUses data={data} cpu={cpu} ram={ram} />
    </div>
  )
}
