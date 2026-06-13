import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ReferenceLine, ResponsiveContainer, Area, AreaChart
} from 'recharts'

interface ProgressPoint {
  week: number
  planned_topics: number
  actual_topics: number
  status: string
  intervention?: { agent: string; action: string; reason: string }
}

interface Props {
  series: ProgressPoint[]
  title?: string
}

const STATUS_COLOR: Record<string, string> = {
  on_track: '#22c55e',
  ahead: '#3b82f6',
  at_risk: '#f59e0b',
  off_track: '#ef4444',
}

export default function DeviationGraph({ series, title = 'Planned vs Actual Progress' }: Props) {
  if (!series || series.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 bg-white/5 rounded border border-dashed border-line-strong text-ink-subtle text-sm">
        Progress data will appear here after a workflow runs.
      </div>
    )
  }

  const interventionWeeks = series
    .filter((p) => p.intervention)
    .map((p) => p.week)

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={series} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="week"
            label={{ value: 'Week', position: 'insideBottom', offset: -2 }}
            tick={{ fontSize: 11 }}
          />
          <YAxis tick={{ fontSize: 11 }} label={{ value: 'Topics', angle: -90, position: 'insideLeft', fontSize: 11 }} />
          <Tooltip
            formatter={(val: number, name: string) => [val, name === 'planned_topics' ? 'Planned' : 'Actual']}
            labelFormatter={(l) => `Week ${l}`}
          />
          <Legend
            formatter={(v) => v === 'planned_topics' ? 'Planned' : 'Actual'}
            wrapperStyle={{ fontSize: 11 }}
          />
          {interventionWeeks.map((w) => (
            <ReferenceLine
              key={w}
              x={w}
              stroke="#8b5cf6"
              strokeDasharray="4 2"
              label={{ value: '↑ Replan', position: 'top', fill: '#8b5cf6', fontSize: 10 }}
            />
          ))}
          <Line
            type="monotone"
            dataKey="planned_topics"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
            strokeDasharray="5 3"
          />
          <Line
            type="monotone"
            dataKey="actual_topics"
            stroke="#22c55e"
            strokeWidth={2}
            dot={(props) => {
              const { cx, cy, payload } = props
              const color = STATUS_COLOR[payload.status] ?? '#6b7280'
              return <circle key={cx} cx={cx} cy={cy} r={4} fill={color} stroke="#fff" strokeWidth={1.5} />
            }}
          />
        </LineChart>
      </ResponsiveContainer>
      <div className="flex gap-4 text-xs">
        {Object.entries(STATUS_COLOR).map(([s, c]) => (
          <span key={s} className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: c }} />
            {s.replace('_', ' ')}
          </span>
        ))}
      </div>
    </div>
  )
}
