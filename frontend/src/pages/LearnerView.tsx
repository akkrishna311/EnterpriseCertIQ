import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Play, BookOpen, Target, Zap, ClipboardList, Loader2, CheckCircle2 } from 'lucide-react'
import { api, streamEvents, type TraceEvent, type Forecast, type MasteryGrid } from '../api/client'
import ReasoningPanel from '../components/ReasoningPanel'
import CriticVsPlanView from '../components/CriticVsPlanView'
import DeviationGraph from '../components/DeviationGraph'
import DomainMasteryChart from '../components/DomainMasteryChart'
import ServiceHeatmap from '../components/ServiceHeatmap'
import PassThresholdGauge from '../components/PassThresholdGauge'
import AIDisclosureBanner from '../components/AIDisclosureBanner'
import StudyPlanView, { type StudyPlan } from '../components/StudyPlanView'

function mergeObjections(existing: any[], incoming: any[]): any[] {
  const merged = [...existing]
  for (const objection of incoming) {
    const key = `${objection?.objection_id ?? 'unknown'}|${objection?.description ?? ''}|${objection?.recommendation ?? ''}`
    const currentIndex = merged.findIndex((item) => (
      `${item?.objection_id ?? 'unknown'}|${item?.description ?? ''}|${item?.recommendation ?? ''}` === key
    ))
    if (currentIndex >= 0) {
      merged[currentIndex] = { ...merged[currentIndex], ...objection }
      continue
    }
    merged.push(objection)
  }
  return merged
}

type TabKey = 'reasoning' | 'plan' | 'critic' | 'progress' | 'readiness' | 'assessment'

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: 'reasoning', label: 'Reasoning', icon: <Zap size={14} /> },
  { key: 'plan', label: 'Study Plan', icon: <ClipboardList size={14} /> },
  { key: 'critic', label: 'Critic vs Plan', icon: <Target size={14} /> },
  { key: 'progress', label: 'Progress', icon: <BookOpen size={14} /> },
  { key: 'readiness', label: 'Readiness', icon: <Target size={14} /> },
  { key: 'assessment', label: 'Mock Exam', icon: <BookOpen size={14} /> },
]

const DIFFICULTIES = ['Mixed', 'Easy', 'Medium', 'Hard'] as const
type Difficulty = typeof DIFFICULTIES[number]

const DIFF_BADGE: Record<string, string> = {
  Easy: 'bg-green-100 text-green-700',
  Medium: 'bg-amber-100 text-amber-700',
  Hard: 'bg-red-100 text-red-700',
}

export default function LearnerView() {
  const [selectedLearner, setSelectedLearner] = useState('L-1004')
  const [runId, setRunId] = useState<string>()
  const [running, setRunning] = useState(false)
  const [events, setEvents] = useState<TraceEvent[]>([])
  const [activeTab, setActiveTab] = useState<TabKey>('reasoning')
  const [planId, setPlanId] = useState<string>()
  const [planData, setPlanData] = useState<StudyPlan>()
  const [planApproved, setPlanApproved] = useState(false)
  const [objections, setObjections] = useState<any[]>([])
  const [progressSeries, setProgressSeries] = useState<any[]>([])
  const [readiness, setReadiness] = useState<any>()
  const [assessment, setAssessment] = useState<any>(null)
  const [difficulty, setDifficulty] = useState<Difficulty>('Mixed')
  const [generating, setGenerating] = useState(false)
  const [answers, setAnswers] = useState<Record<string, number>>({})
  const [examResult, setExamResult] = useState<any>(null)
  const [submitting, setSubmitting] = useState(false)

  const { data: learners = [] } = useQuery({ queryKey: ['learners'], queryFn: api.learners })
  const learner = learners.find((l) => l.learner_id === selectedLearner)

  const { data: mastery, refetch: refetchMastery } = useQuery<MasteryGrid>({
    queryKey: ['mastery', selectedLearner, learner?.cert_target],
    queryFn: () => api.mastery(selectedLearner, learner!.cert_target),
    enabled: !!learner,
  })
  const { data: forecast, refetch: refetchForecast } = useQuery<Forecast>({
    queryKey: ['forecast', selectedLearner, learner?.cert_target],
    queryFn: () => api.forecast(selectedLearner, learner!.cert_target),
    enabled: !!learner,
  })

  async function handleRun() {
    if (!learner) return
    setRunning(true)
    setEvents([]); setObjections([]); setProgressSeries([]); setReadiness(undefined)
    setPlanId(undefined); setPlanData(undefined); setPlanApproved(false)
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
          setObjections((prev) => mergeObjections(prev, evt.data?.objections ?? []))
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
          setRunning(false)
          stop()
          refetchMastery()
          refetchForecast()
        }
      })
    } catch (e) {
      setRunning(false)
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
    setExamResult(null)
    setAnswers({})
    try {
      const result = await api.generateAssessment(selectedLearner, learner.cert_target, difficulty)
      setAssessment(result)
      setActiveTab('assessment')
    } finally {
      setGenerating(false)
    }
  }

  async function handleSubmitExam() {
    if (!assessment || !learner) return
    setSubmitting(true)
    try {
      const r = await fetch('/api/assessment/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          assessment_id: assessment.assessment_id,
          learner_id: selectedLearner,
          cert_id: learner.cert_target,
          answers,
        }),
      })
      setExamResult(await r.json())
    } finally {
      setSubmitting(false)
    }
  }

  const totalQ = assessment?.questions?.length ?? 0
  const answeredQ = Object.keys(answers).length

  return (
    <div className="flex h-[calc(100vh-52px)] bg-gray-50">
      {/* Left sidebar */}
      <aside className="w-64 shrink-0 border-r border-gray-200 bg-white flex flex-col">
        <div className="p-4 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Select Learner</h2>
          <select
            value={selectedLearner}
            onChange={(e) => {
              setSelectedLearner(e.target.value)
              setEvents([]); setRunId(undefined); setPlanData(undefined)
              setPlanId(undefined); setPlanApproved(false); setObjections([])
              setProgressSeries([]); setAssessment(null); setExamResult(null); setReadiness(undefined)
            }}
            className="w-full text-sm border border-gray-300 rounded-md px-2 py-1.5 focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
          >
            {learners.map((l) => (
              <option key={l.learner_id} value={l.learner_id}>{l.learner_id} — {l.role}</option>
            ))}
          </select>
        </div>

        {learner && (
          <div className="p-4 space-y-1.5 text-xs text-gray-600 border-b border-gray-100">
            <p><span className="text-gray-400">Role</span> · {learner.role}</p>
            <p><span className="text-gray-400">Cert</span> · <span className="font-semibold text-gray-800">{learner.cert_target}</span></p>
            <p><span className="text-gray-400">Team</span> · {learner.team_id}</p>
            <p><span className="text-gray-400">Deadline</span> · {learner.deadline}</p>
          </div>
        )}

        <div className="p-4 space-y-3">
          <button
            onClick={handleRun}
            disabled={running || !learner}
            className="w-full flex items-center justify-center gap-2 bg-brand-600 hover:bg-brand-700 text-white text-sm px-3 py-2 rounded-md font-medium disabled:opacity-50 transition"
          >
            {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            {running ? 'Running…' : 'Run Workflow'}
          </button>

          {/* Mock exam controls */}
          <div className="pt-2 border-t border-gray-100 space-y-2">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Mock Exam Difficulty</label>
            <div className="grid grid-cols-2 gap-1.5">
              {DIFFICULTIES.map((d) => (
                <button
                  key={d}
                  onClick={() => setDifficulty(d)}
                  className={`text-xs py-1.5 rounded-md border transition ${
                    difficulty === d
                      ? 'bg-brand-600 text-white border-brand-600'
                      : 'bg-white text-gray-600 border-gray-300 hover:border-brand-400'
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
              {generating ? 'Generating…' : `Generate ${difficulty} Exam`}
            </button>
          </div>
        </div>

        {planId && (
          <div className="mt-auto p-4 border-t border-gray-100">
            <button
              onClick={() => setActiveTab('plan')}
              className={`w-full flex items-center justify-center gap-2 text-sm px-3 py-2 rounded-md font-medium transition ${
                planApproved
                  ? 'bg-green-50 text-green-700 border border-green-200'
                  : 'bg-amber-50 text-amber-700 border border-amber-300 hover:bg-amber-100'
              }`}
            >
              {planApproved ? <CheckCircle2 size={14} /> : <ClipboardList size={14} />}
              {planApproved ? 'Plan Approved' : 'Review & Approve Plan'}
            </button>
          </div>
        )}
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex border-b border-gray-200 bg-white px-4 overflow-x-auto">
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
                    : 'border-transparent text-gray-500 hover:text-gray-700'
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

          {activeTab === 'reasoning' && (
            <div className="h-[calc(100%-40px)] mt-3">
              <ReasoningPanel events={events} runId={runId} />
            </div>
          )}

          {activeTab === 'plan' && (
            <div className="mt-3">
              <StudyPlanView plan={planData} approved={planApproved} onApproved={() => setPlanApproved(true)} />
            </div>
          )}

          {activeTab === 'critic' && (
            <div className="mt-3"><CriticVsPlanView objections={objections} /></div>
          )}

          {activeTab === 'progress' && (
            <div className="mt-3 max-w-2xl bg-white rounded-lg border border-gray-200 p-4">
              <DeviationGraph series={progressSeries} />
            </div>
          )}

          {activeTab === 'readiness' && (
            <div className="mt-3 space-y-4">
            {readiness && (
              <div className={`rounded-lg border p-4 ${
                readiness.kind === 'readiness_advance'
                  ? 'bg-green-50 border-green-200'
                  : 'bg-amber-50 border-amber-300'
              }`}>
                <div className="flex items-center gap-2 text-sm font-semibold mb-1">
                  <Target size={15} className={readiness.kind === 'readiness_advance' ? 'text-green-700' : 'text-amber-700'} />
                  <span className={readiness.kind === 'readiness_advance' ? 'text-green-800' : 'text-amber-800'}>
                    Assessment Agent verdict: {readiness.verdict === 'ready' ? 'READY — advance' : readiness.verdict === 'not_ready' ? 'NOT READY — loop back to prep' : 'Insufficient evidence'}
                  </span>
                </div>
                <p className="text-xs text-gray-700">{readiness.message}</p>
                {readiness.next_step && <p className="text-xs text-gray-600 mt-1"><strong>Next step:</strong> {readiness.next_step}</p>}
              </div>
            )}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">Pass-Threshold Forecast</h3>
                {forecast ? <PassThresholdGauge forecast={forecast} /> : <p className="text-gray-400 text-sm">Run a workflow first.</p>}
              </div>
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">Domain Mastery Breakdown</h3>
                {mastery ? <DomainMasteryChart domains={mastery.domains} passThreshold={mastery.pass_threshold} /> : <p className="text-gray-400 text-sm">Run a workflow first.</p>}
              </div>
              <div className="bg-white rounded-lg border border-gray-200 p-4 xl:col-span-2">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">Service-Level Heatmap</h3>
                {mastery ? <ServiceHeatmap domains={mastery.domains} /> : <p className="text-gray-400 text-sm">Run a workflow first.</p>}
              </div>
            </div>
            </div>
          )}

          {activeTab === 'assessment' && (
            <div className="mt-3 max-w-3xl space-y-4">
              {!assessment && (
                <div className="flex flex-col items-center justify-center h-64 bg-gray-50 rounded-lg border border-dashed border-gray-300 text-gray-400">
                  <BookOpen size={28} className="mb-2 opacity-50" />
                  <p className="text-sm">Pick a difficulty and click "Generate Exam" in the sidebar.</p>
                </div>
              )}
              {assessment && !examResult && (
                <>
                  <div className="sticky top-0 bg-gray-50 py-2 flex items-center justify-between border-b border-gray-200 z-10">
                    <div>
                      <h3 className="font-semibold text-gray-700">{assessment.cert_id} — Mock Exam</h3>
                      <p className="text-xs text-gray-500">
                        {totalQ} questions · {assessment.time_limit_minutes} min · answered {answeredQ}/{totalQ}
                      </p>
                    </div>
                    <button
                      onClick={handleSubmitExam}
                      disabled={submitting || answeredQ === 0}
                      className="bg-brand-600 hover:bg-brand-700 text-white text-sm px-4 py-1.5 rounded-md disabled:opacity-50 flex items-center gap-1.5"
                    >
                      {submitting && <Loader2 size={13} className="animate-spin" />}
                      Submit ({answeredQ}/{totalQ})
                    </button>
                  </div>
                  <div className="space-y-4">
                    {assessment.questions.map((q: any, idx: number) => (
                      <div key={q.question_id} className="bg-white border border-gray-200 rounded-lg p-4 space-y-2">
                        <div className="flex items-start justify-between gap-3">
                          <p className="text-sm font-medium">{idx + 1}. {q.question_text}</p>
                          {q.difficulty && (
                            <span className={`shrink-0 text-[10px] font-semibold px-2 py-0.5 rounded-full ${DIFF_BADGE[q.difficulty] ?? 'bg-gray-100 text-gray-600'}`}>
                              {q.difficulty}
                            </span>
                          )}
                        </div>
                        <div className="space-y-1">
                          {q.options.map((opt: string, oi: number) => (
                            <label key={oi} className={`flex items-center gap-2 text-sm cursor-pointer rounded px-2 py-1 transition ${answers[q.question_id] === oi ? 'bg-brand-50' : 'hover:bg-gray-50'}`}>
                              <input
                                type="radio" name={q.question_id} value={oi}
                                checked={answers[q.question_id] === oi}
                                onChange={() => setAnswers((a) => ({ ...a, [q.question_id]: oi }))}
                              />
                              {opt}
                            </label>
                          ))}
                        </div>
                        <p className="text-xs text-gray-400">{q.domain}{q.sub_topic ? ` · ${q.sub_topic}` : ''}</p>
                      </div>
                    ))}
                  </div>
                </>
              )}
              {examResult && (
                <div className="bg-white border rounded-lg p-6 space-y-3">
                  <h3 className="font-semibold text-lg">Assessment Result</h3>
                  <div className={`text-3xl font-bold ${examResult.passed ? 'text-green-600' : 'text-red-500'}`}>
                    {examResult.passed ? '✓ PASS' : '✗ FAIL'}
                  </div>
                  <p className="text-gray-600">
                    Score: <strong>{examResult.score_pct}%</strong> ·
                    {' '}Estimated exam score: <strong>{examResult.estimated_exam_score} / 1000</strong> ·
                    {' '}Scored <strong>{examResult.questions_scored}</strong> questions
                  </p>
                  {forecast && <PassThresholdGauge forecast={forecast} />}
                  <button
                    onClick={() => { setExamResult(null); setAnswers({}) }}
                    className="text-sm text-brand-600 hover:underline"
                  >
                    ← Retake / review questions
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
