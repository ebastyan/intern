-- scripts/migrations/001_create_holidays.sql
CREATE TABLE IF NOT EXISTS holidays (
  date DATE NOT NULL,
  name VARCHAR(100) NOT NULL,
  type VARCHAR(20) NOT NULL CHECK (type IN ('national', 'catholic', 'orthodox')),
  is_official BOOLEAN NOT NULL,
  PRIMARY KEY (date, type)
);

CREATE INDEX IF NOT EXISTS idx_holidays_date ON holidays(date);
CREATE INDEX IF NOT EXISTS idx_holidays_official ON holidays(date) WHERE is_official = true;
