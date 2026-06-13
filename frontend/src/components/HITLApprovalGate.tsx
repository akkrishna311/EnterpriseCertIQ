import { CheckCircle, UserCheck, Clock } from 'lucide-react'

interface Props {
  planId: string
  onApproved: () => void
  alreadyApproved?: boolean
  canApprove?: boolean
}

export default function HITLApprovalGate({ alreadyApproved = false, canApprove = false }: Props) {
  if (alreadyApproved) {
    return (
      <div className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-700">
        <CheckCircle size={16} />
        <span><strong>Plan approved &amp; published.</strong> Human oversight complete — the plan is now active.</span>
      </div>
    )
  }

  if (!canApprove) {
    return (
      <div className="flex items-center gap-3 bg-amber-50 border border-amber-300 rounded-lg px-4 py-3 text-sm text-amber-800">
        <Clock size={16} className="shrink-0" />
        <span>
          <strong>Awaiting manager approval.</strong> Your manager will review this AI-generated plan before it goes live. No action needed from you.
        </span>
      </div>
    )
  }

  return (
    <div className="bg-amber-50 border border-amber-300 rounded-lg p-4 space-y-3">
      <div className="flex items-center gap-2 text-amber-800 font-semibold text-sm">
        <UserCheck size={16} />
        Human review required before this plan is published
      </div>
      <p className="text-xs text-amber-700">
        This study plan was AI-generated. Review the weekly breakdown and Critic objections, then approve. The plan stays a <strong>draft</strong> until you approve it.
      </p>
    </div>
  )
}
