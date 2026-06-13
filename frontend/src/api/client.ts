const BASE = '/api'

export async function fetchJSON<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`)
  if (!r.ok) throw new Error(`API error ${r.status}: ${path}`)
  return r.json()
}

export async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`API error ${r.status}: ${path}`)
  return r.json()
}

export async function postNoBodyJSON<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: 'POST',
  })
  if (!r.ok) throw new Error(`API error ${r.status}: ${path}`)
  return r.json()
}

export async function deleteJSON<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: 'DELETE',
  })
  if (!r.ok) throw new Error(`API error ${r.status}: ${path}`)
  return r.json()
}

export function streamEvents(runId: string, onEvent: (e: unknown) => void): () => void {
  const es = new EventSource(`/api/workflow/${runId}/stream`)
  es.onmessage = (e) => {
    try { onEvent(JSON.parse(e.data)) } catch { /* ignore malformed */ }
  }
  es.onerror = () => es.close()
  return () => es.close()
}

// API helpers
export const api = {
  learners: () => fetchJSON<Learner[]>('/learners'),
  learner: (id: string) => fetchJSON<Learner>(`/learners/${id}`),
  teams: () => fetchJSON<Team[]>('/teams'),
  runWorkflow: (learner_id: string) => postJSON<{ run_id: string }>('/workflow/run', { learner_id }),
  approvePlan: (plan_id: string) => postJSON('/plans/approve', { plan_id, approved_by: 'manager' }),
  listPlans: (lid: string) => fetchJSON<DraftPlan[]>(`/plans/${lid}`),
  getPlan: (planId: string) => fetchJSON<DraftPlan>(`/plan/${planId}`),
  getTrace: (runId: string) => fetchJSON<{ run_id: string; events: TraceEvent[] }>(`/workflow/${runId}/trace`),
  listTraces: (learnerId: string) => fetchJSON<{ run_id: string; learner_id: string; events: TraceEvent[]; started_at?: string }[]>(`/traces/${learnerId}`),
  progress: (lid: string, cid: string) => fetchJSON<ProgressSnapshot>(`/progress/${lid}/${cid}`),
  mastery: (lid: string, cid: string) => fetchJSON<MasteryGrid>(`/mastery/${lid}/${cid}`),
  forecast: (lid: string, cid: string) => fetchJSON<Forecast>(`/forecast/${lid}/${cid}`),
  evalSummary: () => fetchJSON<EvalSummary>('/eval/summary'),
  generateAssessment: (lid: string, cid: string, difficulty?: string, count = 20) => {
    const diff = difficulty && difficulty !== 'Mixed' ? `&difficulty=${difficulty}` : ''
    return postNoBodyJSON<Assessment>(
      `/assessment/generate?learner_id=${lid}&cert_id=${cid}&question_count=${count}${diff}`,
    )
  },
  submitAssessment: (body: { assessment_id: string; learner_id: string; cert_id: string; answers: Record<string, number> }) => (
    postJSON<AssessmentResult>('/assessment/submit', body)
  ),
  certStructure: (cid: string) => fetchJSON<CertStructure>(`/cert-structures/${cid}`),
  audioConcepts: (lid: string, cid: string) => fetchJSON<AudioConcepts>(`/audio/concepts/${lid}/${cid}`),
  audioTranscript: (lid: string, cid: string, focus?: string) => fetchJSON<AudioTranscript>(
    `/audio/learner/${lid}/${cid}/transcript${focus ? `?focus=${encodeURIComponent(focus)}` : ''}`),
  audioUrl: (lid: string, cid: string, focus?: string) =>
    `/api/audio/learner/${lid}/${cid}.mp3${focus ? `?focus=${encodeURIComponent(focus)}` : ''}`,
  raiStatus: () => fetchJSON<RAIStatus>('/rai/status'),
  groundednessEval: (runId: string) => fetchJSON<GroundednessEval>(`/evals/groundedness/${runId}`),
  rubricEval: (runId: string) => fetchJSON<RubricEval>(`/evals/rubric/${runId}`),
  managerInsights: (tid: string) => fetchJSON<TeamInsights>(`/manager/${tid}/insights`),
  managerWhatIf: (tid: string, body: ManagerWhatIfRequest) => postJSON<ManagerWhatIfResult>(`/manager/${tid}/what-if`, body),
  peerSessions: (tid: string) => fetchJSON<PeerLearningSession[]>(`/manager/${tid}/peer-sessions`),
  savePeerSession: (tid: string, body: PeerLearningSessionRequest) => postJSON<PeerLearningSession>(`/manager/${tid}/peer-sessions`, body),
  deletePeerSession: (tid: string, sessionId: string) => deleteJSON<{ status: string; id: string }>(`/manager/${tid}/peer-sessions/${sessionId}`),
  interventions: (tid: string) => fetchJSON<ManagerIntervention[]>(`/manager/${tid}/interventions`),
  saveIntervention: (tid: string, body: ManagerInterventionRequest) => postJSON<ManagerIntervention>(`/manager/${tid}/interventions`, body),
  deleteIntervention: (tid: string, interventionId: string) => deleteJSON<{ status: string; id: string }>(`/manager/${tid}/interventions/${interventionId}`),
}

// ── Types ──────────────────────────────────────────────────────────────────

export interface Learner {
  learner_id: string
  display_name: string
  role: string
  team_id: string
  cert_target: string
  deadline: string
}

export interface Team {
  team_id: string
  team_name: string
  manager_id: string
  members: string[]
  cert_targets: string[]
  quarter_goal?: string
}

export interface PodcastTurn {
  speaker: 'host_a' | 'host_b'
  text: string
}

export interface PodcastScript {
  title: string
  cert_id: string
  learner_id: string
  mode?: string
  focus?: string
  is_weakest?: boolean
  turns: PodcastTurn[]
  citations: string[]
  ai_disclosure: string
}

export interface AudioTranscript {
  script: PodcastScript
  audio_available: boolean
}

export interface AudioConcept {
  domain_id: string
  name: string
  weight_pct: number
  services: string[]
  mastery_pct: number | null
  is_weakest: boolean
}

export interface AudioConcepts {
  cert_id: string
  weakest_domain_id: string
  concepts: AudioConcept[]
}

export interface DomainMastery {
  domain_id: string
  name: string
  weight_pct: number
  mastery_pct: number
  confidence: number
  evidence_count: number
  flag: string
  services: ServiceCell[]
}

export interface ServiceCell {
  service_id: string
  service_name: string
  mastery_pct: number
  evidence_count: number
  status: string
}

export interface MasteryGrid {
  learner_id: string
  cert_id: string
  updated_at: string
  domains: DomainMastery[]
  pass_threshold: number
}

export interface Forecast {
  learner_id: string
  cert_id: string
  pass_probability: number
  confidence_interval_lower: number
  confidence_interval_upper: number
  estimated_exam_score: number
  pass_threshold: number
  points_below_threshold: number
  weakest_topic: string
  minimum_additional_hours: number
  insufficient_evidence: boolean
  calibrated?: {
    insufficient_evidence: boolean
    pass_probability?: number
    verdict?: string
  }
}

export interface EvalSummary {
  readiness_model: { auc_loo: number; brier_loo: number; n: number }
  red_team: { held: number; total: number; attack_success_rate: number }
  content_safety: string
}

export interface ProgressPoint {
  week: number
  planned_topics: number
  actual_topics: number
  status: string
}

export interface AssessmentAttempt {
  attempt_number: number
  assessment_id: string
  submitted_at: string
  score_pct: number
  estimated_exam_score: number
  passed: boolean
  difficulty: string
  question_count: number
}

export interface ProgressSnapshot {
  learner_id: string
  cert_id: string
  plan_id: string
  series: ProgressPoint[]
  attempts: AssessmentAttempt[]
}

export interface Question {
  question_id: string
  domain: string
  question_text: string
  options: string[]
  // Answer key is withheld from the client; scored server-side on submit.
  correct_index?: number
  explanation?: string
  difficulty: string
}

export interface Assessment {
  assessment_id: string
  learner_id: string
  cert_id: string
  questions: Question[]
  time_limit_minutes: number
}

export interface AssessmentResult {
  assessment_id: string
  learner_id: string
  score_pct: number
  questions_scored: number
  estimated_exam_score: number
  pass_threshold: number
  passed: boolean
  booking_verdict?: 'GO' | 'CONDITIONAL_GO' | 'NOT_YET'
  forecast?: Forecast
  ai_disclosure: string
}

export interface CertStructure {
  cert_id: string
  cert_name: string
  recommended_study_hours: number
  passing_score: number
  domains: { domain_id: string; name: string; weight_pct: number; services: string[] }[]
}

export interface TeamInsights {
  team_id: string
  summary: string
  member_count: number
  average_meeting_hours_pw: number
  high_capacity_risk_members: string[]
  readiness_distribution: Record<string, number>
  capacity_conflicts: string[]
  risk_areas: string[]
  peer_learning_pairs: PeerLearningPair[]
  manager_actions: string[]
  members: MemberContext[]
  roi_summary?: {
    at_risk_headcount: number
    cert: string
    cert_market_value_uplift_usd: number
    monthly_delay_cost_usd: number
    narrative: string
  }
  ai_disclosure: string
}

export interface ManagerWhatIfRequest {
  target_learner_id: string
  protected_focus_hours: number
  reduced_meeting_hours: number
  targeted_review_hours: number
  peer_mentor_id?: string
  peer_session_count: number
}

export interface ManagerWhatIfLearnerSnapshot {
  learner_id: string
  bucket: string
  estimated_exam_score: number
  pass_threshold: number
  weakest_topic?: string | null
  available_study_hours_pw: number
  meeting_hours_pw: number
  focus_hours_pw: number
}

export interface ManagerWhatIfProjection {
  summary: string
  readiness_distribution: Record<string, number>
  high_capacity_risk_members: string[]
  learner_snapshots: ManagerWhatIfLearnerSnapshot[]
  target_learner: ManagerWhatIfLearnerSnapshot
}

export interface ManagerWhatIfResult {
  team_id: string
  scenario_summary: string
  assumptions: string[]
  baseline: ManagerWhatIfProjection
  projected: ManagerWhatIfProjection
  deltas: Record<string, number>
  recommended_action: string
}

export interface PeerLearningPair {
  learner_a: string
  strength: string
  learner_b: string
  gap: string
  match_type?: string
}

export interface PeerLearningSessionRequest {
  id: string
  mentor_id: string
  learner_id: string
  cert_id: string
  focus_domain: string
  suggested_slot?: string
  rationale: string
  owner_id: string
  status: string
  manager_note: string
}

export interface PeerLearningSession extends PeerLearningSessionRequest {
  team_id: string
  created_at?: string
  _updated_at?: string
}

export interface ManagerInterventionRequest {
  id: string
  learner_id: string
  priority: string
  reasons: string[]
  owner_id: string
  status: string
  manager_note: string
}

export interface ManagerIntervention extends ManagerInterventionRequest {
  team_id: string
  created_at?: string
  _updated_at?: string
}

export interface MemberContext {
  employee_id: string
  meeting_hours_pw: number
  focus_hours_pw: number
  capacity_risk: string
  recommended_slots: string[]
}

export interface DraftPlan {
  plan_id: string
  learner_id: string
  cert_id: string
  status?: string
  deadline?: string
  total_planned_hours?: number
  weeks?: { week: number; topics: { title: string }[]; planned_hours: number }[]
  created_at?: string
}

export interface TraceEvent {
  event_id: string
  run_id: string
  timestamp: string
  event_type: string
  agent_name: string
  data: Record<string, unknown>
}

export interface RAIControl {
  control: string
  mode: string
  active: boolean
  detail: string
  categories?: string[]
}

export interface RAIStatus {
  rai_controls: RAIControl[]
  ai_disclosure: string
  model_backend: string
  content_safety_threshold: number
}

export interface GroundednessEval {
  run_id: string
  groundedness_score: number
  passed: boolean
  citation_count: number
  assertion_count: number
  uncited_sample: string[]
  evaluator: string
  note: string
}

export interface RubricCheck {
  id: string
  description: string
  passed: boolean
}

export interface RubricAgentResult {
  score: number
  passed: boolean
  checks: RubricCheck[]
}

export interface RubricEval {
  results: Record<string, RubricAgentResult>
  mean_score: number
  all_passed: boolean
  threshold: number
}
