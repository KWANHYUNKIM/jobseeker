// 역설계 탭의 작은 공용 조각들.
// 회사 상세(CompanyTeardown)와 화면 도해(UiSketch)가 함께 쓴다 — 한쪽에 두고
// 다른 쪽에서 import 하면 순환 참조가 되므로 밖으로 뺐다.
import type { Confidence, Source } from '../lib/useReveng'

const CONF_LABEL: Record<Confidence, string> = {
  confirmed: '확인',
  inferred: '추정',
  unknown: '미확인',
}

export function ConfBadge({ c }: { c?: Confidence }) {
  if (!c || c === 'confirmed') return null // '확인'은 기본값 — 뱃지로 화면을 채우지 않는다
  return (
    <span
      className={
        'ml-1.5 align-middle px-1 py-px rounded text-[10px] border ' +
        (c === 'inferred'
          ? 'border-amber-500/40 text-amber-500'
          : 'border-(--color-border) text-(--color-muted)')
      }
      title={c === 'inferred' ? '공개 자료에서 추론한 내용' : '공개 자료로 확인하지 못함'}
    >
      {CONF_LABEL[c]}
    </span>
  )
}

export function SourceLinks({ sources }: { sources?: Source[] }) {
  if (!sources || sources.length === 0) return null
  return (
    <div className="flex flex-wrap gap-x-2 gap-y-0.5 mt-1">
      {sources.map((s) => (
        <a
          key={s.url}
          href={s.url}
          target="_blank"
          rel="noreferrer noopener"
          className="text-[11px] text-(--color-accent) hover:underline"
          title={s.title}
        >
          {s.publisher || new URL(s.url).hostname}
        </a>
      ))}
    </div>
  )
}
