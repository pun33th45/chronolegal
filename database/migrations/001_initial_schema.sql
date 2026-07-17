-- =============================================================================
-- ChronoLegal Initial Schema
-- This runs automatically when the PostgreSQL container starts
-- =============================================================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For full-text search
CREATE EXTENSION IF NOT EXISTS "btree_gin"; -- For GIN indexes

-- Create indexes for performance after tables are created by SQLAlchemy
-- (SQLAlchemy creates the tables; this script adds extra optimizations)

-- Note: Tables are created by SQLAlchemy's create_all on startup.
-- This file adds supplementary indexes and constraints.

-- Full-text search index on case name
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'legal_cases') THEN
        CREATE INDEX IF NOT EXISTS idx_legal_cases_name_trgm
            ON legal_cases USING gin (case_name gin_trgm_ops);

        CREATE INDEX IF NOT EXISTS idx_legal_cases_acts_gin
            ON legal_cases USING gin (acts);

        CREATE INDEX IF NOT EXISTS idx_legal_cases_judges_gin
            ON legal_cases USING gin (judges);

        CREATE INDEX IF NOT EXISTS idx_legal_cases_keywords_gin
            ON legal_cases USING gin (keywords);

        CREATE INDEX IF NOT EXISTS idx_legal_cases_date
            ON legal_cases (judgment_date DESC NULLS LAST);
    END IF;
END $$;
