import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Users, AlertTriangle, CheckCircle, HelpCircle } from 'lucide-react'
import { api, type Team, type TeamInsights } from '../api/client'
import AIDisclosureBanner from '../components/AIDisclosureBanner'
import clsx from 'clsx'

const RISK_STYLE: Record<string, string> = {
  low: 'bg-green-100 text-green-700',
  medium: 'bg-amber-100 text-amber-700',
  high: 'bg-red-100 text-red-700',
}

const RISK_ICON: Record<string, React.ReactNode> = {
  low: <CheckCircle size={14} />,
  medium: <AlertTriangle size={14} />,
  high: <AlertTriangle size={14} className="text-red-500" />,
}

function CapacityCard({ member }: { member: any }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm text-gray-700">{member.employee_id}</span>
        <span className={clsx('flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium', RISK_STYLE[member.capacity_risk] ?? 'bg-gray-100 text-gray-600')}>
          {RISK_ICON[member.capacity_risk]}
          {member.capacity_risk} capacity risk
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs text-gray-600">
        <div>
          <p className="text-gray-400">Meeting hrs/wk</p>
          <p className="font-semibold text-gray-800">{member.meeting_hours_pw}h</p>
        </div>
        <div>
          <p className="text-gray-400">Focus hrs/wk</p>
          <p className="font-semibold text-gray-800">{member.focus_hours_pw}h</p>
        </div>
      </div>
      {member.recommended_slots && member.recommended_slots.length > 0 && (
        <div>
          <p className="text-xs text-gray-400 mb-1">Recommended study slots</p>
          <div className="flex flex-wrap gap-1">
            {member.recommended_slots.slice(0, 2).map((slot: string) => (
              <span key={slot} className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">{slot}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function ManagerView() {
  const [selectedTeam, setSelectedTeam] = useState('TEAM-A')

  const { data: teams = [] } = useQuery<Team[]>({ queryKey: ['teams'], queryFn: api.teams })
  const { data: insights, isLoading } = useQuery<TeamInsights>({
    queryKey: ['manager', selectedTeam],
    queryFn: () => api.managerInsights(selectedTeam),
  })

  const team = teams.find((t) => t.team_id === selectedTeam)

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Users size={22} className="text-brand-600" />
          <h1 className="text-xl font-bold text-gray-900">Manager Insights</h1>
        </div>
        <select
          value={selectedTeam}
          onChange={(e) => setSelectedTeam(e.target.value)}
          className="text-sm border border-gray-300 rounded px-3 py-1.5"
        >
          {teams.map((t) => (
            <option key={t.team_id} value={t.team_id}>{t.team_id} — {t.team_name}</option>
          ))}
        </select>
      </div>

      <AIDisclosureBanner message="AI-generated team insights; verify before use in performance or HR decisions." />

      {isLoading && <p className="text-gray-400 text-sm">Loading team insights…</p>}

      {insights && (
        <>
          {/* Summary stats */}
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: 'Team members', value: insights.member_count },
              { label: 'Avg meeting hrs/wk', value: `${insights.average_meeting_hours_pw}h` },
              { label: 'High capacity risk', value: insights.high_capacity_risk_members.length },
            ].map((s) => (
              <div key={s.label} className="bg-white rounded-lg border border-gray-200 p-4 text-center">
                <p className="text-2xl font-bold text-gray-900">{s.value}</p>
                <p className="text-xs text-gray-500 mt-1">{s.label}</p>
              </div>
            ))}
          </div>

          {/* High risk members */}
          {insights.high_capacity_risk_members.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-red-700 flex items-center gap-2 mb-2">
                <AlertTriangle size={15} /> Capacity conflicts flagged
              </h3>
              <p className="text-sm text-red-600">
                {insights.high_capacity_risk_members.join(', ')} have high meeting loads (&gt;25h/wk).
                Consider schedule adjustments before certification deadlines.
              </p>
            </div>
          )}

          {/* Member cards */}
          <div>
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Team Members — Work Context</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {insights.members.map((m) => <CapacityCard key={m.employee_id} member={m} />)}
            </div>
          </div>

          {/* Cert targets */}
          {team && (
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <h2 className="text-sm font-semibold text-gray-700 mb-2">Team Certification Targets</h2>
              <div className="flex flex-wrap gap-2">
                {team.cert_targets.map((c) => (
                  <span key={c} className="bg-blue-50 text-blue-700 text-xs px-3 py-1 rounded-full font-medium">{c}</span>
                ))}
              </div>
              <p className="text-xs text-gray-400 mt-2">{team.quarter_goal}</p>
            </div>
          )}

          {/* Peer-learning note */}
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-2">
              <HelpCircle size={14} className="inline mr-1 text-blue-400" />
              Peer Learning Opportunities
            </h2>
            <p className="text-sm text-gray-500">
              Run individual learner workflows from the Learner view to generate peer-learning pair recommendations.
              The system identifies complementary strengths and gaps across the team.
            </p>
          </div>

          <p className="text-xs text-gray-400">{insights.ai_disclosure}</p>
        </>
      )}
    </div>
  )
}
