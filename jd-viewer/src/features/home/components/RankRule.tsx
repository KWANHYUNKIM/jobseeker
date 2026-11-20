/**
 * '왜 이 순서인가요?' — 메인의 순위가 무엇으로 정해지는지 그대로 적는다. 숨은 가중치가 있으면 사람은
 * 그 순위를 믿을 이유가 없다. 숫자는 backend `app/features/home/service.py` 의 `_sort_key`·`score_parts` 와
 * 같아야 한다(규칙을 바꾸면 여기도 고친다). 광고·유료 노출은 없다.
 */
export function RankRule({ kind }: { kind: 'companies' | 'jobs' }) {
  return (
    <details className="group text-[13px] text-[#777]">
      <summary className="cursor-pointer list-none select-none hover:text-[#272727] [&::-webkit-details-marker]:hidden">
        왜 이 순서인가요? <span className="inline-block transition group-open:rotate-90">›</span>
      </summary>
      <div className="mt-2 rounded-xl border border-[#e2e8ec] bg-[#f7f9fa] px-4 py-3 leading-[1.7] text-[#474747]">
        {kind === 'companies' ? (
          <>
            <p className="font-medium text-[#272727]">회사 순서는 아래 셋을 차례로 비교해 정해요.</p>
            <ol className="mt-1 list-decimal pl-5">
              <li>회사 규모 — 대기업 → 중견기업 → 해외 기업 → 중소기업</li>
              <li>같은 규모 안에서는 지금 모집중인 IT 공고가 많은 순</li>
              <li>그것도 같으면 이번 주(7일) 새로 올라온 공고가 많은 순</li>
            </ol>
            <p className="mt-1">
              카드의 숫자가 그 값이에요. 마감일 없이 늘 열려 있는 상시 공고만 있는 회사는 여기서 빼고 상시 채용에 따로 모았어요.
              광고나 유료 노출은 없어요.
            </p>
          </>
        ) : (
          <>
            <p className="font-medium text-[#272727]">공고마다 아래 점수를 더해 높은 순으로 줄 세워요.</p>
            <ul className="mt-1 list-disc pl-5">
              <li>회사 규모 — 대기업 30 · 중견 18 · 해외 14 · 중소 4</li>
              <li>새 공고 — 올라온 지 21일 안이면 남은 날 × 1.2 (오늘 올라오면 25.2)</li>
              <li>적극 채용 — 그 회사가 이번 주 새로 낸 공고 수 (최대 15)</li>
              <li>마감 임박 — 마감이 7일 안이면 6</li>
              <li>채용대행·헤드헌팅 공고는 −25</li>
            </ul>
            <p className="mt-1">
              한 회사가 순위를 독차지하지 않도록 회사마다 1건씩 먼저 세우고, 자리가 남으면 2번째 공고를 넣어요. 공고에 마우스를
              올리면 점수 내역이 보여요. 광고나 유료 노출은 없어요.
            </p>
          </>
        )}
      </div>
    </details>
  )
}
