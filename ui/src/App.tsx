import { ReactNode } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';

import { useAuth } from './auth/AuthContext';
import { Capability, hasAllCapabilities, hasAnyCapability, hasCapability } from './auth/permissions';
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

function RequireCapability({ capability, capabilities, requireAll = false, children }: { capability?: Capability; capabilities?: Capability[]; requireAll?: boolean; children: ReactNode }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  const allowed = capability
    ? hasCapability(user.role, capability, user.capabilities)
    : capabilities?.length
      ? requireAll
        ? hasAllCapabilities(user.role, capabilities, user.capabilities)
        : hasAnyCapability(user.role, capabilities, user.capabilities)
      : true;
  if (!allowed) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

export default function App() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/dashboard" replace /> : <LoginPage />} />
      <Route path="/" element={<RequireAuth><AppShell /></RequireAuth>}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="intake" element={<RequireCapability capability="view_intake"><ClientIntakePage /></RequireCapability>} />
        <Route path="kyc" element={<RequireCapability capability="view_kyc"><KycOnboardingPage /></RequireCapability>} />
        <Route path="documents" element={<RequireCapability capability="view_kyc"><KycDocumentsPage /></RequireCapability>} />
        <Route path="cdd" element={<RequireCapability capability="view_kyc"><CddWorkflowPage /></RequireCapability>} />
        <Route path="ownership" element={<RequireCapability capability="view_kyc"><BeneficialOwnershipPage /></RequireCapability>} />
        <Route path="screening" element={<RequireCapability capability="view_screening"><ScreeningPage /></RequireCapability>} />
        <Route path="risk" element={<RequireCapability capability="view_risk"><RiskAssessmentPage /></RequireCapability>} />
        <Route path="edd" element={<RequireCapability capability="view_edd"><EddCasesPage /></RequireCapability>} />
        <Route path="monitoring" element={<RequireCapability capability="view_monitoring"><MonitoringPage /></RequireCapability>} />
        <Route path="workbench" element={<RequireCapability capability="view_workbench"><AnalystWorkbenchPage /></RequireCapability>} />
        <Route path="reports" element={<RequireCapability capability="view_reports"><ReportsPage /></RequireCapability>} />
        <Route path="admin" element={<RequireCapability capability="view_admin"><AdministrationPage /></RequireCapability>} />
      </Route>
      <Route path="*" element={<Navigate to={user ? '/dashboard' : '/login'} replace />} />
    </Routes>
  );
}
