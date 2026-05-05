from __future__ import annotations

from app.models.user import UserRole

ROLE_CAPABILITIES: dict[UserRole, list[str]] = {
    UserRole.ADMINISTRATOR: [
        'view_dashboard','view_intake','edit_intake','view_kyc','edit_kyc','view_screening','resolve_screening','view_risk','assess_risk','view_edd','manage_edd','view_monitoring','manage_monitoring','view_workbench','resolve_workbench','view_reports','export_reports','view_admin','manage_admin'
    ],
    UserRole.COMPLIANCE_OFFICER: [
        'view_dashboard','view_intake','edit_intake','view_kyc','edit_kyc','view_screening','resolve_screening','view_risk','assess_risk','view_edd','manage_edd','view_monitoring','manage_monitoring','view_workbench','resolve_workbench','view_reports','export_reports'
    ],
    UserRole.ANALYST: [
        'view_dashboard','view_intake','edit_intake','view_kyc','edit_kyc','view_screening','view_risk','assess_risk','view_edd','view_monitoring','view_workbench'
    ],
    UserRole.REVIEWER: [
        'view_dashboard','view_screening','resolve_screening','view_risk','assess_risk','view_edd','view_monitoring','view_workbench','resolve_workbench','view_reports'
    ],
    UserRole.AUDITOR: [
        'view_dashboard','view_intake','view_kyc','view_screening','view_risk','view_edd','view_monitoring','view_workbench','view_reports'
    ],
}


def get_role_capabilities(role: UserRole) -> list[str]:
    return ROLE_CAPABILITIES.get(role, []).copy()
