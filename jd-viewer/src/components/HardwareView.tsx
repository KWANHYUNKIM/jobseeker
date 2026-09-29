import { useMemo, useState } from 'react'
import {
  CATEGORY_ORDER,
  RES_LABEL,
  autoBuild,
  buildTotal,
  checkBuild,
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
} from '../lib/hardware'
import { onLinkClick } from '../lib/router'
import { absUrl, useSeo } from '../lib/seo'
import { paths, TAB_SEO } from '../lib/urls'
import { HardwareParts } from './HardwareParts'
import { HardwarePrices } from './HardwarePrices'
import { ErrorState, Loader } from './ui'

// PC 부품 — 기술 역설계가 "그 회사가 무엇으로 만들어졌나"라면 여기는 "내 책상 위 기계가 무엇으로
// 만들어졌나"다. 화면 셋:
//   /hardware          조립·시뮬레이션 — 용도와 예산을 고르면 조합과 '그래서 뭐가 되나'가 나온다
//   /hardware/parts    부품 비교 — 전문가용. 등급·스펙·원/성능으로 줄 세우고 골라 나란히 본다
//   /hardware/prices   가격 추이 — 매일 찍는 다나와 최저가. 색인하지 않는다(가격 DB 를 다시 싣지 않는다)

type Sub = 'build' | 'parts' | 'prices'

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
      {item('prices', paths.hardwarePrices(), '가격 추이')}
    </div>
  )
}

export function HardwareView({ seg }: { seg: string[] }) {
  const { data, error } = useHardware()
  const sub: Sub = seg[0] === 'parts' ? 'parts' : seg[0] === 'prices' ? 'prices' : 'build'
  if (error) return <ErrorState title="부품 데이터를 불러오지 못했습니다" detail={error} hint={<>public/hardware/parts.json 이 있는지 확인하세요.</>} />
  if (!data) return <Loader label="부품 데이터 불러오는 중…" />
  return (
    <div className="flex flex-col flex-1 min-h-0 min-w-0">
      <HardwareNav current={sub} />
      <main data-scroll className="flex-1 min-h-0 overflow-auto jd-panel">
        {sub === 'parts' ? (
          <HardwareParts data={data} partId={seg[1] ?? null} />
        ) : sub === 'prices' ? (
          <HardwarePrices data={data} />
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

const BUDGETS = [1_500_000, 2_000_000, 3_000_000, 4_000_000, 6_000_000, 10_000_000]

function Builder({ data }: { data: HwData }) {
  useSeo({ title: TAB_SEO.hardware.title, description: TAB_SEO.hardware.desc, canonical: absUrl(paths.hardware()) })
  const [useKey, setUseKey] = useState(data.uses[1]?.key ?? data.uses[0].key)
  const [budget, setBudget] = useState(3_000_000)
  const use = data.uses.find((u) => u.key === useKey) ?? data.uses[0]
  const [build, setBuild] = useState<Build>(() => autoBuild(budget, use, data))
  const [saved, setSaved] = useState<Saved[]>(loadSaved)
  // 용도·예산을 바꾸면 추천을 다시 짠다. 손으로 고친 부품은 그 뒤에 다시 고친다.
  const choose = (nextUse: string, nextBudget: number) => {
    setUseKey(nextUse)
    setBudget(nextBudget)
    setBuild(autoBuild(nextBudget, data.uses.find((u) => u.key === nextUse) ?? data.uses[0], data))
  }

  const byId = useMemo(() => new Map(data.parts.map((p) => [p.id, p])), [data.parts])
  const checks = checkBuild(build, data.parts)
  const { total, missing } = buildTotal(build, data.parts, data.prices)
  const gpu = build.gpu ? byId.get(build.gpu) : undefined
  const cpu = build.cpu ? byId.get(build.cpu) : undefined
  const ram = build.ram ? byId.get(build.ram) : undefined
  const errors = checks.filter((c) => c.level === 'error').length

  const save = () => {
    const name = `${use.name} · ${won(total)}`
    const next = [{ name, build, at: new Date().toISOString().slice(0, 10) }, ...saved].slice(0, 12)
    setSaved(next)
    storeSaved(next)
  }

  return (
    <div className="max-w-[1400px] mx-auto p-4 flex flex-col gap-4">
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
              onClick={() => choose(u.key, budget)}
              className={`px-3 py-2 rounded-lg border text-left transition ${
                u.key === useKey ? 'border-(--color-accent) bg-(--color-accent)/10' : 'border-(--color-border) hover:border-(--color-muted)'
              }`}
            >
              <div className="text-sm font-semibold text-(--color-text)">{u.name}</div>
              <div className="text-[11px] text-(--color-muted)">{u.plain}</div>
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
            max={12_000_000}
            step={100_000}
            value={budget}
            onChange={(e) => choose(useKey, Number(e.target.value))}
            className="flex-1 min-w-40 accent-(--color-accent)"
            aria-label="예산"
          />
          <span className="text-sm font-semibold tabular-nums w-20 text-right">{won(budget)}</span>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
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
          <div className="flex flex-col divide-y divide-(--color-border-soft)">
            {CATEGORY_ORDER.map((cat) => (
              <PartPicker key={cat} cat={cat} data={data} value={build[cat]} onChange={(id) => setBuild({ ...build, [cat]: id || undefined })} />
            ))}
          </div>
          <ul className="flex flex-col gap-1 text-sm">
            {checks.map((c, i) => (
              <li key={i} className={c.level === 'error' ? 'text-(--color-red-400)' : c.level === 'warn' ? 'text-(--color-amber-400)' : 'text-(--color-muted)'}>
                {c.level === 'error' ? '✕' : c.level === 'warn' ? '!' : '✓'} {c.text}
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-2 items-center">
            <button onClick={save} className="px-3 py-1.5 text-sm rounded-md bg-(--color-accent) text-(--color-on-accent) font-semibold disabled:opacity-50" disabled={errors > 0}>
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

        <section className="flex flex-col gap-4 min-w-0">
          {gpu ? <GameSim key={use.res} data={data} gpu={gpu} cpu={cpu ?? null} defaultRes={use.res} /> : <div className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 text-sm text-(--color-muted)">그래픽카드를 고르면 게임 성능이 나온다.</div>}
          {gpu && <AiSim data={data} gpu={gpu} ram={ram} />}
          {cpu && <DevSim data={data} cpu={cpu} ram={ram} />}
        </section>
      </div>
    </div>
  )
}

function PartPicker({ cat, data, value, onChange }: { cat: Category; data: HwData; value?: string; onChange: (id: string) => void }) {
  const def = data.categories.find((c) => c.key === cat)
  const opts = data.parts.filter((p) => p.category === cat)
  const cur = opts.find((p) => p.id === value)
  const tier = cur ? tierOf(cur, data.categories) : null
  const price = cur ? priceOf(cur, data.prices) : null
  return (
    <div className="py-2 grid grid-cols-[5.5rem_minmax(0,1fr)_auto] items-center gap-2">
      <div className="text-xs font-semibold text-(--color-muted)" title={def?.why}>
        {def?.name ?? cat}
      </div>
      <div className="min-w-0 flex items-center gap-2">
        {tier && <TierBadge tier={tier.tier} />}
        <select
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value)}
          className="min-w-0 flex-1 bg-transparent text-sm text-(--color-text) border border-(--color-border-soft) rounded px-1.5 py-1"
        >
          <option value="">{cat === 'hdd' ? '없음' : '고르기'}</option>
          {opts.map((p) => {
            const pr = priceOf(p, data.prices)
            return (
              <option key={p.id} value={p.id}>
                {p.name} {pr != null ? `· ${won(pr)}` : '· 가격 모름'}
              </option>
            )
          })}
        </select>
      </div>
      <div className="text-sm tabular-nums text-right w-20" data-nosnippet>
        {price != null ? won(price * (cat === 'ram' ? 2 : 1)) : '—'}
        {cat === 'ram' && price != null && <div className="text-[10px] text-(--color-faint)">두 장</div>}
      </div>
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
    </div>
  )
}
