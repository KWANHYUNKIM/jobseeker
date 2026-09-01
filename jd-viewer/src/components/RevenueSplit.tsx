import type { RevenueStream } from '../lib/useReveng'
import { Md } from './Md'

// 수익 구성 한 줄.
//
// 도메인을 상자로 그린 그림이 '어떻게 도는가'를 말한다면 여기는 '어디서 얼마가
// 나오는가'를 말한다. 같은 말을 두 번 하지 않도록 그림에는 숫자를 넣지 않고,
// 숫자는 이 막대에만 둔다.
//
// 공개 실적에 부문별 숫자가 있는 회사에서만 나온다 — 비중이 적힌 수익원이
// 둘 미만이면 통째로 접는다. 없는 숫자를 그럴듯하게 만들지 않는다는 규칙이
// 그림에도 똑같이 적용된다.

const MIN_LABEL_SHARE = 11 // 이 아래로는 칸 안에 글자가 안 들어간다 — 범례로 내린다

// 칸마다 다른 색을 주면 색이 다섯 개가 되어 강조가 사라진다. 한 색의 농도만
// 비중 순으로 낮춘다 — 막대가 왼쪽부터 옅어지는 것 자체가 순위를 말한다.
const RAMP = [26, 17, 11, 7, 5]
const fill = (rank: number) =>
  rank < 0
    ? 'var(--color-bg)'
    : `color-mix(in srgb, var(--color-accent) ${RAMP[Math.min(rank, RAMP.length - 1)]}%, var(--color-panel))`

export function RevenueSplit({
  streams,
  total,
}: {
  streams: RevenueStream[]
  total?: string
}) {
  const known = streams.filter((s) => typeof s.share === 'number' && s.share > 0)
  const sum = known.reduce((a, s) => a + (s.share ?? 0), 0)
  const rest = Math.max(0, 100 - sum)
  // 합이 100 에 못 미치면 남은 만큼을 '그 외'로 둔다. 눈속임으로 늘려 채우면
  // 막대가 곧 거짓말이 된다.
  const cells = [
    ...known.map((s, i) => ({ key: s.name, name: s.name, share: s.share ?? 0, amount: s.amount, rank: i })),
    ...(rest > 1 ? [{ key: '__rest', name: '그 외', share: rest, amount: undefined, rank: -1 }] : []),
  ]
  // 칸이 하나뿐이면 막대가 아니라 그냥 색칠한 줄이다. 다만 '광고 95% + 그 외'
  // 처럼 회사가 한 줄로만 밝힌 경우는 그 자체가 그림이 되므로 살린다.
  //
  // 수익원이 애초에 하나인 회사(Figma·무신사처럼 구독 하나로 사는 곳)는 나눌
  // 것이 없어 막대가 성립하지 않는다. 그렇다고 통째로 접으면 확인해 둔 총매출까지
  // 화면에서 사라지므로, 그 한 줄만 남긴다.
  if (cells.length < 2) {
    if (!total) return null
    return (
      <p className="mt-3 text-xs text-(--color-muted) tracking-wide reveng-prose">
        {total}
        {known.length === 1 && (
          <span className="text-(--color-text)">
            {' — 전부 '}
            <Md>{known[0].name}</Md>
          </span>
        )}
      </p>
    )
  }

  return (
    <figure className="m-0 mt-3 reveng-prose">
      {total && (
        <figcaption className="text-xs text-(--color-muted) mb-1.5 tracking-wide">{total}</figcaption>
      )}

      <div className="flex h-9 w-full overflow-hidden rounded border border-(--color-border)">
        {cells.map((c) => (
          <div
            key={c.key}
            title={`${c.name} ${c.share}%${c.amount ? ` · ${c.amount}` : ''}`}
            style={{ width: `${c.share}%`, background: fill(c.rank) }}
            className="flex items-center justify-center border-r border-(--color-border) last:border-r-0 min-w-0 px-1"
          >
            {c.share >= MIN_LABEL_SHARE && (
              <span className="text-xs text-(--color-text) truncate">{c.name}</span>
            )}
          </div>
        ))}
      </div>

      {/* 범례가 곧 표다 — 막대에서 읽히지 않는 작은 칸도 여기서는 같은 무게로 읽힌다 */}
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        {cells.map((c) => (
          <li key={c.key} className="text-xs text-(--color-muted) flex items-baseline gap-1.5">
            <span
              style={{ background: fill(c.rank) }}
              className="inline-block w-2.5 h-2.5 shrink-0 translate-y-px border border-(--color-border)"
            />
            <span className="text-(--color-text)"><Md>{c.name}</Md></span>
            <span className="tabular-nums">{c.share}%</span>
            {c.amount && <span className="tabular-nums opacity-80">· {c.amount}</span>}
          </li>
        ))}
      </ul>
    </figure>
  )
}
