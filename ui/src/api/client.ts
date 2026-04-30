export type UserRole = 'administrator' | 'compliance_officer' | 'analyst' | 'reviewer' | 'auditor';
export type ClientType = 'individual' | 'company';
export type ClientStatus = 'draft' | 'in_progress' | 'submitted' | 'under_review' | 'completed' | 'rejected';
export type DealStatus = 'draft' | 'in_progress' | 'screening_pending' | 'under_review' | 'completed' | 'cancelled';
export type DealTransactionType = 'purchase' | 'sale' | 'lease' | 'rental' | 'transfer' | 'other';
export type LinkedPartyType = 'individual' | 'company';
export type LinkedPartyRole = 'beneficial_owner' | 'representative' | 'co_buyer' | 'co_seller' | 'payer' | 'intermediary' | 'other';
export type CandidateDisposition = 'pending' | 'confirmed_match' | 'false_positive' | 'needs_edd';
export type MatchCategory = 'standard' | 'pep' | 'rca';
export type VerificationStatus = 'pending' | 'approved' | 'rejected' | 'escalated';
export type WorkflowStatus = 'open' | 'in_progress' | 'under_review' | 'completed' | 'escalated';
export type DocumentLifecycleStatus = 'required' | 'submitted' | 'under_review' | 'verified' | 'rejected' | 'expired' | 'resubmission_required';
export type KycOnboardingStatus = 'draft' | 'in_progress' | 'ready_for_review' | 'approved' | 'rejected';
export type TaxClearanceStatus = 'unknown' | 'pending' | 'verified' | 'exempt' | 'rejected';
export type OwnershipOwnerType = 'individual' | 'company' | 'trust' | 'nominee';
export type EddCaseStatus = 'open' | 'assigned' | 'in_review' | 'awaiting_information' | 'escalated' | 'approved' | 'rejected' | 'closed';
export type EddCasePriority = 'low' | 'medium' | 'high' | 'critical';
export type AlertSeverity = 'low' | 'medium' | 'high' | 'critical';
export type AlertStatus = 'open' | 'assigned' | 'in_review' | 'escalated' | 'closed';
export type RiskLevel = 'low' | 'medium' | 'high';

const TOKEN_KEY = 'trustgate_access_token';

function resolveLocalApiBaseUrl(): string {
  if (typeof window === 'undefined') return 'http://localhost:8000';
  const host = window.location.hostname || 'localhost';
  return `http://${host}:8000`;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? resolveLocalApiBaseUrl();

export const API_BASE_URL = API_BASE;
export const APP_ORIGIN = typeof window === 'undefined' ? 'server' : window.location.origin;

function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.sessionStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  if (typeof window === 'undefined') return;
  window.sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  if (typeof window === 'undefined') return;
  window.sessionStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getStoredToken();
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {})
    },
    ...init
  }).catch(() => {
    throw new Error(`Network or CORS error contacting API at ${API_BASE}`);
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

export type User = {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type DashboardSummary = {
  total_clients: number;
  pending_kyc_reviews: number;
  incomplete_document_files: number;
  open_cdd_tasks: number;
  open_edd_cases: number;
  screening_hits_requiring_review: number;
  open_alerts: number;
  high_risk_clients_or_deals: number;
  reports_shortcut_count: number;
};

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
  client: {
    id: number;
    primary_name: string;
    client_type: ClientType;
    status: ClientStatus;
    created_at?: string;
    updated_at?: string;
  };
  deal: {
    id: number;
    client_id?: number;
    transaction_reference: string;
    transaction_type: DealTransactionType;
    status: DealStatus;
    property_location?: string;
    transaction_value?: string;
    currency?: string;
    is_cross_border?: boolean;
    created_at?: string;
    updated_at?: string;
  };
};

export type IntakeListItem = {
  client_id: number;
  deal_id: number | null;
  primary_name: string;
  client_type: ClientType;
  client_status: ClientStatus;
  transaction_reference: string | null;
  transaction_type: DealTransactionType | null;
  deal_status: DealStatus | null;
  risk_level: RiskLevel | null;
  updated_at: string;
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

export type KycProfile = {
  id: number;
  client_id: number;
  deal_id: number | null;
  onboarding_status: KycOnboardingStatus;
  full_legal_name: string;
  date_of_birth: string | null;
  national_id_or_passport_number: string | null;
  nationality: string | null;
  address: string | null;
  contact_details: string | null;
  occupation: string | null;
  employer: string | null;
  business_activity: string | null;
  company_registration_number: string | null;
  tax_identification_number: string | null;
  tax_clearance_status: TaxClearanceStatus;
  residency_status: string | null;
  cross_border_indicator: boolean;
  pep_declaration: boolean;
  related_party_declaration: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type KycProfilePayload = Omit<KycProfile, 'id' | 'client_id' | 'created_at' | 'updated_at'>;

export type DocumentRecord = {
  id: number;
  client_id: number;
  deal_id: number | null;
  linked_party_id: number | null;
  document_type: string;
  lifecycle_status: DocumentLifecycleStatus;
  file_name: string;
  content_type: string | null;
  storage_path: string;
  storage_reference: string | null;
  checksum_sha256: string;
  file_size_bytes: number;
  expiry_date: string | null;
  reviewer_user_id: number | null;
  review_timestamp: string | null;
  rejection_reason: string | null;
  reviewer_comments: string | null;
  created_by_user_id: number | null;
  created_at: string;
  updated_at: string;
};

export type DocumentChecklistSummary = {
  client_id: number;
  total_documents: number;
  verified_documents: number;
  missing_document_types: string[];
  expired_documents: number;
  requires_resubmission: number;
};

export type CddWorkflow = {
  id: number;
  client_id: number;
  deal_id: number | null;
  assigned_analyst_id: number | null;
  completion_status: WorkflowStatus;
  source_of_funds_status: VerificationStatus;
  source_of_wealth_status: VerificationStatus;
  payment_method_review: string | null;
  transaction_purpose_review: string | null;
  expected_activity_profile: string | null;
  adverse_transaction_indicators: string | null;
  supporting_evidence_checklist: Record<string, unknown> | null;
  analyst_decision: VerificationStatus;
  reviewer_decision: VerificationStatus;
  analyst_notes: string | null;
  reviewer_notes: string | null;
  created_at: string;
  updated_at: string;
};

export type CddWorkflowPayload = Omit<CddWorkflow, 'id' | 'client_id' | 'created_at' | 'updated_at'>;

export type OwnershipRecord = {
  id: number;
  client_id: number;
  deal_id: number | null;
  linked_party_id: number | null;
  parent_record_id: number | null;
  owner_name: string;
  owner_type: OwnershipOwnerType;
  classification: string | null;
  ownership_percentage: string | null;
  control_type: string | null;
  direct_ownership: boolean;
  indirect_ownership: boolean;
  nominee_indicator: boolean;
  trust_indicator: boolean;
  representative_relationship: boolean;
  control_without_ownership: boolean;
  corporate_parent_name: string | null;
  ownership_chain_notes: string | null;
  complexity_score: string | null;
  created_at: string;
  updated_at: string;
};

export type OwnershipGraphNode = {
  id: number;
  owner_name: string;
  parent_record_id: number | null;
  ownership_percentage: string | null;
  control_type: string | null;
  complexity_score: string | null;
};

export type OwnershipPayload = Omit<OwnershipRecord, 'id' | 'client_id' | 'created_at' | 'updated_at'>;

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

export type ScreeningResult = {
  id: number;
  subject_type: 'client' | 'linked_party';
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
  risk_level: RiskLevel;
  factor_breakdown: Record<string, unknown> | null;
  summary: string | null;
  assessed_at: string;
};

export type RiskOverride = {
  id: number;
  risk_assessment_id: number;
  overridden_by_user_id: number | null;
  override_level: string;
  justification: string;
  notes: string | null;
  created_at: string;
};

export type RiskAssessmentResponse = {
  risk_assessment: RiskAssessment;
  recommended_action: string | null;
  edd_required: boolean;
  overrides: RiskOverride[];
};

export type EddCase = {
  id: number;
  client_id: number;
  deal_id: number | null;
  source_module: string;
  case_type: string;
  trigger_reason: string;
  assigned_analyst_id: number | null;
  priority: EddCasePriority;
  status: EddCaseStatus;
  required_actions: Record<string, unknown> | null;
  evidence_checklist: Record<string, unknown> | null;
  analyst_findings: string | null;
  reviewer_comments: string | null;
  approval_outcome: string | null;
  closure_decision: string | null;
  due_at: string | null;
  created_at: string;
  updated_at: string;
};

export type EddCasePayload = Omit<EddCase, 'id' | 'client_id' | 'created_at' | 'updated_at'>;

export type MonitoringAlert = {
  id: number;
  client_id: number;
  deal_id: number | null;
  linked_party_id: number | null;
  edd_case_id: number | null;
  module: string;
  alert_type: string;
  severity: AlertSeverity;
  status: AlertStatus;
  assigned_user_id: number | null;
  disposition: string | null;
  escalation_reason: string | null;
  closure_reason: string | null;
  due_at: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
};

export type MonitoringEvent = {
  id: number;
  client_id: number;
  deal_id: number | null;
  event_type: string;
  event_source: string;
  summary: string;
  details: Record<string, unknown> | null;
  triggered_by_user_id: number | null;
  created_at: string;
};

export type MonitoringAlertPayload = Omit<MonitoringAlert, 'id' | 'client_id' | 'resolved_at' | 'created_at' | 'updated_at'>;

export type WorkbenchItem = {
  module: string;
  item_type: string;
  item_id: number;
  client_id: number | null;
  deal_id: number | null;
  title: string;
  status: string;
  severity_or_priority: string | null;
  assigned_user_id: number | null;
  updated_at: string;
};

export type WorkbenchQueueResponse = {
  items: WorkbenchItem[];
};

export type ReportExportResponse = {
  report_name: string;
  rows: Record<string, unknown>[];
  csv: string | null;
};

export type AppSetting = {
  id: number;
  key: string;
  value_json: Record<string, unknown> | null;
  description: string | null;
  updated_by_user_id: number | null;
  updated_at: string;
};

export type AuditEvent = {
  id: number;
  user_id: number | null;
  actor: string;
  action: string;
  module: string;
  entity_type: string;
  entity_id: string;
  previous_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  reason: string | null;
  comment: string | null;
  timestamp: string;
};

export type AdminOverview = {
  users: Array<{ id: number; username: string; full_name: string; email: string; role: UserRole; is_active: boolean }>;
  settings: AppSetting[];
  audit_events: AuditEvent[];
};

export const api = {
  login: (username: string, password: string) =>
    request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password })
    }),
  me: () => request<User>('/auth/me'),
  listUsers: () => request<User[]>('/auth/users'),
  createUser: (payload: { username: string; email: string; full_name: string; role: UserRole; password: string }) =>
    request<User>('/auth/users', { method: 'POST', body: JSON.stringify(payload) }),
  updateUser: (userId: number, payload: Partial<{ email: string; full_name: string; role: UserRole; is_active: boolean; password: string }>) =>
    request<User>(`/auth/users/${userId}`, { method: 'PATCH', body: JSON.stringify(payload) }),

  getDashboardSummary: () => request<DashboardSummary>('/dashboard/summary'),

  listIntakes: () => request<IntakeListItem[]>('/intake'),
  createIntake: (payload: IntakePayload) => request<IntakeResponse>('/intake', { method: 'POST', body: JSON.stringify(payload) }),
  getIntakeByClientId: (clientId: number) => request<IntakeResponse>(`/intake/clients/${clientId}`),
  patchIntakeByClientId: (clientId: number, payload: Partial<IntakePayload>) =>
    request<IntakeResponse>(`/intake/clients/${clientId}`, { method: 'PATCH', body: JSON.stringify(payload) }),

  getKycProfile: (clientId: number) => request<KycProfile | null>(`/kyc/clients/${clientId}`),
  upsertKycProfile: (clientId: number, payload: KycProfilePayload) =>
    request<KycProfile>(`/kyc/clients/${clientId}`, { method: 'PUT', body: JSON.stringify(payload) }),

  listDocuments: (clientId: number) => request<DocumentRecord[]>(`/documents/clients/${clientId}`),
  getDocumentChecklist: (clientId: number) => request<DocumentChecklistSummary>(`/documents/clients/${clientId}/checklist`),
  uploadDocument: async (
    clientId: number,
    payload: { document_type: string; deal_id?: number | null; linked_party_id?: number | null; expiry_date?: string | null; file: File }
  ) => {
    const token = getStoredToken();
    const form = new FormData();
    form.append('document_type', payload.document_type);
    if (payload.deal_id) form.append('deal_id', String(payload.deal_id));
    if (payload.linked_party_id) form.append('linked_party_id', String(payload.linked_party_id));
    if (payload.expiry_date) form.append('expiry_date', payload.expiry_date);
    form.append('file', payload.file);
    const response = await fetch(`${API_BASE}/documents/clients/${clientId}`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      body: form
    }).catch(() => {
      throw new Error(`Network or CORS error contacting API at ${API_BASE}`);
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `Request failed: ${response.status}`);
    }
    return (await response.json()) as DocumentRecord;
  },
  reviewDocument: (documentId: number, payload: { lifecycle_status: DocumentLifecycleStatus; expiry_date?: string | null; rejection_reason?: string | null; reviewer_comments?: string | null }) =>
    request<DocumentRecord>(`/documents/${documentId}`, { method: 'PATCH', body: JSON.stringify(payload) }),

  getCddWorkflow: (clientId: number, dealId?: number | null) =>
    request<CddWorkflow>(`/cdd/clients/${clientId}${dealId ? `?deal_id=${dealId}` : ''}`),
  upsertCddWorkflow: (clientId: number, payload: CddWorkflowPayload) =>
    request<CddWorkflow>(`/cdd/clients/${clientId}`, { method: 'PUT', body: JSON.stringify(payload) }),

  getRelationships: (clientId: number, dealId: number) => request<LinkedParty[]>(`/relationships?client_id=${clientId}&deal_id=${dealId}`),
  createRelationship: (payload: LinkedPartyPayload) => request<LinkedParty>('/relationships', { method: 'POST', body: JSON.stringify(payload) }),
  patchRelationship: (linkedPartyId: number, payload: Partial<LinkedPartyPayload>) =>
    request<LinkedParty>(`/relationships/${linkedPartyId}`, { method: 'PATCH', body: JSON.stringify(payload) }),

  listOwnership: (clientId: number) => request<OwnershipRecord[]>(`/ownership/clients/${clientId}`),
  getOwnershipGraph: (clientId: number) => request<OwnershipGraphNode[]>(`/ownership/clients/${clientId}/graph`),
  createOwnership: (clientId: number, payload: OwnershipPayload) =>
    request<OwnershipRecord>(`/ownership/clients/${clientId}`, { method: 'POST', body: JSON.stringify(payload) }),
  updateOwnership: (recordId: number, payload: OwnershipPayload) =>
    request<OwnershipRecord>(`/ownership/${recordId}`, { method: 'PATCH', body: JSON.stringify(payload) }),

  runScreening: (clientId: number) =>
    request<ScreeningResult[]>('/screening/run', { method: 'POST', body: JSON.stringify({ subject_type: 'client', client_id: clientId }) }),
  getScreeningByClientId: (clientId: number) => request<ScreeningResult[]>(`/screening/clients/${clientId}`),
  patchCandidateDisposition: (candidateId: number, disposition: CandidateDisposition, dispositionReason?: string) =>
    request<ScreeningCandidate>(`/screening/candidates/${candidateId}/disposition`, {
      method: 'PATCH',
      body: JSON.stringify({ disposition, disposition_reason: dispositionReason ?? null })
    }),
  openPepCase: (candidateId: number) => request<{ id: number }>(`/screening/candidates/${candidateId}/pep-case`, { method: 'POST' }),
  getPepCasesByClientId: (clientId: number) => request<Array<Record<string, unknown>>>(`/screening/clients/${clientId}/pep-cases`),

  runRisk: (clientId: number, dealId?: number | null) =>
    request<RiskAssessmentResponse>(`/risk/clients/${clientId}${dealId ? `?deal_id=${dealId}` : ''}`, { method: 'POST' }),
  getLatestRisk: (clientId: number, dealId?: number | null) =>
    request<RiskAssessmentResponse>(`/risk/clients/${clientId}${dealId ? `?deal_id=${dealId}` : ''}`),
  createRiskOverride: (clientId: number, payload: { override_level: string; justification: string; notes?: string | null }, dealId?: number | null) =>
    request<RiskOverride>(`/risk/clients/${clientId}/override${dealId ? `?deal_id=${dealId}` : ''}`, {
      method: 'POST',
      body: JSON.stringify(payload)
    }),

  listEddCases: (clientId?: number | null) => request<EddCase[]>(`/edd/cases${clientId ? `?client_id=${clientId}` : ''}`),
  createEddCase: (clientId: number, payload: EddCasePayload) =>
    request<EddCase>(`/edd/clients/${clientId}/cases`, { method: 'POST', body: JSON.stringify(payload) }),
  updateEddCase: (caseId: number, payload: EddCasePayload) =>
    request<EddCase>(`/edd/cases/${caseId}`, { method: 'PATCH', body: JSON.stringify(payload) }),

  listAlerts: (clientId?: number | null) => request<MonitoringAlert[]>(`/monitoring/alerts${clientId ? `?client_id=${clientId}` : ''}`),
  listMonitoringEvents: (clientId?: number | null) => request<MonitoringEvent[]>(`/monitoring/events${clientId ? `?client_id=${clientId}` : ''}`),
  runMonitoring: (clientId: number, dealId?: number | null, reason?: string) =>
    request<MonitoringAlert[]>('/monitoring/run', { method: 'POST', body: JSON.stringify({ client_id: clientId, deal_id: dealId, reason }) }),
  createAlert: (clientId: number, payload: MonitoringAlertPayload) =>
    request<MonitoringAlert>(`/monitoring/clients/${clientId}/alerts`, { method: 'POST', body: JSON.stringify(payload) }),
  updateAlert: (alertId: number, payload: MonitoringAlertPayload) =>
    request<MonitoringAlert>(`/monitoring/alerts/${alertId}`, { method: 'PATCH', body: JSON.stringify(payload) }),

  getWorkbenchQueue: (filters?: { status?: string; assignee_id?: number | null; client_id?: number | null; module?: string | null }) => {
    const params = new URLSearchParams();
    if (filters?.status) params.set('status', filters.status);
    if (filters?.assignee_id) params.set('assignee_id', String(filters.assignee_id));
    if (filters?.client_id) params.set('client_id', String(filters.client_id));
    if (filters?.module) params.set('module', filters.module);
    const query = params.toString();
    return request<WorkbenchQueueResponse>(`/workbench/queue${query ? `?${query}` : ''}`);
  },

  generateReport: (reportName: string, format: 'json' | 'csv' = 'json') =>
    request<ReportExportResponse>(`/reports/${reportName}?format=${format}`),

  getAdminOverview: () => request<AdminOverview>('/admin/overview'),
  listSettings: () => request<AppSetting[]>('/admin/settings'),
  updateSetting: (key: string, payload: { key: string; value_json: Record<string, unknown> | null; description?: string | null }) =>
    request<AppSetting>(`/admin/settings/${key}`, { method: 'PUT', body: JSON.stringify(payload) }),

  generateComplianceDecision: (clientId: number, dealId?: number | null) =>
    request<Record<string, unknown>>(`/compliance/clients/${clientId}/decision${dealId ? `?deal_id=${dealId}` : ''}`, { method: 'POST' })
};
