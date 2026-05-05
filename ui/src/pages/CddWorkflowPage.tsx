import { FormEvent, useEffect, useState } from 'react';

import { api, CddWorkflowPayload, IntakeListItem, VerificationStatus, WorkflowStatus } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { hasCapability } from '../auth/permissions';
import { Button, PageHeader, Panel, Select, TextArea } from '../components/ui';

const emptyWorkflow: CddWorkflowPayload = {
  deal_id: null,
  assigned_analyst_id: null,
  completion_status: 'open',
  source_of_funds_status: 'pending',
  source_of_wealth_status: 'pending',
  payment_method_review: null,
  transaction_purpose_review: null,
  expected_activity_profile: null,
  adverse_transaction_indicators: null,
  supporting_evidence_checklist: { source_of_funds: false, source_of_wealth: false, payment_method: false, transaction_purpose: false },
  analyst_decision: 'pending',
  reviewer_decision: 'pending',
  analyst_notes: null,
  reviewer_notes: null
};

export default function CddWorkflowPage() {
  const [clients, setClients] = useState<IntakeListItem[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null);
  const [form, setForm] = useState<CddWorkflowPayload>(emptyWorkflow);
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth();
  const canEdit = hasCapability(user?.role, 'assess_risk', user?.capabilities);

  useEffect(() => {
    api.listIntakes().then((items) => {
      setClients(items);
      if (items[0] && selectedClientId === null) setSelectedClientId(items[0].client_id);
    }).catch((loadError) => setError((loadError as Error).message));
  }, [selectedClientId]);

  useEffect(() => {
    if (!selectedClientId || !canEdit) return;
    api.getCddWorkflow(selectedClientId)
      .then((workflow) => {
        setForm({
          deal_id: workflow.deal_id,
          assigned_analyst_id: workflow.assigned_analyst_id,
          completion_status: workflow.completion_status,
          source_of_funds_status: workflow.source_of_funds_status,
          source_of_wealth_status: workflow.source_of_wealth_status,
          payment_method_review: workflow.payment_method_review,
          transaction_purpose_review: workflow.transaction_purpose_review,
          expected_activity_profile: workflow.expected_activity_profile,
          adverse_transaction_indicators: workflow.adverse_transaction_indicators,
          supporting_evidence_checklist: workflow.supporting_evidence_checklist,
          analyst_decision: workflow.analyst_decision,
          reviewer_decision: workflow.reviewer_decision,
          analyst_notes: workflow.analyst_notes,
          reviewer_notes: workflow.reviewer_notes
        });
      })
      .catch((loadError) => setError((loadError as Error).message));
  }, [selectedClientId]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!selectedClientId || !canEdit) return;
    setError(null);
    try {
      await api.upsertCddWorkflow(selectedClientId, form);
    } catch (submitError) {
      setError((submitError as Error).message);
    }
  }

  function toggleChecklist(key: string) {
    const current = (form.supporting_evidence_checklist ?? {}) as Record<string, boolean>;
    setForm((existing) => ({
      ...existing,
      supporting_evidence_checklist: {
        ...current,
        [key]: !current[key]
      }
    }));
  }

  return (
    <div className="space-y-6">
      <PageHeader title="CDD Workflow" description="Structured due diligence review for source of funds, source of wealth, payment methods, expected activity, and analyst decisions." />
      {!canEdit ? <p className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-700">You have read-only access to this page.</p> : null}
      {error ? <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p> : null}
      <Panel title="CDD Case" subtitle="One structured workflow per client context.">
        <div className="mb-4 max-w-sm">
          <label className="mb-2 block text-sm font-medium text-slate-700">Client</label>
          <Select value={selectedClientId ?? ''} onChange={(event) => setSelectedClientId(Number(event.target.value))}>
            {clients.map((item) => <option key={item.client_id} value={item.client_id}>{item.primary_name}</option>)}
          </Select>
        </div>
        <form className="grid gap-4 md:grid-cols-2" onSubmit={handleSubmit}>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Workflow status</label>
            <Select value={form.completion_status} onChange={(event) => setForm((current) => ({ ...current, completion_status: event.target.value as WorkflowStatus }))}>
              <option value="open">Open</option>
              <option value="in_progress">In progress</option>
              <option value="under_review">Under review</option>
              <option value="completed">Completed</option>
              <option value="escalated">Escalated</option>
            </Select>
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Source of funds status</label>
            <Select value={form.source_of_funds_status} onChange={(event) => setForm((current) => ({ ...current, source_of_funds_status: event.target.value as VerificationStatus }))}>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="escalated">Escalated</option>
            </Select>
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Source of wealth status</label>
            <Select value={form.source_of_wealth_status} onChange={(event) => setForm((current) => ({ ...current, source_of_wealth_status: event.target.value as VerificationStatus }))}>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="escalated">Escalated</option>
            </Select>
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Analyst decision</label>
            <Select value={form.analyst_decision} onChange={(event) => setForm((current) => ({ ...current, analyst_decision: event.target.value as VerificationStatus }))}>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="escalated">Escalated</option>
            </Select>
          </div>
          <div className="md:col-span-2">
            <label className="mb-2 block text-sm font-medium text-slate-700">Payment method review</label>
            <TextArea rows={3} value={form.payment_method_review ?? ''} onChange={(event) => setForm((current) => ({ ...current, payment_method_review: event.target.value || null }))} />
          </div>
          <div className="md:col-span-2">
            <label className="mb-2 block text-sm font-medium text-slate-700">Transaction purpose review</label>
            <TextArea rows={3} value={form.transaction_purpose_review ?? ''} onChange={(event) => setForm((current) => ({ ...current, transaction_purpose_review: event.target.value || null }))} />
          </div>
          <div className="md:col-span-2">
            <label className="mb-2 block text-sm font-medium text-slate-700">Expected activity profile</label>
            <TextArea rows={3} value={form.expected_activity_profile ?? ''} onChange={(event) => setForm((current) => ({ ...current, expected_activity_profile: event.target.value || null }))} />
          </div>
          <div className="md:col-span-2">
            <label className="mb-2 block text-sm font-medium text-slate-700">Adverse indicators</label>
            <TextArea rows={3} value={form.adverse_transaction_indicators ?? ''} onChange={(event) => setForm((current) => ({ ...current, adverse_transaction_indicators: event.target.value || null }))} />
          </div>
          <div className="md:col-span-2 rounded-xl border border-slate-200 bg-slate-50 p-3">
            <p className="mb-2 text-sm font-medium text-slate-800">Supporting evidence checklist</p>
            {['source_of_funds', 'source_of_wealth', 'payment_method', 'transaction_purpose'].map((key) => (
              <label key={key} className="flex items-center gap-2 py-1 text-sm text-slate-700">
                <input type="checkbox" checked={Boolean((form.supporting_evidence_checklist as Record<string, boolean> | null)?.[key])} onChange={() => toggleChecklist(key)} />
                {key.replace(/_/g, ' ')}
              </label>
            ))}
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Analyst notes</label>
            <TextArea rows={3} value={form.analyst_notes ?? ''} onChange={(event) => setForm((current) => ({ ...current, analyst_notes: event.target.value || null }))} />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Reviewer notes</label>
            <TextArea rows={3} value={form.reviewer_notes ?? ''} onChange={(event) => setForm((current) => ({ ...current, reviewer_notes: event.target.value || null }))} />
          </div>
          <div className="md:col-span-2">
            <Button disabled={!canEdit}>Save CDD workflow</Button>
          </div>
        </form>
      </Panel>
    </div>
  );
}
