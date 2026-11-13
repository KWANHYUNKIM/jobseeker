import { useMemo, useState } from 'react'
import { useReposts, type RepostChange } from '../hooks/useReposts'
import type { ReactNode } from 'react'
import { Loader, ErrorState, SearchInput, hits } from '../../../components/ui'
import { SiteFooter } from '../../../components/SiteFooter'
import { onLinkClick } from '../../../utils/navigation'
import { paths } from '../../../utils/urls'

// 재공고 — 마감됐다 다시 올라온 자리와 그 사이의 변경 로그.
//
// 채용 사이트는 재공고에 새 URL 을 발급하므로 겉으로는 완전히 새 공고로 보이고, 무엇이
// 달라졌는지는 아무도 말해주지 않는다. 그런데 바로 그게 시장 신호다 — 경력 요구를
// 낮췄다면 사람을 못 구했다는 뜻이고, 스택이 빠졌다면 범위를 줄였다는 뜻이다.

const FIELD_KO: Record<string, string> = {
  career: '경력 요구',
  location: '근무지',
  deadline: '마감 표기',
  dday: 'D-day',
  title: '공고 제목',
  url: '공고 주소',
  site: '게시 사이트',
  tech_stack: '기술 스택',
  qualifications: '자격요건',
  preferences: '우대사항',
  main_tasks: '주요업무',
  benefits: '복지',
}

// 마감·주소 변경은 재공고라면 당연히 바뀌는 값이라, 목록에서는 '무엇이 달라졌나' 로
// 세지 않는다. 이걸 같이 세면 모든 재공고가 똑같이 2건 변경으로 보인다.
const TRIVIAL = new Set(['url', 'deadline', 'dday', 'site'])

export function RepostView() {
  const { data, loading, error } = useReposts()
  const [picked, setPicked] = useState<number>(0)
  const [query, setQuery] = useState('')

  const rows = useMemo(() => {
    if (!data) return []
    return data.reposts.map((r) => ({
      r,
      // 비교 불가(한쪽 본문 미수집)는 변경으로 세지 않는다. 세면 크롤이 본문을 놓친
      // 공고일수록 "많이 바뀐 공고"로 올라와 목록 상단이 전부 수집 실패로 찬다.
      meaningful: r.changes.filter(
        (c) => !TRIVIAL.has(c.field) && !(c.kind === 'text' && c.missing),
      ),
      unknown: r.changes.filter((c) => c.kind === 'text' && c.missing),
    }))
  }, [data])

  // 검색어는 회사·제목·사이트에 더해 **무엇이 바뀌었는가**에도 건다 — '경력 요구'
  // 로 쳐서 경력을 손본 자리만 보는 것이 이 탭에서 가장 자주 하는 일이다.
  const shown = useMemo(
    () =>
      rows.filter(({ r, meaningful }) =>
        hits(
          query,
          r.company,
          r.title,
          r.site,
          ...meaningful.map((c) => FIELD_KO[c.field] ?? c.field),
        ),
      ),
    [rows, query],
  )

  if (loading) return <Loader label="재공고 불러오는 중…" />
  if (error)
    return (
      <ErrorState
        title="reposts.json 로드 실패"
        detail={error}
        hint={
          <>
            생성:{' '}
            <code className="text-(--color-text)">
              catch_capture/.venv/bin/python bin/build_reposts.py
            </code>
          </>
        }
      />
    )
  if (!data) return null
  if (rows.length === 0)
    return (
      <Shell data={data}>
        <EmptyCard tracked={data.tracked_positions} />
      </Shell>
    )

  // 검색으로 목록이 줄면 고른 번호가 목록 밖을 가리킬 수 있다 — 첫 줄로 되돌린다.
  const cur = shown.length > 0 ? shown[Math.min(picked, shown.length - 1)] : null
  return (
    <Shell data={data}>
      <div className="rounded-[30px] border border-[#e2e8ec] overflow-hidden">
      <div className="px-[29px] py-4 border-b border-[#e2e8ec] text-[13px] text-[#777]">
        자주 바뀌는 항목{' '}
        {data.summary.changed_fields
          .filter(([f]) => !TRIVIAL.has(f))
          .slice(0, 4)
          .map(([f, n]) => `${FIELD_KO[f] ?? f} ${n}`)
          .join(' · ') || '없음'}
      </div>
      <div className="flex flex-col md:flex-row md:h-[640px]">
        <aside className="w-full md:w-80 shrink-0 md:overflow-auto border-b md:border-b-0 md:border-r border-(--color-border) bg-(--color-panel) p-2">
          <div className="px-1 pb-2 flex flex-col gap-1">
            <SearchInput
              value={query}
              onChange={(v) => {
                setQuery(v)
                setPicked(0)
              }}
              placeholder="회사·공고·바뀐 항목 검색"
            />
            {query && (
              <div className="text-[11px] text-(--color-muted) px-0.5">
                {rows.length}건 중 <b className="text-(--color-text)">{shown.length}건</b>
              </div>
            )}
          </div>
          <ul className="flex flex-col gap-0.5">
            {shown.map(({ r, meaningful }, i) => (
              <li key={`${r.company}-${r.title}-${i}`}>
                <button
                  onClick={() => setPicked(i)}
                  className={`w-full text-left px-2 py-1.5 rounded ${i === picked ? 'bg-(--color-accent)/15' : 'hover:bg-(--color-bg)'}`}
                >
                  <div className="flex items-baseline gap-2">
                    <span className="text-xs text-(--color-accent) truncate">{r.company || r.site}</span>
                    <span className="ml-auto text-[10px] text-(--color-muted) shrink-0">
                      {r.rounds}판
                    </span>
                  </div>
                  <div className="text-xs text-(--color-text) line-clamp-2">{r.title}</div>
                  <div className="mt-0.5 text-[10px] text-(--color-muted)">
                    변경 {meaningful.length}곳
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <main className="flex-1 min-w-0 md:overflow-auto p-4 sm:p-5">
          {!cur ? (
            <p className="text-sm text-(--color-muted)">
              <b className="text-(--color-text)">{query}</b> 로 걸리는 재공고가 없습니다.
            </p>
          ) : (
          <>
          <div className="flex items-baseline gap-2 flex-wrap">
            <h2 className="text-lg font-semibold text-(--color-text)">{cur.r.title}</h2>
            <span className="text-xs text-(--color-accent)">{cur.r.company || cur.r.site}</span>
            <a
              href={cur.r.url}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-(--color-muted) hover:text-(--color-text) underline"
            >
              현재 공고 ↗
            </a>
          </div>

          {/* 마감 → 재공고 타임라인 */}
          <div className="mt-3 flex items-center gap-2 flex-wrap text-xs">
            <span className="px-2 py-1 rounded border border-(--color-border) bg-(--color-bg) text-(--color-muted)">
              마감 {cur.r.prev_deadline || '표기 없음'}
            </span>
            <span className="text-(--color-muted)">→</span>
            <span className="px-2 py-1 rounded border border-(--color-accent)/40 bg-(--color-accent)/10 text-(--color-accent)">
              재공고 {cur.r.now_deadline || '표기 없음'}
            </span>
            <span className="text-(--color-muted)">· 기록된 판 {cur.r.rounds}개</span>
          </div>

          <h3 className="mt-5 text-sm font-semibold text-(--color-text)">변경 로그</h3>
          <p className="text-xs text-(--color-muted) mb-2">
            직전 마감 판과 현재 판의 차이. 마감일·주소는 재공고면 당연히 바뀌므로 아래로 내렸다.
          </p>
          {cur.meaningful.length === 0 ? (
            <p className="text-sm text-(--color-muted)">
              마감일과 주소 말고는 달라진 게 없다 — 같은 조건으로 그대로 다시 올린 자리다.
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {cur.meaningful.map((c, i) => (
                <ChangeRow key={`${c.field}-${i}`} c={c} />
              ))}
            </ul>
          )}

          {cur.unknown.length > 0 && (
            <p className="mt-3 text-[11px] text-(--color-muted)">
              ⚠ {cur.unknown.length}개 항목은 한쪽 판의 본문을 크롤에서 받지 못해 비교할 수
              없다. 변경 수에는 넣지 않았다.
            </p>
          )}

          <details className="mt-4">
            <summary className="text-xs text-(--color-muted) cursor-pointer">
              마감일·주소 변경도 보기
            </summary>
            <ul className="mt-2 flex flex-col gap-2">
              {cur.r.changes
                .filter((c) => TRIVIAL.has(c.field))
                .map((c, i) => (
                  <ChangeRow key={`t-${c.field}-${i}`} c={c} />
                ))}
            </ul>
          </details>
          </>
          )}
        </main>
      </div>
      </div>
    </Shell>
  )
}

type RepostData = NonNullable<ReturnType<typeof useReposts>['data']>

/**
 * 재공고 화면 껍데기(캐치형 07) — 제목·설명, 숫자 칸 셋(추적 중·변경 이력·재공고 판정),
 * 본문(목록 또는 빈 상태), '이렇게 판정해요' 세 단계, 경력 조건 변화 줄, 바닥 띠.
 */
function Shell({ data, children }: { data: RepostData; children: ReactNode }) {
  const moves = data.summary.career_moves || {}
  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[43px] pb-[90px]">
        <h1 className="text-[28px] font-bold leading-10 tracking-[-0.6px] text-[#272727]">재공고</h1>
        <p className="mt-1 text-base leading-6 tracking-[-0.16px] text-[#666]">
          한 번 닫혔다가 다시 열린 공고를 찾아 드려요. 다시 열린 회사는 아직 사람을 못 구했다는 신호예요.
        </p>
        <div className="mt-[29px] grid sm:grid-cols-3 gap-4">
          <Stat label="추적 중인 공고" n={data.tracked_positions} />
          <Stat label="저장된 변경 이력" n={data.history_versions} />
          <Stat label="재공고로 판정" n={data.summary.count} accent />
        </div>
        <div className="mt-6">{children}</div>

        <h2 className="mt-[55px] text-[22px] font-bold leading-8 tracking-[-0.22px] text-[#272727]">
          이렇게 <span className="font-black text-(--color-accent)">판정</span>해요
        </h2>
        <ol className="mt-5 grid sm:grid-cols-3 gap-4">
          {[
            ['같은 공고 찾기', '회사·직무·근무지가 같은 공고를 이전 기록과 묶어요.'],
            ['닫힘 → 열림 확인', '마감·삭제됐던 공고가 다시 올라왔는지 확인해요.'],
            ['바뀐 조건 비교', '경력·연봉·기술스택이 낮아졌는지 높아졌는지 함께 보여줘요.'],
          ].map(([t, d], i) => (
            <li key={t} className="min-h-[169px] rounded-[22px] bg-[#f7f9fa] px-7 pt-[30px] pb-6">
              <div className="text-[15px] font-bold text-(--color-accent) tabular-nums">{String(i + 1).padStart(2, '0')}</div>
              <div className="mt-[11px] text-[19px] font-bold leading-[27px] tracking-[-0.16px] text-[#272727]">{t}</div>
              <p className="mt-2 text-[15px] leading-[22px] tracking-[-0.16px] text-[#666]">{d}</p>
            </li>
          ))}
        </ol>
        <div className="mt-4 flex flex-wrap items-center gap-x-[37px] gap-y-2 min-h-[75px] rounded-[30px] border border-[#e2e8ec] px-[29px] py-4">
          <span className="text-[17px] font-bold tracking-[-0.16px] text-[#272727]">경력 조건 변화</span>
          {(['낮춤', '동일', '높임'] as const).map((k) => (
            <span key={k} className="text-base tracking-[-0.16px] text-[#666]">
              {k} <b className="ml-1.5 font-bold text-[#272727] tabular-nums">{moves[k] ?? 0}건</b>
            </span>
          ))}
        </div>
      </div>
      <SiteFooter updated={data.generated_at} />
    </div>
  )
}

function Stat({ label, n, accent }: { label: string; n: number; accent?: boolean }) {
  return (
    <div className={'h-32 rounded-[22px] border px-[29px] pt-[25px] ' + (accent ? 'bg-(--color-accent-weak) border-[#ffd5d5]' : 'border-[#e2e8ec]')}>
      <div className="text-[15px] tracking-[-0.16px] text-[#777]">{label}</div>
      <div className="mt-1">
        <span className={'text-[34px] font-bold leading-[49px] tracking-[-0.6px] tabular-nums ' + (accent ? 'text-(--color-accent)' : 'text-[#272727]')}>
          {n.toLocaleString()}
        </span>
        <span className="ml-0.5 text-base text-[#474747]">건</span>
      </div>
    </div>
  )
}

/** 아직 판정된 재공고가 없을 때 — 무엇을 지켜보고 있는지와 갈 곳을 알려 준다. */
function EmptyCard({ tracked }: { tracked: number }) {
  return (
    <div className="flex flex-col items-center rounded-[30px] border border-[#e2e8ec] px-6 pt-[71px] pb-[61px] text-center">
      <span className="grid place-items-center w-[84px] h-[84px] rounded-full bg-[#f3f6f8] text-[40px] text-[#9aa1a8]" aria-hidden>
        ↻
      </span>
      <h2 className="mt-[22px] text-2xl font-bold leading-9 tracking-[-0.4px] text-[#272727]">아직 재공고로 판정된 공고가 없어요</h2>
      <p className="mt-[9px] max-w-[560px] text-base leading-[25px] tracking-[-0.16px] text-[#666]">
        공고 {tracked.toLocaleString()}건의 변경 이력을 매일 비교하고 있어요. 같은 회사·같은 직무가 다시 올라오면 여기에 바로 보여 드릴게요.
      </p>
      <div className="mt-[29px] flex flex-wrap justify-center gap-2.5">
        <a
          href={paths.jobs()}
          onClick={onLinkClick(paths.jobs())}
          className="inline-flex items-center gap-2 h-11 px-[50px] rounded-[30px] bg-[#272727] text-base font-medium text-white hover:bg-black"
        >
          잡 리스트 보러가기
          <svg width="8" height="10" viewBox="0 0 8 10" fill="none" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" aria-hidden>
            <path d="M2.5 1.5 6 5l-3.5 3.5" />
          </svg>
        </a>
        {/* 알림은 아직 없다 — 자리만 잡아 두고 눌러도 아무 일이 없다는 걸 숨기지 않는다. */}
        <button
          type="button"
          disabled
          title="재공고 알림은 준비 중이에요"
          className="h-11 px-[17px] rounded-[18px] border border-(--color-accent) bg-white text-sm font-medium text-(--color-accent) disabled:cursor-not-allowed"
        >
          알림 받기
        </button>
      </div>
    </div>
  )
}

function ChangeRow({ c }: { c: RepostChange }) {
  const name = FIELD_KO[c.field] ?? c.field
  return (
    <li className="rounded border border-(--color-border) bg-(--color-bg) p-2.5">
      <div className="text-xs font-medium text-(--color-text) mb-1">{name}</div>
      {c.kind === 'value' ? (
        <div className="flex items-center gap-2 flex-wrap text-xs">
          <span className="px-1.5 py-0.5 rounded bg-(--color-panel) text-(--color-muted) line-through break-all">
            {c.from || '(없음)'}
          </span>
          <span className="text-(--color-muted)">→</span>
          <span className="px-1.5 py-0.5 rounded bg-(--color-accent)/15 text-(--color-accent) break-all">
            {c.to || '(없음)'}
          </span>
        </div>
      ) : c.kind === 'list' ? (
        <div className="flex flex-wrap gap-1">
          {c.added.map((t) => (
            <span key={`a-${t}`} className="px-1.5 py-0.5 text-[11px] rounded bg-(--color-accent)/15 text-(--color-accent)">
              + {t}
            </span>
          ))}
          {c.removed.map((t) => (
            <span key={`r-${t}`} className="px-1.5 py-0.5 text-[11px] rounded bg-(--color-panel) text-(--color-muted) line-through">
              − {t}
            </span>
          ))}
        </div>
      ) : c.missing ? (
        <div className="text-xs text-(--color-muted)">
          본문 미수집 — 비교 불가 ({c.from_len}자 → {c.to_len}자). 한쪽 판의 본문을 크롤에서
          받지 못했다는 뜻이지, 내용이 지워진 것이 아니다.
        </div>
      ) : (
        <div className="text-xs text-(--color-muted)">
          <span className="tabular-nums">
            {c.from_len}자 → {c.to_len}자
          </span>
          {c.to_excerpt && (
            <p className="mt-1 text-(--color-text) line-clamp-3">{c.to_excerpt}</p>
          )}
        </div>
      )}
    </li>
  )
}
