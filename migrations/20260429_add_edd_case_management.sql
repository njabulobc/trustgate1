CREATE TABLE IF NOT EXISTS edd_cases (
    id INTEGER PRIMARY KEY,
    trigger_type TEXT NOT NULL CHECK (trigger_type IN ('screening','risk','pep','manual')),
    trigger_reference VARCHAR(120),
    priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low','medium','high','critical')),
    risk_level VARCHAR(50),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','assigned','in_review','escalated','approved','rejected','closed')),
    assignee VARCHAR(120),
    due_date DATETIME,
    acknowledged_at DATETIME,
    started_at DATETIME,
    escalated_at DATETIME,
    closed_at DATETIME,
    closure_reason TEXT,
    closure_evidence JSON,
    client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    linked_party_id INTEGER REFERENCES linked_parties(id) ON DELETE SET NULL,
    deal_id INTEGER REFERENCES deals(id) ON DELETE SET NULL,
    screening_candidate_id INTEGER UNIQUE REFERENCES screening_candidates(id) ON DELETE SET NULL,
    risk_assessment_id INTEGER UNIQUE REFERENCES risk_assessments(id) ON DELETE SET NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_edd_cases_status ON edd_cases(status);
CREATE INDEX IF NOT EXISTS ix_edd_cases_priority ON edd_cases(priority);
CREATE INDEX IF NOT EXISTS ix_edd_cases_assignee ON edd_cases(assignee);
CREATE INDEX IF NOT EXISTS ix_edd_cases_client_id ON edd_cases(client_id);
CREATE INDEX IF NOT EXISTS ix_edd_cases_due_date ON edd_cases(due_date);

ALTER TABLE pep_cases ADD COLUMN edd_case_id INTEGER UNIQUE REFERENCES edd_cases(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_pep_cases_edd_case_id ON pep_cases(edd_case_id);
