BEGIN;

-- Revert iframe_nonces
ALTER TABLE iframe_nonces DROP CONSTRAINT IF EXISTS iframe_nonces_org_nonce_key;
ALTER TABLE iframe_nonces ALTER COLUMN organization_id TYPE BIGINT USING NULLIF(organization_id, '')::bigint;
ALTER TABLE iframe_nonces RENAME COLUMN organization_id TO tenant_id;
ALTER TABLE iframe_nonces ADD CONSTRAINT iframe_nonces_tenant_id_nonce_key UNIQUE (tenant_id, nonce);
CREATE INDEX IF NOT EXISTS idx_iframe_nonces_ts ON iframe_nonces(ts);

-- Remove organization iframe fields
DROP INDEX IF EXISTS idx_organizations_external_id;
ALTER TABLE organizations DROP COLUMN IF EXISTS iframe_secret;
ALTER TABLE organizations DROP COLUMN IF EXISTS external_id;

-- Re-add tenant iframe fields (data is lost)
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS external_id VARCHAR(128);
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS iframe_secret TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_tenants_external_id
    ON tenants(external_id)
    WHERE external_id IS NOT NULL AND deleted_at IS NULL;

COMMIT;
