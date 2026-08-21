import { useMemo, useState } from 'react'
import {
  useBlogGuides,
  useInflearn,
  type Course,
  type GuidePost,
} from '../lib/useLearningPaths'
import { Loader, ErrorState, TechIcon } from './ui'

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

  const maxN = Math.max(...items.map((i) => i.n), 1)

  return (
    <div className="flex flex-col md:flex-row flex-1 min-h-0 min-w-0 overflow-y-auto md:overflow-hidden">
      <aside className="w-full md:w-64 shrink-0 md:overflow-auto border-b md:border-b-0 md:border-r border-(--color-border) bg-(--color-panel) p-3">
        <div className="inline-flex rounded-md border border-(--color-border) overflow-hidden mb-2">
          <AxisBtn active={axis === 'concept'} onClick={() => { setAxis('concept'); setPicked(null) }}>
            요구사항
          </AxisBtn>
          <AxisBtn active={axis === 'tech'} onClick={() => { setAxis('tech'); setPicked(null) }}>
            기술
          </AxisBtn>
        </div>
        <p className="text-[11px] text-(--color-muted) mb-2 leading-relaxed">
          {axis === 'concept'
            ? `공고 ${guides.jobs.toLocaleString()}건의 자격·우대 원문에서 뽑은 요구. 옆 숫자는 그 요구를 하는 공고 수.`
            : '수요 상위 기술. 옆 숫자는 그 기술을 쓰는 공고 수.'}
        </p>
        <ul className="flex flex-col gap-0.5">
          {items.map((it) => {
            const on = it.name === current
            return (
              <li key={it.name}>
                <button
                  onClick={() => setPicked(it.name)}
                  className={`w-full text-left px-2 py-1.5 rounded ${on ? 'bg-(--color-accent)/15' : 'hover:bg-(--color-bg)'}`}
                >
                  <div className="flex items-baseline gap-2">
                    {axis === 'tech' && (
                      <span className="self-center">
                        <TechIcon tech={it.name} size={13} />
                      </span>
                    )}
                    <span className="flex-1 text-xs text-(--color-text) truncate">{it.name}</span>
                    <span className="text-[11px] text-(--color-muted) tabular-nums shrink-0">
                      {it.n.toLocaleString()}
                    </span>
                  </div>
                  <span className="mt-1 block h-1 rounded bg-(--color-bg) overflow-hidden">
                    <span className="block h-full bg-(--color-accent)" style={{ width: `${(it.n / maxN) * 100}%` }} />
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      </aside>

      <main className="flex-1 min-w-0 md:overflow-auto p-4 sm:p-5 flex flex-col gap-6">
        <div>
          <div className="flex items-baseline gap-2 flex-wrap">
            <h2 className="text-xl font-semibold text-(--color-text)">{current}</h2>
            {concept && (
              <span className="text-xs text-(--color-muted)">
                공고 {concept.jobs.toLocaleString()}건이 요구 · 전체의 {concept.job_pct}%
              </span>
            )}
            {tech && (
              <span className="text-xs text-(--color-muted)">
                공고 {tech.jobs.toLocaleString()}건에서 사용
              </span>
            )}
          </div>
          {concept && concept.tech.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              <span className="text-xs text-(--color-muted) mr-1 py-0.5">함께 쓰는 스택</span>
              {concept.tech.map((t) => (
                <span key={t.name} className="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs rounded border border-(--color-border) bg-(--color-bg) text-(--color-text)">
                  <TechIcon tech={t.name} size={13} />
                  {t.name} <span className="text-(--color-muted)">{t.n}</span>
                </span>
              ))}
            </div>
          )}
          {concept && concept.sharpness < 0.06 && (
            <p className="mt-2 text-[11px] text-(--color-muted) leading-relaxed">
              ⚠ 이 요구는 거의 모든 공고에 들어 있어(선명도 {concept.sharpness}) 방향이 흐리다.
              아래 추천은 다른 주제보다 일반적일 수 있다.
            </p>
          )}
        </div>

        <section>
          <h3 className="text-base font-semibold text-(--color-text)">읽을 글</h3>
          <p className="text-xs text-(--color-muted) mb-3">
            이 요구를 하는 공고들과 내용이 가장 가까운 기술 블로그 글. 제목에 키워드가 없어도
            내용이 맞으면 올라온다.
          </p>
          {posts.length === 0 ? (
            <p className="text-sm text-(--color-muted)">해당하는 글이 없습니다.</p>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {posts.map((p) => (
                <li key={p.url}>
                  <a
                    href={p.url}
                    target="_blank"
                    rel="noreferrer"
                    className="block px-2 py-1.5 rounded hover:bg-(--color-bg)"
                  >
                    <div className="flex items-baseline gap-2">
                      <span className="text-sm text-(--color-text) flex-1 min-w-0 truncate">{p.title}</span>
                      <span className="text-[11px] text-(--color-muted) shrink-0">{p.company}</span>
                      <span className="text-[11px] text-(--color-accent) shrink-0 tabular-nums">
                        {p.edge > 0 ? `+${p.edge.toFixed(2)}` : p.edge.toFixed(2)}
                      </span>
                    </div>
                    {p.tech.length > 0 && (
                      <div className="mt-0.5 flex flex-wrap gap-1">
                        {p.tech.map((t) => (
                          <span key={t} className="px-1.5 py-0.5 text-[10px] rounded bg-(--color-accent)/10 text-(--color-accent)">
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <h3 className="text-base font-semibold text-(--color-text)">
            돈 주고 볼 만한 강의 <span className="text-xs font-normal text-(--color-muted)">인프런</span>
          </h3>
          <p className="text-xs text-(--color-muted) mb-3">
            난이도 사다리 순. 같은 칸 안에서는 최근 갱신된 것부터 — 수강생 순으로만 줄 세우면
            몇 년 된 강의가 늘 1등이라 "지금 어떻게 발전했는지"를 못 본다.
          </p>
          {il ? (
            <p className="text-sm text-(--color-muted)">불러오는 중…</p>
          ) : !courseSet || courseSet.courses.length === 0 ? (
            <p className="text-sm text-(--color-muted)">
              {axis === 'concept'
                ? '강의는 기술 단위로 모읍니다 — 위에서 「기술」로 바꿔 보세요.'
                : '수집된 강의가 없습니다.'}
            </p>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              {courseSet.courses.map((c) => (
                <CourseCard key={c.id} c={c} />
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  )
}

function CourseCard({ c }: { c: Course }) {
  const price = c.is_free
    ? '무료'
    : c.price_pay
      ? `${c.price_pay.toLocaleString()}원`
      : '가격 미상'
  const discounted = !c.is_free && c.price_regular && c.price_pay && c.price_regular > c.price_pay

  return (
    <a
      href={c.url}
      target="_blank"
      rel="noreferrer"
      className="rounded border border-(--color-border) bg-(--color-bg) p-3 hover:border-(--color-accent)/50 transition"
    >
      <div className="flex items-baseline gap-2">
        {c.level_ko && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-(--color-accent)/15 text-(--color-accent) shrink-0">
            {c.level_ko}
          </span>
        )}
        <span className="text-sm font-medium text-(--color-text) flex-1 min-w-0">{c.title}</span>
      </div>

      <div className="mt-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[11px] text-(--color-muted)">
        <span className="text-(--color-text) font-medium">{price}</span>
        {discounted && <span className="line-through">{c.price_regular!.toLocaleString()}원</span>}
        <span>수강 {c.students.toLocaleString()}</span>
        {c.updated_at && <span>갱신 {c.updated_at}</span>}
        {c.instructors[0] && <span>{c.instructors[0]}</span>}
      </div>

      {c.prerequisites.length > 0 && (
        <p className="mt-1.5 text-[11px] text-(--color-muted) line-clamp-2">
          <span className="text-(--color-text)">선수지식</span> {c.prerequisites[0]}
        </p>
      )}
      {c.abilities.length > 0 && (
        <p className="mt-1 text-[11px] text-(--color-muted) line-clamp-2">
          <span className="text-(--color-text)">배우는 것</span> {c.abilities.slice(0, 2).join(' · ')}
        </p>
      )}
      {c.skills.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {c.skills.slice(0, 5).map((s) => (
            <span key={s} className="px-1.5 py-0.5 text-[10px] rounded border border-(--color-border) text-(--color-muted)">
              {s}
            </span>
          ))}
        </div>
      )}
    </a>
  )
}

function AxisBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1 text-xs font-medium transition ${active ? 'bg-(--color-accent) text-(--color-on-accent)' : 'bg-(--color-bg) text-(--color-muted) hover:text-(--color-text)'}`}
    >
      {children}
    </button>
  )
}
