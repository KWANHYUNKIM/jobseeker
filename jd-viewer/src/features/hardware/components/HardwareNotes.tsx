import { useEffect, useState } from 'react'
import { docFetch } from '../../../api/client'

// 실무자 이야기 — 고성능 그래픽카드를 AI·ML 에 쓰는 사람들의 실측·경험을 요약한 참고 카드.
//
// 원본은 public/hardware/notes.json. Reddit 은 robots.txt 가 전부 막아 쓰지 않는다 — 읽고 링크할 수 있는
// 곳(GitHub 토론·Puget Systems·Phoronix·Tom's Hardware·Hugging Face·제조사 문서)만 쓰고, 원문은 옮기지 않고
// 우리 말로 요약한다. 근거 종류(실측·경험담·공식)를 늘 같이 보인다. 참고용이다 — 조건에 따라 다르다.

interface Src {
  title: string
  url: string
}
export interface Note {
  topic: string
  gpus: string[]
  use: string
  summary: string
  evidence: 'measurement' | 'experience' | 'official'
  numbers?: string
  as_of: string
  confidence: 'high' | 'medium' | 'low'
  sources: Src[]
}

const EVIDENCE: Record<Note['evidence'], { label: string; cls: string }> = {
  measurement: { label: '실측', cls: 'bg-(--color-accent)/12 text-(--color-accent)' },
  official: { label: '공식', cls: 'bg-(--color-sky-400)/12 text-(--color-sky-400)' },
  experience: { label: '경험담', cls: 'bg-(--color-amber-400)/12 text-(--color-amber-400)' },
}
const USE: Record<string, string> = {
  'llm-inference': '언어 모델 추론',
  'fine-tuning': '미세조정',
  'image-gen': '이미지 생성',
  'multi-gpu': '여러 장',
  build: '조립',
  alternatives: '다른 선택지',
}
const CONF: Record<Note['confidence'], string> = { high: '높음', medium: '보통', low: '낮음' }

let cache: Promise<Note[]> | null = null
function useNotes(): Note[] | null {
  const [xs, setXs] = useState<Note[] | null>(null)
  useEffect(() => {
    cache ??= docFetch('/hardware/notes.json')
      .then((r) => (r.ok ? r.json() : { notes: [] }))
      .then((d: { notes?: Note[] }) => d.notes ?? [])
      .catch(() => [])
    let alive = true
    cache.then((x) => alive && setXs(x))
    return () => {
      alive = false
    }
  }, [])
  return xs
}

/** 실무자 이야기 카드들 — gpus 를 주면 그 카드가 나오는 것만, limit 로 개수를 줄인다 */
export function FieldNotes({ gpus, limit, title = '실무자 이야기' }: { gpus?: string[]; limit?: number; title?: string }) {
  const all = useNotes()
  const [use, setUse] = useState('')
  const [more, setMore] = useState(false)
  if (!all?.length) return null
  const mine = gpus?.length ? all.filter((n) => n.gpus.some((g) => gpus.includes(g))) : all
  if (!mine.length) return null
  const uses = [...new Set(mine.map((n) => n.use))]
  // 그 카드에 딱 맞는 이야기(관련 카드가 적은 것) → 신뢰도 높은 것 → 최근 것
  const fit = (n: Note) => (n.gpus.length ? n.gpus.length : 99)
  const trust = { high: 0, medium: 1, low: 2 } as const
  const xs = mine
    .filter((n) => !use || n.use === use)
    .sort((a, b) => fit(a) - fit(b) || trust[a.confidence] - trust[b.confidence] || b.as_of.localeCompare(a.as_of))
  const cut = limit && !more ? xs.slice(0, limit) : xs
  return (
    <section className="flex flex-col gap-2">
      <div className="flex flex-wrap items-baseline gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        <span className="text-[11px] text-(--color-muted)">
          AI·ML 에 쓰는 사람들의 실측·경험 요약 — <b>참고용</b>이다. 조건(모델·양자화·드라이버)에 따라 다르고 원문은 링크로 본다.
        </span>
      </div>
      {uses.length > 1 && (
        <div className="flex flex-wrap gap-1 text-xs">
          {['', ...uses].map((u) => (
            <button
              key={u || 'all'}
              onClick={() => setUse(u)}
              className={`px-2 py-0.5 rounded ${use === u ? 'bg-(--color-text) text-(--color-panel) font-semibold' : 'bg-(--color-band) hover:bg-(--color-border-soft)'}`}
            >
              {u ? (USE[u] ?? u) : '전체'}
            </button>
          ))}
        </div>
      )}
      <div className="grid gap-2 md:grid-cols-2">
        {cut.map((n) => (
          <article key={n.topic + n.as_of} className="rounded-md border border-(--color-border-soft) p-3 text-xs flex flex-col gap-1.5">
            <div className="flex flex-wrap items-baseline gap-1.5">
              <span className={`text-[10px] px-1.5 rounded font-semibold ${EVIDENCE[n.evidence].cls}`}>{EVIDENCE[n.evidence].label}</span>
              <b className="text-sm">{n.topic}</b>
              <span className="text-[10px] text-(--color-faint)">
                {USE[n.use] ?? n.use} · {n.as_of} · 신뢰도 {CONF[n.confidence]}
              </span>
            </div>
            <p>{n.summary}</p>
            {n.numbers && <p className="text-(--color-muted) tabular-nums">{n.numbers}</p>}
            <div className="text-[10px] flex flex-wrap gap-x-2">
              {n.sources.map((s) => (
                <a key={s.url} href={s.url} target="_blank" rel="noreferrer" className="text-(--color-sky-400) hover:underline">
                  {s.title}
                </a>
              ))}
            </div>
          </article>
        ))}
      </div>
      {limit && xs.length > limit && (
        <button onClick={() => setMore(!more)} className="self-start text-xs text-(--color-accent) hover:underline">
          {more ? '접기' : `${xs.length - limit}개 더 보기`}
        </button>
      )}
    </section>
  )
}
