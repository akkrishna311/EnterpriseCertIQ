import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Play, BookOpen, Target, Zap, ClipboardList, Loader2, CheckCircle2, AlertTriangle, Headphones, ShieldCheck, ExternalLink } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { api, streamEvents, type TraceEvent, type AssessmentResult, type Forecast, type MasteryGrid, type ProgressSnapshot } from '../api/client'
import ReasoningPanel from '../components/ReasoningPanel'
import CriticVsPlanView from '../components/CriticVsPlanView'
import DeviationGraph from '../components/DeviationGraph'
import AssessmentHistoryChart from '../components/AssessmentHistoryChart'
import DomainMasteryChart from '../components/DomainMasteryChart'
import ServiceHeatmap from '../components/ServiceHeatmap'
import PassThresholdGauge from '../components/PassThresholdGauge'
import TrustSafetyPanel from '../components/TrustSafetyPanel'
import AIDisclosureBanner from '../components/AIDisclosureBanner'
import StudyPlanView, { type StudyPlan } from '../components/StudyPlanView'
import AudioBriefing from '../components/AudioBriefing'
import RAIPanel from '../components/RAIPanel'

// The critic runs in a self-correction loop: each round emits one
// critic_objection event carrying that round's COMPLETE objection list against
// the current plan. We only ever want the latest round's snapshot — accumulating
// across rounds produced duplicate cards (same O1–O4 reworded each round).
function latestObjectionsFromEvents(events: TraceEvent[]): any[] {
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i] as any
    if ((e.event_type ?? e.type) === 'critic_objection') {
      return (e.data?.objections as any[]) ?? []
    }
  }
  return []
}

type TabKey = 'reasoning' | 'plan' | 'critic' | 'progress' | 'readiness' | 'assessment' | 'audio' | 'safety'

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: 'reasoning', label: 'Journey Trace', icon: <Zap size={14} /> },
  { key: 'plan', label: 'Study Plan', icon: <ClipboardList size={14} /> },
  { key: 'critic', label: 'Plan Review', icon: <Target size={14} /> },
  { key: 'progress', label: 'Progress', icon: <BookOpen size={14} /> },
  { key: 'readiness', label: 'Exam Readiness', icon: <Target size={14} /> },
  { key: 'assessment', label: 'Practice Exam', icon: <BookOpen size={14} /> },
  { key: 'audio', label: 'Audio Briefing', icon: <Headphones size={14} /> },
  { key: 'safety', label: 'Safety & RAI', icon: <ShieldCheck size={14} /> },
]

const DIFFICULTIES = ['Mixed', 'Easy', 'Medium', 'Hard'] as const
type Difficulty = typeof DIFFICULTIES[number]

const DIFF_BADGE: Record<string, string> = {
  Easy: 'bg-emerald-500/15 text-emerald-300',
  Medium: 'bg-amber-500/15 text-amber-300',
  Hard: 'bg-rose-500/15 text-rose-300',
}

export default function LearnerView() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedLearner, setSelectedLearner] = useState(searchParams.get('learner') ?? 'L-1004')
  const [runId, setRunId] = useState<string | undefined>(searchParams.get('runId') ?? undefined)
  const [running, setRunning] = useState(false)
  const [events, setEvents] = useState<TraceEvent[]>([])
  const [activeTab, setActiveTab] = useState<TabKey>((searchParams.get('tab') as TabKey) ?? 'reasoning')
  const [planId, setPlanId] = useState<string | undefined>(searchParams.get('planId') ?? undefined)
  const [planData, setPlanData] = useState<StudyPlan>()
  const [planApproved, setPlanApproved] = useState(false)
  const [objections, setObjections] = useState<any[]>([])
  const [progressSeries, setProgressSeries] = useState<any[]>([])
  const [readiness, setReadiness] = useState<any>()
  const [assessment, setAssessment] = useState<any>(null)
  const [difficulty, setDifficulty] = useState<Difficulty>('Mixed')
  const [generating, setGenerating] = useState(false)
  const [answers, setAnswers] = useState<Record<string, number>>({})
  const [examResult, setExamResult] = useState<AssessmentResult | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [actionError, setActionError] = useState<string>()
  const [foundryThreadUrl, setFoundryThreadUrl] = useState<string>()

  const { data: learners = [] } = useQuery({ queryKey: ['learners'], queryFn: api.learners })
  const learner = learners.find((l) => l.learner_id === selectedLearner)

  const { data: mastery, refetch: refetchMastery, isLoading: masteryLoading, isFetching: masteryFetching } = useQuery<MasteryGrid>({
    queryKey: ['mastery', selectedLearner, learner?.cert_target],
    queryFn: () => api.mastery(selectedLearner, learner!.cert_target),
    enabled: !!learner,
  })
  const { data: forecast, refetch: refetchForecast, isLoading: forecastLoading, isFetching: forecastFetching } = useQuery<Forecast>({
    queryKey: ['forecast', selectedLearner, learner?.cert_target],
    queryFn: () => api.forecast(selectedLearner, learner!.cert_target),
    enabled: !!learner,
  })
  const { data: progressData, refetch: refetchProgress, isLoading: progressLoading, isFetching: progressFetching } = useQuery<ProgressSnapshot>({
    queryKey: ['progress', selectedLearner, learner?.cert_target],
    queryFn: () => api.progress(selectedLearner, learner!.cert_target),
    enabled: !!learner,
  })

  // URL → state: only fires when the URL actually changes (e.g. browser back/forward).
  useEffect(() => {
    const learnerParam = searchParams.get('learner')
    const tabParam = searchParams.get('tab') as TabKey | null
    const planIdParam = searchParams.get('planId') ?? undefined
    const runIdParam = searchParams.get('runId') ?? undefined
    if (learnerParam) setSelectedLearner(learnerParam)
    if (tabParam && TABS.some((tab) => tab.key === tabParam)) setActiveTab(tabParam)
    if (planIdParam) setPlanId(planIdParam)
    if (runIdParam) setRunId(runIdParam)
  }, [searchParams]) // eslint-disable-line react-hooks/exhaustive-deps

  // State → URL: persist learner, tab, planId and runId so navigation away and back restores state.
  useEffect(() => {
    const params: Record<string, string> = { learner: selectedLearner, tab: activeTab }
    if (planId) params.planId = planId
    if (runId) params.runId = runId
    setSearchParams(params, { replace: true })
  }, [activeTab, selectedLearner, planId, runId, setSearchParams])

  // Restore plan from backend when planId is in the URL but planData is not loaded.
  useEffect(() => {
    if (!planId || planData) return
    api.getPlan(planId).then((plan) => {
      if ((plan as any).learner_id !== selectedLearner) {
        setPlanId(undefined)
        return
      }
      setPlanData(plan as unknown as StudyPlan)
      if ((plan as any).status === 'approved') setPlanApproved(true)
    }).catch(() => setPlanId(undefined))
  }, [planId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Restore trace events: if runId is known, fetch that trace directly.
  // If runId is absent (e.g. navigated via Manager "Review Plan" link) fall back
  // to the most-recent trace for this learner so the Journey Trace tab isn't blank.
  useEffect(() => {
    if (events.length > 0) return
    if (runId) {
      api.getTrace(runId).then((trace) => {
        if (trace.events?.length) {
          setEvents(trace.events)
          setObjections(latestObjectionsFromEvents(trace.events))
        }
      }).catch(() => { /* trace not ready — ignore */ })
    } else if (planId) {
      api.listTraces(selectedLearner).then((traces) => {
        const latest = traces[0]
        if (latest?.run_id) {
          setRunId(latest.run_id)
          if (latest.events?.length) {
            setEvents(latest.events)
            setObjections(latestObjectionsFromEvents(latest.events))
          }
        }
      }).catch(() => { /* ignore */ })
    }
  }, [runId, planId]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleRun() {
    if (!learner) return
    setRunning(true)
    setActionError(undefined)
    setEvents([]); setObjections([]); setProgressSeries([]); setReadiness(undefined)
    setPlanId(undefined); setPlanData(undefined); setPlanApproved(false); setFoundryThreadUrl(undefined)
    setActiveTab('reasoning')

    try {
      const { run_id } = await api.runWorkflow(selectedLearner)
      setRunId(run_id)

      const stop = streamEvents(run_id, (evt: any) => {
        const eventType = evt.event_type ?? evt.type

        if (evt.event_id && evt.event_type) {
          setEvents((prev) => [...prev, evt])
        }
        if (eventType === 'critic_objection') {
          // Each critic round emits a complete snapshot — replace, don't accumulate.
          setObjections(evt.data?.objections ?? [])
        }
        if (eventType === 'tool_result' && evt.data?.tool === 'generate_study_plan') {
          const result = evt.data?.result
          if (result?.plan_id) {
            setPlanId(result.plan_id)
            setPlanData(result)
          }
        }
        if (eventType === 'tool_result' && evt.data?.tool === 'compute_progress_series') {
          setProgressSeries(evt.data?.result?.series ?? [])
        }
        if (eventType === 'readiness_advance' || eventType === 'readiness_loopback') {
          setReadiness({ kind: eventType, ...evt.data })
        }
        if (eventType === 'workflow_error') {
          setEvents((prev) => [...prev, {
            event_id: `${run_id}-workflow-error`, run_id,
            timestamp: new Date().toISOString(), event_type: 'error',
            agent_name: 'orchestrator', data: { message: evt.error ?? 'Workflow failed' },
          }])
        }

        // IMPORTANT: only the SSE *sentinel* (which has `type` but no `event_id`)
        // terminates the stream. The orchestrator's workflow_complete *trace event*
        // (has event_id) arrives before the progress series is broadcast, so closing
        // on it would drop the Progress data.
        const isSentinel = !evt.event_id && (evt.type === 'workflow_complete' || evt.type === 'workflow_error')
        if (isSentinel) {
          if (evt.foundry_thread_url) setFoundryThreadUrl(evt.foundry_thread_url)
          setRunning(false)
          stop()
          refetchMastery()
          refetchForecast()
          refetchProgress()
          if (evt.type === 'workflow_error') {
            setActionError(evt.error ?? 'Workflow failed before completion.')
          }
        }
      })
    } catch (e) {
      setRunning(false)
      setActionError(e instanceof Error ? e.message : 'Failed to start workflow')
      setEvents([{
        event_id: `${Date.now()}-run-error`, run_id: runId ?? 'pending',
        timestamp: new Date().toISOString(), event_type: 'error',
        agent_name: 'orchestrator', data: { message: e instanceof Error ? e.message : 'Failed to start workflow' },
      }])
    }
  }

  async function handleGenerateAssessment() {
    if (!learner) return
    setGenerating(true)
    setActionError(undefined)
    setExamResult(null)
    setAnswers({})
    try {
      const result = await api.generateAssessment(selectedLearner, learner.cert_target, difficulty)
      setAssessment(result)
      setActiveTab('assessment')
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Failed to generate mock exam')
    } finally {
      setGenerating(false)
    }
  }

  async function handleSubmitExam() {
    if (!assessment || !learner) return
    setSubmitting(true)
    setActionError(undefined)
    try {
      const result = await api.submitAssessment({
        assessment_id: assessment.assessment_id,
        learner_id: selectedLearner,
        cert_id: learner.cert_target,
        answers,
      })
      setExamResult(result)
      setReadiness({
        kind: result.passed ? 'readiness_advance' : 'readiness_loopback',
        verdict: result.passed ? 'ready' : 'not_ready',
        estimated_exam_score: result.forecast?.estimated_exam_score ?? result.estimated_exam_score,
        pass_threshold: result.pass_threshold,
        weak_area: result.forecast?.weakest_topic,
        next_step: result.passed ? 'Plan approved and assessment passed. Learner can continue with the next certification target.' : undefined,
        message: result.passed
          ? `Assessment passed (${result.estimated_exam_score}/${result.pass_threshold}). Readiness updated from latest exam evidence.`
          : `Assessment below threshold (${result.estimated_exam_score}/${result.pass_threshold}). Continue remediation on ${result.forecast?.weakest_topic ?? 'the weakest area'}.`,
      })
      setActiveTab('readiness')
      await refetchForecast()
      await refetchMastery()
      await refetchProgress()
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Failed to submit mock exam')
    } finally {
      setSubmitting(false)
    }
  }

  const totalQ = assessment?.questions?.length ?? 0
  const answeredQ = Object.keys(answers).length
  const resolvedProgressSeries = progressData?.series?.length ? progressData.series : progressSeries
  const assessmentAttempts = progressData?.attempts ?? []
  const assessmentForecast = examResult?.forecast ?? forecast
  const latestAttempt = assessmentAttempts[assessmentAttempts.length - 1]
  const readinessScore = assessmentForecast?.estimated_exam_score
  const readinessGap = assessmentForecast ? Math.max(0, assessmentForecast.pass_threshold - assessmentForecast.estimated_exam_score) : undefined
  const weakestTopic = assessmentForecast?.weakest_topic?.replace(/_/g, ' ')
  const readinessBusy = masteryLoading || forecastLoading
  const readinessRefreshing = masteryFetching || forecastFetching
  const progressBusy = progressLoading
  const progressRefreshing = progressFetching

  const nextStep = (() => {
    if (running) {
      return {
        title: 'Workflow is running',
        detail: 'Stay on the journey trace to watch each planning step complete before reviewing the study plan.',
        actionLabel: 'Open Journey Trace',
        action: () => setActiveTab('reasoning' as TabKey),
      }
    }
    if (planId && !planApproved) {
      return {
        title: 'Review the draft plan',
        detail: 'The workflow has produced a study plan. Approve it before treating the path as publishable.',
        actionLabel: 'Open Study Plan',
        action: () => setActiveTab('plan' as TabKey),
      }
    }
    if (!assessmentAttempts.length) {
      return {
        title: 'Generate a first mock exam',
        detail: 'You have no scored assessment yet, so readiness is still based on limited evidence.',
        actionLabel: 'Open Practice Exam',
        action: () => setActiveTab('assessment' as TabKey),
      }
    }
    if (examResult && !examResult.passed) {
      return {
        title: 'Close the weakest gap first',
        detail: `Review ${weakestTopic ?? 'the weakest topic'} in readiness, then retake the mock exam.`,
        actionLabel: 'Open Exam Readiness',
        action: () => setActiveTab('readiness' as TabKey),
      }
    }
    if (readinessGap && readinessGap > 0) {
      return {
        title: 'Keep remediating before advancing',
        detail: `${readinessGap} points remain to threshold. Use the progress and readiness tabs to target the next study block.`,
        actionLabel: 'Open Progress',
        action: () => setActiveTab('progress' as TabKey),
      }
    }
    if (assessmentForecast && readinessGap === 0) {
      return {
        title: 'You are ready to advance',
        detail: 'Latest evidence is at or above threshold. Confirm the readiness view, then move to the next certification milestone.',
        actionLabel: 'Open Exam Readiness',
        action: () => setActiveTab('readiness' as TabKey),
      }
    }
    return {
      title: 'Run the learner workflow',
      detail: 'Start with the reasoning workflow to produce a plan, critic output, and readiness baseline.',
        actionLabel: 'Open Journey Trace',
      action: () => setActiveTab('reasoning' as TabKey),
    }
  })()

  return (
    <div className="flex h-[calc(100vh-52px)] bg-white/5">
      {/* Left sidebar */}
      <aside className="w-64 shrink-0 border-r border-line bg-surface-2 flex flex-col">
        <div className="p-4 border-b border-line">
          <h2 className="text-sm font-semibold text-ink mb-3">Select Learner</h2>
          <select
            value={selectedLearner}
            onChange={(e) => {
              setSelectedLearner(e.target.value)
              setEvents([]); setRunId(undefined); setPlanId(undefined); setPlanData(undefined)
              setPlanApproved(false); setObjections([])
              setProgressSeries([]); setAssessment(null); setExamResult(null); setReadiness(undefined)
              setActionError(undefined); setAnswers({})
            }}
            className="field-dark w-full"
          >
            {learners.map((l) => (
              <option key={l.learner_id} value={l.learner_id}>{l.learner_id} — {l.role}</option>
            ))}
          </select>
        </div>

        {learner && (
          <div className="p-4 space-y-1.5 text-xs text-ink-muted border-b border-line">
            <p><span className="text-ink-subtle">Role</span> · {learner.role}</p>
            <p><span className="text-ink-subtle">Cert</span> · <span className="font-semibold text-ink">{learner.cert_target}</span></p>
            <p><span className="text-ink-subtle">Team</span> · {learner.team_id}</p>
            <p><span className="text-ink-subtle">Deadline</span> · {learner.deadline}</p>
          </div>
        )}

        <div className="p-4 border-b border-line space-y-3 bg-white/5/80">
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Current Signal</h3>
            <p className="mt-1 text-sm font-semibold text-ink">
              {readinessScore ? `${readinessScore} / ${assessmentForecast?.pass_threshold ?? 0}` : 'No readiness signal yet'}
            </p>
            <p className="text-xs text-ink-muted">
              {assessmentForecast
                ? readinessGap === 0
                  ? 'At or above pass threshold based on latest evidence.'
                  : `${readinessGap} points below current threshold.`
                : 'Run workflow or complete a mock exam to populate readiness.'}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="rounded-md border border-line bg-surface-2 px-2.5 py-2">
              <p className="text-ink-subtle">Latest mock</p>
              <p className="font-semibold text-ink">{latestAttempt ? `${latestAttempt.score_pct}%` : 'No attempts'}</p>
            </div>
            <div className="rounded-md border border-line bg-surface-2 px-2.5 py-2">
              <p className="text-ink-subtle">Attempts</p>
              <p className="font-semibold text-ink">{assessmentAttempts.length}</p>
            </div>
          </div>
          <div className="rounded-md border border-line bg-surface-2 px-2.5 py-2 text-xs">
            <p className="text-ink-subtle">Weakest topic</p>
            <p className="font-medium text-ink">{weakestTopic || 'Need more evidence'}</p>
          </div>
          <div className="rounded-md border border-blue-500/30 bg-blue-500/10 px-3 py-3 text-xs space-y-2">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-blue-300">Suggested next step</p>
              <p className="mt-1 font-semibold text-ink">{nextStep.title}</p>
              <p className="mt-1 text-ink-muted">{nextStep.detail}</p>
            </div>
            <button
              type="button"
              onClick={nextStep.action}
              className="w-full rounded-md bg-surface-2 px-2.5 py-2 text-xs font-medium text-blue-300 border border-blue-500/30 hover:bg-blue-500/15 transition"
            >
              {nextStep.actionLabel}
            </button>
          </div>
        </div>

        <div className="p-4 space-y-3">
          <button
            onClick={handleRun}
            disabled={running || !learner}
            className="w-full flex items-center justify-center gap-2 bg-brand-600 hover:bg-brand-700 text-white text-sm px-3 py-2 rounded-md font-medium disabled:opacity-50 transition"
          >
            {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            {running ? 'Building plan…' : 'Build My Plan'}
          </button>

          {foundryThreadUrl && (
            <a
              href={foundryThreadUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="w-full flex items-center justify-center gap-2 bg-surface-2 border border-accent text-blue-300 text-xs px-3 py-2 rounded-md font-medium hover:bg-blue-500/10 transition"
            >
              <ExternalLink size={12} />
              View run in Foundry portal
            </a>
          )}

          {/* Mock exam controls */}
          <div className="pt-2 border-t border-line space-y-2">
            <label className="text-xs font-semibold text-ink-muted uppercase tracking-wide">Practice Exam Difficulty</label>
            <div className="grid grid-cols-2 gap-1.5">
              {DIFFICULTIES.map((d) => (
                <button
                  key={d}
                  onClick={() => setDifficulty(d)}
                  className={`text-xs py-1.5 rounded-md border transition ${
                    difficulty === d
                      ? 'bg-brand-600 text-white border-brand-600'
                      : 'bg-surface-2 text-ink-muted border-line-strong hover:border-brand-400'
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
            <button
              onClick={handleGenerateAssessment}
              disabled={!learner || generating}
              className="w-full flex items-center justify-center gap-2 bg-gray-800 hover:bg-gray-900 text-white text-sm px-3 py-2 rounded-md font-medium disabled:opacity-50 transition"
            >
              {generating ? <Loader2 size={14} className="animate-spin" /> : <BookOpen size={14} />}
              {generating ? 'Generating…' : `Generate ${difficulty} Practice Exam`}
            </button>
          </div>
        </div>

        {planId && (
          <div className="mt-auto p-4 border-t border-line">
            <button
              onClick={() => setActiveTab('plan')}
              className={`w-full flex items-center justify-center gap-2 text-sm px-3 py-2 rounded-md font-medium transition ${
                planApproved
                  ? 'bg-green-50 text-emerald-300 border border-green-200'
                  : 'bg-amber-500/10 text-amber-300 border border-amber-500/40 hover:bg-amber-500/15'
              }`}
            >
              {planApproved ? <CheckCircle2 size={14} /> : <ClipboardList size={14} />}
              {planApproved ? 'Plan Approved' : 'Review Study Plan'}
            </button>
          </div>
        )}
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex border-b border-line bg-surface-2 px-4 overflow-x-auto">
          {TABS.map((t) => {
            const badge = t.key === 'critic' && objections.length > 0 ? objections.length
              : t.key === 'plan' && planId && !planApproved ? '!' : undefined
            return (
              <button
                key={t.key}
                onClick={() => setActiveTab(t.key)}
                className={`relative flex items-center gap-1.5 px-4 py-3 text-sm font-medium border-b-2 transition whitespace-nowrap ${
                  activeTab === t.key
                    ? 'border-brand-600 text-brand-600'
                    : 'border-transparent text-ink-muted hover:text-ink'
                }`}
              >
                {t.icon}
                {t.label}
                {badge !== undefined && (
                  <span className="ml-1 text-[10px] font-bold bg-amber-500 text-white rounded-full min-w-[16px] h-4 px-1 flex items-center justify-center">
                    {badge}
                  </span>
                )}
              </button>
            )
          })}
        </div>

        <div className="flex-1 overflow-auto p-4">
          <AIDisclosureBanner />

          {actionError && (
            <div className="mt-3 flex items-start gap-3 rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
              <AlertTriangle size={16} className="mt-0.5 shrink-0" />
              <div>
                <p className="font-medium">Action failed</p>
                <p className="text-rose-300">{actionError}</p>
              </div>
            </div>
          )}

          {activeTab === 'reasoning' && (
            <div className="h-[calc(100%-40px)] mt-3">
              <ReasoningPanel events={events} runId={runId} />
            </div>
          )}

          {activeTab === 'plan' && (
            <div className="mt-3">
              <StudyPlanView plan={planData} approved={planApproved} onApproved={() => setPlanApproved(true)} canApprove={false} />
            </div>
          )}

          {activeTab === 'critic' && (
            <div className="mt-3"><CriticVsPlanView objections={objections} /></div>
          )}

          {activeTab === 'progress' && (
            <div className="mt-3 space-y-4">
              {progressRefreshing && (
                <div className="flex items-center gap-2 rounded-lg border border-blue-500/30 bg-blue-500/10 px-4 py-3 text-sm text-blue-300">
                  <Loader2 size={14} className="animate-spin" />
                  Refreshing progress from the latest plan and exam evidence.
                </div>
              )}
              {progressBusy && !resolvedProgressSeries.length && !assessmentAttempts.length ? (
                <div className="bg-surface-2 rounded-lg border border-line p-6 flex items-center gap-3 text-sm text-ink-muted">
                  <Loader2 size={16} className="animate-spin" />
                  Loading progress and assessment history…
                </div>
              ) : (
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                  <div className="bg-surface-2 rounded-lg border border-line p-4">
                    <DeviationGraph series={resolvedProgressSeries} />
                  </div>
                  <div className="bg-surface-2 rounded-lg border border-line p-4">
                    <AssessmentHistoryChart attempts={assessmentAttempts} />
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'audio' && learner && (
            <div className="mt-3">
              <AudioBriefing key={`${selectedLearner}:${learner.cert_target}`}
                learnerId={selectedLearner} certId={learner.cert_target} />
            </div>
          )}

          {activeTab === 'safety' && (
            <div className="mt-3">
              <RAIPanel runId={runId} />
            </div>
          )}

          {activeTab === 'readiness' && (
            <div className="mt-3 space-y-4">
            {readinessRefreshing && (
              <div className="flex items-center gap-2 rounded-lg border border-blue-500/30 bg-blue-500/10 px-4 py-3 text-sm text-blue-300">
                <Loader2 size={14} className="animate-spin" />
                Refreshing forecast and mastery from the latest evidence.
              </div>
            )}
            {readiness && (
              <div className={`rounded-lg border p-4 ${
                readiness.kind === 'readiness_advance'
                  ? 'bg-green-50 border-green-200'
                  : 'bg-amber-500/10 border-amber-500/40'
              }`}>
                <div className="flex items-center gap-2 text-sm font-semibold mb-1">
                  <Target size={15} className={readiness.kind === 'readiness_advance' ? 'text-emerald-300' : 'text-amber-300'} />
                  <span className={readiness.kind === 'readiness_advance' ? 'text-green-800' : 'text-amber-300'}>
                    Readiness decision: {readiness.verdict === 'ready' ? 'READY — advance' : readiness.verdict === 'not_ready' ? 'NOT READY — continue prep' : 'Insufficient evidence'}
                  </span>
                </div>
                <p className="text-xs text-ink">{readiness.message}</p>
                {readiness.next_step && <p className="text-xs text-ink-muted mt-1"><strong>Next step:</strong> {readiness.next_step}</p>}
              </div>
            )}
            {readinessBusy && !forecast && !mastery ? (
              <div className="bg-surface-2 rounded-lg border border-line p-6 flex items-center gap-3 text-sm text-ink-muted">
                <Loader2 size={16} className="animate-spin" />
                Loading readiness forecast and mastery breakdown…
              </div>
            ) : (
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                <div className="bg-surface-2 rounded-lg border border-line p-4">
                  <h3 className="text-sm font-semibold text-ink mb-3">Exam Readiness Forecast</h3>
                  {forecast ? <PassThresholdGauge forecast={forecast} /> : <p className="text-ink-subtle text-sm">Run a workflow first.</p>}
                </div>
                <div className="bg-surface-2 rounded-lg border border-line p-4">
                  <h3 className="text-sm font-semibold text-ink mb-3">Domain Mastery Breakdown</h3>
                  {mastery ? <DomainMasteryChart domains={mastery.domains} passThreshold={mastery.pass_threshold} /> : <p className="text-ink-subtle text-sm">Run a workflow first.</p>}
                </div>
                <div className="bg-surface-2 rounded-lg border border-line p-4 xl:col-span-2">
                  <h3 className="text-sm font-semibold text-ink mb-3">Service Confidence Heatmap</h3>
                  {mastery ? <ServiceHeatmap domains={mastery.domains} /> : <p className="text-ink-subtle text-sm">Run a workflow first.</p>}
                </div>
                <div className="xl:col-span-2">
                  <h3 className="text-sm font-semibold text-ink mb-2">Trust &amp; Safety</h3>
                  <TrustSafetyPanel />
                </div>
              </div>
            )}
            </div>
          )}

          {activeTab === 'assessment' && (
            <div className="mt-3 max-w-3xl space-y-4">
              {!assessment && (
                <div className="flex flex-col items-center justify-center h-64 bg-white/5 rounded-lg border border-dashed border-line-strong text-ink-subtle">
                  <BookOpen size={28} className="mb-2 opacity-50" />
                  <p className="text-sm">Pick a difficulty and click "Generate Practice Exam" in the sidebar.</p>
                </div>
              )}
              {assessment && !examResult && (
                <>
                  <div className="sticky top-0 bg-white/5 py-2 flex items-center justify-between border-b border-line z-10">
                    <div>
                      <h3 className="font-semibold text-ink">{assessment.cert_id} — Practice Exam</h3>
                      <p className="text-xs text-ink-muted">
                        {totalQ} questions · {assessment.time_limit_minutes} min · answered {answeredQ}/{totalQ}
                      </p>
                    </div>
                    <button
                      onClick={handleSubmitExam}
                      disabled={submitting || answeredQ < totalQ}
                      className="bg-brand-600 hover:bg-brand-700 text-white text-sm px-4 py-1.5 rounded-md disabled:opacity-50 flex items-center gap-1.5"
                    >
                      {submitting && <Loader2 size={13} className="animate-spin" />}
                      Submit ({answeredQ}/{totalQ})
                    </button>
                  </div>
                  <div className="space-y-4">
                    {answeredQ < totalQ && (
                      <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
                        Answer all {totalQ} questions before submitting. Current progress: {answeredQ}/{totalQ}.
                      </div>
                    )}
                    {assessment.questions.map((q: any, idx: number) => (
                      <div key={q.question_id} className="bg-surface-2 border border-line rounded-lg p-4 space-y-2">
                        <div className="flex items-start justify-between gap-3">
                          <p className="text-sm font-medium">{idx + 1}. {q.question_text}</p>
                          {q.difficulty && (
                            <span className={`shrink-0 text-[10px] font-semibold px-2 py-0.5 rounded-full ${DIFF_BADGE[q.difficulty] ?? 'bg-white/10 text-ink-muted'}`}>
                              {q.difficulty}
                            </span>
                          )}
                        </div>
                        <div className="space-y-1">
                          {q.options.map((opt: string, oi: number) => (
                            <label key={oi} className={`flex items-center gap-2 text-sm cursor-pointer rounded px-2 py-1 transition ${answers[q.question_id] === oi ? 'bg-accent/15 border border-accent/40' : 'hover:bg-white/5'}`}>
                              <input
                                type="radio" name={q.question_id} value={oi}
                                checked={answers[q.question_id] === oi}
                                onChange={() => setAnswers((a) => ({ ...a, [q.question_id]: oi }))}
                              />
                              {opt}
                            </label>
                          ))}
                        </div>
                        <p className="text-xs text-ink-subtle">{q.domain}{q.sub_topic ? ` · ${q.sub_topic}` : ''}</p>
                      </div>
                    ))}
                  </div>
                </>
              )}
              {examResult && (
                <div className="bg-surface-2 border rounded-lg p-6 space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="font-semibold text-lg">Assessment Result</h3>
                    {examResult.booking_verdict && (() => {
                      const v = examResult.booking_verdict
                      const style = v === 'GO'
                        ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40'
                        : v === 'CONDITIONAL_GO'
                          ? 'bg-amber-500/15 text-amber-300 border-amber-500/40'
                          : 'bg-rose-500/15 text-rose-300 border-rose-500/40'
                      const label = v === 'GO' ? 'GO — book the exam'
                        : v === 'CONDITIONAL_GO' ? 'CONDITIONAL GO — close, keep prepping'
                        : 'NOT YET — keep preparing'
                      return (
                        <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${style}`}>
                          <span className="text-[13px]">{v === 'GO' ? '✓' : v === 'CONDITIONAL_GO' ? '◐' : '✗'}</span>
                          {label}
                        </span>
                      )
                    })()}
                  </div>
                  <div className={`text-3xl font-bold ${examResult.passed ? 'text-emerald-300' : 'text-rose-400'}`}>
                    {examResult.passed ? '✓ PASS' : '✗ FAIL'}
                  </div>
                  <p className="text-ink-muted">
                    Score: <strong>{examResult.score_pct}%</strong> ·
                    {' '}Estimated exam score: <strong>{examResult.estimated_exam_score} / 1000</strong> ·
                    {' '}Scored <strong>{examResult.questions_scored}</strong> questions
                  </p>
                  {assessmentForecast && <PassThresholdGauge forecast={assessmentForecast} />}
                  <button
                    onClick={() => { setExamResult(null); setAnswers({}); setActiveTab('assessment'); setActionError(undefined) }}
                    className="text-sm text-brand-600 hover:underline"
                  >
                    ← Retake or review questions
                  </button>
                  <AIDisclosureBanner message="AI-generated assessment result; not an official exam score." />
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
