BEGIN;
DROP TABLE IF EXISTS iframe_nonces;
DROP INDEX IF EXISTS idx_tenants_external_id;
DROP INDEX IF EXISTS idx_users_tenant_mobile;
ALTER TABLE tenants DROP COLUMN IF EXISTS iframe_secret;
ALTER TABLE tenants DROP COLUMN IF EXISTS external_id;
ALTER TABLE users DROP COLUMN IF EXISTS mobile;
COMMIT;
