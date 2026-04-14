BEGIN;

-- -----------------------------------------------------------------------------
-- R2 iframe refactor: HMAC secret moves from tenants to organizations; cid now
-- maps to an Organization (shared space) rather than a personal Tenant.
-- Pre-migration cleanup first so drop-column doesn't leave orphan rows.
-- -----------------------------------------------------------------------------

-- Clean up R1 iframe test data (UAT / E2E).
DELETE FROM users WHERE tenant_id IN (
    SELECT id FROM tenants WHERE external_id IN ('UAT-1','E2E-TEST-1','E2E1','TEST1','MANUAL')
);
DELETE FROM tenants WHERE external_id IN ('UAT-1','E2E-TEST-1','E2E1','TEST1','MANUAL');
DELETE FROM iframe_nonces;  -- schema is changing; no prod data

-- tenants: drop iframe-specific fields
DROP INDEX IF EXISTS idx_tenants_external_id;
ALTER TABLE tenants DROP COLUMN IF EXISTS external_id;
ALTER TABLE tenants DROP COLUMN IF EXISTS iframe_secret;

-- organizations: add iframe-specific fields
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS external_id VARCHAR(128);
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS iframe_secret TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_organizations_external_id
    ON organizations(external_id)
    WHERE external_id IS NOT NULL AND deleted_at IS NULL;

-- iframe_nonces: rekey against organization instead of tenant
DROP INDEX IF EXISTS idx_iframe_nonces_ts;
ALTER TABLE iframe_nonces DROP CONSTRAINT IF EXISTS iframe_nonces_tenant_id_nonce_key;
ALTER TABLE iframe_nonces RENAME COLUMN tenant_id TO organization_id;
-- Note: tenant_id was BIGINT, organization_id should be VARCHAR(36) since Organization.ID is a UUID.
ALTER TABLE iframe_nonces ALTER COLUMN organization_id TYPE VARCHAR(36) USING organization_id::text;
ALTER TABLE iframe_nonces ADD CONSTRAINT iframe_nonces_org_nonce_key UNIQUE (organization_id, nonce);
CREATE INDEX IF NOT EXISTS idx_iframe_nonces_ts ON iframe_nonces(ts);

COMMIT;
