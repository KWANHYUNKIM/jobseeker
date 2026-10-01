import { apiOrFile } from '../../api/client'
import type { PriceRec } from './utils/hardware'

export interface PricesFile {
  day?: string
  parts: Record<string, PriceRec>
}

/**
 * 부품 가격(오늘 최저가·매물·이력). 뷰어 API(`/api/hardware/prices`)가 먼저, 없으면 크롤러가
 * 매일 찍는 prices.json. 둘 다 없으면(크롤러가 한 번도 안 돌았다) 가격 없이 보인다.
 * 부품·성능·스펙(parts·index·bench·models)은 조사 엔진이 쓰는 문서라 정적 파일 그대로다.
 */
export async function fetchPrices(): Promise<PricesFile> {
  try {
    return (await apiOrFile<PricesFile>('/api/hardware/prices', '/hardware/prices.json')).data
  } catch {
    return { parts: {} }
  }
}
