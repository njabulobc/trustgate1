import { useMemo, useState } from 'react';

import { api } from '../../api/client';
import { useAsyncQuery } from '../../hooks/useAsyncQuery';
import { useCaseContext } from '../../state/CaseContext';

export function RiskHistoryPage() {
  const { clientId, dealId } = useCaseContext();
  const [level, setLevel] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 5;
  const { data, loading, error, refetch } = useAsyncQuery(() => api.getRiskHistory(clientId!, dealId ?? undefined), [clientId, dealId], Boolean(clientId));

  const filtered = useMemo(() => (data?.items ?? []).filter((item) => !level || item.risk_level === level), [data, level]);
  const paged = filtered.slice((page - 1) * pageSize, page * pageSize);
  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));

  if (!clientId) return <p className="rounded-xl border bg-white p-6">Create intake first.</p>;

  return <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"><h2 className="text-lg font-semibold">Risk History</h2><div className="mt-3 flex gap-2"><button className="rounded bg-brand-500 px-3 py-2 text-white" onClick={async () => { await api.runRisk(clientId, dealId ?? undefined); refetch(); }}>Run risk</button><select className="rounded border p-2" value={level} onChange={(e) => { setLevel(e.target.value); setPage(1); }}><option value="">All levels</option><option value="low">low</option><option value="medium">medium</option><option value="high">high</option></select></div>{loading && <p className="mt-2 text-sm">Loading risk history…</p>}{error && <p className="mt-2 text-sm text-rose-700">{error}</p>}<ul className="mt-3 space-y-2">{paged.map((item) => <li key={item.id} className="rounded border p-2 text-sm">#{item.id} · {item.risk_level} · score {item.total_score} · {new Date(item.assessed_at).toLocaleString()}</li>)}{!loading && paged.length===0 && <li className="text-sm text-slate-500">No history entries.</li>}</ul><div className="mt-3 flex gap-2"><button className="rounded border px-2" disabled={page===1} onClick={() => setPage((p) => p-1)}>Prev</button><span className="text-sm">Page {page}/{totalPages}</span><button className="rounded border px-2" disabled={page===totalPages} onClick={() => setPage((p) => p+1)}>Next</button></div></section>;
}
