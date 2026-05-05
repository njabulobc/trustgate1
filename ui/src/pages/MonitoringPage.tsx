import { useEffect, useState } from 'react';

import { api, IntakeListItem, MonitoringAlert, MonitoringEvent } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { hasCapability } from '../auth/permissions';
import { Button, PageHeader, Panel, Select } from '../components/ui';

export default function MonitoringPage() {
  const [clients, setClients] = useState<IntakeListItem[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null);
  const [alerts, setAlerts] = useState<MonitoringAlert[]>([]);
  const [events, setEvents] = useState<MonitoringEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth();
  const canManage = hasCapability(user?.role, 'manage_monitoring', user?.capabilities);

  function refresh(clientId?: number | null) {
    Promise.all([api.listAlerts(clientId), api.listMonitoringEvents(clientId)])
      .then(([alertItems, eventItems]) => {
        setAlerts(alertItems);
        setEvents(eventItems);
      })
      .catch((loadError) => setError((loadError as Error).message));
  }

  useEffect(() => {
    api.listIntakes().then((items) => {
      setClients(items);
      if (items[0] && selectedClientId === null) setSelectedClientId(items[0].client_id);
    }).catch((loadError) => setError((loadError as Error).message));
    refresh();
  }, [selectedClientId]);

  async function runMonitoring() {
    if (!selectedClientId) return;
    setError(null);
    try {
      await api.runMonitoring(selectedClientId, undefined, 'Manual monitoring run from analyst console.');
      refresh(selectedClientId);
    } catch (runError) {
      setError((runError as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Monitoring & Alerts" description="Periodic or event-driven monitoring, generated alert queue, and escalation tracking." actions={canManage ? <Button onClick={runMonitoring}>Run monitoring</Button> : undefined} />
      {!canManage ? <p className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-700">You have read-only access to this page.</p> : null}
      {error ? <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p> : null}
      <div className="max-w-sm">
        <label className="mb-2 block text-sm font-medium text-slate-700">Client</label>
        <Select value={selectedClientId ?? ''} onChange={(event) => setSelectedClientId(Number(event.target.value))}>
          {clients.map((item) => <option key={item.client_id} value={item.client_id}>{item.primary_name}</option>)}
        </Select>
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <Panel title="Alert Queue" subtitle="Active alerts requiring review or escalation.">
          <div className="space-y-3">
            {alerts.map((alert) => (
              <div key={alert.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="font-medium text-slate-900">{alert.alert_type}</p>
                <p className="mt-1 text-sm text-slate-600">{alert.disposition ?? 'No disposition yet.'}</p>
                <p className="mt-2 text-xs text-slate-500">{alert.module} · {alert.severity} · {alert.status}</p>
              </div>
            ))}
            {alerts.length === 0 ? <p className="text-sm text-slate-500">No alerts in the current queue.</p> : null}
          </div>
        </Panel>
        <Panel title="Monitoring History" subtitle="Monitoring events and trigger runs.">
          <div className="space-y-3">
            {events.map((event) => (
              <div key={event.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="font-medium text-slate-900">{event.event_type}</p>
                <p className="mt-1 text-sm text-slate-600">{event.summary}</p>
                <p className="mt-2 text-xs text-slate-500">{event.event_source} · {new Date(event.created_at).toLocaleString()}</p>
              </div>
            ))}
            {events.length === 0 ? <p className="text-sm text-slate-500">No monitoring events yet.</p> : null}
          </div>
        </Panel>
      </div>
    </div>
  );
}
