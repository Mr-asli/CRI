# Database migrations

Apply the versioned PostgreSQL migration using a migration-owner account:

```sh
psql "$CRI_DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/alembic/versions/0001_initial.sql
```

The runtime application role should receive only the minimum required DML privileges. It must not own the schema, migration functions, or audit trigger. The SQLAlchemy models describe application records; the SQL migration additionally enables pgvector and installs the append-only audit trigger.
