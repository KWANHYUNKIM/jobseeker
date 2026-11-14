import { useState, type ReactNode } from 'react'
import { RES_LABEL, estimateBuildMin, won, type HwData, type Part, type Res } from '../utils/hardware'

// 조립 화면 아래쪽 전체 — "이 조합으로 무엇을 할 수 있나"(Penpot 12-1 캐치형 1920).
// 예전에는 게임·AI·개발·영상 예측이 오른쪽 좁은 칸에 쌓여 있었다. 이제 조합 아래에 전체 너비로
// 01 게임 · 02 AI · 03 개발 · 04 영상 편집 순서로 한 줄씩 펼친다. 머리의 탭 넷은 그 구역으로 간다.

type UseKey = 'game' | 'ai' | 'dev' | 'video'

const USE_ANCHOR: Record<UseKey, string> = { game: 'use-game', ai: 'use-ai', dev: 'use-dev', video: 'use-video' }

interface Props {
  data: HwData
  useName: string
  budget: number
  res: Res
  gpu?: Part
  cpu?: Part
  ram?: Part
  sections: Partial<Record<UseKey, ReactNode>>
}

export function UseSection({ data, useName, budget, res, gpu, cpu, ram, sections }: Props) {
  const [on, setOn] = useState<UseKey>('game')
  const vram = gpu ? Number(gpu.specs.vram_gb) : null
  const mins = cpu ? estimateBuildMin(data.bench, cpu) : null
  const effects = gpu ? data.bench.video?.gpu[gpu.id]?.effects : undefined
  const ramGb = ram ? Number(ram.specs.capacity_gb) * 2 : null
  const tabs: { key: UseKey; name: string; sub: string }[] = [
    { key: 'game', name: '게임', sub: `${RES_LABEL[res]} · ${data.bench.games.length}개 게임` },
    { key: 'ai', name: 'AI', sub: vram != null ? `VRAM ${vram}GB · ${String(gpu!.specs.stack)}` : '그래픽카드를 고르면' },
    { key: 'dev', name: '개발', sub: mins != null ? `풀 빌드 약 ${mins < 10 ? mins.toFixed(1) : Math.round(mins)}분` : 'CPU 를 고르면' },
    { key: 'video', name: '영상 편집', sub: effects != null ? `효과 점수 ${Math.round(effects)}` : '실측 없음' },
  ]
  const go = (k: UseKey) => {
    setOn(k)
    document.getElementById(USE_ANCHOR[k])?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  const order: UseKey[] = ['game', 'ai', 'dev', 'video']
  return (
    <section aria-label="이 조합으로 무엇을 할 수 있나" className="mt-[70px]">
      <div className="relative pb-8 after:absolute after:bottom-0 after:left-1/2 after:h-px after:w-screen after:-translate-x-1/2 after:bg-[#e2e8ec]">
        <nav aria-label="경로" className="text-sm leading-5 tracking-[-0.16px] text-[#737373]">
          PC 하드웨어 › 조립 · 성능 예측 › <b className="font-bold text-(--color-accent)">이 조합으로 무엇을 할 수 있나</b>
        </nav>
        <div className="mt-[22px] flex flex-col lg:flex-row lg:items-start gap-5">
          <div className="min-w-0 flex-1">
            <h2 className="text-[34px] font-bold leading-[49px] tracking-[-0.8px] text-[#272727]">이 조합으로 무엇을 할 수 있나</h2>
            <p className="mt-2 text-[17px] leading-[25px] tracking-[-0.16px] text-[#555]">게임 · AI · 개발 · 영상 편집을 한 줄씩 — 숫자는 위 화면의 예측값 그대로예요.</p>
          </div>
          <div className="shrink-0 lg:min-w-[560px] h-[87px] rounded-[22px] bg-[#272727] px-[22px] pt-[18px]" data-nosnippet>
            <div className="text-[13px] leading-[19px] text-[#ccc]">
              지금 고른 조합 · {won(budget)} · {useName}
            </div>
            <div className="mt-[7px] flex items-baseline gap-x-[17px] whitespace-nowrap overflow-hidden">
              {cpu && <Spec k="CPU" v={cpu.name} />}
              {gpu && <Spec k="그래픽" v={gpu.name} />}
              {ram && ramGb != null && <Spec k="메모리" v={`${String(ram.specs.type ?? 'DDR5')} ${ramGb}GB`} />}
            </div>
          </div>
        </div>
        <div className="mt-6 grid grid-cols-2 lg:grid-cols-4 gap-[10px]">
          {tabs.map((t, i) => {
            const active = t.key === on
            return (
              <button
                key={t.key}
                type="button"
                onClick={() => go(t.key)}
                aria-current={active ? 'true' : undefined}
                className={
                  'h-[76px] rounded-2xl bg-white px-5 flex items-center gap-[13px] text-left ' +
                  (active ? 'border-2 border-(--color-accent)' : 'border border-[#e2e8ec] hover:border-[#999]')
                }
              >
                <span className={'text-[20px] font-bold leading-[29px] tabular-nums ' + (active ? 'text-(--color-accent)' : 'text-[#c9d1d8]')}>
                  {String(i + 1).padStart(2, '0')}
                </span>
                <span className="min-w-0">
                  <span className="block text-[17px] font-bold leading-[25px] text-[#272727]">{t.name}</span>
                  <span className="block text-[13px] leading-[19px] text-[#737373] truncate">{t.sub}</span>
                </span>
              </button>
            )
          })}
        </div>
      </div>
      <div className="flex flex-col">
        {order.map((k) =>
          sections[k] ? (
            <div key={k} id={USE_ANCHOR[k]} className="scroll-mt-24 pt-[60px] min-w-0">
              {sections[k]}
            </div>
          ) : null,
        )}
      </div>
    </section>
  )
}

function Spec({ k, v }: { k: string; v: string }) {
  return (
    <span className="inline-flex items-baseline gap-[5px] shrink-0">
      <span className="text-xs leading-[18px] text-[#ff9a9a]">{k}</span>
      <span className="text-base font-bold leading-6 text-white">{v}</span>
    </span>
  )
}
