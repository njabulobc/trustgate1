import { FormEvent, useMemo, useState } from 'react';

import { api, LinkedPartyRole, LinkedPartyType } from '../../api/client';
import { useAsyncQuery } from '../../hooks/useAsyncQuery';
import { useCaseContext } from '../../state/CaseContext';

export function RelationshipsPage() {
  const { clientId, dealId } = useCaseContext();
  const [name, setName] = useState('');
  const [relationship, setRelationship] = useState('');
  const [partyType, setPartyType] = useState<LinkedPartyType>('individual');
  const [role, setRole] = useState<LinkedPartyRole>('beneficial_owner');
  const [filter, setFilter] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 5;
  const { data, loading, error, refetch } = useAsyncQuery(() => api.getRelationships(clientId!, dealId!), [clientId, dealId], Boolean(clientId && dealId));

  const filtered = useMemo(() => (data ?? []).filter((item) => item.primary_name.toLowerCase().includes(filter.toLowerCase())), [data, filter]);
  const paged = useMemo(() => filtered.slice((page - 1) * pageSize, page * pageSize), [filtered, page]);
  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!clientId || !dealId) return;
    await api.createRelationship({ client_id: clientId, deal_id: dealId, primary_name: name, relationship_to_client: relationship, role, party_type: partyType, screening_required: true });
    setName('');
    setRelationship('');
    refetch();
  }

  if (!clientId || !dealId) return <p className="rounded-xl border bg-white p-6">Create intake first.</p>;

  return <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"><h2 className="text-lg font-semibold">Relationships</h2><form className="mt-3 grid gap-2 md:grid-cols-3" onSubmit={submit}><input className="rounded border p-2" placeholder="Primary name" value={name} onChange={(e) => setName(e.target.value)} /><input className="rounded border p-2" placeholder="Relationship" value={relationship} onChange={(e) => setRelationship(e.target.value)} /><select className="rounded border p-2" value={partyType} onChange={(e) => setPartyType(e.target.value as LinkedPartyType)}><option value="individual">individual</option><option value="company">company</option></select><select className="rounded border p-2" value={role} onChange={(e) => setRole(e.target.value as LinkedPartyRole)}><option value="beneficial_owner">beneficial_owner</option><option value="representative">representative</option><option value="co_buyer">co_buyer</option><option value="co_seller">co_seller</option><option value="payer">payer</option><option value="intermediary">intermediary</option><option value="other">other</option></select><button className="rounded bg-brand-500 px-3 py-2 text-white">Add linked party</button></form><input className="mt-4 rounded border p-2" placeholder="Filter by name" value={filter} onChange={(e) => {setFilter(e.target.value); setPage(1);}} />{loading && <p className="mt-2 text-sm">Loading linked parties…</p>}{error && <p className="mt-2 text-sm text-rose-700">{error}</p>}<ul className="mt-3 space-y-2">{paged.map((item) => <li key={item.id} className="rounded border p-2 text-sm">#{item.id} {item.primary_name} · {item.role}</li>)}{!loading && paged.length===0 && <li className="text-sm text-slate-500">No records.</li>}</ul><div className="mt-3 flex gap-2"><button className="rounded border px-2" disabled={page===1} onClick={() => setPage((p) => p-1)}>Prev</button><span className="text-sm">Page {page}/{totalPages}</span><button className="rounded border px-2" disabled={page===totalPages} onClick={() => setPage((p) => p+1)}>Next</button></div></section>;
}
