import { useState } from 'react';

import { api, QueueStatus } from '../../api/client';
import { useAsyncQuery } from '../../hooks/useAsyncQuery';

export function WorkflowQueuePage() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<QueueStatus | ''>('');
  const [assignedReviewer, setAssignedReviewer] = useState('');
  const [search, setSearch] = useState('');
  const pageSize = 10;

  const { data, loading, error, refetch } = useAsyncQuery(
    () => api.listCases({ page, pageSize, status, assignedReviewer, search }),
    [page, status, assignedReviewer, search],
    true
  );

  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / pageSize));

  return <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"><h2 className="text-lg font-semibold">Case Queue</h2><div className="mt-3 flex flex-wrap gap-2"><select className="rounded border p-2" value={status} onChange={(e) => { setStatus(e.target.value as QueueStatus | ''); setPage(1); }}><option value="">All statuses</option><option value="new">new</option><option value="queued">queued</option><option value="in_review">in_review</option><option value="escalated">escalated</option><option value="completed">completed</option></select><input className="rounded border p-2" placeholder="Assigned reviewer" value={assignedReviewer} onChange={(e) => { setAssignedReviewer(e.target.value); setPage(1);} } /><input className="rounded border p-2" placeholder="Search notes" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1);} } /><button className="rounded border px-2" onClick={refetch}>Refresh</button></div>{loading && <p className="mt-2 text-sm">Loading queue...</p>}{error && <p className="mt-2 text-sm text-rose-700">{error}</p>}<ul className="mt-3 space-y-2">{(data?.items ?? []).map((item) => <li key={item.id} className="rounded border p-2 text-sm">Case #{item.id} · client {item.client_id} · deal {item.deal_id} · {item.status} · assignee {item.assigned_reviewer ?? '—'}</li>)}{!loading && (data?.items?.length ?? 0) === 0 && <li className="text-sm text-slate-500">No queue records.</li>}</ul><div className="mt-3 flex gap-2"><button className="rounded border px-2" disabled={page===1} onClick={() => setPage((p)=>p-1)}>Prev</button><span className="text-sm">Page {page}/{totalPages}</span><button className="rounded border px-2" disabled={page===totalPages} onClick={() => setPage((p)=>p+1)}>Next</button></div></section>;
}
