import { useState } from 'react'
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { Users, AlertTriangle, CheckCircle, HelpCircle, UserCheck, LayoutGrid, Gauge } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api, type DraftPlan, type Learner, type ManagerIntervention, type ManagerInterventionRequest, type ManagerWhatIfRequest, type ManagerWhatIfResult, type MasteryGrid, type PeerLearningSession, type PeerLearningSessionRequest, type ProgressSnapshot, type Team, type TeamInsights } from '../api/client'
import AIDisclosureBanner from '../components/AIDisclosureBanner'
import clsx from 'clsx'

const RISK_STYLE: Record<string, string> = {
  low: 'bg-emerald-500/15 text-emerald-300',
  medium: 'bg-amber-500/15 text-amber-300',
  high: 'bg-rose-500/15 text-rose-300',
}

const RISK_ICON: Record<string, React.ReactNode> = {
  low: <CheckCircle size={14} />,
  medium: <AlertTriangle size={14} />,
  high: <AlertTriangle size={14} className="text-rose-400" />,
}

function CapacityCard({ member }: { member: any }) {
  return (
    <div className="bg-surface-2 rounded-lg border border-line p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm text-ink">{member.employee_id}</span>
        <span className={clsx('flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium', RISK_STYLE[member.capacity_risk] ?? 'bg-white/10 text-ink-muted')}>
          {RISK_ICON[member.capacity_risk]}
          {member.capacity_risk} capacity risk
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs text-ink-muted">
        <div>
          <p className="text-ink-subtle">Meeting hrs/wk</p>
          <p className="font-semibold text-ink">{member.meeting_hours_pw}h</p>
        </div>
        <div>
          <p className="text-ink-subtle">Focus hrs/wk</p>
          <p className="font-semibold text-ink">{member.focus_hours_pw}h</p>
        </div>
      </div>
      {member.recommended_slots && member.recommended_slots.length > 0 && (
        <div>
          <p className="text-xs text-ink-subtle mb-1">Recommended study slots</p>
          <div className="flex flex-wrap gap-1">
            {member.recommended_slots.slice(0, 2).map((slot: string) => (
              <span key={slot} className="text-xs bg-blue-500/10 text-blue-300 px-2 py-0.5 rounded">{slot}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function TrendSparkline({ scores }: { scores: number[] }) {
  if (!scores.length) {
    return <div className="h-10 rounded bg-white/5 border border-dashed border-line" />
  }

  const width = 120
  const height = 36
  const points = scores.map((score, index) => {
    const x = scores.length === 1 ? width / 2 : (index / (scores.length - 1)) * width
    const y = height - (score / 100) * (height - 6) - 3
    return `${x},${y}`
  }).join(' ')

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-10 w-full overflow-visible">
      <polyline
        fill="none"
        stroke="#93c5fd"
        strokeWidth="2"
        points={`0,${height - 3} ${width},${height - 3}`}
        opacity="0.4"
      />
      <polyline
        fill="none"
        stroke="#2563eb"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
      {scores.map((score, index) => {
        const x = scores.length === 1 ? width / 2 : (index / (scores.length - 1)) * width
        const y = height - (score / 100) * (height - 6) - 3
        return <circle key={`${index}-${score}`} cx={x} cy={y} r="2.5" fill="#1d4ed8" />
      })}
    </svg>
  )
}

function formatAttemptTime(timestamp?: string): string {
  if (!timestamp) {
    return 'No timestamp'
  }
  const parsed = new Date(timestamp)
  return Number.isNaN(parsed.getTime()) ? timestamp : parsed.toLocaleString()
}

function formatWorkflowTimestamp(timestamp?: string): string {
  if (!timestamp) {
    return 'Not saved yet'
  }
  const parsed = new Date(timestamp)
  return Number.isNaN(parsed.getTime()) ? timestamp : parsed.toLocaleString()
}

function titleCaseLabel(value: string | undefined | null): string {
  return (value ?? '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function buildManagerHandoffBrief(
  team: Team | undefined,
  insights: TeamInsights,
  interventions: ManagerIntervention[],
  peerSessions: PeerLearningSession[],
): string {
  const lines = [
    `Manager handoff for ${team?.team_id ?? insights.team_id} — ${team?.team_name ?? 'Team'}`,
    insights.summary,
    '',
    `Readiness distribution: on track ${insights.readiness_distribution.on_track ?? 0}, at risk ${insights.readiness_distribution.at_risk ?? 0}, insufficient evidence ${insights.readiness_distribution.insufficient_evidence ?? 0}`,
  ]

  if (insights.manager_actions.length) {
    lines.push('', 'Recommended manager actions:')
    insights.manager_actions.forEach((action) => lines.push(`- ${action}`))
  }

  if (interventions.length) {
    lines.push('', 'Pinned learner interventions:')
    interventions.forEach((intervention) => {
      lines.push(`- ${intervention.learner_id}: ${titleCaseLabel(intervention.priority)} / ${intervention.status} / ${intervention.reasons.join(', ')}`)
    })
  }

  if (peerSessions.length) {
    lines.push('', 'Pinned peer sessions:')
    peerSessions.forEach((session) => {
      lines.push(`- ${session.mentor_id} coaching ${session.learner_id} on ${session.focus_domain} (${session.status})`)
    })
  }

  return lines.join('\n')
}

function getNeedsActionPriority(reasons: string[]): { label: string; score: number; tone: string } {
  const hasCapacityRisk = reasons.includes('High capacity risk')
  const hasFailedMock = reasons.includes('Latest mock below threshold')

  if (hasCapacityRisk && hasFailedMock) {
    return { label: 'Critical', score: 3, tone: 'bg-rose-500/15 text-rose-300' }
  }
  if (hasFailedMock) {
    return { label: 'High', score: 2, tone: 'bg-amber-500/15 text-amber-300' }
  }
  return { label: 'Watch', score: 1, tone: 'bg-yellow-100 text-yellow-800' }
}

function findSharedStudySlot(left: string[] = [], right: string[] = []): string | undefined {
  const overlap = left.find((slot) => right.includes(slot))
  return overlap ?? left[0] ?? right[0]
}

type NeedsActionDetail = {
  id: string
  learner: Learner
  reasons: string[]
  latestAttempt?: ProgressSnapshot['attempts'][number]
  priority: { label: string; score: number; tone: string }
}

type PeerLearningOpportunity = {
  id: string
  learner: Learner
  mentor: Learner
  focusDomain: string
  mentorStrengthPct: number
  learnerGapPct: number
  suggestedSlot?: string
  rationale: string
  matchType: string
  exchangeFocus?: string
}

function MomentumCard({ learner, progress, loading, attention }: { learner: Learner; progress?: ProgressSnapshot; loading: boolean; attention?: NeedsActionDetail }) {
  const latestAttempt = progress?.attempts?.[progress.attempts.length - 1]
  const previousAttempt = progress && progress.attempts.length > 1 ? progress.attempts[progress.attempts.length - 2] : undefined
  const delta = latestAttempt && previousAttempt
    ? Math.round((latestAttempt.score_pct - previousAttempt.score_pct) * 10) / 10
    : null
  const sparklineScores = progress?.attempts?.slice(-5).map((attempt) => attempt.score_pct) ?? []
  const sparklineAttempts = progress?.attempts?.slice(-5) ?? []

  return (
    <div className={clsx(
      'bg-surface-2 rounded-lg border p-4 space-y-2',
      attention ? 'border-amber-500/30 shadow-sm' : 'border-line',
    )}>
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="font-mono text-sm text-ink">{learner.learner_id}</p>
          <p className="text-xs text-ink-subtle">{learner.cert_target} · {learner.role}</p>
        </div>
        <div className="flex items-center gap-2">
          {attention && (
            <span className={clsx('text-xs px-2 py-0.5 rounded-full font-medium', attention.priority.tone)}>
              {attention.priority.label}
            </span>
          )}
          <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-300 font-medium">
            {progress?.attempts.length ?? 0} attempts
          </span>
        </div>
      </div>

      {attention && (
        <div className="flex flex-wrap gap-2">
          {attention.reasons.map((reason) => (
            <span key={reason} className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-medium text-amber-300">
              {reason}
            </span>
          ))}
        </div>
      )}

      {loading && <p className="text-xs text-ink-subtle">Loading learner momentum…</p>}

      {!loading && !latestAttempt && (
        <>
          <p className="text-xs text-ink-muted">No submitted mock exams yet. Use the Learner view to create the first assessment trail.</p>
          <div className="flex gap-2 pt-1">
            <Link
              to={`/?learner=${learner.learner_id}&tab=assessment`}
              className="text-xs px-2 py-1 rounded bg-blue-500/10 text-blue-300 hover:bg-blue-500/15 font-medium"
            >
              Open Mock Exam
            </Link>
            <Link
              to={`/?learner=${learner.learner_id}&tab=reasoning`}
              className="text-xs px-2 py-1 rounded bg-amber-500/10 text-amber-300 hover:bg-amber-500/15 font-medium"
            >
              Open Reasoning
            </Link>
          </div>
        </>
      )}

      {!loading && latestAttempt && (
        <>
          <div>
            <div className="flex items-center justify-between gap-2 text-[11px] text-ink-subtle mb-1">
              <span>Last {sparklineScores.length} attempts</span>
              <span>{sparklineScores.join(' · ')}</span>
            </div>
            <div className="relative">
              <TrendSparkline scores={sparklineScores} />
              <div className="sr-only">
                {sparklineAttempts.map((attempt) => (
                  <span key={attempt.assessment_id}>
                    Attempt {attempt.attempt_number}: {attempt.score_pct}% at {formatAttemptTime(attempt.submitted_at)}
                  </span>
                ))}
              </div>
              <div className="absolute inset-0 flex items-stretch justify-between px-1 pointer-events-none">
                {sparklineAttempts.map((attempt) => (
                  <div
                    key={attempt.assessment_id}
                    className="pointer-events-auto flex-1 relative group"
                  >
                    <div className="absolute -top-14 left-1/2 -translate-x-1/2 hidden whitespace-nowrap rounded-md border border-line bg-slate-900 px-2.5 py-1.5 text-[11px] font-medium text-white shadow-lg group-hover:block">
                      <div>Attempt {attempt.attempt_number} · {attempt.score_pct}%</div>
                      <div className="text-ink-muted">{formatAttemptTime(attempt.submitted_at)}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="flex items-center justify-between gap-2 text-sm">
            <span className="text-ink-muted">Latest mock result</span>
            <span className={latestAttempt.passed ? 'text-emerald-300 font-semibold' : 'text-amber-300 font-semibold'}>
              {latestAttempt.score_pct}% · {latestAttempt.passed ? 'PASS' : 'REVIEW'}
            </span>
          </div>
          <div className="flex items-center justify-between gap-2 text-xs text-ink-muted">
            <span>{latestAttempt.difficulty} · {latestAttempt.question_count} questions</span>
            <span>{latestAttempt.estimated_exam_score} / 1000</span>
          </div>
          <div className="text-xs text-ink-muted">Latest attempt: {formatAttemptTime(latestAttempt.submitted_at)}</div>
          <div className={`text-xs ${delta === null ? 'text-ink-muted' : delta >= 0 ? 'text-emerald-300' : 'text-amber-300'}`}>
            {delta === null ? 'First attempt on record' : `${delta > 0 ? '+' : ''}${delta}% vs previous attempt`}
          </div>
          <div className="flex gap-2 pt-1">
            <Link
              to={`/?learner=${learner.learner_id}&tab=progress`}
              className="text-xs px-2 py-1 rounded bg-blue-500/10 text-blue-300 hover:bg-blue-500/15 font-medium"
            >
              Open Progress
            </Link>
            <Link
              to={`/?learner=${learner.learner_id}&tab=readiness`}
              className="text-xs px-2 py-1 rounded bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/15 font-medium"
            >
              Open Readiness
            </Link>
          </div>
        </>
      )}
    </div>
  )
}

export default function ManagerView() {
  const [selectedTeam, setSelectedTeam] = useState('TEAM-A')
  const [managerTab, setManagerTab] = useState<'overview' | 'approvals' | 'capacity' | 'peer'>('overview')
  const [showNeedsAction, setShowNeedsAction] = useState(false)
  const [briefCopied, setBriefCopied] = useState(false)
  const [peerSessionDrafts, setPeerSessionDrafts] = useState<Record<string, { status: string; manager_note: string }>>({})
  const [interventionDrafts, setInterventionDrafts] = useState<Record<string, { status: string; manager_note: string }>>({})
  const [whatIfForm, setWhatIfForm] = useState<ManagerWhatIfRequest>({
    target_learner_id: '',
    protected_focus_hours: 2,
    reduced_meeting_hours: 2,
    targeted_review_hours: 3,
    peer_mentor_id: '',
    peer_session_count: 1,
  })
  const queryClient = useQueryClient()

  const { data: teams = [] } = useQuery<Team[]>({ queryKey: ['teams'], queryFn: api.teams })
  const { data: learners = [] } = useQuery<Learner[]>({ queryKey: ['learners'], queryFn: api.learners })
  const { data: insights, isLoading } = useQuery<TeamInsights>({
    queryKey: ['manager', selectedTeam],
    queryFn: () => api.managerInsights(selectedTeam),
  })
  const { data: persistedPeerSessions = [] } = useQuery<PeerLearningSession[]>({
    queryKey: ['peer-sessions', selectedTeam],
    queryFn: () => api.peerSessions(selectedTeam),
    enabled: !!selectedTeam,
  })
  const { data: persistedInterventions = [] } = useQuery<ManagerIntervention[]>({
    queryKey: ['interventions', selectedTeam],
    queryFn: () => api.interventions(selectedTeam),
    enabled: !!selectedTeam,
  })
  const savePeerSession = useMutation({
    mutationFn: (payload: PeerLearningSessionRequest) => api.savePeerSession(selectedTeam, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['peer-sessions', selectedTeam] })
    },
  })
  const deletePeerSession = useMutation({
    mutationFn: (sessionId: string) => api.deletePeerSession(selectedTeam, sessionId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['peer-sessions', selectedTeam] })
    },
  })
  const saveIntervention = useMutation({
    mutationFn: (payload: ManagerInterventionRequest) => api.saveIntervention(selectedTeam, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['interventions', selectedTeam] })
    },
  })
  const deleteIntervention = useMutation({
    mutationFn: (interventionId: string) => api.deleteIntervention(selectedTeam, interventionId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['interventions', selectedTeam] })
    },
  })
  const runWhatIf = useMutation<ManagerWhatIfResult, Error, ManagerWhatIfRequest>({
    mutationFn: (payload) => api.managerWhatIf(selectedTeam, payload),
  })
  const [approveError, setApproveError] = useState<string | null>(null)
  const approvePlan = useMutation({
    mutationFn: (planId: string) => api.approvePlan(planId),
    onSuccess: async () => {
      setApproveError(null)
      await queryClient.refetchQueries({ queryKey: ['plans'] })
    },
    onError: (err: Error) => {
      setApproveError(err.message)
    },
  })

  const team = teams.find((t) => t.team_id === selectedTeam)
  const managerOwnerId = team?.manager_id ?? 'manager'
  const teamLearners = (team?.members ?? [])
    .map((learnerId) => learners.find((learner) => learner.learner_id === learnerId))
    .filter(Boolean) as Learner[]
  const targetLearnerId = teamLearners.some((learner) => learner.learner_id === whatIfForm.target_learner_id)
    ? whatIfForm.target_learner_id
    : (teamLearners[0]?.learner_id ?? '')
  const mentorLearnerId = whatIfForm.peer_mentor_id && teamLearners.some((learner) => learner.learner_id === whatIfForm.peer_mentor_id)
    ? whatIfForm.peer_mentor_id
    : ''

  const progressQueries = useQueries({
    queries: teamLearners.map((learner) => ({
      queryKey: ['progress', learner.learner_id, learner.cert_target],
      queryFn: () => api.progress(learner.learner_id, learner.cert_target),
      enabled: !!team,
    })),
  })
  const masteryQueries = useQueries({
    queries: teamLearners.map((learner) => ({
      queryKey: ['mastery', learner.learner_id, learner.cert_target],
      queryFn: () => api.mastery(learner.learner_id, learner.cert_target),
      enabled: !!team,
    })),
  })
  const planQueries = useQueries({
    queries: teamLearners.map((learner) => ({
      queryKey: ['plans', learner.learner_id],
      queryFn: () => api.listPlans(learner.learner_id),
      enabled: !!team,
    })),
  })
  const draftPlans = teamLearners.flatMap((learner, index) => {
    const allDrafts = (planQueries[index]?.data ?? [])
      .filter((p: DraftPlan) =>
        p.status !== 'approved' &&
        p.learner_id === learner.learner_id &&
        p.cert_id === learner.cert_target &&
        (p.total_planned_hours ?? 0) > 0 &&
        (p.weeks?.length ?? 0) > 0,
      )
      .sort((a: DraftPlan, b: DraftPlan) => (b.created_at ?? '').localeCompare(a.created_at ?? ''))
    const latest = allDrafts[0]
    return latest ? [{ ...latest, learner }] : []
  })

  const progressData = progressQueries.map((query) => query.data).filter(Boolean) as ProgressSnapshot[]
  const learnerById = new Map(teamLearners.map((learner) => [learner.learner_id, learner]))
  const memberContextById = new Map((insights?.members ?? []).map((member) => [member.employee_id, member]))
  const latestAttempts = progressData
    .map((progress) => progress.attempts[progress.attempts.length - 1])
    .filter(Boolean)
  const latestScores = progressData
    .map((progress) => progress.attempts[progress.attempts.length - 1]?.score_pct)
    .filter((score): score is number => typeof score === 'number')
  const improvingLearners = progressData.filter((progress) => {
    if (progress.attempts.length < 2) return false
    const latest = progress.attempts[progress.attempts.length - 1]
    const previous = progress.attempts[progress.attempts.length - 2]
    return latest.score_pct > previous.score_pct
  }).length
  const decliningLearners = progressData.filter((progress) => {
    if (progress.attempts.length < 2) return false
    const latest = progress.attempts[progress.attempts.length - 1]
    const previous = progress.attempts[progress.attempts.length - 2]
    return latest.score_pct < previous.score_pct
  }).length
  const noAttemptLearners = teamLearners.length - progressData.filter((progress) => progress.attempts.length > 0).length
  const passingLearners = latestAttempts.filter((attempt) => attempt.passed).length
  const belowThresholdLearners = latestAttempts.filter((attempt) => !attempt.passed).length
  const learnersNeedingActionDetails: NeedsActionDetail[] = teamLearners.flatMap((learner, index) => {
    const progress = progressQueries[index]?.data
    const latestAttempt = progress?.attempts[progress.attempts.length - 1]
    const reasons: string[] = []

    if (insights?.high_capacity_risk_members.includes(learner.learner_id)) {
      reasons.push('High capacity risk')
    }
    if (latestAttempt && !latestAttempt.passed) {
      reasons.push('Latest mock below threshold')
    }

    if (!reasons.length) {
      return []
    }

    const priority = getNeedsActionPriority(reasons)
    return [{ id: `intervention:${learner.learner_id}`, learner, reasons, latestAttempt, priority }]
  }).sort((left, right) => {
    if (right.priority.score !== left.priority.score) {
      return right.priority.score - left.priority.score
    }
    const leftScore = left.latestAttempt?.score_pct ?? Number.POSITIVE_INFINITY
    const rightScore = right.latestAttempt?.score_pct ?? Number.POSITIVE_INFINITY
    if (leftScore !== rightScore) {
      return leftScore - rightScore
    }
    return left.learner.learner_id.localeCompare(right.learner.learner_id)
  })
  const learnersNeedingActionById = new Map(learnersNeedingActionDetails.map((detail) => [detail.learner.learner_id, detail]))
  const interventionById = new Map(persistedInterventions.map((intervention) => [intervention.id, intervention]))
  const learnersNeedingActionNow = learnersNeedingActionDetails.length
  const momentumEntries = teamLearners
    .map((learner, index) => ({
      learner,
      progress: progressQueries[index]?.data,
      loading: progressQueries[index]?.isLoading ?? false,
      attention: learnersNeedingActionById.get(learner.learner_id),
    }))
    .sort((left, right) => {
      const leftPriority = left.attention?.priority.score ?? 0
      const rightPriority = right.attention?.priority.score ?? 0
      if (rightPriority !== leftPriority) {
        return rightPriority - leftPriority
      }
      const leftScore = left.progress?.attempts[left.progress.attempts.length - 1]?.score_pct ?? Number.POSITIVE_INFINITY
      const rightScore = right.progress?.attempts[right.progress.attempts.length - 1]?.score_pct ?? Number.POSITIVE_INFINITY
      if (leftScore !== rightScore) {
        return leftScore - rightScore
      }
      return left.learner.learner_id.localeCompare(right.learner.learner_id)
    })
  const peerLearningOpportunities: PeerLearningOpportunity[] = teamLearners.flatMap((learner, learnerIndex) => {
    const learnerMastery = masteryQueries[learnerIndex]?.data as MasteryGrid | undefined
    const learnerProgress = progressQueries[learnerIndex]?.data
    const learnerLatestScore = learnerProgress?.attempts[learnerProgress.attempts.length - 1]?.score_pct
    if (!learnerMastery?.domains.length) {
      return []
    }

    const weakestDomain = [...learnerMastery.domains].sort((left, right) => left.mastery_pct - right.mastery_pct)[0]
    const needsPeerSupport = learnerLatestScore === undefined
      ? weakestDomain.mastery_pct < 60
      : learnerLatestScore < 70
    if (!weakestDomain || !needsPeerSupport) {
      return []
    }

    const mentorCandidates = teamLearners.flatMap((candidate, candidateIndex) => {
      if (candidate.learner_id === learner.learner_id || candidate.cert_target !== learner.cert_target) {
        return []
      }

      const candidateMastery = masteryQueries[candidateIndex]?.data as MasteryGrid | undefined
      const candidateProgress = progressQueries[candidateIndex]?.data
      if (!candidateMastery?.domains.length) {
        return []
      }

      const matchingDomain = candidateMastery.domains.find((domain) => domain.domain_id === weakestDomain.domain_id)
      if (!matchingDomain) {
        return []
      }

      const strengthDelta = matchingDomain.mastery_pct - weakestDomain.mastery_pct
      if (strengthDelta < 8) {
        return []
      }

      const candidateLatestScore = candidateProgress?.attempts[candidateProgress.attempts.length - 1]?.score_pct ?? -1
      return [{
        mentor: candidate,
        matchingDomain,
        strengthDelta,
        candidateLatestScore,
      }]
    }).sort((left, right) => {
      if (right.strengthDelta !== left.strengthDelta) {
        return right.strengthDelta - left.strengthDelta
      }
      if (right.candidateLatestScore !== left.candidateLatestScore) {
        return right.candidateLatestScore - left.candidateLatestScore
      }
      return left.mentor.learner_id.localeCompare(right.mentor.learner_id)
    })

    const bestMentor = mentorCandidates[0]
    if (bestMentor) {
      const learnerSlots = memberContextById.get(learner.learner_id)?.recommended_slots
      const mentorSlots = memberContextById.get(bestMentor.mentor.learner_id)?.recommended_slots
      const suggestedSlot = findSharedStudySlot(learnerSlots, mentorSlots)

      return [{
        id: `${learner.learner_id}:${bestMentor.mentor.learner_id}:${weakestDomain.domain_id}`,
        learner,
        mentor: bestMentor.mentor,
        focusDomain: weakestDomain.name,
        mentorStrengthPct: Math.round(bestMentor.matchingDomain.mastery_pct),
        learnerGapPct: Math.round(weakestDomain.mastery_pct),
        suggestedSlot,
        rationale: `${bestMentor.mentor.learner_id} is currently stronger in ${weakestDomain.name.toLowerCase()} than ${learner.learner_id}.`,
        matchType: 'Same-cert mentor match',
      }]
    }

    const crossCertCandidates = teamLearners.flatMap((candidate, candidateIndex) => {
      if (candidate.learner_id === learner.learner_id) {
        return []
      }
      const candidateProgress = progressQueries[candidateIndex]?.data
      const candidateMastery = masteryQueries[candidateIndex]?.data as MasteryGrid | undefined
      const candidateLatestScore = candidateProgress?.attempts[candidateProgress.attempts.length - 1]?.score_pct ?? 0
      const candidateAverageMastery = candidateMastery?.domains.length
        ? candidateMastery.domains.reduce((sum, domain) => sum + domain.mastery_pct, 0) / candidateMastery.domains.length
        : 0
      const candidateContext = memberContextById.get(candidate.learner_id)
      return [{
        mentor: candidate,
        latestScore: candidateLatestScore,
        averageMastery: candidateAverageMastery,
        focusHours: candidateContext?.focus_hours_pw ?? 0,
      }]
    }).sort((left, right) => {
      if (right.latestScore !== left.latestScore) {
        return right.latestScore - left.latestScore
      }
      if (right.averageMastery !== left.averageMastery) {
        return right.averageMastery - left.averageMastery
      }
      return right.focusHours - left.focusHours
    })

    const crossCertMentor = crossCertCandidates[0]
    if (!crossCertMentor || crossCertMentor.latestScore < 70 && crossCertMentor.averageMastery < 70) {
      return []
    }
    const learnerSlots = memberContextById.get(learner.learner_id)?.recommended_slots
    const mentorSlots = memberContextById.get(crossCertMentor.mentor.learner_id)?.recommended_slots
    const suggestedSlot = findSharedStudySlot(learnerSlots, mentorSlots)
    const learnerAverageMastery = learnerMastery.domains.reduce((sum, domain) => sum + domain.mastery_pct, 0) / learnerMastery.domains.length

    return [{
      id: `${learner.learner_id}:${crossCertMentor.mentor.learner_id}:cross-cert`,
      learner,
      mentor: crossCertMentor.mentor,
      focusDomain: 'Exam rehearsal and study cadence',
      mentorStrengthPct: Math.round(Math.max(crossCertMentor.latestScore, crossCertMentor.averageMastery)),
      learnerGapPct: Math.round(Math.max(0, 100 - learnerAverageMastery)),
      suggestedSlot,
      rationale: `${crossCertMentor.mentor.learner_id} is the strongest available coach on study cadence and exam follow-through for ${learner.learner_id}.`,
      matchType: 'Cross-cert study-habit match',
    }]
  })
  const pinnedPeerOpportunityIds = new Set(persistedPeerSessions.map((session) => session.id))
  const managerHandoffBrief = buildManagerHandoffBrief(team, insights ?? {
    team_id: selectedTeam,
    summary: '',
    member_count: 0,
    average_meeting_hours_pw: 0,
    high_capacity_risk_members: [],
    readiness_distribution: {},
    capacity_conflicts: [],
    risk_areas: [],
    peer_learning_pairs: [],
    manager_actions: [],
    members: [],
    ai_disclosure: '',
  }, persistedInterventions, persistedPeerSessions)
  const averageLatestScore = latestScores.length
    ? `${Math.round(latestScores.reduce((sum, score) => sum + score, 0) / latestScores.length)}%`
    : 'No data'

  const copyManagerBrief = async () => {
    if (!navigator.clipboard) {
      return
    }
    await navigator.clipboard.writeText(managerHandoffBrief)
    setBriefCopied(true)
    window.setTimeout(() => setBriefCopied(false), 1500)
  }

  const approvalsCount = draftPlans.length + persistedInterventions.length
  const managerTabs = [
    { key: 'overview' as const, label: 'Overview', icon: <LayoutGrid size={15} /> },
    { key: 'approvals' as const, label: 'Approvals & Actions', icon: <UserCheck size={15} />, count: approvalsCount },
    { key: 'capacity' as const, label: 'Capacity & Simulator', icon: <Gauge size={15} /> },
    { key: 'peer' as const, label: 'Peer Learning', icon: <Users size={15} /> },
  ]

  return (
    <div className="mx-auto max-w-6xl space-y-5 p-6 scrollbar-dark">
      {/* Hero header */}
      <div className="panel panel-pad overflow-hidden p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <span className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-accent to-brand-600 shadow-glow">
              <Users size={22} className="text-white" />
            </span>
            <div>
              <p className="eyebrow">Team Command Center</p>
              <h1 className="text-xl font-bold tracking-tight text-ink">Manager Insights</h1>
              <p className="mt-0.5 text-xs text-ink-muted">
                {team?.team_name ?? selectedTeam} · {teamLearners.length} members · avg latest {averageLatestScore}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void copyManagerBrief()}
              className="btn-ghost text-xs"
            >
              {briefCopied ? '✓ Copied brief' : 'Copy handoff brief'}
            </button>
            <select
              value={selectedTeam}
              onChange={(e) => { setSelectedTeam(e.target.value); runWhatIf.reset() }}
              className="field-dark"
            >
              {teams.map((t) => (
                <option key={t.team_id} value={t.team_id}>{t.team_id} — {t.team_name}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Sub-tab navigation */}
        <div className="mt-4 flex flex-wrap gap-1.5 border-t border-line pt-4">
          {managerTabs.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setManagerTab(t.key)}
              className={clsx('subtab', managerTab === t.key && 'subtab-active')}
            >
              {t.icon}
              {t.label}
              {!!t.count && t.count > 0 && <span className="subtab-count">{t.count}</span>}
            </button>
          ))}
        </div>
      </div>

      <AIDisclosureBanner message="AI-generated team insights; verify before use in performance or HR decisions." />

      {isLoading && <p className="text-ink-subtle text-sm">Loading team insights…</p>}

      {managerTab === 'approvals' && draftPlans.length > 0 && (
        <div className="bg-surface-2 rounded-lg border border-amber-500/40 p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-amber-300 flex items-center gap-2">
                <UserCheck size={15} /> Plans Pending Your Approval
              </h2>
              <p className="text-xs text-ink-muted mt-0.5">Review AI-generated study plans before they go live for your team members.</p>
            </div>
            <span className="rounded-full bg-amber-500/15 px-2.5 py-1 text-xs font-medium text-amber-300">{draftPlans.length} pending</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {draftPlans.map((plan) => (
              <div key={`${plan.plan_id}:${plan.learner.learner_id}`} className="rounded-lg border border-amber-500/30 bg-amber-500/[0.06] p-4 space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-ink">{plan.learner.learner_id} — {plan.cert_id}</p>
                    <p className="text-xs text-ink-subtle font-mono mt-0.5">{plan.plan_id}</p>
                  </div>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 font-medium">Draft</span>
                </div>
                <div className="flex gap-4 text-xs text-ink-muted">
                  <span>{plan.total_planned_hours ?? 0}h total</span>
                  <span>{plan.weeks?.length ?? 0} weeks</span>
                  {plan.deadline && <span>Deadline: {plan.deadline}</span>}
                </div>
                <div className="space-y-1.5">
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => approvePlan.mutate(plan.plan_id)}
                      disabled={approvePlan.isPending}
                      className="text-xs px-3 py-1.5 rounded bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-60 font-medium"
                    >
                      {approvePlan.isPending ? 'Approving…' : '✓ Approve & Publish'}
                    </button>
                    <Link
                      to={`/?learner=${plan.learner.learner_id}&tab=plan&planId=${plan.plan_id}`}
                      className="text-xs px-3 py-1.5 rounded border border-amber-500/40 text-amber-300 hover:bg-amber-500/15 font-medium"
                    >
                      Review Plan
                    </Link>
                  </div>
                  {approveError && (
                    <p className="text-xs text-rose-300">{approveError}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {insights && (
        <>
          {managerTab === 'overview' && (<>
          <div className="panel p-4 space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="panel-title">Manager Briefing</h2>
                <p className="mt-1 text-sm text-ink-muted">{insights.summary}</p>
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="rounded-full bg-emerald-500/10 px-2.5 py-1 font-medium text-emerald-300">On track {insights.readiness_distribution.on_track ?? 0}</span>
                <span className="rounded-full bg-amber-500/10 px-2.5 py-1 font-medium text-amber-300">At risk {insights.readiness_distribution.at_risk ?? 0}</span>
                <span className="rounded-full bg-white/10 px-2.5 py-1 font-medium text-ink-muted">Insufficient evidence {insights.readiness_distribution.insufficient_evidence ?? 0}</span>
              </div>
            </div>
            {insights.roi_summary && (
              <div className="flex flex-wrap items-center gap-4 rounded-xl border border-emerald-500/30 bg-emerald-500/[0.06] px-4 py-3">
                <div className="shrink-0">
                  <p className="eyebrow text-emerald-300/80">ROI · Cost of delay</p>
                  <p className="text-2xl font-bold text-emerald-300">
                    ${insights.roi_summary.monthly_delay_cost_usd.toLocaleString()}<span className="text-sm font-medium text-ink-muted">/mo</span>
                  </p>
                </div>
                <div className="h-10 w-px bg-line-strong" />
                <div className="min-w-0 flex-1 text-xs text-ink-muted">
                  <p>{insights.roi_summary.narrative}</p>
                  <p className="mt-1 text-ink-subtle">
                    {insights.roi_summary.at_risk_headcount} at-risk · {insights.roi_summary.cert} uplift ${insights.roi_summary.cert_market_value_uplift_usd.toLocaleString()}/yr
                  </p>
                </div>
              </div>
            )}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-ink-subtle mb-2">Manager actions</p>
                <div className="space-y-2">
                  {insights.manager_actions.map((action) => (
                    <p key={action} className="rounded-lg bg-white/5 border border-line px-3 py-2 text-ink">{action}</p>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-ink-subtle mb-2">Risk areas</p>
                <div className="space-y-2">
                  {insights.risk_areas.map((risk) => (
                    <p key={risk} className="rounded-lg bg-amber-500/10 border border-amber-500/30 px-3 py-2 text-amber-300">{risk}</p>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-ink-subtle mb-2">Peer pair signals</p>
                <div className="space-y-2">
                  {insights.peer_learning_pairs.map((pair) => (
                    <p key={`${pair.learner_a}-${pair.learner_b}-${pair.gap}`} className="rounded-lg bg-blue-500/10 border border-blue-500/30 px-3 py-2 text-blue-300">
                      {pair.learner_a} can help {pair.learner_b} on {titleCaseLabel(pair.gap)}.
                    </p>
                  ))}
                </div>
              </div>
            </div>
          </div>
          </>)}

          {managerTab === 'capacity' && (<>
          <div className="panel panel-accent p-4 space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="panel-title">Counterfactual Readiness Simulator</h2>
                <p className="mt-1 text-sm text-ink-muted">Test a concrete manager action before committing to it. The simulator estimates workload relief, study-time gain, and target-learner exam movement.</p>
              </div>
              <span className="rounded-full bg-violet-500/10 px-2.5 py-1 text-xs font-medium text-violet-300">Standout reasoning</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3">
              <label className="text-xs text-ink-muted">
                Target learner
                <select
                  value={targetLearnerId}
                  onChange={(event) => setWhatIfForm((current) => ({ ...current, target_learner_id: event.target.value }))}
                  className="field-dark mt-1 w-full"
                >
                  {teamLearners.map((learner) => (
                    <option key={learner.learner_id} value={learner.learner_id}>{learner.learner_id}</option>
                  ))}
                </select>
              </label>

              <label className="text-xs text-ink-muted">
                Peer mentor
                <select
                  value={mentorLearnerId}
                  onChange={(event) => setWhatIfForm((current) => ({ ...current, peer_mentor_id: event.target.value }))}
                  className="field-dark mt-1 w-full"
                >
                  <option value="">No peer mentor</option>
                  {teamLearners
                    .filter((learner) => learner.learner_id !== targetLearnerId)
                    .map((learner) => (
                      <option key={learner.learner_id} value={learner.learner_id}>{learner.learner_id}</option>
                    ))}
                </select>
              </label>

              <label className="text-xs text-ink-muted">
                Protected focus hours
                <input
                  type="number"
                  min={0}
                  max={10}
                  step={1}
                  value={whatIfForm.protected_focus_hours}
                  onChange={(event) => setWhatIfForm((current) => ({ ...current, protected_focus_hours: Number(event.target.value) }))}
                  className="field-dark mt-1 w-full"
                />
              </label>

              <label className="text-xs text-ink-muted">
                Reduced meeting hours
                <input
                  type="number"
                  min={0}
                  max={10}
                  step={1}
                  value={whatIfForm.reduced_meeting_hours}
                  onChange={(event) => setWhatIfForm((current) => ({ ...current, reduced_meeting_hours: Number(event.target.value) }))}
                  className="field-dark mt-1 w-full"
                />
              </label>

              <label className="text-xs text-ink-muted">
                Review hours / week
                <div className="mt-1 flex gap-2">
                  <input
                    type="number"
                    min={0}
                    max={10}
                    step={1}
                    value={whatIfForm.targeted_review_hours}
                    onChange={(event) => setWhatIfForm((current) => ({ ...current, targeted_review_hours: Number(event.target.value) }))}
                    className="field-dark w-full"
                  />
                  <input
                    type="number"
                    min={1}
                    max={4}
                    step={1}
                    value={whatIfForm.peer_session_count}
                    onChange={(event) => setWhatIfForm((current) => ({ ...current, peer_session_count: Number(event.target.value) }))}
                    className="field-dark w-20"
                    aria-label="Peer session count"
                  />
                </div>
              </label>
            </div>

            <div className="flex items-center justify-between gap-3">
              <p className="text-xs text-ink-muted">The estimate blends current evidence, workload signals, and the likely lift from focused remediation.</p>
              <button
                type="button"
                onClick={() => runWhatIf.mutate({
                  ...whatIfForm,
                  target_learner_id: targetLearnerId,
                  peer_mentor_id: mentorLearnerId || undefined,
                })}
                disabled={!targetLearnerId || runWhatIf.isPending}
                className="text-sm px-3 py-2 rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-60"
              >
                {runWhatIf.isPending ? 'Simulating…' : 'Run what-if'}
              </button>
            </div>

            {runWhatIf.error && (
              <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-300">
                Unable to run the scenario. Check the selected learner inputs and try again.
              </div>
            )}

            {runWhatIf.data && (
              <div className="rounded-xl border border-violet-500/30 bg-violet-500/[0.06] p-4 space-y-4">
                <div>
                  <p className="text-sm font-semibold text-ink">Projected outcome</p>
                  <p className="mt-1 text-sm text-ink-muted">{runWhatIf.data.scenario_summary}</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
                  <div className="rounded-lg border border-line bg-surface-2 p-3">
                    <p className="text-xs text-ink-muted">Target score movement</p>
                    <p className="mt-1 text-lg font-semibold text-ink">
                      {runWhatIf.data.baseline.target_learner.estimated_exam_score} → {runWhatIf.data.projected.target_learner.estimated_exam_score}
                    </p>
                    <p className="text-xs text-violet-300">Threshold {runWhatIf.data.projected.target_learner.pass_threshold}</p>
                  </div>
                  <div className="rounded-lg border border-line bg-surface-2 p-3">
                    <p className="text-xs text-ink-muted">Readiness movement</p>
                    <p className="mt-1 text-lg font-semibold text-ink">
                      {runWhatIf.data.baseline.readiness_distribution.on_track} → {runWhatIf.data.projected.readiness_distribution.on_track}
                    </p>
                    <p className="text-xs text-emerald-300">On-track delta {runWhatIf.data.deltas.on_track >= 0 ? '+' : ''}{runWhatIf.data.deltas.on_track}</p>
                  </div>
                  <div className="rounded-lg border border-line bg-surface-2 p-3">
                    <p className="text-xs text-ink-muted">At-risk movement</p>
                    <p className="mt-1 text-lg font-semibold text-ink">
                      {runWhatIf.data.baseline.readiness_distribution.at_risk} → {runWhatIf.data.projected.readiness_distribution.at_risk}
                    </p>
                    <p className="text-xs text-amber-300">At-risk delta {runWhatIf.data.deltas.at_risk >= 0 ? '+' : ''}{runWhatIf.data.deltas.at_risk}</p>
                  </div>
                  <div className="rounded-lg border border-line bg-surface-2 p-3">
                    <p className="text-xs text-ink-muted">Capacity pressure</p>
                    <p className="mt-1 text-lg font-semibold text-ink">
                      {runWhatIf.data.baseline.high_capacity_risk_members.length} → {runWhatIf.data.projected.high_capacity_risk_members.length}
                    </p>
                    <p className="text-xs text-ink-muted">Risk delta {runWhatIf.data.deltas.high_capacity_risk >= 0 ? '+' : ''}{runWhatIf.data.deltas.high_capacity_risk}</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="rounded-lg border border-line bg-surface-2 p-4 space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-ink-subtle">Reasoning assumptions</p>
                    <div className="space-y-2">
                      {runWhatIf.data.assumptions.map((assumption) => (
                        <p key={assumption} className="rounded-lg bg-white/5 px-3 py-2 text-sm text-ink">{assumption}</p>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-lg border border-line bg-surface-2 p-4 space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-ink-subtle">Recommendation</p>
                    <p className="text-sm text-ink">{runWhatIf.data.recommended_action}</p>
                    <div className="grid grid-cols-2 gap-3 pt-2 text-xs text-ink-muted">
                      <div>
                        <p className="text-ink-subtle">Weakest topic</p>
                        <p className="font-medium text-ink">{titleCaseLabel(runWhatIf.data.projected.target_learner.weakest_topic ?? 'insufficient_evidence')}</p>
                      </div>
                      <div>
                        <p className="text-ink-subtle">Available study hours</p>
                        <p className="font-medium text-ink">{runWhatIf.data.projected.target_learner.available_study_hours_pw}h / week</p>
                      </div>
                      <div>
                        <p className="text-ink-subtle">Meeting load</p>
                        <p className="font-medium text-ink">{runWhatIf.data.projected.target_learner.meeting_hours_pw}h / week</p>
                      </div>
                      <div>
                        <p className="text-ink-subtle">Focus time</p>
                        <p className="font-medium text-ink">{runWhatIf.data.projected.target_learner.focus_hours_pw}h / week</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          </>)}

          {managerTab === 'overview' && (<>
          {/* Summary stats */}
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-9 gap-4">
            {[
              { label: 'Team members', value: insights.member_count },
              { label: 'Avg meeting hrs/wk', value: `${insights.average_meeting_hours_pw}h` },
              { label: 'High capacity risk', value: insights.high_capacity_risk_members.length },
              { label: 'Needs action now', value: learnersNeedingActionNow, interactive: true },
              { label: 'Avg latest mock score', value: averageLatestScore },
              { label: 'Passing learners', value: passingLearners },
              { label: 'Below threshold', value: belowThresholdLearners },
              { label: 'Improving learners', value: improvingLearners },
              { label: 'No mock attempts', value: noAttemptLearners },
            ].map((s) => {
              const isNeedsAction = s.label === 'Needs action now'
              const isActive = isNeedsAction && showNeedsAction

              if (isNeedsAction) {
                return (
                  <button
                    key={s.label}
                    type="button"
                    onClick={() => setShowNeedsAction((current) => !current)}
                    className={clsx(
                      'rounded-lg border p-4 text-center transition text-left',
                      isActive ? 'border-amber-500/40 bg-amber-500/10' : 'border-line bg-surface-2 hover:border-amber-500/30 hover:bg-amber-500/[0.08]',
                    )}
                  >
                    <p className="text-2xl font-bold text-ink text-center">{s.value}</p>
                    <p className="text-xs text-ink-muted mt-1 text-center">{s.label}</p>
                    <p className="mt-2 text-[11px] text-amber-300 text-center font-medium">
                      {learnersNeedingActionNow > 0 ? 'Click to view flagged learners' : 'No learners currently flagged'}
                    </p>
                  </button>
                )
              }

              return (
                <div key={s.label} className="bg-surface-2 rounded-lg border border-line p-4 text-center">
                  <p className="text-2xl font-bold text-ink">{s.value}</p>
                  <p className="text-xs text-ink-muted mt-1">{s.label}</p>
                </div>
              )
            })}
          </div>

          {showNeedsAction && learnersNeedingActionNow > 0 && (
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold text-amber-300">Needs Action Now</h2>
                  <p className="text-xs text-amber-300">Learners flagged by workload risk, recent mock performance, or both.</p>
                </div>
                <button
                  type="button"
                  onClick={() => setShowNeedsAction(false)}
                  className="text-xs font-medium text-amber-300 hover:text-amber-300"
                >
                  Hide
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {learnersNeedingActionDetails.map(({ id, learner, reasons, latestAttempt, priority }) => (
                  <div key={learner.learner_id} className="rounded-lg border border-amber-500/30 bg-surface-2 p-4 space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-mono text-sm text-ink">{learner.learner_id}</p>
                        <p className="text-xs text-ink-muted">{learner.cert_target} · {learner.role}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={clsx('rounded-full px-2 py-0.5 text-xs font-medium', priority.tone)}>
                          {priority.label}
                        </span>
                        {latestAttempt && (
                          <span className={clsx(
                            'rounded-full px-2 py-0.5 text-xs font-medium',
                            latestAttempt.passed ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-300',
                          )}>
                            {latestAttempt.score_pct}%
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {reasons.map((reason) => (
                        <span key={reason} className="rounded-full bg-amber-500/15 px-2 py-0.5 text-xs font-medium text-amber-300">
                          {reason}
                        </span>
                      ))}
                    </div>
                    <div className="flex items-center justify-between gap-3 text-xs text-ink-muted">
                      <span>{interventionById.get(id)?.owner_id ? `Owner: ${interventionById.get(id)?.owner_id}` : 'Not pinned to intervention queue'}</span>
                      <span>{interventionById.get(id)?._updated_at ? `Updated ${formatWorkflowTimestamp(interventionById.get(id)?._updated_at)}` : 'Not saved yet'}</span>
                    </div>
                    <div className="flex gap-2 pt-1">
                      <button
                        type="button"
                        onClick={() => saveIntervention.mutate({
                          id,
                          learner_id: learner.learner_id,
                          priority: priority.label.toLowerCase(),
                          reasons,
                          owner_id: managerOwnerId,
                          status: interventionById.get(id)?.status ?? 'planned',
                          manager_note: interventionById.get(id)?.manager_note ?? '',
                        })}
                        className={clsx(
                          'text-xs px-2 py-1 rounded font-medium',
                          interventionById.get(id)
                            ? 'bg-emerald-500/15 text-emerald-300'
                            : 'bg-surface-2 border border-amber-500/30 text-amber-300 hover:bg-amber-500/15',
                        )}
                      >
                        {interventionById.get(id) ? 'Pinned to queue' : 'Pin intervention'}
                      </button>
                      <Link
                        to={`/?learner=${learner.learner_id}&tab=readiness`}
                        className="text-xs px-2 py-1 rounded bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/15 font-medium"
                      >
                        Open Readiness
                      </Link>
                      <Link
                        to={`/?learner=${learner.learner_id}&tab=progress`}
                        className="text-xs px-2 py-1 rounded bg-blue-500/10 text-blue-300 hover:bg-blue-500/15 font-medium"
                      >
                        Open Progress
                      </Link>
                      <Link
                        to={`/?learner=${learner.learner_id}&tab=assessment`}
                        className="text-xs px-2 py-1 rounded bg-amber-500/10 text-amber-300 hover:bg-amber-500/15 font-medium"
                      >
                        Open Mock Exam
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          </>)}

          {managerTab === 'approvals' && (<>
          {persistedInterventions.length > 0 && (
            <div className="panel panel-rose p-4 space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="panel-title">Manager Intervention Queue</h2>
                  <p className="text-xs text-ink-muted">Pinned at-risk learners tracked with status, notes, and owner.</p>
                </div>
                <span className="rounded-full bg-rose-500/10 px-2.5 py-1 text-xs font-medium text-rose-300">{persistedInterventions.length} active</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {persistedInterventions.map((intervention) => {
                  const interventionLearner = learnerById.get(intervention.learner_id)
                  const draft = interventionDrafts[intervention.id] ?? { status: intervention.status, manager_note: intervention.manager_note }
                  return (
                    <div key={intervention.id} className="rounded-lg border border-rose-500/30 bg-rose-500/[0.06] p-4 space-y-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-ink">{intervention.learner_id}</p>
                          <p className="text-xs text-ink-muted">{interventionLearner?.cert_target ?? 'Unknown cert'} · {titleCaseLabel(intervention.priority)}</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => deleteIntervention.mutate(intervention.id)}
                          className="text-xs font-medium text-rose-300 hover:text-rose-200"
                        >
                          Remove
                        </button>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {intervention.reasons.map((reason) => (
                          <span key={reason} className="rounded-full bg-surface-2 px-2 py-0.5 text-xs font-medium text-rose-300 border border-rose-500/30">
                            {reason}
                          </span>
                        ))}
                      </div>
                      <div className="grid grid-cols-2 gap-3 text-xs text-ink-muted">
                        <div>
                          <p className="text-ink-subtle">Owner</p>
                          <p className="font-medium text-ink">{intervention.owner_id}</p>
                        </div>
                        <div>
                          <p className="text-ink-subtle">Last updated</p>
                          <p className="font-medium text-ink">{formatWorkflowTimestamp(intervention._updated_at ?? intervention.created_at)}</p>
                        </div>
                      </div>
                      <label className="block text-xs text-ink-muted">
                        Status
                        <select
                          value={draft.status}
                          onChange={(event) => setInterventionDrafts((current) => ({ ...current, [intervention.id]: { ...draft, status: event.target.value } }))}
                          className="field-dark mt-1 w-full"
                        >
                          <option value="planned">Planned</option>
                          <option value="in_progress">In progress</option>
                          <option value="completed">Completed</option>
                        </select>
                      </label>
                      <label className="block text-xs text-ink-muted">
                        Manager note
                        <textarea
                          value={draft.manager_note}
                          onChange={(event) => setInterventionDrafts((current) => ({ ...current, [intervention.id]: { ...draft, manager_note: event.target.value } }))}
                          rows={2}
                          className="field-dark mt-1 w-full"
                        />
                      </label>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => saveIntervention.mutate({ ...intervention, status: draft.status, manager_note: draft.manager_note })}
                          className="text-xs px-2 py-1 rounded bg-rose-500/15 text-rose-300 hover:bg-rose-500/20 font-medium"
                        >
                          Save intervention
                        </button>
                        <Link
                          to={`/?learner=${intervention.learner_id}&tab=readiness`}
                          className="text-xs px-2 py-1 rounded bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/15 font-medium"
                        >
                          Open Readiness
                        </Link>
                        <Link
                          to={`/?learner=${intervention.learner_id}&tab=assessment`}
                          className="text-xs px-2 py-1 rounded bg-amber-500/10 text-amber-300 hover:bg-amber-500/15 font-medium"
                        >
                          Open Mock Exam
                        </Link>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          </>)}

          {managerTab === 'overview' && (<>
          {decliningLearners > 0 && (
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4">
              <p className="text-sm text-amber-300 font-medium">
                {decliningLearners} learner{decliningLearners === 1 ? '' : 's'} {decliningLearners === 1 ? 'is' : 'are'} trending down on recent mock attempts.
              </p>
            </div>
          )}

          </>)}

          {managerTab === 'capacity' && (<>
          {/* High risk members */}
          {insights.high_capacity_risk_members.length > 0 && (
            <div className="bg-rose-500/10 border border-rose-500/30 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-rose-300 flex items-center gap-2 mb-2">
                <AlertTriangle size={15} /> Capacity conflicts flagged
              </h3>
              <p className="text-sm text-rose-300">
                {insights.high_capacity_risk_members.join(', ')} {insights.high_capacity_risk_members.length === 1 ? 'has' : 'have'} high meeting loads (&gt;25h/wk).
                Consider schedule adjustments before certification deadlines.
              </p>
            </div>
          )}

          {/* Member cards */}
          <div>
            <h2 className="text-sm font-semibold text-ink mb-3">Team Members — Work Context</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {insights.members.map((m) => <CapacityCard key={m.employee_id} member={m} />)}
            </div>
          </div>

          </>)}

          {managerTab === 'overview' && (<>
          <div>
            <h2 className="panel-title mb-3">Certification Momentum</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {momentumEntries.map(({ learner, progress, loading, attention }) => (
                <MomentumCard
                  key={learner.learner_id}
                  learner={learner}
                  progress={progress}
                  loading={loading}
                  attention={attention}
                />
              ))}
            </div>
          </div>

          {/* Cert targets */}
          {team && (
            <div className="bg-surface-2 rounded-lg border border-line p-4">
              <h2 className="text-sm font-semibold text-ink mb-2">Team Certification Targets</h2>
              <div className="flex flex-wrap gap-2">
                {team.cert_targets.map((c) => (
                  <span key={c} className="bg-blue-500/10 text-blue-300 text-xs px-3 py-1 rounded-full font-medium">{c}</span>
                ))}
              </div>
              <p className="text-xs text-ink-subtle mt-2">{team.quarter_goal}</p>
            </div>
          )}

          </>)}

          {managerTab === 'peer' && (<>
          <div className="panel p-4 space-y-4">
            <h2 className="panel-title mb-2">
              <HelpCircle size={14} className="inline mr-1 text-blue-300" />
              Peer Learning Opportunities
            </h2>
            {persistedPeerSessions.length > 0 && (
              <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold text-emerald-300">Manager Follow-up Queue</h3>
                    <p className="text-xs text-emerald-300">Pinned peer-learning sessions ready for follow-through.</p>
                  </div>
                  <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs font-medium text-emerald-300">
                    {persistedPeerSessions.length} pinned
                  </span>
                </div>
                <div className="space-y-3">
                  {persistedPeerSessions.map((session) => (
                    <div key={`pinned-${session.id}`} className="rounded-lg border border-emerald-500/30 bg-surface-2 p-3 space-y-2">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-ink">{session.mentor_id} coaching {session.learner_id}</p>
                          <p className="text-xs text-ink-muted">{session.focus_domain} · {session.suggested_slot ?? 'Schedule next shared slot manually'}</p>
                          <p className="mt-1 text-[11px] text-ink-subtle">Owner {session.owner_id} · Updated {formatWorkflowTimestamp(session._updated_at ?? session.created_at)}</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => deletePeerSession.mutate(session.id)}
                          className="text-xs font-medium text-emerald-300 hover:text-emerald-200"
                        >
                          Remove
                        </button>
                      </div>
                      <div className="grid grid-cols-2 gap-3 text-xs text-ink-muted">
                        <div>
                          <p className="text-ink-subtle">Status</p>
                          <p className="font-medium text-ink">{titleCaseLabel(session.status ?? 'pinned')}</p>
                        </div>
                        <div>
                          <p className="text-ink-subtle">Manager note</p>
                          <p className="font-medium text-ink">{session.manager_note || 'No note yet'}</p>
                        </div>
                      </div>
                      <label className="block text-xs text-ink-muted">
                        Session status
                        <select
                          value={(peerSessionDrafts[session.id] ?? { status: session.status, manager_note: session.manager_note }).status}
                          onChange={(event) => setPeerSessionDrafts((current) => ({
                            ...current,
                            [session.id]: {
                              status: event.target.value,
                              manager_note: (current[session.id]?.manager_note ?? session.manager_note),
                            },
                          }))}
                          className="field-dark mt-1 w-full"
                        >
                          <option value="planned">Planned</option>
                          <option value="in_progress">In progress</option>
                          <option value="completed">Completed</option>
                        </select>
                      </label>
                      <label className="block text-xs text-ink-muted">
                        Manager note
                        <textarea
                          value={(peerSessionDrafts[session.id] ?? { status: session.status, manager_note: session.manager_note }).manager_note}
                          onChange={(event) => setPeerSessionDrafts((current) => ({
                            ...current,
                            [session.id]: {
                              status: current[session.id]?.status ?? session.status,
                              manager_note: event.target.value,
                            },
                          }))}
                          rows={2}
                          className="field-dark mt-1 w-full"
                        />
                      </label>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            const draft = peerSessionDrafts[session.id] ?? { status: session.status, manager_note: session.manager_note }
                            savePeerSession.mutate({
                              id: session.id,
                              mentor_id: session.mentor_id,
                              learner_id: session.learner_id,
                              cert_id: session.cert_id,
                              focus_domain: session.focus_domain,
                              suggested_slot: session.suggested_slot,
                              rationale: session.rationale,
                              owner_id: session.owner_id,
                              status: draft.status,
                              manager_note: draft.manager_note,
                            })
                          }}
                          className="text-xs px-2 py-1 rounded bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/20 font-medium"
                        >
                          Save session
                        </button>
                        <Link
                          to={`/?learner=${session.mentor_id}&tab=readiness`}
                          className="text-xs px-2 py-1 rounded bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/15 font-medium"
                        >
                          Review Mentor Readiness
                        </Link>
                        <Link
                          to={`/?learner=${session.learner_id}&tab=progress`}
                          className="text-xs px-2 py-1 rounded bg-blue-500/10 text-blue-300 hover:bg-blue-500/15 font-medium"
                        >
                          Review Learner Progress
                        </Link>
                        <Link
                          to={`/?learner=${session.learner_id}&tab=assessment`}
                          className="text-xs px-2 py-1 rounded bg-amber-500/10 text-amber-300 hover:bg-amber-500/15 font-medium"
                        >
                          Queue Next Mock Exam
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {peerLearningOpportunities.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {peerLearningOpportunities.map((opportunity) => (
                  <div key={opportunity.id} className="rounded-lg border border-blue-500/30 bg-blue-500/[0.06] p-4 space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-ink">
                          Pair {opportunity.mentor.learner_id} with {opportunity.learner.learner_id}
                        </p>
                        <p className="text-xs text-ink-muted">{opportunity.matchType} · {opportunity.learner.cert_target === opportunity.mentor.cert_target ? `Shared cert target: ${opportunity.learner.cert_target}` : `Cross-cert support: ${opportunity.mentor.cert_target} to ${opportunity.learner.cert_target}`}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="rounded-full bg-blue-500/15 px-2 py-0.5 text-xs font-medium text-blue-300">
                          {opportunity.matchType}
                        </span>
                        <button
                          type="button"
                          onClick={() => savePeerSession.mutate({
                            id: opportunity.id,
                            mentor_id: opportunity.mentor.learner_id,
                            learner_id: opportunity.learner.learner_id,
                            cert_id: opportunity.learner.cert_target,
                            focus_domain: opportunity.focusDomain,
                            suggested_slot: opportunity.suggestedSlot,
                            rationale: opportunity.rationale,
                            owner_id: managerOwnerId,
                            status: 'planned',
                            manager_note: '',
                          })}
                          className={clsx(
                            'rounded-full px-2 py-0.5 text-xs font-medium',
                            pinnedPeerOpportunityIds.has(opportunity.id)
                              ? 'bg-emerald-500/15 text-emerald-300'
                              : 'border border-line bg-surface-2 text-ink hover:border-accent hover:text-blue-300',
                          )}
                        >
                          {pinnedPeerOpportunityIds.has(opportunity.id) ? 'Pinned' : 'Pin session'}
                        </button>
                      </div>
                    </div>
                    <div className="space-y-1 text-sm text-ink">
                      <p><span className="font-medium text-ink">Focus domain:</span> {opportunity.focusDomain}</p>
                      <p><span className="font-medium text-ink">Why this pair:</span> {opportunity.rationale}</p>
                      <p><span className="font-medium text-ink">Suggested session:</span> {opportunity.suggestedSlot ?? 'Use the next available study slot from either learner.'}</p>
                      {opportunity.exchangeFocus && (
                        <p><span className="font-medium text-ink">Reciprocal exchange:</span> {opportunity.learner.learner_id} can give back support on {opportunity.exchangeFocus}.</p>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div className="rounded-lg bg-surface-2 border border-line p-3">
                        <p className="text-ink-subtle">Mentor strength</p>
                        <p className="font-semibold text-ink">{opportunity.mentor.learner_id} · {opportunity.mentorStrengthPct}%</p>
                        <p className="text-ink-muted mt-1">Strongest relevant domain coverage for this pairing.</p>
                      </div>
                      <div className="rounded-lg bg-surface-2 border border-line p-3">
                        <p className="text-ink-subtle">Learner gap</p>
                        <p className="font-semibold text-ink">{opportunity.learner.learner_id} · {opportunity.learnerGapPct}%</p>
                        <p className="text-ink-muted mt-1">Current weakest same-cert domain to target first.</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2 pt-1">
                      <Link
                        to={`/?learner=${opportunity.mentor.learner_id}&tab=readiness`}
                        className="text-xs px-2 py-1 rounded bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/15 font-medium"
                      >
                        Open Mentor Readiness
                      </Link>
                      <Link
                        to={`/?learner=${opportunity.learner.learner_id}&tab=progress`}
                        className="text-xs px-2 py-1 rounded bg-blue-500/10 text-blue-300 hover:bg-blue-500/15 font-medium"
                      >
                        Open Learner Progress
                      </Link>
                      <Link
                        to={`/?learner=${opportunity.learner.learner_id}&tab=assessment`}
                        className="text-xs px-2 py-1 rounded bg-amber-500/10 text-amber-300 hover:bg-amber-500/15 font-medium"
                      >
                        Open Next Mock Exam
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-ink-muted">
                No peer-learning match is ready yet. Add another learner attempt or switch teams to surface either same-cert mentoring or cross-cert study-habit coaching.
              </p>
            )}
          </div>
          </>)}

          <p className="text-xs text-ink-subtle">{insights.ai_disclosure}</p>
        </>
      )}
    </div>
  )
}
