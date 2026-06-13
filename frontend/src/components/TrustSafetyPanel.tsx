import { useQuery } from '@tanstack/react-query'
import { ShieldCheck, Target, Lock } from 'lucide-react'
import { api } from '../api/client'

/** Surfaces the project's quality + safety metrics so judges see them in the demo:
 *  calibrated readiness AUC, the adversarial red-team scorecard, and content-safety mode. */
export default function TrustSafetyPanel() {
  const { data } = useQuery({ queryKey: ['eval-summary'], queryFn: api.evalSummary, staleTime: 60_000 })
  if (!data) return null

  const rt = data.red_team
  const held = rt.held === rt.total
  const asr = `${(rt.attack_success_rate * 100).toFixed(0)}%`

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
      <div className="bg-surface-2 rounded-lg border border-line p-4">
        <div className="flex items-center gap-2 text-violet-300 font-semibold mb-1">
          <Target size={15} /> Calibrated readiness
        </div>
        <p className="text-2xl font-bold text-ink">{data.readiness_model.auc_loo}</p>
        <p className="text-[11px] text-ink-muted">LOO AUC · Brier {data.readiness_model.brier_loo} · n={data.readiness_model.n}</p>
      </div>
      <div className="bg-surface-2 rounded-lg border border-line p-4">
        <div className="flex items-center gap-2 font-semibold mb-1" style={{ color: held ? '#16a34a' : '#b45309' }}>
          <ShieldCheck size={15} /> Adversarial red-team
        </div>
        <p className="text-2xl font-bold text-ink">{rt.held}/{rt.total}</p>
        <p className="text-[11px] text-ink-muted">attacks held · ASR {asr}</p>
      </div>
      <div className="bg-surface-2 rounded-lg border border-line p-4">
        <div className="flex items-center gap-2 text-ink font-semibold mb-1">
          <Lock size={15} /> Content Safety
        </div>
        <p className="text-2xl font-bold text-ink capitalize">{data.content_safety}</p>
        <p className="text-[11px] text-ink-muted">{data.content_safety === 'azure' ? 'Azure AI Content Safety (live)' : 'regex fallback (set key for live)'}</p>
      </div>
    </div>
  )
}
