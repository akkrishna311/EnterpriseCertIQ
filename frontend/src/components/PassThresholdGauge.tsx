import { RadialBarChart, RadialBar, ResponsiveContainer } from 'recharts'
import type { Forecast } from '../api/client'
import clsx from 'clsx'

interface Props {
  forecast: Forecast
}

export default function PassThresholdGauge({ forecast }: Props) {
  if (forecast.insufficient_evidence) {
    return (
      <div className="text-center py-6 text-sm text-gray-500">
        <div className="text-3xl mb-2">?</div>
        <p className="font-medium">Insufficient evidence to forecast</p>
        <p className="text-xs mt-1 text-gray-400">Complete at least one assessment to generate a forecast.</p>
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
            <span className="text-xs text-gray-400">pass prob.</span>
          </div>
        </div>

        {/* Score breakdown */}
        <div className="flex-1 space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-600">Estimated score</span>
            <span className={clsx('font-bold', score >= threshold ? 'text-green-600' : 'text-red-600')}>
              {score} / 1000
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Pass threshold</span>
            <span className="font-medium">{threshold}</span>
          </div>
          {gap > 0 && (
            <div className="flex justify-between">
              <span className="text-gray-600">Points needed</span>
              <span className="text-red-600 font-medium">+{gap} pts</span>
            </div>
          )}
          <div className="flex justify-between">
            <span className="text-gray-600">Confidence interval</span>
            <span className="text-gray-500 text-xs">
              [{Math.round(forecast.confidence_interval_lower * 100)}% – {Math.round(forecast.confidence_interval_upper * 100)}%]
            </span>
          </div>
        </div>
      </div>

      {/* Weak area + hours */}
      <div className="bg-gray-50 rounded p-3 text-xs space-y-1 border border-gray-200">
        <p><span className="text-gray-500">Weakest area:</span> <strong>{forecast.weakest_topic}</strong></p>
        <p><span className="text-gray-500">Min. additional study hours to reach 75% probability:</span> <strong>{forecast.minimum_additional_hours}h</strong></p>
      </div>
    </div>
  )
}
