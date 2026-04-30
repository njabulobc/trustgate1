import { FormEvent, useEffect, useState } from 'react';

import { api, WorkbenchItem } from '../api/client';
import { Button, PageHeader, Panel, Select, TextInput } from '../components/ui';

export default function AnalystWorkbenchPage() {
  const [items, setItems] = useState<WorkbenchItem[]>([]);
  const [moduleFilter, setModuleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    api.getWorkbenchQueue({ module: moduleFilter || undefined, status: statusFilter || undefined })
      .then((response) => setItems(response.items))
      .catch((loadError) => setError((loadError as Error).message));
  }

  useEffect(() => {
    refresh();
  }, []);

  function handleFilter(event: FormEvent) {
    event.preventDefault();
    refresh();
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Analyst Workbench" description="Daily operational queue across documents, CDD, screening, EDD, and monitoring." />
      {error ? <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p> : null}
      <Panel title="Filters" subtitle="Narrow the queue by module or status.">
        <form className="grid gap-3 md:grid-cols-[1fr_1fr_auto]" onSubmit={handleFilter}>
          <Select value={moduleFilter} onChange={(event) => setModuleFilter(event.target.value)}>
            <option value="">All modules</option>
            <option value="documents">Documents</option>
            <option value="cdd">CDD</option>
            <option value="screening">Screening</option>
            <option value="edd">EDD</option>
            <option value="monitoring">Monitoring</option>
          </Select>
          <TextInput placeholder="Status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} />
          <Button>Apply</Button>
        </form>
      </Panel>
      <Panel title="Queue" subtitle="Assigned and pending tasks visible across modules.">
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-slate-500">
              <tr>
                <th className="py-2 font-medium">Module</th>
                <th className="py-2 font-medium">Title</th>
                <th className="py-2 font-medium">Status</th>
                <th className="py-2 font-medium">Priority</th>
                <th className="py-2 font-medium">Updated</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={`${item.module}-${item.item_type}-${item.item_id}`} className="border-b border-slate-100">
                  <td className="py-3">{item.module}</td>
                  <td>{item.title}</td>
                  <td>{item.status}</td>
                  <td>{item.severity_or_priority ?? '—'}</td>
                  <td>{new Date(item.updated_at).toLocaleString()}</td>
                </tr>
              ))}
              {items.length === 0 ? <tr><td colSpan={5} className="py-6 text-slate-500">No workbench items available.</td></tr> : null}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
