import { useEffect, useRef } from 'react'
import { CheckCircle, Circle, Loader, AlertCircle } from 'lucide-react'
import clsx from 'clsx'
import type { TraceEvent } from '../api/client'

const AGENT_ORDER = [
  'learner_intake',
  'curator',
  'plan_generator',
  'readiness_critic',
  'engagement',
  'assessment',
  'manager_insights',
  'retrospective',
]

const AGENT_LABELS: Record<string, string> = {
  learner_intake: 'Learner Intake',
  curator: 'Learning Path Curator',
  plan_generator: 'Study Plan Generator',
  readiness_critic: 'Readiness Critic',
  engagement: 'Engagement Agent',
  assessment: 'Assessment Agent',
  manager_insights: 'Manager Insights',
  retrospective: 'Retrospective',
  orchestrator: 'Orchestrator',
}

function agentStatus(events: TraceEvent[], name: string): 'idle' | 'running' | 'done' | 'error' {
  const evts = events.filter((e) => e.agent_name === name)
  if (evts.some((e) => e.event_type === 'agent_complete')) return 'done'
  if (evts.some((e) => e.event_type === 'error')) return 'error'
  if (evts.some((e) => e.event_type === 'agent_start')) return 'running'
  return 'idle'
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'done') return <CheckCircle size={16} className="text-green-500" />
  if (status === 'running') return <Loader size={16} className="text-blue-500 animate-spin" />
  if (status === 'error') return <AlertCircle size={16} className="text-rose-400" />
  return <Circle size={16} className="text-gray-300" />
}

interface Props {
  events: TraceEvent[]
  runId?: string
}

function formatEventValue(value: unknown): string {
  if (value == null) return ''
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

export default function ReasoningPanel({ events, runId }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events.length])

  const toolCalls = events.filter((e) => e.event_type === 'tool_call')
  const hitlEvent = events.find((e) => e.event_type === 'hitl_request')
  const latestOutputs = AGENT_ORDER.map((agentName) => {
    const latestEvent = [...events]
      .reverse()
      .find((event) => event.agent_name === agentName && event.event_type === 'agent_complete')

    return {
      agentName,
      event: latestEvent,
      content: latestEvent?.data?.content,
      structuredOutput: latestEvent?.data?.structured_output,
      groundedness: latestEvent?.data?.groundedness,
      warnings: latestEvent?.data?.warnings,
    }
  }).filter((item) => item.event)

  return (
    <div className="h-full flex flex-col bg-gray-900 text-gray-100 rounded-lg overflow-hidden">
      <div className="px-4 py-3 bg-gray-800 border-b border-gray-700 text-sm font-semibold">
        Live Journey Trace {runId && <span className="text-ink-subtle font-mono text-xs ml-2">{runId.slice(0, 8)}</span>}
      </div>

      {/* Agent pipeline status */}
      <div className="px-4 py-3 border-b border-gray-700">
        <div className="flex gap-3 flex-wrap">
          {AGENT_ORDER.map((name) => {
            const status = agentStatus(events, name)
            return (
              <div
                key={name}
                className={clsx(
                  'flex items-center gap-1.5 px-2 py-1 rounded text-xs border transition-all',
                  status === 'done' && 'border-green-600 bg-green-900/30 text-green-300',
                  status === 'running' && 'border-blue-500 bg-blue-900/30 text-blue-300',
                  status === 'error' && 'border-red-500 bg-red-900/30 text-red-300',
                  status === 'idle' && 'border-gray-700 text-ink-muted'
                )}
              >
                <StatusIcon status={status} />
                {AGENT_LABELS[name] ?? name}
              </div>
            )
          })}
        </div>
      </div>

      {latestOutputs.length > 0 && (
        <div className="px-4 py-3 border-b border-gray-700 space-y-2 bg-gray-950/40">
          <div className="text-xs font-semibold uppercase tracking-wide text-ink-subtle">Latest Step Summaries</div>
          <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
            {latestOutputs.map(({ agentName, content, structuredOutput, groundedness, warnings }) => (
              <details key={agentName} className="rounded border border-gray-800 bg-gray-900/70">
                <summary className="cursor-pointer list-none px-3 py-2 text-xs font-medium text-gray-200 flex items-center justify-between">
                  <span>{AGENT_LABELS[agentName] ?? agentName}</span>
                  <span className="text-ink-muted">expand</span>
                </summary>
                <div className="px-3 pb-3 space-y-2 text-xs">
                  {typeof content === 'string' && content.trim() && (
                    <pre className="whitespace-pre-wrap rounded bg-gray-950 p-2 text-gray-200 font-mono">{content}</pre>
                  )}
                  {structuredOutput != null && (
                    <pre className="whitespace-pre-wrap rounded bg-slate-950 p-2 text-sky-200 font-mono">{formatEventValue(structuredOutput)}</pre>
                  )}
                  {groundedness != null && (
                    <div className="text-gray-300">Groundedness: {formatEventValue(groundedness)}</div>
                  )}
                  {Array.isArray(warnings) && warnings.length > 0 && (
                    <div className="text-amber-300">Warnings: {warnings.join(', ')}</div>
                  )}
                </div>
              </details>
            ))}
          </div>
        </div>
      )}

      {/* Event log */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-1 scrollbar-thin text-xs font-mono">
        {events.length === 0 && (
          <p className="text-ink-muted text-center mt-8">Build your plan to see each journey step complete...</p>
        )}
        {events.map((e) => (
          <div key={e.event_id} className={clsx(
            'flex gap-2',
            e.event_type === 'critic_objection' && 'text-red-400',
            e.event_type === 'hitl_request' && 'text-amber-400 font-bold',
            e.event_type === 'tool_call' && 'text-cyan-400',
            e.event_type === 'agent_complete' && 'text-green-400',
          )}>
            <div className="flex-1">
              <div className="flex gap-2">
                <span className="text-ink-muted shrink-0">
                  {new Date(e.timestamp).toLocaleTimeString()}
                </span>
                <span className="text-ink-subtle">[{AGENT_LABELS[e.agent_name] ?? e.agent_name}]</span>
                <span>{e.event_type.replace(/_/g, ' ')}</span>
                {e.data?.tool != null && <span className="text-cyan-300">→ {String(e.data.tool)}</span>}
                {typeof e.data?.message === 'string' && <span className="text-red-300">- {e.data.message}</span>}
              </div>
              {(typeof e.data?.content === 'string' && e.data.content.trim()) && (
                <details className="mt-1 ml-16">
                  <summary className="cursor-pointer text-ink-subtle">view output</summary>
                  <pre className="mt-1 whitespace-pre-wrap rounded bg-gray-950 p-2 text-gray-200 font-mono">{e.data.content}</pre>
                </details>
              )}
              {e.event_type === 'tool_result' && e.data?.result != null && (
                <details className="mt-1 ml-16">
                  <summary className="cursor-pointer text-ink-subtle">view tool result</summary>
                  <pre className="mt-1 whitespace-pre-wrap rounded bg-gray-950 p-2 text-cyan-200 font-mono">{formatEventValue(e.data.result)}</pre>
                </details>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* HITL gate */}
      {hitlEvent && (
        <div className="px-4 py-3 bg-amber-900/40 border-t border-amber-700 text-xs text-amber-200">
          ⏸ Manager approval is required before this study plan is published
        </div>
      )}

      {/* Tool call count */}
      {toolCalls.length > 0 && (
        <div className="px-4 py-2 bg-gray-800 border-t border-gray-700 text-xs text-ink-subtle">
          {toolCalls.length} workflow actions · {events.length} total updates
        </div>
      )}
    </div>
  )
}
