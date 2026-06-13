import clsx from 'clsx'
import type { DomainMastery, ServiceCell } from '../api/client'

interface Props {
  domains: DomainMastery[]
}

const STATUS_STYLE: Record<string, string> = {
  strong: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  developing: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  weak: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
  unknown: 'bg-white/10 text-ink-muted border-line-strong',
}

function ServiceChip({ cell }: { cell: ServiceCell }) {
  return (
    <span className={clsx(
      'inline-block px-2 py-0.5 rounded border text-xs font-medium',
      STATUS_STYLE[cell.status] ?? STATUS_STYLE.unknown
    )}>
      {cell.service_name}
      <span className="ml-1 font-semibold opacity-80">{Math.round(cell.mastery_pct)}%</span>
    </span>
  )
}

export default function ServiceHeatmap({ domains }: Props) {
  if (!domains || domains.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 bg-white/5 rounded border border-dashed border-line-strong text-ink-subtle text-sm">
        Service heatmap will appear after assessment data is available.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-3 text-xs">
        {Object.entries({ strong: 'Strong (≥75%)', developing: 'Developing (55–74%)', weak: 'Weak (<55%)', unknown: 'Insufficient data' }).map(([k, v]) => (
          <span key={k} className={clsx('px-2 py-0.5 rounded border', STATUS_STYLE[k])}>{v}</span>
        ))}
      </div>
      <div className="divide-y divide-white/10">
        {domains.map((d) => (
          <div key={d.domain_id} className="py-2">
            <div className="text-xs font-semibold text-ink mb-1.5">
              {d.name} <span className="font-normal text-ink-muted">({d.weight_pct}% of exam)</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {d.services && d.services.length > 0 ? (
                d.services.map((cell) => <ServiceChip key={cell.service_id} cell={cell} />)
              ) : (
                <span className="text-xs text-ink-subtle">No service-level data</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
