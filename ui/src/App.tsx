import { FormEvent, useState } from 'react';
import { Navigate, NavLink, Route, Routes } from 'react-router-dom';

import { IntakePage } from './features/intake/IntakePage';
import { RelationshipsPage } from './features/relationships/RelationshipsPage';
import { RiskHistoryPage } from './features/risk/RiskHistoryPage';
import { ScreeningReviewPage } from './features/screening/ScreeningReviewPage';
import { WorkflowQueuePage } from './features/workflow/WorkflowQueuePage';
import { useAuth } from './state/AuthContext';

function LoginGate({ children }: { children: React.ReactNode }) {
  const { user, login } = useAuth();
  const [username, setUsername] = useState('superuser');
  const [password, setPassword] = useState('superuser-pass');
  const [error, setError] = useState('');

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      setError('');
      await login(username, password);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (!user) {
    return <main className="mx-auto mt-20 max-w-md rounded-xl border bg-white p-6 shadow"><h1 className="text-xl font-semibold">TrustGate Login</h1><p className="mt-2 text-sm text-slate-600">Dummy credentials for testing: <strong>superuser/superuser-pass</strong></p><form className="mt-4 space-y-3" onSubmit={submit}><input className="w-full rounded border p-2" value={username} onChange={(e) => setUsername(e.target.value)} /><input className="w-full rounded border p-2" type="password" value={password} onChange={(e) => setPassword(e.target.value)} /><button className="rounded bg-brand-500 px-3 py-2 text-white">Login</button></form>{error && <p className="mt-2 text-sm text-rose-700">{error}</p>}</main>;
  }

  return <>{children}</>;
}

export default function App() {
  const { user, logout } = useAuth();
  return <LoginGate><main className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-4 p-6"><header className="rounded-xl border border-slate-200 bg-brand-50 p-4"><h1 className="text-2xl font-semibold">TrustGate Workflow Console</h1><p className="text-sm">Logged in as {user?.display_name} ({user?.role})</p><button className="mt-2 rounded border px-2 py-1 text-xs" onClick={logout}>Logout</button><nav className="mt-3 flex flex-wrap gap-2 text-sm">{['/intake','/relationships','/screening-review','/risk-history','/case-queue'].map((path) => <NavLink key={path} to={path} className={({isActive}) => `rounded px-2 py-1 ${isActive ? 'bg-brand-500 text-white' : 'bg-white border'}`}>{path.replace('/','')}</NavLink>)}</nav></header><Routes><Route path="/" element={<Navigate to="/intake" replace />} /><Route path="/intake" element={<IntakePage />} /><Route path="/relationships" element={<RelationshipsPage />} /><Route path="/screening-review" element={<ScreeningReviewPage />} /><Route path="/risk-history" element={<RiskHistoryPage />} /><Route path="/case-queue" element={<WorkflowQueuePage />} /></Routes></main></LoginGate>;
}
