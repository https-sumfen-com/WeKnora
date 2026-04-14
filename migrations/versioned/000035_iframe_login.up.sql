BEGIN;

-- users: add mobile column + partial unique index
ALTER TABLE users ADD COLUMN IF NOT EXISTS mobile VARCHAR(11);
CREATE UNIQUE INDEX IF NOT EXISTS uk_users_tenant_mobile
    ON users(tenant_id, mobile)
    WHERE mobile IS NOT NULL AND deleted_at IS NULL;

-- tenants: add external_id + iframe_secret
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS external_id VARCHAR(128);
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS iframe_secret TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS uk_tenants_external_id
    ON tenants(external_id)
    WHERE external_id IS NOT NULL AND deleted_at IS NULL;

-- iframe_nonces table
CREATE TABLE IF NOT EXISTS iframe_nonces (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   BIGINT      NOT NULL,
    nonce       VARCHAR(64) NOT NULL,
    ts          BIGINT      NOT NULL,
    consumed_at TIMESTAMP   NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, nonce)
);
CREATE INDEX IF NOT EXISTS idx_iframe_nonces_ts ON iframe_nonces(ts);

COMMIT;
