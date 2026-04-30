import { NavLink, Outlet } from 'react-router-dom';

import { API_BASE_URL, APP_ORIGIN, UserRole } from '../api/client';
import { useAuth } from '../auth/AuthContext';

type NavItem = {
  label: string;
  to: string;
  roles?: UserRole[];
};

const navItems: NavItem[] = [
  { label: 'Dashboard', to: '/dashboard' },
  { label: 'Client Intake', to: '/intake' },
  { label: 'KYC Onboarding', to: '/kyc' },
  { label: 'KYC Documents', to: '/documents' },
  { label: 'CDD Workflow', to: '/cdd' },
  { label: 'Beneficial Ownership', to: '/ownership' },
  { label: 'Screening', to: '/screening' },
  { label: 'Risk Assessment', to: '/risk' },
  { label: 'EDD Cases', to: '/edd' },
  { label: 'Monitoring & Alerts', to: '/monitoring' },
  { label: 'Analyst Workbench', to: '/workbench' },
  { label: 'Reports', to: '/reports' },
  { label: 'Administration', to: '/admin', roles: ['administrator'] }
];

export default function AppShell() {
  const { user, logout } = useAuth();
  const visibleItems = navItems.filter((item) => !item.roles || (user && item.roles.includes(user.role)));

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <div className="grid min-h-screen lg:grid-cols-[250px_minmax(0,1fr)]">
        <aside className="border-r border-slate-200 bg-slate-950 px-5 py-6 text-slate-100">
          <div className="border-b border-slate-800 pb-5">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-300">TrustGate</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight">Compliance Platform</h1>
            <p className="mt-2 text-sm text-slate-400">Operational workspace for onboarding, screening, reviews, monitoring, and case control.</p>
          </div>
          <nav className="mt-5 flex flex-col gap-1">
            {visibleItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `rounded-xl px-3 py-2.5 text-sm transition ${isActive ? 'bg-sky-500 text-white' : 'text-slate-300 hover:bg-slate-900 hover:text-white'}`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="mt-8 rounded-2xl border border-slate-800 bg-slate-900 p-4 text-xs text-slate-400">
            <p className="font-semibold uppercase tracking-[0.16em] text-slate-500">Session</p>
            <p className="mt-2 text-slate-200">{user?.full_name}</p>
            <p className="mt-1">{user?.role.replace(/_/g, ' ')}</p>
            <p className="mt-3 break-all">Origin: {APP_ORIGIN}</p>
            <p className="mt-1 break-all">API: {API_BASE_URL}</p>
            <button className="mt-4 rounded-xl border border-slate-700 px-3 py-2 text-slate-200 hover:bg-slate-800" onClick={logout}>
              Log out
            </button>
          </div>
        </aside>
        <main className="min-w-0 px-5 py-6 md:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
