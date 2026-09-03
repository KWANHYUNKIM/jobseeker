import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { migrateLegacyHash } from './lib/router'
import { trackVisit } from './lib/track'

// 예전 해시 주소(#radar/netflix)로 저장된 북마크·공유 링크를 새 경로로 넘긴 뒤 그린다.
// 렌더 전에 해야 첫 화면이 옛 주소로 한 번 그려졌다가 튀는 일이 없다.
migrateLegacyHash()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// 방문 시작 1회. 화면이 그려지기 전에 불러도 되지만, 렌더 실패로 화면이
// 안 뜬 방문까지 '들어왔다'로 세지 않도록 마운트 뒤에 둔다.
trackVisit()
