import { RadialBarChart, RadialBar, ResponsiveContainer } from 'recharts'
import type { Forecast } from '../api/client'
import clsx from 'clsx'

interface Props {
  forecast: Forecast
}

export default function PassThresholdGauge({ forecast }: Props) {
  if (forecast.insufficient_evidence) {
    return (
      <div className="text-center py-6 text-sm text-ink-muted">
        <div className="text-3xl mb-2">?</div>
        <p className="font-medium">Insufficient evidence to forecast</p>
        <p className="text-xs mt-1 text-ink-subtle">Complete at least one assessment to generate a forecast.</p>
      </div>
    )
  }

  const pct = Math.round(forecast.pass_probability * 100)
  const color = pct >= 75 ? '#22c55e' : pct >= 55 ? '#f59e0b' : '#ef4444'
  const data = [{ value: pct, fill: color }]

  const score = forecast.estimated_exam_score
  const threshold = forecast.pass_threshold
  const gap = forecast.points_below_threshold

  return (
    <div className="space-y-4">
      {/* Gauge */}
      <div className="flex items-center gap-6">
        <div className="relative w-28 h-28">
          <ResponsiveContainer width="100%" height="100%">
            <RadialBarChart
              cx="50%" cy="50%"
              innerRadius="65%" outerRadius="100%"
              startAngle={220} endAngle={-40}
              data={data}
              barSize={12}
            >
              <RadialBar dataKey="value" background={{ fill: '#e5e7eb' }} cornerRadius={6} />
            </RadialBarChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-bold" style={{ color }}>{pct}%</span>
            <span className="text-xs text-ink-subtle">pass prob.</span>
          </div>
        </div>

        {/* Score breakdown */}
        <div className="flex-1 space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-ink-muted">Estimated score</span>
            <span className={clsx('font-bold', score >= threshold ? 'text-emerald-300' : 'text-rose-300')}>
              {score} / 1000
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-ink-muted">Pass threshold</span>
            <span className="font-medium">{threshold}</span>
          </div>
          {gap > 0 && (
            <div className="flex justify-between">
              <span className="text-ink-muted">Points needed</span>
              <span className="text-rose-300 font-medium">+{gap} pts</span>
            </div>
          )}
          <div className="flex justify-between">
            <span className="text-ink-muted">Confidence interval</span>
            <span className="text-ink-muted text-xs">
              [{Math.round(forecast.confidence_interval_lower * 100)}% – {Math.round(forecast.confidence_interval_upper * 100)}%]
            </span>
          </div>
        </div>
      </div>

      {/* Calibrated P(pass) — logistic model, LOO AUC ≈ 0.80 */}
      {forecast.calibrated && !forecast.calibrated.insufficient_evidence && forecast.calibrated.pass_probability != null && (
        <div className="flex items-center justify-between bg-violet-500/10 border border-violet-500/30 rounded p-3 text-sm">
          <div>
            <span className="text-violet-200 font-semibold">Calibrated P(pass)</span>
            <span className="block text-[11px] text-violet-300">logistic model · LOO AUC ≈ 0.80 · abstains when thin</span>
          </div>
          <div className="text-right">
            <span className="text-xl font-bold text-violet-300">{Math.round(forecast.calibrated.pass_probability * 100)}%</span>
            <span className={clsx('block text-[11px] font-medium',
              forecast.calibrated.verdict === 'likely_pass' ? 'text-emerald-300' : 'text-amber-300')}>
              {forecast.calibrated.verdict === 'likely_pass' ? 'likely pass' : 'at risk'}
            </span>
          </div>
        </div>
      )}

      {/* Weak area + hours */}
      <div className="bg-white/5 rounded p-3 text-xs space-y-1 border border-line">
        <p><span className="text-ink-muted">Weakest area:</span> <strong>{forecast.weakest_topic}</strong></p>
        <p><span className="text-ink-muted">Min. additional study hours to reach 75% probability:</span> <strong>{forecast.minimum_additional_hours}h</strong></p>
      </div>
    </div>
  )
}
