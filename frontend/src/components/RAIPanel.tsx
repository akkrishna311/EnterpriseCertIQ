import { useQuery } from '@tanstack/react-query'
import { ShieldCheck, ShieldAlert, AlertTriangle, CheckCircle2, Loader2, Info } from 'lucide-react'
import { api, type RAIControl, type GroundednessEval, type RubricEval } from '../api/client'

const MODE_BADGE: Record<string, string> = {
  azure_ai_content_safety: 'bg-emerald-500/15 text-emerald-300',
  regex_fallback: 'bg-amber-500/15 text-amber-300',
  azure_ai_evaluation: 'bg-emerald-500/15 text-emerald-300',
  heuristic: 'bg-amber-500/15 text-amber-300',
  domain_aware: 'bg-blue-500/15 text-blue-300',
  pipeline_check: 'bg-blue-500/15 text-blue-300',
  regex_scan: 'bg-blue-500/15 text-blue-300',
  human_in_the_loop: 'bg-violet-500/15 text-violet-300',
  azure_ai_foundry_agent_service: 'bg-emerald-500/15 text-emerald-300',
  custom_orchestrator_local: 'bg-amber-500/15 text-amber-300',
}

function modeLabel(mode: string) {
  return mode.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function ControlRow({ c }: { c: RAIControl }) {
  const badgeClass = MODE_BADGE[c.mode] ?? 'bg-white/10 text-ink-muted'
  const isAzure = c.mode.startsWith('azure')
  return (
    <div className="flex items-start gap-3 rounded-lg border border-line bg-surface-2 p-4">
      <div className="mt-0.5 shrink-0">
        {isAzure
          ? <ShieldCheck size={16} className="text-emerald-300" />
          : <ShieldAlert size={16} className="text-amber-500" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="text-sm font-semibold text-ink">{c.control}</p>
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${badgeClass}`}>
            {modeLabel(c.mode)}
          </span>
        </div>
        <p className="mt-1 text-xs text-ink-muted">{c.detail}</p>
        {c.categories && (
          <div className="mt-2 flex flex-wrap gap-1">
            {c.categories.map((cat) => (
              <span key={cat} className="text-[10px] bg-white/10 text-ink-muted px-1.5 py-0.5 rounded">
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
      <div className="flex items-center gap-2 rounded-lg border border-line bg-surface-2 p-4 text-sm text-ink-muted">
        <Loader2 size={14} className="animate-spin" />
        Evaluating groundedness…
      </div>
    )
  }
  if (error || !data) {
    return (
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-300">
        Groundedness eval unavailable for this run. Run the workflow first.
      </div>
    )
  }

  const pct = Math.round(data.groundedness_score * 100)
  const barColor = pct >= 80 ? 'bg-emerald-500' : pct >= 50 ? 'bg-amber-400' : 'bg-red-400'

  return (
    <div className="rounded-lg border border-line bg-surface-2 p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">Groundedness Score</p>
          <p className="text-xs text-ink-muted mt-0.5">{data.note}</p>
        </div>
        <div className={`text-lg font-bold ${pct >= 80 ? 'text-emerald-300' : pct >= 50 ? 'text-amber-300' : 'text-rose-300'}`}>
          {pct}%
        </div>
      </div>
      <div className="h-2 rounded-full bg-white/10 overflow-hidden">
        <div className={`h-full rounded-full ${barColor} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <div className="grid grid-cols-3 gap-3 text-xs text-center">
        <div className="rounded-lg bg-white/5 border border-line px-2 py-2">
          <p className="text-ink-subtle">Citations found</p>
          <p className="font-semibold text-ink">{data.citation_count}</p>
        </div>
        <div className="rounded-lg bg-white/5 border border-line px-2 py-2">
          <p className="text-ink-subtle">Assertions</p>
          <p className="font-semibold text-ink">{data.assertion_count}</p>
        </div>
        <div className={`rounded-lg border px-2 py-2 ${data.passed ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-amber-500/10 border-amber-500/30'}`}>
          <p className={data.passed ? 'text-emerald-500' : 'text-amber-500'}>Status</p>
          <p className={`font-semibold ${data.passed ? 'text-emerald-300' : 'text-amber-300'}`}>
            {data.passed ? 'Pass' : 'Review'}
          </p>
        </div>
      </div>
      {data.uncited_sample.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-ink-muted mb-1">Uncited assertion samples</p>
          <ul className="space-y-1">
            {data.uncited_sample.map((s, i) => (
              <li key={i} className="text-[11px] text-ink-muted bg-white/5 rounded px-2 py-1 truncate">
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
      <div className="flex items-center gap-2 rounded-lg border border-line bg-surface-2 p-4 text-sm text-ink-muted">
        <Loader2 size={14} className="animate-spin" />
        Running rubric checks…
      </div>
    )
  }
  if (error || !data) {
    return (
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-300">
        Rubric eval unavailable. Run the workflow first.
      </div>
    )
  }

  const agentEntries = Object.entries(data.results)
  const meanPct = Math.round(data.mean_score * 100)

  return (
    <div className="rounded-lg border border-line bg-surface-2 p-4 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">Agent Quality Rubrics</p>
          <p className="text-xs text-ink-muted">
            {agentEntries.length} agents checked · mean score {meanPct}% ·
            threshold {Math.round(data.threshold * 100)}%
          </p>
        </div>
        {data.all_passed
          ? <CheckCircle2 size={18} className="text-emerald-300 shrink-0" />
          : <AlertTriangle size={18} className="text-amber-500 shrink-0" />}
      </div>

      <div className="space-y-3">
        {agentEntries.map(([agent, result]) => (
          <div key={agent} className="space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-ink">{agent.replace(/_/g, ' ')}</span>
              <span className={`font-semibold ${result.passed ? 'text-emerald-300' : 'text-amber-300'}`}>
                {Math.round(result.score * 100)}%
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
              <div
                className={`h-full rounded-full ${result.passed ? 'bg-emerald-400' : 'bg-amber-400'}`}
                style={{ width: `${Math.round(result.score * 100)}%` }}
              />
            </div>
            <div className="grid grid-cols-2 gap-1">
              {result.checks.map((chk) => (
                <div key={chk.id} className="flex items-center gap-1 text-[10px] text-ink-muted">
                  {chk.passed
                    ? <CheckCircle2 size={10} className="text-emerald-500 shrink-0" />
                    : <AlertTriangle size={10} className="text-amber-500 shrink-0" />}
                  <span className={chk.passed ? 'text-ink-muted' : 'text-amber-300 font-medium'}>
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
      <div className="rounded-xl border border-line bg-white/5 p-4 space-y-2">
        <div className="flex items-center gap-2">
          <ShieldCheck size={18} className="text-brand-600" />
          <h2 className="text-sm font-semibold text-ink">Responsible AI Controls</h2>
          {!isLoading && status && (
            <span className="ml-auto text-xs font-medium text-ink-muted">
              {azureCount}/{totalCount} using Azure services
            </span>
          )}
        </div>
        {status && (
          <div className="flex items-start gap-2 rounded-lg border border-blue-500/30 bg-blue-500/10 px-3 py-2">
            <Info size={13} className="text-blue-500 mt-0.5 shrink-0" />
            <p className="text-xs text-blue-300">{status.ai_disclosure}</p>
          </div>
        )}
        {status && (
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded-full bg-surface-2 border border-line px-2.5 py-1 text-ink">
              Backend: {status.model_backend}
            </span>
            <span className="rounded-full bg-surface-2 border border-line px-2.5 py-1 text-ink">
              Content Safety threshold: {status.content_safety_threshold}
            </span>
          </div>
        )}
      </div>

      {/* Control cards */}
      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-ink-muted">
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
          <h3 className="text-sm font-semibold text-ink">Run Evaluations</h3>
          <p className="text-xs text-ink-muted">
            Run ID: <span className="font-mono text-ink">{runId}</span>
          </p>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <GroundednessCard runId={runId} />
            <RubricCard runId={runId} />
          </div>
        </div>
      )}

      {!runId && (
        <div className="rounded-lg border border-dashed border-line bg-white/5 p-6 text-center text-sm text-ink-subtle">
          Run a learner workflow to see per-run groundedness and rubric evaluation results.
        </div>
      )}
    </div>
  )
}
