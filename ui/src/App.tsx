import { Navigate, Route, Routes, useLocation } from 'react-router-dom';

import { useAuth } from './auth/AuthContext';
import AppShell from './layout/AppShell';
import AdministrationPage from './pages/AdministrationPage';
import AnalystWorkbenchPage from './pages/AnalystWorkbenchPage';
import BeneficialOwnershipPage from './pages/BeneficialOwnershipPage';
import CddWorkflowPage from './pages/CddWorkflowPage';
import ClientIntakePage from './pages/ClientIntakePage';
import DashboardPage from './pages/DashboardPage';
import EddCasesPage from './pages/EddCasesPage';
import KycDocumentsPage from './pages/KycDocumentsPage';
import KycOnboardingPage from './pages/KycOnboardingPage';
import LoginPage from './pages/LoginPage';
import MonitoringPage from './pages/MonitoringPage';
import ReportsPage from './pages/ReportsPage';
import RiskAssessmentPage from './pages/RiskAssessmentPage';
import ScreeningPage from './pages/ScreeningPage';

function RequireAuth({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <div className="flex min-h-screen items-center justify-center bg-slate-100 text-slate-600">Loading TrustGate…</div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  return children;
}

function RequireAdmin({ children }: { children: JSX.Element }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== 'administrator') return <Navigate to="/dashboard" replace />;
  return children;
}

export default function App() {
  const { user } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/dashboard" replace /> : <LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="intake" element={<ClientIntakePage />} />
        <Route path="kyc" element={<KycOnboardingPage />} />
        <Route path="documents" element={<KycDocumentsPage />} />
        <Route path="cdd" element={<CddWorkflowPage />} />
        <Route path="ownership" element={<BeneficialOwnershipPage />} />
        <Route path="screening" element={<ScreeningPage />} />
        <Route path="risk" element={<RiskAssessmentPage />} />
        <Route path="edd" element={<EddCasesPage />} />
        <Route path="monitoring" element={<MonitoringPage />} />
        <Route path="workbench" element={<AnalystWorkbenchPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route
          path="admin"
          element={
            <RequireAdmin>
              <AdministrationPage />
            </RequireAdmin>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to={user ? '/dashboard' : '/login'} replace />} />
    </Routes>
  );
}
