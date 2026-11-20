import { useState, type ReactNode } from 'react'
import { SiteFooter } from '../../../components/SiteFooter'
import { ErrorState, Loader } from '../../../components/ui'
import { onLinkClick } from '../../../utils/navigation'
import { useSeo } from '../../../utils/seo'
import { paths } from '../../../utils/urls'
import { careersKey, fetchStory, setCareersKey } from '../api'
import { useAsync } from '../hooks/useAsync'
import { Card, Steps } from './parts'

const NOINDEX = 'noindex, nofollow'

const hostOf = (u: string) => {
  try {
    return new URL(u).host
  } catch {
    return u
  }
}

const strs = (v: unknown): string[] =>
  Array.isArray(v) ? v.filter((x) => x !== null && x !== undefined && typeof x !== 'object' && String(x).trim() && String(x) !== 'null').map(String) : typeof v === 'string' && v.trim() && v !== 'null' ? [v] : []

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex gap-3 py-1.5 text-sm border-b border-[#f4f4f4] last:border-0">
      <dt className="w-[96px] shrink-0 text-[#999]">{label}</dt>
      <dd className="flex-1 min-w-0 text-[#333]">{children}</dd>
    </div>
  )
}

function List({ xs }: { xs: string[] }) {
  if (!xs.length) return <span className="text-[#bbb]">—</span>
  return (
    <ul className="list-disc pl-4 flex flex-col gap-0.5">
      {xs.map((x, i) => (
        <li key={i}>{x}</li>
      ))}
    </ul>
  )
}

export function StoryView({ id }: { id: string }) {
  const [key, setKey] = useState(careersKey())
  const { data: s, error, loading } = useAsync((sig) => fetchStory(id, key, sig), `${id}|${key}`)
  useSeo({ title: s?.title ?? '후기', description: '혼자 보는 취업 자료', robots: NOINDEX })

  if (loading && !s) return <Loader label="후기 여는 중…" />
  if (!s) return <ErrorState title="후기를 못 읽었다" detail={error ?? ''} />

  const spec = s.spec ?? {}
  const sel = s.selection ?? {}
  const app = s.application ?? {}
  const bg = s.background ?? {}
  const back = paths.careers()
  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container max-w-[980px] pt-[43px] pb-[90px]">
        <nav className="text-sm text-[#999]">
          <a href={paths.wiki()} onClick={onLinkClick(paths.wiki())} className="hover:text-[#272727]">
            기술도서
          </a>
          <span className="mx-1.5">›</span>
          <a href={back} onClick={onLinkClick(back)} className="hover:text-[#272727]">
            취업
          </a>
        </nav>
        <h1 className="mt-2 text-[24px] font-bold leading-9 text-[#272727]">{s.title ?? '(제목 없음)'}</h1>
        <p className="mt-1 text-sm text-[#888]">
          {[s.source, s.posted_on, s.year && `${s.year}년${s.year_from === 'posted' ? '(게시 연도)' : ''}`, s.period, s.kind].filter(Boolean).join(' · ')}
        </p>
        {s.summary && <p className="mt-4 rounded-xl bg-[#f6f7f9] p-4 text-[15px] leading-relaxed text-[#333]">{s.summary}</p>}

        <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card title="어디로">
            <dl>
              <Field label="간 곳">
                {s.company ?? s.company_desc ?? '밝히지 않음'}
                {s.company_from === 'other_companies' && <span className="ml-1 text-xs text-[#aaa]">(지원처 중 최종 합격)</span>}
              </Field>
              <Field label="회사 유형">{[s.company_type, s.company_size].filter(Boolean).join(' · ') || '—'}</Field>
              <Field label="직무">{s.role ?? '—'}</Field>
              <Field label="구분">{[s.level, s.years_before ? `그 전 경력 ${s.years_before}년` : null].filter(Boolean).join(' · ') || '—'}</Field>
              <Field label="출발지">{s.origin ?? '—'}</Field>
              <Field label="전환">{[s.transition_cat, s.transition].filter(Boolean).join(' — ') || '—'}</Field>
            </dl>
          </Card>
          <Card title="스펙">
            <dl>
              <Field label="학력">{[s.education, strs(bg.major_field)[0]].filter(Boolean).join(' · ') || '—'}</Field>
              <Field label="나이">{s.age ? `${s.age}세` : '—'}</Field>
              <Field label="학점">{strs(spec.gpa)[0] ?? '—'}</Field>
              <Field label="자격증">{strs(spec.certs).join(', ') || '—'}</Field>
              <Field label="어학">{strs(spec.language).join(', ') || '—'}</Field>
              <Field label="알고리즘">{strs(spec.algorithm)[0] ?? '—'}</Field>
              <Field label="대외활동">{strs(spec.activities).join(', ') || '—'}</Field>
              <Field label="인턴">{strs(spec.internships).join(', ') || '—'}</Field>
              <Field label="수상">{strs(spec.awards).join(', ') || '—'}</Field>
              <Field label="교육과정">{strs(bg.bootcamp).join(', ') || s.program || '—'}</Field>
              <Field label="기술">{(s.stack ?? []).join(', ') || '—'}</Field>
            </dl>
          </Card>
        </div>

        <Card title="경로" className="mt-4" note={s.prep_months ? `준비 기간 ${s.prep_months}개월` : undefined}>
          <Steps steps={(s.path ?? []).map((p) => (p.months ? `${p.step} (${p.months}개월)` : p.step))} />
        </Card>

        <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card title="전형">
            <dl>
              <Field label="코딩테스트">{strs(sel.coding_test).join(', ') || '—'}</Field>
              <Field label="과제">{strs(sel.assignment).join(', ') || '—'}</Field>
              <Field label="면접">
                <List xs={strs(sel.interviews)} />
              </Field>
              <Field label="나온 질문">
                <List xs={strs(sel.notable_questions)} />
              </Field>
            </dl>
          </Card>
          <Card title="같이 지원한 곳">
            {(s.other_companies ?? []).length ? (
              <ul className="text-sm flex flex-col gap-1">
                {(s.other_companies ?? []).map((o, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="font-semibold">{o.company ?? '?'}</span>
                    <span className={/불|탈락/.test(o.result ?? '') ? 'text-rose-700' : 'text-emerald-700'}>{o.result}</span>
                    {o.stage && <span className="text-[#999]">{o.stage}</span>}
                  </li>
                ))}
              </ul>
            ) : (
              <span className="text-sm text-[#bbb]">—</span>
            )}
          </Card>
          <Card title="준비·붙은 이유·조언">
            <dl>
              <Field label="준비 방법">
                <List xs={strs(s.prep_methods)} />
              </Field>
              <Field label="붙은 이유">
                <List xs={strs(s.key_factors)} />
              </Field>
              <Field label="조언">
                <List xs={strs(s.advice)} />
              </Field>
              {s.market_note && <Field label="그때 시장">{s.market_note}</Field>}
            </dl>
          </Card>
          <Card title="서류">
            <dl>
              <Field label="이력서">
                <List xs={[...strs(app.resume), ...strs(app.resume_points)]} />
              </Field>
              <Field label="포트폴리오">
                <List xs={[...strs(app.portfolio), ...strs(app.portfolio_points), ...strs(app.portfolio_projects)]} />
              </Field>
              <Field label="자기소개서">
                <List xs={[...strs(app.cover_letter_points), ...strs(app.cover_letter_questions)]} />
              </Field>
              <Field label="서류 결과">{strs(app.doc_result)[0] ?? '—'}</Field>
            </dl>
          </Card>
        </div>

        <Card
          title="원문"
          className="mt-4"
          note={
            <>
              DB(career_post)에 보관한 판 — {s.body_chars.toLocaleString()}자.
              {s.url && (
                <>
                  {' '}
                  처음 본 곳:{' '}
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className="underline">
                    {hostOf(s.url)}
                  </a>
                </>
              )}
            </>
          }
        >
          {s.body_locked ? (
            <KeyForm
              onSave={(v) => {
                setCareersKey(v)
                setKey(v)
              }}
              tried={!!key}
            />
          ) : (
            <>
              <div className="whitespace-pre-wrap break-words text-[14px] leading-7 text-[#333] max-h-[70vh] overflow-auto">{s.body}</div>
              <button
                type="button"
                className="mt-3 text-xs text-[#aaa] underline"
                onClick={() => {
                  setCareersKey('')
                  setKey('')
                }}
              >
                이 브라우저에서 열쇠 지우기
              </button>
            </>
          )}
        </Card>
      </div>
      <SiteFooter />
    </div>
  )
}

function KeyForm({ onSave, tried }: { onSave: (v: string) => void; tried: boolean }) {
  const [v, setV] = useState('')
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        onSave(v.trim())
      }}
      className="flex flex-col gap-2 text-sm"
    >
      <p className="text-[#666]">
        남의 글이라 원문은 열쇠가 있어야 열린다. 뷰어 API 의 환경변수 <code>CAREERS_KEY</code> 값을 넣으면 이 브라우저에 기억한다.
        {tried && <span className="block text-rose-700 mt-1">넣어 둔 열쇠가 맞지 않거나, 서버에 CAREERS_KEY 가 없다.</span>}
      </p>
      <div className="flex gap-2">
        <input type="password" value={v} onChange={(e) => setV(e.target.value)} placeholder="열쇠" className="w-[240px] rounded-lg border border-[#ddd] px-3 py-1.5" />
        <button type="submit" className="rounded-lg bg-[#272727] px-3 py-1.5 text-white">
          열기
        </button>
      </div>
    </form>
  )
}
