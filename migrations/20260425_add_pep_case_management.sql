-- Adds explicit PEP/RCA case-management controls and candidate policy classification.

ALTER TABLE screening_candidates ADD COLUMN match_category VARCHAR(20) NOT NULL DEFAULT 'standard';
ALTER TABLE screening_candidates ADD COLUMN policy_flags JSON;

CREATE TABLE IF NOT EXISTS pep_cases (
    id INTEGER PRIMARY KEY,
    screening_candidate_id INTEGER NOT NULL UNIQUE,
    status VARCHAR(40) NOT NULL DEFAULT 'open',
    senior_approval_status VARCHAR(40) NOT NULL DEFAULT 'pending',
    source_of_wealth_status VARCHAR(40) NOT NULL DEFAULT 'pending',
    source_of_funds_status VARCHAR(40) NOT NULL DEFAULT 'pending',
    enhanced_monitoring BOOLEAN NOT NULL DEFAULT 1,
    monitoring_notes TEXT,
    closure_evidence JSON,
    reviewed_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (screening_candidate_id) REFERENCES screening_candidates(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_pep_cases_screening_candidate_id ON pep_cases(screening_candidate_id);
CREATE INDEX IF NOT EXISTS ix_pep_cases_status ON pep_cases(status);
CREATE INDEX IF NOT EXISTS ix_screening_candidates_match_category ON screening_candidates(match_category);
