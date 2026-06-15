import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

interface Props {
  data: { name: string; count: number }[]
  onPick: (name: string) => void
  highlight: Set<string>
}

// 테마 변수를 런타임에 읽어 차트에 적용(SVG 속성은 var() 호환이 불안정).
// themechange 이벤트로 다크/라이트 전환 시 재렌더.
function useThemeColors() {
  const read = () => {
    const s = getComputedStyle(document.documentElement)
    const v = (n: string) => s.getPropertyValue(n).trim()
    return {
      border: v('--color-border'),
      muted: v('--color-muted'),
      panel: v('--color-panel'),
      text: v('--color-text'),
      accent: v('--color-accent'),
    }
  }
  const [c, setC] = useState(read)
  useEffect(() => {
    const on = () => setC(read())
    window.addEventListener('themechange', on)
    return () => window.removeEventListener('themechange', on)
  }, [])
  return c
}

export function TechChart({ data, onPick, highlight }: Props) {
  const c = useThemeColors()

  if (data.length === 0) {
    return (
      <div className="px-4 pb-2 text-xs text-(--color-muted)">
        기술스택 데이터가 없습니다.
      </div>
    )
  }

  const top = data.slice(0, 30)

  return (
    <div className="border-b border-(--color-border) bg-(--color-panel) px-4 pt-3 pb-4">
      <div className="flex items-baseline justify-between mb-2">
        <h2 className="text-(--color-text) text-sm font-medium">기술스택 빈도 (상위 30)</h2>
        <span className="text-xs text-(--color-muted)">막대 클릭으로 필터 토글</span>
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={top} margin={{ top: 4, right: 8, left: -16, bottom: 56 }}>
          <CartesianGrid stroke={c.border} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="name"
            angle={-45}
            textAnchor="end"
            interval={0}
            tick={{ fill: c.muted, fontSize: 11 }}
            stroke={c.border}
          />
          <YAxis tick={{ fill: c.muted, fontSize: 11 }} stroke={c.border} />
          <Tooltip
            cursor={{ fill: c.text, fillOpacity: 0.06 }}
            contentStyle={{
              background: c.panel,
              border: `1px solid ${c.border}`,
              borderRadius: 4,
              fontSize: 12,
              color: c.text,
            }}
            labelStyle={{ color: c.text }}
            itemStyle={{ color: c.text }}
          />
          <Bar
            dataKey="count"
            fill={c.accent}
            onClick={(d: { name?: string }) => {
              if (d.name) onPick(d.name)
            }}
            cursor="pointer"
            shape={(props: {
              x?: number
              y?: number
              width?: number
              height?: number
              payload?: { name: string }
            }) => {
              const { x = 0, y = 0, width = 0, height = 0, payload } = props
              const isHi = payload ? highlight.has(payload.name) : false
              return (
                <rect
                  x={x}
                  y={y}
                  width={width}
                  height={height}
                  fill={c.accent}
                  fillOpacity={isHi ? 1 : 0.55}
                  rx={2}
                />
              )
            }}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
