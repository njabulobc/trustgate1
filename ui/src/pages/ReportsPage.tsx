import { useState } from 'react';

import { api, ReportExportResponse } from '../api/client';
import { Button, PageHeader, Panel, Select, TextArea } from '../components/ui';

const reportOptions = [
  'kyc_completeness',
  'document_expiry',
  'screening_history',
  'open_edd_aging',
  'alert_summary',
  'high_risk_clients',
  'audit_export'
];

export default function ReportsPage() {
  const [reportName, setReportName] = useState(reportOptions[0]);
  const [report, setReport] = useState<ReportExportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate(format: 'json' | 'csv') {
    setError(null);
    try {
      setReport(await api.generateReport(reportName, format));
    } catch (loadError) {
      setError((loadError as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Reports" description="Operational and audit-facing outputs generated from KYC, documents, screening, risk, EDD, monitoring, and user activity." />
      {error ? <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p> : null}
      <Panel title="Generate Report" subtitle="Query live operational data and export JSON or CSV.">
        <div className="flex flex-col gap-3 md:flex-row md:items-end">
          <div className="min-w-[260px]">
            <label className="mb-2 block text-sm font-medium text-slate-700">Report</label>
            <Select value={reportName} onChange={(event) => setReportName(event.target.value)}>
              {reportOptions.map((option) => <option key={option} value={option}>{option}</option>)}
            </Select>
          </div>
          <Button onClick={() => handleGenerate('json')}>Generate JSON</Button>
          <Button tone="secondary" onClick={() => handleGenerate('csv')}>Generate CSV</Button>
        </div>
      </Panel>
      <Panel title="Report Output" subtitle="Preview rows and exported content for analyst and audit workflows.">
        {!report ? <p className="text-sm text-slate-500">No report generated yet.</p> : (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">Rows: {report.rows.length}</p>
            {report.csv ? (
              <TextArea rows={12} value={report.csv} readOnly />
            ) : (
              <pre className="overflow-auto rounded-2xl bg-slate-950 p-4 text-xs text-slate-100">{JSON.stringify(report.rows.slice(0, 20), null, 2)}</pre>
            )}
          </div>
        )}
      </Panel>
    </div>
  );
}
