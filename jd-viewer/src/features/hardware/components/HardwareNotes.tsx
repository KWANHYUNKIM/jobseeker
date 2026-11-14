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
  measurement: { label: '실측', cls: 'bg-[#fff0f0] text-[#e03131]' },
  official: { label: '공식', cls: 'bg-[#eef8f1] text-[#1e8a3c]' },
  experience: { label: '경험담', cls: 'bg-[#fff4e6] text-[#d9480f]' },
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
    <section className="flex flex-col">
      <h3 className="text-[20px] font-bold leading-[29px] tracking-[-0.2px] text-[#555]">{title}</h3>
      <p className="mt-[3px] text-[13px] leading-[19px] text-[#555]">실측·경험 요약 — 참고용. 조건(모델·양자화·드라이버)에 따라 다르고 원문은 링크로 본다.</p>
      {uses.length > 1 && (
        <div className="mt-4 flex flex-wrap gap-[6px]">
          {['', ...uses].map((u) => (
            <button
              key={u || 'all'}
              type="button"
              aria-pressed={use === u}
              onClick={() => setUse(u)}
              className={'h-8 px-[14px] rounded-2xl text-sm ' + (use === u ? 'bg-[#272727] text-white' : 'border border-[#d8d8d8] bg-white text-[#272727] hover:border-[#272727]')}
            >
              {u ? (USE[u] ?? u) : '전체'}
            </button>
          ))}
        </div>
      )}
      <div className="mt-[14px] grid gap-[15px] md:grid-cols-2">
        {cut.map((n) => (
          <article key={n.topic + n.as_of} className="rounded-[22px] border border-[#e2e8ec] bg-white px-6 pt-5 pb-[22px] flex flex-col">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`rounded px-[7px] text-[13px] leading-[22px] ${EVIDENCE[n.evidence].cls}`}>{EVIDENCE[n.evidence].label}</span>
              <span className="text-[13px] text-[#555]">
                {USE[n.use] ?? n.use} · {n.as_of} · 신뢰도 {CONF[n.confidence]}
              </span>
            </div>
            <h4 className="mt-[10px] text-[18px] font-bold leading-[27px] text-[#272727]">{n.topic}</h4>
            <p className="mt-[6px] text-[15px] leading-[25px] text-[#333]">{n.summary}</p>
            {n.numbers && (
              <p className="mt-[10px] self-start rounded-md bg-[#f1f4f8] px-[9px] py-[2px] text-[13px] leading-5 text-[#272727] tabular-nums">{n.numbers}</p>
            )}
            <div className="mt-[10px] flex flex-wrap gap-x-3 text-sm font-medium">
              {n.sources.map((s) => (
                <a key={s.url} href={s.url} target="_blank" rel="noreferrer" className="text-(--color-accent) hover:underline">
                  {s.title} ↗
                </a>
              ))}
            </div>
          </article>
        ))}
      </div>
      {limit && xs.length > limit && (
        <button
          type="button"
          onClick={() => setMore(!more)}
          className="mt-[13px] h-[46px] rounded-xl border border-[#e2e8ec] bg-white text-sm font-bold text-[#272727] hover:border-[#999]"
        >
          {more ? '접기' : `${xs.length - limit}개 더 보기`}
        </button>
      )}
    </section>
  )
}
