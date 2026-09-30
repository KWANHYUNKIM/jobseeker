import { useMemo, useState } from 'react'

/**
 * 한 쪽에 몇 개를 보여 주나 — 뷰어 전체의 규칙.
 *
 * 본문에서 아래로 끝없이 늘어나는 목록은 전부 쪽으로 끊고, 기본은 10개다.
 * 10개로 두면 화면이 이상해지는 곳만 예외를 쓴다.
 * - DENSE: 한 줄짜리 표·목록. 10건이면 넓은 화면의 절반이 빈다.
 * - GRID : 2·3·4열 격자. 10은 3열에서 마지막 줄이 한 칸만 남는다.
 * 왼쪽의 고르는 목록(nav)은 대상이 아니다 — 고른 항목이 다른 쪽으로 숨어 버린다.
 */
export const PAGE_SIZE = 10
export const PAGE_SIZE_DENSE = 20
export const PAGE_SIZE_GRID = 12

/**
 * 목록을 페이지로 자른다.
 *
 * 목록 탭들은 왼쪽 필터 바가 세로로 길어서 그쪽은 스크롤이 자연스럽지만, 오른쪽 본문까지
 * 끝없이 스크롤되면 "지금 몇 번째를 보고 있는지"가 사라진다. 그래서 본문은 페이지로 끊는다.
 *
 * 필터가 바뀌면 1페이지로 돌아간다. effect 에서 setState 하면 한 번 그린 뒤 다시 그리게
 * 되어(잘못된 페이지가 한 프레임 보인다) React 가 권하는 '렌더 중 조정' 패턴을 쓴다.
 * 그래서 `items` 는 필터 결과처럼 **내용이 바뀔 때만 새 배열**이어야 한다(useMemo 결과).
 */
export function usePaged<T>(items: T[], pageSize: number) {
  const [page, setPage] = useState(0)

  const [prevItems, setPrevItems] = useState(items)
  if (items !== prevItems) {
    setPrevItems(items)
    setPage(0)
  }

  const totalPages = Math.max(1, Math.ceil(items.length / pageSize))
  // 마지막 페이지를 보던 중 목록이 줄면 빈 페이지가 남는다 — 렌더 시점에 접어 준다.
  const safePage = Math.min(page, totalPages - 1)
  const start = safePage * pageSize
  const slice = useMemo(() => items.slice(start, start + pageSize), [items, start, pageSize])

  return { page: safePage, setPage, totalPages, start, slice, total: items.length }
}
