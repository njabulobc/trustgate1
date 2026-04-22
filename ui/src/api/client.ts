export type ClientType = 'INDIVIDUAL' | 'ENTITY';
export type ClientStatus = 'DRAFT' | 'ACTIVE' | 'ARCHIVED';
export type DealStatus = 'DRAFT' | 'ACTIVE' | 'CLOSED' | 'ABORTED';
export type DealTransactionType = 'PURCHASE' | 'SALE' | 'TRANSFER' | 'LEASE';
export type LinkedPartyType = 'INDIVIDUAL' | 'ENTITY';
export type LinkedPartyRole = 'OWNER' | 'BENEFICIAL_OWNER' | 'DIRECTOR' | 'AUTHORIZED_SIGNATORY' | 'INTERMEDIARY' | 'OTHER';
export type ScreeningSubjectType = 'CLIENT' | 'LINKED_PARTY';
export type CandidateDisposition = 'OPEN' | 'CLEAR' | 'ESCALATED' | 'FALSE_POSITIVE';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
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
  matched_name: string;
  match_score: string | null;
  list_name: string | null;
  country: string | null;
  disposition: CandidateDisposition;
  disposition_reason: string | null;
};

export type ScreeningResult = {
  id: number;
  subject_type: ScreeningSubjectType;
  client_id: number | null;
  linked_party_id: number | null;
  provider_name: string;
  status: string;
  subject_name_snapshot: string;
  screened_at: string;
  candidates: ScreeningCandidate[];
};

export type RiskAssessment = {
  id: number;
  client_id: number;
  deal_id: number | null;
  total_score: string;
  risk_level: string;
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
      subject_type: 'CLIENT',
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

  runRisk: (clientId: number, dealId?: number) => request<{ risk_assessment: RiskAssessment }>(`/risk/clients/${clientId}${dealId ? `?deal_id=${dealId}` : ''}`, {
    method: 'POST'
  }),
  getLatestRisk: (clientId: number, dealId?: number) => request<{ risk_assessment: RiskAssessment }>(`/risk/clients/${clientId}${dealId ? `?deal_id=${dealId}` : ''}`)
};
