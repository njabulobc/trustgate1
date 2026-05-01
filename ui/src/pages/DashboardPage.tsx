import { useEffect, useState } from 'react';

import { api, DashboardSummary, WorkbenchItem } from '../api/client';
import { Metric, PageHeader, Panel, StatusPill } from '../components/ui';

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [queue, setQueue] = useState<WorkbenchItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.getDashboardSummary(), api.getWorkbenchQueue()])
      .then(([dashboardSummary, queueResponse]) => {
        setSummary(dashboardSummary);
        setQueue(queueResponse.items.slice(0, 8));
      })
      .catch((loadError) => setError((loadError as Error).message));
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Current compliance workload across onboarding, reviews, investigations, monitoring, and reporting."
      />
      {error ? <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p> : null}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Metric label="Total clients" value={summary?.total_clients ?? '—'} />
        <Metric label="Pending KYC" value={summary?.pending_kyc_reviews ?? '—'} />
        <Metric label="Open EDD" value={summary?.open_edd_cases ?? '—'} />
        <Metric label="Open alerts" value={summary?.open_alerts ?? '—'} />
        <Metric label="Incomplete documents" value={summary?.incomplete_document_files ?? '—'} />
        <Metric label="Open CDD" value={summary?.open_cdd_tasks ?? '—'} />
        <Metric label="Screening hits" value={summary?.screening_hits_requiring_review ?? '—'} />
        <Metric label="High risk" value={summary?.high_risk_clients_or_deals ?? '—'} />
      </div>

      <Panel title="Analyst Queue" subtitle="The most recent operational items across the platform.">
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="text-slate-500">
              <tr className="border-b border-slate-200">
                <th className="py-2 font-medium">Module</th>
                <th className="py-2 font-medium">Work item</th>
                <th className="py-2 font-medium">Status</th>
                <th className="py-2 font-medium">Priority</th>
                <th className="py-2 font-medium">Updated</th>
              </tr>
            </thead>
            <tbody>
              {queue.map((item) => (
                <tr key={`${item.module}-${item.item_type}-${item.item_id}`} className="border-b border-slate-100">
                  <td className="py-3">{item.module}</td>
                  <td>{item.title}</td>
                  <td><StatusPill label={item.status} tone={item.status.includes('closed') ? 'neutral' : 'warning'} /></td>
                  <td>{item.severity_or_priority ?? 'n/a'}</td>
                  <td>{new Date(item.updated_at).toLocaleString()}</td>
                </tr>
              ))}
              {queue.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-6 text-slate-500">No queued items.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
