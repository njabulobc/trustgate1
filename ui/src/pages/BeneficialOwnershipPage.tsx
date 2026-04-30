import { FormEvent, useEffect, useState } from 'react';

import { api, IntakeListItem, OwnershipGraphNode, OwnershipOwnerType, OwnershipPayload, OwnershipRecord } from '../api/client';
import { Button, PageHeader, Panel, Select, TextArea, TextInput } from '../components/ui';

const emptyPayload: OwnershipPayload = {
  deal_id: null,
  linked_party_id: null,
  parent_record_id: null,
  owner_name: '',
  owner_type: 'individual',
  classification: null,
  ownership_percentage: null,
  control_type: null,
  direct_ownership: true,
  indirect_ownership: false,
  nominee_indicator: false,
  trust_indicator: false,
  representative_relationship: false,
  control_without_ownership: false,
  corporate_parent_name: null,
  ownership_chain_notes: null,
  complexity_score: null
};

export default function BeneficialOwnershipPage() {
  const [clients, setClients] = useState<IntakeListItem[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null);
  const [records, setRecords] = useState<OwnershipRecord[]>([]);
  const [graph, setGraph] = useState<OwnershipGraphNode[]>([]);
  const [form, setForm] = useState<OwnershipPayload>(emptyPayload);
  const [error, setError] = useState<string | null>(null);

  function refresh(clientId: number) {
    Promise.all([api.listOwnership(clientId), api.getOwnershipGraph(clientId)])
      .then(([ownershipRecords, graphNodes]) => {
        setRecords(ownershipRecords);
        setGraph(graphNodes);
      })
      .catch((loadError) => setError((loadError as Error).message));
  }

  useEffect(() => {
    api.listIntakes().then((items) => {
      setClients(items);
      if (items[0] && selectedClientId === null) setSelectedClientId(items[0].client_id);
    }).catch((loadError) => setError((loadError as Error).message));
  }, [selectedClientId]);

  useEffect(() => {
    if (selectedClientId) refresh(selectedClientId);
  }, [selectedClientId]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!selectedClientId) return;
    setError(null);
    try {
      await api.createOwnership(selectedClientId, form);
      setForm(emptyPayload);
      refresh(selectedClientId);
    } catch (submitError) {
      setError((submitError as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Beneficial Ownership" description="Map direct and indirect ownership, control relationships, complexity flags, and representative or trust structures." />
      {error ? <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p> : null}
      <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <Panel title="Ownership Record" subtitle="Add a control or ownership record to the client structure.">
          <div className="mb-4">
            <label className="mb-2 block text-sm font-medium text-slate-700">Client</label>
            <Select value={selectedClientId ?? ''} onChange={(event) => setSelectedClientId(Number(event.target.value))}>
              {clients.map((item) => <option key={item.client_id} value={item.client_id}>{item.primary_name}</option>)}
            </Select>
          </div>
          <form className="space-y-3" onSubmit={handleSubmit}>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Owner name</label>
              <TextInput value={form.owner_name} onChange={(event) => setForm((current) => ({ ...current, owner_name: event.target.value }))} />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Owner type</label>
              <Select value={form.owner_type} onChange={(event) => setForm((current) => ({ ...current, owner_type: event.target.value as OwnershipOwnerType }))}>
                <option value="individual">Individual</option>
                <option value="company">Company</option>
                <option value="trust">Trust</option>
                <option value="nominee">Nominee</option>
              </Select>
            </div>
            <TextInput placeholder="Classification" value={form.classification ?? ''} onChange={(event) => setForm((current) => ({ ...current, classification: event.target.value || null }))} />
            <TextInput placeholder="Ownership percentage" type="number" value={form.ownership_percentage ?? ''} onChange={(event) => setForm((current) => ({ ...current, ownership_percentage: event.target.value || null }))} />
            <TextInput placeholder="Control type" value={form.control_type ?? ''} onChange={(event) => setForm((current) => ({ ...current, control_type: event.target.value || null }))} />
            <TextInput placeholder="Complexity score" type="number" value={form.complexity_score ?? ''} onChange={(event) => setForm((current) => ({ ...current, complexity_score: event.target.value || null }))} />
            <TextArea rows={3} placeholder="Ownership chain notes" value={form.ownership_chain_notes ?? ''} onChange={(event) => setForm((current) => ({ ...current, ownership_chain_notes: event.target.value || null }))} />
            <div className="grid grid-cols-2 gap-2 text-sm text-slate-700">
              {[
                ['direct_ownership', 'Direct ownership'],
                ['indirect_ownership', 'Indirect ownership'],
                ['nominee_indicator', 'Nominee indicator'],
                ['trust_indicator', 'Trust indicator'],
                ['representative_relationship', 'Representative'],
                ['control_without_ownership', 'Control without ownership']
              ].map(([key, label]) => (
                <label key={key} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={Boolean(form[key as keyof OwnershipPayload])}
                    onChange={(event) => setForm((current) => ({ ...current, [key]: event.target.checked }))}
                  />
                  {label}
                </label>
              ))}
            </div>
            <Button className="w-full">Add ownership record</Button>
          </form>
        </Panel>

        <div className="space-y-6">
          <Panel title="Ownership Table" subtitle="Structured view of ownership percentages and control types.">
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-slate-200 text-slate-500">
                  <tr>
                    <th className="py-2 font-medium">Owner</th>
                    <th className="py-2 font-medium">Type</th>
                    <th className="py-2 font-medium">Ownership</th>
                    <th className="py-2 font-medium">Control</th>
                    <th className="py-2 font-medium">Complexity</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((record) => (
                    <tr key={record.id} className="border-b border-slate-100">
                      <td className="py-3">{record.owner_name}</td>
                      <td>{record.owner_type}</td>
                      <td>{record.ownership_percentage ?? '—'}</td>
                      <td>{record.control_type ?? '—'}</td>
                      <td>{record.complexity_score ?? '—'}</td>
                    </tr>
                  ))}
                  {records.length === 0 ? <tr><td colSpan={5} className="py-6 text-slate-500">No ownership records yet.</td></tr> : null}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel title="Control Graph" subtitle="Graph-style hierarchy using parent-child ownership references.">
            <div className="space-y-2">
              {graph.map((node) => (
                <div key={node.id} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm">
                  <p className="font-medium text-slate-900">{node.owner_name}</p>
                  <p className="mt-1 text-slate-600">parent={node.parent_record_id ?? 'root'} · ownership={node.ownership_percentage ?? '—'} · control={node.control_type ?? '—'}</p>
                </div>
              ))}
              {graph.length === 0 ? <p className="text-sm text-slate-500">No graph nodes yet.</p> : null}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
