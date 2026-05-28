import { defineConfig, type PluginOption, type ViteDevServer } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

// public/mindmap.md, public/all_jobs_enriched.json 변경 시 브라우저 자동 새로고침
function dataReloadPlugin(): PluginOption {
  const watched = [
    path.resolve(__dirname, 'public/mindmap.md'),
    path.resolve(__dirname, 'public/all_jobs_enriched.json'),
  ]
  return {
    name: 'data-reload',
    configureServer(server: ViteDevServer) {
      for (const f of watched) server.watcher.add(f)
      server.watcher.on('change', (file: string) => {
        if (watched.includes(file)) {
          server.ws.send({ type: 'full-reload', path: '*' })
          // eslint-disable-next-line no-console
          console.log(`[data-reload] ${path.basename(file)} 변경 감지 → 페이지 새로고침`)
        }
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), dataReloadPlugin()],
  server: {
    fs: {
      allow: [path.resolve(__dirname, '..')],
    },
  },
})
