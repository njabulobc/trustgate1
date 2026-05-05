import { ChangeEvent, FormEvent, useEffect, useState } from 'react';

import { api, DocumentChecklistSummary, DocumentLifecycleStatus, DocumentRecord, IntakeListItem } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { hasCapability } from '../auth/permissions';
import { Button, PageHeader, Panel, Select, TextInput } from '../components/ui';

export default function KycDocumentsPage() {
  const [clients, setClients] = useState<IntakeListItem[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [checklist, setChecklist] = useState<DocumentChecklistSummary | null>(null);
  const [documentType, setDocumentType] = useState('national_id');
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth();
  const canEdit = hasCapability(user?.role, 'edit_kyc', user?.capabilities);

  function refresh(clientId: number) {
    Promise.all([api.listDocuments(clientId), api.getDocumentChecklist(clientId)])
      .then(([items, checklistSummary]) => {
        setDocuments(items);
        setChecklist(checklistSummary);
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

  async function handleUpload(event: FormEvent) {
    event.preventDefault();
    if (!selectedClientId || !file || !canEdit) return;
    setError(null);
    try {
      await api.uploadDocument(selectedClientId, { document_type: documentType, file });
      setFile(null);
      refresh(selectedClientId);
    } catch (uploadError) {
      setError((uploadError as Error).message);
    }
  }

  async function handleStatusChange(documentId: number, status: DocumentLifecycleStatus) {
    if (!canEdit) return;
    try {
      await api.reviewDocument(documentId, { lifecycle_status: status });
      if (selectedClientId) refresh(selectedClientId);
    } catch (updateError) {
      setError((updateError as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="KYC Documents" description="Upload supporting documents, track lifecycle states, and identify gaps before review closure." />
      {!canEdit ? <p className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-700">You have read-only access to this page.</p> : null}
      {error ? <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p> : null}
      <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <Panel title="Upload" subtitle="Attach supporting evidence and maintain the checklist lifecycle.">
          <div className="space-y-4">
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Client</label>
              <Select value={selectedClientId ?? ''} onChange={(event) => setSelectedClientId(Number(event.target.value))}>
                {clients.map((item) => <option key={item.client_id} value={item.client_id}>{item.primary_name}</option>)}
              </Select>
            </div>
            <form className="space-y-3" onSubmit={handleUpload}>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">Document type</label>
                <TextInput value={documentType} onChange={(event) => setDocumentType(event.target.value)} />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">File</label>
                <input type="file" onChange={(event: ChangeEvent<HTMLInputElement>) => setFile(event.target.files?.[0] ?? null)} />
              </div>
              <Button disabled={!file || !canEdit}>Upload document</Button>
            </form>
            <div className="rounded-xl bg-slate-50 p-3 text-sm text-slate-700">
              <p className="font-medium text-slate-900">Checklist summary</p>
              <p className="mt-2">Verified: {checklist?.verified_documents ?? 0}</p>
              <p>Expired: {checklist?.expired_documents ?? 0}</p>
              <p>Resubmission: {checklist?.requires_resubmission ?? 0}</p>
              <p className="mt-2 text-xs text-slate-500">Missing: {checklist?.missing_document_types.join(', ') || 'none'}</p>
            </div>
          </div>
        </Panel>

        <Panel title="Document Register" subtitle="Verification workspace for uploaded KYC evidence.">
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-slate-500">
                <tr>
                  <th className="py-2 font-medium">Type</th>
                  <th className="py-2 font-medium">File</th>
                  <th className="py-2 font-medium">Status</th>
                  <th className="py-2 font-medium">Expiry</th>
                  <th className="py-2 font-medium">Review</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((document) => (
                  <tr key={document.id} className="border-b border-slate-100">
                    <td className="py-3">{document.document_type}</td>
                    <td>
                      <div>{document.file_name}</div>
                      <div className="text-xs text-slate-500">{document.file_size_bytes} bytes</div>
                    </td>
                    <td>{document.lifecycle_status}</td>
                    <td>{document.expiry_date ?? '—'}</td>
                    <td>
                      <Select value={document.lifecycle_status} disabled={!canEdit} onChange={(event) => handleStatusChange(document.id, event.target.value as DocumentLifecycleStatus)}>
                        <option value="submitted">Submitted</option>
                        <option value="under_review">Under review</option>
                        <option value="verified">Verified</option>
                        <option value="rejected">Rejected</option>
                        <option value="expired">Expired</option>
                        <option value="resubmission_required">Resubmission required</option>
                      </Select>
                    </td>
                  </tr>
                ))}
                {documents.length === 0 ? <tr><td colSpan={5} className="py-6 text-slate-500">No documents uploaded yet.</td></tr> : null}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </div>
  );
}
