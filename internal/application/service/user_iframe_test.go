package service

import (
	"context"
	"testing"

	"github.com/Tencent/WeKnora/internal/application/repository"
	"github.com/Tencent/WeKnora/internal/types"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

const iframeTestAESKey = "01234567890123456789012345678901" // 32 bytes

// setupIframeTestDB creates an in-memory SQLite DB with the schema needed by IframeLogin tests.
func setupIframeTestDB(t *testing.T) *gorm.DB {
	t.Helper()
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("failed to open sqlite: %v", err)
	}
	if err := db.AutoMigrate(
		&types.Tenant{},
		&types.User{},
		&types.IframeNonce{},
		&types.AuthToken{},
	); err != nil {
		t.Fatalf("automigrate failed: %v", err)
	}
	return db
}

// newIframeTestService wires a userService with real repos but a fresh in-memory DB.
func newIframeTestService(t *testing.T) (*userService, *gorm.DB) {
	t.Helper()
	// Set the AES key so BeforeSave/AfterFind hooks work correctly.
	t.Setenv("SYSTEM_AES_KEY", iframeTestAESKey)
	db := setupIframeTestDB(t)
	svc := &userService{
		userRepo:        repository.NewUserRepository(db),
		tokenRepo:       repository.NewAuthTokenRepository(db),
		tenantRepo:      repository.NewTenantRepository(db),
		iframeNonceRepo: repository.NewIframeNonceRepository(db),
		// tenantService and config are not used by IframeLogin; left nil.
	}
	return svc, db
}

// seedTenant inserts a tenant with the given external_id and plaintext iframe_secret.
func seedTenant(t *testing.T, db *gorm.DB, cid, plaintextSecret string) *types.Tenant {
	t.Helper()
	tenant := &types.Tenant{
		Name:         "Test-" + cid,
		Status:       "active",
		ExternalID:   cid,
		IframeSecret: plaintextSecret,
	}
	if err := db.Create(tenant).Error; err != nil {
		t.Fatalf("create tenant: %v", err)
	}
	return tenant
}

func TestIframeLogin_HappyPath_CreatesUser(t *testing.T) {
	svc, db := newIframeTestService(t)
	seedTenant(t, db, "ACME", "secret1")
	req := &types.IframeLoginRequest{
		CID:    "ACME",
		Mobile: "13812345678",
		TS:     "1000",
		Nonce:  "n1",
		Sig:    SignIframeMessage("secret1", "ACME", "13812345678", "1000", "n1"),
	}
	resp, err := svc.IframeLogin(context.Background(), req)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !resp.Success || resp.User == nil {
		t.Fatalf("expected success with user, got: %+v", resp)
	}
	if resp.User.Mobile != "13812345678" {
		t.Fatalf("expected mobile 13812345678, got %q", resp.User.Mobile)
	}
	if resp.Token == "" {
		t.Fatalf("expected non-empty token")
	}
}

func TestIframeLogin_Replay(t *testing.T) {
	svc, db := newIframeTestService(t)
	seedTenant(t, db, "ACME", "secret1")
	req := &types.IframeLoginRequest{
		CID:    "ACME",
		Mobile: "13812345678",
		TS:     "1000",
		Nonce:  "n1",
	}
	req.Sig = SignIframeMessage("secret1", req.CID, req.Mobile, req.TS, req.Nonce)

	// First call succeeds.
	if _, err := svc.IframeLogin(context.Background(), req); err != nil {
		t.Fatalf("first call should succeed, got: %v", err)
	}
	// Second call with same nonce → replay error.
	_, err := svc.IframeLogin(context.Background(), req)
	ilErr, ok := err.(*types.IframeLoginError)
	if !ok || ilErr.Code != types.IframeErrReplay {
		t.Fatalf("expected IFRAME_REPLAY, got %v", err)
	}
}

func TestIframeLogin_BadSignature(t *testing.T) {
	svc, db := newIframeTestService(t)
	seedTenant(t, db, "ACME", "secret1")
	req := &types.IframeLoginRequest{
		CID:    "ACME",
		Mobile: "13812345678",
		TS:     "1000",
		Nonce:  "n2",
		// 64 hex chars, but wrong HMAC
		Sig: "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
	}
	_, err := svc.IframeLogin(context.Background(), req)
	ilErr, ok := err.(*types.IframeLoginError)
	if !ok || ilErr.Code != types.IframeErrBadSignature {
		t.Fatalf("expected IFRAME_BAD_SIGNATURE, got %v", err)
	}
}

func TestIframeLogin_UnknownTenant(t *testing.T) {
	svc, _ := newIframeTestService(t)
	req := &types.IframeLoginRequest{
		CID:    "UNKNOWN",
		Mobile: "13812345678",
		TS:     "1000",
		Nonce:  "n3",
		Sig:    SignIframeMessage("any", "UNKNOWN", "13812345678", "1000", "n3"),
	}
	_, err := svc.IframeLogin(context.Background(), req)
	ilErr, ok := err.(*types.IframeLoginError)
	if !ok || ilErr.Code != types.IframeErrTenantNotFound {
		t.Fatalf("expected IFRAME_TENANT_NOT_FOUND, got %v", err)
	}
}

func TestIframeLogin_NotEnabled(t *testing.T) {
	svc, db := newIframeTestService(t)
	seedTenant(t, db, "ACME2", "") // empty secret means iframe not enabled
	req := &types.IframeLoginRequest{
		CID:    "ACME2",
		Mobile: "13812345678",
		TS:     "1000",
		Nonce:  "n4",
		Sig:    "any",
	}
	_, err := svc.IframeLogin(context.Background(), req)
	ilErr, ok := err.(*types.IframeLoginError)
	if !ok || ilErr.Code != types.IframeErrNotEnabled {
		t.Fatalf("expected IFRAME_NOT_ENABLED, got %v", err)
	}
}

func TestIframeLogin_InvalidMobile(t *testing.T) {
	svc, db := newIframeTestService(t)
	seedTenant(t, db, "ACME3", "secret")
	req := &types.IframeLoginRequest{
		CID:    "ACME3",
		Mobile: "not-a-number",
		TS:     "1000",
		Nonce:  "n5",
		Sig:    SignIframeMessage("secret", "ACME3", "not-a-number", "1000", "n5"),
	}
	_, err := svc.IframeLogin(context.Background(), req)
	ilErr, ok := err.(*types.IframeLoginError)
	if !ok || ilErr.Code != types.IframeErrMobileInvalid {
		t.Fatalf("expected IFRAME_MOBILE_INVALID, got %v", err)
	}
}

func TestIframeLogin_MissingParams(t *testing.T) {
	svc, _ := newIframeTestService(t)
	// Missing CID
	req := &types.IframeLoginRequest{
		CID:    "",
		Mobile: "13812345678",
		TS:     "1000",
		Nonce:  "n6",
		Sig:    "s",
	}
	_, err := svc.IframeLogin(context.Background(), req)
	ilErr, ok := err.(*types.IframeLoginError)
	if !ok || ilErr.Code != types.IframeErrParamsMissing {
		t.Fatalf("expected IFRAME_PARAMS_MISSING, got %v", err)
	}
}

func TestIframeLogin_NonIntegerTS(t *testing.T) {
	svc, _ := newIframeTestService(t)
	req := &types.IframeLoginRequest{
		CID:    "ACME",
		Mobile: "13812345678",
		TS:     "abc",
		Nonce:  "n7",
		Sig:    "s",
	}
	_, err := svc.IframeLogin(context.Background(), req)
	ilErr, ok := err.(*types.IframeLoginError)
	if !ok || ilErr.Code != types.IframeErrParamsMissing {
		t.Fatalf("expected IFRAME_PARAMS_MISSING for non-integer ts, got %v", err)
	}
}

func TestIframeLogin_ExistingUserReturned(t *testing.T) {
	svc, db := newIframeTestService(t)
	tenant := seedTenant(t, db, "ACME4", "secret4")

	// Pre-create the user so the second call finds them.
	req := &types.IframeLoginRequest{
		CID:    "ACME4",
		Mobile: "13800000001",
		TS:     "2000",
		Nonce:  "n8",
		Sig:    SignIframeMessage("secret4", "ACME4", "13800000001", "2000", "n8"),
	}
	resp1, err := svc.IframeLogin(context.Background(), req)
	if err != nil {
		t.Fatalf("first login error: %v", err)
	}
	userID := resp1.User.ID

	// Second login with different nonce → same user returned.
	req2 := &types.IframeLoginRequest{
		CID:    "ACME4",
		Mobile: "13800000001",
		TS:     "3000",
		Nonce:  "n9",
	}
	req2.Sig = SignIframeMessage("secret4", req2.CID, req2.Mobile, req2.TS, req2.Nonce)
	_ = tenant
	resp2, err := svc.IframeLogin(context.Background(), req2)
	if err != nil {
		t.Fatalf("second login error: %v", err)
	}
	if resp2.User.ID != userID {
		t.Fatalf("expected same user ID %q, got %q", userID, resp2.User.ID)
	}
}
