import { useEffect, useState, type ReactNode } from 'react'
import { ErrorState, Loader } from '../../../components/ui'
import { SiteFooter } from '../../../components/SiteFooter'
import { onLinkClick } from '../../../utils/navigation'
import { absUrl, clip, useSeo } from '../../../utils/seo'
import { paths } from '../../../utils/urls'
import { fetchFreelanceProject } from '../api'
import { useFreelance } from '../hooks/useFreelance'
import { BODY_BLOCKED, SITE_KO, budgetLabel, projectState, splitProjectSlug, type ProjectDetail } from '../utils/freelance'

// 외주 프로젝트 한 건 — `/freelance/<사이트>-<번호>`.
//
// 예전에는 목록을 누르면 원본 사이트로 나갔다. 이제 본문을 크롤러가 받아 DB(project_body)에 두고
// 여기서 읽는다. 지원은 원본에서만 된다 — 그래서 '원문에서 지원하기' 하나만 밖으로 나간다.
// API 가 없으면(정적 배포·DB 다운) 목록 데이터의 요약으로 물러선다.

const NOINDEX = 'noindex, follow' // 남의 글을 옮긴 화면이라 색인하지 않는다

/** 어느 주소의 답인가(slug)까지 들고 있다 — 다른 프로젝트로 넘어가면 그 답은 '불러오는 중' 이다. */
type State = { slug: string; p: ProjectDetail | null; error: string | null }

export function FreelanceProjectView({ slug }: { slug: string }) {
  const key = splitProjectSlug(slug)
  const list = useFreelance()
  const [got, setGot] = useState<State | null>(null)

  useEffect(() => {
    const k = splitProjectSlug(slug)
    if (!k) return
    const ctl = new AbortController()
    fetchFreelanceProject(k[0], k[1], { signal: ctl.signal })
      .then((p) => setGot({ slug, p, error: null }))
      .catch((e: Error) => e.name !== 'AbortError' && setGot({ slug, p: null, error: e.message }))
    return () => ctl.abort()
  }, [slug])
  const st = got?.slug === slug ? { ...got, loading: false } : { p: null, error: null, loading: true }

  // API 가 안 되면 목록(freelance.json)의 같은 행 — 본문 없이 요약만.
  const fallback: ProjectDetail | null = (() => {
    if (st.p || st.loading || !key || !list.data) return null
    const row = list.data.projects.find((x) => x.id === `${key[0]}:${key[1]}`)
    return row ? { ...row, body: null, body_at: null } : null
  })()
  const p = st.p ?? fallback

  useSeo({
    title: p ? `${p.title} — 외주·프리` : '외주·프리 프로젝트',
    description: p ? clip(`${budgetLabel(p.budget)} · ${p.location || '근무지 미정'} · ${p.summary}`) : undefined,
    robots: NOINDEX,
    canonical: absUrl(paths.freelanceProject(key?.[0] ?? '', key?.[1] ?? '')),
  })

  if (!key) return <ErrorState title="프로젝트 주소가 이상해요" detail={slug} />
  if (!p) {
    if (st.loading || list.loading) return <Loader label="프로젝트 불러오는 중…" />
    return (
      <ErrorState
        title="프로젝트를 찾지 못했어요"
        detail={st.error ?? slug}
        hint={
          <a href={paths.freelance()} onClick={onLinkClick(paths.freelance())} className="text-(--color-accent) underline">
            외주·프리 목록으로
          </a>
        }
      />
    )
  }
  return <Detail p={p} fromApi={!!st.p} />
}

function Detail({ p, fromApi }: { p: ProjectDetail; fromApi: boolean }) {
  const site = SITE_KO[p.site] ?? p.site
  // 주소로 바로 들어온 상세도 목록과 같은 규칙으로 닫는다 — status 만 보면 마감일 지난 자리가 모집중으로 보인다.
  const state = projectState(p)
  const closed = !state.open
  const priced = !!p.budget && !!(p.budget.min || p.budget.max)
  const facts: [string, string][] = [
    ['단가', budgetLabel(p.budget)],
    ['기간', p.duration || '—'],
    ['시작', p.start || '—'],
    ['근무', `${p.kind === 'onsite' ? '상주' : p.kind === 'remote' ? '원격·도급' : '—'}${p.location ? ` · ${p.location}` : ''}`],
    ['경력', p.career || '—'],
    ['마감', p.deadline ?? '상시'],
    ['지원자', p.applicants != null ? `${p.applicants}명` : '—'],
    ['올라온 날', p.posted_date ?? p.first_seen_at.slice(0, 10)],
  ]
  const history = (p.history ?? []).filter((h) => h.budget)
  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[38px] pb-16">
        <nav aria-label="경로" className="text-sm text-[#777]">
          <a href={paths.freelance()} onClick={onLinkClick(paths.freelance())} className="hover:text-[#272727]">
            외주·프리
          </a>
          {` › ${site}`}
        </nav>

        <header className="mt-5 rounded-[30px] bg-[#f7f9fa] px-6 sm:px-[34px] py-[34px] flex flex-col lg:flex-row lg:items-end gap-6">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap gap-1">
              <Chip>{p.kind === 'onsite' ? '상주' : '원격·도급'}</Chip>
              {p.work_type && <Chip>{p.work_type}</Chip>}
              {p.grade && p.grade !== '혼합' && <Chip tone="grade">{p.grade}</Chip>}
              {p.tags.filter((t) => t !== p.work_type).map((t) => (
                <Chip key={t}>{t}</Chip>
              ))}
              {closed && <Chip tone="closed">{state.label}</Chip>}
            </div>
            <h1 className="mt-3 text-[26px] sm:text-[30px] font-bold leading-[1.35] tracking-[-0.6px] text-[#272727] break-keep">{p.title}</h1>
            <p className="mt-2 text-sm text-[#888]">
              {site} · {p.category || '분야 미정'}
              {p.role ? ` · ${p.role}` : ''}
            </p>
          </div>
          <div className="shrink-0 flex flex-col items-start lg:items-end gap-3">
            <span className={'text-[26px] font-bold leading-9 tabular-nums ' + (priced ? 'text-(--color-accent)' : 'text-[#999]')}>{budgetLabel(p.budget)}</span>
            <a
              href={p.url}
              target="_blank"
              rel="noopener noreferrer"
              className={
                'inline-flex items-center h-11 px-6 rounded-[22px] text-[15px] font-bold ' +
                (closed ? 'border border-[#d8d8d8] bg-white text-[#666]' : 'bg-(--color-accent) text-white hover:opacity-90')
              }
            >
              {closed ? `${site}에서 원문 보기` : `${site}에서 지원하기`} ↗
            </a>
          </div>
        </header>

        <div className="mt-10 flex flex-col lg:flex-row gap-7 items-start">
          <main className="w-full lg:flex-1 min-w-0">
            <h2 className="text-[20px] font-bold leading-[29px] tracking-[-0.2px] text-[#272727]">프로젝트 내용</h2>
            <Body p={p} fromApi={fromApi} />
          </main>

          <aside className="w-full lg:w-[348px] shrink-0 flex flex-col gap-4">
            <section className="rounded-[22px] border border-[#e2e8ec] bg-white px-[23px] pt-[23px] pb-4">
              <h3 className="text-[17px] font-bold text-[#272727]">한눈에</h3>
              <dl className="mt-2">
                {facts.map(([k, v]) => (
                  <div key={k} className="flex gap-3 border-b border-[#f1f3f5] py-2.5 last:border-0 text-sm">
                    <dt className="w-[68px] shrink-0 text-[#888]">{k}</dt>
                    <dd className="min-w-0 flex-1 text-[#272727] break-keep">{v}</dd>
                  </div>
                ))}
              </dl>
            </section>
            {p.skills.length > 0 && (
              <section className="rounded-[22px] border border-[#e2e8ec] bg-white px-[23px] py-[22px]">
                <h3 className="text-[17px] font-bold text-[#272727]">기술</h3>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {p.skills.map((s) => (
                    <span key={s} className="rounded-md border border-[#e2e2e2] px-2 text-[13px] leading-6 text-[#474747]">
                      {s}
                    </span>
                  ))}
                </div>
              </section>
            )}
            {history.length > 1 && (
              <section className="rounded-[22px] border border-[#e2e8ec] bg-white px-[23px] py-[22px]">
                <h3 className="text-[17px] font-bold text-[#272727]">단가가 바뀐 기록</h3>
                <ul className="mt-2 text-sm">
                  {history.map((h) => (
                    <li key={h.at} className="flex justify-between border-b border-[#f1f3f5] py-2 last:border-0">
                      <span className="text-[#888] tabular-nums">{h.at.slice(0, 10)}</span>
                      <span className="text-[#272727] tabular-nums">{budgetLabel(h.budget)}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            {closed && state.reason && <p className="px-1 text-xs text-[#999]">마감 근거: {state.reason}</p>}
          </aside>
        </div>
      </div>
      <SiteFooter />
    </div>
  )
}

function Body({ p, fromApi }: { p: ProjectDetail; fromApi: boolean }) {
  const blocked = BODY_BLOCKED[p.site]
  const text = p.body ?? p.summary
  return (
    <>
      {text ? (
        <div className="mt-4 rounded-[22px] border border-[#e2e8ec] bg-white px-6 sm:px-[30px] py-[26px] break-words text-[15px] leading-[1.75] text-[#333]">
          {/* 원본 HTML 의 문단·줄바꿈이 빈 줄로 온다 — 빈 줄을 통째 띄우면 글이 성기니 문단 간격으로 바꾼다 */}
          {text.split(/\n{2,}/).map((para, i) => (
            <p key={i} className="whitespace-pre-line [&+p]:mt-1.5">
              {para}
            </p>
          ))}
        </div>
      ) : null}
      <p className="mt-3 text-xs leading-5 text-[#999]">
        {p.body
          ? `${SITE_KO[p.site] ?? p.site} 원문을 ${p.body_at?.slice(0, 10) ?? ''} 에 받아 옮겼어요. 이메일·전화번호는 지웠어요 — 문의·지원은 원문에서 해 주세요.`
          : blocked
            ? `${blocked} 위는 목록에 보이는 요약이에요.`
            : fromApi
              ? '본문을 아직 받지 못했어요 — 다음 수집 때 채워져요. 위는 목록에 보이는 요약이에요.'
              : '지금은 서버에 연결되지 않아 목록에 보이는 요약만 보여요.'}
      </p>
    </>
  )
}

function Chip({ children, tone }: { children: ReactNode; tone?: 'grade' | 'closed' }) {
  const cls =
    tone === 'grade' ? 'bg-[#f1efff] text-[#5b4fd6]' : tone === 'closed' ? 'bg-[#272727] text-white' : 'bg-white text-[#474747] border border-[#e2e2e2]'
  return <span className={'rounded px-[7px] text-[13px] leading-[22px] ' + cls}>{children}</span>
}
