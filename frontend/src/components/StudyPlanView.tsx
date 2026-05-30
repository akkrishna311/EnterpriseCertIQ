import { Calendar, Clock, BookOpen, AlertCircle } from 'lucide-react'
import HITLApprovalGate from './HITLApprovalGate'

interface Topic {
  title: string
  domain?: string
  hours_allocated?: number
  difficulty?: string
}
interface Week {
  week: number
  topics: Topic[]
  planned_hours: number
  notes?: string
}
export interface StudyPlan {
  plan_id: string
  learner_id?: string
  cert_id?: string
  deadline?: string
  status?: string
  total_planned_hours?: number
  weeks?: Week[]
}

interface Props {
  plan?: StudyPlan
  approved: boolean
  onApproved: () => void
}

export default function StudyPlanView({ plan, approved, onApproved }: Props) {
  if (!plan) {
    return (
      <div className="flex flex-col items-center justify-center h-64 bg-gray-50 rounded-lg border border-dashed border-gray-300 text-gray-400">
        <BookOpen size={28} className="mb-2 opacity-50" />
        <p className="text-sm">Run a workflow to generate a study plan.</p>
      </div>
    )
  }

  const weeks = plan.weeks ?? []

  return (
    <div className="space-y-4 max-w-4xl">
      {/* Header card */}
      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div>
            <h3 className="text-lg font-semibold text-gray-800">{plan.cert_id} Study Plan</h3>
            <p className="text-xs text-gray-500 font-mono mt-0.5">{plan.plan_id}</p>
          </div>
          <span
            className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
              approved || plan.status === 'approved'
                ? 'bg-green-100 text-green-700'
                : 'bg-amber-100 text-amber-700'
            }`}
          >
            {approved || plan.status === 'approved' ? 'Approved · Published' : 'Draft · Pending approval'}
          </span>
        </div>
        <div className="flex gap-6 mt-4 text-sm">
          <div className="flex items-center gap-1.5 text-gray-600">
            <Calendar size={15} className="text-brand-600" />
            <span>Deadline: <strong>{plan.deadline || '—'}</strong></span>
          </div>
          <div className="flex items-center gap-1.5 text-gray-600">
            <Clock size={15} className="text-brand-600" />
            <span>Total: <strong>{plan.total_planned_hours ?? 0}h</strong> over <strong>{weeks.length}</strong> weeks</span>
          </div>
        </div>
      </div>

      {/* Approval gate */}
      <HITLApprovalGate planId={plan.plan_id} alreadyApproved={approved} onApproved={onApproved} />

      {/* Weekly breakdown */}
      <div className="space-y-3">
        {weeks.map((w) => (
          <div key={w.week} className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <div className="flex items-center justify-between bg-gray-50 px-4 py-2 border-b border-gray-100">
              <span className="text-sm font-semibold text-gray-700">Week {w.week}</span>
              <span className="text-xs text-gray-500 flex items-center gap-1">
                <Clock size={12} /> {w.planned_hours}h planned
              </span>
            </div>
            <ul className="divide-y divide-gray-50">
              {w.topics.map((t, i) => (
                <li key={i} className="px-4 py-2.5 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm text-gray-800 truncate">{t.title}</p>
                    {t.domain && <p className="text-xs text-gray-400 truncate">{t.domain}</p>}
                  </div>
                  {t.hours_allocated != null && (
                    <span className="shrink-0 text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">
                      {t.hours_allocated}h
                    </span>
                  )}
                </li>
              ))}
              {w.topics.length === 0 && (
                <li className="px-4 py-2.5 text-xs text-gray-400 flex items-center gap-1.5">
                  <AlertCircle size={12} /> No topics scheduled this week.
                </li>
              )}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}
