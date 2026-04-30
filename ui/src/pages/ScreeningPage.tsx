import { FormEvent, useEffect, useMemo, useState } from 'react';

import { api, CandidateDisposition, IntakeListItem, ScreeningResult } from '../api/client';
import { Button, PageHeader, Panel, Select, TextArea } from '../components/ui';

export default function ScreeningPage() {
  const [clients, setClients] = useState<IntakeListItem[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null);
  const [results, setResults] = useState<ScreeningResult[]>([]);
  const [candidateId, setCandidateId] = useState<number | null>(null);
  const [disposition, setDisposition] = useState<CandidateDisposition>('pending');
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);

  const candidates = useMemo(() => results.flatMap((result) => result.candidates), [results]);

  function refresh(clientId: number) {
    api.getScreeningByClientId(clientId).then(setResults).catch((loadError) => setError((loadError as Error).message));
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

  async function handleRun() {
    if (!selectedClientId) return;
    setError(null);
    try {
      const screeningResults = await api.runScreening(selectedClientId);
      setResults(screeningResults);
    } catch (runError) {
      setError((runError as Error).message);
    }
  }

  async function handleDisposition(event: FormEvent) {
    event.preventDefault();
    if (!candidateId || !selectedClientId) return;
    setError(null);
    try {
      await api.patchCandidateDisposition(candidateId, disposition, reason);
      refresh(selectedClientId);
      setReason('');
    } catch (submitError) {
      setError((submitError as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Screening" description="Run provider screening for clients and linked parties, review matches, and disposition candidates into standard review or EDD escalation." actions={<Button onClick={handleRun}>Run screening</Button>} />
      {error ? <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p> : null}
      <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
        <Panel title="Disposition" subtitle="Review a candidate and record the analyst outcome.">
          <div className="space-y-3">
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Client</label>
              <Select value={selectedClientId ?? ''} onChange={(event) => setSelectedClientId(Number(event.target.value))}>
                {clients.map((item) => <option key={item.client_id} value={item.client_id}>{item.primary_name}</option>)}
              </Select>
            </div>
            <form className="space-y-3" onSubmit={handleDisposition}>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">Candidate</label>
                <Select value={candidateId ?? ''} onChange={(event) => setCandidateId(Number(event.target.value))}>
                  <option value="">Select candidate</option>
                  {candidates.map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.matched_name} ({candidate.match_category})</option>)}
                </Select>
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">Disposition</label>
                <Select value={disposition} onChange={(event) => setDisposition(event.target.value as CandidateDisposition)}>
                  <option value="pending">Pending</option>
                  <option value="confirmed_match">Confirmed match</option>
                  <option value="needs_edd">Needs EDD</option>
                  <option value="false_positive">False positive</option>
                </Select>
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">Reason</label>
                <TextArea rows={4} value={reason} onChange={(event) => setReason(event.target.value)} />
              </div>
              <Button className="w-full">Apply disposition</Button>
            </form>
          </div>
        </Panel>

        <Panel title="Screening History" subtitle="Provider result sets and candidate review queue.">
          <div className="space-y-4">
            {results.map((result) => (
              <div key={result.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-sm font-medium text-slate-900">{result.subject_name_snapshot}</p>
                <p className="mt-1 text-xs text-slate-500">provider={result.provider_name} · status={result.status} · screened={new Date(result.screened_at).toLocaleString()}</p>
                <div className="mt-3 overflow-x-auto">
                  <table className="min-w-full text-left text-sm">
                    <thead className="border-b border-slate-200 text-slate-500">
                      <tr>
                        <th className="py-2 font-medium">Candidate</th>
                        <th className="py-2 font-medium">Category</th>
                        <th className="py-2 font-medium">Score</th>
                        <th className="py-2 font-medium">Disposition</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.candidates.map((candidate) => (
                        <tr key={candidate.id} className="border-b border-slate-100">
                          <td className="py-2">{candidate.matched_name}</td>
                          <td>{candidate.match_category}</td>
                          <td>{candidate.match_score ?? '—'}</td>
                          <td>{candidate.disposition}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
            {results.length === 0 ? <p className="text-sm text-slate-500">No screening results yet.</p> : null}
          </div>
        </Panel>
      </div>
    </div>
  );
}
