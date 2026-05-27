import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

interface Props {
  data: { name: string; count: number }[]
  onPick: (name: string) => void
  highlight: Set<string>
}

export function TechChart({ data, onPick, highlight }: Props) {
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
        <h2 className="text-white text-sm font-medium">기술스택 빈도 (상위 30)</h2>
        <span className="text-xs text-(--color-muted)">막대 클릭으로 필터 토글</span>
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={top} margin={{ top: 4, right: 8, left: -16, bottom: 56 }}>
          <CartesianGrid stroke="#2a2d36" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="name"
            angle={-45}
            textAnchor="end"
            interval={0}
            tick={{ fill: '#9aa0aa', fontSize: 11 }}
            stroke="#2a2d36"
          />
          <YAxis tick={{ fill: '#9aa0aa', fontSize: 11 }} stroke="#2a2d36" />
          <Tooltip
            cursor={{ fill: 'rgba(192,132,252,0.1)' }}
            contentStyle={{
              background: '#15171d',
              border: '1px solid #2a2d36',
              borderRadius: 4,
              fontSize: 12,
              color: '#e6e7eb',
            }}
          />
          <Bar
            dataKey="count"
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
                  fill={isHi ? '#c084fc' : '#7d4dab'}
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
