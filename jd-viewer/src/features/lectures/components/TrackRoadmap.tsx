import { onLinkClick } from '../../../utils/navigation'
import { paths } from '../../../utils/urls'
import type { LectureCard, Track } from '../hooks/useLectures'
import { firstReads } from '../utils/roadmap'

// 학습 로드맵 — 트랙 하나(AI·코딩테스트·백엔드…)를 "처음 보는 사람이 무엇부터 어떤 순서로" 보나로 펼친다.
// 순서와 공부법은 lecture-engine/paths.json 에 손으로 쓴 것이고, 진행률은 validate.py 가 붙인다.
// 단계마다 이미 정리된 노트 중 쉬운 것(입문 → 차례) 몇 편을 '먼저 볼 노트'로 보여 준다.

const LEVEL_TONE: Record<string, string> = {
  입문: 'bg-[#e8f6ee] text-[#1b7a44]',
  중급: 'bg-[#eef2ff] text-[#3b4fc4]',
  심화: 'bg-[#fdecec] text-[#b42318]',
}
export function TrackRoadmap({ t, items }: { t: Track; items: LectureCard[] }) {
  const pct = t.total ? Math.round((t.done / t.total) * 100) : 0
  return (
    <section className="mt-[28px] rounded-2xl border border-[#e5e5e5] p-5 sm:p-7">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="text-[22px] font-bold text-[#272727]">{t.label} 학습 순서</h2>
        <span className="text-sm text-[#888]">{t.for}</span>
      </div>
      <p className="mt-2 text-[15px] leading-6 text-[#444]">
        <b className="text-[#272727]">목표</b> · {t.goal}
      </p>
      <div className="mt-3 flex items-center gap-3">
        <div className="flex-1 h-1.5 rounded-full bg-[#eee] overflow-hidden">
          <div className="h-full bg-(--color-accent)" style={{ width: `${pct}%` }} />
        </div>
        <span className="shrink-0 text-[13px] text-[#666]">
          {t.total}편 중 <b className="text-[#272727]">{t.done}편</b> 정리
        </span>
      </div>

      <div className="mt-5 rounded-xl bg-[#f7f7f8] px-5 py-4">
        <div className="text-[15px] font-bold text-[#272727]">이렇게 공부하면 쉬워요</div>
        <ul className="mt-2 space-y-1.5 text-[14px] leading-6 text-[#444] list-disc pl-5">
          {t.how.map((h) => (
            <li key={h}>{h}</li>
          ))}
        </ul>
      </div>

      <ol className="mt-6 space-y-5">
        {t.steps.map((st, i) => {
          const reads = firstReads(items, st.series.map((s) => s.key))
          return (
            <li key={st.title} className="relative pl-11">
              <span className="absolute left-0 top-0 grid place-items-center w-8 h-8 rounded-full bg-(--color-accent) text-white text-sm font-bold">
                {i + 1}
              </span>
              {i < t.steps.length - 1 && <span aria-hidden className="absolute left-[15px] top-9 bottom-[-18px] w-px bg-[#e0e0e0]" />}
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-[17px] font-bold text-[#272727]">{st.title.replace(/^\d+단계\s*·\s*/, '')}</h3>
                <span className={`rounded px-1.5 py-0.5 text-xs ${LEVEL_TONE[st.level] ?? ''}`}>{st.level}</span>
                <span className="text-xs text-[#888]">
                  {st.done}/{st.total}편
                </span>
              </div>
              <p className="mt-1 text-[14px] leading-6 text-[#555]">{st.why}</p>
              {st.tip && (
                <p className="mt-1 text-[13px] leading-5 text-[#1b7a44]">
                  <b>팁</b> · {st.tip}
                </p>
              )}
              <div className="mt-2 flex flex-wrap gap-2">
                {st.series.map((s) => {
                  const href = paths.lectureSeries(s.key)
                  return (
                    <a
                      key={s.key}
                      href={href}
                      onClick={onLinkClick(href)}
                      className="rounded-lg border border-[#d8d8d8] px-3 py-1.5 text-[13px] text-[#272727] hover:border-[#272727]"
                    >
                      {s.title}{' '}
                      <span className="text-[#888]">
                        {s.done}/{s.total}
                      </span>
                    </a>
                  )
                })}
              </div>
              {reads.length > 0 && (
                <div className="mt-2 text-[13px] text-[#666]">
                  먼저 볼 노트:{' '}
                  {reads.map((c, j) => {
                    const href = paths.lecture(c.id)
                    return (
                      <span key={c.id}>
                        {j > 0 && ' · '}
                        <a href={href} onClick={onLinkClick(href)} className="text-(--color-accent) hover:underline">
                          {c.title_ko}
                        </a>
                      </span>
                    )
                  })}
                </div>
              )}
              {st.done === 0 && <div className="mt-2 text-[13px] text-[#999]">아직 정리 전 — 루프가 차례대로 채웁니다.</div>}
            </li>
          )
        })}
      </ol>
    </section>
  )
}
