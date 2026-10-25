/**
 * 공고 본문(주요 업무·자격 요건·우대 사항)을 화면에 그릴 덩어리로 나눈다.
 *
 * 크롤러는 원문 줄바꿈을 그대로 들고 온다. 그걸 <pre> 로 통째로 그리면 글머리표가
 * 사이트마다 제각각(• - ㆍ · * 1.)이고 소제목([주의사항])·구분선(-----)이 본문과 같은
 * 무게로 섞여 한 덩어리 글자벽이 된다. 여기서 줄마다 무엇인지 가려 두면 화면은
 * 번호 붙은 항목 · 소제목 · 보조 설명을 각자의 모양으로 그릴 수 있다.
 *
 * 못 알아본 줄은 버리지 않고 문단(para)으로 둔다 — 모양이 덜 예쁠 뿐 글은 다 보인다.
 */

export type JdBlock =
  | { kind: 'heading'; text: string }
  | { kind: 'item'; text: string; depth: 0 | 1 }
  | { kind: 'note'; text: string }
  | { kind: 'para'; text: string }

// 글머리표. 숫자 목록(1. 1) ①)도 화면이 번호를 다시 매기므로 떼어 낸다.
const BULLET = /^([•\-ㆍ·・*+▪▫◦○●►▶▷✓✔✅➤→]|\d{1,2}[.)](?!\d)|[①-⑳])\s*/
const DIVIDER = /^[-=_~*─━·.]{3,}$/
const NOTE = /^[※*]\s*/
// 소제목: [주의사항] · 【필수】 · <우대> · ■ 전형방법 · "Requirements:" 처럼 짧고 홀로 선 줄.
const BRACKET_HEAD = /^(\[[^\]]{1,30}\]|【[^】]{1,30}】|<[^>]{1,30}>|〈[^〉]{1,30}〉)$/
const MARK_HEAD = /^[■□◆◇◼◻]\s*(.{1,30})$/
const COLON_HEAD = /^([^:：]{1,40})[:：]$/

function headingOf(s: string): string | null {
  if (BRACKET_HEAD.test(s)) return s.slice(1, -1).trim()
  const m = MARK_HEAD.exec(s) ?? COLON_HEAD.exec(s)
  if (m && !/[.。]$/.test(m[1])) return m[1].trim()
  return null
}

export function parseJdText(text: string): JdBlock[] {
  const lines = text.replace(/\r\n?/g, '\n').split('\n')
  const hasBullets = lines.some((l) => BULLET.test(l.trim()) && !DIVIDER.test(l.trim()))
  const out: JdBlock[] = []
  // 소제목마다 처음 본 글머리표가 1단계다. 다른 표가 나오면 그 아래 2단계로 본다
  // ("• 대분류" 아래 "- 세부"). 들여쓰기가 남아 있으면 그것도 2단계의 근거다.
  let topMark: string | null = null

  for (const raw of lines) {
    const s = raw.trim()
    if (!s || DIVIDER.test(s)) continue

    const head = headingOf(s)
    if (head) {
      out.push({ kind: 'heading', text: head })
      topMark = null
      continue
    }
    if (NOTE.test(s) && s.startsWith('※')) {
      out.push({ kind: 'note', text: s.replace(NOTE, '') })
      continue
    }

    const m = BULLET.exec(s)
    if (m) {
      const body = s.slice(m[0].length).trim()
      if (!body) continue
      const mark = /\d/.test(m[1]) ? '1.' : /[①-⑳]/.test(m[1]) ? '①' : m[1]
      if (topMark === null) topMark = mark
      const indented = /^\s{2,}/.test(raw)
      const depth = mark !== topMark || (indented && out.length > 0) ? 1 : 0
      out.push({ kind: 'item', text: body, depth })
      continue
    }

    // 글머리표가 하나도 없는 본문은 줄 하나가 항목 하나다(그리팅 등). 다만 긴 산문은 문단.
    if (!hasBullets && s.length <= 200) out.push({ kind: 'item', text: s, depth: 0 })
    else out.push({ kind: 'para', text: s })
  }

  // 항목이 하나뿐이면 번호 '01' 이 오히려 어색하다 — 문단으로 돌린다.
  const items = out.filter((b) => b.kind === 'item')
  if (items.length === 1) {
    return out.map((b) => (b.kind === 'item' ? { kind: 'para', text: b.text } : b))
  }
  return out
}
