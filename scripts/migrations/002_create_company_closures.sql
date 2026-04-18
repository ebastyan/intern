-- scripts/migrations/002_create_company_closures.sql
CREATE TABLE IF NOT EXISTS company_closures (
  date DATE PRIMARY KEY,
  reason VARCHAR(200),
  detected_automatically BOOLEAN NOT NULL DEFAULT true,
  validated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_closures_date ON company_closures(date);
