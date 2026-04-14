# iframe 嵌入免登 + 前端嵌入模式 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 WeKnora 可被外部系统以 `<iframe src="/iframe-login?cid=..&mobile=..&ts=..&nonce=..&sig=..">` 嵌入，HMAC 校验通过后按需创建 tenant/user 并签发 JWT；嵌入场景下隐藏 logo/外链/语言切换器。

**Architecture:** 方案 A（后端独立端点 + 前端薄跳转页）。每个 cid 独立 HMAC secret，通过 CLI `weknora-admin` 预先 provision；iframe-login 端点不自动建 tenant，但在已 provisioned 的 tenant 下按需建 user。前端用 Pinia `embedded` store + sessionStorage 承载嵌入标志。

**Tech Stack:** Go 1.24 (Gin, GORM, dig DI, jwt-v5, bcrypt, hmac/sha256, crypto/rand, golang.org/x/time/rate), Vue 3 + Pinia + TDesign, golang-migrate。

**设计文档:** `docs/superpowers/specs/2026-04-14-iframe-auto-login-design.md`

---

## File Structure

**后端改动/新增**
- `migrations/versioned/000035_iframe_login.{up,down}.sql` — Postgres/ParadeDB
- `migrations/sqlite/000000_init.up.sql` — Lite 初始化合并新字段
- `internal/types/user.go` — +`Mobile` 字段
- `internal/types/tenant.go` — +`ExternalID` +`IframeSecret` + 加解密钩子扩展
- `internal/types/iframe_login.go` — DTO（新）
- `internal/types/iframe_nonce.go` — GORM model（新）
- `internal/types/interfaces/user.go` — `UserService.IframeLogin` 接口
- `internal/types/interfaces/iframe_nonce.go` — 新 repo interface
- `internal/types/interfaces/tenant.go` — `TenantRepository.GetByExternalID` 接口
- `internal/application/repository/user.go` — +`GetByTenantAndMobile`
- `internal/application/repository/tenant.go` — +`GetByExternalID`
- `internal/application/repository/iframe_nonce.go` — 新
- `internal/application/service/iframe_auth.go` — HMAC 校验 + nonce 消费（新）
- `internal/application/service/iframe_auth_test.go` — 新
- `internal/application/service/user.go` — +`IframeLogin` 方法
- `internal/application/service/user_iframe_test.go` — 新
- `internal/handler/auth.go` — +`IframeLogin` handler
- `internal/middleware/auth.go` — 白名单 `/auth/iframe-login`
- `internal/middleware/frame_ancestors.go` — 新
- `internal/router/router.go` — 挂载 + 中间件
- `internal/container/container.go` — 注入新 repo/service
- `cmd/weknora-admin/main.go` — 新二进制
- `cmd/weknora-admin/iframe.go` — provision/rotate/revoke 子命令
- `Makefile` — +`build-admin` 目标

**前端改动/新增**
- `frontend/src/stores/embedded.ts` — 新
- `frontend/src/composables/useEmbedded.ts` — 新
- `frontend/src/api/auth.ts` — +`iframeLogin`
- `frontend/src/views/auth/IframeLogin.vue` — 新
- `frontend/src/router/index.ts` — +路由 + 守卫
- `frontend/src/views/auth/Login.vue` — 条件渲染
- `frontend/src/App.vue` + 主 layout 组件 — 条件渲染

**文档**
- `docs/iframe-integration.md` — 外部系统接入指南（新）

---

## Phase 1 · 数据库迁移

### Task 1: Postgres/ParadeDB 迁移脚本

**Files:**
- Create: `migrations/versioned/000035_iframe_login.up.sql`
- Create: `migrations/versioned/000035_iframe_login.down.sql`

- [ ] **Step 1: Write up migration**

File `migrations/versioned/000035_iframe_login.up.sql`:
```sql
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
```

- [ ] **Step 2: Write down migration**

File `migrations/versioned/000035_iframe_login.down.sql`:
```sql
BEGIN;
DROP TABLE IF EXISTS iframe_nonces;
DROP INDEX IF EXISTS uk_tenants_external_id;
DROP INDEX IF EXISTS uk_users_tenant_mobile;
ALTER TABLE tenants DROP COLUMN IF EXISTS iframe_secret;
ALTER TABLE tenants DROP COLUMN IF EXISTS external_id;
ALTER TABLE users DROP COLUMN IF EXISTS mobile;
COMMIT;
```

- [ ] **Step 3: Apply migration and verify schema**

Run (after `make dev-start`):
```bash
make migrate-up
docker exec -it weknora-postgres psql -U postgres -d weknora -c "\d users" | grep mobile
docker exec -it weknora-postgres psql -U postgres -d weknora -c "\d tenants" | grep -E "external_id|iframe_secret"
docker exec -it weknora-postgres psql -U postgres -d weknora -c "\d iframe_nonces"
```
Expected: `mobile character varying(11)`, `external_id character varying(128)`, `iframe_secret text`, table `iframe_nonces` exists with expected columns.

- [ ] **Step 4: Verify rollback works**

Run:
```bash
make migrate-down
docker exec -it weknora-postgres psql -U postgres -d weknora -c "\d users" | grep mobile && echo "FAIL" || echo "OK"
make migrate-up
```
Expected: second command prints `OK`, indicating `mobile` column removed by down migration; then re-applied by up.

- [ ] **Step 5: Commit**

```bash
git add migrations/versioned/000035_iframe_login.up.sql migrations/versioned/000035_iframe_login.down.sql
git commit -m "feat(db): add iframe_login schema (users.mobile, tenants.external_id/iframe_secret, iframe_nonces)"
```

### Task 2: SQLite (Lite) schema

**Files:**
- Modify: `migrations/sqlite/000000_init.up.sql`

- [ ] **Step 1: Locate users/tenants CREATE TABLE blocks**

Run:
```bash
grep -n "CREATE TABLE.*users\|CREATE TABLE.*tenants" migrations/sqlite/000000_init.up.sql
```
Note line numbers to target edits.

- [ ] **Step 2: Add mobile column to users CREATE TABLE block**

Add inside the `CREATE TABLE users (...)` block after the existing `email` column definition:
```sql
    mobile TEXT,
```

- [ ] **Step 3: Add iframe columns to tenants CREATE TABLE block**

Add inside `CREATE TABLE tenants (...)` after `api_key`:
```sql
    external_id TEXT,
    iframe_secret TEXT,
```

- [ ] **Step 4: Add indexes and iframe_nonces table at end of file**

Append:
```sql
CREATE UNIQUE INDEX IF NOT EXISTS uk_users_tenant_mobile
    ON users(tenant_id, mobile)
    WHERE mobile IS NOT NULL AND deleted_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uk_tenants_external_id
    ON tenants(external_id)
    WHERE external_id IS NOT NULL AND deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS iframe_nonces (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id   INTEGER      NOT NULL,
    nonce       TEXT         NOT NULL,
    ts          INTEGER      NOT NULL,
    consumed_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, nonce)
);
CREATE INDEX IF NOT EXISTS idx_iframe_nonces_ts ON iframe_nonces(ts);
```

- [ ] **Step 5: Build Lite and verify schema**

```bash
make build-lite SKIP_FRONTEND=1
rm -f ./weknora-lite.db
./WeKnora-lite &
sleep 3
sqlite3 ./weknora-lite.db ".schema users" | grep mobile
sqlite3 ./weknora-lite.db ".schema tenants" | grep -E "external_id|iframe_secret"
sqlite3 ./weknora-lite.db ".schema iframe_nonces"
kill %1
```
Expected: schema reflects new columns + new table.

- [ ] **Step 6: Commit**

```bash
git add migrations/sqlite/000000_init.up.sql
git commit -m "feat(db): mirror iframe_login schema in sqlite init"
```

---

## Phase 2 · Go 类型 & DTO

### Task 3: Add Mobile field to User

**Files:**
- Modify: `internal/types/user.go`

- [ ] **Step 1: Add Mobile field**

In `internal/types/user.go`, inside `type User struct { ... }` after the `Email` field (around line 16), insert:
```go
	// Mobile phone number (China mainland, 11 digits), unique per tenant
	Mobile string `json:"mobile,omitempty" gorm:"type:varchar(11);index"`
```

- [ ] **Step 2: Add Mobile to UserInfo and ToUserInfo**

In the same file, `type UserInfo struct {...}` (around line 123): add after `Email`:
```go
	Mobile    string    `json:"mobile,omitempty"`
```
In `ToUserInfo()` (around line 136): add in the returned struct literal:
```go
		Mobile:              u.Mobile,
```

- [ ] **Step 3: Verify compilation**

```bash
go build ./...
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add internal/types/user.go
git commit -m "feat(types): add Mobile field to User"
```

### Task 4: Add ExternalID + IframeSecret to Tenant with AES encryption hooks

**Files:**
- Modify: `internal/types/tenant.go`

- [ ] **Step 1: Add new fields to Tenant struct**

In `internal/types/tenant.go`, inside `type Tenant struct { ... }` after `APIKey` (line 81), insert:
```go
	// ExternalID is the business-side tenant identifier exposed in iframe URLs (cid)
	ExternalID string `yaml:"external_id"    json:"external_id,omitempty"    gorm:"type:varchar(128);uniqueIndex"`
	// IframeSecret is an AES-256-GCM encrypted HMAC secret for iframe URL signature
	IframeSecret string `yaml:"iframe_secret"  json:"-"                        gorm:"type:text"`
```

Note: `json:"-"` on IframeSecret keeps it out of API responses.

- [ ] **Step 2: Extend BeforeSave hook to encrypt IframeSecret**

Replace the existing `BeforeSave` method body (around line 141):
```go
func (t *Tenant) BeforeSave(tx *gorm.DB) error {
	key := utils.GetAESKey()
	if key != nil {
		if t.APIKey != "" {
			if encrypted, err := utils.EncryptAESGCM(t.APIKey, key); err == nil {
				tx.Statement.SetColumn("api_key", encrypted)
			}
		}
		if t.IframeSecret != "" {
			if encrypted, err := utils.EncryptAESGCM(t.IframeSecret, key); err == nil {
				tx.Statement.SetColumn("iframe_secret", encrypted)
			}
		}
	}
	return nil
}
```

- [ ] **Step 3: Extend AfterFind hook to decrypt IframeSecret**

Replace `AfterFind` (around line 152):
```go
func (t *Tenant) AfterFind(tx *gorm.DB) error {
	key := utils.GetAESKey()
	if key != nil {
		if t.APIKey != "" {
			if decrypted, err := utils.DecryptAESGCM(t.APIKey, key); err == nil {
				t.APIKey = decrypted
			}
		}
		if t.IframeSecret != "" {
			if decrypted, err := utils.DecryptAESGCM(t.IframeSecret, key); err == nil {
				t.IframeSecret = decrypted
			}
		}
	}
	return nil
}
```

- [ ] **Step 4: Compile**

```bash
go build ./...
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add internal/types/tenant.go
git commit -m "feat(types): add ExternalID/IframeSecret to Tenant with AES-GCM at rest"
```

### Task 5: iframe_login DTO + iframe_nonce model

**Files:**
- Create: `internal/types/iframe_login.go`
- Create: `internal/types/iframe_nonce.go`

- [ ] **Step 1: Create iframe_login.go**

File `internal/types/iframe_login.go`:
```go
package types

// IframeLoginRequest carries HMAC-signed parameters from an embedding parent system.
type IframeLoginRequest struct {
	CID    string `json:"cid"    binding:"required"`
	Mobile string `json:"mobile" binding:"required"`
	TS     string `json:"ts"     binding:"required"`
	Nonce  string `json:"nonce"  binding:"required"`
	Sig    string `json:"sig"    binding:"required"`
}

// IframeErrorCode is the `code` field returned to clients for iframe-login failures.
type IframeErrorCode string

const (
	IframeErrParamsMissing    IframeErrorCode = "IFRAME_PARAMS_MISSING"
	IframeErrMobileInvalid    IframeErrorCode = "IFRAME_MOBILE_INVALID"
	IframeErrBadSignature     IframeErrorCode = "IFRAME_BAD_SIGNATURE"
	IframeErrReplay           IframeErrorCode = "IFRAME_REPLAY"
	IframeErrUserDisabled     IframeErrorCode = "IFRAME_USER_DISABLED"
	IframeErrNotEnabled       IframeErrorCode = "IFRAME_NOT_ENABLED"
	IframeErrTenantNotFound   IframeErrorCode = "IFRAME_TENANT_NOT_FOUND"
	IframeErrInternal         IframeErrorCode = "IFRAME_INTERNAL"
)
```

- [ ] **Step 2: Create iframe_nonce.go**

File `internal/types/iframe_nonce.go`:
```go
package types

import "time"

// IframeNonce records a consumed HMAC URL nonce to prevent replay.
type IframeNonce struct {
	ID         uint64    `gorm:"primaryKey" json:"id"`
	TenantID   uint64    `gorm:"index;not null;uniqueIndex:uk_iframe_nonce" json:"tenant_id"`
	Nonce      string    `gorm:"type:varchar(64);not null;uniqueIndex:uk_iframe_nonce" json:"nonce"`
	TS         int64     `gorm:"not null;index" json:"ts"`
	ConsumedAt time.Time `gorm:"not null;default:CURRENT_TIMESTAMP" json:"consumed_at"`
}

// TableName returns the table name for IframeNonce.
func (IframeNonce) TableName() string { return "iframe_nonces" }
```

- [ ] **Step 3: Compile**

```bash
go build ./...
```

- [ ] **Step 4: Commit**

```bash
git add internal/types/iframe_login.go internal/types/iframe_nonce.go
git commit -m "feat(types): add iframe login DTO + nonce model"
```

---

## Phase 3 · Repositories

### Task 6: UserRepository.GetByTenantAndMobile

**Files:**
- Modify: `internal/types/interfaces/user.go`
- Modify: `internal/application/repository/user.go`

- [ ] **Step 1: Add interface method**

In `internal/types/interfaces/user.go`, `UserRepository` interface (around line 50), add before `UpdateUser`:
```go
	// GetUserByTenantAndMobile gets a user within a tenant by mobile number
	GetUserByTenantAndMobile(ctx context.Context, tenantID uint64, mobile string) (*types.User, error)
```

- [ ] **Step 2: Implement in repository**

In `internal/application/repository/user.go`, append (use the same pattern as existing `GetUserByEmail`):
```go
// GetUserByTenantAndMobile retrieves a user by tenant ID and mobile number.
// Returns (nil, nil) when the user does not exist.
func (r *userRepository) GetUserByTenantAndMobile(
	ctx context.Context, tenantID uint64, mobile string,
) (*types.User, error) {
	var user types.User
	err := r.db.WithContext(ctx).
		Where("tenant_id = ? AND mobile = ?", tenantID, mobile).
		First(&user).Error
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, nil
		}
		return nil, err
	}
	return &user, nil
}
```

Ensure imports at top of file include `"errors"` and `"gorm.io/gorm"` (usually already present).

- [ ] **Step 3: Compile**

```bash
go build ./...
```

- [ ] **Step 4: Commit**

```bash
git add internal/types/interfaces/user.go internal/application/repository/user.go
git commit -m "feat(repo): add UserRepository.GetUserByTenantAndMobile"
```

### Task 7: TenantRepository.GetByExternalID + UpdateIframeSecret

**Files:**
- Modify: `internal/types/interfaces/tenant.go`
- Modify: `internal/application/repository/tenant.go`

- [ ] **Step 1: Add interface methods**

In `internal/types/interfaces/tenant.go`, inside `TenantRepository` interface, add:
```go
	// GetByExternalID fetches a tenant by external business ID (cid). Returns (nil, nil) if absent.
	GetByExternalID(ctx context.Context, externalID string) (*types.Tenant, error)
	// UpdateIframeSecret persists a new plaintext secret (encrypted by Tenant.BeforeSave) or clears it when empty.
	UpdateIframeSecret(ctx context.Context, tenantID uint64, plaintextSecret string) error
```

- [ ] **Step 2: Implement GetByExternalID**

In `internal/application/repository/tenant.go`, append:
```go
// GetByExternalID finds a tenant by ExternalID. Returns (nil, nil) on not found.
func (r *tenantRepository) GetByExternalID(ctx context.Context, externalID string) (*types.Tenant, error) {
	var t types.Tenant
	err := r.db.WithContext(ctx).
		Where("external_id = ?", externalID).
		First(&t).Error
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, nil
		}
		return nil, err
	}
	return &t, nil
}

// UpdateIframeSecret sets/clears the iframe secret. Uses Updates via map so gorm runs BeforeSave
// hook and encrypts the plaintext when non-empty; passes empty string to clear.
func (r *tenantRepository) UpdateIframeSecret(ctx context.Context, tenantID uint64, plaintextSecret string) error {
	t := types.Tenant{IframeSecret: plaintextSecret}
	return r.db.WithContext(ctx).
		Model(&types.Tenant{}).
		Where("id = ?", tenantID).
		Updates(map[string]interface{}{
			"iframe_secret": t.IframeSecret,
		}).Error
}
```

Note: direct column update via `Updates(map)` bypasses `BeforeSave` hook. To keep encryption symmetric we instead call `Save`/`Model(&t).Update(...)` which triggers hooks. Replace step 2's `UpdateIframeSecret` body with:
```go
func (r *tenantRepository) UpdateIframeSecret(ctx context.Context, tenantID uint64, plaintextSecret string) error {
	// Load existing tenant so BeforeSave has the other fields; then set secret and Save.
	var t types.Tenant
	if err := r.db.WithContext(ctx).Where("id = ?", tenantID).First(&t).Error; err != nil {
		return err
	}
	t.IframeSecret = plaintextSecret
	return r.db.WithContext(ctx).Save(&t).Error
}
```

- [ ] **Step 3: Compile**

```bash
go build ./...
```

- [ ] **Step 4: Commit**

```bash
git add internal/types/interfaces/tenant.go internal/application/repository/tenant.go
git commit -m "feat(repo): add TenantRepository.GetByExternalID + UpdateIframeSecret"
```

### Task 8: IframeNonceRepository (new)

**Files:**
- Create: `internal/types/interfaces/iframe_nonce.go`
- Create: `internal/application/repository/iframe_nonce.go`

- [ ] **Step 1: Create interface**

File `internal/types/interfaces/iframe_nonce.go`:
```go
package interfaces

import (
	"context"

	"github.com/Tencent/WeKnora/internal/types"
)

// IframeNonceRepository persists consumed iframe-login nonces for replay protection.
type IframeNonceRepository interface {
	// Consume atomically records a (tenant, nonce) tuple.
	// Returns (true, nil) if inserted (first consumption); (false, nil) if already existed (replay).
	Consume(ctx context.Context, nonce *types.IframeNonce) (inserted bool, err error)
	// DeleteOlderThan prunes nonces with ts < cutoff (Unix seconds). Returns rows deleted.
	DeleteOlderThan(ctx context.Context, cutoff int64) (int64, error)
}
```

- [ ] **Step 2: Create implementation**

File `internal/application/repository/iframe_nonce.go`:
```go
package repository

import (
	"context"
	"errors"

	"github.com/jackc/pgx/v5/pgconn"
	"gorm.io/gorm"

	"github.com/Tencent/WeKnora/internal/types"
	"github.com/Tencent/WeKnora/internal/types/interfaces"
)

type iframeNonceRepository struct {
	db *gorm.DB
}

// NewIframeNonceRepository constructs a new IframeNonceRepository.
func NewIframeNonceRepository(db *gorm.DB) interfaces.IframeNonceRepository {
	return &iframeNonceRepository{db: db}
}

// Consume attempts to INSERT the nonce. Returns (false, nil) when the (tenant_id, nonce) pair already exists.
func (r *iframeNonceRepository) Consume(ctx context.Context, n *types.IframeNonce) (bool, error) {
	err := r.db.WithContext(ctx).Create(n).Error
	if err == nil {
		return true, nil
	}
	// Postgres unique violation → pgconn.PgError.Code == "23505"
	var pgErr *pgconn.PgError
	if errors.As(err, &pgErr) && pgErr.Code == "23505" {
		return false, nil
	}
	// SQLite unique constraint: err string contains "UNIQUE constraint failed"
	if err != nil && (errContainsSQLiteUnique(err) || errors.Is(err, gorm.ErrDuplicatedKey)) {
		return false, nil
	}
	return false, err
}

// DeleteOlderThan deletes nonces whose ts < cutoff.
func (r *iframeNonceRepository) DeleteOlderThan(ctx context.Context, cutoff int64) (int64, error) {
	res := r.db.WithContext(ctx).
		Where("ts < ?", cutoff).
		Delete(&types.IframeNonce{})
	return res.RowsAffected, res.Error
}

func errContainsSQLiteUnique(err error) bool {
	return err != nil && (containsStr(err.Error(), "UNIQUE constraint failed") ||
		containsStr(err.Error(), "constraint failed: iframe_nonces"))
}

func containsStr(s, sub string) bool {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return true
		}
	}
	return false
}
```

- [ ] **Step 3: Compile**

```bash
go build ./...
```
Expected: no errors. If `pgx/v5/pgconn` is missing from go.mod, it already is (from container.go imports).

- [ ] **Step 4: Commit**

```bash
git add internal/types/interfaces/iframe_nonce.go internal/application/repository/iframe_nonce.go
git commit -m "feat(repo): add IframeNonceRepository (Postgres + SQLite aware)"
```

---

## Phase 4 · iframe_auth 服务 (HMAC + nonce)

### Task 9: iframe_auth service + unit tests

**Files:**
- Create: `internal/application/service/iframe_auth.go`
- Create: `internal/application/service/iframe_auth_test.go`

- [ ] **Step 1: Write failing test file**

File `internal/application/service/iframe_auth_test.go`:
```go
package service

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"testing"
)

func TestSignIframeMessage_Deterministic(t *testing.T) {
	secret := "testsecret"
	got := SignIframeMessage(secret, "ACME", "13812345678", "1713081234", "nonce123")
	want := expectedHMAC(secret, "cid=ACME&mobile=13812345678&nonce=nonce123&ts=1713081234")
	if got != want {
		t.Fatalf("sig mismatch\n got=%s\nwant=%s", got, want)
	}
}

func TestVerifyIframeSignature_OrderInsensitiveViaDictSort(t *testing.T) {
	secret := "testsecret"
	sig := SignIframeMessage(secret, "ACME", "13812345678", "1000", "abcd")
	// Verify with same params → pass
	if !VerifyIframeSignature(secret, "ACME", "13812345678", "1000", "abcd", sig) {
		t.Fatal("verify should pass with identical params")
	}
	// Tamper each field → fail
	cases := []struct{ name, cid, mobile, ts, nonce string }{
		{"cid", "ACMEX", "13812345678", "1000", "abcd"},
		{"mobile", "ACME", "13812345679", "1000", "abcd"},
		{"ts", "ACME", "13812345678", "1001", "abcd"},
		{"nonce", "ACME", "13812345678", "1000", "abce"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if VerifyIframeSignature(secret, c.cid, c.mobile, c.ts, c.nonce, sig) {
				t.Fatalf("tampered %s should not verify", c.name)
			}
		})
	}
}

func TestVerifyIframeSignature_ConstantTime(t *testing.T) {
	secret := "testsecret"
	correct := SignIframeMessage(secret, "ACME", "138", "1", "n")
	wrong := "0" + correct[1:]
	if VerifyIframeSignature(secret, "ACME", "138", "1", "n", wrong) {
		t.Fatal("wrong sig must fail")
	}
}

func expectedHMAC(secret, msg string) string {
	m := hmac.New(sha256.New, []byte(secret))
	m.Write([]byte(msg))
	return hex.EncodeToString(m.Sum(nil))
}
```

- [ ] **Step 2: Run tests → expected FAIL**

```bash
go test ./internal/application/service/ -run TestSignIframe -v
go test ./internal/application/service/ -run TestVerifyIframe -v
```
Expected: compilation error (functions undefined).

- [ ] **Step 3: Write minimal implementation**

File `internal/application/service/iframe_auth.go`:
```go
package service

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
)

// SignIframeMessage builds the canonical message string (fields in dictionary order, no URL encoding)
// and returns hex(HMAC-SHA256(secret, message)).
func SignIframeMessage(secret, cid, mobile, ts, nonce string) string {
	msg := "cid=" + cid + "&mobile=" + mobile + "&nonce=" + nonce + "&ts=" + ts
	m := hmac.New(sha256.New, []byte(secret))
	m.Write([]byte(msg))
	return hex.EncodeToString(m.Sum(nil))
}

// VerifyIframeSignature performs constant-time comparison of the expected and provided signatures.
// Returns false on any decoding error or mismatch.
func VerifyIframeSignature(secret, cid, mobile, ts, nonce, providedSig string) bool {
	expected := SignIframeMessage(secret, cid, mobile, ts, nonce)
	if len(expected) != len(providedSig) {
		return false
	}
	expBytes, err1 := hex.DecodeString(expected)
	gotBytes, err2 := hex.DecodeString(providedSig)
	if err1 != nil || err2 != nil {
		return false
	}
	return hmac.Equal(expBytes, gotBytes)
}
```

- [ ] **Step 4: Run tests → expected PASS**

```bash
go test ./internal/application/service/ -run "TestSignIframe|TestVerifyIframe" -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/application/service/iframe_auth.go internal/application/service/iframe_auth_test.go
git commit -m "feat(service): add iframe HMAC sign/verify primitives"
```

---

## Phase 5 · UserService.IframeLogin

### Task 10: Add IframeLogin interface method

**Files:**
- Modify: `internal/types/interfaces/user.go`

- [ ] **Step 1: Add IframeErrorResult type and interface method**

In `internal/types/interfaces/user.go`:
- Below existing `UserService` interface, modify the interface to add:
```go
	// IframeLogin authenticates a request from an embedded iframe URL and returns a login response.
	// The error field is a *types.IframeLoginError for expected failure cases (signature, replay, etc.).
	IframeLogin(ctx context.Context, req *types.IframeLoginRequest) (*types.LoginResponse, error)
```

- [ ] **Step 2: Add IframeLoginError type in types package**

Append to `internal/types/iframe_login.go`:
```go
// IframeLoginError wraps a user-visible iframe-login failure with a stable code.
type IframeLoginError struct {
	Code    IframeErrorCode
	Message string
}

// Error satisfies the error interface.
func (e *IframeLoginError) Error() string { return string(e.Code) + ": " + e.Message }

// NewIframeLoginError constructs a typed iframe-login error.
func NewIframeLoginError(code IframeErrorCode, message string) *IframeLoginError {
	return &IframeLoginError{Code: code, Message: message}
}
```

- [ ] **Step 3: Compile**

```bash
go build ./...
```

- [ ] **Step 4: Commit**

```bash
git add internal/types/interfaces/user.go internal/types/iframe_login.go
git commit -m "feat(types): UserService.IframeLogin interface + IframeLoginError"
```

### Task 11: Implement UserService.IframeLogin

**Files:**
- Modify: `internal/application/service/user.go`

- [ ] **Step 1: Locate userService struct to find its repositories**

Run:
```bash
grep -n "type userService struct\|userRepo\|tenantService\|tenantRepo" internal/application/service/user.go | head
```
Note: `userService` uses `s.userRepo`, `s.tenantService`. We need tenant repository for `GetByExternalID`. If `tenantService` exposes it, reuse; otherwise, inject `tenantRepo` or fetch via existing method.

Run (to confirm tenantService interface):
```bash
grep -n "type TenantService interface\|GetByExternalID" internal/types/interfaces/tenant.go
```

If `tenantService` has no `GetByExternalID`, add a thin pass-through method on `TenantService` in step 2. Otherwise skip step 2.

- [ ] **Step 2 (conditional): Expose GetByExternalID via TenantService**

In `internal/types/interfaces/tenant.go`, add to `TenantService` interface:
```go
	// GetTenantByExternalID fetches a tenant by external ID (iframe cid)
	GetTenantByExternalID(ctx context.Context, externalID string) (*types.Tenant, error)
```

In `internal/application/service/tenant.go`, implement:
```go
func (s *tenantService) GetTenantByExternalID(ctx context.Context, externalID string) (*types.Tenant, error) {
	return s.tenantRepo.GetByExternalID(ctx, externalID)
}
```
Verify `tenantService` struct has `tenantRepo` field; exact field name may differ — check with `grep -n "type tenantService struct" internal/application/service/tenant.go` and adjust.

- [ ] **Step 3: Add IframeNonceRepository dependency to userService**

In `internal/application/service/user.go`, find the `userService` struct + its constructor `NewUserService` and add:
- Field: `iframeNonceRepo interfaces.IframeNonceRepository`
- Constructor param: same

Example modification (adapt to actual signature):
```go
type userService struct {
	userRepo         interfaces.UserRepository
	tokenRepo        interfaces.AuthTokenRepository
	tenantService    interfaces.TenantService
	iframeNonceRepo  interfaces.IframeNonceRepository   // new
	// ... other fields unchanged
}

func NewUserService(
	userRepo interfaces.UserRepository,
	tokenRepo interfaces.AuthTokenRepository,
	tenantService interfaces.TenantService,
	iframeNonceRepo interfaces.IframeNonceRepository,   // new
	// ... other params unchanged
) interfaces.UserService {
	return &userService{
		userRepo:         userRepo,
		tokenRepo:        tokenRepo,
		tenantService:    tenantService,
		iframeNonceRepo:  iframeNonceRepo,
		// ...
	}
}
```

- [ ] **Step 4: Implement IframeLogin method**

Append to `internal/application/service/user.go`:
```go
var mobileRe = regexp.MustCompile(`^1[3-9][0-9]{9}$`)

// IframeLogin authenticates an HMAC-signed iframe URL request.
func (s *userService) IframeLogin(
	ctx context.Context, req *types.IframeLoginRequest,
) (*types.LoginResponse, error) {
	logger.Info(ctx, "Start iframe login")

	if req.CID == "" || req.Mobile == "" || req.TS == "" || req.Nonce == "" || req.Sig == "" {
		return nil, types.NewIframeLoginError(types.IframeErrParamsMissing, "required parameter missing")
	}
	if !mobileRe.MatchString(req.Mobile) {
		return nil, types.NewIframeLoginError(types.IframeErrMobileInvalid, "invalid mobile format")
	}

	// 1. Locate tenant by cid
	tenant, err := s.tenantService.GetTenantByExternalID(ctx, req.CID)
	if err != nil {
		logger.Errorf(ctx, "iframe_login tenant lookup failed: %v", err)
		return nil, types.NewIframeLoginError(types.IframeErrInternal, "tenant lookup failed")
	}
	if tenant == nil {
		return nil, types.NewIframeLoginError(types.IframeErrTenantNotFound, "tenant not found")
	}
	if tenant.IframeSecret == "" {
		return nil, types.NewIframeLoginError(types.IframeErrNotEnabled, "iframe login not enabled")
	}

	// 2. Verify HMAC
	if !VerifyIframeSignature(tenant.IframeSecret, req.CID, req.Mobile, req.TS, req.Nonce, req.Sig) {
		return nil, types.NewIframeLoginError(types.IframeErrBadSignature, "signature verification failed")
	}

	// 3. Consume nonce
	tsInt, err := strconv.ParseInt(req.TS, 10, 64)
	if err != nil {
		return nil, types.NewIframeLoginError(types.IframeErrBadSignature, "ts not an integer")
	}
	inserted, err := s.iframeNonceRepo.Consume(ctx, &types.IframeNonce{
		TenantID: tenant.ID, Nonce: req.Nonce, TS: tsInt, ConsumedAt: time.Now(),
	})
	if err != nil {
		logger.Errorf(ctx, "iframe_login nonce consume failed: %v", err)
		return nil, types.NewIframeLoginError(types.IframeErrInternal, "nonce persistence failed")
	}
	if !inserted {
		return nil, types.NewIframeLoginError(types.IframeErrReplay, "nonce already consumed")
	}

	// 4. Find or create user
	user, err := s.userRepo.GetUserByTenantAndMobile(ctx, tenant.ID, req.Mobile)
	if err != nil {
		logger.Errorf(ctx, "iframe_login user lookup failed: %v", err)
		return nil, types.NewIframeLoginError(types.IframeErrInternal, "user lookup failed")
	}
	if user == nil {
		user, err = s.createIframeUser(ctx, tenant.ID, req.Mobile)
		if err != nil {
			logger.Errorf(ctx, "iframe_login user creation failed: %v", err)
			return nil, types.NewIframeLoginError(types.IframeErrInternal, "user creation failed")
		}
	} else if !user.IsActive {
		return nil, types.NewIframeLoginError(types.IframeErrUserDisabled, "user disabled")
	}

	// 5. Generate tokens (24h access + 7d refresh, reusing existing mechanism)
	accessToken, refreshToken, err := s.GenerateTokens(ctx, user)
	if err != nil {
		logger.Errorf(ctx, "iframe_login token generation failed: %v", err)
		return nil, types.NewIframeLoginError(types.IframeErrInternal, "token generation failed")
	}

	logger.Infof(ctx, "iframe_login.success tenant_id=%d user_id=%s mobile_suffix=%s",
		tenant.ID, user.ID, maskMobile(req.Mobile))

	return &types.LoginResponse{
		Success:      true,
		User:         user,
		Tenant:       tenant,
		Token:        accessToken,
		RefreshToken: refreshToken,
	}, nil
}

// createIframeUser provisions a placeholder user for an iframe-login flow.
func (s *userService) createIframeUser(
	ctx context.Context, tenantID uint64, mobile string,
) (*types.User, error) {
	randomBytes := make([]byte, 32)
	if _, err := rand.Read(randomBytes); err != nil {
		return nil, err
	}
	passHash, err := bcrypt.GenerateFromPassword(randomBytes, bcrypt.DefaultCost)
	if err != nil {
		return nil, err
	}
	placeholder := fmt.Sprintf("iframe_%d_%s", tenantID, mobile)
	user := &types.User{
		ID:           uuid.New().String(),
		Username:     placeholder,
		Email:        placeholder + "@iframe.invalid",
		PasswordHash: string(passHash),
		Mobile:       mobile,
		TenantID:     tenantID,
		IsActive:     true,
		CreatedAt:    time.Now(),
		UpdatedAt:    time.Now(),
	}
	if err := s.userRepo.CreateUser(ctx, user); err != nil {
		return nil, err
	}
	return user, nil
}

// maskMobile returns only the last 4 digits for logging.
func maskMobile(m string) string {
	if len(m) < 4 {
		return "****"
	}
	return m[len(m)-4:]
}
```

- [ ] **Step 5: Ensure imports**

At top of `internal/application/service/user.go`, verify/add:
```go
"crypto/rand"
"regexp"
"strconv"
```

- [ ] **Step 6: Compile**

```bash
go build ./...
```
Expected: no errors. If DI wiring breaks elsewhere (because `NewUserService` gained a param), the fix happens in Task 16 (container wiring) — compilation of the service package should still pass. If it doesn't, temporarily make `iframeNonceRepo` accept `nil` and defer full wiring to Task 16.

- [ ] **Step 7: Commit**

```bash
git add internal/application/service/user.go
git commit -m "feat(service): implement UserService.IframeLogin (HMAC + nonce + auto-user)"
```

### Task 12: Unit tests for UserService.IframeLogin

**Files:**
- Create: `internal/application/service/user_iframe_test.go`

- [ ] **Step 1: Inspect existing test patterns**

Run:
```bash
ls internal/application/service/*_test.go
grep -l "NewUserService\|fakeTenantService\|mockUserRepo" internal/application/service/*_test.go | head
```
If no user service tests exist, examples may live in repo tests under `repository/tenant_test.go`. Use Go's stdlib testing + simple struct fakes; do not introduce gomock/testify unless already used.

- [ ] **Step 2: Write table-driven test with in-memory fakes**

File `internal/application/service/user_iframe_test.go` — use this as a starting point (adapt imports/fakes to match real userService constructor arity):
```go
package service

import (
	"context"
	"testing"
	"time"

	"github.com/Tencent/WeKnora/internal/types"
)

// --- fakes ---

type fakeTenantSvc struct{ t *types.Tenant }

func (f *fakeTenantSvc) GetTenantByExternalID(_ context.Context, id string) (*types.Tenant, error) {
	if f.t != nil && f.t.ExternalID == id {
		return f.t, nil
	}
	return nil, nil
}
// stub out the rest of TenantService interface with no-ops (compile-satisfying, not called)
// ... ADD stubs per the actual TenantService interface ...

type fakeUserRepo struct {
	byMobile map[string]*types.User
	created  []*types.User
}

func (f *fakeUserRepo) GetUserByTenantAndMobile(_ context.Context, tid uint64, m string) (*types.User, error) {
	return f.byMobile[m], nil
}
func (f *fakeUserRepo) CreateUser(_ context.Context, u *types.User) error {
	f.created = append(f.created, u)
	f.byMobile[u.Mobile] = u
	return nil
}
// ... stub other UserRepository methods ...

type fakeNonceRepo struct{ seen map[string]bool }

func (f *fakeNonceRepo) Consume(_ context.Context, n *types.IframeNonce) (bool, error) {
	k := n.Nonce
	if f.seen[k] {
		return false, nil
	}
	f.seen = map[string]bool{k: true}
	return true, nil
}
func (f *fakeNonceRepo) DeleteOlderThan(_ context.Context, _ int64) (int64, error) { return 0, nil }

// --- test ---

func TestIframeLogin(t *testing.T) {
	tenant := &types.Tenant{ID: 42, ExternalID: "ACME", IframeSecret: "secret", Status: "active"}
	svc := &userService{
		tenantService:   &fakeTenantSvc{t: tenant},
		userRepo:        &fakeUserRepo{byMobile: map[string]*types.User{}},
		iframeNonceRepo: &fakeNonceRepo{seen: map[string]bool{}},
		// tokenRepo: &fakeTokenRepo{},  // add if GenerateTokens touches it
	}
	ctx := context.Background()
	validSig := SignIframeMessage("secret", "ACME", "13812345678", "1000", "n1")
	goodReq := &types.IframeLoginRequest{
		CID: "ACME", Mobile: "13812345678", TS: "1000", Nonce: "n1", Sig: validSig,
	}

	t.Run("first call creates user and returns tokens", func(t *testing.T) {
		resp, err := svc.IframeLogin(ctx, goodReq)
		if err != nil {
			t.Fatalf("unexpected err: %v", err)
		}
		if !resp.Success || resp.User.Mobile != "13812345678" {
			t.Fatalf("bad resp: %+v", resp)
		}
	})

	t.Run("replay of same nonce is rejected", func(t *testing.T) {
		_, err := svc.IframeLogin(ctx, goodReq)
		ilErr, ok := err.(*types.IframeLoginError)
		if !ok || ilErr.Code != types.IframeErrReplay {
			t.Fatalf("expected IFRAME_REPLAY, got %v", err)
		}
	})

	t.Run("bad signature is rejected", func(t *testing.T) {
		bad := *goodReq
		bad.Nonce = "n2"
		bad.Sig = "deadbeef" + validSig[8:]
		_, err := svc.IframeLogin(ctx, &bad)
		ilErr, ok := err.(*types.IframeLoginError)
		if !ok || ilErr.Code != types.IframeErrBadSignature {
			t.Fatalf("expected IFRAME_BAD_SIGNATURE, got %v", err)
		}
	})

	t.Run("unknown cid → tenant not found", func(t *testing.T) {
		bad := *goodReq
		bad.CID = "UNKNOWN"
		bad.Nonce = "n3"
		bad.Sig = SignIframeMessage("secret", "UNKNOWN", goodReq.Mobile, goodReq.TS, bad.Nonce)
		_, err := svc.IframeLogin(ctx, &bad)
		ilErr, ok := err.(*types.IframeLoginError)
		if !ok || ilErr.Code != types.IframeErrTenantNotFound {
			t.Fatalf("expected IFRAME_TENANT_NOT_FOUND, got %v", err)
		}
	})

	_ = time.Now // keep import
}
```

**Note to implementer:** the stub list (`fakeTenantSvc`, `fakeUserRepo`) must satisfy the full interface. Run `go test ./internal/application/service/` — the compiler error will list every method you still need to stub. Add empty stubs returning `nil, nil` or zero values. This is mechanical work (~10–15 min).

- [ ] **Step 3: Run tests → PASS**

```bash
go test ./internal/application/service/ -run TestIframeLogin -v
```
Expected: all subtests PASS.

- [ ] **Step 4: Commit**

```bash
git add internal/application/service/user_iframe_test.go
git commit -m "test(service): IframeLogin happy/replay/badsig/unknown-tenant"
```

---

## Phase 6 · HTTP handler, middleware, router, container

### Task 13: IframeLogin HTTP handler

**Files:**
- Modify: `internal/handler/auth.go`

- [ ] **Step 1: Add handler method**

In `internal/handler/auth.go`, append before the package-local end:
```go
// IframeLogin godoc
// @Summary      iframe 免登
// @Description  通过 HMAC 签名的 URL 参数自动创建/登录用户
// @Tags         认证
// @Accept       json
// @Produce      json
// @Param        request  body      types.IframeLoginRequest  true  "iframe 登录请求"
// @Success      200      {object}  types.LoginResponse
// @Failure      400      {object}  errors.AppError
// @Failure      401      {object}  errors.AppError
// @Failure      403      {object}  errors.AppError
// @Failure      404      {object}  errors.AppError
// @Router       /auth/iframe-login [post]
func (h *AuthHandler) IframeLogin(c *gin.Context) {
	ctx := c.Request.Context()

	var req types.IframeLoginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"success": false,
			"code":    string(types.IframeErrParamsMissing),
			"message": "required parameter missing",
		})
		return
	}

	resp, err := h.userService.IframeLogin(ctx, &req)
	if err != nil {
		if ilErr, ok := err.(*types.IframeLoginError); ok {
			status := iframeErrorStatus(ilErr.Code)
			c.JSON(status, gin.H{
				"success": false,
				"code":    string(ilErr.Code),
				"message": ilErr.Message,
			})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{
			"success": false,
			"code":    string(types.IframeErrInternal),
			"message": "internal error",
		})
		return
	}
	c.JSON(http.StatusOK, resp)
}

func iframeErrorStatus(code types.IframeErrorCode) int {
	switch code {
	case types.IframeErrParamsMissing, types.IframeErrMobileInvalid:
		return http.StatusBadRequest
	case types.IframeErrBadSignature, types.IframeErrReplay:
		return http.StatusUnauthorized
	case types.IframeErrUserDisabled, types.IframeErrNotEnabled:
		return http.StatusForbidden
	case types.IframeErrTenantNotFound:
		return http.StatusNotFound
	default:
		return http.StatusInternalServerError
	}
}
```

- [ ] **Step 2: Compile**

```bash
go build ./...
```

- [ ] **Step 3: Commit**

```bash
git add internal/handler/auth.go
git commit -m "feat(handler): add POST /auth/iframe-login"
```

### Task 14: Middleware whitelist + rate limiter

**Files:**
- Modify: `internal/middleware/auth.go`
- Create: `internal/middleware/iframe_ratelimit.go`

- [ ] **Step 1: Whitelist the endpoint**

Find the no-auth path list (around line 20-29 in `internal/middleware/auth.go`):
```bash
grep -n "iframe-login\|auth/login\|auth/register" internal/middleware/auth.go
```
Add `/api/v1/auth/iframe-login` to the existing slice of public paths. Follow the style of adjacent entries.

- [ ] **Step 2: Create IP-scoped rate limiter for bad-signature events**

File `internal/middleware/iframe_ratelimit.go`:
```go
package middleware

import (
	"sync"
	"time"

	"golang.org/x/time/rate"
)

// iframeBadSigLimiter limits same-IP BAD_SIGNATURE hits (5 per minute, burst 5).
// Used manually by the handler AFTER detecting IFRAME_BAD_SIGNATURE; not a Gin middleware.
type iframeBadSigLimiter struct {
	mu       sync.Mutex
	limiters map[string]*ipLim
}

type ipLim struct {
	l   *rate.Limiter
	hit time.Time
}

var globalIframeBadSigLimiter = &iframeBadSigLimiter{limiters: map[string]*ipLim{}}

// AllowBadSignature returns true when the IP is under limit; false when throttled.
func AllowBadSignature(ip string) bool {
	return globalIframeBadSigLimiter.allow(ip)
}

func (l *iframeBadSigLimiter) allow(ip string) bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	entry, ok := l.limiters[ip]
	if !ok {
		entry = &ipLim{l: rate.NewLimiter(rate.Every(12*time.Second), 5)}
		l.limiters[ip] = entry
	}
	entry.hit = time.Now()
	return entry.l.Allow()
}
```

- [ ] **Step 3: Wire rate limiter into handler**

Edit `internal/handler/auth.go` `IframeLogin`:
after calling `userService.IframeLogin`, if the returned error is `IframeErrBadSignature`, consult the limiter — and if the limiter says no, return HTTP 429:
```go
if ilErr, ok := err.(*types.IframeLoginError); ok {
    if ilErr.Code == types.IframeErrBadSignature && !middleware.AllowBadSignature(c.ClientIP()) {
        c.JSON(http.StatusTooManyRequests, gin.H{
            "success": false,
            "code":    string(types.IframeErrBadSignature),
            "message": "too many attempts",
        })
        return
    }
    // ... existing error formatting
}
```

Add `"github.com/Tencent/WeKnora/internal/middleware"` import.

- [ ] **Step 4: Compile**

```bash
go build ./...
```

- [ ] **Step 5: Commit**

```bash
git add internal/middleware/auth.go internal/middleware/iframe_ratelimit.go internal/handler/auth.go
git commit -m "feat(middleware): whitelist iframe-login + per-IP bad-sig rate limit"
```

### Task 15: frame-ancestors CSP middleware

**Files:**
- Create: `internal/middleware/frame_ancestors.go`
- Modify: `internal/router/router.go`

- [ ] **Step 1: Create middleware**

File `internal/middleware/frame_ancestors.go`:
```go
package middleware

import (
	"os"
	"strings"

	"github.com/gin-gonic/gin"
)

// FrameAncestors sets Content-Security-Policy: frame-ancestors <value> when
// WEKNORA_FRAME_ANCESTORS env is non-empty. Empty env → header not set (any origin can embed).
func FrameAncestors() gin.HandlerFunc {
	raw := strings.TrimSpace(os.Getenv("WEKNORA_FRAME_ANCESTORS"))
	if raw == "" {
		return func(c *gin.Context) { c.Next() }
	}
	header := "frame-ancestors " + raw
	return func(c *gin.Context) {
		c.Writer.Header().Set("Content-Security-Policy", header)
		c.Next()
	}
}
```

- [ ] **Step 2: Mount middleware**

In `internal/router/router.go`, after the CORS middleware setup, add:
```go
r.Use(middleware.FrameAncestors())
```
Ensure `"github.com/Tencent/WeKnora/internal/middleware"` is already imported (it is, based on the existing auth middleware usage).

- [ ] **Step 3: Mount the iframe-login route**

In `internal/router/router.go`, locate the auth route group (search for `/auth/login` or `AuthHandler.Login`). Add:
```go
authGroup.POST("/iframe-login", params.AuthHandler.IframeLogin)
```
Place it next to the other unauthenticated auth routes (`/login`, `/register`).

- [ ] **Step 4: Compile + smoke boot**

```bash
go build ./...
```

- [ ] **Step 5: Commit**

```bash
git add internal/middleware/frame_ancestors.go internal/router/router.go
git commit -m "feat(router): mount iframe-login + frame-ancestors CSP middleware"
```

### Task 16: Wire IframeNonceRepository in DI container

**Files:**
- Modify: `internal/container/container.go`

- [ ] **Step 1: Locate NewUserService registration**

```bash
grep -n "NewUserService\|NewIframeNonceRepository\|repository.NewUserRepository" internal/container/container.go
```
Find the `c.Provide(repository.NewUserRepository)` line and adjacent service registrations.

- [ ] **Step 2: Register the new repository**

Near the other repository `c.Provide(...)` lines, add:
```go
c.Provide(repository.NewIframeNonceRepository)
```

- [ ] **Step 3: Verify NewUserService provider compiles**

Since `NewUserService` now takes `IframeNonceRepository`, dig will inject it automatically based on the interface. No explicit wiring change needed beyond Step 2.

Run:
```bash
go build ./...
```
Expected: no errors.

- [ ] **Step 4: Start server and verify no DI panic**

Assumes `make dev-start` infra is running:
```bash
make dev-app
```
Watch logs: should reach `Server is running at :8080` without dig container resolution errors. Ctrl+C to stop.

- [ ] **Step 5: Commit**

```bash
git add internal/container/container.go
git commit -m "feat(container): register IframeNonceRepository provider"
```

---

## Phase 7 · weknora-admin CLI

### Task 17: weknora-admin binary with iframe subcommands

**Files:**
- Create: `cmd/weknora-admin/main.go`
- Create: `cmd/weknora-admin/iframe.go`

- [ ] **Step 1: Create main entry**

File `cmd/weknora-admin/main.go`:
```go
// Package main is the entry for weknora-admin — a small operator CLI for
// server-side admin actions (iframe tenant provisioning, secret rotation, etc.).
package main

import (
	"context"
	"fmt"
	"os"

	"github.com/Tencent/WeKnora/internal/config"
	"github.com/Tencent/WeKnora/internal/container"
	"github.com/Tencent/WeKnora/internal/runtime"
)

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	switch os.Args[1] {
	case "iframe":
		if len(os.Args) < 3 {
			usage()
			os.Exit(2)
		}
		runIframe(os.Args[2], os.Args[3:])
	default:
		usage()
		os.Exit(2)
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, `weknora-admin — operator CLI

Usage:
  weknora-admin iframe provision --cid <cid> --name <display-name>
  weknora-admin iframe rotate    --cid <cid>
  weknora-admin iframe revoke    --cid <cid>`)
}

// buildContainer wires the minimal services needed for admin actions.
func buildContainer() (*container.Container, func()) {
	c := container.BuildContainer(runtime.GetContainer())
	cleanup := func() {
		_ = c.Invoke(func(cfg *config.Config) error { _ = cfg; return nil })
	}
	_ = context.Background()
	return c, cleanup
}
```

Note on `container.Container` return type: the existing `BuildContainer` returns a `*dig.Container`. Adjust the import/return type to match. Run:
```bash
grep -n "func BuildContainer" internal/container/container.go
```

- [ ] **Step 2: Implement iframe subcommands**

File `cmd/weknora-admin/iframe.go`:
```go
package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"flag"
	"fmt"
	"os"
	"time"

	"go.uber.org/dig"

	"github.com/Tencent/WeKnora/internal/application/repository"
	"github.com/Tencent/WeKnora/internal/application/service"
	"github.com/Tencent/WeKnora/internal/container"
	"github.com/Tencent/WeKnora/internal/runtime"
	"github.com/Tencent/WeKnora/internal/types"
	"github.com/Tencent/WeKnora/internal/types/interfaces"
)

func runIframe(sub string, args []string) {
	fs := flag.NewFlagSet("iframe "+sub, flag.ExitOnError)
	cid := fs.String("cid", "", "tenant external id (required)")
	name := fs.String("name", "", "tenant display name (provision only)")
	_ = fs.Parse(args)
	if *cid == "" {
		fmt.Fprintln(os.Stderr, "--cid is required")
		os.Exit(2)
	}

	c := container.BuildContainer(runtime.GetContainer())
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	err := c.Invoke(func(
		tenantRepo interfaces.TenantRepository,
	) error {
		switch sub {
		case "provision":
			if *name == "" {
				return fmt.Errorf("--name is required for provision")
			}
			return provision(ctx, tenantRepo, *cid, *name)
		case "rotate":
			return rotate(ctx, tenantRepo, *cid)
		case "revoke":
			return revoke(ctx, tenantRepo, *cid)
		default:
			return fmt.Errorf("unknown subcommand: %s", sub)
		}
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}
}

func generateSecret() (string, error) {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return hex.EncodeToString(b), nil
}

func provision(ctx context.Context, repo interfaces.TenantRepository, cid, name string) error {
	existing, err := repo.GetByExternalID(ctx, cid)
	if err != nil {
		return fmt.Errorf("lookup failed: %w", err)
	}
	if existing != nil {
		return fmt.Errorf("tenant with cid=%s already exists (id=%d); use rotate to refresh secret", cid, existing.ID)
	}
	secret, err := generateSecret()
	if err != nil {
		return err
	}
	t := &types.Tenant{
		Name:         name,
		Description:  "iframe-provisioned",
		Status:       "active",
		Business:     "iframe",
		ExternalID:   cid,
		IframeSecret: secret,
	}
	if err := repo.CreateTenant(ctx, t); err != nil {
		return fmt.Errorf("create failed: %w", err)
	}
	fmt.Printf("Tenant created: id=%d, external_id=%s\n", t.ID, cid)
	fmt.Println("iframe_secret (SAVE THIS, shown only once):")
	fmt.Println("────────────────────────────────────────")
	fmt.Println(secret)
	fmt.Println("────────────────────────────────────────")
	return nil
}

func rotate(ctx context.Context, repo interfaces.TenantRepository, cid string) error {
	t, err := repo.GetByExternalID(ctx, cid)
	if err != nil {
		return err
	}
	if t == nil {
		return fmt.Errorf("cid=%s not found; provision first", cid)
	}
	secret, err := generateSecret()
	if err != nil {
		return err
	}
	if err := repo.UpdateIframeSecret(ctx, t.ID, secret); err != nil {
		return err
	}
	fmt.Printf("Secret rotated for cid=%s (tenant_id=%d)\n", cid, t.ID)
	fmt.Println("new iframe_secret (SAVE THIS, shown only once):")
	fmt.Println("────────────────────────────────────────")
	fmt.Println(secret)
	fmt.Println("────────────────────────────────────────")
	return nil
}

func revoke(ctx context.Context, repo interfaces.TenantRepository, cid string) error {
	t, err := repo.GetByExternalID(ctx, cid)
	if err != nil {
		return err
	}
	if t == nil {
		return fmt.Errorf("cid=%s not found", cid)
	}
	if err := repo.UpdateIframeSecret(ctx, t.ID, ""); err != nil {
		return err
	}
	fmt.Printf("iframe access revoked for cid=%s\n", cid)
	return nil
}

// unused imports guard
var _ = dig.Version
var _ = service.SignIframeMessage
var _ = repository.NewIframeNonceRepository
```

Notes:
- `TenantRepository.CreateTenant` signature may differ — verify with `grep -n "CreateTenant\|Create(ctx.*tenant" internal/application/repository/tenant.go`.
- If `TenantService.CreateTenant` is the only creation path (adds RetrieverEngines defaults etc.), invoke `interfaces.TenantService` instead and use its `CreateTenant`, then a follow-up `UpdateIframeSecret` call (secret must be post-create so the row exists).

- [ ] **Step 3: Add Makefile target**

In `Makefile`, near the `build-prod` section add:
```makefile
build-admin:
	CGO_ENABLED=1 go build -o weknora-admin ./cmd/weknora-admin
```
Update the `.PHONY:` line at top to include `build-admin`.

- [ ] **Step 4: Build + verify binary**

```bash
make build-admin
./weknora-admin   # no args → usage + exit 2
./weknora-admin iframe provision --cid TEST1 --name "Test Org"
```
Expected: help text on no-args, secret printed on provision.

- [ ] **Step 5: Verify DB state**

```bash
docker exec -it weknora-postgres psql -U postgres -d weknora -c \
  "SELECT id, name, external_id, (iframe_secret IS NOT NULL) AS has_secret FROM tenants WHERE external_id='TEST1';"
```
Expected: row with `has_secret = t` (true).

- [ ] **Step 6: Test rotate and revoke**

```bash
./weknora-admin iframe rotate --cid TEST1
./weknora-admin iframe revoke --cid TEST1
docker exec -it weknora-postgres psql -U postgres -d weknora -c \
  "SELECT external_id, (iframe_secret IS NOT NULL OR iframe_secret = '') FROM tenants WHERE external_id='TEST1';"
```

- [ ] **Step 7: Commit**

```bash
git add cmd/weknora-admin/ Makefile
git commit -m "feat(cli): add weknora-admin iframe provision/rotate/revoke"
```

---

## Phase 8 · End-to-end backend smoke test

### Task 18: curl-based E2E smoke test

**Files:**
- None (scratch work)

- [ ] **Step 1: Provision a fresh cid**

```bash
./weknora-admin iframe provision --cid E2E1 --name "E2E Test" | tee /tmp/e2e.out
SECRET=$(grep -A1 '────' /tmp/e2e.out | grep -v '────' | head -1 | tr -d '[:space:]')
echo "SECRET=$SECRET"
```

- [ ] **Step 2: Generate signed URL parameters in bash**

```bash
CID=E2E1
MOBILE=13812345678
TS=$(date +%s)
NONCE=$(openssl rand -hex 16)
MSG="cid=$CID&mobile=$MOBILE&nonce=$NONCE&ts=$TS"
SIG=$(printf '%s' "$MSG" | openssl dgst -sha256 -hmac "$SECRET" -hex | awk '{print $2}')
echo "URL: /iframe-login?cid=$CID&mobile=$MOBILE&ts=$TS&nonce=$NONCE&sig=$SIG"
```

- [ ] **Step 3: POST to iframe-login endpoint**

```bash
curl -sS -X POST http://localhost:8080/api/v1/auth/iframe-login \
  -H "Content-Type: application/json" \
  -d "{\"cid\":\"$CID\",\"mobile\":\"$MOBILE\",\"ts\":\"$TS\",\"nonce\":\"$NONCE\",\"sig\":\"$SIG\"}" | jq
```
Expected: JSON with `success: true`, `user.mobile=13812345678`, `token` non-empty.

- [ ] **Step 4: Replay same payload → expect 401 IFRAME_REPLAY**

```bash
curl -sS -o /dev/stdout -w "\nHTTP %{http_code}\n" -X POST http://localhost:8080/api/v1/auth/iframe-login \
  -H "Content-Type: application/json" \
  -d "{\"cid\":\"$CID\",\"mobile\":\"$MOBILE\",\"ts\":\"$TS\",\"nonce\":\"$NONCE\",\"sig\":\"$SIG\"}"
```
Expected: `"code":"IFRAME_REPLAY"`, HTTP 401.

- [ ] **Step 5: Tamper sig → expect 401 IFRAME_BAD_SIGNATURE**

```bash
NONCE2=$(openssl rand -hex 16)
BADSIG="deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
curl -sS -o /dev/stdout -w "\nHTTP %{http_code}\n" -X POST http://localhost:8080/api/v1/auth/iframe-login \
  -H "Content-Type: application/json" \
  -d "{\"cid\":\"$CID\",\"mobile\":\"$MOBILE\",\"ts\":\"$TS\",\"nonce\":\"$NONCE2\",\"sig\":\"$BADSIG\"}"
```
Expected: `"code":"IFRAME_BAD_SIGNATURE"`, HTTP 401.

- [ ] **Step 6: Unknown cid → 404 IFRAME_TENANT_NOT_FOUND**

```bash
curl -sS -o /dev/stdout -w "\nHTTP %{http_code}\n" -X POST http://localhost:8080/api/v1/auth/iframe-login \
  -H "Content-Type: application/json" \
  -d '{"cid":"NOPE","mobile":"13812345678","ts":"1","nonce":"x","sig":"'$BADSIG'"}'
```
Expected: HTTP 404, `IFRAME_TENANT_NOT_FOUND`.

- [ ] **Step 7: Use returned token on a protected endpoint**

```bash
TOKEN=$(curl -sS -X POST http://localhost:8080/api/v1/auth/iframe-login \
  -H "Content-Type: application/json" \
  -d "{\"cid\":\"$CID\",\"mobile\":\"$MOBILE\",\"ts\":\"$(date +%s)\",\"nonce\":\"$(openssl rand -hex 16)\",\"sig\":\"$(python3 -c "import hmac,hashlib;s='$SECRET';m=f'cid=$CID&mobile=$MOBILE&nonce=freshnonce&ts=freshts';print(hmac.new(s.encode(),m.encode(),hashlib.sha256).hexdigest())")\"}" | jq -r .token)
# Use token
curl -sS -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/v1/tenants/current | jq
```
(This last step is optional — goal is just to verify the JWT works. Skip if token format requires additional tenant header.)

No commit needed; this is a one-shot verification.

---

## Phase 9 · Frontend embedded mode

### Task 19: Embedded store + composable

**Files:**
- Create: `frontend/src/stores/embedded.ts`
- Create: `frontend/src/composables/useEmbedded.ts`

- [ ] **Step 1: Create Pinia store**

File `frontend/src/stores/embedded.ts`:
```ts
import { defineStore } from 'pinia'

const STORAGE_KEY = 'weknora_embedded'

export const useEmbeddedStore = defineStore('embedded', {
  state: () => ({
    embedded: sessionStorage.getItem(STORAGE_KEY) === '1',
  }),
  actions: {
    enable() {
      this.embedded = true
      sessionStorage.setItem(STORAGE_KEY, '1')
    },
    disable() {
      this.embedded = false
      sessionStorage.removeItem(STORAGE_KEY)
    },
  },
})
```

- [ ] **Step 2: Create composable**

File `frontend/src/composables/useEmbedded.ts`:
```ts
import { storeToRefs } from 'pinia'
import { useEmbeddedStore } from '@/stores/embedded'

// useEmbedded exposes a reactive `embedded` boolean for hiding brand elements
// when WeKnora is embedded in a parent system via iframe.
export function useEmbedded() {
  const store = useEmbeddedStore()
  const { embedded } = storeToRefs(store)
  return { embedded }
}
```

- [ ] **Step 3: Verify TS builds**

```bash
cd frontend && npx vue-tsc --noEmit && cd ..
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/embedded.ts frontend/src/composables/useEmbedded.ts
git commit -m "feat(frontend): add embedded store + useEmbedded composable"
```

### Task 20: Frontend API client method

**Files:**
- Modify: `frontend/src/api/auth.ts`

- [ ] **Step 1: Locate existing auth api patterns**

```bash
grep -n "login\|register\|refresh" frontend/src/api/auth.ts | head
```
Follow existing axios/fetch usage.

- [ ] **Step 2: Add iframeLogin**

Append to `frontend/src/api/auth.ts`:
```ts
export interface IframeLoginParams {
  cid: string
  mobile: string
  ts: string
  nonce: string
  sig: string
}

export interface IframeLoginErrorCode {
  code:
    | 'IFRAME_PARAMS_MISSING'
    | 'IFRAME_MOBILE_INVALID'
    | 'IFRAME_BAD_SIGNATURE'
    | 'IFRAME_REPLAY'
    | 'IFRAME_USER_DISABLED'
    | 'IFRAME_NOT_ENABLED'
    | 'IFRAME_TENANT_NOT_FOUND'
    | 'IFRAME_INTERNAL'
  message: string
}

export async function iframeLogin(params: IframeLoginParams) {
  // Reuse the project's axios instance; adapt path/request-shape to match existing auth calls.
  const { data } = await http.post('/api/v1/auth/iframe-login', params)
  return data as {
    success: boolean
    user: any
    tenant: any
    token: string
    refresh_token: string
  }
}
```
(Use the file's existing `http`/`axios` import. If this file exports a single default object, append the function inside that object instead.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/auth.ts
git commit -m "feat(frontend): iframeLogin api client"
```

### Task 21: IframeLogin.vue page

**Files:**
- Create: `frontend/src/views/auth/IframeLogin.vue`

- [ ] **Step 1: Create component**

File `frontend/src/views/auth/IframeLogin.vue`:
```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useEmbeddedStore } from '@/stores/embedded'
import { iframeLogin } from '@/api/auth'
import { useI18n } from 'vue-i18n'

const route = useRoute()
const router = useRouter()
const embedded = useEmbeddedStore()
const { locale } = useI18n()

const loading = ref(true)
const errorMsg = ref<string>('')

const errorMap: Record<string, string> = {
  IFRAME_PARAMS_MISSING: '链接参数不完整，请联系系统管理员',
  IFRAME_MOBILE_INVALID: '手机号格式非法',
  IFRAME_BAD_SIGNATURE: '鉴权失败，请联系系统管理员',
  IFRAME_REPLAY: '请求重复，请刷新页面后重试',
  IFRAME_USER_DISABLED: '账号已被禁用',
  IFRAME_NOT_ENABLED: '该组织未启用 iframe 登录',
  IFRAME_TENANT_NOT_FOUND: '组织未开通，请联系系统管理员',
  IFRAME_INTERNAL: '服务暂时不可用，请稍后重试',
}

function pickError(e: any): string {
  const code = e?.response?.data?.code
  if (code && errorMap[code]) return errorMap[code]
  return '登录失败，请刷新页面重试'
}

onMounted(async () => {
  embedded.enable()
  locale.value = 'zh-CN'

  const q = route.query
  const params = {
    cid: String(q.cid ?? ''),
    mobile: String(q.mobile ?? ''),
    ts: String(q.ts ?? ''),
    nonce: String(q.nonce ?? ''),
    sig: String(q.sig ?? ''),
  }
  if (!params.cid || !params.mobile || !params.ts || !params.nonce || !params.sig) {
    errorMsg.value = errorMap.IFRAME_PARAMS_MISSING
    loading.value = false
    return
  }

  try {
    const resp = await iframeLogin(params)
    // Persist auth (use existing token storage convention — adapt if different)
    localStorage.setItem('access_token', resp.token)
    localStorage.setItem('refresh_token', resp.refresh_token)
    router.replace('/platform/knowledge-bases')
  } catch (e: any) {
    errorMsg.value = pickError(e)
    loading.value = false
  }
})
</script>

<template>
  <div class="iframe-login-root">
    <div v-if="loading" class="loading">
      <div class="spinner" />
      <div class="hint">正在登录…</div>
    </div>
    <div v-else class="error">
      <div class="msg">{{ errorMsg }}</div>
    </div>
  </div>
</template>

<style scoped>
.iframe-login-root {
  display: flex; align-items: center; justify-content: center;
  height: 100vh; background: #f5f7fa;
}
.spinner {
  width: 48px; height: 48px;
  border: 4px solid #ddd; border-top-color: #4e6b99; border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto;
}
.hint, .msg { margin-top: 16px; color: #666; text-align: center; }
.msg { color: #d54; font-weight: 500; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
```

**Adapt:**
- Verify the exact localStorage keys used by the app (search `grep -rn "access_token\|setItem.*token" frontend/src` to confirm).
- The redirect target `/platform/knowledge-bases` is from the design doc; confirm it matches an existing route.

- [ ] **Step 2: Build frontend**

```bash
cd frontend && npm run build && cd ..
```
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/auth/IframeLogin.vue
git commit -m "feat(frontend): add IframeLogin.vue page"
```

### Task 22: Router + guard

**Files:**
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: Register route**

In the routes array:
```ts
{
  path: '/iframe-login',
  name: 'iframe-login',
  component: () => import('@/views/auth/IframeLogin.vue'),
  meta: { requiresAuth: false },
},
```

- [ ] **Step 2: Update beforeEach to block /login when embedded**

Inside `router.beforeEach(...)`, after retrieving the embedded store:
```ts
import { useEmbeddedStore } from '@/stores/embedded'
// ...
const embedded = useEmbeddedStore()
if (embedded.embedded && to.path === '/login') {
  // Prevent standalone login UI from appearing inside an iframe session
  return next({ path: '/iframe-login', query: to.query })
}
```

And ensure the existing "already logged in → redirect to /platform..." check does NOT apply to `/iframe-login`:
```ts
if (isLoggedIn && to.path === '/iframe-login') {
  return next() // allow fresh iframe-login flow to override token
}
```

- [ ] **Step 3: Build frontend**

```bash
cd frontend && npm run build && cd ..
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/router/index.ts
git commit -m "feat(frontend): route /iframe-login + embedded guard for /login"
```

### Task 23: Hide logos/external links on Login.vue

**Files:**
- Modify: `frontend/src/views/auth/Login.vue`

- [ ] **Step 1: Inspect current structure**

```bash
sed -n '85,145p' frontend/src/views/auth/Login.vue
```
Identify the top-left GitHub logo block (~line 96-98) and top-right external links + language switcher block (~line 102-141).

- [ ] **Step 2: Import composable**

In `<script setup>` block, add:
```ts
import { useEmbedded } from '@/composables/useEmbedded'
const { embedded } = useEmbedded()
```

- [ ] **Step 3: Wrap brand blocks with v-if**

Wrap the top-left logo container:
```html
<div v-if="!embedded" class="...existing-classes...">
  <!-- existing GitHub logo markup -->
</div>
```

Wrap the top-right links + language switcher container similarly:
```html
<div v-if="!embedded" class="...existing-classes...">
  <!-- existing external links + language switcher -->
</div>
```

- [ ] **Step 4: Verify standalone mode still renders brand**

```bash
cd frontend && npm run dev &
# open http://localhost:5173/login in browser
# Expected: logo + links visible
```
Stop dev server.

- [ ] **Step 5: Verify embedded mode hides brand**

Open `http://localhost:5173/login?embedded=1` after manually running `sessionStorage.setItem('weknora_embedded','1')` in devtools console, refresh.
Expected: logo + links hidden.

(Full iframe-login flow tested in Task 26.)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/auth/Login.vue
git commit -m "feat(frontend): hide Login.vue brand elements when embedded"
```

### Task 24: Hide brand in main layout & settings/about

**Files:**
- Modify: `frontend/src/App.vue`
- Modify: (layout / sidebar / topbar components — to be located)
- Modify: (settings "about" component — to be located)

- [ ] **Step 1: Locate brand-bearing components**

```bash
grep -rn "github.com/Tencent/WeKnora\|WeKnora' *}" frontend/src/ | head -30
grep -rn 'logo' frontend/src/components/ frontend/src/views/ | head -30
grep -rn "<img" frontend/src/components/ | head -20
```

List each hit in the commit message so the reviewer can audit coverage.

- [ ] **Step 2: For each hit, import and apply `v-if="!embedded"`**

Pattern per file:
```ts
// <script setup> additions
import { useEmbedded } from '@/composables/useEmbedded'
const { embedded } = useEmbedded()
```
```html
<!-- template: wrap brand element -->
<div v-if="!embedded">
  <!-- existing logo/link markup -->
</div>
```

For inline brand text in attributes (e.g., `<h1>WeKnora</h1>` in a fixed sidebar header), wrap the parent or replace with `v-if="!embedded"` on the heading itself.

- [ ] **Step 3: Build frontend**

```bash
cd frontend && npm run build && cd ..
```

- [ ] **Step 4: Manual check**

```bash
cd frontend && npm run dev
```
- Open `http://localhost:5173/iframe-login?cid=E2E1&mobile=13812345678&ts=...` (use values from Task 18)
- Expected: after redirect to `/platform/knowledge-bases`, NO logo, NO GitHub link, NO language switcher, NO "关于/about" external links anywhere.
- Open `http://localhost:5173/platform/knowledge-bases` directly (no embedded) with a regular login session.
- Expected: standard UI with logo/links.

Stop dev server.

- [ ] **Step 5: Commit (split per file group if touching many)**

```bash
git add frontend/src/App.vue frontend/src/components/... frontend/src/views/...
git commit -m "feat(frontend): hide brand elements across layout when embedded"
```

---

## Phase 10 · Docs & final verification

### Task 25: External integration documentation

**Files:**
- Create: `docs/iframe-integration.md`

- [ ] **Step 1: Write doc**

File `docs/iframe-integration.md`:
```markdown
# WeKnora iframe 嵌入接入指南

本文档面向自维护的外部业务系统，说明如何将 WeKnora 作为 iframe 嵌入并免登。

## 1. 前置步骤（运维）

在 WeKnora 部署机上预先为每个组织创建 tenant 并生成 iframe secret：

\`\`\`bash
make build-admin
./weknora-admin iframe provision --cid ACME-2024 --name "ACME 公司"
# 输出（仅显示一次，请妥善保存）:
#   iframe_secret (SAVE THIS, shown only once):
#   ────────────────────────────────────────
#   <64-char hex secret>
#   ────────────────────────────────────────
\`\`\`

轮换或吊销：
\`\`\`bash
./weknora-admin iframe rotate --cid ACME-2024
./weknora-admin iframe revoke --cid ACME-2024
\`\`\`

## 2. 签名算法

URL 格式：
\`\`\`
/iframe-login?cid=<cid>&mobile=<mobile>&ts=<unix>&nonce=<random>&sig=<hex>
\`\`\`

签名：
- 字段按字典序拼接：`cid={cid}&mobile={mobile}&nonce={nonce}&ts={ts}`
- `sig = hex(HMAC-SHA256(secret, message))`
- 值**不做** URL 编码后再签名

## 3. Python 示例

\`\`\`python
import hmac, hashlib, time, secrets

def build_iframe_url(base, cid, mobile, secret):
    ts = str(int(time.time()))
    nonce = secrets.token_hex(16)
    msg = f"cid={cid}&mobile={mobile}&nonce={nonce}&ts={ts}"
    sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return (f"{base}/iframe-login?cid={cid}&mobile={mobile}"
            f"&ts={ts}&nonce={nonce}&sig={sig}")

url = build_iframe_url("https://weknora.example.com", "ACME-2024", "13812345678", SECRET)
# 在外部系统中：<iframe :src="url" ...>
\`\`\`

## 4. Node.js 示例

\`\`\`js
const crypto = require('crypto');
function buildIframeUrl(base, cid, mobile, secret) {
  const ts = Math.floor(Date.now() / 1000).toString();
  const nonce = crypto.randomBytes(16).toString('hex');
  const msg = `cid=${cid}&mobile=${mobile}&nonce=${nonce}&ts=${ts}`;
  const sig = crypto.createHmac('sha256', secret).update(msg).digest('hex');
  return `${base}/iframe-login?cid=${cid}&mobile=${mobile}&ts=${ts}&nonce=${nonce}&sig=${sig}`;
}
\`\`\`

## 5. 错误码

| HTTP | code | 处理建议 |
|---|---|---|
| 400 | IFRAME_PARAMS_MISSING | 检查 URL 参数是否齐全 |
| 400 | IFRAME_MOBILE_INVALID | 手机号须为中国大陆 11 位，^1[3-9][0-9]{9}$ |
| 401 | IFRAME_BAD_SIGNATURE | 检查 secret 是否正确 |
| 401 | IFRAME_REPLAY | 同一 URL 不可复用，父系统应为每次 iframe 渲染重新生成 |
| 403 | IFRAME_USER_DISABLED | 联系 WeKnora 管理员启用用户 |
| 403 | IFRAME_NOT_ENABLED | 联系管理员执行 `provision` |
| 404 | IFRAME_TENANT_NOT_FOUND | cid 未 provision |
| 429 | （BAD_SIGNATURE 频率过高） | 60 秒后重试 |

## 6. 安全注意事项

- secret 长度固定 64 hex 字符（32 字节），由 WeKnora 生成；严禁在前端或浏览器可见的代码中保存
- 父系统应**每次渲染 iframe 时生成新的 nonce**；同一 URL 不支持复用
- 怀疑 secret 泄漏时立即 `weknora-admin iframe rotate --cid X`
- 如需限制允许嵌入的父域名，设置环境变量：
  \`WEKNORA_FRAME_ANCESTORS="https://parent.example.com https://another.example.com"\`
  （空值表示允许任意域嵌入，适合内网）

## 7. 会话管理

- WeKnora 签发 24h access token + 7d refresh token（存 localStorage）
- 父系统自身会话过期时负责导走用户；WeKnora 不主动校验父系统状态
- 用户关闭 iframe tab 后 `embedded` 标志随 sessionStorage 自动清除
```

- [ ] **Step 2: Update CHANGELOG.md if project uses it**

```bash
grep -l "v0.3" CHANGELOG.md && echo "CHANGELOG exists — add entry under Unreleased"
```
Add entry:
```markdown
## Unreleased
- feat: iframe 嵌入免登（HMAC 签名 URL，cid + mobile 自动创建/登录）
- feat: embedded 模式下隐藏 logo/外链/语言切换器
- feat: weknora-admin CLI（iframe provision/rotate/revoke）
```

- [ ] **Step 3: Regenerate Swagger**

```bash
make install-swagger  # if not installed
make docs
```

- [ ] **Step 4: Commit**

```bash
git add docs/iframe-integration.md docs/swagger.json docs/swagger.yaml CHANGELOG.md
git commit -m "docs: iframe integration guide + swagger + changelog"
```

### Task 26: Full end-to-end manual acceptance

**Files:**
- None (verification only)

- [ ] **Step 1: Fresh infra + fresh migrations**

```bash
make dev-stop
docker volume rm weknora_postgres-data || true
make dev-start
sleep 30
make migrate-up
```

- [ ] **Step 2: Build everything**

```bash
make build-admin
make dev-app &  # backend
cd frontend && npm run dev &  # frontend
```

- [ ] **Step 3: Provision tenant + generate URL**

```bash
./weknora-admin iframe provision --cid MANUAL --name "Manual Test"
# save SECRET
python3 - <<PY
import hmac,hashlib,time,secrets
s = "<PASTE-SECRET>"
cid,mob = "MANUAL","13912345678"
ts = str(int(time.time()))
nonce = secrets.token_hex(16)
msg = f"cid={cid}&mobile={mob}&nonce={nonce}&ts={ts}"
sig = hmac.new(s.encode(),msg.encode(),hashlib.sha256).hexdigest()
print(f"http://localhost:5173/iframe-login?cid={cid}&mobile={mob}&ts={ts}&nonce={nonce}&sig={sig}")
PY
```

- [ ] **Step 4: Visit URL in browser**

- Expected: spinner briefly → redirect to `/platform/knowledge-bases`
- Expected: **NO** logo, **NO** GitHub link, **NO** language switcher visible anywhere
- Open devtools → `sessionStorage.weknora_embedded === '1'`
- Open devtools → `localStorage.access_token` non-empty

- [ ] **Step 5: Re-visit the SAME URL → expect error page in iframe**

- Expected: `IFRAME_REPLAY` error message shown

- [ ] **Step 6: Open `/login` in a different browser/incognito**

- Expected: logo + external links **visible** (standalone mode unaffected)

- [ ] **Step 7: Rotate secret, old URL fails**

```bash
./weknora-admin iframe rotate --cid MANUAL
```
Visit old URL → expect `IFRAME_BAD_SIGNATURE`.

- [ ] **Step 8: Revoke, new URL fails with NOT_ENABLED**

```bash
./weknora-admin iframe revoke --cid MANUAL
```
Generate new URL with old (revoked) secret → expect `IFRAME_NOT_ENABLED`.

No commit. Stop background processes.

---

## Coverage cross-check against spec

- [x] R1 iframe 免登 → Tasks 1–16, 18
- [x] R2 embedded 模式 → Tasks 19–24
- [x] `weknora-admin` CLI → Task 17
- [x] 数据模型变更 → Tasks 1–5
- [x] HMAC 协议 → Tasks 9, 11, 25
- [x] 错误码契约 → Tasks 10, 13, 25
- [x] 日志/限流 → Tasks 11, 14
- [x] frame-ancestors CSP → Task 15
- [x] 前端品牌清理 → Tasks 23, 24
- [x] 测试策略 → Tasks 9, 12, 18, 26
- [x] 文档 → Task 25
