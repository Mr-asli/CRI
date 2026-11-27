-- Preserve the exact timestamp input so the database can independently recompute event hashes.
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS event_time double precision NOT NULL DEFAULT 0;
