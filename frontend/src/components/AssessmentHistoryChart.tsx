import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine } from 'recharts'
import type { AssessmentAttempt } from '../api/client'

interface Props {
  attempts: AssessmentAttempt[]
}

export default function AssessmentHistoryChart({ attempts }: Props) {
  if (!attempts.length) {
    return (
      <div className="flex items-center justify-center h-48 bg-white/5 rounded border border-dashed border-line-strong text-ink-subtle text-sm">
        Submitted mock exams will appear here as a score trend.
      </div>
    )
  }

  const latestAttempt = attempts[attempts.length - 1]
  const previousAttempt = attempts.length > 1 ? attempts[attempts.length - 2] : undefined
  const latestDelta = previousAttempt ? latestAttempt.score_pct - previousAttempt.score_pct : null

  function formatDelta(delta: number | null): string {
    if (delta === null) {
      return 'First recorded attempt'
    }
    const rounded = Math.round(delta * 10) / 10
    const prefix = rounded > 0 ? '+' : ''
    return `${prefix}${rounded}% vs previous attempt`
  }

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-ink">Assessment Trend</h3>
        <p className="text-xs text-ink-muted">Each submitted mock exam is persisted and plotted as a learner trend.</p>
        <p className={`text-xs mt-1 ${latestDelta === null ? 'text-ink-muted' : latestDelta >= 0 ? 'text-emerald-300' : 'text-amber-300'}`}>
          {formatDelta(latestDelta)}
        </p>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={attempts} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="attempt_number" tick={{ fontSize: 11 }} label={{ value: 'Attempt', position: 'insideBottom', offset: -2 }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} label={{ value: 'Score %', angle: -90, position: 'insideLeft', fontSize: 11 }} />
          <Tooltip
            formatter={(value: number, name: string) => [name === 'score_pct' ? `${value}%` : value, name === 'score_pct' ? 'Score' : 'Estimated exam score']}
            labelFormatter={(label) => `Attempt ${label}`}
          />
          <ReferenceLine y={70} stroke="#f59e0b" strokeDasharray="4 2" label={{ value: 'Pass threshold', position: 'insideTopRight', fill: '#b45309', fontSize: 10 }} />
          <Line type="monotone" dataKey="score_pct" stroke="#2563eb" strokeWidth={2.5} dot={{ r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-ink-muted">
        {attempts.slice().reverse().map((attempt) => {
          const previous = attempt.attempt_number > 1 ? attempts[attempt.attempt_number - 2] : undefined
          const delta = previous ? Math.round((attempt.score_pct - previous.score_pct) * 10) / 10 : null
          return (
          <div key={attempt.assessment_id} className="rounded-md border border-line bg-white/5 px-3 py-2">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium text-ink">Attempt {attempt.attempt_number}</span>
              <span className={attempt.passed ? 'text-emerald-300' : 'text-amber-300'}>{attempt.passed ? 'PASS' : 'REVIEW'}</span>
            </div>
            <div>{attempt.score_pct}% score · {attempt.estimated_exam_score} / 1000</div>
            <div>{attempt.difficulty} · {attempt.question_count} questions</div>
            <div className={delta === null ? 'text-ink-muted' : delta >= 0 ? 'text-emerald-300' : 'text-amber-300'}>
              {delta === null ? 'First attempt on record' : `${delta > 0 ? '+' : ''}${delta}% vs previous`}
            </div>
          </div>
        )})}
      </div>
    </div>
  )
}