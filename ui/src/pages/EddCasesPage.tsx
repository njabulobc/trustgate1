import { FormEvent, useEffect, useState } from 'react';

import { api, EddCase, EddCasePayload, EddCasePriority, EddCaseStatus, IntakeListItem } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { hasCapability } from '../auth/permissions';
import { Button, PageHeader, Panel, Select, TextArea, TextInput } from '../components/ui';

const emptyCase: EddCasePayload = {
  deal_id: null,
  source_module: 'manual',
  case_type: 'enhanced_due_diligence',
  trigger_reason: '',
  assigned_analyst_id: null,
  priority: 'medium',
  status: 'open',
  required_actions: null,
  evidence_checklist: null,
  analyst_findings: null,
  reviewer_comments: null,
  approval_outcome: null,
  closure_decision: null,
  due_at: null
};

export default function EddCasesPage() {
  const [clients, setClients] = useState<IntakeListItem[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null);
  const [cases, setCases] = useState<EddCase[]>([]);
  const [form, setForm] = useState<EddCasePayload>(emptyCase);
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth();
  const canManage = hasCapability(user?.role, 'manage_edd', user?.capabilities);

  function refresh(clientId?: number | null) {
    api.listEddCases(clientId).then(setCases).catch((loadError) => setError((loadError as Error).message));
  }

  useEffect(() => {
    api.listIntakes().then((items) => {
      setClients(items);
      if (items[0] && selectedClientId === null) setSelectedClientId(items[0].client_id);
    }).catch((loadError) => setError((loadError as Error).message));
    refresh();
  }, [selectedClientId]);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (!selectedClientId) return;
    setError(null);
    try {
      await api.createEddCase(selectedClientId, form);
      setForm(emptyCase);
      refresh(selectedClientId);
    } catch (submitError) {
      setError((submitError as Error).message);
    }
  }

  async function handleStatusChange(caseId: number, statusValue: EddCaseStatus) {
    const current = cases.find((item) => item.id === caseId);
    if (!current) return;
    try {
      await api.updateEddCase(caseId, { ...current, status: statusValue });
      refresh(selectedClientId);
    } catch (updateError) {
      setError((updateError as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="EDD Cases" description="Generalized enhanced due diligence case management across screening, ownership, transaction, and monitoring triggers." />
      {!canManage ? <p className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-700">You have read-only access to this page.</p> : null}
      {error ? <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p> : null}
      <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <Panel title="New EDD Case" subtitle="Open a generalized EDD case from any risk or workflow trigger.">
          <div className="mb-4">
            <label className="mb-2 block text-sm font-medium text-slate-700">Client</label>
            <Select value={selectedClientId ?? ''} onChange={(event) => setSelectedClientId(Number(event.target.value))}>
              {clients.map((item) => <option key={item.client_id} value={item.client_id}>{item.primary_name}</option>)}
            </Select>
          </div>
          <form className="space-y-3" onSubmit={handleCreate}>
            <TextInput placeholder="Case type" value={form.case_type} onChange={(event) => setForm((current) => ({ ...current, case_type: event.target.value }))} />
            <TextInput placeholder="Source module" value={form.source_module} onChange={(event) => setForm((current) => ({ ...current, source_module: event.target.value }))} />
            <Select value={form.priority} onChange={(event) => setForm((current) => ({ ...current, priority: event.target.value as EddCasePriority }))}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </Select>
            <TextArea rows={4} placeholder="Trigger reason" value={form.trigger_reason} onChange={(event) => setForm((current) => ({ ...current, trigger_reason: event.target.value }))} />
            <TextArea rows={3} placeholder="Required actions JSON or notes" value={JSON.stringify(form.required_actions ?? {}, null, 2)} onChange={(event) => setForm((current) => ({ ...current, required_actions: event.target.value ? { note: event.target.value } : null }))} />
            <Button className="w-full" disabled={!canManage}>Create EDD case</Button>
          </form>
        </Panel>

        <Panel title="EDD Register" subtitle="Track aging, ownership, approvals, and closure decisions.">
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-slate-500">
                <tr>
                  <th className="py-2 font-medium">Type</th>
                  <th className="py-2 font-medium">Trigger</th>
                  <th className="py-2 font-medium">Priority</th>
                  <th className="py-2 font-medium">Status</th>
                  <th className="py-2 font-medium">Updated</th>
                </tr>
              </thead>
              <tbody>
                {cases.map((caseItem) => (
                  <tr key={caseItem.id} className="border-b border-slate-100">
                    <td className="py-3">{caseItem.case_type}</td>
                    <td className="max-w-sm">{caseItem.trigger_reason}</td>
                    <td>{caseItem.priority}</td>
                    <td>
                      <Select value={caseItem.status} disabled={!canManage} onChange={(event) => handleStatusChange(caseItem.id, event.target.value as EddCaseStatus)}>
                        <option value="open">Open</option>
                        <option value="assigned">Assigned</option>
                        <option value="in_review">In review</option>
                        <option value="awaiting_information">Awaiting information</option>
                        <option value="escalated">Escalated</option>
                        <option value="approved">Approved</option>
                        <option value="rejected">Rejected</option>
                        <option value="closed">Closed</option>
                      </Select>
                    </td>
                    <td>{new Date(caseItem.updated_at).toLocaleString()}</td>
                  </tr>
                ))}
                {cases.length === 0 ? <tr><td colSpan={5} className="py-6 text-slate-500">No EDD cases yet.</td></tr> : null}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </div>
  );
}
