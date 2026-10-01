import type { ReactNode } from 'react'
import { JobBoardContext, useJobBoard } from '../features/jobs/hooks/useJobBoard'

/** 앱 전체가 같이 쓰는 상태. 지금은 잡 리스트 하나다(헤더 건수와 JobsPage 가 같이 읽는다). */
export function Providers({ children }: { children: ReactNode }) {
  const board = useJobBoard()
  return <JobBoardContext.Provider value={board}>{children}</JobBoardContext.Provider>
}
