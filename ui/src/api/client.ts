export type ClientType = 'individual' | 'company';
export type ClientStatus = 'draft' | 'in_progress' | 'submitted' | 'under_review' | 'completed' | 'rejected';
export type DealStatus = 'draft' | 'in_progress' | 'screening_pending' | 'under_review' | 'completed' | 'cancelled';
export type DealTransactionType = 'purchase' | 'sale' | 'lease' | 'rental' | 'transfer' | 'other';
export type LinkedPartyType = 'individual' | 'company';
export type LinkedPartyRole = 'beneficial_owner' | 'representative' | 'co_buyer' | 'co_seller' | 'payer' | 'intermediary' | 'other';
export type ScreeningSubjectType = 'client' | 'linked_party';
export type CandidateDisposition = 'pending' | 'confirmed_match' | 'false_positive' | 'needs_edd';
export type MatchCategory = 'standard' | 'pep' | 'rca';
export type PepCaseStatus = 'open' | 'in_review' | 'senior_approved' | 'rejected' | 'closed';
export type VerificationStatus = 'pending' | 'verified' | 'insufficient';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
const API_TOKEN = import.meta.env.VITE_API_BEARER_TOKEN;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const localStorageToken = typeof window !== 'undefined' ? window.localStorage.getItem('trustgate_api_token') : null;
  const bearerToken = API_TOKEN ?? localStorageToken;
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(bearerToken ? { Authorization: `Bearer ${bearerToken}` } : {}),
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

export type IntakePayload = {
  client: {
    client_type: ClientType;
    primary_name: string;
    first_name?: string;
    last_name?: string;
    email?: string;
    nationality?: string;
    status?: ClientStatus;
  };
  deal: {
    transaction_reference: string;
    transaction_type: DealTransactionType;
    property_location: string;
    transaction_value: string;
    currency: string;
    is_cross_border: boolean;
    status?: DealStatus;
    source_of_funds_summary?: string;
  };
};

export type IntakeResponse = {
  client: { id: number; primary_name: string; client_type: ClientType; status: ClientStatus };
  deal: { id: number; transaction_reference: string; transaction_type: DealTransactionType; status: DealStatus };
};

export type LinkedParty = {
  id: number;
  client_id: number;
  deal_id: number;
  party_type: LinkedPartyType;
  role: LinkedPartyRole;
  relationship_to_client: string;
  primary_name: string;
  screening_required: boolean;
};

export type LinkedPartyPayload = Omit<LinkedParty, 'id'> & {
  first_name?: string;
  last_name?: string;
  email?: string;
};

export type ScreeningCandidate = {
  id: number;
  screening_result_id: number;
  provider_candidate_id: string | null;
  provider_entity_id: string | null;
  matched_name: string;
  match_score: string | number | null;
  list_name: string | null;
  dataset: string | null;
  country: string | null;
  notes: string | null;
  match_category: MatchCategory;
  policy_flags: Record<string, unknown> | null;
  disposition: CandidateDisposition;
  disposition_reason: string | null;
  reviewed_at: string | null;
  candidate_payload: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type PepCase = {
  id: number;
  screening_candidate_id: number;
  status: PepCaseStatus;
  senior_approval_status: VerificationStatus;
  source_of_wealth_status: VerificationStatus;
  source_of_funds_status: VerificationStatus;
  enhanced_monitoring: boolean;
  monitoring_notes: string | null;
  closure_evidence: Record<string, unknown> | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ScreeningResult = {
  id: number;
  subject_type: ScreeningSubjectType;
  client_id: number | null;
  linked_party_id: number | null;
  provider_name: string;
  status: string;
  subject_name_snapshot: string;
  query_text?: string | null;
  request_payload?: Record<string, unknown> | null;
  response_payload?: Record<string, unknown> | null;
  error_message?: string | null;
  screened_at: string;
  reviewed_at?: string | null;
  created_at?: string;
  updated_at?: string;
  candidates: ScreeningCandidate[];
};

export type RiskAssessment = {
  id: number;
  client_id: number;
  deal_id: number | null;
  total_score: string;
  risk_level: string;
  factor_breakdown?: Record<string, unknown> | null;
  summary: string | null;
  assessed_at: string;
};

export const api = {
  createIntake: (payload: IntakePayload) => request<IntakeResponse>('/intake', {
    method: 'POST',
    body: JSON.stringify(payload)
  }),
  getIntakeByClientId: (clientId: number) => request<IntakeResponse>(`/intake/clients/${clientId}`),
  patchIntakeByClientId: (clientId: number, payload: Partial<IntakePayload>) => request<IntakeResponse>(`/intake/clients/${clientId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  }),

  createRelationship: (payload: LinkedPartyPayload) => request<LinkedParty>('/relationships', {
    method: 'POST',
    body: JSON.stringify(payload)
  }),
  getRelationships: (clientId: number, dealId: number) => request<LinkedParty[]>(`/relationships?client_id=${clientId}&deal_id=${dealId}`),
  patchRelationship: (linkedPartyId: number, payload: Partial<LinkedPartyPayload>) => request<LinkedParty>(`/relationships/${linkedPartyId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  }),

  runScreening: (clientId: number) => request<ScreeningResult[]>('/screening/run', {
    method: 'POST',
    body: JSON.stringify({
      subject_type: 'client',
      client_id: clientId
    })
  }),
  getScreeningByClientId: (clientId: number) => request<ScreeningResult[]>(`/screening/clients/${clientId}`),
  patchCandidateDisposition: (candidateId: number, disposition: CandidateDisposition, dispositionReason?: string) => request<ScreeningCandidate>(`/screening/candidates/${candidateId}/disposition`, {
    method: 'PATCH',
    body: JSON.stringify({
      disposition,
      disposition_reason: dispositionReason ?? null
    })
  }),
  openPepCase: (candidateId: number) => request<PepCase>(`/screening/candidates/${candidateId}/pep-case`, {
    method: 'POST'
  }),
  patchPepCase: (pepCaseId: number, payload: Partial<PepCase>) => request<PepCase>(`/screening/pep-cases/${pepCaseId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  }),
  getPepCasesByClientId: (clientId: number) => request<PepCase[]>(`/screening/clients/${clientId}/pep-cases`),

  runRisk: (clientId: number, dealId?: number) => request<{ risk_assessment: RiskAssessment }>(`/risk/clients/${clientId}${dealId ? `?deal_id=${dealId}` : ''}`, {
    method: 'POST'
  }),
  getLatestRisk: (clientId: number, dealId?: number) => request<{ risk_assessment: RiskAssessment }>(`/risk/clients/${clientId}${dealId ? `?deal_id=${dealId}` : ''}`)
};
