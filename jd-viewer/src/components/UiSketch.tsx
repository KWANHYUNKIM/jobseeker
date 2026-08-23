import { useState } from 'react'
import type { UiElement, UiPin, UiSketchData } from '../lib/useReveng'
import { Md } from './Md'
import { ConfBadge, SourceLinks } from './RevengBits'

// 사용자가 보는 화면을 왼쪽에 놓고, 그 위의 번호에 설명을 차곡차곡 건다.
//
// 이 탭의 글은 전부 "무엇을 어떻게 만들었나"인데, 읽는 사람에게는 그게 앱의 어느
// 부분 이야기인지 붙들 데가 없다. 추상적인 네모로 그린 도메인 지도는 그 자리를
// 대신하지 못한다 — 사용자가 실제로 누르는 것이 무엇인지가 안 나오기 때문이다.
//
// ⚠️ 여기 그려지는 것은 **실제 화면 캡처가 아니라 재구성**이다. 남의 앱 화면을
// 공개 사이트에 올리는 문제를 피하고, 앱 로그인이 필요해 애초에 찍을 수 없는
// 회사까지 같은 형식으로 다루기 위해서다. 그 사실을 화면에서도 항상 밝힌다 —
// 밝히지 않으면 읽는 사람이 이것을 그 회사의 실제 화면으로 착각한다.

const DEFAULT_NOTE =
  '실제 화면 캡처가 아니라, 공개 자료에 적힌 것만으로 이 사이트가 다시 그린 도해입니다.'

export function UiSketch({
  ui,
  idKey,
  onPickDomain,
}: {
  ui: UiSketchData
  idKey: string
  /** 회사 화면 도해에서 핀이 도메인을 가리킬 때 — 누르면 그 도메인으로 간다 */
  onPickDomain?: (domain: string) => void
}) {
  const [active, setActive] = useState<number | null>(null)
  const pins = [...(ui.pins ?? [])].sort((a, b) => a.n - b.n)

  return (
    <figure className="m-0">
      <figcaption className="mb-2">
        <div className="text-sm font-medium text-(--color-text)">{ui.title}</div>
        {ui.question && <div className="text-xs text-(--color-muted) mt-0.5">{ui.question}</div>}
      </figcaption>

      <div className="grid grid-cols-1 lg:grid-cols-[auto_1fr] gap-4 lg:gap-6 items-start">
        <div className="lg:sticky lg:top-16">
          <Frame kind={ui.kind ?? 'phone'}>
            {(ui.screen ?? []).map((el, i) => (
              <Row
                key={`${idKey}-${i}`}
                el={el}
                active={active}
                onPick={(n) => setActive(active === n ? null : n)}
              />
            ))}
          </Frame>
          <p className="mt-2 max-w-[300px] text-[11px] leading-relaxed text-(--color-muted)">
            <Md>{ui.note || DEFAULT_NOTE}</Md>
          </p>
        </div>

        <ol className="flex flex-col gap-2 min-w-0">
          {pins.map((p) => (
            <PinStep
              key={p.n}
              p={p}
              active={active === p.n}
              onPick={() => setActive(active === p.n ? null : p.n)}
              onPickDomain={onPickDomain}
            />
          ))}
        </ol>
      </div>
    </figure>
  )
}

// 종이 위의 기기. 그림자·그라디언트를 쓰지 않는 것은 도해 양식(STYLE.md)과 같은 이유다 —
// 꾸미면 무엇이 중요한지가 안 보인다.
function Frame({ kind, children }: { kind: 'phone' | 'web'; children: React.ReactNode }) {
  if (kind === 'web') {
    return (
      <div className="w-[300px] sm:w-[340px] rounded-lg border border-(--color-border) bg-(--color-panel) overflow-hidden">
        <div className="flex items-center gap-1.5 px-2.5 py-1.5 border-b border-(--color-border)">
          <span className="w-2 h-2 rounded-full border border-(--color-border)" />
          <span className="w-2 h-2 rounded-full border border-(--color-border)" />
          <span className="w-2 h-2 rounded-full border border-(--color-border)" />
          <span className="ml-2 flex-1 h-3.5 rounded-sm border border-(--color-border)" />
        </div>
        <div className="p-3 flex flex-col gap-2">{children}</div>
      </div>
    )
  }
  return (
    <div className="w-[300px] rounded-[22px] border-2 border-(--color-border) bg-(--color-panel) p-2">
      <div className="flex justify-center pb-1.5">
        <span className="w-16 h-1 rounded-full bg-(--color-border)" />
      </div>
      <div className="rounded-[14px] border border-(--color-border) bg-(--color-bg) p-3 flex flex-col gap-2">
        {children}
      </div>
    </div>
  )
}

// 요소 한 줄 = [번호 자리][내용]. 번호를 절대 위치로 띄우지 않고 왼쪽 여백 칸에
// 두는 이유는, 화면 폭이 바뀌어도 번호와 요소가 절대 어긋나지 않기 때문이다.
function Row({
  el,
  active,
  onPick,
}: {
  el: UiElement
  active: number | null
  onPick: (n: number) => void
}) {
  const on = el.pin != null && active === el.pin
  return (
    <div className="grid grid-cols-[16px_1fr] gap-1.5 items-start">
      <div className="pt-1">
        {el.pin != null && (
          <button
            onClick={() => onPick(el.pin!)}
            title={`설명 ${el.pin} 번으로`}
            className={
              'w-4 h-4 rounded-full border text-[9px] leading-none flex items-center justify-center tabular-nums transition ' +
              (on
                ? 'bg-(--color-accent) text-(--color-on-accent) border-(--color-accent)'
                : 'border-(--color-accent) text-(--color-accent) hover:bg-(--color-accent)/10')
            }
          >
            {el.pin}
          </button>
        )}
      </div>
      <div className={'min-w-0 rounded ' + (on ? 'ring-1 ring-(--color-accent)' : '')}>
        <Element el={el} />
      </div>
    </div>
  )
}

function Element({ el }: { el: UiElement }) {
  switch (el.type) {
    case 'appbar':
      return (
        <div className="flex items-center gap-1.5 text-xs text-(--color-text) pb-1 border-b border-(--color-border)">
          <span className="text-(--color-muted)">←</span>
          <span className="font-medium">{el.text}</span>
        </div>
      )
    case 'label':
      return <div className="text-[11px] text-(--color-muted)">{el.text}</div>
    case 'text':
      return <div className="text-xs text-(--color-text) leading-relaxed">{el.text}</div>
    case 'input':
      return (
        <div className="px-2.5 py-2 rounded border border-(--color-border) bg-(--color-panel) text-xs">
          {el.text ? (
            <span className="text-(--color-text) tabular-nums">{el.text}</span>
          ) : (
            <span className="text-(--color-muted)">{el.hint}</span>
          )}
        </div>
      )
    case 'chips':
      return (
        <div className="flex flex-wrap gap-1">
          {(el.items ?? []).map((it) => (
            <span
              key={it}
              className="px-1.5 py-0.5 rounded-full border border-(--color-border) text-[10px] text-(--color-text)"
            >
              {it}
            </span>
          ))}
        </div>
      )
    case 'amount':
      return (
        <div className="py-1.5 text-center text-xl font-semibold text-(--color-text) tabular-nums">
          {el.text}
        </div>
      )
    case 'button':
      return (
        <div
          className={
            'py-2 rounded text-center text-xs font-medium ' +
            (el.variant === 'ghost'
              ? 'border border-(--color-border) text-(--color-text)'
              : 'bg-(--color-accent) text-(--color-on-accent)')
          }
        >
          {el.text}
        </div>
      )
    case 'rows':
      return (
        <div className="flex flex-col divide-y divide-(--color-border) border border-(--color-border) rounded">
          {(el.rows ?? []).map((r, i) => (
            <div key={i} className="flex items-center gap-2 px-2 py-1.5">
              <div className="min-w-0">
                <div className="text-xs text-(--color-text) truncate">{r.title}</div>
                {r.sub && <div className="text-[10px] text-(--color-muted) truncate">{r.sub}</div>}
              </div>
              {r.right && (
                <div className="ml-auto shrink-0 text-[11px] text-(--color-muted) tabular-nums">
                  {r.right}
                </div>
              )}
            </div>
          ))}
        </div>
      )
    case 'tabs':
      return (
        <div className="flex gap-3 border-b border-(--color-border) pb-1">
          {(el.items ?? []).map((it, i) => (
            <span
              key={it}
              className={
                'text-[11px] ' +
                (i === 0
                  ? 'text-(--color-text) font-medium border-b-2 border-(--color-accent) -mb-1.5 pb-1'
                  : 'text-(--color-muted)')
              }
            >
              {it}
            </span>
          ))}
        </div>
      )
    case 'card':
      return (
        <div className="rounded border border-(--color-border) bg-(--color-panel) px-2.5 py-2">
          {el.text && <div className="text-xs font-medium text-(--color-text)">{el.text}</div>}
          {(el.items ?? []).map((it) => (
            <div key={it} className="text-[11px] text-(--color-muted) mt-0.5">
              {it}
            </div>
          ))}
        </div>
      )
    case 'divider':
      return <div className="h-px bg-(--color-border) my-0.5" />
    case 'spacer':
      return <div className="h-3" />
    default:
      return null
  }
}

function PinStep({
  p,
  active,
  onPick,
  onPickDomain,
}: {
  p: UiPin
  active: boolean
  onPick: () => void
  onPickDomain?: (domain: string) => void
}) {
  return (
    <li
      onClick={onPick}
      className={
        'cursor-pointer rounded border p-2.5 transition-colors ' +
        (active
          ? 'border-(--color-accent) bg-(--color-accent)/5'
          : 'border-(--color-border) hover:border-(--color-accent)/50')
      }
    >
      <div className="flex items-start gap-2">
        <span
          className={
            'mt-px shrink-0 w-4 h-4 rounded-full border text-[9px] leading-none flex items-center justify-center tabular-nums ' +
            (active
              ? 'bg-(--color-accent) text-(--color-on-accent) border-(--color-accent)'
              : 'border-(--color-accent) text-(--color-accent)')
          }
        >
          {p.n}
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-sm text-(--color-text)">
            <span className="font-medium">
              <Md>{p.title}</Md>
            </span>
            <ConfBadge c={p.confidence} />
            {p.domain && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onPickDomain?.(p.domain!)
                }}
                className="ml-1.5 align-middle px-1.5 py-px rounded text-[10px] border border-(--color-border) text-(--color-muted) hover:border-(--color-accent) hover:text-(--color-accent)"
                title={onPickDomain ? '이 도메인의 기능만 보기' : undefined}
              >
                {p.domain}
              </button>
            )}
          </div>
          <div className="text-sm text-(--color-muted) leading-relaxed reveng-prose mt-0.5">
            <Md>{p.what}</Md>
          </div>
          <SourceLinks sources={p.sources} />
        </div>
      </div>
    </li>
  )
}
