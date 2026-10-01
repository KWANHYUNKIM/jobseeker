// 필터 축 규칙 — catch_capture/tests/test_facets.py 와 같은 사례를 같은 답으로 고정한다.
// 규칙이 TS(여기)와 파이썬(store/jobs/facets.py) 두 곳에 있으니, 한쪽만 고치면 둘 중 하나가 깨진다.
import { describe, expect, it } from 'vitest'
import { careerBucket } from './career'
import { classifyRoles } from '../../../utils/classify'
import { placeOf } from './region'

const W = '　'

describe('careerBucket', () => {
  it.each([
    ['', '정보없음'],
    ['신입', '신입/무관'],
    ['경력무관', '신입/무관'],
    ['경력 3년 이상', '3-4년'],
    ['1~2년', '1-2년'],
    ['10년 이상', '8년+'],
    ['경력', '정보없음'],
  ])('%s → %s', (career, want) => expect(careerBucket(career)).toBe(want))
})

describe('classifyRoles', () => {
  it.each<[string, string[], string, string[]]>([
    ['백엔드 개발자', [], '', ['백엔드']],
    ['Android 개발자', [], '', ['모바일']],
    // 알려진 버그: \b 는 ASCII 기준이라 한글 '안드로이드' 옆에서 경계가 안 생긴다
    ['안드로이드 개발자', [], '', ['기타']],
    ['풀스택 엔지니어', [], '', ['풀스택', '백엔드', '프론트엔드']],
    ['사내 IT', [], `업무시스템\n\n${W}운영 경험`, ['DevOps/인프라']],
    ['Senior Engineer', ['React', 'Spring'], '', ['백엔드', '프론트엔드']],
    ['마케팅 담당', [], '', ['기타']],
  ])('%s', (title, stack, extra, want) => expect(classifyRoles(title, stack, extra)).toEqual(want))
})

describe('placeOf', () => {
  it.each<[string, string, string | null]>([
    ['서울 강남구', '서울', '강남구'],
    // 알려진 버그: '서울특별시' 도 '서울' 로 시작해 '특별시' 를 시군구로 읽고 버린다
    ['서울특별시 강남구', '서울', null],
    ['경기성남시 분당구', '경기', '성남시'],
    ['교육생 | 서울 송파구', '서울', '송파구'],
    ['해외 도쿄', '해외·원격', null],
    ['Pangyo (Software Dream Center), South Korea', '경기', null],
    ['Remote', '해외·원격', null],
    ['South Korea', '정보없음', null],
    ['', '정보없음', null],
    [`${W}부산 해운대구`, '부산', '해운대구'],
  ])('%s', (location, region, district) => expect(placeOf({ location })).toEqual({ region, district }))

  it('overseas 표시가 주소보다 먼저다', () => {
    expect(placeOf({ location: '서울 강남구', overseas: true })).toEqual({ region: '해외·원격', district: null })
  })
})
