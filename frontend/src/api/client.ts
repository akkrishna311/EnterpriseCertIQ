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
  approvePlan: (plan_id: string) => postJSON('/plans/approve', { plan_id, approved_by: 'human' }),
  mastery: (lid: string, cid: string) => fetchJSON<MasteryGrid>(`/mastery/${lid}/${cid}`),
  forecast: (lid: string, cid: string) => fetchJSON<Forecast>(`/forecast/${lid}/${cid}`),
  generateAssessment: (lid: string, cid: string, difficulty?: string, count = 20) => {
    const diff = difficulty && difficulty !== 'Mixed' ? `&difficulty=${difficulty}` : ''
    return postNoBodyJSON<Assessment>(
      `/assessment/generate?learner_id=${lid}&cert_id=${cid}&question_count=${count}${diff}`,
    )
  },
  certStructure: (cid: string) => fetchJSON<CertStructure>(`/cert-structures/${cid}`),
  managerInsights: (tid: string) => fetchJSON<TeamInsights>(`/manager/${tid}/insights`),
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

export interface CertStructure {
  cert_id: string
  cert_name: string
  recommended_study_hours: number
  passing_score: number
  domains: { domain_id: string; name: string; weight_pct: number; services: string[] }[]
}

export interface TeamInsights {
  team_id: string
  member_count: number
  average_meeting_hours_pw: number
  high_capacity_risk_members: string[]
  members: MemberContext[]
  ai_disclosure: string
}

export interface MemberContext {
  employee_id: string
  meeting_hours_pw: number
  focus_hours_pw: number
  capacity_risk: string
  recommended_slots: string[]
}

export interface TraceEvent {
  event_id: string
  run_id: string
  timestamp: string
  event_type: string
  agent_name: string
  data: Record<string, unknown>
}
