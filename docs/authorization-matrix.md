# TrustGate Authorization Matrix

Backend authorization is the enforcement layer. Frontend capability checks are UX gates for navigation, route guarding, and avoiding failed actions.

When adding a new endpoint or page, update this matrix. If backend roles and frontend capabilities disagree, backend policy wins and frontend mapping must be corrected.

| Frontend route/path | Backend endpoint | User-visible action | Allowed backend roles / require_roles source | Required frontend capability | Notes |
|---|---|---|---|---|---|
| `/dashboard` | `GET /platform/dashboard` | View KPI summary | role checks in platform routes (`require_roles`) | `view_dashboard` | Read-only display. |
| `/intake` | `GET/POST /intake/*` | View/create intake | intake route `require_roles` | `view_intake` (view), `edit_intake` (mutate) | UI should hide mutation for read-only users. |
| `/kyc` | `GET/PUT /platform/kyc/*` | View/update KYC profile | platform route `require_roles` | `view_kyc` / `edit_kyc` | Includes onboarding updates. |
| `/screening` | `POST /screening/run`, `PATCH /screening/candidates/*` | Run screening and disposition candidates | screening route `require_roles` | `view_screening` / `resolve_screening` | Route guard + action guard. |
| `/risk` | `POST /risk/run`, `POST /platform/risk-overrides/*` | Run risk and record override | risk/platform route `require_roles` | `view_risk` / `assess_risk` | Read-only users can view latest output. |
| `/edd` | `GET/POST/PATCH /platform/edd-cases/*` | Create/update EDD cases | platform route `require_roles` | `view_edd` / `manage_edd` | Status updates are mutation actions. |
| `/monitoring` | `GET /monitoring/*`, `POST /monitoring/run`, `PATCH /monitoring/alerts/*` | View events/alerts and resolve alerts | monitoring route `require_roles` | `view_monitoring` / `manage_monitoring` | Running monitoring is a managed action. |
| `/workbench` | `GET /platform/workbench` | View and resolve queue items | platform route `require_roles` | `view_workbench` / `resolve_workbench` | Current page is primarily view-focused. |
| `/reports` | `POST /platform/reports/export` | Generate/export reports | platform route `require_roles` | `view_reports` / `export_reports` | Export actions are capability-gated. |
| `/admin` | `GET /administration/*`, `PUT /administration/settings/*`, `GET/POST/PATCH /auth/users*` | Admin visibility and mutations | admin/auth route `require_roles(UserRole.ADMINISTRATOR)` | `view_admin` / `manage_admin` | Backend remains strict admin authority. |
