import { useMemo } from 'react'
import { won, type Build, type HwData, type UseDef } from '../lib/hardware'
import { analyze, perfOf, usePrebuilt, type PerfUse, type Prebuilt } from '../lib/prebuilt'
import { onLinkClick } from '../lib/router'
import { paths } from '../lib/urls'

// 조립 화면 오른쪽 — '같은 돈이면 완제품은?' 지금 고른 용도·예산에 맞는 완제품 중 성능이 높은 것을 둔다.
// 완제품 분석(/hardware/prebuilt)의 성능 우선 순위를 예산 창(예산의 60~110%)으로 자른 것이다.
// 조립이 안 되는 구성(호환 오류)은 뺀다. 각 줄은 다나와 상품 페이지로 바로 사러 간다.
//
// 사무용은 성능 우선 순위에 없는 용도라(그래픽카드 없음) CPU 지수로 줄 세운다. 다나와 상품 페이지를
// 아직 못 읽어 구성을 모르는 사무용 PC 는 '구성 확인 전'으로 따로 보인다 — 추측으로 순위에 넣지 않는다.

const PERF_OF_USE: Record<string, PerfUse> = {
  'game-fhd': 'game-qhd',
  'game-qhd': 'game-qhd',
  'game-4k': 'game-4k',
  llm: 'ai',
  dev: 'build',
  video: 'build',
}

const OFFICE_NAME = /오피스|사무|업무|홈|office/i

interface Row {
  it: Prebuilt
  score: number | null
  display: string
  premiumPct: number | null
  /** 구성을 못 읽어 상품명으로 잰 값 */
  guessed?: boolean
}

export function PrebuiltPicks({ data, use, budget, build, buildCost }: { data: HwData; use: UseDef; budget: number; build: Build; buildCost: number }) {
  const pb = usePrebuilt()
  const office = !!use.no_gpu
  const perfUse = PERF_OF_USE[use.key] ?? 'game-qhd'

  // 우리 조합도 같은 잣대로 잰다 — 완제품과 나란히 놓으려면 같은 계산이어야 한다
  const mine = useMemo(() => {
    const byId = new Map(data.parts.map((p) => [p.id, p]))
    if (office) {
      const cpu = build.cpu ? byId.get(build.cpu) : undefined
      return cpu ? { score: cpu.perf.index, display: `CPU 지수 ${cpu.perf.index}` } : null
    }
    const ram = build.ram ? byId.get(build.ram) : undefined
    // 구성(comp)을 채워 두어야 perfOf 가 이름에서 부품을 짐작하지 않는다
    const fake = {
      name: '직접 조립',
      mapped: { cpu: build.cpu ?? null, gpu: build.gpu ?? null, ram: build.ram ?? null },
      comp: { cpu: build.cpu ?? null, gpu: build.gpu ?? '내장 그래픽', ram_gb: ram ? Number(ram.specs.capacity_gb) * 2 : null },
    } as unknown as Prebuilt
    const s = perfOf(fake, data, perfUse)
    return s.score == null ? null : { score: s.score, display: s.display }
  }, [data, build, office, perfUse])

  const { rows, pending } = useMemo(() => {
    if (!pb) return { rows: [] as Row[], pending: [] as Prebuilt[] }
    const inWindow = pb.items.filter((it) => it.last_seen === pb.day && it.price >= budget * 0.6 && it.price <= budget * 1.1)
    const byId = new Map(data.parts.map((p) => [p.id, p]))
    const out: Row[] = []
    const pending: Prebuilt[] = []
    for (const it of inWindow) {
      const integrated = !it.mapped?.gpu && (!it.comp?.gpu || it.comp.gpu.includes('내장'))
      if (office) {
        if (!it.comp) {
          if (OFFICE_NAME.test(it.name)) pending.push(it)
          continue
        }
        if (!integrated) continue
        const cpu = it.mapped?.cpu ? byId.get(it.mapped.cpu) : undefined
        if (!cpu) continue
        const a = analyze(it, data)
        if (a.errors.length) continue
        out.push({ it, score: cpu.perf.index, display: `CPU 지수 ${cpu.perf.index}`, premiumPct: a.premiumPct })
      } else {
        // 구성을 아직 못 읽은 것도 perfOf 가 상품명의 CPU·그래픽카드로 잰다
        if (it.comp && integrated) continue
        const s = perfOf(it, data, perfUse)
        if (s.score == null) continue
        const a = analyze(it, data)
        if (a.errors.length) continue
        out.push({ it, score: s.score, display: s.display, premiumPct: a.premiumPct, guessed: !it.comp })
      }
    }
    // 성능이 먼저, 같은 성능이면 싼 쪽. 같은 모델의 용량만 다른 매물은 하나만(가장 빠르고 싼 것)
    out.sort((x, y) => (y.score ?? 0) - (x.score ?? 0) || x.it.price - y.it.price)
    const seen = new Set<string>()
    const uniq = out.filter((r) => {
      const k = `${r.it.mapped?.cpu}|${r.it.mapped?.gpu}|${r.it.brand ?? r.it.name.split(' ')[0]}`
      if (seen.has(k)) return false
      seen.add(k)
      return true
    })
    pending.sort((a, b) => Math.abs(a.price - budget) - Math.abs(b.price - budget))
    return { rows: uniq.slice(0, 4), pending: pending.slice(0, 3) }
  }, [pb, data, budget, office, perfUse])

  const rel = (score: number | null) => {
    if (score == null || !mine) return null
    // 빌드 시간은 음수(분)로 들어온다 — 짧을수록 빠르다
    const r = perfUse === 'build' && !office ? mine.score / score : score / mine.score
    return (r - 1) * 100
  }

  return (
    <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 flex flex-col gap-3 min-w-0">
      <div className="flex items-baseline gap-2">
        <h2 className="text-base font-bold">같은 돈이면 완제품은</h2>
        <a href={paths.hardwarePrebuilt()} onClick={onLinkClick(paths.hardwarePrebuilt())} className="ml-auto text-xs text-(--color-accent) hover:underline">
          완제품 분석 →
        </a>
      </div>
      <p className="text-[11px] text-(--color-muted) -mt-2">
        {won(budget * 0.6)}~{won(budget * 1.1)} 완제품 중 {office ? 'CPU 성능' : '이 용도의 예상 성능'}이 높은 순. 조립·검수·A/S 가 붙는 대신 부품값보다 비싸다.
      </p>
      {mine && (
        <div className="rounded-md bg-(--color-band) px-3 py-2 text-xs flex items-baseline gap-2" data-nosnippet>
          <span className="text-(--color-muted)">직접 조립(왼쪽 조합)</span>
          <span className="ml-auto font-semibold tabular-nums">{mine.display}</span>
          <span className="tabular-nums">{won(buildCost)}</span>
        </div>
      )}
      {!pb ? (
        <div className="text-xs text-(--color-muted)">완제품 불러오는 중…</div>
      ) : rows.length === 0 && pending.length === 0 ? (
        <div className="text-xs text-(--color-muted)">
          이 예산대에 구성까지 확인한 완제품이 아직 없다 — 완제품은 매일 다나와에서 새로 받고 상품 페이지를 차례로 읽는다.
        </div>
      ) : null}
      <ul className="flex flex-col gap-2">
        {rows.map((r) => {
          const d = rel(r.score)
          const diff = r.it.price - buildCost
          return (
            <li key={r.it.key} className="rounded-md border border-(--color-border-soft) p-2.5 flex flex-col gap-1">
              <a
                href={paths.hardwarePrebuiltItem(r.it.key)}
                onClick={onLinkClick(paths.hardwarePrebuiltItem(r.it.key))}
                className="text-sm font-medium text-(--color-text) hover:underline line-clamp-2"
              >
                {r.it.name}
              </a>
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-xs" data-nosnippet>
                <span className="text-base font-bold tabular-nums">{won(r.it.price)}</span>
                <span className="font-semibold">{r.display}</span>
                {d != null && Math.abs(d) >= 1 && (
                  <span className={d > 0 ? 'text-(--color-accent)' : 'text-(--color-muted)'}>
                    조립보다 {d > 0 ? `${Math.round(d)}% 빠르고` : `${Math.round(-d)}% 느리고`} {diff >= 0 ? `${won(diff)} 비싸다` : `${won(-diff)} 싸다`}
                  </span>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-(--color-muted)">
                {r.guessed && <span>상품명으로 잰 값</span>}
                {r.premiumPct != null && <span>부품값 대비 {r.premiumPct >= 0 ? '+' : ''}{Math.round(r.premiumPct)}%</span>}
                {r.it.rating && (
                  <span>
                    ★ {r.it.rating.avg.toFixed(1)} · 리뷰 {r.it.rating.count.toLocaleString()}
                  </span>
                )}
                <a
                  href={r.it.url}
                  target="_blank"
                  rel="noopener noreferrer nofollow"
                  className="ml-auto px-2.5 py-1 rounded-md bg-(--color-accent) text-(--color-on-accent) font-semibold hover:opacity-90"
                >
                  {r.it.source === 'naver' ? '네이버쇼핑' : '다나와'}에서 사기 ↗
                </a>
              </div>
            </li>
          )
        })}
      </ul>
      {pending.length > 0 && (
        <div className="flex flex-col gap-1">
          <div className="text-[11px] font-semibold text-(--color-muted)">구성 확인 전 — 상품 페이지에서 CPU·메모리를 보고 고른다</div>
          {pending.map((it) => (
            <div key={it.key} className="flex items-baseline gap-2 text-xs">
              <a href={it.url} target="_blank" rel="noopener noreferrer nofollow" className="truncate text-(--color-accent) hover:underline">
                {it.name}
              </a>
              <span className="ml-auto tabular-nums shrink-0" data-nosnippet>
                {won(it.price)}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
