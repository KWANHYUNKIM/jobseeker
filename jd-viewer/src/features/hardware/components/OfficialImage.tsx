import { useState } from 'react'

// 제조사 공식 이미지 — 파일로 복사하지 않고 원본 주소에서 불러온다(hw-engine PROMPT 규칙 7).
// 원본이 막히거나(일부 제조사 CDN 은 자동화 브라우저를 거른다) 주소가 바뀌면 깨진 그림 대신
// '공식 페이지에서 보기' 로 바꾼다. 출처는 늘 같이 단다.

export interface ImageRef {
  url: string
  credit: string
  page: string
}

export function OfficialImage({ image, alt, className, caption = false }: { image: ImageRef; alt: string; className: string; caption?: boolean }) {
  const [broken, setBroken] = useState(false)
  if (broken) {
    return (
      <a href={image.page} target="_blank" rel="noreferrer" className={`${className} grid place-items-center text-center text-[10px] text-(--color-faint) bg-(--color-band) hover:underline`}>
        사진 불러오기 실패
        <br />
        {image.credit} 공식 페이지에서 보기
      </a>
    )
  }
  const img = <img src={image.url} alt={alt} loading="lazy" referrerPolicy="no-referrer" onError={() => setBroken(true)} className={`${className} object-contain bg-white`} />
  if (!caption) return img
  return (
    <figure>
      {img}
      <figcaption className="text-[10px] text-(--color-faint)">
        사진:{' '}
        <a href={image.page} target="_blank" rel="noreferrer" className="hover:underline">
          {image.credit} 공식 페이지
        </a>
      </figcaption>
    </figure>
  )
}
