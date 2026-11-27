"""Run versioned CRI PostgreSQL migrations using a dedicated schema-owner URL."""
from __future__ import annotations
import os
from pathlib import Path
import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "alembic" / "versions"

def main():
    url = os.getenv("CRI_MIGRATION_DATABASE_URL", "")
    runtime_password = os.getenv("CRI_APP_PASSWORD", "")
    if not url or len(runtime_password) < 32:
        raise SystemExit("CRI_MIGRATION_DATABASE_URL and CRI_APP_PASSWORD (>=32 chars) are required")
    if url.startswith("postgresql+psycopg://"):
        url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    with psycopg.connect(url) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS cri_schema_migrations (version varchar(32) PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
        for version in ("0001_initial", "0002_runtime_role", "0003_runtime_state", "0004_audit_event_time"):
            if conn.execute("SELECT 1 FROM cri_schema_migrations WHERE version=%s", (version,)).fetchone():
                continue
            if version == "0001_initial":
                conn.execute((MIGRATIONS / (version + ".sql")).read_text(), prepare=False)
            elif version == "0002_runtime_role":
                exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname='cri_app'").fetchone()
                if exists:
                    conn.execute(sql.SQL("ALTER ROLE cri_app WITH LOGIN PASSWORD {}").format(sql.Literal(runtime_password)))
                else:
                    conn.execute(sql.SQL("CREATE ROLE cri_app LOGIN PASSWORD {}").format(sql.Literal(runtime_password)))
                conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO cri_app").format(sql.Identifier(conn.info.dbname)))
                conn.execute("GRANT USAGE ON SCHEMA public TO cri_app")
                conn.execute("GRANT SELECT, INSERT, UPDATE ON TABLE tasks, memory_records, memory_embeddings TO cri_app")
                conn.execute("GRANT SELECT, INSERT ON TABLE audit_events TO cri_app")
                conn.execute("GRANT USAGE, SELECT ON SEQUENCE audit_events_sequence_seq TO cri_app")
                conn.execute("REVOKE UPDATE, DELETE, TRUNCATE ON TABLE audit_events FROM cri_app")
            else:
                conn.execute((MIGRATIONS / (version + ".sql")).read_text(), prepare=False)
            conn.execute("INSERT INTO cri_schema_migrations(version) VALUES (%s)", (version,))
        conn.commit()
    print("CRI PostgreSQL migrations are current")

if __name__ == "__main__": main()
