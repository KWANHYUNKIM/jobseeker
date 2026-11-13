const SOURCES = '사람인 · 잡코리아 · 인크루트 · 게임잡 · 각 사 채용 페이지'

/**
 * 화면 맨 아래 띠(캐치형 디자인) — 이름·안내 낱말·출처·갱신 시각, 오른쪽에 맨 위로 단추.
 * 안내 낱말(서비스 소개 등)은 아직 따로 된 화면이 없어서 글자만 둔다.
 */
export function SiteFooter({
  updated,
  jobs,
  companies,
  sources = SOURCES,
}: {
  updated?: string | null
  jobs?: number
  companies?: number
  /** 공고 출처 줄 — 화면마다 실린 출처가 다르다(잡 리스트는 원티드·점핏까지). */
  sources?: string
}) {
  const meta = [
    updated ? `마지막 갱신 ${updated.slice(0, 16).replace('T', ' ')}` : null,
    jobs != null ? `공고 ${jobs.toLocaleString()}건` : null,
    companies != null ? `회사 ${companies.toLocaleString()}곳` : null,
  ].filter(Boolean)
  const toTop = () => {
    document.querySelector('[data-scroll]')?.scrollTo({ top: 0, behavior: 'smooth' })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
  return (
    <footer className="bg-[#f3f6f8]">
      <div className="jd-container relative pt-[31px] pb-[40px] min-h-[167px]">
        <div className="flex flex-col md:flex-row md:justify-between gap-4">
          <div className="text-[22px] font-bold leading-8 tracking-[-1px] text-[#9aa1a8]">JD Viewer</div>
          <div className="md:text-right">
            <ul className="flex flex-wrap md:justify-end gap-x-[21px] gap-y-1 pt-1 text-xs leading-[18px] text-[#474747]">
              <li>서비스 소개</li>
              <li>이용가이드</li>
              <li>이용약관</li>
              <li className="font-bold text-[#272727]">개인정보처리방침</li>
              <li>데이터 출처</li>
              <li>고객센터</li>
            </ul>
            <p className="mt-[9px] text-[11px] leading-4 text-[#777]">
              공고 출처 : {sources} | 매일 06시 갱신
            </p>
            <p className="mt-[2px] text-[11px] leading-4 text-[#777]">Copyright © JD Viewer. All rights reserved.</p>
          </div>
        </div>
        {meta.length > 0 && <p className="mt-[29px] md:-mt-[2px] text-xs leading-[18px] text-[#999]">{meta.join(' · ')}</p>}
        <button
          type="button"
          onClick={toTop}
          aria-label="맨 위로"
          className="absolute right-4 -top-5 min-[1400px]:-right-[42px] min-[1400px]:top-px w-10 h-10 rounded-full bg-[#272727] grid place-items-center"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 10l4-4 4 4" />
          </svg>
        </button>
      </div>
    </footer>
  )
}
