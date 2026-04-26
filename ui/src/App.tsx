import { FormEvent, useEffect, useMemo, useState } from 'react';

import {
  api,
  CandidateDisposition,
  ComplianceDecisionResponse,
  ScreeningCandidate,
  DealTransactionType,
  IntakePayload,
  IntakeResponse,
  LinkedParty,
  LinkedPartyPayload,
  LinkedPartyRole,
  LinkedPartyType,
  ScreeningResult,
  RiskAssessment,
  ClientType,
  PepCase
} from './api/client';

type AsyncState = {
  loading: boolean;
  error: string | null;
  success: string | null;
};

const cardClass = 'rounded-xl border border-slate-200 bg-white p-6 shadow-sm';
const inputClass = 'w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-50';
const buttonClass = 'rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50';
const badgeClass = 'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium';

type PolicyAlert = {
  severity: string;
  rationale?: string | null;
  source?: string | null;
};

function formatDateTime(value?: string | null): string {
  if (!value) return '—';
  return new Date(value).toLocaleString();
}

function extractTopics(candidate: ScreeningCandidate): string[] {
  const payload = candidate.candidate_payload;
  if (!payload || typeof payload !== 'object') return [];
  const topics = (payload as Record<string, unknown>).topics;
  if (!Array.isArray(topics)) return [];
  return topics.map((topic) => String(topic));
}

function extractPolicyAlerts(candidate: ScreeningCandidate): PolicyAlert[] {
  const policyFlags = candidate.policy_flags;
  if (policyFlags && typeof policyFlags === 'object') {
    const alerts = (policyFlags as Record<string, unknown>).alerts;
    if (Array.isArray(alerts)) {
      return alerts
        .filter((alert): alert is Record<string, unknown> => typeof alert === 'object' && alert !== null)
        .map((alert) => ({
          severity: String(alert.severity ?? 'unknown'),
          rationale: typeof alert.rationale === 'string' ? alert.rationale : null,
          source: typeof alert.policy === 'string' ? alert.policy : null
        }));
    }
  }

  const payload = candidate.candidate_payload;
  if (!payload || typeof payload !== 'object') return [];
  const record = payload as Record<string, unknown>;
  const sources = [record.alerts, record.policy_alerts, record.policy_hits];
  const alerts = sources.find((value) => Array.isArray(value));
  if (!Array.isArray(alerts)) return [];

  return alerts
    .filter((alert): alert is Record<string, unknown> => typeof alert === 'object' && alert !== null)
    .map((alert) => ({
      severity: String(alert.severity ?? alert.level ?? 'unknown'),
      rationale: typeof alert.rationale === 'string' ? alert.rationale : typeof alert.reason === 'string' ? alert.reason : null,
      source: typeof alert.policy === 'string' ? alert.policy : null
    }));
}

function severityBadgeClass(severity: string): string {
  const normalized = severity.toLowerCase();
  if (normalized === 'high' || normalized === 'critical') return `${badgeClass} bg-rose-100 text-rose-700`;
  if (normalized === 'medium') return `${badgeClass} bg-amber-100 text-amber-700`;
  return `${badgeClass} bg-slate-100 text-slate-700`;
}

export default function App() {
  const [intake, setIntake] = useState<IntakeResponse | null>(null);
  const [clientType, setClientType] = useState<ClientType>('individual');
  const [clientName, setClientName] = useState('');
  const [email, setEmail] = useState('');
  const [dealRef, setDealRef] = useState('');
  const [transactionType, setTransactionType] = useState<DealTransactionType>('purchase');
  const [propertyLocation, setPropertyLocation] = useState('');
  const [transactionValue, setTransactionValue] = useState('0');

  const [relationshipForm, setRelationshipForm] = useState({
    party_type: 'individual' as LinkedPartyType,
    role: 'beneficial_owner' as LinkedPartyRole,
    relationship_to_client: '',
    primary_name: ''
  });
  const [linkedParties, setLinkedParties] = useState<LinkedParty[]>([]);
  const [selectedLinkedPartyId, setSelectedLinkedPartyId] = useState<number | null>(null);

  const [screeningResults, setScreeningResults] = useState<ScreeningResult[]>([]);
  const [selectedCandidateId, setSelectedCandidateId] = useState<number | null>(null);
  const [candidateDisposition, setCandidateDisposition] = useState<CandidateDisposition>('pending');
  const [dispositionReason, setDispositionReason] = useState('');

  const [riskAssessment, setRiskAssessment] = useState<RiskAssessment | null>(null);
  const [complianceDecision, setComplianceDecision] = useState<ComplianceDecisionResponse | null>(null);
  const [decisionExpanded, setDecisionExpanded] = useState(false);
  const [pepCases, setPepCases] = useState<PepCase[]>([]);

  const [intakeState, setIntakeState] = useState<AsyncState>({ loading: false, error: null, success: null });
  const [relationshipState, setRelationshipState] = useState<AsyncState>({ loading: false, error: null, success: null });
  const [screeningState, setScreeningState] = useState<AsyncState>({ loading: false, error: null, success: null });
  const [riskState, setRiskState] = useState<AsyncState>({ loading: false, error: null, success: null });
  const [decisionState, setDecisionState] = useState<AsyncState>({ loading: false, error: null, success: null });

  const clientId = intake?.client.id;
  const dealId = intake?.deal.id;

  useEffect(() => {
    if (!clientId || !dealId) return;
    api.getRelationships(clientId, dealId).then(setLinkedParties).catch(() => undefined);
    api.getScreeningByClientId(clientId).then(setScreeningResults).catch(() => undefined);
    api.getPepCasesByClientId(clientId).then(setPepCases).catch(() => undefined);
    api.getLatestRisk(clientId, dealId).then((res) => setRiskAssessment(res.risk_assessment)).catch(() => undefined);
  }, [clientId, dealId]);

  const flatCandidates = useMemo(
    () => screeningResults.flatMap((result) => result.candidates.map((candidate) => ({ ...candidate, screeningResultId: result.id }))),
    [screeningResults]
  );
  const selectedCandidate = useMemo(
    () => flatCandidates.find((candidate) => candidate.id === selectedCandidateId) ?? null,
    [flatCandidates, selectedCandidateId]
  );
  const selectedCandidateAlerts = useMemo(
    () => (selectedCandidate ? extractPolicyAlerts(selectedCandidate) : []),
    [selectedCandidate]
  );
  const selectedCandidateHasHighSeverity = selectedCandidateAlerts.some((alert) => {
    const severity = alert.severity.toLowerCase();
    return severity === 'high' || severity === 'critical';
  });

  useEffect(() => {
    if (selectedCandidateId && !selectedCandidate) {
      setSelectedCandidateId(null);
      setDispositionReason('');
    }
  }, [selectedCandidateId, selectedCandidate]);

  async function handleCreateIntake(event: FormEvent) {
    event.preventDefault();
    if (!clientName || !dealRef || !propertyLocation || Number(transactionValue) <= 0) {
      setIntakeState({ loading: false, error: 'Please complete required fields with valid values.', success: null });
      return;
    }

    setIntakeState({ loading: true, error: null, success: null });
    try {
      const payload: IntakePayload = {
        client: {
          client_type: clientType,
          primary_name: clientName,
          email: email || undefined,
          status: 'draft'
        },
        deal: {
          transaction_reference: dealRef,
          transaction_type: transactionType,
          property_location: propertyLocation,
          transaction_value: transactionValue,
          currency: 'USD',
          is_cross_border: false,
          status: 'draft'
        }
      };
      const created = await api.createIntake(payload);
      setIntake(created);
      setScreeningResults([]);
      setComplianceDecision(null);
      setSelectedCandidateId(null);
      setDispositionReason('');
      setIntakeState({ loading: false, error: null, success: `Created client_id=${created.client.id} and deal_id=${created.deal.id}.` });
    } catch (error) {
      setIntakeState({ loading: false, error: (error as Error).message, success: null });
    }
  }

  async function handleAddRelationship(event: FormEvent) {
    event.preventDefault();
    if (!clientId || !dealId) {
      setRelationshipState({ loading: false, error: 'Create intake first to get client_id and deal_id.', success: null });
      return;
    }
    if (!relationshipForm.primary_name || !relationshipForm.relationship_to_client) {
      setRelationshipState({ loading: false, error: 'Relationship name and relationship label are required.', success: null });
      return;
    }

    setRelationshipState({ loading: true, error: null, success: null });
    try {
      const payload: LinkedPartyPayload = {
        ...relationshipForm,
        client_id: clientId,
        deal_id: dealId,
        screening_required: true
      };
      const created = await api.createRelationship(payload);
      const refreshed = await api.getRelationships(clientId, dealId);
      setLinkedParties(refreshed);
      setSelectedLinkedPartyId(created.id);
      setRelationshipState({ loading: false, error: null, success: `Created linked_party_id=${created.id}.` });
      setRelationshipForm((old) => ({ ...old, primary_name: '', relationship_to_client: '' }));
    } catch (error) {
      setRelationshipState({ loading: false, error: (error as Error).message, success: null });
    }
  }

  async function handleRunScreening() {
    if (!clientId) {
      setScreeningState({ loading: false, error: 'client_id is required to run screening.', success: null });
      return;
    }
    setScreeningState({ loading: true, error: null, success: null });
    try {
      const results = await api.runScreening(clientId);
      setScreeningResults(results);
      const cases = await api.getPepCasesByClientId(clientId);
      setPepCases(cases);
      setSelectedCandidateId(null);
      setDispositionReason('');
      setScreeningState({ loading: false, error: null, success: `Screening complete with ${results.length} result set(s).` });
    } catch (error) {
      setScreeningState({ loading: false, error: (error as Error).message, success: null });
    }
  }

  async function handleDispositionUpdate(event: FormEvent) {
    event.preventDefault();
    if (!selectedCandidateId || !selectedCandidate) {
      setScreeningState({ loading: false, error: 'Pick a candidate_id to update disposition.', success: null });
      return;
    }
    if (selectedCandidateHasHighSeverity && dispositionReason.trim().length === 0) {
      setScreeningState({ loading: false, error: 'Disposition reason is required for high-severity policy alerts.', success: null });
      return;
    }
    setScreeningState({ loading: true, error: null, success: null });
    try {
      const candidate = await api.patchCandidateDisposition(selectedCandidate.id, candidateDisposition, dispositionReason || undefined);
      if ((selectedCandidate.match_category === 'pep' || selectedCandidate.match_category === 'rca') && (candidateDisposition === 'confirmed_match' || candidateDisposition === 'needs_edd')) {
        await api.openPepCase(selectedCandidate.id);
      }
      if (clientId) {
        const refreshed = await api.getScreeningByClientId(clientId);
        const caseRefresh = await api.getPepCasesByClientId(clientId);
        setScreeningResults(refreshed);
        setPepCases(caseRefresh);
      }
      setScreeningState({ loading: false, error: null, success: `Updated candidate_id=${candidate.id} disposition.` });
    } catch (error) {
      setScreeningState({ loading: false, error: (error as Error).message, success: null });
    }
  }

  async function handleRunRisk() {
    if (!clientId) {
      setRiskState({ loading: false, error: 'client_id is required to assess risk.', success: null });
      return;
    }
    setRiskState({ loading: true, error: null, success: null });
    try {
      const response = await api.runRisk(clientId, dealId);
      setRiskAssessment(response.risk_assessment);
      setRiskState({ loading: false, error: null, success: `Created risk id=${response.risk_assessment.id}.` });
    } catch (error) {
      setRiskState({ loading: false, error: (error as Error).message, success: null });
    }
  }

  async function handleGenerateComplianceDecision() {
    if (!clientId) {
      setDecisionState({ loading: false, error: 'client_id is required to generate a decision brief.', success: null });
      return;
    }
    setDecisionState({ loading: true, error: null, success: null });
    try {
      const response = await api.generateComplianceDecision(clientId, dealId);
      setComplianceDecision(response);
      setDecisionState({ loading: false, error: null, success: `Decision generated with verdict=${response.verdict}.` });
    } catch (error) {
      setDecisionState({ loading: false, error: (error as Error).message, success: null });
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-4 p-6">
      <header className={`${cardClass} bg-brand-50`}>
        <h1 className="text-2xl font-semibold">TrustGate UI Workflow</h1>
        <p className="mt-2 text-sm text-slate-700">Complete intake → relationships → screening → risk, while carrying IDs between steps.</p>
        <p className="mt-1 text-xs text-slate-600">client_id: <span className="font-semibold">{clientId ?? '—'}</span> · deal_id: <span className="font-semibold">{dealId ?? '—'}</span> · linked_party_id: <span className="font-semibold">{selectedLinkedPartyId ?? '—'}</span> · candidate_id: <span className="font-semibold">{selectedCandidateId ?? '—'}</span></p>
      </header>

      <section className={cardClass}>
        <h2 className="text-lg font-semibold">1) Intake Form</h2>
        <form className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2" onSubmit={handleCreateIntake}>
          <label className="text-sm font-medium">Client type
            <select className={inputClass} value={clientType} onChange={(e) => setClientType(e.target.value as ClientType)}>
              <option value="individual">Individual</option>
              <option value="company">Company</option>
            </select>
          </label>
          <label className="text-sm font-medium">Client primary name*
            <input className={inputClass} value={clientName} onChange={(e) => setClientName(e.target.value)} />
          </label>
          <label className="text-sm font-medium">Email
            <input className={inputClass} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="text-sm font-medium">Deal transaction reference*
            <input className={inputClass} value={dealRef} onChange={(e) => setDealRef(e.target.value)} />
          </label>
          <label className="text-sm font-medium">Transaction type
            <select className={inputClass} value={transactionType} onChange={(e) => setTransactionType(e.target.value as DealTransactionType)}>
              <option value="purchase">Purchase</option>
              <option value="sale">Sale</option>
              <option value="transfer">Transfer</option>
              <option value="lease">Lease</option>
              <option value="rental">Rental</option>
              <option value="other">Other</option>
            </select>
          </label>
          <label className="text-sm font-medium">Property location*
            <input className={inputClass} value={propertyLocation} onChange={(e) => setPropertyLocation(e.target.value)} />
          </label>
          <label className="text-sm font-medium">Transaction value (USD)*
            <input className={inputClass} type="number" min={0} value={transactionValue} onChange={(e) => setTransactionValue(e.target.value)} />
          </label>
          <div className="flex items-end">
            <button className={buttonClass} disabled={intakeState.loading}>{intakeState.loading ? 'Saving...' : 'Create Intake'}</button>
          </div>
        </form>
        {intakeState.error && <p className="mt-3 rounded-md bg-rose-50 p-2 text-sm text-rose-700">{intakeState.error}</p>}
        {intakeState.success && <p className="mt-3 rounded-md bg-emerald-50 p-2 text-sm text-emerald-700">{intakeState.success}</p>}
      </section>

      <section className={cardClass}>
        <h2 className="text-lg font-semibold">2) Linked Parties CRUD (create + update)</h2>
        <form className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3" onSubmit={handleAddRelationship}>
          <label className="text-sm font-medium">Party type
            <select className={inputClass} value={relationshipForm.party_type} onChange={(e) => setRelationshipForm((old) => ({ ...old, party_type: e.target.value as LinkedPartyType }))}>
              <option value="individual">Individual</option>
              <option value="company">Company</option>
            </select>
          </label>
          <label className="text-sm font-medium">Role
            <select className={inputClass} value={relationshipForm.role} onChange={(e) => setRelationshipForm((old) => ({ ...old, role: e.target.value as LinkedPartyRole }))}>
              <option value="beneficial_owner">Beneficial owner</option>
              <option value="representative">Representative</option>
              <option value="co_buyer">Co-buyer</option>
              <option value="co_seller">Co-seller</option>
              <option value="payer">Payer</option>
              <option value="intermediary">Intermediary</option>
              <option value="other">Other</option>
            </select>
          </label>
          <label className="text-sm font-medium">Relationship to client*
            <input className={inputClass} value={relationshipForm.relationship_to_client} onChange={(e) => setRelationshipForm((old) => ({ ...old, relationship_to_client: e.target.value }))} />
          </label>
          <label className="text-sm font-medium">Primary name*
            <input className={inputClass} value={relationshipForm.primary_name} onChange={(e) => setRelationshipForm((old) => ({ ...old, primary_name: e.target.value }))} />
          </label>
          <div className="flex items-end">
            <button className={buttonClass} disabled={relationshipState.loading}>{relationshipState.loading ? 'Saving...' : 'Add Linked Party'}</button>
          </div>
        </form>
        {relationshipState.error && <p className="mt-3 rounded-md bg-rose-50 p-2 text-sm text-rose-700">{relationshipState.error}</p>}
        {relationshipState.success && <p className="mt-3 rounded-md bg-emerald-50 p-2 text-sm text-emerald-700">{relationshipState.success}</p>}

        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-slate-600">
                <th className="py-2">linked_party_id</th><th>Name</th><th>Role</th><th>Relation</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {linkedParties.map((party) => (
                <tr key={party.id} className="border-b border-slate-100">
                  <td className="py-2">{party.id}</td><td>{party.primary_name}</td><td>{party.role}</td><td>{party.relationship_to_client}</td>
                  <td>
                    <button className="rounded bg-slate-100 px-2 py-1 text-xs hover:bg-slate-200" onClick={async () => {
                      await api.patchRelationship(party.id, { relationship_to_client: `${party.relationship_to_client} (updated)` });
                      if (clientId && dealId) setLinkedParties(await api.getRelationships(clientId, dealId));
                      setSelectedLinkedPartyId(party.id);
                    }}>Quick update</button>
                  </td>
                </tr>
              ))}
              {linkedParties.length === 0 && <tr><td colSpan={5} className="py-4 text-slate-500">No linked parties yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <section className={cardClass}>
        <h2 className="text-lg font-semibold">3) Screening + Candidate Disposition</h2>
        <div className="mt-4 flex flex-wrap gap-3">
          <button className={buttonClass} onClick={handleRunScreening} disabled={screeningState.loading}>{screeningState.loading ? 'Running...' : 'Run Screening'}</button>
        </div>
        {screeningState.error && <p className="mt-3 rounded-md bg-rose-50 p-2 text-sm text-rose-700">{screeningState.error}</p>}
        {screeningState.success && <p className="mt-3 rounded-md bg-emerald-50 p-2 text-sm text-emerald-700">{screeningState.success}</p>}

        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <div className="rounded-lg border border-slate-200 p-4">
            <h3 className="text-sm font-semibold">Results</h3>
            {screeningResults.map((result) => (
              <div key={result.id} className="mt-3 rounded border border-slate-100 p-3">
                <p className="text-xs text-slate-600">
                  Result #{result.id} · Subject: {result.subject_name_snapshot}
                </p>
                <p className="mt-1 text-xs text-slate-600">
                  Provider: <span className="font-medium">{result.provider_name}</span> · Status: <span className="font-medium">{result.status}</span> · Screened: <span className="font-medium">{formatDateTime(result.screened_at)}</span>
                </p>
                <ul className="mt-2 space-y-1 text-sm">
                  {result.candidates.map((candidate) => (
                    <li key={candidate.id}>
                      <button className="w-full rounded border border-slate-200 px-2 py-1 text-left hover:bg-slate-50" onClick={() => setSelectedCandidateId(candidate.id)}>
                        {(() => {
                          const payload = candidate.candidate_payload as Record<string, unknown> | null;
                          const topicsText = extractTopics(candidate).join(', ');
                          const notesOrTopics = candidate.notes ?? (topicsText || 'n/a');
                          const candidateAlerts = extractPolicyAlerts(candidate);
                          return (
                            <>
                        <p>candidate_id={candidate.id} · {candidate.matched_name} · {candidate.disposition}</p>
                        <p className="mt-1 text-xs text-slate-600">
                          dataset: {candidate.dataset ?? 'n/a'} · match_score: {candidate.match_score ?? 'n/a'} · country: {candidate.country ?? 'n/a'} · category: {candidate.match_category}
                        </p>
                        <p className="mt-1 text-xs text-slate-600">notes/topics: {notesOrTopics}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          payload excerpt: schema={String(payload?.schema ?? 'n/a')} · id={String(payload?.id ?? 'n/a')}
                        </p>
                        {candidateAlerts.length > 0 && (
                          <div className="mt-2 space-y-1">
                            {candidateAlerts.map((alert, index) => (
                              <div key={`${candidate.id}-alert-${index}`} className="text-xs">
                                <span className={severityBadgeClass(alert.severity)}>{alert.severity.toUpperCase()}</span>
                                <span className="ml-2 text-slate-700">{alert.source ? `${alert.source}: ` : ''}{alert.rationale ?? 'No rationale provided by backend policy output.'}</span>
                              </div>
                            ))}
                          </div>
                        )}
                            </>
                          );
                        })()}
                      </button>
                    </li>
                  ))}
                  {result.candidates.length === 0 && <li className="text-slate-500">No candidates.</li>}
                </ul>
              </div>
            ))}
            {screeningResults.length === 0 && <p className="mt-2 text-sm text-slate-500">No screening data yet.</p>}
          </div>

          <form className="rounded-lg border border-slate-200 p-4" onSubmit={handleDispositionUpdate}>
            <h3 className="text-sm font-semibold">Update disposition</h3>
            <p className="mt-1 text-xs text-slate-600">Selected candidate_id: {selectedCandidateId ?? 'none'}</p>
            {selectedCandidateHasHighSeverity && (
              <p className="mt-2 rounded-md bg-amber-50 p-2 text-xs text-amber-700">
                High-severity policy outcome detected. A disposition reason is required.
              </p>
            )}
            <label className="mt-3 block text-sm font-medium">Disposition
              <select className={inputClass} value={candidateDisposition} onChange={(e) => setCandidateDisposition(e.target.value as CandidateDisposition)}>
                <option value="pending">pending</option>
                <option value="confirmed_match">confirmed_match</option>
                <option value="needs_edd">needs_edd</option>
                <option value="false_positive">false_positive</option>
              </select>
            </label>
            <label className="mt-3 block text-sm font-medium">Reason
              <textarea className={inputClass} value={dispositionReason} onChange={(e) => setDispositionReason(e.target.value)} rows={3} required={selectedCandidateHasHighSeverity} />
            </label>
            <button className={`mt-4 ${buttonClass}`} disabled={screeningState.loading || (selectedCandidateHasHighSeverity && dispositionReason.trim().length === 0)}>Apply Disposition</button>
            <p className="mt-2 text-xs text-slate-500">Available candidate IDs: {flatCandidates.map((c) => c.id).join(', ') || '—'}</p>
          </form>
        </div>
      </section>

      <section className={cardClass}>
        <h2 className="text-lg font-semibold">4) PEP/RCA Case Management</h2>
        <p className="mt-2 text-sm text-slate-600">Cases open automatically when PEP/RCA candidates are dispositioned as confirmed match or needs EDD.</p>
        <div className="mt-3 space-y-2">
          {pepCases.map((pepCase) => (
            <div key={pepCase.id} className="rounded border border-slate-200 p-3 text-sm">
              <p>Case #{pepCase.id} · candidate_id={pepCase.screening_candidate_id} · status={pepCase.status}</p>
              <p className="text-xs text-slate-600">senior approval={pepCase.senior_approval_status} · SoW={pepCase.source_of_wealth_status} · SoF={pepCase.source_of_funds_status} · enhanced monitoring={pepCase.enhanced_monitoring ? 'yes' : 'no'}</p>
            </div>
          ))}
          {pepCases.length === 0 && <p className="text-sm text-slate-500">No PEP/RCA cases yet.</p>}
        </div>
      </section>

      <section className={cardClass}>
        <h2 className="text-lg font-semibold">5) Risk Assessment</h2>
        <div className="mt-3 flex flex-wrap gap-3">
          <button className={buttonClass} onClick={handleRunRisk} disabled={riskState.loading}>{riskState.loading ? 'Running...' : 'Run Risk Assessment'}</button>
          <button className={buttonClass} onClick={handleGenerateComplianceDecision} disabled={decisionState.loading}>{decisionState.loading ? 'Generating...' : 'Generate Compliance Decision'}</button>
        </div>
        {riskState.error && <p className="mt-3 rounded-md bg-rose-50 p-2 text-sm text-rose-700">{riskState.error}</p>}
        {riskState.success && <p className="mt-3 rounded-md bg-emerald-50 p-2 text-sm text-emerald-700">{riskState.success}</p>}
        {decisionState.error && <p className="mt-3 rounded-md bg-rose-50 p-2 text-sm text-rose-700">{decisionState.error}</p>}
        {decisionState.success && <p className="mt-3 rounded-md bg-emerald-50 p-2 text-sm text-emerald-700">{decisionState.success}</p>}

        {riskAssessment && (
          <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm">
            <p><span className="font-medium">Risk ID:</span> {riskAssessment.id}</p>
            <p><span className="font-medium">Client ID:</span> {riskAssessment.client_id}</p>
            <p><span className="font-medium">Deal ID:</span> {riskAssessment.deal_id ?? 'N/A'}</p>
            <p><span className="font-medium">Total score:</span> {riskAssessment.total_score}</p>
            <p><span className="font-medium">Level:</span> {riskAssessment.risk_level}</p>
            <p><span className="font-medium">Summary:</span> {riskAssessment.summary ?? 'No summary.'}</p>
            <p><span className="font-medium">Assessed at:</span> {new Date(riskAssessment.assessed_at).toLocaleString()}</p>
          </div>
        )}

        <div className="mt-4 rounded-lg border border-slate-200 p-4 text-sm">
          <h3 className="font-semibold">Decision Brief</h3>
          {!complianceDecision && <p className="mt-2 text-slate-500">No decision brief yet. Generate one after screening/risk data is available.</p>}
          {complianceDecision && (
            <>
              <p className="mt-2">
                <span className="font-medium">Verdict:</span>{' '}
                <span className={severityBadgeClass(complianceDecision.verdict === 'edd_required' ? 'high' : complianceDecision.verdict === 'review_required' ? 'medium' : 'low')}>
                  {complianceDecision.verdict.toUpperCase()}
                </span>
              </p>
              <div className="mt-3">
                <p className="font-medium">Top reasons</p>
                <ul className="ml-4 list-disc">
                  {complianceDecision.top_reasons.slice(0, 3).map((reason, index) => <li key={`${reason}-${index}`}>{reason}</li>)}
                  {complianceDecision.top_reasons.length === 0 && <li>No top reasons returned.</li>}
                </ul>
              </div>
              <div className="mt-3">
                <p className="font-medium">Required actions</p>
                <ul className="mt-1 space-y-1">
                  {complianceDecision.required_actions.map((action, index) => (
                    <li key={`${action.action}-${index}`} className="flex items-center gap-2">
                      <input type="checkbox" checked={action.status === 'verified'} readOnly />
                      <span>{action.action}{action.pep_case_id ? ` (case ${action.pep_case_id})` : ''}</span>
                    </li>
                  ))}
                  {complianceDecision.required_actions.length === 0 && <li>No pending required actions.</li>}
                </ul>
              </div>
              <p className="mt-3 text-xs text-slate-600">
                Evidence · candidates: {complianceDecision.evidence.candidate_ids.join(', ') || '—'} · pep cases: {complianceDecision.evidence.pep_case_ids.join(', ') || '—'} · risk: {complianceDecision.evidence.risk_assessment_id}
              </p>
              <button className="mt-3 rounded bg-slate-100 px-2 py-1 text-xs hover:bg-slate-200" onClick={() => setDecisionExpanded((old) => !old)}>
                {decisionExpanded ? 'Hide Why' : 'Show Why'}
              </button>
              {decisionExpanded && (
                <div className="mt-3 rounded border border-slate-100 bg-slate-50 p-3">
                  <p className="font-medium">Why</p>
                  <ul className="mt-2 space-y-2 text-xs">
                    {(complianceDecision.why.candidate_context ?? []).map((entry) => (
                      <li key={`why-${entry.candidate_id}`}>
                        candidate_id={entry.candidate_id} · match_category={entry.match_category} · alerts={(entry.policy_alerts ?? []).map((a) => `${a.severity ?? 'unknown'}:${a.rationale ?? 'n/a'}`).join(' | ') || 'none'}
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 text-xs text-slate-700">
                    Triggered risk factors: {(complianceDecision.why.risk?.triggered_factors ?? []).join(', ') || 'none'}
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      </section>
    </main>
  );
}
