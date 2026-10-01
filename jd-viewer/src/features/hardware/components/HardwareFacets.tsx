import { useState } from 'react'
import type { Facet, OptionState, Picked } from '../utils/hwFacets'

// 조건 필터 — 줄마다 이름 · 체크박스 칸 · 더보기. 이미 체크한 조건과 부딪치는 항목은 흐리게 ✕ 를
// 달고, 줄 밑에 '무엇과 왜' 를 이유별로 묶어 적는다(항목마다 적으면 열 줄이 같은 말을 반복한다).
// 흐린 항목도 누를 수는 있다 — 누르면 위에 '선택한 조건끼리 호환 안 됨' 이 뜬다.

const SHOW = 10 // 접힌 상태에서 보이는 항목 수(두 줄)

export function FacetPanel({
  facets,
  picked,
  states,
  onToggle,
  onReset,
}: {
  facets: Facet[]
  picked: Picked
  states: Map<string, OptionState>
  onToggle: (facet: string, value: string) => void
  onReset: () => void
}) {
  const [open, setOpen] = useState<Record<string, boolean>>({})
  const conflicts = facets.flatMap((f) =>
    f.options
      .filter((o) => picked[f.key]?.includes(o.value) && states.get(`${f.key}:${o.value}`)?.disabled)
      .map((o) => ({ f, o, st: states.get(`${f.key}:${o.value}`)! })),
  )
  const any = Object.values(picked).some((v) => v.length)

  return (
    <section className="rounded-lg border border-(--color-border) bg-(--color-panel) overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-(--color-border) bg-(--color-band)">
        <h2 className="text-sm font-bold">조건으로 고르기</h2>
        <span className="text-xs text-(--color-muted)">한 줄 안은 '또는', 줄끼리는 '그리고' · 안 맞는 항목은 ✕ 와 이유가 붙는다</span>
        {any && (
          <button onClick={onReset} className="ml-auto text-xs text-(--color-accent) hover:underline">
            선택 초기화
          </button>
        )}
      </div>
      {conflicts.length > 0 && (
        <div role="alert" className="px-4 py-2 text-sm text-(--color-red-400) bg-(--color-red-400)/8 border-b border-(--color-red-400)/30">
          <b>선택한 조건끼리 호환 안 됨</b>
          {conflicts.map(({ f, o, st }) => (
            <div key={`${f.key}:${o.value}`} className="text-xs mt-0.5">
              ✕ {f.label} '{o.label}' ↔ '{st.against}' — {st.reason}
            </div>
          ))}
        </div>
      )}
      <div className="divide-y divide-(--color-border-soft)">
        {facets.map((f) => {
          const expanded = open[f.key]
          const shown = expanded ? f.options : f.options.slice(0, SHOW)
          // 흐린 항목의 이유를 묶는다: 이유 → 항목 이름들
          const why = new Map<string, string[]>()
          for (const o of f.options) {
            const st = states.get(`${f.key}:${o.value}`)
            if (st?.disabled && st.reason) why.set(`${st.against}|${st.reason}`, [...(why.get(`${st.against}|${st.reason}`) ?? []), o.label])
          }
          return (
            <div key={f.key} className="grid grid-cols-[7.5rem_minmax(0,1fr)_auto] gap-x-3 px-4 py-2.5 items-start">
              <div className="text-sm font-bold pt-0.5" title={f.hint}>
                {f.label}
                <div className="text-[10px] font-normal text-(--color-faint) leading-snug mt-0.5 hidden xl:block">{f.hint}</div>
              </div>
              <div className="min-w-0">
                <div className="grid grid-cols-2 md:grid-cols-3 2xl:grid-cols-4 gap-x-3 gap-y-1.5">
                  {shown.map((o) => {
                    const st = states.get(`${f.key}:${o.value}`)
                    const checked = !!picked[f.key]?.includes(o.value)
                    const off = !!st?.disabled
                    return (
                      <label
                        key={o.value}
                        title={off ? `호환 안 됨 — ${st!.against} 와(과): ${st!.reason}` : undefined}
                        className={`flex items-start gap-1.5 text-sm leading-snug cursor-pointer select-none min-w-0 ${
                          off ? (checked ? 'text-(--color-red-400)' : 'text-(--color-faint) line-through decoration-(--color-faint)/50') : ''
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => onToggle(f.key, o.value)}
                          className="accent-(--color-accent) shrink-0 mt-0.5"
                          aria-describedby={off ? `why-${f.key}` : undefined}
                        />
                        {off && <span className="text-(--color-red-400) no-underline shrink-0">✕</span>}
                        <span className={`break-keep ${checked && !off ? 'text-(--color-accent) font-semibold' : ''}`}>{o.label}</span>
                      </label>
                    )
                  })}
                </div>
                {why.size > 0 && (
                  <div id={`why-${f.key}`} className="mt-1.5 flex flex-col gap-0.5">
                    {[...why.entries()].map(([k, labels]) => {
                      const [against, reason] = k.split('|')
                      return (
                        <div key={k} className="text-[11px] text-(--color-red-400)">
                          ✕ {labels.join(' · ')} — '{against}' 와 호환 안 됨: {reason}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
              {f.options.length > SHOW ? (
                <button
                  onClick={() => setOpen({ ...open, [f.key]: !expanded })}
                  className="text-xs text-(--color-muted) hover:text-(--color-text) whitespace-nowrap pt-0.5"
                >
                  {expanded ? '접기 −' : `${f.options.length - SHOW}개 +`}
                </button>
              ) : (
                <span />
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
