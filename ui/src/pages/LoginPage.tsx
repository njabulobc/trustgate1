import { FormEvent, useState } from 'react';
import { Navigate } from 'react-router-dom';

import { API_BASE_URL, APP_ORIGIN } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { Button, TextInput } from '../components/ui';

export default function LoginPage() {
  const { login, user } = useAuth();
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin123!');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to="/dashboard" replace />;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(username, password);
    } catch (submitError) {
      setError((submitError as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="grid min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.18),_transparent_28%),linear-gradient(180deg,#f8fafc_0%,#e2e8f0_100%)] px-6 py-10">
      <div className="m-auto grid w-full max-w-5xl gap-8 rounded-[28px] border border-slate-200 bg-white/90 p-6 shadow-2xl backdrop-blur md:grid-cols-[1.1fr_0.9fr] md:p-10">
        <section className="flex flex-col justify-between gap-8 rounded-[24px] bg-slate-950 p-8 text-white">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-sky-300">TrustGate</p>
            <h1 className="mt-4 max-w-md text-4xl font-semibold tracking-tight">Compliance operations with accountable workflows.</h1>
            <p className="mt-4 max-w-md text-sm text-slate-300">
              Sign in to manage onboarding, documents, screening, risk, EDD, monitoring, and audit output from one analyst workspace.
            </p>
          </div>
          <div className="space-y-2 text-sm text-slate-400">
            <p>Origin: {APP_ORIGIN}</p>
            <p>API base: {API_BASE_URL}</p>
          </div>
        </section>
        <section className="flex flex-col justify-center">
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Username</label>
              <TextInput value={username} onChange={(event) => setUsername(event.target.value)} />
            </div>
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Password</label>
              <TextInput type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
            </div>
            {error ? <p className="rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}
            <Button disabled={submitting} className="w-full">
              {submitting ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </section>
      </div>
    </main>
  );
}
