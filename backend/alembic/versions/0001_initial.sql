-- PostgreSQL 16 + pgvector initial schema. Apply once with psql -v ON_ERROR_STOP=1.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS tasks (
  id varchar(32) PRIMARY KEY, goal text NOT NULL, status varchar(32) NOT NULL,
  proposal jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_tasks_status ON tasks(status);
CREATE TABLE IF NOT EXISTS audit_events (
  sequence bigserial PRIMARY KEY, event_id varchar(64) UNIQUE NOT NULL,
  event varchar(128) NOT NULL, actor varchar(128) NOT NULL, details jsonb NOT NULL,
  previous_hash char(64) NOT NULL, event_hash char(64) UNIQUE NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS memory_records (
  id varchar(32) PRIMARY KEY, kind varchar(32) NOT NULL, content text NOT NULL,
  metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_memory_kind ON memory_records(kind);
CREATE TABLE IF NOT EXISTS memory_embeddings (
  memory_id varchar(32) PRIMARY KEY REFERENCES memory_records(id) ON DELETE CASCADE,
  embedding vector(1536) NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_memory_embeddings_cosine ON memory_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
-- Audit rows are append-only for the application DB role. Use a separate migration owner.
CREATE OR REPLACE FUNCTION cri_reject_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'audit_events is append-only'; END; $$;
DROP TRIGGER IF EXISTS audit_events_no_mutation ON audit_events;
CREATE TRIGGER audit_events_no_mutation BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION cri_reject_audit_mutation();
