import { UserRole } from '../api/client';

export type Capability =
  | 'view_dashboard'
  | 'view_intake'
  | 'edit_intake'
  | 'view_kyc'
  | 'edit_kyc'
  | 'view_screening'
  | 'resolve_screening'
  | 'view_risk'
  | 'assess_risk'
  | 'view_edd'
  | 'manage_edd'
  | 'view_monitoring'
  | 'manage_monitoring'
  | 'view_workbench'
  | 'resolve_workbench'
  | 'view_reports'
  | 'export_reports'
  | 'view_admin'
  | 'manage_admin';

const ALL_CAPABILITIES: Capability[] = [
  'view_dashboard','view_intake','edit_intake','view_kyc','edit_kyc','view_screening','resolve_screening','view_risk','assess_risk','view_edd','manage_edd','view_monitoring','manage_monitoring','view_workbench','resolve_workbench','view_reports','export_reports','view_admin','manage_admin'
];

export const ROLE_CAPABILITIES: Record<UserRole, Capability[]> = {
  administrator: ALL_CAPABILITIES,
  compliance_officer: [
    'view_dashboard','view_intake','edit_intake','view_kyc','edit_kyc','view_screening','resolve_screening','view_risk','assess_risk','view_edd','manage_edd','view_monitoring','manage_monitoring','view_workbench','resolve_workbench','view_reports','export_reports'
  ],
  analyst: [
    'view_dashboard','view_intake','edit_intake','view_kyc','edit_kyc','view_screening','view_risk','assess_risk','view_edd','view_monitoring','view_workbench'
  ],
  reviewer: [
    'view_dashboard','view_screening','resolve_screening','view_risk','assess_risk','view_edd','view_monitoring','view_workbench','resolve_workbench','view_reports'
  ],
  auditor: [
    'view_dashboard','view_intake','view_kyc','view_screening','view_risk','view_edd','view_monitoring','view_workbench','view_reports'
  ]
};

function resolveCapabilities(role?: UserRole | null, serverCapabilities?: string[] | null): string[] {
  if (serverCapabilities && serverCapabilities.length > 0) return serverCapabilities;
  return role ? ROLE_CAPABILITIES[role] ?? [] : [];
}

export function getRoleCapabilities(role?: UserRole | null): Capability[] {
  return role ? ROLE_CAPABILITIES[role] ?? [] : [];
}

export function hasCapability(role: UserRole | undefined | null, capability: Capability, serverCapabilities?: string[] | null): boolean {
  return resolveCapabilities(role, serverCapabilities).includes(capability);
}

export function hasAnyCapability(role: UserRole | undefined | null, capabilities: Capability[], serverCapabilities?: string[] | null): boolean {
  const effective = resolveCapabilities(role, serverCapabilities);
  return capabilities.some((capability) => effective.includes(capability));
}

export function hasAllCapabilities(role: UserRole | undefined | null, capabilities: Capability[], serverCapabilities?: string[] | null): boolean {
  const effective = resolveCapabilities(role, serverCapabilities);
  return capabilities.every((capability) => effective.includes(capability));
}
