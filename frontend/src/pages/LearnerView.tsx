import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Play, BookOpen, Target, Zap } from 'lucide-react'
import { api, streamEvents, type TraceEvent, type Forecast, type MasteryGrid } from '../api/client'
import ReasoningPanel from '../components/ReasoningPanel'
import CriticVsPlanView from '../components/CriticVsPlanView'
import DeviationGraph from '../components/DeviationGraph'
import DomainMasteryChart from '../components/DomainMasteryChart'
import ServiceHeatmap from '../components/ServiceHeatmap'
import PassThresholdGauge from '../components/PassThresholdGauge'
import HITLApprovalGate from '../components/HITLApprovalGate'
import AIDisclosureBanner from '../components/AIDisclosureBanner'

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

type TabKey = 'reasoning' | 'critic' | 'progress' | 'readiness' | 'assessment'

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: 'reasoning', label: 'Reasoning', icon: <Zap size={14} /> },
  { key: 'critic', label: 'Critic vs Plan', icon: <Target size={14} /> },
  { key: 'progress', label: 'Progress', icon: <BookOpen size={14} /> },
  { key: 'readiness', label: 'Readiness', icon: <Target size={14} /> },
  { key: 'assessment', label: 'Mock Exam', icon: <BookOpen size={14} /> },
]

export default function LearnerView() {
  const [selectedLearner, setSelectedLearner] = useState('L-1004')
  const [runId, setRunId] = useState<string>()
  const [running, setRunning] = useState(false)
  const [events, setEvents] = useState<TraceEvent[]>([])
  const [activeTab, setActiveTab] = useState<TabKey>('reasoning')
  const [planId, setPlanId] = useState<string>()
  const [planApproved, setPlanApproved] = useState(false)
  const [objections, setObjections] = useState<any[]>([])
  const [progressSeries, setProgressSeries] = useState<any[]>([])
  const [assessment, setAssessment] = useState<any>(null)
  const [answers, setAnswers] = useState<Record<string, number>>({})
  const [examResult, setExamResult] = useState<any>(null)

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
    setEvents([])
    setObjections([])
    setProgressSeries([])
    setPlanId(undefined)
    setPlanApproved(false)

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
          if (result?.plan_id) setPlanId(result.plan_id)
        }
        if (eventType === 'tool_result' && evt.data?.tool === 'compute_progress_series') {
          setProgressSeries(evt.data?.result?.series ?? [])
        }
        if (eventType === 'workflow_error') {
          setEvents((prev) => [...prev, {
            event_id: `${run_id}-workflow-error`,
            run_id,
            timestamp: new Date().toISOString(),
            event_type: 'error',
            agent_name: 'orchestrator',
            data: { message: evt.error ?? 'Workflow failed' },
          }])
        }

        if (eventType === 'workflow_complete' || eventType === 'workflow_error') {
          setRunning(false)
          stop()
          refetchMastery()
          refetchForecast()
        }
      })
    } catch (e) {
      setRunning(false)
      setEvents([{
        event_id: `${Date.now()}-run-error`,
        run_id: runId ?? 'pending',
        timestamp: new Date().toISOString(),
        event_type: 'error',
        agent_name: 'orchestrator',
        data: { message: e instanceof Error ? e.message : 'Failed to start workflow' },
      }])
    }
  }

  async function handleGenerateAssessment() {
    if (!learner) return
    const result = await api.generateAssessment(selectedLearner, learner.cert_target)
    setAssessment(result)
    setAnswers({})
    setExamResult(null)
    setActiveTab('assessment')
  }

  async function handleSubmitExam() {
    if (!assessment || !learner) return
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
  }

  return (
    <div className="flex h-[calc(100vh-52px)]">
      {/* Left sidebar */}
      <aside className="w-64 shrink-0 border-r border-gray-200 bg-white flex flex-col">
        <div className="p-4 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Select Learner</h2>
          <select
            value={selectedLearner}
            onChange={(e) => { setSelectedLearner(e.target.value); setEvents([]); setRunId(undefined) }}
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5"
          >
            {learners.map((l) => (
              <option key={l.learner_id} value={l.learner_id}>
                {l.learner_id} — {l.role}
              </option>
            ))}
          </select>
        </div>

        {learner && (
          <div className="p-4 space-y-2 text-xs text-gray-600 border-b border-gray-100">
            <p><strong>Role:</strong> {learner.role}</p>
            <p><strong>Cert:</strong> {learner.cert_target}</p>
            <p><strong>Team:</strong> {learner.team_id}</p>
            <p><strong>Deadline:</strong> {learner.deadline}</p>
          </div>
        )}

        <div className="p-4 space-y-2">
          <button
            onClick={handleRun}
            disabled={running || !learner}
            className="w-full flex items-center justify-center gap-2 bg-brand-600 hover:bg-brand-700 text-white text-sm px-3 py-2 rounded font-medium disabled:opacity-50 transition"
          >
            <Play size={14} />
            {running ? 'Running…' : 'Run Workflow'}
          </button>
          <button
            onClick={handleGenerateAssessment}
            disabled={!learner}
            className="w-full flex items-center justify-center gap-2 bg-gray-700 hover:bg-gray-800 text-white text-sm px-3 py-2 rounded font-medium disabled:opacity-50 transition"
          >
            <BookOpen size={14} />
            Mock Exam
          </button>
        </div>

        {planId && !planApproved && (
          <div className="p-4 border-t border-gray-100">
            <HITLApprovalGate planId={planId} onApproved={() => setPlanApproved(true)} />
          </div>
        )}
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Tab bar */}
        <div className="flex border-b border-gray-200 bg-white px-4">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              className={`flex items-center gap-1.5 px-4 py-3 text-sm font-medium border-b-2 transition ${
                activeTab === t.key
                  ? 'border-brand-600 text-brand-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-auto p-4">
          <AIDisclosureBanner />

          {activeTab === 'reasoning' && (
            <div className="h-[calc(100%-40px)] mt-3">
              <ReasoningPanel events={events} runId={runId} />
            </div>
          )}

          {activeTab === 'critic' && (
            <div className="mt-3">
              <CriticVsPlanView objections={objections} />
            </div>
          )}

          {activeTab === 'progress' && (
            <div className="mt-3 max-w-2xl">
              <DeviationGraph series={progressSeries} />
            </div>
          )}

          {activeTab === 'readiness' && (
            <div className="mt-3 grid grid-cols-1 xl:grid-cols-2 gap-6">
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
          )}

          {activeTab === 'assessment' && (
            <div className="mt-3 max-w-3xl space-y-4">
              {!assessment && (
                <p className="text-gray-400 text-sm">Click "Mock Exam" in the sidebar to generate a timed assessment.</p>
              )}
              {assessment && !examResult && (
                <>
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-gray-700">{assessment.cert_id} — Mock Exam ({assessment.questions.length} questions)</h3>
                    <button onClick={handleSubmitExam} className="bg-brand-600 hover:bg-brand-700 text-white text-sm px-4 py-1.5 rounded">
                      Submit
                    </button>
                  </div>
                  <div className="space-y-4">
                    {assessment.questions.slice(0, 10).map((q: any, idx: number) => (
                      <div key={q.question_id} className="bg-white border border-gray-200 rounded-lg p-4 space-y-2">
                        <p className="text-sm font-medium">{idx + 1}. {q.question_text}</p>
                        <div className="space-y-1">
                          {q.options.map((opt: string, oi: number) => (
                            <label key={oi} className="flex items-center gap-2 text-sm cursor-pointer">
                              <input
                                type="radio"
                                name={q.question_id}
                                value={oi}
                                checked={answers[q.question_id] === oi}
                                onChange={() => setAnswers((a) => ({ ...a, [q.question_id]: oi }))}
                              />
                              {opt}
                            </label>
                          ))}
                        </div>
                        <p className="text-xs text-gray-400">{q.domain} · {q.difficulty}</p>
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
                  <p className="text-gray-600">Score: <strong>{examResult.score_pct}%</strong> · Estimated exam score: <strong>{examResult.estimated_exam_score} / 1000</strong></p>
                  {forecast && <PassThresholdGauge forecast={forecast} />}
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
