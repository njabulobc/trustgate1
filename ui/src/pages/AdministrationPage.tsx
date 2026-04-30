import { FormEvent, useEffect, useState } from 'react';

import { api, AdminOverview } from '../api/client';
import { Button, PageHeader, Panel, Select, TextArea } from '../components/ui';

export default function AdministrationPage() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [settingKey, setSettingKey] = useState('monitoring');
  const [settingValue, setSettingValue] = useState('{"interval_days": 30}');
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    api.getAdminOverview().then(setOverview).catch((loadError) => setError((loadError as Error).message));
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleSettingSave(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api.updateSetting(settingKey, { key: settingKey, value_json: JSON.parse(settingValue) });
      refresh();
    } catch (submitError) {
      setError((submitError as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Administration" description="Manage users, role assignments, configurable checklists, trigger settings, monitoring intervals, and audit visibility." />
      {error ? <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p> : null}
      <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <Panel title="Configuration" subtitle="Update module settings stored in platform configuration.">
          <form className="space-y-3" onSubmit={handleSettingSave}>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Setting key</label>
              <Select value={settingKey} onChange={(event) => setSettingKey(event.target.value)}>
                {overview?.settings.map((setting) => <option key={setting.key} value={setting.key}>{setting.key}</option>)}
              </Select>
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">JSON value</label>
              <TextArea rows={8} value={settingValue} onChange={(event) => setSettingValue(event.target.value)} />
            </div>
            <Button className="w-full">Save setting</Button>
          </form>
        </Panel>

        <div className="space-y-6">
          <Panel title="Users" subtitle="Current user roster and active roles.">
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-slate-200 text-slate-500">
                  <tr>
                    <th className="py-2 font-medium">Username</th>
                    <th className="py-2 font-medium">Name</th>
                    <th className="py-2 font-medium">Role</th>
                    <th className="py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {overview?.users.map((user) => (
                    <tr key={user.id} className="border-b border-slate-100">
                      <td className="py-3">{user.username}</td>
                      <td>{user.full_name}</td>
                      <td>{user.role}</td>
                      <td>{user.is_active ? 'active' : 'inactive'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel title="Audit Trail" subtitle="Recent auditable actions across compliance modules.">
            <div className="space-y-3">
              {overview?.audit_events.slice(0, 20).map((event) => (
                <div key={event.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="font-medium text-slate-900">{event.action}</p>
                  <p className="mt-1 text-sm text-slate-600">{event.actor} · {event.module} · {event.entity_type}#{event.entity_id}</p>
                  <p className="mt-2 text-xs text-slate-500">{new Date(event.timestamp).toLocaleString()}</p>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
