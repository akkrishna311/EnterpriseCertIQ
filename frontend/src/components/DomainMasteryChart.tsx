import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ReferenceLine, ResponsiveContainer } from 'recharts'
import type { DomainMastery } from '../api/client'
import clsx from 'clsx'

interface Props {
  domains: DomainMastery[]
  passThreshold?: number
}

function barColor(pct: number): string {
  if (pct >= 75) return '#22c55e'
  if (pct >= 55) return '#f59e0b'
  return '#ef4444'
}

export default function DomainMasteryChart({ domains, passThreshold = 700 }: Props) {
  if (!domains || domains.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 bg-white/5 rounded border border-dashed border-line-strong text-ink-subtle text-sm">
        Domain mastery will appear after assessment data is available.
      </div>
    )
  }

  const data = domains.map((d) => ({
    name: d.name.length > 25 ? d.name.slice(0, 24) + '…' : d.name,
    fullName: d.name,
    mastery: Math.round(d.mastery_pct),
    weight: d.weight_pct,
    confidence: Math.round(d.confidence * 100),
    flag: d.flag,
  }))

  return (
    <div className="space-y-3">
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 32, top: 4, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
          <YAxis type="category" dataKey="name" width={170} tick={{ fontSize: 10 }} />
          <Tooltip
            formatter={(v: number, _: string, props) => [
              `${v}% mastery (${props.payload.confidence}% confidence)`,
              props.payload.fullName,
            ]}
          />
          <ReferenceLine x={75} stroke="#6b7280" strokeDasharray="4 2" label={{ value: '75%', fontSize: 10, fill: '#6b7280' }} />
          <Bar dataKey="mastery" radius={[0, 3, 3, 0]}>
            {data.map((entry, i) => (
              <Cell key={i} fill={barColor(entry.mastery)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Domain table */}
      <div className="text-xs divide-y divide-gray-100">
        {domains.map((d) => (
          <div key={d.domain_id} className="flex items-center gap-3 py-1.5 px-1">
            <div className="w-3 h-3 rounded-full shrink-0" style={{ background: barColor(d.mastery_pct) }} />
            <span className="flex-1 text-ink truncate">{d.name}</span>
            <span className="text-ink-subtle">{d.weight_pct}%</span>
            <span className={clsx('font-semibold w-12 text-right',
              d.mastery_pct >= 75 ? 'text-emerald-300' : d.mastery_pct >= 55 ? 'text-amber-300' : 'text-rose-300'
            )}>{Math.round(d.mastery_pct)}%</span>
            {d.flag === 'low_evidence' && (
              <span className="text-amber-500 text-xs">⚠ low evidence</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
