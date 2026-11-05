import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Metric } from '../types'

interface MetricChartProps {
  metrics: Metric[]
  lines: { key: keyof Metric; label: string; color: string }[]
  unit?: string
}

export function MetricChart({ metrics, lines, unit = '%' }: MetricChartProps) {
  const data = [...metrics]
    .reverse()
    .map((metric) => ({
      ...metric,
      time: new Date(metric.collected_at).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      }),
    }))

  if (data.length === 0) {
    return <div className="chart-empty">No metric history has been reported yet.</div>
  }

  return (
    <div className="metric-chart" role="img" aria-label={`${lines.map((line) => line.label).join(' and ')} history chart`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
          <CartesianGrid stroke="#e9edf2" strokeDasharray="3 5" vertical={false} />
          <XAxis dataKey="time" tick={{ fill: '#8a94a5', fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={30} />
          <YAxis
            tick={{ fill: '#8a94a5', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={42}
            tickFormatter={(value: number) => unit === '%' ? `${value}%` : formatBytes(value)}
          />
          <Tooltip
            contentStyle={{ border: '1px solid #e8ebf0', borderRadius: 10, boxShadow: '0 8px 24px #17203312' }}
            formatter={(value, name) => [
              unit === '%' ? `${Number(value).toFixed(1)}%` : formatBytes(Number(value)),
              name,
            ]}
            labelStyle={{ color: '#667085', fontSize: 12, marginBottom: 4 }}
          />
          {lines.map((line) => (
            <Line
              key={line.key}
              type="monotone"
              dataKey={line.key}
              name={line.label}
              stroke={line.color}
              strokeWidth={2.5}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 0 }}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let value = bytes
  let unitIndex = -1
  do {
    value /= 1024
    unitIndex += 1
  } while (value >= 1024 && unitIndex < units.length - 1)
  return `${value.toFixed(1)} ${units[unitIndex]}`
}
