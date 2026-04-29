export type ClientType = 'individual' | 'company';
export type ClientStatus = 'draft' | 'in_progress' | 'submitted' | 'under_review' | 'completed' | 'rejected';
export type DealStatus = 'draft' | 'in_progress' | 'screening_pending' | 'under_review' | 'completed' | 'cancelled';
export type DealTransactionType = 'purchase' | 'sale' | 'lease' | 'rental' | 'transfer' | 'other';
export type LinkedPartyType = 'individual' | 'company';
export type LinkedPartyRole = 'beneficial_owner' | 'representative' | 'co_buyer' | 'co_seller' | 'payer' | 'intermediary' | 'other';
export type ScreeningSubjectType = 'client' | 'linked_party';
export type CandidateDisposition = 'pending' | 'confirmed_match' | 'false_positive' | 'needs_edd';
export type UserRole = 'superuser' | 'reviewer' | 'analyst';
export type QueueStatus = 'new' | 'queued' | 'in_review' | 'escalated' | 'completed';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
let authToken: string | null = null;

export function setAuthToken(token: string | null) {
  authToken = token;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      ...(init?.headers ?? {})
    },
    ...init
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

export type SessionUser = { username: string; role: UserRole; display_name: string };

export type IntakePayload = {
  client: { client_type: ClientType; primary_name: string; email?: string; status?: ClientStatus };
  deal: { transaction_reference: string; transaction_type: DealTransactionType; property_location: string; transaction_value: string; currency: string; is_cross_border: boolean; status?: DealStatus; source_of_funds_summary?: string };
};
export type IntakeResponse = { client: { id: number; primary_name: string; client_type: ClientType; status: ClientStatus }; deal: { id: number; transaction_reference: string; transaction_type: DealTransactionType; status: DealStatus } };

export type LinkedParty = { id: number; client_id: number; deal_id: number; party_type: LinkedPartyType; role: LinkedPartyRole; relationship_to_client: string; primary_name: string; screening_required: boolean };
export type LinkedPartyPayload = Omit<LinkedParty, 'id'> & { first_name?: string; last_name?: string; email?: string };

export type ScreeningCandidate = { id: number; screening_result_id: number; matched_name: string; disposition: CandidateDisposition; notes: string | null; candidate_payload: Record<string, unknown> | null; dataset: string | null; country: string | null; match_score: string | number | null };
export type ScreeningResult = { id: number; client_id: number | null; provider_name: string; status: string; subject_name_snapshot: string; screened_at: string; candidates: ScreeningCandidate[] };
export type RiskAssessment = { id: number; client_id: number; deal_id: number | null; total_score: string; risk_level: string; summary: string | null; assessed_at: string };
export type WorkflowCase = { id: number; client_id: number; deal_id: number; status: QueueStatus; assigned_reviewer: string | null; queue_notes: string | null; updated_at: string };

export const api = {
  login: (username: string, password: string) => request<{ access_token: string; user: SessionUser }>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  getSession: () => request<SessionUser>('/auth/session'),

  createIntake: (payload: IntakePayload) => request<IntakeResponse>('/intake', { method: 'POST', body: JSON.stringify(payload) }),
  getIntakeByClientId: (clientId: number) => request<IntakeResponse>(`/intake/clients/${clientId}`),

  createRelationship: (payload: LinkedPartyPayload) => request<LinkedParty>('/relationships', { method: 'POST', body: JSON.stringify(payload) }),
  getRelationships: (clientId: number, dealId: number) => request<LinkedParty[]>(`/relationships?client_id=${clientId}&deal_id=${dealId}`),
  patchRelationship: (linkedPartyId: number, payload: Partial<LinkedPartyPayload>) => request<LinkedParty>(`/relationships/${linkedPartyId}`, { method: 'PATCH', body: JSON.stringify(payload) }),

  runScreening: (clientId: number) => request<ScreeningResult[]>('/screening/run', { method: 'POST', body: JSON.stringify({ subject_type: 'client', client_id: clientId }) }),
  getScreeningByClientId: (clientId: number) => request<ScreeningResult[]>(`/screening/clients/${clientId}`),
  patchCandidateDisposition: (candidateId: number, disposition: CandidateDisposition, dispositionReason?: string) => request<ScreeningCandidate>(`/screening/candidates/${candidateId}/disposition`, { method: 'PATCH', body: JSON.stringify({ disposition, disposition_reason: dispositionReason ?? null }) }),

  runRisk: (clientId: number, dealId?: number) => request<{ risk_assessment: RiskAssessment }>(`/risk/clients/${clientId}${dealId ? `?deal_id=${dealId}` : ''}`, { method: 'POST' }),
  getLatestRisk: (clientId: number, dealId?: number) => request<{ risk_assessment: RiskAssessment }>(`/risk/clients/${clientId}${dealId ? `?deal_id=${dealId}` : ''}`),
  getRiskHistory: (clientId: number, dealId?: number) => request<{ items: RiskAssessment[] }>(`/risk/clients/${clientId}/history${dealId ? `?deal_id=${dealId}` : ''}`),

  queueCase: (dealId: number, notes?: string) => request<WorkflowCase>(`/workflow/deals/${dealId}/queue`, { method: 'POST', body: JSON.stringify({ notes }) }),
  assignCase: (dealId: number, assignedReviewer: string) => request<WorkflowCase>(`/workflow/deals/${dealId}/assign`, { method: 'PATCH', body: JSON.stringify({ assigned_reviewer: assignedReviewer }) }),
  transitionCase: (dealId: number, status: QueueStatus) => request<WorkflowCase>(`/workflow/deals/${dealId}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  listCases: (params: { page: number; pageSize: number; status?: QueueStatus | ''; assignedReviewer?: string; search?: string }) => {
    const query = new URLSearchParams({ page: String(params.page), page_size: String(params.pageSize) });
    if (params.status) query.set('status', params.status);
    if (params.assignedReviewer) query.set('assigned_reviewer', params.assignedReviewer);
    if (params.search) query.set('search', params.search);
    return request<{ items: WorkflowCase[]; total: number; page: number; page_size: number }>(`/workflow/cases?${query.toString()}`);
  }
};
