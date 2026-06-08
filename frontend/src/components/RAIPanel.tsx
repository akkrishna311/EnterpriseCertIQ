import { useQuery } from '@tanstack/react-query'
import { ShieldCheck, ShieldAlert, AlertTriangle, CheckCircle2, Loader2, Info } from 'lucide-react'
import { api, type RAIControl, type GroundednessEval, type RubricEval } from '../api/client'

const MODE_BADGE: Record<string, string> = {
  azure_ai_content_safety: 'bg-emerald-100 text-emerald-700',
  regex_fallback: 'bg-amber-100 text-amber-700',
  azure_ai_evaluation: 'bg-emerald-100 text-emerald-700',
  heuristic: 'bg-amber-100 text-amber-700',
  domain_aware: 'bg-blue-100 text-blue-700',
  pipeline_check: 'bg-blue-100 text-blue-700',
  regex_scan: 'bg-blue-100 text-blue-700',
  human_in_the_loop: 'bg-purple-100 text-purple-700',
  azure_ai_foundry_agent_service: 'bg-emerald-100 text-emerald-700',
  custom_orchestrator_local: 'bg-amber-100 text-amber-700',
}

function modeLabel(mode: string) {
  return mode.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function ControlRow({ c }: { c: RAIControl }) {
  const badgeClass = MODE_BADGE[c.mode] ?? 'bg-gray-100 text-gray-600'
  const isAzure = c.mode.startsWith('azure')
  return (
    <div className="flex items-start gap-3 rounded-lg border border-gray-200 bg-white p-4">
      <div className="mt-0.5 shrink-0">
        {isAzure
          ? <ShieldCheck size={16} className="text-emerald-600" />
          : <ShieldAlert size={16} className="text-amber-500" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="text-sm font-semibold text-gray-800">{c.control}</p>
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${badgeClass}`}>
            {modeLabel(c.mode)}
          </span>
        </div>
        <p className="mt-1 text-xs text-gray-600">{c.detail}</p>
        {c.categories && (
          <div className="mt-2 flex flex-wrap gap-1">
            {c.categories.map((cat) => (
              <span key={cat} className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                {cat}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function GroundednessCard({ runId }: { runId: string }) {
  const { data, isLoading, error } = useQuery<GroundednessEval>({
    queryKey: ['groundedness', runId],
    queryFn: () => api.groundednessEval(runId),
    enabled: !!runId,
    retry: false,
  })

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-500">
        <Loader2 size={14} className="animate-spin" />
        Evaluating groundedness…
      </div>
    )
  }
  if (error || !data) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
        Groundedness eval unavailable for this run. Run the workflow first.
      </div>
    )
  }

  const pct = Math.round(data.groundedness_score * 100)
  const barColor = pct >= 80 ? 'bg-emerald-500' : pct >= 50 ? 'bg-amber-400' : 'bg-red-400'

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-gray-800">Groundedness Score</p>
          <p className="text-xs text-gray-500 mt-0.5">{data.note}</p>
        </div>
        <div className={`text-lg font-bold ${pct >= 80 ? 'text-emerald-700' : pct >= 50 ? 'text-amber-700' : 'text-red-600'}`}>
          {pct}%
        </div>
      </div>
      <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
        <div className={`h-full rounded-full ${barColor} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <div className="grid grid-cols-3 gap-3 text-xs text-center">
        <div className="rounded-lg bg-slate-50 border border-slate-200 px-2 py-2">
          <p className="text-slate-400">Citations found</p>
          <p className="font-semibold text-slate-800">{data.citation_count}</p>
        </div>
        <div className="rounded-lg bg-slate-50 border border-slate-200 px-2 py-2">
          <p className="text-slate-400">Assertions</p>
          <p className="font-semibold text-slate-800">{data.assertion_count}</p>
        </div>
        <div className={`rounded-lg border px-2 py-2 ${data.passed ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'}`}>
          <p className={data.passed ? 'text-emerald-500' : 'text-amber-500'}>Status</p>
          <p className={`font-semibold ${data.passed ? 'text-emerald-700' : 'text-amber-700'}`}>
            {data.passed ? 'Pass' : 'Review'}
          </p>
        </div>
      </div>
      {data.uncited_sample.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 mb-1">Uncited assertion samples</p>
          <ul className="space-y-1">
            {data.uncited_sample.map((s, i) => (
              <li key={i} className="text-[11px] text-gray-600 bg-slate-50 rounded px-2 py-1 truncate">
                {s.slice(0, 120)}{s.length > 120 ? '…' : ''}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function RubricCard({ runId }: { runId: string }) {
  const { data, isLoading, error } = useQuery<RubricEval>({
    queryKey: ['rubric', runId],
    queryFn: () => api.rubricEval(runId),
    enabled: !!runId,
    retry: false,
  })

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-500">
        <Loader2 size={14} className="animate-spin" />
        Running rubric checks…
      </div>
    )
  }
  if (error || !data) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
        Rubric eval unavailable. Run the workflow first.
      </div>
    )
  }

  const agentEntries = Object.entries(data.results)
  const meanPct = Math.round(data.mean_score * 100)

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-gray-800">Agent Quality Rubrics</p>
          <p className="text-xs text-gray-500">
            {agentEntries.length} agents checked · mean score {meanPct}% ·
            threshold {Math.round(data.threshold * 100)}%
          </p>
        </div>
        {data.all_passed
          ? <CheckCircle2 size={18} className="text-emerald-600 shrink-0" />
          : <AlertTriangle size={18} className="text-amber-500 shrink-0" />}
      </div>

      <div className="space-y-3">
        {agentEntries.map(([agent, result]) => (
          <div key={agent} className="space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-gray-700">{agent.replace(/_/g, ' ')}</span>
              <span className={`font-semibold ${result.passed ? 'text-emerald-700' : 'text-amber-700'}`}>
                {Math.round(result.score * 100)}%
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
              <div
                className={`h-full rounded-full ${result.passed ? 'bg-emerald-400' : 'bg-amber-400'}`}
                style={{ width: `${Math.round(result.score * 100)}%` }}
              />
            </div>
            <div className="grid grid-cols-2 gap-1">
              {result.checks.map((chk) => (
                <div key={chk.id} className="flex items-center gap-1 text-[10px] text-gray-600">
                  {chk.passed
                    ? <CheckCircle2 size={10} className="text-emerald-500 shrink-0" />
                    : <AlertTriangle size={10} className="text-amber-500 shrink-0" />}
                  <span className={chk.passed ? 'text-gray-600' : 'text-amber-800 font-medium'}>
                    {chk.id}: {chk.description}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

interface RAIPanelProps {
  runId?: string
}

export default function RAIPanel({ runId }: RAIPanelProps) {
  const { data: status, isLoading } = useQuery<import('../api/client').RAIStatus>({
    queryKey: ['rai-status'],
    queryFn: api.raiStatus,
    staleTime: 60_000,
  })

  const azureCount = status?.rai_controls.filter((c) => c.mode.startsWith('azure')).length ?? 0
  const totalCount = status?.rai_controls.length ?? 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-2">
        <div className="flex items-center gap-2">
          <ShieldCheck size={18} className="text-brand-600" />
          <h2 className="text-sm font-semibold text-gray-800">Responsible AI Controls</h2>
          {!isLoading && status && (
            <span className="ml-auto text-xs font-medium text-gray-500">
              {azureCount}/{totalCount} using Azure services
            </span>
          )}
        </div>
        {status && (
          <div className="flex items-start gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2">
            <Info size={13} className="text-blue-500 mt-0.5 shrink-0" />
            <p className="text-xs text-blue-800">{status.ai_disclosure}</p>
          </div>
        )}
        {status && (
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded-full bg-white border border-slate-200 px-2.5 py-1 text-slate-700">
              Backend: {status.model_backend}
            </span>
            <span className="rounded-full bg-white border border-slate-200 px-2.5 py-1 text-slate-700">
              Content Safety threshold: {status.content_safety_threshold}
            </span>
          </div>
        )}
      </div>

      {/* Control cards */}
      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Loader2 size={14} className="animate-spin" /> Loading RAI status…
        </div>
      )}
      {status && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
          {status.rai_controls.map((c) => <ControlRow key={c.control} c={c} />)}
        </div>
      )}

      {/* Per-run evaluations (only when a run has completed) */}
      {runId && (
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-700">Run Evaluations</h3>
          <p className="text-xs text-gray-500">
            Run ID: <span className="font-mono text-gray-700">{runId}</span>
          </p>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <GroundednessCard runId={runId} />
            <RubricCard runId={runId} />
          </div>
        </div>
      )}

      {!runId && (
        <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 p-6 text-center text-sm text-gray-400">
          Run a learner workflow to see per-run groundedness and rubric evaluation results.
        </div>
      )}
    </div>
  )
}
