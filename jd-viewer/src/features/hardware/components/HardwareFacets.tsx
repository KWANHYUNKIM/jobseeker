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
    <section className="rounded-[30px] border border-[#e2e8ec] bg-white overflow-hidden">
      <div className="px-[25px] pt-[26px] pb-3">
        <div className="flex items-center gap-2">
          <h2 className="text-[19px] font-bold leading-[27px] text-[#272727]">조건으로 고르기</h2>
          {any && (
            <button type="button" onClick={onReset} className="ml-auto text-[13px] text-(--color-accent) hover:underline">
              선택 초기화
            </button>
          )}
        </div>
        <p className="mt-1 text-[13px] leading-[19px] text-[#999]">한 줄 안은 '또는', 줄끼리는 '그리고' · 안 맞는 항목은 ✕와 이유가 붙어요</p>
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
      <div className="px-[25px] pb-6 flex flex-col gap-[22px]">
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
            <div key={f.key} className="min-w-0">
              <div className="flex items-baseline gap-2">
                <div className="text-[15px] font-bold text-[#272727]">{f.label}</div>
                {f.options.length > SHOW && (
                  <button
                    type="button"
                    onClick={() => setOpen({ ...open, [f.key]: !expanded })}
                    className="ml-auto text-xs text-[#999] hover:text-[#272727] whitespace-nowrap"
                  >
                    {expanded ? '접기 −' : `${f.options.length - SHOW}개 +`}
                  </button>
                )}
              </div>
              {f.hint && <div className="mt-0.5 text-xs leading-[18px] text-[#999]">{f.hint}</div>}
              <div className="min-w-0 mt-2.5">
                <div className="flex flex-wrap gap-1.5">
                  {shown.map((o) => {
                    const st = states.get(`${f.key}:${o.value}`)
                    const checked = !!picked[f.key]?.includes(o.value)
                    const off = !!st?.disabled
                    return (
                      <label
                        key={o.value}
                        title={off ? `호환 안 됨 — ${st!.against} 와(과): ${st!.reason}` : undefined}
                        className={
                          'inline-flex items-center gap-1 h-8 px-3 rounded-2xl border text-[13px] cursor-pointer select-none ' +
                          (checked
                            ? off
                              ? 'border-(--color-red-400) text-(--color-red-400)'
                              : 'bg-(--color-accent) border-(--color-accent) text-white font-medium'
                            : off
                              ? 'border-[#eee] text-[#bbb] line-through'
                              : 'border-[#d8d8d8] text-[#272727] hover:border-[#272727]')
                        }
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => onToggle(f.key, o.value)}
                          className="sr-only"
                          aria-describedby={off ? `why-${f.key}` : undefined}
                        />
                        {off && <span className="no-underline">✕</span>}
                        <span className="break-keep">{o.label}</span>
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

            </div>
          )
        })}
      </div>
    </section>
  )
}
