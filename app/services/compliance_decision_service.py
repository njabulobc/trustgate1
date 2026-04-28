from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.risk_assessment import RiskAssessment, RiskLevel
from app.models.screening import CandidateDisposition, MatchCategory, PepCase, PepCaseStatus, ScreeningCandidate
from app.schemas.compliance import (
    ComplianceDecisionActionRead,
    ComplianceDecisionEvidenceRead,
    ComplianceDecisionReasonRead,
    ComplianceDecisionResponse,
    ComplianceVerdict,
)
from app.services.audit_service import record_audit_event
from app.services.risk_service import assess_risk
from app.services.screening_service import ensure_pep_case, run_screening_for_client


@dataclass(frozen=True, slots=True)
class _CandidateContext:
    screening_result_id: int
    candidate: ScreeningCandidate


class ComplianceDecisionService:
    @staticmethod
    async def generate_client_decision(
        db: Session,
        client_id: int,
        *,
        deal_id: int | None = None,
        actor: str = "demo_user",
    ) -> ComplianceDecisionResponse:
        screening_results = await run_screening_for_client(
            db=db,
            client_id=client_id,
            deal_id=deal_id,
            actor=actor,
        )
        screening_result_ids = [result.id for result in screening_results]

        candidate_contexts = [
            _CandidateContext(screening_result_id=result.id, candidate=candidate)
            for result in screening_results
            for candidate in result.candidates
        ]

        ensured_cases: list[PepCase] = []
        for candidate_context in candidate_contexts:
            candidate = candidate_context.candidate
            if candidate.disposition not in {
                CandidateDisposition.CONFIRMED_MATCH,
                CandidateDisposition.NEEDS_EDD,
            }:
                continue
            if candidate.match_category not in {MatchCategory.PEP, MatchCategory.RCA}:
                continue
            ensured_cases.append(
                ensure_pep_case(
                    db=db,
                    screening_candidate_id=candidate.id,
                    actor=actor,
                )
            )

        risk_assessment = assess_risk(
            db=db,
            client_id=client_id,
            deal_id=deal_id,
            actor=actor,
        )

        verdict = ComplianceDecisionService._determine_verdict(
            candidate_contexts=candidate_contexts,
            pep_cases=ensured_cases,
            risk_assessment=risk_assessment,
        )
        reasons = ComplianceDecisionService._build_reasons(
            candidate_contexts=candidate_contexts,
            risk_assessment=risk_assessment,
        )
        required_actions = ComplianceDecisionService._build_required_actions(pep_cases=ensured_cases)
        evidence = ComplianceDecisionService._build_evidence(
            screening_result_ids=screening_result_ids,
            candidate_contexts=candidate_contexts,
            pep_cases=ensured_cases,
            risk_assessment=risk_assessment,
        )

        response = ComplianceDecisionResponse(
            verdict=verdict,
            top_reasons=[reason.summary for reason in reasons[:3]],
            required_actions=required_actions,
            evidence=evidence,
            why={
                "candidate_context": [
                    {
                        "candidate_id": context.candidate.id,
                        "screening_result_id": context.screening_result_id,
                        "match_category": context.candidate.match_category.value,
                        "disposition": context.candidate.disposition.value,
                        "policy_alerts": ComplianceDecisionService._extract_policy_alerts(context.candidate),
                    }
                    for context in candidate_contexts
                ],
                "risk": {
                    "risk_assessment_id": risk_assessment.id,
                    "risk_level": risk_assessment.risk_level.value,
                    "triggered_factors": ComplianceDecisionService._extract_triggered_factors(risk_assessment),
                },
            },
        )

        record_audit_event(
            db=db,
            actor=actor,
            action="compliance_decision.generated",
            entity_type="client",
            entity_id=client_id,
            metadata_payload={
                "client_id": client_id,
                "deal_id": deal_id,
                "verdict": verdict.value,
                "screening_result_ids": screening_result_ids,
                "risk_assessment_id": risk_assessment.id,
                "pep_case_ids": [pep_case.id for pep_case in ensured_cases],
            },
        )
        db.commit()

        return response

    @staticmethod
    def _determine_verdict(
        *,
        candidate_contexts: list[_CandidateContext],
        pep_cases: list[PepCase],
        risk_assessment: RiskAssessment,
    ) -> ComplianceVerdict:
        has_edd_candidate = any(
            context.candidate.disposition == CandidateDisposition.NEEDS_EDD
            for context in candidate_contexts
        )
        open_pep_statuses = {PepCaseStatus.OPEN, PepCaseStatus.IN_REVIEW}
        has_open_pep_obligations = any(pep_case.status in open_pep_statuses for pep_case in pep_cases)

        if has_edd_candidate or has_open_pep_obligations or risk_assessment.risk_level == RiskLevel.HIGH:
            return ComplianceVerdict.EDD_REQUIRED

        has_review_candidate = any(
            context.candidate.disposition in {CandidateDisposition.CONFIRMED_MATCH, CandidateDisposition.PENDING}
            for context in candidate_contexts
        )
        if has_review_candidate or risk_assessment.risk_level == RiskLevel.MEDIUM:
            return ComplianceVerdict.REVIEW_REQUIRED
        return ComplianceVerdict.CLEAR

    @staticmethod
    def _build_reasons(
        *,
        candidate_contexts: list[_CandidateContext],
        risk_assessment: RiskAssessment,
    ) -> list[ComplianceDecisionReasonRead]:
        reasons: list[ComplianceDecisionReasonRead] = []

        for context in candidate_contexts:
            candidate = context.candidate
            for alert in ComplianceDecisionService._extract_policy_alerts(candidate):
                severity = str(alert.get("severity", "low"))
                rationale = str(alert.get("rationale", "Policy alert triggered."))
                reasons.append(
                    ComplianceDecisionReasonRead(
                        code=f"policy_alert.{alert.get('policy', 'unknown')}",
                        summary=f"{severity.upper()} policy alert for candidate {candidate.id}",
                        severity=severity,
                        rationale=rationale,
                    )
                )

            if candidate.match_category in {MatchCategory.PEP, MatchCategory.RCA}:
                reasons.append(
                    ComplianceDecisionReasonRead(
                        code=f"match_category.{candidate.match_category.value}",
                        summary=f"Candidate {candidate.id} classified as {candidate.match_category.value.upper()}.",
                        severity="high" if candidate.match_category == MatchCategory.PEP else "medium",
                        rationale="Match category is derived by deterministic screening policy flags.",
                    )
                )

        for factor in ComplianceDecisionService._extract_triggered_factors(risk_assessment):
            reasons.append(
                ComplianceDecisionReasonRead(
                    code=f"risk_factor.{factor}",
                    summary=f"Risk factor triggered: {factor.replace('_', ' ')}.",
                    severity="medium",
                    rationale="Factor is present in risk factor_breakdown.triggered_factors.",
                )
            )

        reasons.sort(key=lambda reason: (ComplianceDecisionService._severity_rank(reason.severity), reason.code))
        return reasons

    @staticmethod
    def _build_required_actions(*, pep_cases: list[PepCase]) -> list[ComplianceDecisionActionRead]:
        actions: list[ComplianceDecisionActionRead] = []
        for pep_case in pep_cases:
            if pep_case.senior_approval_status.value != "verified":
                actions.append(
                    ComplianceDecisionActionRead(
                        action="Senior approval pending",
                        status=pep_case.senior_approval_status.value,
                        pep_case_id=pep_case.id,
                    )
                )
            if pep_case.source_of_wealth_status.value != "verified":
                actions.append(
                    ComplianceDecisionActionRead(
                        action="Source of wealth verification pending",
                        status=pep_case.source_of_wealth_status.value,
                        pep_case_id=pep_case.id,
                    )
                )
            if pep_case.source_of_funds_status.value != "verified":
                actions.append(
                    ComplianceDecisionActionRead(
                        action="Source of funds verification pending",
                        status=pep_case.source_of_funds_status.value,
                        pep_case_id=pep_case.id,
                    )
                )
        return actions

    @staticmethod
    def _build_evidence(
        *,
        screening_result_ids: list[int],
        candidate_contexts: list[_CandidateContext],
        pep_cases: list[PepCase],
        risk_assessment: RiskAssessment,
    ) -> ComplianceDecisionEvidenceRead:
        return ComplianceDecisionEvidenceRead(
            screening_result_ids=sorted(set(screening_result_ids)),
            candidate_ids=sorted({context.candidate.id for context in candidate_contexts}),
            pep_case_ids=sorted({pep_case.id for pep_case in pep_cases}),
            risk_assessment_id=risk_assessment.id,
        )

    @staticmethod
    def _extract_policy_alerts(candidate: ScreeningCandidate) -> list[dict[str, Any]]:
        if not isinstance(candidate.policy_flags, dict):
            return []
        alerts = candidate.policy_flags.get("alerts")
        if not isinstance(alerts, list):
            return []
        return [alert for alert in alerts if isinstance(alert, dict)]

    @staticmethod
    def _extract_triggered_factors(risk_assessment: RiskAssessment) -> list[str]:
        factor_breakdown = risk_assessment.factor_breakdown
        if not isinstance(factor_breakdown, dict):
            return []
        triggered = factor_breakdown.get("triggered_factors")
        if not isinstance(triggered, list):
            return []
        return [str(item) for item in triggered]

    @staticmethod
    def _severity_rank(severity: str) -> int:
        order = {"high": 0, "critical": 0, "medium": 1, "low": 2}
        return order.get(severity.lower(), 3)


async def generate_client_compliance_decision(
    db: Session,
    client_id: int,
    *,
    deal_id: int | None = None,
    actor: str = "demo_user",
) -> ComplianceDecisionResponse:
    return await ComplianceDecisionService.generate_client_decision(
        db=db,
        client_id=client_id,
        deal_id=deal_id,
        actor=actor,
    )
