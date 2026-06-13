import { AlertTriangle } from 'lucide-react'

export default function AIDisclosureBanner({ message }: { message?: string }) {
  return (
    <div className="flex items-center gap-2 bg-amber-500/10 border border-amber-500/30 rounded px-3 py-2 text-xs text-amber-300">
      <AlertTriangle size={14} className="shrink-0" />
      <span>
        <strong>AI-generated</strong> —{' '}
        {message ?? 'Review before acting on this information.'}
      </span>
    </div>
  )
}
