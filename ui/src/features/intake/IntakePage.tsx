import { FormEvent, useState } from 'react';

import { api, ClientType, DealTransactionType } from '../../api/client';
import { useCaseContext } from '../../state/CaseContext';

export function IntakePage() {
  const { setIntake, clientId, dealId } = useCaseContext();
  const [clientType, setClientType] = useState<ClientType>('individual');
  const [clientName, setClientName] = useState('');
  const [dealRef, setDealRef] = useState('');
  const [transactionType, setTransactionType] = useState<DealTransactionType>('purchase');
  const [propertyLocation, setPropertyLocation] = useState('');
  const [transactionValue, setTransactionValue] = useState('0');
  const [state, setState] = useState({ loading: false, error: '', success: '' });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setState({ loading: true, error: '', success: '' });
    try {
      const created = await api.createIntake({ client: { client_type: clientType, primary_name: clientName, status: 'draft' }, deal: { transaction_reference: dealRef, transaction_type: transactionType, property_location: propertyLocation, transaction_value: transactionValue, currency: 'USD', is_cross_border: false, status: 'draft' } });
      setIntake(created);
      setState({ loading: false, error: '', success: `Created client ${created.client.id} / deal ${created.deal.id}` });
    } catch (error) {
      setState({ loading: false, error: (error as Error).message, success: '' });
    }
  }

  return <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"><h2 className="text-lg font-semibold">Intake</h2><p className="text-xs text-slate-500">Current case: client {clientId ?? '—'} / deal {dealId ?? '—'}</p><form className="mt-3 grid gap-3 md:grid-cols-2" onSubmit={submit}><input className="rounded border p-2" placeholder="Client name" value={clientName} onChange={(e) => setClientName(e.target.value)} /><input className="rounded border p-2" placeholder="Deal ref" value={dealRef} onChange={(e) => setDealRef(e.target.value)} /><input className="rounded border p-2" placeholder="Property location" value={propertyLocation} onChange={(e) => setPropertyLocation(e.target.value)} /><input className="rounded border p-2" type="number" value={transactionValue} onChange={(e) => setTransactionValue(e.target.value)} /><select className="rounded border p-2" value={clientType} onChange={(e) => setClientType(e.target.value as ClientType)}><option value="individual">individual</option><option value="company">company</option></select><select className="rounded border p-2" value={transactionType} onChange={(e) => setTransactionType(e.target.value as DealTransactionType)}><option value="purchase">purchase</option><option value="sale">sale</option><option value="transfer">transfer</option><option value="lease">lease</option><option value="rental">rental</option><option value="other">other</option></select><button className="rounded bg-brand-500 px-3 py-2 text-white" disabled={state.loading}>{state.loading ? 'Saving...' : 'Create intake'}</button></form>{state.error && <p className="mt-2 text-sm text-rose-700">{state.error}</p>}{state.success && <p className="mt-2 text-sm text-emerald-700">{state.success}</p>}</section>;
}
