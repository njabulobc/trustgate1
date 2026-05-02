import { FormEvent, useEffect, useState } from 'react';

import { api, ClientType, DealTransactionType, IntakeListItem, LinkedParty, LinkedPartyRole, LinkedPartyType } from '../api/client';
import { Button, PageHeader, Panel, Select, TextInput } from '../components/ui';

export default function ClientIntakePage() {
  const [items, setItems] = useState<IntakeListItem[]>([]);
  const [linkedParties, setLinkedParties] = useState<LinkedParty[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedRow, setSelectedRow] = useState<IntakeListItem | null>(null);
  const [clientType, setClientType] = useState<ClientType>('individual');
  const [transactionType, setTransactionType] = useState<DealTransactionType>('purchase');
  const [primaryName, setPrimaryName] = useState('');
  const [email, setEmail] = useState('');
  const [reference, setReference] = useState('');
  const [location, setLocation] = useState('');
  const [value, setValue] = useState('0');
  const [partyName, setPartyName] = useState('');
  const [partyType, setPartyType] = useState<LinkedPartyType>('individual');
  const [partyRole, setPartyRole] = useState<LinkedPartyRole>('beneficial_owner');
  const [relationship, setRelationship] = useState('');

  function refresh() {
    api.listIntakes().then((intakes) => {
      setItems(intakes);
      if (!selectedRow && intakes[0]) setSelectedRow(intakes[0]);
    }).catch((loadError) => setError((loadError as Error).message));
  }

  function refreshLinkedParties(row: IntakeListItem | null) {
    if (!row?.deal_id) {
      setLinkedParties([]);
      return;
    }
    api.getRelationships(row.client_id, row.deal_id).then(setLinkedParties).catch((loadError) => setError((loadError as Error).message));
  }

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    refreshLinkedParties(selectedRow);
  }, [selectedRow]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.createIntake({
        client: { client_type: clientType, primary_name: primaryName, email, status: 'draft' },
        deal: {
          transaction_reference: reference,
          transaction_type: transactionType,
          property_location: location,
          transaction_value: value,
          currency: 'USD',
          is_cross_border: false,
          status: 'draft'
        }
      });
      setPrimaryName('');
      setEmail('');
      setReference('');
      setLocation('');
      setValue('0');
      refresh();
    } catch (submitError) {
      setError((submitError as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleAddLinkedParty(event: FormEvent) {
    event.preventDefault();
    if (!selectedRow?.deal_id) return;
    setError(null);
    try {
      await api.createRelationship({
        client_id: selectedRow.client_id,
        deal_id: selectedRow.deal_id,
        party_type: partyType,
        role: partyRole,
        relationship_to_client: relationship,
        primary_name: partyName,
        screening_required: true
      });
      setPartyName('');
      setRelationship('');
      refreshLinkedParties(selectedRow);
    } catch (submitError) {
      setError((submitError as Error).message);
    }
  }

  async function handleDeleteLinkedParty(linkedPartyId: number) {
    setError(null);
    try {
      await api.deleteRelationship(linkedPartyId);
      refreshLinkedParties(selectedRow);
    } catch (submitError) {
      setError((submitError as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Client Intake" description="Create or update clients and deal records before they enter structured KYC onboarding." />
      {error ? <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p> : null}
      <div className="grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
        <Panel title="New Intake" subtitle="Create a new client and initial deal context.">
          <form className="space-y-3" onSubmit={handleSubmit}>{/* unchanged form */}
            <div><label className="mb-2 block text-sm font-medium text-slate-700">Client type</label><Select value={clientType} onChange={(event) => setClientType(event.target.value as ClientType)}><option value="individual">Individual</option><option value="company">Company</option></Select></div>
            <div><label className="mb-2 block text-sm font-medium text-slate-700">Primary name</label><TextInput value={primaryName} onChange={(event) => setPrimaryName(event.target.value)} /></div>
            <div><label className="mb-2 block text-sm font-medium text-slate-700">Email</label><TextInput value={email} onChange={(event) => setEmail(event.target.value)} /></div>
            <div><label className="mb-2 block text-sm font-medium text-slate-700">Deal reference</label><TextInput value={reference} onChange={(event) => setReference(event.target.value)} /></div>
            <div><label className="mb-2 block text-sm font-medium text-slate-700">Transaction type</label><Select value={transactionType} onChange={(event) => setTransactionType(event.target.value as DealTransactionType)}><option value="purchase">Purchase</option><option value="sale">Sale</option><option value="lease">Lease</option><option value="rental">Rental</option><option value="transfer">Transfer</option><option value="other">Other</option></Select></div>
            <div><label className="mb-2 block text-sm font-medium text-slate-700">Property location</label><TextInput value={location} onChange={(event) => setLocation(event.target.value)} /></div>
            <div><label className="mb-2 block text-sm font-medium text-slate-700">Transaction value</label><TextInput type="number" value={value} onChange={(event) => setValue(event.target.value)} /></div>
            <Button disabled={loading} className="w-full">{loading ? 'Saving…' : 'Create intake'}</Button>
          </form>
        </Panel>

        <div className="space-y-6">
          <Panel title="Client Register" subtitle="Operational view of current client and deal intake state.">
            <div className="overflow-x-auto"><table className="min-w-full text-left text-sm"><thead className="border-b border-slate-200 text-slate-500"><tr><th className="py-2 font-medium">Client</th><th className="py-2 font-medium">Type</th><th className="py-2 font-medium">Deal</th><th className="py-2 font-medium">Status</th><th className="py-2 font-medium">Risk</th></tr></thead><tbody>
              {items.map((item) => (
                <tr key={`${item.client_id}-${item.deal_id ?? 'none'}`} className="cursor-pointer border-b border-slate-100" onClick={() => setSelectedRow(item)}>
                  <td className="py-3"><div className="font-medium text-slate-900">{item.primary_name}</div><div className="text-xs text-slate-500">client_id={item.client_id}</div></td><td>{item.client_type}</td><td><div>{item.transaction_reference ?? '—'}</div><div className="text-xs text-slate-500">{item.transaction_type ?? 'no deal'}</div></td><td><div>{item.client_status}</div><div className="text-xs text-slate-500">{item.deal_status ?? '—'}</div></td><td>{item.risk_level ?? 'unassessed'}</td>
                </tr>
              ))}
              {items.length === 0 ? <tr><td colSpan={5} className="py-6 text-slate-500">No clients yet.</td></tr> : null}
            </tbody></table></div>
          </Panel>

          <Panel title="Linked Parties" subtitle="Create, list, and remove client-deal linked parties for screening and ownership workflows.">
            {!selectedRow?.deal_id ? <p className="text-sm text-slate-500">Select a client/deal row to manage linked parties.</p> : (
              <div className="space-y-4">
                <form className="grid gap-3 md:grid-cols-2" onSubmit={handleAddLinkedParty}>
                  <TextInput value={partyName} onChange={(event) => setPartyName(event.target.value)} placeholder="Party name" />
                  <TextInput value={relationship} onChange={(event) => setRelationship(event.target.value)} placeholder="Relationship to client" />
                  <Select value={partyType} onChange={(event) => setPartyType(event.target.value as LinkedPartyType)}><option value="individual">Individual</option><option value="company">Company</option></Select>
                  <Select value={partyRole} onChange={(event) => setPartyRole(event.target.value as LinkedPartyRole)}><option value="beneficial_owner">Beneficial owner</option><option value="representative">Representative</option><option value="co_buyer">Co-buyer</option><option value="co_seller">Co-seller</option><option value="payer">Payer</option><option value="intermediary">Intermediary</option><option value="other">Other</option></Select>
                  <Button className="md:col-span-2">Add linked party</Button>
                </form>
                <div className="space-y-2">
                  {linkedParties.map((party) => (
                    <div key={party.id} className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                      <div><p className="font-medium text-slate-900">{party.primary_name}</p><p className="text-slate-600">{party.role} · {party.relationship_to_client}</p></div>
                      <Button tone="secondary" onClick={() => handleDeleteLinkedParty(party.id)}>Remove</Button>
                    </div>
                  ))}
                  {linkedParties.length === 0 ? <p className="text-sm text-slate-500">No linked parties found.</p> : null}
                </div>
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
