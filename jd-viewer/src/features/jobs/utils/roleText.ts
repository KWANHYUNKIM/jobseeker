// 공고 풀이 글의 작은 표기 — **굵게**, [n] 출처 번호, {추론} 표시 — 를 조각으로 나눈다.
// 공고 줄과 풀이의 quote 를 맞출 때는 글머리표·공백·문장부호 차이를 지운 꼴로 비교한다(engine/roles/validate.py 의 norm 과 같은 규칙).

export type RoleToken =
  | { kind: 'text'; text: string }
  | { kind: 'bold'; text: string }
  | { kind: 'ref'; n: number }
  | { kind: 'guess' }

const TOKEN = /(\*\*[^*]+\*\*|\[\d{1,2}\]|\{추론\})/g

export function roleTokens(s: string): RoleToken[] {
  const out: RoleToken[] = []
  for (const part of s.split(TOKEN)) {
    if (!part) continue
    if (part.startsWith('**') && part.endsWith('**')) out.push({ kind: 'bold', text: part.slice(2, -2) })
    else if (/^\[\d{1,2}\]$/.test(part)) out.push({ kind: 'ref', n: Number(part.slice(1, -1)) })
    else if (part === '{추론}') out.push({ kind: 'guess' })
    else out.push({ kind: 'text', text: part })
  }
  return out
}

export function normLine(s: string): string {
  return (s || '')
    .replace(/^[\s\-•·*○●▶▪✓✔\d.)]+/, '')
    .replace(/[\s.,·!?~'"“”‘’()]+/g, '')
    .toLowerCase()
}

/** 공고 본문의 한 줄에 맞는 풀이 줄. 줄 하나에 풀이 하나 — 서로 포함하면 같은 줄로 본다. */
export function matchRoleLine<T extends { quote: string }>(lines: T[], rowText: string): T | undefined {
  const n = normLine(rowText)
  if (n.length < 8) return undefined
  return lines.find((l) => {
    const q = normLine(l.quote)
    return q.includes(n) || n.includes(q)
  })
}
