import { useMemo, useState } from 'react'
import { useReposts, type RepostChange } from '../lib/useReposts'
import { Loader, ErrorState } from './ui'

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
  if (!data || rows.length === 0)
    return <div className="p-8 text-(--color-muted)">재공고로 판정된 공고가 없습니다.</div>

  const cur = rows[Math.min(picked, rows.length - 1)]
  const moves = data.summary.career_moves || {}

  return (
    <div className="flex flex-col flex-1 min-h-0 min-w-0">
      <div className="px-4 py-2 border-b border-(--color-border) bg-(--color-panel)/60 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className="text-sm text-(--color-text)">
          재공고 <b>{data.summary.count}</b>건
        </span>
        <span className="text-xs text-(--color-muted)">
          추적 자리 {data.tracked_positions.toLocaleString()} · 누적 {data.history_versions.toLocaleString()}판
        </span>
        <span className="text-xs text-(--color-muted)">
          경력 요구 <b className="text-(--color-accent)">낮춤 {moves['낮춤'] ?? 0}</b> ·
          높임 {moves['높임'] ?? 0} · 동일 {moves['동일'] ?? 0}
        </span>
        <span className="text-xs text-(--color-muted) ml-auto">
          자주 바뀌는 항목{' '}
          {data.summary.changed_fields
            .filter(([f]) => !TRIVIAL.has(f))
            .slice(0, 4)
            .map(([f, n]) => `${FIELD_KO[f] ?? f} ${n}`)
            .join(' · ')}
        </span>
      </div>

      <div className="flex flex-col md:flex-row flex-1 min-h-0 overflow-y-auto md:overflow-hidden">
        <aside className="w-full md:w-80 shrink-0 md:overflow-auto border-b md:border-b-0 md:border-r border-(--color-border) bg-(--color-panel) p-2">
          <ul className="flex flex-col gap-0.5">
            {rows.map(({ r, meaningful }, i) => (
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
        </main>
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
