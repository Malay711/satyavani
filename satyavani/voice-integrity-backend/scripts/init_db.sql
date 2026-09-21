-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============ USERS ============
CREATE TABLE IF NOT EXISTS users (
  id BIGSERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  org_id BIGINT,
  password_hash VARCHAR(255) NOT NULL,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now(),
  deleted_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS organizations (
  id BIGSERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  api_key VARCHAR(255) UNIQUE,
  tier VARCHAR(32) DEFAULT 'free',  -- free, pro, enterprise
  quota_monthly INT DEFAULT 100,
  created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_users_org ON users(org_id);
CREATE INDEX idx_users_email ON users(email);

-- ============ ANALYSIS JOBS ============
CREATE TABLE IF NOT EXISTS analysis_jobs (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  org_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  
  audio_file_path VARCHAR(512),        -- local path or minio key
  audio_file_hash VARCHAR(64),         -- sha256 hex
  audio_duration_ms INT,
  sample_rate INT DEFAULT 16000,
  file_size_bytes INT,
  
  source VARCHAR(32) DEFAULT 'upload', -- upload, record, api
  user_note TEXT,
  
  status VARCHAR(32) DEFAULT 'queued', -- queued, processing, completed, failed
  error_message TEXT,
  
  processing_started_at TIMESTAMP,
  processing_ended_at TIMESTAMP,
  
  created_at TIMESTAMP DEFAULT now(),
  expires_at TIMESTAMP DEFAULT (now() + interval '30 days'),
  
  INDEX (user_id, created_at DESC),
  INDEX (org_id),
  INDEX (status),
  INDEX (created_at)
);

-- ============ ANALYSIS RESULTS ============
CREATE TABLE IF NOT EXISTS analysis_results (
  id BIGSERIAL PRIMARY KEY,
  job_id BIGINT UNIQUE NOT NULL REFERENCES analysis_jobs(id) ON DELETE CASCADE,
  
  verdict VARCHAR(32),                 -- human, synthetic, replay, uncertain
  authenticity_score INT,              -- 0-100
  risk_score INT,                      -- 0-100 (inverse of authenticity)
  confidence INT,                      -- 0-100
  
  anti_spoof_score INT,
  temporal_consistency INT,
  spectral_score INT,
  replay_indicator INT,
  
  model_version VARCHAR(64) DEFAULT 'aasist-v1.0',
  inference_time_ms INT,
  
  feature_data JSONB,                  -- { acoustic: {...}, prosody: {...} }
  risk_timeline JSONB,                 -- array of {time_ms, risk} points
  
  created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_results_job ON analysis_results(job_id);
CREATE INDEX idx_results_verdict ON analysis_results(verdict);

-- ============ EVIDENCE / AUDIT ============
CREATE TABLE IF NOT EXISTS evidence_records (
  id BIGSERIAL PRIMARY KEY,
  result_id BIGINT NOT NULL REFERENCES analysis_results(id) ON DELETE CASCADE,
  
  evidence_type VARCHAR(64),           -- anti_spoof, temporal, spectral, replay
  label VARCHAR(255),
  score INT,                           -- 0-100
  interpretation VARCHAR(32),          -- high, moderate, low
  details TEXT,
  
  created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_evidence_result ON evidence_records(result_id);

-- ============ AUDIT LOG ============
CREATE TABLE IF NOT EXISTS audit_log (
  id BIGSERIAL PRIMARY KEY,
  org_id BIGINT REFERENCES organizations(id),
  user_id BIGINT REFERENCES users(id),
  
  action VARCHAR(64),                  -- upload, analyze, view, delete
  resource_type VARCHAR(64),           -- job, result
  resource_id BIGINT,
  
  ip_address INET,
  status_code INT,
  error_message TEXT,
  
  created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_audit_org ON audit_log(org_id, created_at DESC);
CREATE INDEX idx_audit_user ON audit_log(user_id, created_at DESC);

-- ============ QUOTA TRACKING ============
CREATE TABLE IF NOT EXISTS quota_usage (
  id BIGSERIAL PRIMARY KEY,
  org_id BIGINT UNIQUE NOT NULL REFERENCES organizations(id),
  year_month DATE,                     -- first day of month
  
  analyses_count INT DEFAULT 0,
  audio_processed_seconds INT DEFAULT 0,
  
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_quota_org ON quota_usage(org_id, year_month DESC);

-- ============ SEED DATA ============
INSERT INTO organizations (name, tier, quota_monthly) 
VALUES 
  ('Hack Forge Team', 'free', 1000),
  ('Test Org', 'free', 500)
ON CONFLICT DO NOTHING;

INSERT INTO users (email, org_id, password_hash, is_active)
SELECT 'demo@voiceintegrity.local', id, '$2b$12$demo_hash_bcrypt', TRUE
FROM organizations
WHERE name = 'Hack Forge Team'
ON CONFLICT DO NOTHING;

-- Cleanup function (run daily via cron/scheduler)
CREATE OR REPLACE FUNCTION cleanup_expired_data()
RETURNS void AS $$
BEGIN
  DELETE FROM analysis_jobs
  WHERE expires_at < now() AND status = 'completed';
  
  DELETE FROM analysis_results
  WHERE created_at < now() - interval '30 days';
END;
$$ LANGUAGE plpgsql;