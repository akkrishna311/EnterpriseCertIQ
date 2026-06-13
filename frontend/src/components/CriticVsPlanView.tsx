import clsx from 'clsx'
import { CheckCircle, XCircle, AlertCircle } from 'lucide-react'

interface Objection {
  objection_id: string
  plan_element_id: string
  severity: 'red' | 'amber' | 'green'
  description: string
  recommendation: string
  citation?: string
  resolved?: boolean
}

interface Props {
  objections: Objection[]
  planSummary?: string
}

function ObjectionCard({ obj }: { obj: Objection }) {
  const color = obj.resolved
    ? 'border-green-400 bg-green-50'
    : obj.severity === 'red'
    ? 'border-red-400 bg-rose-500/10'
    : 'border-amber-400 bg-amber-500/10'

  const Icon = obj.resolved
    ? CheckCircle
    : obj.severity === 'red'
    ? XCircle
    : AlertCircle

  const iconColor = obj.resolved
    ? 'text-green-500'
    : obj.severity === 'red'
    ? 'text-rose-400'
    : 'text-amber-500'

  return (
    <div className={clsx('border-l-4 rounded-r p-3 text-sm space-y-1', color)}>
      <div className="flex items-center gap-2 font-semibold">
        <Icon size={14} className={iconColor} />
        <span className="text-xs text-ink-muted">[{obj.objection_id}]</span>
        {obj.resolved && (
          <span className="ml-auto text-xs text-emerald-300 font-normal">Resolved ✓</span>
        )}
      </div>
      <p className="text-ink">{obj.description}</p>
      <p className="text-ink-muted italic text-xs">→ {obj.recommendation}</p>
      {obj.citation && (
        <p className="text-ink-subtle text-xs">Source: {obj.citation}</p>
      )}
    </div>
  )
}

export default function CriticVsPlanView({ objections, planSummary }: Props) {
  const red = objections.filter((o) => o.severity === 'red' && !o.resolved)
  const amber = objections.filter((o) => o.severity === 'amber' && !o.resolved)
  const resolved = objections.filter((o) => o.resolved)

  return (
    <div className="space-y-4">
      {planSummary && (
        <div className="bg-blue-500/10 border border-blue-500/30 rounded p-3 text-sm text-blue-300">
          <strong>Plan Summary:</strong> {planSummary}
        </div>
      )}

      {objections.length === 0 ? (
        <div className="text-center text-ink-subtle py-8 text-sm">
          No plan review notes yet. Build your plan to see feedback and recommendations.
        </div>
      ) : (
        <>
          {red.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-rose-300 uppercase tracking-wide mb-2">
                🔴 Needs Attention — High Priority ({red.length})
              </h4>
              <div className="space-y-2">
                {red.map((o, index) => <ObjectionCard key={`${o.objection_id}-${index}`} obj={o} />)}
              </div>
            </div>
          )}

          {amber.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-amber-300 uppercase tracking-wide mb-2">
                🟡 Needs Attention — Medium Priority ({amber.length})
              </h4>
              <div className="space-y-2">
                {amber.map((o, index) => <ObjectionCard key={`${o.objection_id}-${index}`} obj={o} />)}
              </div>
            </div>
          )}

          {resolved.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-emerald-300 uppercase tracking-wide mb-2">
                🟢 Resolved ({resolved.length})
              </h4>
              <div className="space-y-2">
                {resolved.map((o, index) => <ObjectionCard key={`${o.objection_id}-${index}`} obj={o} />)}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
