import {
  airflowFor,
  caseFans,
  caseHeat,
  caseSize,
  fanLayout,
  type CaseFan,
  type FanPos,
  type HwData,
  type Model,
} from '../utils/hardware'

// 케이스 제품 한 줄을 펼치면 나오는 것 — 크기·바람길 그림과 '이 조합의 열을 빼나'.
//
// 그림은 옆에서 본 모습이다(깊이 × 높이). 왼쪽이 앞이다. 기본으로 들어 있는 팬은 칠하고, 비어 있는
// 팬 자리는 점선으로 둔다. 화살표는 흡기(앞·옆·아래 → 안)와 배기(안 → 뒤·위)다.

const IN = 'var(--color-sky-400)'
const OUT = 'var(--color-red-400)'

export function CaseDrawing({ specs }: { specs: Model['specs'] }) {
  const d = Number(specs.depth_mm), h = Number(specs.height_mm)
  if (!d || !h) return null
  const f = caseFans(specs)
  const scale = 220 / Math.max(d, h)
  const W = d * scale, H = h * scale
  const x0 = 34, y0 = 24
  // 자리마다 [기본 팬 수, 전체 자리 수]
  const at = (xs: CaseFan[] | null, pos: FanPos) => (xs ?? []).filter((x) => x.pos === pos).reduce((a, x) => a + Number(x.n || 0), 0)
  const slot = (pos: FanPos) => ({ inc: at(f.included, pos), all: Math.max(at(f.mounts, pos), at(f.included, pos)) })
  const r = Math.min(W, H) * 0.075
  const fansAlong = (pos: FanPos, n: { inc: number; all: number }) => {
    const out: { cx: number; cy: number; on: boolean }[] = []
    for (let k = 0; k < n.all; k++) {
      const t = (k + 0.5) / n.all
      const on = k < n.inc
      if (pos === 'front') out.push({ cx: x0 + r + 2, cy: y0 + H * (0.15 + 0.7 * t), on })
      if (pos === 'rear') out.push({ cx: x0 + W - r - 2, cy: y0 + H * (0.12 + 0.2 * t), on })
      if (pos === 'top') out.push({ cx: x0 + W * (0.2 + 0.6 * t), cy: y0 + r + 2, on })
      if (pos === 'bottom') out.push({ cx: x0 + W * (0.2 + 0.6 * t), cy: y0 + H - r - 2, on })
      if (pos === 'side') out.push({ cx: x0 + W * 0.5 + (t - 0.5) * r * 2.6 * n.all, cy: y0 + H * 0.55, on })
    }
    return out
  }
  const positions: FanPos[] = ['front', 'side', 'bottom', 'top', 'rear']
  const arrow = (x1: number, y1: number, x2: number, y2: number, c: string, k: string) => (
    <line key={k} x1={x1} y1={y1} x2={x2} y2={y2} stroke={c} strokeWidth={2} markerEnd={`url(#arr-${c === IN ? 'in' : 'out'})`} />
  )
  const arrows = [
    slot('front').inc > 0 && arrow(4, y0 + H * 0.5, x0 - 2, y0 + H * 0.5, IN, 'f'),
    slot('bottom').inc > 0 && arrow(x0 + W * 0.5, y0 + H + 22, x0 + W * 0.5, y0 + H + 2, IN, 'b'),
    slot('side').inc > 0 && arrow(x0 + W * 0.5, y0 + H * 0.55 + r * 2.4, x0 + W * 0.5, y0 + H * 0.55 + r * 1.2, IN, 's'),
    slot('rear').inc > 0 && arrow(x0 + W + 2, y0 + H * 0.22, x0 + W + 28, y0 + H * 0.22, OUT, 'r'),
    slot('top').inc > 0 && arrow(x0 + W * 0.5, y0 - 2, x0 + W * 0.5, y0 - 20, OUT, 't'),
  ]
  return (
    <svg
      viewBox={`0 0 ${W + x0 + 40} ${H + y0 + 44}`}
      className="w-full max-w-[300px] h-auto"
      role="img"
      aria-label={`케이스 옆모습 — 깊이 ${d}mm, 높이 ${h}mm, 기본 팬 ${fanLayout(f.included)}`}
    >
      <defs>
        {(['in', 'out'] as const).map((k) => (
          <marker key={k} id={`arr-${k}`} viewBox="0 0 6 6" refX={5} refY={3} markerWidth={5} markerHeight={5} orient="auto">
            <path d="M0,0 L6,3 L0,6 z" fill={k === 'in' ? IN : OUT} />
          </marker>
        ))}
      </defs>
      <rect x={x0} y={y0} width={W} height={H} rx={4} fill="color-mix(in srgb, var(--color-muted) 12%, var(--color-panel))" stroke="var(--color-muted)" />
      {positions.flatMap((pos) =>
        fansAlong(pos, slot(pos)).map((c, k) => (
          <circle
            key={`${pos}${k}`}
            cx={c.cx}
            cy={c.cy}
            r={r}
            fill={c.on ? `color-mix(in srgb, ${['top', 'rear'].includes(pos) ? OUT : IN} 25%, var(--color-panel))` : 'none'}
            stroke={c.on ? (['top', 'rear'].includes(pos) ? OUT : IN) : 'var(--color-faint)'}
            strokeDasharray={c.on ? undefined : '2 2'}
          />
        )),
      )}
      {arrows}
      <text x={x0 + 2} y={y0 + H + 14} fontSize={9} fill="var(--color-muted)">
        앞
      </text>
      <text x={x0 + W - 2} y={y0 + H + 14} fontSize={9} textAnchor="end" fill="var(--color-muted)">
        뒤
      </text>
      <text x={x0 + W / 2} y={y0 + H + 38} fontSize={10} textAnchor="middle" fill="var(--color-text)">
        깊이 {d}mm · 높이 {h}mm{specs.width_mm ? ` · 가로 ${specs.width_mm}mm` : ''}
      </text>
    </svg>
  )
}

// 기준 조합 세 개 — 보급·중급·고급. 부품 목록에 없으면 그 줄은 빠진다.
const REF_BUILDS: { label: string; cpu: string; gpu: string }[] = [
  { label: '보급', cpu: 'cpu-ryzen-5-7500f', gpu: 'gpu-rtx-5060' },
  { label: '중급', cpu: 'cpu-ryzen-7-9800x3d', gpu: 'gpu-rtx-5070-ti' },
  { label: '고급', cpu: 'cpu-ryzen-7-9800x3d', gpu: 'gpu-rtx-5090' },
]

const LEVEL = {
  ok: { mark: '✓', cls: '' },
  warn: { mark: '△', cls: 'text-(--color-amber-400)' },
  bad: { mark: '✕', cls: 'text-(--color-red-400)' },
} as const

export function CaseMore({ m, data }: { m: Model; data: HwData }) {
  const s = m.specs
  const f = caseFans(s)
  const size = caseSize(s)
  const byId = new Map(data.parts.map((p) => [p.id, p]))
  const refs = REF_BUILDS.map((b) => ({ ...b, cpuP: byId.get(b.cpu), gpuP: byId.get(b.gpu) })).filter((b) => b.cpuP && b.gpuP)
  return (
    <div className="flex flex-col gap-2">
      <CaseDrawing specs={s} />
      <div className="text-[11px] text-(--color-muted)">
        <span style={{ color: IN }}>● 흡기</span> · <span style={{ color: OUT }}>● 배기</span> · 점선 = 비어 있는 팬 자리
      </div>
      <dl className="grid grid-cols-[5.5rem_minmax(0,1fr)] gap-y-0.5">
        <dt className="text-(--color-muted)">바깥 크기</dt>
        <dd>
          {size.text}mm{size.liters != null && ` · ${size.liters}L`}
        </dd>
        <dt className="text-(--color-muted)">보드</dt>
        <dd>{Array.isArray(s.boards) ? (s.boards as string[]).join(' · ') : String(s.form ?? '—')}</dd>
        <dt className="text-(--color-muted)">기본 팬</dt>
        <dd>{fanLayout(f.included)}</dd>
        <dt className="text-(--color-muted)">팬 자리</dt>
        <dd>{f.mounts ? `${fanLayout(f.mounts)} (모두 ${f.slots}곳)` : '—'}</dd>
        <dt className="text-(--color-muted)">흡기면</dt>
        <dd>
          {String(s.intake_panel ?? '—')}
          {s.dust_filter === true && ' · 먼지 필터 있음'}
        </dd>
        {s.btf === true && (
          <>
            <dt className="text-(--color-muted)">뒷면 커넥터</dt>
            <dd>BTF(선이 뒤로 빠지는 보드) 지원</dd>
          </>
        )}
      </dl>
      {refs.length > 0 && (
        <>
          <div className="font-semibold text-(--color-muted) mt-1">열을 빼나 — 기본 팬 그대로</div>
          {refs.map((b) => {
            const heat = caseHeat(b.cpuP, b.gpuP)
            const v = airflowFor(s, heat)
            return (
              <div key={b.label} className={LEVEL[v.level].cls}>
                {LEVEL[v.level].mark} <b>{b.label}</b> {b.cpuP!.name.replace(/^(AMD|Intel) /, '')} + {b.gpuP!.name.replace(/^(GeForce|Radeon) /, '')} ({heat}W)
                <div className="pl-4 text-(--color-muted)">{v.lines.join(' ')}</div>
              </div>
            )
          })}
          <p className="text-[10px] text-(--color-faint)">
            발열 = CPU 최대 전력 + 그래픽카드 TDP. 필요한 팬 수는 우리 경험 규칙이다(250W 미만 흡기 1·배기 1 · 450W 미만 흡기 2·배기 1 · 그 이상
            흡기 3·배기 1과 메시 앞면) — 측정값이 아니다. 같은 규칙을 조립 화면의 점검에도 쓴다.
          </p>
        </>
      )}
    </div>
  )
}
