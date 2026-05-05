## Purpose of This Manual

This manual explains what TrustGate MVP is, how the system is structured, how a user starts a new local instance, and how an operator moves through the full compliance workflow from onboarding to reporting. It is written against the current implementation in this repository, not against a future roadmap.

TrustGate MVP is a compliance operations platform for real-estate onboarding and anti-money-laundering control work. It combines customer intake, KYC capture, document management, due diligence, beneficial ownership mapping, sanctions and PEP screening, risk scoring, escalation, monitoring, reporting, and audit visibility in one workflow.

The system is especially useful when a team wants to stop handling compliance in disconnected spreadsheets, email chains, paper files, and informal analyst notes. Instead of treating AML work as a single checklist, TrustGate stores each control step as structured data so later stages can reuse it.

## What the System Is

TrustGate MVP is a web application with two main parts:

- A FastAPI backend that exposes the business workflow and stores operational data.
- A React frontend that provides the analyst-facing workspace.

At a practical level, the system does five things:

1. It creates a single operating record for a client and the deal they are involved in.
2. It captures KYC facts, documents, linked relationships, and ownership structures in a reusable form.
3. It screens the client and related parties against external watchlist and PEP data.
4. It converts evidence into explainable risk and escalation decisions.
5. It preserves an audit trail, work queue, and exportable report history.

## Who Should Use TrustGate

The current MVP is designed for users such as:

- Compliance officers
- KYC analysts
- Reviewers
- Auditors
- Administrators

The system defines the following user roles:

- `administrator`
- `compliance_officer`
- `analyst`
- `reviewer`
- `auditor`

Administrators can see the Administration page. Other operational roles use the core workflow pages.

## Main Workflow at a Glance

The intended operating sequence is:

1. Log in.
2. Create the client and deal in Client Intake.
3. Complete KYC Onboarding.
4. Upload and review KYC Documents.
5. Complete the CDD Workflow.
6. Record linked parties.
7. Record beneficial ownership and control.
8. Run Screening and review candidates.
9. Run Risk Assessment.
10. Open or manage EDD if needed.
11. Run Monitoring and review Alerts.
12. Use the Analyst Workbench to track pending work.
13. Export Reports.
14. Use Administration for settings, users, and audit visibility.
15. Generate a final compliance decision through the backend when needed.

## Current MVP Coverage and Practical Note

Most of the analyst workflow is available in the UI. Three important workflow areas are implemented in the backend but are not fully routed as standalone pages in the React application:

- Linked-party management
- PEP case management
- Final compliance decision generation

For these areas, the practical workaround is to use the FastAPI Swagger UI at `http://localhost:8000/docs` after the backend is running.

## Starting a New Local Instance

### Prerequisites

Before starting the system, confirm that the machine has:

- Python installed
- Node.js and npm installed
- The project checked out locally
- A valid `.env` file in the project root

The backend configuration requires an `OPENSANCTIONS_API_KEY`. Without it, the application import will fail and screening will not work.

The project root directory in this workspace is:

`C:\Users\njabulobc\Desktop\TrustGate MVP`

The frontend directory is:

`C:\Users\njabulobc\Desktop\TrustGate MVP\ui`

### Starting the Backend in Command Prompt

Use Command Prompt if you want the simplest Windows flow:

```bat
cd /d "C:\Users\njabulobc\Desktop\TrustGate MVP"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

What this does:

- `cd /d` moves into the project drive and folder.
- `uvicorn app.main:app` starts the FastAPI application from `app/main.py`.
- `--reload` restarts the backend when code changes.
- `--host 127.0.0.1` binds locally.
- `--port 8000` exposes the API on port 8000.

When the backend starts correctly, the useful URLs are:

- API root health check: `http://127.0.0.1:8000/health`
- Swagger UI: `http://127.0.0.1:8000/docs`

### Starting the Backend in PowerShell

```powershell
cd "C:\Users\njabulobc\Desktop\TrustGate MVP"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Starting the Frontend in Command Prompt

Open a second terminal window:

```bat
cd /d "C:\Users\njabulobc\Desktop\TrustGate MVP\ui"
npm install
npm run dev
```

The Vite development server is configured to run on port `5173`.

Open:

`http://127.0.0.1:5173`

### Starting the Frontend in PowerShell

```powershell
cd "C:\Users\njabulobc\Desktop\TrustGate MVP\ui"
npm install
npm run dev
```

### What Happens on Startup

When the backend starts:

- Database tables are created if they do not already exist.
- Safe SQLite schema updates run for newer screening fields.
- The `uploads` directory is created if missing.
- A bootstrap administrator is seeded if needed.
- Default application settings are inserted if missing.

### First Login

In the current MVP, the login page pre-populates:

- Username: `admin`
- Password: `admin123!`

These come from the bootstrap defaults unless they have been overridden in the environment.

## End-to-End Example Used in This Manual

To make the workflow concrete, this manual uses a single example from start to finish.

Example case:

- Client: `Mhofu Horizon Properties (Pvt) Ltd`
- Deal reference: `TG-2026-001`
- Transaction type: `purchase`
- Property: commercial building in Harare
- Transaction value: `720000 USD`
- Cross-border context: yes, because part of the funds come from a South African shareholder loan

Related parties in the example:

- `Tariro Mhofu`, beneficial owner and director
- `Southern Capital Trustees`, trust-related control layer
- `Farai Dube`, external intermediary

This example is intentionally rich enough to exercise the major modules:

- Company onboarding
- Ownership complexity
- Cross-border and high-value risk
- Screening review
- EDD escalation
- Monitoring and reporting

## Module 1: Login and Session Access

### What This Module Does

The login page issues a bearer token and establishes the session used by the frontend for all later API calls. Without a valid session, the user is redirected back to `/login`.

### How to Use It Well

1. Confirm the backend is reachable first.
2. Log in with a valid user account.
3. Verify that the sidebar loads and shows your name, role, app origin, and API base.

### In the Example

The analyst logs in as the bootstrap administrator to set up the first test case and later can create separate analyst and reviewer accounts in Administration.

## Module 2: Dashboard

### What This Module Does

The Dashboard gives an immediate operational summary of the platform. It combines:

- total clients
- pending KYC reviews
- open EDD cases
- open alerts
- incomplete document files
- open CDD tasks
- screening hits requiring review
- high-risk clients or deals

It also shows a short Analyst Queue pulled from the workbench service.

### Why It Matters

This is the control room view. A compliance lead should use it at the start of each day to see where the current bottlenecks are.

### How to Get the Most from It

1. Treat the dashboard as a prioritization screen, not a data-entry page.
2. Watch the movement in open alerts, pending KYC, and screening hits.
3. Use it to decide whether the team should focus on evidence gathering, screening review, or escalation cleanup.

### In the Example

Before the example case exists, the dashboard is relatively empty. After the client is created, screened, and risk-assessed, the counts change and the analyst can see whether the case is creating open work items.

## Module 3: Client Intake

### What This Module Does

Client Intake creates the foundational records for the workflow:

- one client
- one initial deal

The frontend supports creation and listing. The backend also supports updates, even though the current page is centered on create-and-list behavior.

### Fields Entered Here

For the client:

- client type
- primary name
- email
- status

For the deal:

- transaction reference
- transaction type
- property location
- transaction value
- currency
- cross-border flag
- status
- source-of-funds summary if used through the API

### Why This Module Matters

Every later module anchors itself to the client record, and many later controls also refer back to the deal context. If intake is wrong, every downstream module will be weaker.

### Best Practice

- Use a meaningful transaction reference.
- Enter the legal or operational name the team will consistently use later.
- Capture a realistic transaction value because risk scoring uses it.

### In the Example

Create:

- Client type: `company`
- Primary name: `Mhofu Horizon Properties (Pvt) Ltd`
- Email: `compliance@mhofuhorizon.co.zw`
- Deal reference: `TG-2026-001`
- Transaction type: `purchase`
- Property location: `Harare CBD commercial block`
- Transaction value: `720000`

This immediately creates the case shell used by every later module.

## Module 4: KYC Onboarding

### What This Module Does

KYC Onboarding captures the structured identity and profile facts for the client. It is more than a notes page. It stores typed fields that the rest of the system can reuse.

The backend also denormalizes some KYC values into the main client record so other modules can read them easily.

### Key Data Captured

- onboarding status
- full legal name
- date of birth where relevant
- national ID or passport number
- nationality
- residency status
- occupation and employer
- business activity
- company registration number
- tax identification number
- tax clearance status
- cross-border indicator
- PEP declaration
- related-party declaration
- address
- contact details
- notes

### Why This Module Matters

This is the point where raw intake becomes actual KYC. Screening quality, document expectations, and risk interpretation are all improved by good KYC data.

### How to Get the Most from It

1. Move the status from `draft` to `in_progress` once evidence collection begins.
2. Use the exact legal name that will later be screened.
3. Set the cross-border, PEP, and related-party declarations honestly. These drive later controls.
4. Use the notes field for context that does not fit a typed field but may matter to the reviewer.

### In the Example

For `Mhofu Horizon Properties (Pvt) Ltd`, the analyst records:

- onboarding status: `in_progress`
- full legal name: `Mhofu Horizon Properties (Pvt) Ltd`
- business activity: `commercial property investment and redevelopment`
- company registration number: the official registry number
- tax ID: the company tax number
- tax clearance status: `pending`
- cross-border indicator: `true`
- PEP declaration: `false`
- related-party declaration: `true`
- notes: mention the shareholder loan and trust-linked control chain

This is a high-value step because it gives context to later document, screening, and risk decisions.

## Module 5: KYC Documents

### What This Module Does

The Documents module stores:

- the file itself under `uploads/`
- metadata in the database
- a lifecycle status for review
- a checklist summary
- checksum and file size information

The system tracks document state from submission to verification.

### Default Required Document Sets

For an individual client, the default expected types are:

- `national_id`
- `passport`
- `proof_of_residence`
- `bank_statement`
- `tax_clearance_certificate`
- `source_of_funds_support`

For a company client, the default expected types are:

- `company_registration_documents`
- `beneficial_ownership_evidence`
- `authorization_or_mandate`
- `tax_clearance_certificate`
- `bank_statement`
- `source_of_funds_support`

### Lifecycle Statuses You Will See

- `required`
- `submitted`
- `under_review`
- `verified`
- `rejected`
- `expired`
- `resubmission_required`

### Why This Module Matters

The checklist summary is not cosmetic. It feeds later review quality and monitoring logic. Missing or expired documents can trigger alerts and increase risk.

### How to Get the Most from It

1. Upload documents with consistent names.
2. Review documents promptly and move them from `submitted` to `verified` or `resubmission_required`.
3. Use lifecycle statuses honestly so the workbench and monitoring queue reflect real operational risk.

### In the Example

For the company case, upload:

- company registration documents
- beneficial ownership evidence
- authorization or board mandate
- tax clearance certificate
- bank statement
- source of funds support

Suppose the bank statement is outdated. Mark it `resubmission_required`. This is useful because:

- the checklist will still show the case as incomplete
- the workbench can surface follow-up work
- monitoring can later raise an alert if the issue remains unresolved

## Module 6: CDD Workflow

### What This Module Does

The CDD Workflow stores structured due-diligence judgments rather than loose notes. It captures whether the analyst has actually reviewed source-of-funds and source-of-wealth evidence and whether the transaction purpose makes sense.

### Main Fields

- workflow status
- source of funds status
- source of wealth status
- payment method review
- transaction purpose review
- expected activity profile
- adverse transaction indicators
- supporting evidence checklist
- analyst decision
- reviewer decision
- analyst notes
- reviewer notes

### Why This Module Matters

This module sits at the center of AML reasoning. Weak or unresolved CDD decisions directly influence the later risk score.

### How to Get the Most from It

1. Do not leave all statuses at `pending` if you have already assessed the evidence.
2. Make the text reviews specific. Explain what was verified and what remains unsupported.
3. Use the checklist to show which evidence themes are truly covered.
4. Distinguish analyst notes from reviewer notes so the second line of defense can see the full reasoning chain.

### In the Example

The analyst records:

- workflow status: `in_progress`
- source of funds status: `pending`
- source of wealth status: `approved`
- payment method review: `Funds expected by bank transfer. No cash expected. Shareholder loan agreement under review.`
- transaction purpose review: `Purchase and redevelopment of CBD commercial property.`
- expected activity profile: `Commercial rental and resale strategy over 24 months.`
- adverse transaction indicators: `Cross-border funding source still awaiting full documentary support.`
- analyst decision: `pending`

This is exactly the kind of detail that later explains why the system may return medium or high risk.

## Module 7: Linked Parties

### What This Module Does

The linked-party module stores people and entities related to the client or deal, such as:

- beneficial owners
- representatives
- co-buyers
- co-sellers
- payers
- intermediaries
- other relationship types

It exists because AML work often depends on people around the client, not only the named primary client.

### Current MVP Note

The backend fully supports linked-party management, but the frontend does not currently have a dedicated page for it. Use Swagger UI at `http://127.0.0.1:8000/docs`.

### Core Fields

- `party_type`
- `role`
- `relationship_to_client`
- `primary_name`
- optional name parts
- date of birth
- nationality
- national ID number
- registration number for entities
- country of incorporation
- email
- phone number
- address
- `screening_required`

### How to Use It Well

1. Record every person or entity that materially affects ownership, control, or funding.
2. Set `screening_required` to `true` for anyone who should be included in the screening pool.
3. Distinguish legal owners from facilitators such as intermediaries.

### In the Example

Add:

- `Tariro Mhofu` as `beneficial_owner`
- `Southern Capital Trustees` as a trust-linked control entity
- `Farai Dube` as `intermediary`

This makes the later screening process more realistic and improves the value of the risk score.

## Module 8: Beneficial Ownership

### What This Module Does

The Beneficial Ownership module records who owns or controls the client directly or indirectly. It supports both a table view and a graph-style hierarchy.

### What Can Be Recorded

- owner name
- owner type
- classification
- ownership percentage
- control type
- direct ownership
- indirect ownership
- nominee indicator
- trust indicator
- representative relationship
- control without ownership
- corporate parent name
- ownership chain notes
- complexity score
- parent-child ownership relationships

### Why This Module Matters

This module is especially important for company clients. Risk logic treats absent or overly complex beneficial ownership as meaningful risk.

### How to Get the Most from It

1. Record real ownership percentages wherever possible.
2. Use the complexity score consistently so later review can compare cases.
3. Use parent-child records to map the actual control chain, not just the immediate shareholder.
4. Mark nominee, trust, and control-without-ownership scenarios clearly because those patterns often need closer review.

### In the Example

The analyst adds:

- `Tariro Mhofu`, 55 percent direct ownership
- `Southern Capital Trustees`, 45 percent indirect control layer
- a high complexity score for the trust-linked structure
- notes describing how the trustee arrangement influences control

This creates a structure that later helps explain why the risk result is not automatically low.

## Module 9: Screening

### What This Module Does

The Screening module runs the client and screening-eligible linked parties through the external provider and stores:

- screening result sets
- matched candidates
- candidate category
- score
- disposition
- request and response snapshots

Candidate categories include:

- `standard`
- `pep`
- `rca`

Candidate dispositions include:

- `pending`
- `confirmed_match`
- `needs_edd`
- `false_positive`

### Why This Module Matters

Screening is the formal control point for sanctions, PEP, and related exposures. It also feeds risk and may create EDD work.

### How to Get the Most from It

1. Complete KYC and linked parties before screening, otherwise matching quality is weaker.
2. Review each candidate deliberately instead of mass-closing them.
3. Use the disposition reason to explain why the candidate was accepted or rejected.

### In the Example

The analyst clicks `Run screening`.

Possible outcome:

- the company itself has no strong adverse match
- `Tariro Mhofu` returns a candidate that is classified as `rca`
- `Farai Dube` returns a weak candidate that is a false positive

The analyst then:

1. sets the weak candidate to `false_positive` with a reason
2. sets the more material candidate to `needs_edd`

That one action can automatically contribute to EDD activity and later risk.

## Module 10: PEP Case Handling

### What This Module Does

PEP case handling is the specialized workflow for candidate-level PEP or RCA follow-up. It is separate from the broader EDD case register because the required controls are more specific.

The backend supports:

- opening a PEP case from a screening candidate
- updating case status
- recording senior approval status
- recording source-of-wealth status
- recording source-of-funds status
- flagging enhanced monitoring
- storing monitoring notes and closure evidence

### Current MVP Note

There is backend support, but there is no routed SPA page for this module. Use Swagger UI.

### In the Example

After the `rca` candidate is dispositioned to `needs_edd`, the reviewer can open a PEP case through the backend and record whether:

- source of wealth was satisfactorily verified
- source of funds was satisfactorily verified
- senior approval is required
- enhanced monitoring should continue after onboarding

## Module 11: Risk Assessment

### What This Module Does

The Risk Assessment module produces an explainable score and risk level. It is not a black box. The backend calculates a factor breakdown and summary narrative.

### Inputs Used by the Risk Engine

- confirmed primary client screening matches
- confirmed linked-party matches
- transaction value
- cross-border context
- unknown beneficial ownership
- PEP or RCA exposure
- sanctions exposure
- cash transaction indicators
- source-of-funds strength
- source-of-wealth strength
- incomplete documents
- expired documents
- ownership complexity
- repeated alerts
- jurisdictional risk

### Important Rule Values in the Current MVP

- high-value transaction threshold: `500000`
- medium-risk threshold: `20`
- high-risk threshold: `55`

### Why This Module Matters

This is where the system converts scattered evidence into an operational risk conclusion.

### How to Get the Most from It

1. Run risk only after the case has enough KYC, document, CDD, ownership, and screening data to make the result meaningful.
2. Read the summary, not just the level.
3. Use overrides sparingly and only with a clear justification because overrides are auditable.

### In the Example

When the analyst runs risk for `Mhofu Horizon Properties (Pvt) Ltd`, the score may rise because of:

- high transaction value
- cross-border indicator
- unresolved source-of-funds verification
- ownership complexity
- RCA-linked exposure
- incomplete document state

If the result is high risk, the analyst should not override it downward casually. The better action is to finish the missing evidence work or move into EDD.

## Module 12: EDD Cases

### What This Module Does

EDD Cases manage enhanced due diligence work at the client level. A case may be created manually or triggered by screening review logic.

### What the Page Supports

- create a new EDD case
- record the source module
- set case type
- set priority
- write the trigger reason
- track status

Supported statuses include:

- `open`
- `assigned`
- `in_review`
- `awaiting_information`
- `escalated`
- `approved`
- `rejected`
- `closed`

### Why This Module Matters

EDD is where the system forces serious issues into a managed queue instead of leaving them as vague concerns in analyst memory.

### How to Get the Most from It

1. Write a precise trigger reason.
2. Use priority to distinguish routine follow-up from urgent escalation.
3. Update statuses actively so the workbench remains meaningful.

### In the Example

The analyst opens or reviews an EDD case with:

- case type: `enhanced_due_diligence`
- source module: `screening`
- priority: `high`
- trigger reason: `RCA-linked screening candidate plus unresolved cross-border source-of-funds evidence`

This converts a risky case into managed investigative work.

## Module 13: Monitoring and Alerts

### What This Module Does

Monitoring checks for ongoing control issues and creates alerts. In the current MVP it runs manually rather than on a background scheduler.

The monitoring logic can generate alerts for:

- missing required documents
- expired documents
- high-risk clients
- high ownership complexity
- aging EDD cases

It also records monitoring events.

### Why This Module Matters

This is the bridge between onboarding and ongoing review. It helps the team catch issues that were left unresolved after the first assessment.

### How to Get the Most from It

1. Run monitoring after major review changes.
2. Use alert queue items as action items, not passive notifications.
3. Re-run after evidence is corrected to confirm the case is stabilizing.

### In the Example

If the company still has a missing bank statement and a high-risk assessment, monitoring may generate:

- `missing_required_document`
- a high-risk alert

The monitoring history then shows when the analyst ran the control and what was found.

## Module 14: Analyst Workbench

### What This Module Does

The Analyst Workbench is the operational queue that brings together pending work across:

- documents
- CDD
- screening
- EDD
- monitoring

### Why This Module Matters

Without a centralized queue, compliance work becomes fragmented. The workbench lets a user filter by module or status and focus on actionable work.

### How to Get the Most from It

1. Use it at the start of the day and after every major workflow run.
2. Filter by module when a specialist is handling one domain.
3. Filter by status when clearing stuck work.

### In the Example

The workbench may show the case because:

- a document needs resubmission
- CDD is still open
- screening candidates need review
- an EDD case remains open

That view tells the analyst exactly what remains before the case can be considered stable.

## Module 15: Reports

### What This Module Does

The Reports module generates operational exports in JSON or CSV.

Current report options are:

- `kyc_completeness`
- `document_expiry`
- `screening_history`
- `open_edd_aging`
- `alert_summary`
- `high_risk_clients`
- `audit_export`

### Why This Module Matters

Reports make the platform useful for supervisors, management, auditors, and periodic control review.

### How to Get the Most from It

1. Use `kyc_completeness` to see onboarding gaps.
2. Use `document_expiry` to plan document refreshes.
3. Use `screening_history` to show screening activity over time.
4. Use `high_risk_clients` for supervisory review.
5. Use `audit_export` when demonstrating traceability.

### In the Example

After working the sample case, export:

- `screening_history` to show who was screened and when
- `high_risk_clients` to see whether the case still appears there
- `audit_export` to show the action history around the case

## Module 16: Administration

### What This Module Does

Administration provides platform governance features:

- settings management
- user visibility
- audit trail visibility

Default setting groups include:

- `risk_factors`
- `document_checklists`
- `cdd_checklist`
- `edd_triggers`
- `monitoring`

### Why This Module Matters

This module controls how the platform is tuned and who has access to it.

### How to Get the Most from It

1. Use it to create cleaner operating discipline, not to make ad hoc hidden changes.
2. Update JSON settings carefully because malformed JSON will fail.
3. Review the audit feed after significant operational or configuration changes.

### In the Example

An administrator can review the recent audit history for the sample case and confirm that intake creation, KYC updates, screening reviews, and risk actions were recorded.

## Module 17: Final Compliance Decision

### What This Module Does

The final compliance decision is generated by the backend and returns a structured result that includes:

- `verdict`
- `top_reasons`
- `required_actions`
- `evidence`
- `why`

Possible verdicts are:

- `clear`
- `review_required`
- `edd_required`

### Current MVP Note

This exists as a backend route but does not currently have its own frontend page. Use Swagger UI to call:

- `POST /compliance/clients/{client_id}/decision`

### Why This Module Matters

This is the system's synthesis layer. It does not replace analyst judgment, but it gives a structured output that ties together screening, risk, and escalation evidence.

### In the Example

For the sample company case, a likely result before all evidence is closed may be:

- verdict: `edd_required`
- top reasons: unresolved source of funds, cross-border context, ownership complexity, RCA-linked exposure
- required actions: finish EDD, verify supporting evidence, consider enhanced monitoring

That gives the reviewer a concise decision object rather than forcing them to reconstruct the whole case manually.

## Recommended End-to-End Operating Pattern

If a user wants to get the most from the current MVP, the most effective operating pattern is:

1. Create the intake carefully.
2. Immediately complete KYC with legal names and declaration flags.
3. Upload the expected document set early.
4. Add linked parties before screening.
5. Map ownership before risk for company clients.
6. Run screening only after the core identities are complete.
7. Record candidate dispositions with reasons.
8. Run risk after the case has real evidence.
9. Open EDD instead of hiding unresolved issues in notes.
10. Run monitoring after major changes or before final review.
11. Use reports and audit export for supervisory or external review.

## Known MVP Limitations a User Should Understand

- Linked-party management is backend-supported but does not yet have a dedicated SPA page.
- PEP case handling is backend-supported but not routed in the SPA.
- Final compliance decision generation is backend-supported but not routed in the SPA.
- Monitoring is manual, not scheduled.
- The Risk Assessment page does not display the full factor breakdown JSON in the UI.
- Administration settings exist, but not every setting is currently enforced dynamically in runtime logic.

These are important because they affect how a user should plan real operations around the MVP.

## Frequently Asked Questions

### 1. What is the first page I should use after logging in?

Start with `Client Intake` if you are opening a new case. Start with `Dashboard` or `Analyst Workbench` if you are continuing existing work.

### 2. Do I need to complete every module in order?

For the best results, yes. The system is designed as a progressive workflow. Screening, risk, and monitoring are more useful when intake, KYC, documents, and ownership are already populated.

### 3. Can I use the system for both individual and company clients?

Yes. The system supports both `individual` and `company` client types. The expected documents and ownership needs differ between them.

### 4. Why is the risk result high even when the client seems legitimate?

The current engine scores based on objective signals such as transaction value, cross-border exposure, unresolved documents, weak source-of-funds review, confirmed screening issues, and ownership complexity. A legitimate client can still require enhanced review if those factors remain open.

### 5. Why does the system still show document issues after I uploaded files?

Uploading a file is not the same as verifying it. The document may still be missing the expected type, may be expired, or may still be marked `submitted` or `resubmission_required`.

### 6. Where do I manage beneficial owners related to screening?

The most complete workflow is to add the related parties first through the backend relationship endpoints, then map the control structure in the Beneficial Ownership page, then run Screening.

### 7. Why do I not see a linked-party page in the sidebar?

That is a current MVP gap. The capability exists in the backend, but not yet as a dedicated page in the SPA.

### 8. How do I use the backend-only modules?

Run the backend and open `http://127.0.0.1:8000/docs`. Use the interactive Swagger UI for linked parties, PEP cases, and compliance decision generation.

### 9. What reports should I use most often?

The most operationally useful reports are usually `kyc_completeness`, `screening_history`, `high_risk_clients`, and `audit_export`.

### 10. What happens if I do not have an OpenSanctions API key?

The backend requires `OPENSANCTIONS_API_KEY`. Without it, screening will not function correctly and application startup may fail because the setting is mandatory.

### 11. Is monitoring automatic?

Not in the current MVP. Monitoring is triggered manually from the Monitoring page or via the backend API.

### 12. Can I change the default admin account?

Yes. The bootstrap administrator values are environment-driven in configuration, but the current local MVP defaults to `admin` and `admin123!` unless overridden.

### 13. Can I generate a final onboarding verdict from the UI?

Not from a dedicated SPA page yet. Use the backend compliance decision endpoint until a routed UI page is added.

### 14. What is the best way to demonstrate the whole system?

Use one realistic company case with linked parties, ownership complexity, source-of-funds evidence, screening review, risk scoring, EDD, monitoring, and reports. The example in this manual follows that pattern because it exercises the strongest parts of the product.

## Closing Note

TrustGate MVP works best when users treat it as a connected compliance workflow rather than a set of unrelated forms. The value of the system comes from the handoff between modules: intake informs KYC, KYC supports documents and screening, screening shapes risk, risk shapes EDD, and all of it feeds monitoring, reporting, and auditability.
