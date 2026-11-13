import { useMemo, useState } from 'react'
import {
  useBlogGuides,
  useInflearn,
  type Course,
  type GuidePost,
} from '../hooks/useLearningPaths'
import { Loader, ErrorState, TechIcon, CompanyMark } from '../../../components/ui'

// 요구사항 → 학습.
//
// 공고의 우대사항에는 "대용량 트래픽 처리 경험" 같은 문장이 계속 나오는데 그걸 어디서
// 배우는지는 아무도 안 알려준다. 이 화면은 그 사이를 잇는다.
//   읽을 글  — 그 요구를 하는 공고들의 임베딩 방향에 가장 가까운 기술 블로그 글
//   유료 강의 — 그 기술의 인프런 강의를 난이도 사다리로
// 무료 영상은 '학습·확장' 탭이 이미 맡는다. 여기 유료를 따로 두는 이유는, 무료 영상이
// 진입에는 좋아도 실무 구간까지 데려가 주는 경우가 드물기 때문이다.

type Axis = 'concept' | 'tech'

export function LearningView() {
  const { data: guides, loading: gl, error: ge } = useBlogGuides()
  const { data: inflearn, loading: il } = useInflearn()
  const [axis, setAxis] = useState<Axis>('concept')
  const [picked, setPicked] = useState<string | null>(null)

  const items = useMemo(() => {
    if (!guides) return []
    return axis === 'concept'
      ? guides.concepts.map((c) => ({ name: c.name, n: c.jobs, sub: `${c.job_pct}%` }))
      : guides.techs.map((t) => ({ name: t.name, n: t.jobs, sub: '' }))
  }, [guides, axis])

  const current = picked ?? items[0]?.name
  const concept = guides?.concepts.find((c) => c.name === current)
  const tech = guides?.techs.find((t) => t.name === current)
  const posts: GuidePost[] = concept?.posts ?? tech?.posts ?? []
  const courseSet = inflearn?.techs.find((t) => t.tech === current)

  if (gl) return <Loader label="학습 경로 불러오는 중…" />
  if (ge)
    return (
      <ErrorState
        title="blog_guides.json 로드 실패"
        detail={ge}
        hint={
          <>
            생성:{' '}
            <code className="text-(--color-text)">
              catch_capture/.venv/bin/python bin/build_blog_guides.py
            </code>
          </>
        }
      />
    )
  if (!guides) return <div className="p-8 text-(--color-muted)">데이터가 없습니다.</div>

  const switchAxis = (a: Axis) => {
    setAxis(a)
    setPicked(null)
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[380px_minmax(0,1fr)] items-start">
      <aside className="rounded-[30px] border border-[#e2e8ec] bg-white px-[21px] pt-[23px] pb-5">
        <div className="grid grid-cols-2 rounded-xl bg-[#f1f3f5] p-1">
          {(
            [
              ['concept', '요구사항'],
              ['tech', '기술'],
            ] as const
          ).map(([k, label]) => (
            <button
              key={k}
              type="button"
              aria-pressed={axis === k}
              onClick={() => switchAxis(k)}
              className={'h-9 rounded-[9px] text-sm font-medium ' + (axis === k ? 'bg-white text-[#272727] shadow-[0_1px_4px_rgba(0,0,0,0.08)]' : 'text-[#777] hover:text-[#272727]')}
            >
              {label}
            </button>
          ))}
        </div>
        <p className="mt-3 text-[13px] leading-[19px] text-[#888]">
          {axis === 'concept'
            ? `공고 ${guides.jobs.toLocaleString()}건의 자격·우대 원문에서 뽑은 요구예요. 숫자는 그 요구를 하는 공고 수.`
            : '수요 상위 기술이에요. 숫자는 그 기술을 쓰는 공고 수.'}
        </p>
        <ul className="mt-3 flex flex-col">
          {items.map((it) => {
            const on = it.name === current
            return (
              <li key={it.name}>
                <button
                  type="button"
                  onClick={() => setPicked(it.name)}
                  aria-pressed={on}
                  className={'w-full flex items-center gap-2 h-[38px] rounded-xl px-2.5 text-left ' + (on ? 'bg-(--color-accent-weak) shadow-[inset_0_0_0_1.5px_#f45757]' : 'hover:bg-[#f7f9fa]')}
                >
                  {axis === 'tech' && <TechIcon tech={it.name} size={14} />}
                  <span className="flex-1 truncate text-sm text-[#272727]">{it.name}</span>
                  <span className="shrink-0 text-[13px] font-bold text-[#272727] tabular-nums">{it.n.toLocaleString()}</span>
                </button>
              </li>
            )
          })}
        </ul>
      </aside>

      <main className="min-w-0 flex flex-col gap-[30px]">
        <div className="flex flex-col gap-3.5">
          <section className="rounded-[26px] bg-[#272727] px-[30px] pt-[26px] pb-6 text-white">
            <div className="text-[13px] text-[#bbb]">{concept ? '선택한 요구사항' : '선택한 기술'}</div>
            <h2 className="mt-0.5 text-[32px] font-bold leading-[47px] break-keep">{current}</h2>
            <p className="mt-1 text-[15px] text-[#ddd]">
              {concept ? (
                <>
                  공고 <b className="font-bold text-[#ff9a9a]">{concept.jobs.toLocaleString()}건</b>이 요구 · 전체의 {concept.job_pct}%
                </>
              ) : tech ? (
                <>
                  공고 <b className="font-bold text-[#ff9a9a]">{tech.jobs.toLocaleString()}건</b>에서 써요
                </>
              ) : null}
            </p>
          </section>
          {concept && concept.sharpness < 0.06 && (
            <p className="rounded-[14px] bg-[#fff8e6] px-[18px] py-3.5 text-sm text-[#8a6100]">
              ⚠ 이 요구는 거의 모든 공고에 들어 있어(선명도 {concept.sharpness}) 방향이 흐려요. 아래 추천은 다른 주제보다 일반적일 수 있어요.
            </p>
          )}
        </div>

        {concept && concept.tech.length > 0 && (
          <Section title="함께 쓰는 스택">
            <div className="flex flex-wrap gap-1.5">
              {concept.tech.map((t) => (
                <span key={t.name} className="inline-flex items-center gap-1.5 h-8 px-[13px] rounded-[18px] border border-[#d8d8d8] bg-white text-[13px] font-medium text-[#272727]">
                  {t.name}
                  <span className="text-xs font-normal text-[#999] tabular-nums">{t.n}</span>
                </span>
              ))}
            </div>
          </Section>
        )}

        <Section title="읽을 글" hint="이 요구를 하는 공고들과 내용이 가장 가까운 기술 블로그 글">
          {posts.length === 0 ? (
            <p className="text-sm text-[#999]">해당하는 글이 없어요.</p>
          ) : (
            <ul className="grid lg:grid-cols-2 gap-2.5">
              {posts.slice(0, 6).map((p) => (
                <li key={p.url}>
                  <a href={p.url} target="_blank" rel="noreferrer" className="group flex gap-3 h-full rounded-[18px] border border-[#e2e8ec] bg-white px-[17px] py-[17px] hover:border-[#999]">
                    <span className="grid place-items-center w-10 h-10 rounded-[10px] overflow-hidden shrink-0">
                      <CompanyMark name={p.company} size={40} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-[15px] font-medium leading-[21px] text-[#272727] line-clamp-2 group-hover:underline underline-offset-2">{p.title}</span>
                      <span className="mt-1 block text-xs text-[#999]">
                        {p.company} · <b className="font-bold text-(--color-accent) tabular-nums">{p.edge > 0 ? `+${p.edge.toFixed(2)}` : p.edge.toFixed(2)}</b>
                      </span>
                      {p.tech.length > 0 && (
                        <span className="mt-2 flex flex-wrap gap-1">
                          {p.tech.map((t) => (
                            <span key={t} className="rounded bg-[#f4f4f4] px-[7px] text-[13px] leading-[22px] text-[#474747]">
                              {t}
                            </span>
                          ))}
                        </span>
                      )}
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="돈 주고 볼 만한 강의" hint="인프런 · 난이도 사다리 순(같은 칸에서는 최근 갱신된 것부터)">
          {il ? (
            <p className="text-sm text-[#999]">불러오는 중…</p>
          ) : !courseSet || courseSet.courses.length === 0 ? (
            <p className="rounded-2xl bg-[#f7f9fa] px-6 py-5 text-center text-sm text-[#666]">
              {axis === 'concept' ? (
                <>
                  강의는 기술 단위로 모아요 — 위에서{' '}
                  <button type="button" onClick={() => switchAxis('tech')} className="font-medium text-(--color-accent) hover:underline">
                    「기술」
                  </button>
                  로 바꿔 보세요.
                </>
              ) : (
                '수집된 강의가 없어요.'
              )}
            </p>
          ) : (
            <div className="grid lg:grid-cols-2 gap-2.5">
              {courseSet.courses.map((c) => (
                <CourseCard key={c.id} c={c} />
              ))}
            </div>
          )}
        </Section>
      </main>
    </div>
  )
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="flex flex-wrap items-baseline gap-x-[13px]">
        <span className="text-[19px] font-bold text-[#272727]">{title}</span>
        {hint && <span className="text-[13px] text-[#999]">{hint}</span>}
      </h3>
      <div className="mt-[14px]">{children}</div>
    </section>
  )
}

function CourseCard({ c }: { c: Course }) {
  const price = c.is_free ? '무료' : c.price_pay ? `${c.price_pay.toLocaleString()}원` : '가격 미상'
  const discounted = !c.is_free && c.price_regular && c.price_pay && c.price_regular > c.price_pay
  return (
    <a href={c.url} target="_blank" rel="noreferrer" className="group block rounded-[18px] border border-[#e2e8ec] bg-white px-[19px] py-[17px] hover:border-[#999]">
      <div className="flex items-start gap-2">
        {c.level_ko && <span className="shrink-0 rounded bg-[#f1efff] px-[7px] text-xs leading-[22px] text-[#5b4fd6]">{c.level_ko}</span>}
        <span className="flex-1 min-w-0 text-[15px] font-medium leading-[22px] text-[#272727] group-hover:underline underline-offset-2">{c.title}</span>
      </div>
      <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs text-[#999]">
        <span className="text-sm font-bold text-[#272727]">{price}</span>
        {discounted && <span className="line-through">{c.price_regular!.toLocaleString()}원</span>}
        <span>수강 {c.students.toLocaleString()}</span>
        {c.updated_at && <span>갱신 {c.updated_at}</span>}
        {c.instructors[0] && <span>{c.instructors[0]}</span>}
      </div>
      {c.prerequisites.length > 0 && (
        <p className="mt-2 text-xs leading-[18px] text-[#666] line-clamp-2">
          <b className="font-medium text-[#272727]">선수지식</b> {c.prerequisites[0]}
        </p>
      )}
      {c.abilities.length > 0 && (
        <p className="mt-1 text-xs leading-[18px] text-[#666] line-clamp-2">
          <b className="font-medium text-[#272727]">배우는 것</b> {c.abilities.slice(0, 2).join(' · ')}
        </p>
      )}
      {c.skills.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {c.skills.slice(0, 5).map((s) => (
            <span key={s} className="rounded bg-[#f4f4f4] px-1.5 text-[11px] leading-5 text-[#474747]">
              {s}
            </span>
          ))}
        </div>
      )}
    </a>
  )
}
