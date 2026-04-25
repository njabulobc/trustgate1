-- Schema docs: `screening_candidates.policy_flags` is the canonical storage for deterministic
-- multi-factor PEP/RCA classification metadata.
--
-- JSON shape (v2):
-- {
--   "version": "candidate_policy_flags.v2",
--   "policy_pack": "default|enhanced_due_diligence",
--   "candidate_type_signal": "pep|rca|standard",
--   "topics": ["role.pep", "role.rca", ...],
--   "signals": {
--     "provider_score": 0.0-1.0,
--     "list_quality": 0.0-1.0,
--     "name_dob_country_concordance": 0.0-1.0
--   },
--   "weights": {
--     "provider_score": number,
--     "list_quality": number,
--     "name_dob_country_concordance": number
--   },
--   "thresholds": {
--     "pep_threshold": number,
--     "rca_threshold": number,
--     "false_positive_score_cap": number,
--     "minimum_topic_signal": number
--   },
--   "weighted_score": 0.0-1.0,
--   "false_positive_reduction": {
--     "applied": boolean,
--     "rules_triggered": [string],
--     "high_confidence_override": boolean
--   },
--   "classification": {
--     "category": "standard|pep|rca",
--     "decision_basis": "multi_factor_policy_pack"
--   },
--   "explainability": [
--     {"factor": "provider_score", "weight": number, "signal": number, "contribution": number},
--     {"factor": "list_quality", "weight": number, "signal": number, "contribution": number},
--     {"factor": "name_dob_country_concordance", "weight": number, "signal": number, "contribution": number}
--   ],
--   "alerts": [{"policy": string, "severity": string, "rationale": string}]
-- }
--
-- Analyst helper view: flatten key policy metadata for easier ad-hoc review.

CREATE VIEW IF NOT EXISTS screening_candidate_policy_audit_v AS
SELECT
    sc.id AS screening_candidate_id,
    sc.screening_result_id,
    sc.match_category,
    json_extract(sc.policy_flags, '$.version') AS policy_version,
    json_extract(sc.policy_flags, '$.policy_pack') AS policy_pack,
    json_extract(sc.policy_flags, '$.candidate_type_signal') AS candidate_type_signal,
    json_extract(sc.policy_flags, '$.weighted_score') AS weighted_score,
    json_extract(sc.policy_flags, '$.signals.provider_score') AS provider_score_signal,
    json_extract(sc.policy_flags, '$.signals.list_quality') AS list_quality_signal,
    json_extract(sc.policy_flags, '$.signals.name_dob_country_concordance') AS concordance_signal,
    json_extract(sc.policy_flags, '$.thresholds.pep_threshold') AS pep_threshold,
    json_extract(sc.policy_flags, '$.thresholds.rca_threshold') AS rca_threshold,
    json_extract(sc.policy_flags, '$.false_positive_reduction.applied') AS false_positive_reduction_applied,
    json_extract(sc.policy_flags, '$.false_positive_reduction.rules_triggered') AS false_positive_reduction_rules,
    json_extract(sc.policy_flags, '$.classification.category') AS classification_category,
    json_extract(sc.policy_flags, '$.classification.decision_basis') AS decision_basis,
    json_extract(sc.policy_flags, '$.alerts') AS alerts,
    sc.created_at,
    sc.updated_at
FROM screening_candidates sc;
