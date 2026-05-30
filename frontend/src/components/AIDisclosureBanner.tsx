import { AlertTriangle } from 'lucide-react'

export default function AIDisclosureBanner({ message }: { message?: string }) {
  return (
    <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded px-3 py-2 text-xs text-amber-800">
      <AlertTriangle size={14} className="shrink-0" />
      <span>
        <strong>AI-generated</strong> —{' '}
        {message ?? 'Review before acting on this information.'}
      </span>
    </div>
  )
}
