import { docFetch } from '../../api/client'
import type { AlbaData } from './utils/alba'

/**
 * 컴퓨터 알바 모음 전량(출처 다섯 곳). 크롤 단계가 구운 alba.json 을 문서 API(`/api/docs/alba.json`)로 먼저,
 * 안 되면 정적 파일로 읽는다.
 */
export async function fetchAlba(init?: RequestInit): Promise<AlbaData> {
  const r = await docFetch('/alba.json', init)
  if (!r.ok) throw new Error(`alba.json ${r.status}`)
  return (await r.json()) as AlbaData
}
