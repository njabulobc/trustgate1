import { FormEvent, useEffect, useMemo, useState } from 'react';

import {
  api,
  CandidateDisposition,
  DealTransactionType,
  IntakePayload,
  IntakeResponse,
  LinkedParty,
  LinkedPartyPayload,
  LinkedPartyRole,
  LinkedPartyType,
  ScreeningResult,
  RiskAssessment,
  ClientType
} from './api/client';

type AsyncState = {
  loading: boolean;
  error: string | null;
  success: string | null;
};

const cardClass = 'rounded-xl border border-slate-200 bg-white p-6 shadow-sm';
const inputClass = 'w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-50';
const buttonClass = 'rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50';

export default function App() {
  const [intake, setIntake] = useState<IntakeResponse | null>(null);
  const [clientType, setClientType] = useState<ClientType>('INDIVIDUAL');
  const [clientName, setClientName] = useState('');
  const [email, setEmail] = useState('');
  const [dealRef, setDealRef] = useState('');
  const [transactionType, setTransactionType] = useState<DealTransactionType>('PURCHASE');
  const [propertyLocation, setPropertyLocation] = useState('');
  const [transactionValue, setTransactionValue] = useState('0');

  const [relationshipForm, setRelationshipForm] = useState({
    party_type: 'INDIVIDUAL' as LinkedPartyType,
    role: 'OWNER' as LinkedPartyRole,
    relationship_to_client: '',
    primary_name: ''
  });
  const [linkedParties, setLinkedParties] = useState<LinkedParty[]>([]);
  const [selectedLinkedPartyId, setSelectedLinkedPartyId] = useState<number | null>(null);

  const [screeningResults, setScreeningResults] = useState<ScreeningResult[]>([]);
  const [selectedCandidateId, setSelectedCandidateId] = useState<number | null>(null);
  const [candidateDisposition, setCandidateDisposition] = useState<CandidateDisposition>('OPEN');
  const [dispositionReason, setDispositionReason] = useState('');

  const [riskAssessment, setRiskAssessment] = useState<RiskAssessment | null>(null);

  const [intakeState, setIntakeState] = useState<AsyncState>({ loading: false, error: null, success: null });
  const [relationshipState, setRelationshipState] = useState<AsyncState>({ loading: false, error: null, success: null });
  const [screeningState, setScreeningState] = useState<AsyncState>({ loading: false, error: null, success: null });
  const [riskState, setRiskState] = useState<AsyncState>({ loading: false, error: null, success: null });

  const clientId = intake?.client.id;
  const dealId = intake?.deal.id;

  useEffect(() => {
    if (!clientId || !dealId) return;
    api.getRelationships(clientId, dealId).then(setLinkedParties).catch(() => undefined);
    api.getScreeningByClientId(clientId).then(setScreeningResults).catch(() => undefined);
    api.getLatestRisk(clientId, dealId).then((res) => setRiskAssessment(res.risk_assessment)).catch(() => undefined);
  }, [clientId, dealId]);

  const flatCandidates = useMemo(
    () => screeningResults.flatMap((result) => result.candidates.map((candidate) => ({ ...candidate, screeningResultId: result.id }))),
    [screeningResults]
  );

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
          status: 'DRAFT'
        },
        deal: {
          transaction_reference: dealRef,
          transaction_type: transactionType,
          property_location: propertyLocation,
          transaction_value: transactionValue,
          currency: 'USD',
          is_cross_border: false,
          status: 'DRAFT'
        }
      };
      const created = await api.createIntake(payload);
      setIntake(created);
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
      setScreeningState({ loading: false, error: null, success: `Screening complete with ${results.length} result set(s).` });
    } catch (error) {
      setScreeningState({ loading: false, error: (error as Error).message, success: null });
    }
  }

  async function handleDispositionUpdate(event: FormEvent) {
    event.preventDefault();
    if (!selectedCandidateId) {
      setScreeningState({ loading: false, error: 'Pick a candidate_id to update disposition.', success: null });
      return;
    }
    setScreeningState({ loading: true, error: null, success: null });
    try {
      const candidate = await api.patchCandidateDisposition(selectedCandidateId, candidateDisposition, dispositionReason || undefined);
      if (clientId) {
        const refreshed = await api.getScreeningByClientId(clientId);
        setScreeningResults(refreshed);
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
              <option value="INDIVIDUAL">Individual</option>
              <option value="ENTITY">Entity</option>
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
              <option value="PURCHASE">Purchase</option>
              <option value="SALE">Sale</option>
              <option value="TRANSFER">Transfer</option>
              <option value="LEASE">Lease</option>
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
              <option value="INDIVIDUAL">Individual</option>
              <option value="ENTITY">Entity</option>
            </select>
          </label>
          <label className="text-sm font-medium">Role
            <select className={inputClass} value={relationshipForm.role} onChange={(e) => setRelationshipForm((old) => ({ ...old, role: e.target.value as LinkedPartyRole }))}>
              <option value="OWNER">Owner</option>
              <option value="BENEFICIAL_OWNER">Beneficial owner</option>
              <option value="DIRECTOR">Director</option>
              <option value="AUTHORIZED_SIGNATORY">Authorized signatory</option>
              <option value="INTERMEDIARY">Intermediary</option>
              <option value="OTHER">Other</option>
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
                <p className="text-xs text-slate-600">Result #{result.id} · Subject: {result.subject_name_snapshot}</p>
                <ul className="mt-2 space-y-1 text-sm">
                  {result.candidates.map((candidate) => (
                    <li key={candidate.id}>
                      <button className="w-full rounded border border-slate-200 px-2 py-1 text-left hover:bg-slate-50" onClick={() => setSelectedCandidateId(candidate.id)}>
                        candidate_id={candidate.id} · {candidate.matched_name} · {candidate.disposition}
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
            <label className="mt-3 block text-sm font-medium">Disposition
              <select className={inputClass} value={candidateDisposition} onChange={(e) => setCandidateDisposition(e.target.value as CandidateDisposition)}>
                <option value="OPEN">OPEN</option>
                <option value="CLEAR">CLEAR</option>
                <option value="ESCALATED">ESCALATED</option>
                <option value="FALSE_POSITIVE">FALSE_POSITIVE</option>
              </select>
            </label>
            <label className="mt-3 block text-sm font-medium">Reason
              <textarea className={inputClass} value={dispositionReason} onChange={(e) => setDispositionReason(e.target.value)} rows={3} />
            </label>
            <button className={`mt-4 ${buttonClass}`} disabled={screeningState.loading}>Apply Disposition</button>
            <p className="mt-2 text-xs text-slate-500">Available candidate IDs: {flatCandidates.map((c) => c.id).join(', ') || '—'}</p>
          </form>
        </div>
      </section>

      <section className={cardClass}>
        <h2 className="text-lg font-semibold">4) Risk Assessment</h2>
        <button className={`mt-3 ${buttonClass}`} onClick={handleRunRisk} disabled={riskState.loading}>{riskState.loading ? 'Running...' : 'Run Risk Assessment'}</button>
        {riskState.error && <p className="mt-3 rounded-md bg-rose-50 p-2 text-sm text-rose-700">{riskState.error}</p>}
        {riskState.success && <p className="mt-3 rounded-md bg-emerald-50 p-2 text-sm text-emerald-700">{riskState.success}</p>}

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
      </section>
    </main>
  );
}
