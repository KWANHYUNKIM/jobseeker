import { Fragment, useMemo } from 'react'

// 역설계 데이터의 본문 필드(business_model, why, tradeoff, thought, solves …)는
// JSON 문자열이지만 안에 마크다운 강조가 들어 있다. 지금까지 그냥 텍스트로 뿌려서
// `**…**` 가 화면에 그대로 나왔다.
//
// 블록 마크다운(ReactMarkdown)을 쓰지 않는 이유: 이 필드들은 문단 하나짜리 인라인
// 텍스트이고, 한 화면에 수백 개가 깔린다. 문단·리스트·표까지 파싱하는 렌더러를
// 태그마다 붙이면 그만큼이 다 낭비다. 여기서 필요한 문법은 네 개뿐이다.
//
// 그리고 `**…**` 는 굵게가 아니라 '하이라이트'로 그린다 — 이 데이터에서 저자가
// 굵게 쓴 자리는 문장의 결론이거나 다른 회사와 갈리는 지점이다. 굵기만으로는
// 긴 문단에서 눈에 걸리지 않는다.

type Tok =
  | { t: 'text'; v: string }
  | { t: 'mark'; v: string }
  | { t: 'em'; v: string }
  | { t: 'code'; v: string }
  | { t: 'link'; v: string; href: string }

// 순서가 곧 우선순위다. code 를 먼저 잡아야 백틱 안의 별표가 강조로 먹히지 않는다.
const RE = /(`[^`\n]+`)|(\[[^\]\n]+\]\([^)\s]+\))|(\*\*[^*\n]+\*\*)|(\*[^*\n]+\*)/g

function tokenize(src: string): Tok[] {
  const out: Tok[] = []
  let last = 0
  for (const m of src.matchAll(RE)) {
    const i = m.index!
    if (i > last) out.push({ t: 'text', v: src.slice(last, i) })
    const s = m[0]
    if (s.startsWith('`')) out.push({ t: 'code', v: s.slice(1, -1) })
    else if (s.startsWith('[')) {
      const cut = s.indexOf('](')
      out.push({ t: 'link', v: s.slice(1, cut), href: s.slice(cut + 2, -1) })
    } else if (s.startsWith('**')) out.push({ t: 'mark', v: s.slice(2, -2) })
    else out.push({ t: 'em', v: s.slice(1, -1) })
    last = i + s.length
  }
  if (last < src.length) out.push({ t: 'text', v: src.slice(last) })
  return out
}

/** 인라인 마크다운 한 조각. 문단 태그를 만들지 않으므로 어떤 부모 안에도 들어간다. */
export function Md({ children }: { children?: string | null }) {
  const toks = useMemo(() => (children ? tokenize(children) : []), [children])
  if (!children) return null
  return (
    <>
      {toks.map((k, i) => {
        switch (k.t) {
          case 'mark':
            return (
              <mark key={i} className="md-mark">
                {k.v}
              </mark>
            )
          case 'em':
            return (
              <em key={i} className="not-italic font-medium text-(--color-text)">
                {k.v}
              </em>
            )
          case 'code':
            return (
              <code key={i} className="md-code">
                {k.v}
              </code>
            )
          case 'link':
            return (
              <a
                key={i}
                href={k.href}
                target="_blank"
                rel="noreferrer noopener"
                className="text-(--color-accent) hover:underline"
              >
                {k.v}
              </a>
            )
          default:
            return <Fragment key={i}>{k.v}</Fragment>
        }
      })}
    </>
  )
}

/** 줄바꿈이 들어 있는 긴 본문용 — 빈 줄을 문단으로 끊는다. */
export function MdBlock({
  children,
  className = '',
}: {
  children?: string | null
  className?: string
}) {
  const paras = useMemo(
    () => (children ?? '').split(/\n{2,}/).filter((p) => p.trim() !== ''),
    [children],
  )
  if (!children) return null
  return (
    <div className={className}>
      {paras.map((p, i) => (
        <p key={i} className={i > 0 ? 'mt-3' : ''}>
          <Md>{p}</Md>
        </p>
      ))}
    </div>
  )
}
