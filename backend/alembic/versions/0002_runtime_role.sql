-- Run as database owner. The API must never connect as the schema owner.
SELECT format('CREATE ROLE cri_app LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cri_app')\gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO cri_app', :'database_name')\gexec
GRANT USAGE ON SCHEMA public TO cri_app;
GRANT SELECT, INSERT, UPDATE ON TABLE tasks, memory_records, memory_embeddings TO cri_app;
GRANT SELECT, INSERT ON TABLE audit_events TO cri_app;
GRANT USAGE, SELECT ON SEQUENCE audit_events_sequence_seq TO cri_app;
REVOKE UPDATE, DELETE, TRUNCATE ON TABLE audit_events FROM cri_app;
