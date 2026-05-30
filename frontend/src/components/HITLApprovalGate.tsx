import { CheckCircle, UserCheck, AlertTriangle } from 'lucide-react'
import { useState } from 'react'
import { postJSON } from '../api/client'

interface Props {
  planId: string
  onApproved: () => void
  alreadyApproved?: boolean
}

export default function HITLApprovalGate({ planId, onApproved, alreadyApproved = false }: Props) {
  const [approving, setApproving] = useState(false)
  const [approved, setApproved] = useState(alreadyApproved)
  const [error, setError] = useState<string>()

  async function handleApprove() {
    setApproving(true)
    setError(undefined)
    try {
      await postJSON('/plans/approve', { plan_id: planId, approved_by: 'human' })
      setApproved(true)
      onApproved()
    } catch {
      setError('Plan is still finalizing — wait for the workflow to finish, then approve.')
      setApproving(false)
    }
  }

  if (approved || alreadyApproved) {
    return (
      <div className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-700">
        <CheckCircle size={16} />
        <span><strong>Plan approved &amp; published.</strong> Human oversight complete — the plan is now active.</span>
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
        This study plan was AI-generated. Review the Critic objections and the weekly breakdown
        below, then approve. The plan stays a <strong>draft</strong> until you approve it.
      </p>
      <button
        onClick={handleApprove}
        disabled={approving}
        className="bg-amber-600 hover:bg-amber-700 text-white text-sm px-4 py-2 rounded-md font-medium disabled:opacity-50 transition"
      >
        {approving ? 'Approving…' : '✓ Approve & Publish Plan'}
      </button>
      {error && (
        <p className="flex items-center gap-1.5 text-xs text-red-600">
          <AlertTriangle size={12} /> {error}
        </p>
      )}
    </div>
  )
}
