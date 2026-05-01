import { FormEvent, useEffect, useState } from 'react';

import { api, ClientType, DealTransactionType, IntakeListItem } from '../api/client';
import { Button, PageHeader, Panel, Select, TextInput } from '../components/ui';

export default function ClientIntakePage() {
  const [items, setItems] = useState<IntakeListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [clientType, setClientType] = useState<ClientType>('individual');
  const [transactionType, setTransactionType] = useState<DealTransactionType>('purchase');
  const [primaryName, setPrimaryName] = useState('');
  const [email, setEmail] = useState('');
  const [reference, setReference] = useState('');
  const [location, setLocation] = useState('');
  const [value, setValue] = useState('0');

  function refresh() {
    api.listIntakes().then(setItems).catch((loadError) => setError((loadError as Error).message));
  }

  useEffect(() => {
    refresh();
  }, []);

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

  return (
    <div className="space-y-6">
      <PageHeader title="Client Intake" description="Create or update clients and deal records before they enter structured KYC onboarding." />
      {error ? <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p> : null}
      <div className="grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
        <Panel title="New Intake" subtitle="Create a new client and initial deal context.">
          <form className="space-y-3" onSubmit={handleSubmit}>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Client type</label>
              <Select value={clientType} onChange={(event) => setClientType(event.target.value as ClientType)}>
                <option value="individual">Individual</option>
                <option value="company">Company</option>
              </Select>
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Primary name</label>
              <TextInput value={primaryName} onChange={(event) => setPrimaryName(event.target.value)} />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Email</label>
              <TextInput value={email} onChange={(event) => setEmail(event.target.value)} />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Deal reference</label>
              <TextInput value={reference} onChange={(event) => setReference(event.target.value)} />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Transaction type</label>
              <Select value={transactionType} onChange={(event) => setTransactionType(event.target.value as DealTransactionType)}>
                <option value="purchase">Purchase</option>
                <option value="sale">Sale</option>
                <option value="lease">Lease</option>
                <option value="rental">Rental</option>
                <option value="transfer">Transfer</option>
                <option value="other">Other</option>
              </Select>
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Property location</label>
              <TextInput value={location} onChange={(event) => setLocation(event.target.value)} />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Transaction value</label>
              <TextInput type="number" value={value} onChange={(event) => setValue(event.target.value)} />
            </div>
            <Button disabled={loading} className="w-full">{loading ? 'Saving…' : 'Create intake'}</Button>
          </form>
        </Panel>

        <Panel title="Client Register" subtitle="Operational view of current client and deal intake state.">
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-slate-500">
                <tr>
                  <th className="py-2 font-medium">Client</th>
                  <th className="py-2 font-medium">Type</th>
                  <th className="py-2 font-medium">Deal</th>
                  <th className="py-2 font-medium">Status</th>
                  <th className="py-2 font-medium">Risk</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={`${item.client_id}-${item.deal_id ?? 'none'}`} className="border-b border-slate-100">
                    <td className="py-3">
                      <div className="font-medium text-slate-900">{item.primary_name}</div>
                      <div className="text-xs text-slate-500">client_id={item.client_id}</div>
                    </td>
                    <td>{item.client_type}</td>
                    <td>
                      <div>{item.transaction_reference ?? '—'}</div>
                      <div className="text-xs text-slate-500">{item.transaction_type ?? 'no deal'}</div>
                    </td>
                    <td>
                      <div>{item.client_status}</div>
                      <div className="text-xs text-slate-500">{item.deal_status ?? '—'}</div>
                    </td>
                    <td>{item.risk_level ?? 'unassessed'}</td>
                  </tr>
                ))}
                {items.length === 0 ? <tr><td colSpan={5} className="py-6 text-slate-500">No clients yet.</td></tr> : null}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </div>
  );
}
