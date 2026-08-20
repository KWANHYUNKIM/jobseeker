import { useState } from 'react'
import { MindmapView } from './MindmapView'
import { ClusterView } from './ClusterView'
import { PathwayView } from './PathwayView'

type View = 'cluster' | 'tree' | 'pathway'

export function CareerMap() {
  const [view, setView] = useState<View>('cluster')

  return (
    <div className="flex flex-1 flex-col min-w-0 min-h-0">
      <div className="border-b border-(--color-border) bg-(--color-panel) px-4 py-1.5 flex items-center gap-1 shrink-0">
        <span className="text-[11px] text-(--color-text)/60 uppercase tracking-wider font-semibold mr-2">
          보기
        </span>
        <ViewButton active={view === 'cluster'} onClick={() => setView('cluster')}>
          ◉ 클러스터
        </ViewButton>
        <ViewButton active={view === 'tree'} onClick={() => setView('tree')}>
          ⊟ 트리
        </ViewButton>
        <ViewButton active={view === 'pathway'} onClick={() => setView('pathway')}>
          ⇄ 이동 경로
        </ViewButton>
        <span className="ml-2 text-[11px] text-(--color-text)/50 hidden sm:inline">
          {view === 'pathway'
            ? 'JD 임베딩 군집 · 어디로 갈 수 있고 무엇이 비는지'
            : '누가 어떤 직군을 뽑고 있는지'}
        </span>
      </div>
      <div className="flex flex-1 min-h-0 relative">
        {view === 'cluster' ? <ClusterView /> : view === 'tree' ? <MindmapView /> : <PathwayView />}
      </div>
    </div>
  )
}

function ViewButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`text-xs px-3 py-1 rounded transition ${
        active
          ? 'bg-(--color-accent) text-(--color-on-accent) font-medium'
          : 'text-(--color-text) hover:bg-(--hover) border border-(--color-border)'
      }`}
    >
      {children}
    </button>
  )
}
