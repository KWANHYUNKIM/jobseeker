/** 쪽 번호(캐치형) — ‹ 1 2 3 4 5 6 7 … 61 ›. 지금 쪽은 검은 동그라미. 잡 리스트·기술 블로그가 같이 쓴다. */
export function Pager({
  page,
  totalPages,
  onChange,
  scrollTo,
}: {
  page: number
  totalPages: number
  onChange: (p: number) => void
  /** 쪽을 넘긴 뒤 화면을 올려 보낼 자리(CSS 선택자). */
  scrollTo?: string
}) {
  if (totalPages <= 1) return null
  const go = (p: number) => {
    onChange(Math.max(0, Math.min(totalPages - 1, p)))
    if (scrollTo) document.querySelector(scrollTo)?.scrollIntoView({ block: 'start' })
  }
  // 앞 일곱 쪽(지금 쪽이 넘어가면 지금 쪽 둘레 일곱) + 마지막 쪽.
  const from = Math.max(0, Math.min(page - 3, totalPages - 7))
  const nums = Array.from({ length: Math.min(7, totalPages) }, (_, k) => from + k)
  const last = totalPages - 1
  return (
    <nav aria-label="쪽" className="mt-[34px] mb-[90px] flex items-center justify-center gap-[6px] text-sm text-[#666] tabular-nums">
      <PageBtn onClick={() => go(page - 1)} label="이전 쪽">‹</PageBtn>
      {from > 0 && (
        <>
          <PageBtn onClick={() => go(0)}>1</PageBtn>
          <span className="w-[34px] text-center">…</span>
        </>
      )}
      {nums.map((p) => (
        <PageBtn key={p} on={p === page} onClick={() => go(p)}>
          {p + 1}
        </PageBtn>
      ))}
      {nums[nums.length - 1] < last && (
        <>
          <span className="w-[34px] text-center">…</span>
          <PageBtn onClick={() => go(last)}>{last + 1}</PageBtn>
        </>
      )}
      <PageBtn onClick={() => go(page + 1)} label="다음 쪽">›</PageBtn>
    </nav>
  )
}

function PageBtn({ on, onClick, label, children }: { on?: boolean; onClick: () => void; label?: string; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-current={on ? 'page' : undefined}
      className={'w-[34px] h-[34px] rounded-full ' + (on ? 'bg-[#272727] font-bold text-white' : 'hover:text-[#272727]')}
    >
      {children}
    </button>
  )
}

