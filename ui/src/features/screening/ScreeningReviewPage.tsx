import { useMemo, useState } from 'react';

import { api, CandidateDisposition, QueueStatus } from '../../api/client';
import { useAsyncQuery } from '../../hooks/useAsyncQuery';
import { useAuth } from '../../state/AuthContext';
import { useCaseContext } from '../../state/CaseContext';

export function ScreeningReviewPage() {
  const { clientId, dealId } = useCaseContext();
  const { user } = useAuth();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [disposition, setDisposition] = useState<CandidateDisposition>('pending');
  const [reason, setReason] = useState('');
  const [workflowNote, setWorkflowNote] = useState('');
  const [assignTo, setAssignTo] = useState('');
  const [status, setStatus] = useState<QueueStatus>('queued');
  const [actionError, setActionError] = useState('');

  const { data, loading, error, refetch } = useAsyncQuery(() => api.getScreeningByClientId(clientId!), [clientId], Boolean(clientId));
  const candidates = useMemo(() => (data ?? []).flatMap((result) => result.candidates), [data]);
  const filtered = candidates.filter((candidate) => candidate.matched_name.toLowerCase().includes(reason.toLowerCase()) || candidate.disposition.includes(disposition));

  if (!clientId || !dealId) return <p className="rounded-xl border bg-white p-6">Create intake first.</p>;

  return <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"><h2 className="text-lg font-semibold">Screening Review</h2><div className="mt-3 flex gap-2"><button className="rounded bg-brand-500 px-3 py-2 text-white" onClick={async () => { await api.runScreening(clientId); refetch(); }}>Run screening</button></div>{loading && <p className="mt-2 text-sm">Loading screening results…</p>}{error && <p className="mt-2 text-sm text-rose-700">{error}</p>}<ul className="mt-3 space-y-2">{filtered.map((candidate) => <li key={candidate.id}><button className={`w-full rounded border p-2 text-left text-sm ${selectedId===candidate.id ? 'bg-slate-50' : ''}`} onClick={() => setSelectedId(candidate.id)}>#{candidate.id} {candidate.matched_name} · {candidate.disposition}</button></li>)}{filtered.length===0 && !loading && <li className="text-sm text-slate-500">No candidates yet.</li>}</ul><div className="mt-4 rounded border p-3"><h3 className="font-medium">Review action</h3><p className="text-xs">Selected candidate: {selectedId ?? 'none'}</p><select className="mt-2 rounded border p-2" value={disposition} onChange={(e) => setDisposition(e.target.value as CandidateDisposition)}><option value="pending">pending</option><option value="confirmed_match">confirmed_match</option><option value="needs_edd">needs_edd</option><option value="false_positive">false_positive</option></select><textarea className="mt-2 w-full rounded border p-2" placeholder="Reason / filter" value={reason} onChange={(e) => setReason(e.target.value)} />{(user?.role === 'reviewer' || user?.role === 'superuser') && <button className="mt-2 rounded bg-brand-500 px-3 py-2 text-white" onClick={async () => { if (!selectedId) return; await api.patchCandidateDisposition(selectedId, disposition, reason || undefined); refetch(); }}>Update disposition</button>}<p className="mt-2 text-xs text-slate-500">Only reviewer/superuser can update dispositions.</p></div><div className="mt-4 rounded border p-3"><h3 className="font-medium">Workflow queue</h3><textarea className="mt-2 w-full rounded border p-2" placeholder="Queue notes" value={workflowNote} onChange={(e) => setWorkflowNote(e.target.value)} /><div className="mt-2 flex flex-wrap gap-2"><button className="rounded border px-2 py-1" onClick={async () => { try { setActionError(''); await api.queueCase(dealId, workflowNote); } catch (e) { setActionError((e as Error).message);} }}>Queue case</button><input className="rounded border p-2" placeholder="Assign reviewer" value={assignTo} onChange={(e) => setAssignTo(e.target.value)} />{(user?.role === 'reviewer' || user?.role === 'superuser') && <button className="rounded border px-2 py-1" onClick={async () => { try { setActionError(''); await api.assignCase(dealId, assignTo); } catch (e) { setActionError((e as Error).message);} }}>Assign</button>}<select className="rounded border p-2" value={status} onChange={(e) => setStatus(e.target.value as QueueStatus)}><option value="queued">queued</option><option value="in_review">in_review</option><option value="escalated">escalated</option><option value="completed">completed</option></select>{(user?.role === 'reviewer' || user?.role === 'superuser') && <button className="rounded border px-2 py-1" onClick={async () => { try { setActionError(''); await api.transitionCase(dealId, status); } catch (e) { setActionError((e as Error).message);} }}>Change status</button>}</div>{actionError && <p className="mt-2 text-sm text-rose-700">{actionError}</p>}</div></section>;
}
