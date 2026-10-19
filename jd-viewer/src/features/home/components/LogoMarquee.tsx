import { CompanyMark } from '../../../components/ui'
import { companyLogoUrl } from '../../../utils/companyMark'
import type { HomeBoard } from '../api'

type Spot = HomeBoard['spotlight'][number]

/**
 * 첫 화면의 로고 띠 — 지금 IT 공고를 낸 큰 회사들이 두 줄로 반대 방향으로 흐른다.
 * 꾸밈이 아니라 정보다: 누가 뽑는지가 첫눈에 보이고, 로고를 누르면 그 회사 공고가 열린다.
 * 마우스를 올리거나 포커스가 들어오면 멈춘다. 움직임 줄이기를 켠 사람에게는 멈춘 로고 벽.
 */
export function LogoMarquee({ items, onOpen }: { items: Spot[]; onOpen: (slug: string) => void }) {
  // 로고를 그릴 수 있는 회사만 — 글자 마크가 섞이면 띠가 듬성듬성해 보인다
  const withLogo = items.filter((x) => x.logo || companyLogoUrl(x.name))
  if (withLogo.length < 8) return null
  const half = Math.ceil(withLogo.length / 2)
  const rows = [withLogo.slice(0, half), withLogo.slice(half)]
  return (
    <div className="flex flex-col gap-3" aria-label="지금 IT 인재를 뽑는 회사">
      {rows.map((row, i) => (
        <div key={i} className="home-marquee-wrap overflow-hidden">
          <ul
            className={'home-marquee gap-3 ' + (i ? 'reverse' : '')}
            style={{ ['--dur' as string]: `${Math.max(40, row.length * 4)}s` }}
          >
            {[...row, ...row].map((c, k) => (
              <li key={c.slug + k} className={k >= row.length ? 'home-dup' : ''} aria-hidden={k >= row.length}>
                <button
                  type="button"
                  tabIndex={k >= row.length ? -1 : 0}
                  onClick={() => onOpen(c.slug)}
                  title={`${c.name} — IT 공고 ${c.active}건`}
                  className="home-press flex items-center gap-2.5 h-14 pl-2.5 pr-4 rounded-2xl bg-(--color-panel) border border-(--color-border-soft) hover:border-(--color-accent) focus-visible:outline-2 focus-visible:outline-(--color-accent)"
                >
                  <span className="grid place-items-center w-9 h-9 rounded-xl bg-white overflow-hidden">
                    <CompanyMark name={c.name} logo={c.logo} size={28} />
                  </span>
                  <span className="text-[13.5px] font-semibold text-(--color-text) whitespace-nowrap">
                    {c.name.replace(/\s*\(.*?\)\s*/g, '')}
                  </span>
                  <span className="text-xs tabular-nums text-(--color-accent-deep) font-semibold">{c.active}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}
