import { Fragment, useEffect, useRef, useState } from 'react'
import {
  useJobGuide,
  sortStudy,
  PRIORITY_LABEL,
  PRIORITY_COLOR,
  FROM_LABEL,
  type AutoGuide,
  type AutoPosting,
  type CompanyGuide,
  type GuidePosting,
  type Source,
  type StudyItem,
} from './useGuide'
import { Md } from '../../shared/ui/Md'

interface Props {
  company: string
  url: string
  /** 지금 본문에서 하이라이트 중인 문장. 학습 항목을 펼치면 그 항목의 quote 가 된다. */
  activeQuote: string | null
  onQuote: (q: string | null) => void
}

/**
 * 공고 오른쪽에 붙는 취업 브리핑 패널.
 *
 * 왼쪽 JD 가 "회사가 원하는 것"이라면 여기는 "그래서 내가 뭘 하나"다. 두 개를 같은
 * 화면에 놓는 것이 이 화면의 전부다 — 공고를 닫고 다른 탭에서 공부거리를 찾는 순간
 * 어느 문장 때문에 그걸 공부하는지가 끊긴다. 그래서 학습 항목마다 원문 문장을 들고
 * 있고, 항목을 펼치면 왼쪽 본문의 그 문장이 켜진다.
 */
export function JobGuide({ company, url, activeQuote, onQuote }: Props) {
  const { loading, guide, posting, auto, autoPosting } = useJobGuide(company, url)

  if (loading) {
    return (
      <PanelShell>
        <p className="text-xs text-(--color-muted)">가이드 불러오는 중…</p>
      </PanelShell>
    )
  }

  const fallback = { auto, autoPosting }
  if (!guide) return <NotYet company={company} kind="company" {...fallback} />
  if (!posting) return <NotYet company={company} kind="posting" guide={guide} {...fallback} />

  return (
    <PanelShell>
      <GuideHeader guide={guide} posting={posting} />
      <StudySection posting={posting} activeQuote={activeQuote} onQuote={onQuote} />
      <EdgeSection posting={posting} />
      <InterviewSection posting={posting} />
      <SalarySection guide={guide} />
      <PeopleSection guide={guide} />
      <CompanySection guide={guide} />
      {guide.open_questions && guide.open_questions.length > 0 && (
        <Block title="아직 모르는 것" icon="❓">
          <ul className="space-y-1">
            {guide.open_questions.map((q, i) => (
              <li key={i} className="text-xs text-(--color-muted) leading-relaxed">
                · <Md>{q}</Md>
              </li>
            ))}
          </ul>
        </Block>
      )}
      <p className="text-[11px] text-(--color-faint) leading-relaxed pt-1">
        공개 자료로 재구성한 브리핑입니다. <Badge>추정</Badge> 이 붙은 항목은 확인된 사실이
        아니라 공개 자료에서 추론한 것입니다. {guide.updated_at} 기준.
      </p>
    </PanelShell>
  )
}

function PanelShell({ children }: { children: React.ReactNode }) {
  return <div className="space-y-4">{children}</div>
}

// ── 브리핑이 아직 없을 때 ────────────────────────────────────────────────
// 빈 패널을 그냥 두지 않는 이유: 이 화면에서 "왜 비었는지"와 "어떻게 채우는지"를
// 안 알려주면, 며칠 뒤엔 이 자리가 원래 비어 있는 자리인 줄 알게 된다.
function NotYet({
  company,
  kind,
  guide,
  auto,
  autoPosting,
}: {
  company: string
  kind: 'company' | 'posting'
  guide?: CompanyGuide
  auto: AutoGuide | null
  autoPosting: AutoPosting | null
}) {
  return (
    <PanelShell>
      <div className="border border-dashed border-(--color-border) rounded-lg p-4">
        <h3 className="text-sm font-medium text-(--color-text) mb-1.5">
          {kind === 'company' ? '아직 조사하지 않은 회사입니다' : '이 공고는 아직입니다'}
        </h3>
        <p className="text-xs text-(--color-muted) leading-relaxed">
          {kind === 'company' ? (
            <>
              <span className="text-(--color-text)">{company}</span> 의 학습 로드맵·연봉·인물
              조사가 아직 없습니다. 취업 브리핑 엔진이 대기열 순서대로 한 사이클에 한 곳씩
              채웁니다.
            </>
          ) : (
            <>
              <span className="text-(--color-text)">{company}</span> 회사 브리핑은 있지만 이
              공고는 아직 안 채웠습니다. 아래 회사 정보는 지금도 볼 수 있습니다.
            </>
          )}
        </p>
        <pre className="mt-3 text-[11px] bg-(--color-bg) border border-(--color-border) rounded px-2.5 py-2 overflow-x-auto text-(--color-muted)">
          {kind === 'company'
            ? `# guide-engine/state/QUEUE.md 의 "## 대기" 에 추가한 뒤\n/loop 30m /hireguide`
            : `/loop 30m /hireguide`}
        </pre>
      </div>
      {auto && (
        <AutoBrief auto={auto} posting={autoPosting} />
      )}
      {guide && (
        <>
          <SalarySection guide={guide} />
          <PeopleSection guide={guide} />
          <CompanySection guide={guide} />
        </>
      )}
    </PanelShell>
  )
}

// ── 자동 브리핑(폴백) ────────────────────────────────────────────────────
// 손으로 쓴 브리핑이 없는 회사에서 화면을 빈 채로 두지 않는다. 다만 **이게 저것의
// 축소판인 척하면 안 된다** — 여기 있는 건 정규식이 공고에서 뽑은 사실뿐이고,
// "왜 필요한가"·"뭘 만들어 볼까"는 아예 없다. 그래서 색을 브랜드색으로 쓰지 않고
// (그건 사람이 쓴 브리핑의 색이다), 무엇이 비어 있는지를 맨 아래 그대로 적는다.
function AutoBrief({
  auto,
  posting,
}: {
  auto: AutoGuide
  posting: AutoPosting | null
}) {
  const facts = Object.values(auto.facts || {})
  const salary = auto.salary_mentions || []
  const dupOf = (auto.duplicates || []).find((g) =>
    g.postings.some((p) => p.url === posting?.url),
  )
  const flags = posting?.employment_flags || []
  const shared = posting?.shared_stack || []
  const onlyHere = posting?.only_here || []
  const careers = careerSpread(auto)

  // 담을 것이 하나도 없으면 패널을 그리지 않는다. 빈 상자를 놓아 두면 "이 회사는
  // 정보가 없다"가 아니라 "이 화면이 고장 났다"로 읽힌다.
  if (
    !facts.length && !salary.length && !dupOf && !flags.length &&
    !shared.length && !onlyHere.length &&
    careers.bands.length + careers.unparsed.length + (careers.any ? 1 : 0) < 2
  ) {
    return null
  }

  return (
    <>
      <div className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-xs font-medium tracking-wider text-(--color-muted)">
            이 공고에 안 적힌 것
          </span>
          <span className="text-[10px] px-1.5 py-0.5 rounded border border-(--color-border) text-(--color-faint)">
            자동 추출
          </span>
        </div>
        <p className="text-xs text-(--color-muted) leading-relaxed">
          사람이 쓴 브리핑을 기다리는 동안, 이 회사의 다른 공고를 모아 본 것입니다.
          왼쪽에 이미 적힌 문장은 옮기지 않습니다. 모집중{' '}
          <span className="text-(--color-text) tabular-nums">{auto.counts.active}</span>건 중 중복을
          뺀 실제 자리{' '}
          <span className="text-(--color-text) tabular-nums">{auto.counts.distinct_active}</span>개
          · {auto.generated_at} 기준.
        </p>
      </div>

      {flags.length > 0 && (
        <div className="rounded-lg border border-(--color-amber-400)/40 bg-(--color-amber-400)/8 p-3.5">
          <div className="flex flex-wrap items-center gap-1.5 mb-1">
            {flags.map((f) => (
              <Badge key={f}>{f}</Badge>
            ))}
          </div>
          <p className="text-xs text-(--color-muted) leading-relaxed">
            공고 본문에 위 표기가 있습니다. 정규직 상시 자리와 준비할 것이 달라집니다.
          </p>
        </div>
      )}

      {dupOf && (
        <Block title="같은 자리가 여기에도" icon="⧉" hint={dupOf.reason}>
          <ul className="space-y-1">
            {dupOf.postings
              .filter((p) => p.url !== posting?.url)
              .map((p) => (
                <li key={p.url} className="text-xs leading-relaxed">
                  <a
                    href={p.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-(--color-muted) hover:text-(--color-accent)"
                  >
                    <span className="text-(--color-faint)">{p.site}</span> · {p.title}
                  </a>
                </li>
              ))}
          </ul>
        </Block>
      )}

      {(shared.length > 0 || onlyHere.length > 0) && (
        <Block title="회사의 바탕 / 이 자리만의 것" icon="◆" hint="다른 공고와 대조한 것">
          {shared.length > 0 && (
            <div className="mb-2">
              <FieldLabel>이 회사 다른 공고에도 나오는 기술</FieldLabel>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {shared.map((t) => (
                  <span key={t} className="text-[10px] px-1.5 py-0.5 rounded bg-(--color-bg) text-(--color-muted)">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}
          {onlyHere.length > 0 && (
            <div>
              <FieldLabel>이 공고에만 나오는 기술</FieldLabel>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {onlyHere.map((t) => (
                  <span
                    key={t}
                    className="text-[10px] px-1.5 py-0.5 rounded border border-(--color-accent)/40 text-(--color-accent)"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}
        </Block>
      )}

      {careers.bands.length + careers.unparsed.length + (careers.any ? 1 : 0) >= 2 && (
        <Block title="이 회사가 뽑는 연차" icon="▤" hint="모집중 공고 전부">
          <CareerChart spread={careers} />
        </Block>
      )}

      {facts.length > 0 && (
        <Block title="회사 규모" icon="▦" hint="다른 공고에 회사가 직접 적은 값">
          <dl className="space-y-1.5">
            {facts.map((f) => (
              <div key={f.label} className="flex items-baseline gap-2">
                <dt className="text-[10px] tracking-wider text-(--color-faint) w-14 shrink-0">
                  {f.label}
                </dt>
                <dd className="text-xs text-(--color-text)">
                  <Md>{f.value}</Md>
                  <span className="text-[10px] text-(--color-faint) ml-1.5 tabular-nums">
                    공고 {f.seen_in}/{f.of_postings}건에 반복
                  </span>
                </dd>
              </div>
            ))}
          </dl>
        </Block>
      )}

      {salary.length > 0 && (
        <Block title="연봉" icon="₩" hint="이 회사 공고 원문에 숫자가 적힌 것">
          <ul className="space-y-2">
            {salary.map((sm, i) => (
              <li key={i}>
                <div className="text-[13px] text-(--color-text) tabular-nums">
                  {sm.low.toLocaleString()}
                  {sm.high ? `~${sm.high.toLocaleString()}` : ''} {sm.unit}
                  {sm.bound !== 'point' && sm.bound !== 'range' ? ` ${sm.bound}` : ''}
                </div>
                <div className="text-[10px] text-(--color-faint) mt-0.5">
                  {sm.title}
                  {sm.career ? ` · ${sm.career}` : ''}
                </div>
              </li>
            ))}
          </ul>
        </Block>
      )}

      {auto.gaps && auto.gaps.length > 0 && (
        <Block title="여기 없는 것" icon="○" hint="코드가 못 채우는 칸">
          <ul className="space-y-1.5">
            {auto.gaps.map((g) => (
              <li key={g.field} className="text-xs leading-relaxed">
                <span className="text-(--color-text)">{g.field}</span>
                <span className="text-(--color-faint)"> — {g.needs}</span>
              </li>
            ))}
          </ul>
        </Block>
      )}
    </>
  )
}

// ── 뽑는 연차 ───────────────────────────────────────────────────────────
// 표기 문자열을 세면 `경력 3-10년` 과 `경력 3~10년` 이 남남이 되어 전부 ×1 로
// 흩어진다. 데이터에는 이미 min_years·max_years 가 파싱돼 있으니 그걸 쓴다.
// 세로로 늘어놓은 글자보다 공통 축 위의 막대가 '이 회사가 노리는 구간'을 바로
// 보여준다 — 겹치는 자리가 곧 그 회사의 중심 연차다.

interface CareerBand {
  key: string
  min: number
  max: number | null // null = '이상' — 끝이 열려 있다
  n: number
  label: string
  raws: string[]
}

interface CareerSpread {
  bands: CareerBand[]
  /** 연차를 안 따지는 공고(경력무관·신입·경력) — 축에 올리면 0→∞ 막대가 화면을 먹는다. */
  any: number
  /** 숫자로 못 읽은 표기. 그대로 적어 준다 — 조용히 버리지 않는다. */
  unparsed: [string, number][]
  domain: number
  total: number
}

function careerSpread(auto: AutoGuide): CareerSpread {
  const by = new Map<string, CareerBand>()
  const un = new Map<string, number>()
  let any = 0
  let total = 0

  for (const p of auto.postings || []) {
    const c = p.career
    if (p.closed || !c?.raw) continue
    total++
    if (c.kind === '경력무관' || c.kind === '신입포함') {
      any++
      continue
    }
    if (c.min_years === null || c.min_years === undefined) {
      un.set(c.raw, (un.get(c.raw) || 0) + 1)
      continue
    }
    const min = c.min_years
    const max = c.max_years ?? null
    const key = `${min}:${max ?? '+'}`
    const hit = by.get(key)
    if (hit) {
      hit.n++
      if (!hit.raws.includes(c.raw)) hit.raws.push(c.raw)
    } else {
      by.set(key, {
        key,
        min,
        max,
        n: 1,
        label: max === null ? `${min}년↑` : min === max ? `${min}년` : `${min}–${max}년`,
        raws: [c.raw],
      })
    }
  }

  const bands = [...by.values()].sort((a, b) => a.min - b.min || (a.max ?? 99) - (b.max ?? 99))
  // 열린 막대는 화살표로 끝나므로 축이 그 min 보다는 넉넉해야 한다.
  const need = bands.reduce((m, b) => Math.max(m, b.max ?? b.min + 3), 0)
  const domain = Math.max(4, Math.ceil(need / 2) * 2)
  return { bands, any, unparsed: [...un.entries()].sort((a, b) => b[1] - a[1]), domain, total }
}

// 축 눈금 — 폭이 좁아 5~6개를 넘기면 숫자가 서로 붙는다. 그래서 축 끝까지
// 딱 나누어떨어지는 간격을 먼저 고른다. 남는 간격을 쓰면 마지막 눈금과 축 끝이
// 나란히 서서 `9 10` 처럼 겹친다.
function ticksFor(domain: number): number[] {
  const step =
    [1, 2, 3, 5, 10, 15, 20].find((s) => domain % s === 0 && domain / s <= 5) ??
    [2, 3, 5, 10, 15, 20].find((s) => domain / s <= 5) ??
    domain
  const out: number[] = []
  for (let v = 0; v <= domain; v += step) out.push(v)
  // 나누어떨어지지 않아 끝이 빈 경우에만 축 끝을 더한다 — 너무 붙으면 앞을 뺀다.
  if (out[out.length - 1] !== domain) {
    if (domain - out[out.length - 1] < step * 0.6) out.pop()
    out.push(domain)
  }
  return out
}

function CareerChart({ spread }: { spread: CareerSpread }) {
  const { bands, any, unparsed, domain, total } = spread
  const pct = (v: number) => (v / domain) * 100
  const peak = Math.max(...bands.map((b) => b.n), 1)

  return (
    <div>
      {bands.length > 0 && (
        <>
          {/* 눈금 — 막대와 같은 좌표계를 쓰도록 라벨 칸만큼 밀어 둔다 */}
          <div className="flex items-center gap-2 mb-1">
            <span className="w-14 shrink-0" />
            <div className="relative flex-1 h-3">
              {ticksFor(domain).map((t) => (
                <span
                  key={t}
                  className="absolute top-0 text-[9px] text-(--color-faint) tabular-nums -translate-x-1/2"
                  style={{ left: `${pct(t)}%` }}
                >
                  {t}
                </span>
              ))}
            </div>
            <span className="w-6 shrink-0 text-[9px] text-(--color-faint)">년</span>
          </div>

          <ul className="space-y-1">
            {bands.map((b) => {
              const left = pct(b.min)
              const right = b.max === null ? 100 : pct(b.max)
              // 한 점(min==max)도 눈에 보이게 최소 폭을 준다.
              const w = Math.max(right - left, 2.5)
              return (
                <li
                  key={b.key}
                  className="flex items-center gap-2"
                  title={`${b.raws.join(' · ')} — 공고 ${b.n}건`}
                >
                  <span className="w-14 shrink-0 text-[10px] text-(--color-text) tabular-nums text-right">
                    {b.label}
                  </span>
                  <div className="relative flex-1 h-3.5">
                    {/* 바탕 눈금선 — 막대가 없는 구간에서도 축이 읽히게 */}
                    {ticksFor(domain).map((t) => (
                      <span
                        key={t}
                        className="absolute inset-y-0 w-px bg-(--color-border)/50"
                        style={{ left: `${pct(t)}%` }}
                      />
                    ))}
                    <span
                      className="absolute inset-y-0 rounded-[3px] bg-(--color-accent)"
                      style={{
                        left: `${left}%`,
                        width: `${w}%`,
                        // 건수가 곧 진하기다(같은 색조 한 가지 — 순서형)
                        opacity: 0.35 + 0.65 * (b.n / peak),
                        // 끝이 열린 막대는 오른쪽 모서리를 깎아 화살표처럼 뺀다
                        ...(b.max === null
                          ? { clipPath: 'polygon(0 0, calc(100% - 5px) 0, 100% 50%, calc(100% - 5px) 100%, 0 100%)' }
                          : null),
                      }}
                    />
                  </div>
                  <span className="w-6 shrink-0 text-[10px] text-(--color-faint) tabular-nums">
                    {b.n > 1 ? `×${b.n}` : ''}
                  </span>
                </li>
              )
            })}
          </ul>
        </>
      )}

      {(any > 0 || unparsed.length > 0) && (
        <div className="mt-2 pt-2 border-t border-(--color-border) space-y-0.5">
          {any > 0 && (
            <p className="text-[10px] text-(--color-muted)">
              연차를 안 따지는 공고(경력무관·신입 포함){' '}
              <span className="tabular-nums">{any}건</span>
            </p>
          )}
          {/* 파서가 공고 제목을 통째로 집어 온 경우가 있어 줄이 길다. 한 줄로 자르되
              지우지는 않는다 — 여기 남아 있어야 파서가 뭘 못 읽는지가 보인다. */}
          {unparsed.map(([raw, n]) => (
            <p key={raw} className="text-[10px] text-(--color-faint) truncate" title={raw}>
              {raw} {n > 1 && <span className="tabular-nums">×{n}</span>}
            </p>
          ))}
        </div>
      )}

      <p className="text-[10px] text-(--color-faint) mt-1.5 tabular-nums">모집중 {total}건</p>
    </div>
  )
}

// ── 헤더 ────────────────────────────────────────────────────────────────
function GuideHeader({ guide, posting }: { guide: CompanyGuide; posting: GuidePosting }) {
  const study = posting.study || []
  const hours = study.reduce((s, x) => s + (x.hours || 0), 0)
  const core = study.filter((s) => s.priority === 'core').length

  return (
    <div className="rounded-lg border border-(--color-accent)/30 bg-(--color-accent)/8 p-4">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-xs font-medium tracking-wider text-(--color-accent)">
          이 회사 가려면
        </span>
        {guide.status === 'in_progress' && (
          <span className="text-[10px] px-1.5 py-0.5 rounded border border-(--color-border) text-(--color-faint)">
            작성 중
          </span>
        )}
      </div>
      <p className="text-sm text-(--color-text) leading-relaxed"><Md>{posting.verdict}</Md></p>
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2.5 text-xs text-(--color-muted) tabular-nums">
        <span>
          학습 <span className="text-(--color-text) font-medium">{study.length}</span>개
        </span>
        {core > 0 && (
          <span>
            필수 <span className="text-(--color-text) font-medium">{core}</span>개
          </span>
        )}
        {hours > 0 && (
          <span>
            대략 <span className="text-(--color-text) font-medium">{hours}</span>시간
          </span>
        )}
      </div>
      {posting.fit && (posting.fit.must_have?.length || posting.fit.can_learn?.length) ? (
        <div className="mt-3 pt-3 border-t border-(--color-accent)/20 grid gap-2">
          {posting.fit.must_have && posting.fit.must_have.length > 0 && (
            <FitRow label="없으면 걸린다" items={posting.fit.must_have} tone="core" />
          )}
          {posting.fit.can_learn && posting.fit.can_learn.length > 0 && (
            <FitRow label="지금 없어도 된다" items={posting.fit.can_learn} tone="nice" />
          )}
        </div>
      ) : null}
    </div>
  )
}

function FitRow({ label, items, tone }: { label: string; items: string[]; tone: 'core' | 'nice' }) {
  return (
    <div className="flex gap-2 items-baseline">
      <span
        className="text-[10px] shrink-0 px-1.5 py-0.5 rounded border"
        style={{ borderColor: PRIORITY_COLOR[tone], color: PRIORITY_COLOR[tone] }}
      >
        {label}
      </span>
      <span className="text-xs text-(--color-muted) leading-relaxed">
        {items.map((it, i) => (
          <Fragment key={i}>
            {i > 0 && ' · '}
            <Md>{it}</Md>
          </Fragment>
        ))}
      </span>
    </div>
  )
}

// ── 학습 로드맵 ──────────────────────────────────────────────────────────
function StudySection({
  posting,
  activeQuote,
  onQuote,
}: {
  posting: GuidePosting
  activeQuote: string | null
  onQuote: (q: string | null) => void
}) {
  const items = sortStudy(posting.study || [])
  const [open, setOpen] = useState(0)

  // 왼쪽 본문의 문장을 눌러서 들어온 경우 — 그 항목이 펼쳐져야 한다. 펼침 상태를 여기서만
  // 들고 있으면 본문 → 패널 방향이 끊겨서, 문장을 눌렀는데 패널은 딴 항목을 펼친 채로 남는다.
  const activeIdx = items.findIndex((i) => i.quote === activeQuote)
  const openIdx = activeIdx >= 0 ? activeIdx : open
  const openRef = useRef<HTMLLIElement>(null)
  useEffect(() => {
    if (activeIdx >= 0) openRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [activeIdx])

  if (items.length === 0) return null

  // 한 번에 하나만 펼친다. 아홉 개를 다 펼쳐 두면 패널이 본문보다 길어져서 "지금 뭘
  // 보고 있는지"가 사라지고, 왼쪽 하이라이트도 어느 항목의 것인지 알 수 없게 된다.
  const toggle = (i: number, it: StudyItem) => {
    if (openIdx === i) {
      setOpen(-1)
      onQuote(null)
    } else {
      setOpen(i)
      onQuote(it.quote)
    }
  }

  return (
    <Block title="학습 로드맵" icon="★" hint="펼치면 왼쪽 본문의 해당 문장이 켜집니다">
      <ol className="space-y-1.5">
        {items.map((it, i) => {
          const isOpen = openIdx === i
          const isActive = activeQuote === it.quote
          return (
            <li key={`${it.topic}-${i}`} ref={isActive ? openRef : undefined}>
              <div
                className={
                  'rounded-md border transition ' +
                  (isActive
                    ? 'border-(--color-accent) bg-(--color-accent)/8'
                    : 'border-(--color-border) hover:border-(--color-accent)/40')
                }
              >
                <button
                  onClick={() => toggle(i, it)}
                  className="w-full text-left px-3 py-2.5 flex items-start gap-2.5"
                >
                  <span className="text-xs text-(--color-faint) tabular-nums mt-0.5 w-4 shrink-0">
                    {i + 1}
                  </span>
                  <span className="flex-1 min-w-0">
                    <span className="block text-[13px] text-(--color-text) leading-snug">
                      <Md>{it.topic}</Md>
                    </span>
                    <span className="flex flex-wrap items-center gap-1.5 mt-1">
                      <span
                        className="text-[10px] px-1.5 py-0.5 rounded border"
                        style={{
                          borderColor: PRIORITY_COLOR[it.priority],
                          color: PRIORITY_COLOR[it.priority],
                        }}
                      >
                        {PRIORITY_LABEL[it.priority]}
                      </span>
                      <span className="text-[10px] text-(--color-faint)">
                        {FROM_LABEL[it.from]}
                      </span>
                      {it.hours ? (
                        <span className="text-[10px] text-(--color-faint) tabular-nums">
                          · {it.hours}h
                        </span>
                      ) : null}
                    </span>
                  </span>
                  <span className="text-(--color-faint) text-xs mt-0.5 shrink-0">
                    {isOpen ? '−' : '+'}
                  </span>
                </button>

                {isOpen && (
                  <div className="px-3 pb-3 pt-0 space-y-2.5 border-t border-(--color-border) mt-0.5">
                    <Quote text={it.quote} from={FROM_LABEL[it.from]} />
                    <Field label="왜 필요한가"><Md>{it.why}</Md></Field>
                    <Field label="스스로 확인"><Md>{it.gap_check}</Md></Field>
                    <Field label="만들어 볼 것" strong>
                      <Md>{it.drill}</Md>
                    </Field>
                    {it.resources && it.resources.length > 0 && (
                      <div>
                        <FieldLabel>자료</FieldLabel>
                        <ul className="space-y-1">
                          {it.resources.map((r, k) => (
                            <li key={k}>
                              <a
                                href={r.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-(--color-sky-400) hover:underline break-words"
                              >
                                <Md>{r.title}</Md> ↗
                              </a>
                              {r.note && (
                                <span className="text-[11px] text-(--color-faint)"> — <Md>{r.note}</Md></span>
                              )}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </li>
          )
        })}
      </ol>
    </Block>
  )
}

function Quote({ text, from }: { text: string; from: string }) {
  return (
    <blockquote className="border-l-2 border-(--color-accent)/50 pl-2.5 py-0.5">
      <span className="text-[10px] text-(--color-faint) block mb-0.5">{from} 원문</span>
      <span className="text-xs text-(--color-muted) leading-relaxed">{text}</span>
    </blockquote>
  )
}

// ── 한 걸음 더 ───────────────────────────────────────────────────────────
function EdgeSection({ posting }: { posting: GuidePosting }) {
  const edge = posting.edge || []
  if (edge.length === 0) return null
  return (
    <Block title="한 걸음 더" icon="↗" hint="위를 다 한 사람이 그다음에 하는 것">
      <ul className="space-y-2">
        {edge.map((e, i) => (
          <li key={i} className="border border-(--color-border) rounded-md px-3 py-2.5">
            <p className="text-[13px] text-(--color-text) leading-snug"><Md>{e.idea}</Md></p>
            <p className="text-xs text-(--color-muted) leading-relaxed mt-1"><Md>{e.why}</Md></p>
            {e.effort && <p className="text-[11px] text-(--color-faint) mt-1">{e.effort}</p>}
          </li>
        ))}
      </ul>
    </Block>
  )
}

// ── 전형 ────────────────────────────────────────────────────────────────
function InterviewSection({ posting }: { posting: GuidePosting }) {
  const iv = posting.interview
  if (!iv || (!iv.process && !(iv.expect || []).length)) return null
  return (
    <Block title="전형" icon="◎">
      {iv.process && <p className="text-[13px] text-(--color-text) mb-2"><Md>{iv.process}</Md></p>}
      {iv.expect && iv.expect.length > 0 && (
        <>
          <FieldLabel>예상되는 것</FieldLabel>
          <ul className="space-y-1">
            {iv.expect.map((q, i) => (
              <li key={i} className="text-xs text-(--color-muted) leading-relaxed">
                · <Md>{q}</Md>
              </li>
            ))}
          </ul>
        </>
      )}
      <Sources sources={iv.sources} />
    </Block>
  )
}

// ── 연봉 ────────────────────────────────────────────────────────────────
const BASIS_LABEL: Record<string, string> = {
  posting: '공고 명시',
  public_data: '공개 데이터',
  market: '시장 밴드',
}

function SalarySection({ guide }: { guide: CompanyGuide }) {
  const sal = guide.salary
  const bands = sal?.bands || []
  if (!sal || bands.length === 0) return null
  const unit = sal.unit || '만원'
  return (
    <Block title="연봉" icon="₩" hint={sal.as_of ? `${sal.as_of} 기준` : undefined}>
      <ul className="space-y-2">
        {bands.map((b, i) => (
          <li key={i} className="border border-(--color-border) rounded-md px-3 py-2.5">
            <div className="flex items-baseline gap-2 flex-wrap">
              <span className="text-[13px] text-(--color-text)"><Md>{b.role}</Md></span>
              <span className="text-[11px] text-(--color-faint)">{b.level}</span>
              <span className="ml-auto text-sm text-(--color-text) tabular-nums font-medium">
                {b.low.toLocaleString()}–{b.high.toLocaleString()}
                <span className="text-[11px] text-(--color-muted) font-normal"> {unit}</span>
              </span>
            </div>
            <div className="flex items-center gap-1.5 mt-1.5">
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-(--color-bg) border border-(--color-border) text-(--color-muted)">
                {BASIS_LABEL[b.basis] || b.basis}
              </span>
              {b.confidence === 'inferred' && <Badge>추정</Badge>}
              <Sources sources={b.sources} inline />
            </div>
          </li>
        ))}
      </ul>
      {sal.equity && <p className="text-xs text-(--color-muted) mt-2"><Md>{sal.equity}</Md></p>}
      {sal.note && (
        <p className="text-[11px] text-(--color-faint) leading-relaxed mt-2"><Md>{sal.note}</Md></p>
      )}
    </Block>
  )
}

// ── 사람 ────────────────────────────────────────────────────────────────
function PeopleSection({ guide }: { guide: CompanyGuide }) {
  const people = guide.people || []
  if (people.length === 0) return null
  return (
    <Block title="공개된 사람들" icon="◍" hint="공개 발표·글에서 읽히는 관점">
      <ul className="space-y-2.5">
        {people.map((p, i) => (
          <li key={i} className="border border-(--color-border) rounded-md px-3 py-2.5">
            <div className="flex items-baseline gap-2">
              <span className="text-[13px] text-(--color-text)">{p.name}</span>
              <span className="text-[11px] text-(--color-muted)">{p.role}</span>
              {p.confidence === 'inferred' && <Badge>추정</Badge>}
            </div>
            {p.why_public && (
              <p className="text-[11px] text-(--color-faint) mt-0.5"><Md>{p.why_public}</Md></p>
            )}
            {p.leanings && p.leanings.length > 0 && (
              <ul className="mt-2 space-y-1">
                {p.leanings.map((t, k) => (
                  <li key={k} className="text-xs text-(--color-muted) leading-relaxed">
                    · <Md>{t}</Md>
                  </li>
                ))}
              </ul>
            )}
            {p.what_it_means && (
              <p className="text-xs text-(--color-text) leading-relaxed mt-2 pt-2 border-t border-(--color-border)">
                <Md>{p.what_it_means}</Md>
              </p>
            )}
            {p.public_work && p.public_work.length > 0 && (
              <ul className="mt-2 space-y-1">
                {p.public_work.map((w, k) => (
                  <li key={k}>
                    <a
                      href={w.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11px] text-(--color-sky-400) hover:underline break-words"
                    >
                      {w.title} ↗
                    </a>
                    {w.date && <span className="text-[10px] text-(--color-faint)"> {w.date}</span>}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </Block>
  )
}

// ── 회사·도메인 ─────────────────────────────────────────────────────────
function CompanySection({ guide }: { guide: CompanyGuide }) {
  const co = guide.company
  if (!co) return null
  const empty =
    !co.business && !(co.revenue || []).length && !(co.domains || []).length && !(co.signals || []).length
  if (empty) return null
  return (
    <Block title="회사와 도메인" icon="◆">
      {co.business && (
        <>
          <p className="text-[13px] text-(--color-text) leading-relaxed"><Md>{co.business}</Md></p>
          <div className="flex items-center gap-1.5 mt-1.5">
            {co.business_confidence === 'inferred' && <Badge>추정</Badge>}
            <Sources sources={co.business_sources} inline />
          </div>
        </>
      )}

      {co.scale && co.scale.length > 0 && (
        <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-3 pt-3 border-t border-(--color-border)">
          {co.scale.map((s, i) => (
            <span key={i} className="text-xs">
              <span className="text-(--color-faint)">{s.label} </span>
              <span className="text-(--color-text) tabular-nums"><Md>{s.value}</Md></span>
            </span>
          ))}
        </div>
      )}

      {co.revenue && co.revenue.length > 0 && (
        <div className="mt-3 pt-3 border-t border-(--color-border) space-y-2.5">
          <FieldLabel>돈이 나오는 곳 → 그걸 떠받치는 도메인</FieldLabel>
          {co.revenue.map((rv, i) => (
            <div key={i} className="border border-(--color-border) rounded-md px-3 py-2.5">
              <div className="flex items-baseline gap-2 flex-wrap">
                <span className="text-[13px] text-(--color-text)">{rv.name}</span>
                {rv.weight && (
                  <span className="text-[11px] text-(--color-accent) tabular-nums">{rv.weight}</span>
                )}
                {rv.confidence === 'inferred' && <Badge>추정</Badge>}
              </div>
              <p className="text-xs text-(--color-muted) leading-relaxed mt-1"><Md>{rv.how}</Md></p>
              {rv.domains && rv.domains.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 mt-2">
                  <span className="text-[10px] text-(--color-faint) shrink-0">↳</span>
                  {rv.domains.map((d) => (
                    <span
                      key={d}
                      className="text-[10px] px-1.5 py-0.5 rounded bg-(--color-accent)/12 text-(--color-accent) border border-(--color-accent)/30"
                    >
                      {d}
                    </span>
                  ))}
                </div>
              )}
              <Sources sources={rv.sources} />
            </div>
          ))}
        </div>
      )}

      {co.domains && co.domains.length > 0 && (
        <div className="mt-3 pt-3 border-t border-(--color-border) space-y-2.5">
          <FieldLabel>이 회사가 푸는 문제</FieldLabel>
          {co.domains.map((d, i) => (
            <div key={i}>
              <p className="text-[13px] text-(--color-text)">
                {d.name}
                {d.confidence === 'inferred' && <Badge className="ml-1.5">추정</Badge>}
              </p>
              <p className="text-xs text-(--color-muted) leading-relaxed mt-0.5"><Md>{d.why}</Md></p>
              {d.what_to_know && d.what_to_know.length > 0 && (
                <ul className="mt-1 space-y-0.5">
                  {d.what_to_know.map((k, m) => (
                    <li key={m} className="text-xs text-(--color-muted) leading-relaxed">
                      · <Md>{k}</Md>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}

      {co.signals && co.signals.length > 0 && (
        <div className="mt-3 pt-3 border-t border-(--color-border) space-y-2.5">
          <FieldLabel>공고에서 읽히는 것 (전부 추정)</FieldLabel>
          {co.signals.map((s, i) => (
            <div key={i}>
              <p className="text-[13px] text-(--color-text) leading-snug"><Md>{s.reading}</Md></p>
              <p className="text-[11px] text-(--color-faint) leading-relaxed mt-0.5 italic">
                근거: <Md>{s.evidence}</Md>
              </p>
              {s.so_what && (
                <p className="text-xs text-(--color-muted) leading-relaxed mt-1">→ <Md>{s.so_what}</Md></p>
              )}
            </div>
          ))}
        </div>
      )}
    </Block>
  )
}

// ── 조각 ────────────────────────────────────────────────────────────────
function Block({
  title,
  icon,
  hint,
  children,
}: {
  title: string
  icon?: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <section className="rounded-lg border border-(--color-border) bg-(--color-panel) p-3.5">
      <h3 className="flex items-baseline gap-1.5 mb-2.5">
        {icon && <span className="text-(--color-accent) text-xs">{icon}</span>}
        <span className="text-xs font-medium tracking-wider text-(--color-text)">{title}</span>
        {hint && <span className="text-[10px] text-(--color-faint) ml-auto">{hint}</span>}
      </h3>
      {children}
    </section>
  )
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="block text-[10px] tracking-wider text-(--color-faint) mb-0.5">{children}</span>
  )
}

function Field({
  label,
  children,
  strong = false,
}: {
  label: string
  children: React.ReactNode
  strong?: boolean
}) {
  return (
    <div>
      <FieldLabel>{label}</FieldLabel>
      <p
        className={
          'text-xs leading-relaxed ' + (strong ? 'text-(--color-text)' : 'text-(--color-muted)')
        }
      >
        {children}
      </p>
    </div>
  )
}

function Badge({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={
        'inline-block text-[10px] px-1.5 py-0.5 rounded border border-(--color-amber-400)/40 text-(--color-amber-400) ' +
        className
      }
    >
      {children}
    </span>
  )
}

function Sources({ sources, inline = false }: { sources?: Source[]; inline?: boolean }) {
  if (!sources || sources.length === 0) return null
  return (
    <span className={inline ? 'inline-flex flex-wrap gap-1.5' : 'flex flex-wrap gap-1.5 mt-2'}>
      {sources.map((s, i) => (
        <a
          key={i}
          href={s.url}
          target="_blank"
          rel="noopener noreferrer"
          title={s.title}
          className="text-[10px] px-1.5 py-0.5 rounded border border-(--color-border) text-(--color-faint) hover:text-(--color-sky-400) hover:border-(--color-sky-400)"
        >
          {s.publisher || s.title.slice(0, 18)} ↗
        </a>
      ))}
    </span>
  )
}
