-- Durable self-improvement and agent state. Apply as the schema owner.
CREATE TABLE IF NOT EXISTS improvement_records (
  id varchar(32) PRIMARY KEY,
  description text NOT NULL,
  stage varchar(32) NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_improvement_records_stage ON improvement_records(stage);
CREATE TABLE IF NOT EXISTS agent_states (
  agent_id varchar(128) PRIMARY KEY,
  role varchar(32) NOT NULL,
  state jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE ON TABLE improvement_records, agent_states TO cri_app;
