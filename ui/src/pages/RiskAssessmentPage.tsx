import { FormEvent, useEffect, useState } from 'react';

import { api, IntakeListItem, RiskAssessmentResponse } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { hasCapability } from '../auth/permissions';
import { Button, PageHeader, Panel, Select, TextArea } from '../components/ui';

export default function RiskAssessmentPage() {
  const [clients, setClients] = useState<IntakeListItem[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null);
  const [risk, setRisk] = useState<RiskAssessmentResponse | null>(null);
  const [overrideLevel, setOverrideLevel] = useState('high');
  const [justification, setJustification] = useState('');
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth();
  const canManage = hasCapability(user?.role, 'assess_risk', user?.capabilities);

  useEffect(() => {
    api.listIntakes().then((items) => {
      setClients(items);
      if (items[0] && selectedClientId === null) setSelectedClientId(items[0].client_id);
    }).catch((loadError) => setError((loadError as Error).message));
  }, [selectedClientId]);

  useEffect(() => {
    if (!selectedClientId) return;
    api.getLatestRisk(selectedClientId).then(setRisk).catch(() => setRisk(null));
  }, [selectedClientId]);

  async function handleRunRisk() {
    if (!selectedClientId) return;
    setError(null);
    try {
      setRisk(await api.runRisk(selectedClientId));
    } catch (runError) {
      setError((runError as Error).message);
    }
  }

  async function handleOverride(event: FormEvent) {
    event.preventDefault();
    if (!selectedClientId) return;
    setError(null);
    try {
      await api.createRiskOverride(selectedClientId, { override_level: overrideLevel, justification });
      setRisk(await api.getLatestRisk(selectedClientId));
      setJustification('');
    } catch (overrideError) {
      setError((overrideError as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Risk Assessment" description="Explainable scoring across screening, documents, ownership, CDD, monitoring, and analyst override." actions={canManage ? <Button onClick={handleRunRisk}>Run risk assessment</Button> : undefined} />
      {!canManage ? <p className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-700">You have read-only access to this page.</p> : null}
      {error ? <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p> : null}
      <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
        <Panel title="Override" subtitle="Manual override requires explicit justification and is fully auditable.">
          <div className="space-y-4">
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Client</label>
              <Select value={selectedClientId ?? ''} onChange={(event) => setSelectedClientId(Number(event.target.value))}>
                {clients.map((item) => <option key={item.client_id} value={item.client_id}>{item.primary_name}</option>)}
              </Select>
            </div>
            <form className="space-y-3" onSubmit={handleOverride}>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">Override level</label>
                <Select value={overrideLevel} onChange={(event) => setOverrideLevel(event.target.value)}>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </Select>
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">Justification</label>
                <TextArea rows={4} value={justification} onChange={(event) => setJustification(event.target.value)} />
              </div>
              <Button className="w-full" disabled={!canManage}>Record override</Button>
            </form>
          </div>
        </Panel>

        <Panel title="Risk Output" subtitle="Current system-calculated outcome and latest override trail.">
          {!risk ? <p className="text-sm text-slate-500">No risk assessment yet.</p> : (
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Risk level</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-950">{risk.risk_assessment.risk_level}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Score</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-950">{risk.risk_assessment.total_score}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Recommended action</p>
                  <p className="mt-2 text-sm font-medium text-slate-950">{risk.recommended_action}</p>
                </div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
                <p className="font-medium text-slate-900">Summary</p>
                <p className="mt-2">{risk.risk_assessment.summary}</p>
              </div>
              <div>
                <p className="mb-2 text-sm font-medium text-slate-800">Overrides</p>
                <div className="space-y-2">
                  {risk.overrides.map((override) => (
                    <div key={override.id} className="rounded-xl border border-slate-200 bg-white p-3 text-sm">
                      <p className="font-medium text-slate-900">{override.override_level}</p>
                      <p className="mt-1 text-slate-600">{override.justification}</p>
                    </div>
                  ))}
                  {risk.overrides.length === 0 ? <p className="text-sm text-slate-500">No manual overrides recorded.</p> : null}
                </div>
              </div>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
