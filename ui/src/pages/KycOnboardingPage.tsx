import { FormEvent, useEffect, useState } from 'react';

import { api, IntakeListItem, KycOnboardingStatus, KycProfilePayload, TaxClearanceStatus } from '../api/client';
import { Button, PageHeader, Panel, Select, TextArea, TextInput } from '../components/ui';

const emptyProfile: KycProfilePayload = {
  deal_id: null,
  onboarding_status: 'draft',
  full_legal_name: '',
  date_of_birth: null,
  national_id_or_passport_number: null,
  nationality: null,
  address: null,
  contact_details: null,
  occupation: null,
  employer: null,
  business_activity: null,
  company_registration_number: null,
  tax_identification_number: null,
  tax_clearance_status: 'unknown',
  residency_status: null,
  cross_border_indicator: false,
  pep_declaration: false,
  related_party_declaration: false,
  notes: null
};

export default function KycOnboardingPage() {
  const [clients, setClients] = useState<IntakeListItem[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null);
  const [form, setForm] = useState<KycProfilePayload>(emptyProfile);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.listIntakes().then((items) => {
      setClients(items);
      if (items[0] && selectedClientId === null) setSelectedClientId(items[0].client_id);
    }).catch((loadError) => setError((loadError as Error).message));
  }, [selectedClientId]);

  useEffect(() => {
    if (!selectedClientId) return;
    api.getKycProfile(selectedClientId)
      .then((profile) => {
        if (profile) {
          setForm({
            deal_id: profile.deal_id,
            onboarding_status: profile.onboarding_status,
            full_legal_name: profile.full_legal_name,
            date_of_birth: profile.date_of_birth,
            national_id_or_passport_number: profile.national_id_or_passport_number,
            nationality: profile.nationality,
            address: profile.address,
            contact_details: profile.contact_details,
            occupation: profile.occupation,
            employer: profile.employer,
            business_activity: profile.business_activity,
            company_registration_number: profile.company_registration_number,
            tax_identification_number: profile.tax_identification_number,
            tax_clearance_status: profile.tax_clearance_status,
            residency_status: profile.residency_status,
            cross_border_indicator: profile.cross_border_indicator,
            pep_declaration: profile.pep_declaration,
            related_party_declaration: profile.related_party_declaration,
            notes: profile.notes
          });
          return;
        }
        const selectedClient = clients.find((item) => item.client_id === selectedClientId);
        setForm({ ...emptyProfile, deal_id: selectedClient?.deal_id ?? null, full_legal_name: selectedClient?.primary_name ?? '' });
      })
      .catch((loadError) => setError((loadError as Error).message));
  }, [clients, selectedClientId]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!selectedClientId) return;
    setSaving(true);
    setError(null);
    try {
      await api.upsertKycProfile(selectedClientId, form);
    } catch (submitError) {
      setError((submitError as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="KYC Onboarding" description="Capture core KYC, residency, PEP, related-party, and cross-border information for individuals and companies." />
      {error ? <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p> : null}
      <Panel title="Onboarding Profile" subtitle="Structured KYC record tied to a client and, where applicable, the active deal.">
        <div className="mb-4 max-w-sm">
          <label className="mb-2 block text-sm font-medium text-slate-700">Client</label>
          <Select value={selectedClientId ?? ''} onChange={(event) => setSelectedClientId(Number(event.target.value))}>
            {clients.map((item) => (
              <option key={item.client_id} value={item.client_id}>
                {item.primary_name} ({item.client_type})
              </option>
            ))}
          </Select>
        </div>
        <form className="grid gap-4 md:grid-cols-2" onSubmit={handleSubmit}>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Onboarding status</label>
            <Select value={form.onboarding_status} onChange={(event) => setForm((current) => ({ ...current, onboarding_status: event.target.value as KycOnboardingStatus }))}>
              <option value="draft">Draft</option>
              <option value="in_progress">In progress</option>
              <option value="ready_for_review">Ready for review</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
            </Select>
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Full legal name</label>
            <TextInput value={form.full_legal_name} onChange={(event) => setForm((current) => ({ ...current, full_legal_name: event.target.value }))} />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Date of birth</label>
            <TextInput type="datetime-local" value={form.date_of_birth ? form.date_of_birth.slice(0, 16) : ''} onChange={(event) => setForm((current) => ({ ...current, date_of_birth: event.target.value ? new Date(event.target.value).toISOString() : null }))} />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">ID or passport number</label>
            <TextInput value={form.national_id_or_passport_number ?? ''} onChange={(event) => setForm((current) => ({ ...current, national_id_or_passport_number: event.target.value || null }))} />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Nationality</label>
            <TextInput value={form.nationality ?? ''} onChange={(event) => setForm((current) => ({ ...current, nationality: event.target.value || null }))} />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Residency status</label>
            <TextInput value={form.residency_status ?? ''} onChange={(event) => setForm((current) => ({ ...current, residency_status: event.target.value || null }))} />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Occupation</label>
            <TextInput value={form.occupation ?? ''} onChange={(event) => setForm((current) => ({ ...current, occupation: event.target.value || null }))} />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Employer</label>
            <TextInput value={form.employer ?? ''} onChange={(event) => setForm((current) => ({ ...current, employer: event.target.value || null }))} />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Company registration number</label>
            <TextInput value={form.company_registration_number ?? ''} onChange={(event) => setForm((current) => ({ ...current, company_registration_number: event.target.value || null }))} />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Tax ID</label>
            <TextInput value={form.tax_identification_number ?? ''} onChange={(event) => setForm((current) => ({ ...current, tax_identification_number: event.target.value || null }))} />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-700">Tax clearance status</label>
            <Select value={form.tax_clearance_status} onChange={(event) => setForm((current) => ({ ...current, tax_clearance_status: event.target.value as TaxClearanceStatus }))}>
              <option value="unknown">Unknown</option>
              <option value="pending">Pending</option>
              <option value="verified">Verified</option>
              <option value="exempt">Exempt</option>
              <option value="rejected">Rejected</option>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <input id="cross-border" type="checkbox" checked={form.cross_border_indicator} onChange={(event) => setForm((current) => ({ ...current, cross_border_indicator: event.target.checked }))} />
            <label htmlFor="cross-border" className="text-sm text-slate-700">Cross-border indicator</label>
          </div>
          <div className="flex items-center gap-2">
            <input id="pep-declaration" type="checkbox" checked={form.pep_declaration} onChange={(event) => setForm((current) => ({ ...current, pep_declaration: event.target.checked }))} />
            <label htmlFor="pep-declaration" className="text-sm text-slate-700">PEP declaration</label>
          </div>
          <div className="md:col-span-2 flex items-center gap-2">
            <input id="related-party" type="checkbox" checked={form.related_party_declaration} onChange={(event) => setForm((current) => ({ ...current, related_party_declaration: event.target.checked }))} />
            <label htmlFor="related-party" className="text-sm text-slate-700">Related-party declaration</label>
          </div>
          <div className="md:col-span-2">
            <label className="mb-2 block text-sm font-medium text-slate-700">Address</label>
            <TextArea rows={3} value={form.address ?? ''} onChange={(event) => setForm((current) => ({ ...current, address: event.target.value || null }))} />
          </div>
          <div className="md:col-span-2">
            <label className="mb-2 block text-sm font-medium text-slate-700">Contact details</label>
            <TextArea rows={2} value={form.contact_details ?? ''} onChange={(event) => setForm((current) => ({ ...current, contact_details: event.target.value || null }))} />
          </div>
          <div className="md:col-span-2">
            <label className="mb-2 block text-sm font-medium text-slate-700">Business activity</label>
            <TextArea rows={3} value={form.business_activity ?? ''} onChange={(event) => setForm((current) => ({ ...current, business_activity: event.target.value || null }))} />
          </div>
          <div className="md:col-span-2">
            <label className="mb-2 block text-sm font-medium text-slate-700">Notes</label>
            <TextArea rows={3} value={form.notes ?? ''} onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value || null }))} />
          </div>
          <div className="md:col-span-2">
            <Button disabled={saving}>{saving ? 'Saving…' : 'Save onboarding profile'}</Button>
          </div>
        </form>
      </Panel>
    </div>
  );
}
