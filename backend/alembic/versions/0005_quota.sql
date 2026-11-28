CREATE TABLE IF NOT EXISTS plans (
  id varchar(64) PRIMARY KEY, name varchar(128) NOT NULL,
  quotas jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS quota_users (
  id varchar(128) PRIMARY KEY, plan_id varchar(64) NOT NULL REFERENCES plans(id),
  active boolean NOT NULL DEFAULT true
);
CREATE TABLE IF NOT EXISTS usage (
  id bigserial PRIMARY KEY, user_id varchar(128) NOT NULL REFERENCES quota_users(id),
  feature varchar(64) NOT NULL, quantity integer NOT NULL CHECK (quantity > 0),
  usage_date date NOT NULL DEFAULT CURRENT_DATE
);
CREATE INDEX IF NOT EXISTS ix_usage_user_feature_date ON usage(user_id, feature, usage_date);
CREATE TABLE IF NOT EXISTS feature_flags (
  name varchar(64) PRIMARY KEY, enabled boolean NOT NULL DEFAULT true
);
INSERT INTO plans(id,name,quotas) VALUES ('free','Free','{"task_create":3,"agent_run":3,"memory_write":10}'::jsonb)
ON CONFLICT (id) DO NOTHING;
INSERT INTO quota_users(id,plan_id) VALUES ('human-admin','free') ON CONFLICT (id) DO NOTHING;
GRANT SELECT ON TABLE plans, quota_users, feature_flags TO cri_app;
GRANT SELECT, INSERT ON TABLE usage TO cri_app;
GRANT USAGE, SELECT ON SEQUENCE usage_id_seq TO cri_app;
