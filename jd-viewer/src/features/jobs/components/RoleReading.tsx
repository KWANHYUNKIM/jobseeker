import { Fragment, useState } from 'react'
import type { RoleLine, RoleReading, RoleSource } from '../hooks/useRoleReading'
import { roleTokens } from '../utils/roleText'

// 공고 한 줄씩 읽기 — 읽는 순서를 세 겹으로 둔다(가독성 설계, 2026-11-23).
//  ① 공고 줄 + 바로 밑에 늘 보이는 한 줄 답(short) — 공고만 훑어도 뜻이 잡힌다
//  ② 누르면: 왜 필요한가 → 흐름(그림) → 실제로는 → 어디까지 (답 → 이유 → 그림 → 사례 → 기준)
//  ③ 예시·코드는 그 안에서 한 번 더 접는다
// 근거는 글 속 작은 번호(누르면 원문)로만 — 배지를 문장마다 붙이면 읽는 흐름이 끊긴다. 근거 없는 판단만 노란 '추론'.

const SRC_KIND: Record<RoleSource['kind'], string> = {
  company: '회사 발표',
  posting: '공고',
  news: '기사',
  reference: '참고 문서',
  community: '커뮤니티',
}

function RichText({ text, sources }: { text: string; sources: RoleSource[] }) {
  return (
    <>
      {roleTokens(text).map((t, i, all) => {
        if (t.kind === 'bold')
          return (
            <b key={i} className="font-semibold text-[#272727]">
              {t.text}
            </b>
          )
        if (t.kind === 'guess')
          return (
            <span key={i} className="mx-0.5 inline-block rounded-full bg-[#fff4d6] px-1.5 text-[11px] font-bold leading-[18px] text-[#8a5a00] align-[1px]" title="공개 근거 없이 정리한 판단">
              추론
            </span>
          )
        if (t.kind === 'ref') {
          const s = sources.find((x) => x.n === t.n)
          return (
            <a
              key={i}
              href={s?.url}
              target="_blank"
              rel="noopener noreferrer"
              title={s ? `${s.n}. ${s.title}${s.date ? ` (${s.date})` : ''}` : undefined}
              className="ml-px align-super text-[10px] font-semibold text-[#3657c8] no-underline hover:underline"
            >
              {all[i - 1]?.kind === 'ref' ? `,${t.n}` : t.n}
            </a>
          )
        }
        return <Fragment key={i}>{t.text}</Fragment>
      })}
    </>
  )
}

/** 공고 본문 맨 위 — 답부터. */
export function RoleSummary({ r, allOpen, onToggleAll }: { r: RoleReading; allOpen: boolean; onToggleAll: () => void }) {
  const rows: [string, string][] = [
    ['무엇을', r.tldr.what],
    ['어떤 환경', r.tldr.env],
    ['한마디로', r.tldr.oneline],
  ]
  return (
    <section className="rounded-2xl border border-[#dbe5ff] bg-[#f5f8ff] px-6 py-5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h3 className="text-[17px] font-bold text-[#272727]">이 자리, 30초 요약</h3>
        <span className="text-[13px] text-[#777]">
          공고 줄마다 풀이 {r.lines.length}개 · 출처 {r.sources.length}곳 · {r.researched_at} 조사
        </span>
        <button
          type="button"
          onClick={onToggleAll}
          className="ml-auto h-8 rounded-lg border border-[#c9d6f5] bg-white px-3 text-[13px] font-medium text-[#272727] hover:border-[#272727]"
        >
          {allOpen ? '풀이 모두 접기' : '풀이 모두 펼치기'}
        </button>
      </div>
      <dl className="mt-3 grid grid-cols-[76px_1fr] gap-x-4 gap-y-2 text-[15px] leading-[24px] text-[#474747] max-sm:grid-cols-1 max-sm:gap-y-0.5">
        {rows.map(([k, v]) => (
          <Fragment key={k}>
            <dt className="pt-px text-[13px] font-semibold text-[#777] max-sm:mt-2">{k}</dt>
            <dd>
              <RichText text={v} sources={r.sources} />
            </dd>
          </Fragment>
        ))}
      </dl>
    </section>
  )
}

/** 공고 줄 하나 밑 — 늘 보이는 한 줄 + 펼치면 풀이. */
export function RoleLineNote({ line, sources, open, onToggle }: { line: RoleLine; sources: RoleSource[]; open: boolean; onToggle: () => void }) {
  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="group flex w-full items-start gap-2 rounded-lg px-2.5 py-1.5 -mx-2.5 text-left hover:bg-[#f5f8ff]"
      >
        <span className="mt-[3px] shrink-0 rounded bg-[#e7edff] px-1.5 text-[11px] font-bold leading-[18px] text-[#3657c8]">풀이</span>
        <span className="min-w-0 flex-1 text-[14.5px] leading-[22px] text-[#474747]">
          <RichText text={line.short} sources={sources} />
        </span>
        <span className="mt-[2px] shrink-0 whitespace-nowrap text-[12.5px] text-[#999] group-hover:text-[#3657c8]">
          {open ? '접기 ▴' : '자세히 ▾'}
        </span>
      </button>
      {open && <LineDetail line={line} sources={sources} />}
    </div>
  )
}

function Label({ children }: { children: React.ReactNode }) {
  return <div className="pt-[2px] text-[13px] font-semibold text-[#777]">{children}</div>
}

function LineDetail({ line, sources }: { line: RoleLine; sources: RoleSource[] }) {
  const t = (s: string) => <RichText text={s} sources={sources} />
  return (
    <div className="mt-2 rounded-xl border border-[#e2e8ec] bg-white px-5 py-4 text-[15px] leading-[25px] text-[#3a3a3a]">
      <div className="grid grid-cols-[92px_1fr] gap-x-4 gap-y-4 max-sm:grid-cols-1 max-sm:gap-y-1">
        <Label>왜 필요한가</Label>
        <div>{t(line.why)}</div>

        {line.flows && line.flows.length > 0 && (
          <>
            <Label>흐름</Label>
            <div className="space-y-3">
              {line.flows.map((f, fi) => (
                <div key={fi}>
                  <div className="mb-1.5 text-[13px] text-[#666]">{t(f.caption)}</div>
                  <div className="flex flex-wrap items-stretch gap-1.5">
                    {f.steps.map((s, si) => {
                      const [name, desc] = s.split(' · ')
                      const mine = f.mine_from != null && si >= f.mine_from
                      return (
                        <Fragment key={si}>
                          {si > 0 && <span className="self-center text-[#aaa]" aria-hidden>→</span>}
                          <span className={'rounded-lg border px-2.5 py-1 text-[13.5px] leading-[19px] ' + (mine ? 'border-[#b9cdf7] bg-[#eef3ff]' : 'border-[#e2e8ec] bg-[#f7f9fa]')}>
                            <b className="font-semibold">{name}</b>
                            {desc && <span className="block text-[12px] text-[#777]">{desc}</span>}
                          </span>
                        </Fragment>
                      )
                    })}
                  </div>
                  {f.mine_from != null && <div className="mt-1 text-[12px] text-[#777]">파란 칸이 이 자리가 맡는 부분</div>}
                </div>
              ))}
            </div>
          </>
        )}

        {line.actually && line.actually.items.length > 0 && (
          <>
            <Label>실제로는</Label>
            <div>
              {line.actually.intro && <p className="mb-1.5 text-[14px] text-[#666]">{t(line.actually.intro)}</p>}
              <ol className="space-y-1.5">
                {line.actually.items.map((it, i) => (
                  <li key={i} className="grid grid-cols-[20px_1fr] gap-1">
                    <span className="text-[13px] font-bold tabular-nums text-[#3657c8]">{i + 1}</span>
                    <span>{t(it)}</span>
                  </li>
                ))}
              </ol>
            </div>
          </>
        )}

        {line.level && (
          <>
            <Label>필요한 수준</Label>
            <div className="grid grid-cols-3 gap-2 max-sm:grid-cols-1">
              {(
                [
                  ['기본', line.level.basic, false],
                  ['실무', line.level.work, false],
                  ['이 팀 수준', line.level.team, true],
                ] as const
              ).map(([k, v, top]) => (
                <div key={k} className={'rounded-lg px-3 py-2 text-[13.5px] leading-[20px] ' + (top ? 'bg-[#eef3ff] ring-1 ring-[#b9cdf7]' : 'bg-[#f7f9fa]')}>
                  <div className="mb-0.5 text-[12px] font-bold text-[#272727]">{k}</div>
                  {v}
                </div>
              ))}
            </div>
          </>
        )}

        {line.examples && line.examples.length > 0 && (
          <>
            <Label>예시</Label>
            <div className="space-y-2">
              {line.examples.map((ex, i) => (
                <Example key={i} ex={ex} sources={sources} />
              ))}
            </div>
          </>
        )}

        {line.how_far && (
          <>
            <Label>어디까지</Label>
            <div className="rounded-lg bg-[#f7f9fa] px-3 py-2">{t(line.how_far)}</div>
          </>
        )}
      </div>
    </div>
  )
}

function Example({ ex, sources }: { ex: NonNullable<RoleLine['examples']>[number]; sources: RoleSource[] }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="rounded-lg border border-[#e2e8ec]">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} className="flex w-full items-center gap-2 px-3 py-2 text-left text-[14px] font-semibold text-[#272727] hover:bg-[#f7f9fa]">
        {ex.code && <span className="rounded bg-[#272727] px-1.5 text-[10.5px] font-bold leading-[17px] text-white">{ex.lang}</span>}
        <span className="flex-1">{ex.title}</span>
        <span className={'text-[12px] text-[#999] ' + (open ? 'rotate-180' : '')} aria-hidden>
          ▾
        </span>
      </button>
      {open && (
        <div className="border-t border-[#e2e8ec] px-3 py-2.5 text-[14px] leading-[23px]">
          <RichText text={ex.body} sources={sources} />
          {ex.code && <pre className="mt-2 overflow-x-auto rounded-lg bg-[#0f172a] px-3 py-2.5 text-[12.5px] leading-[19px] text-[#e2e8f0]">{ex.code}</pre>}
        </div>
      )}
    </div>
  )
}

/** 오른쪽 칸 — 맞는 사람 · 면접 질문 · 출처. */
export function RoleAside({ r }: { r: RoleReading }) {
  const [allSrc, setAllSrc] = useState(false)
  const shown = allSrc ? r.sources : r.sources.slice(0, 5)
  return (
    <div className="rounded-[22px] border border-[#e2e8ec] bg-white px-6 py-6">
      <div className="text-[17px] font-bold text-[#272727]">이 자리 더 알아보기</div>
      <div className="mt-0.5 text-[13px] text-[#777]">
        {r.company} · {r.role}
      </div>

      {r.fit && (
        <div className="mt-5 space-y-4">
          <AsideList title="잘 맞는 사람" tone="text-[#067a06]" items={r.fit.good} sources={r.sources} />
          <AsideList title="힘들 수 있는 점" tone="text-[#b42323]" items={r.fit.hard} sources={r.sources} />
        </div>
      )}

      {r.interview && r.interview.length > 0 && (
        <div className="mt-6">
          <div className="text-[14px] font-bold text-[#272727]">면접에서 나올 만한 질문</div>
          <div className="mb-2 text-[12px] text-[#999]">회사 발표에 나온 실제 문제로 만든 예상 질문</div>
          <ul className="space-y-2">
            {r.interview.map((q, i) => (
              <li key={i} className="rounded-lg bg-[#f7f9fa] px-3 py-2 text-[14px] leading-[21px]">
                <div className="font-medium text-[#272727]">{q.q}</div>
                <div className="mt-0.5 text-[12.5px] text-[#777]">
                  <RichText text={q.a} sources={r.sources} />
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-6">
        <div className="text-[14px] font-bold text-[#272727]">출처</div>
        <ol className="mt-2 space-y-2">
          {shown.map((s) => (
            <li key={s.n} className="grid grid-cols-[18px_1fr] gap-1 text-[13px] leading-[19px]">
              <span className="tabular-nums text-[#999]">{s.n}</span>
              <span className="min-w-0">
                <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-[#272727] hover:underline">
                  {s.title}
                </a>
                <span className="block text-[11.5px] text-[#999]">
                  {SRC_KIND[s.kind]}
                  {s.date && ` · ${s.date}`}
                  {s.note && ` · ${s.note}`}
                </span>
              </span>
            </li>
          ))}
        </ol>
        {r.sources.length > 5 && (
          <button type="button" onClick={() => setAllSrc((v) => !v)} className="mt-2 text-[13px] font-medium text-[#3657c8] hover:underline">
            {allSrc ? '출처 줄이기' : `출처 ${r.sources.length}개 모두 보기`}
          </button>
        )}
        {r.caveat && <p className="mt-3 text-[12px] leading-[18px] text-[#999]">{r.caveat}</p>}
      </div>
    </div>
  )
}

function AsideList({ title, tone, items, sources }: { title: string; tone: string; items: string[]; sources: RoleSource[] }) {
  return (
    <div>
      <div className={'text-[14px] font-bold ' + tone}>{title}</div>
      <ul className="mt-1 space-y-1 text-[14px] leading-[21px] text-[#474747]">
        {items.map((it, i) => (
          <li key={i} className="flex gap-1.5">
            <span aria-hidden className="text-[#bbb]">
              ·
            </span>
            <span>
              <RichText text={it} sources={sources} />
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
