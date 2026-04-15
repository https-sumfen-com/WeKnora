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
		&types.Organization{},
		&types.OrganizationMember{},
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
	// TENANT_AES_KEY is used by CreateTenant → generateApiKey.
	t.Setenv("TENANT_AES_KEY", iframeTestAESKey)
	db := setupIframeTestDB(t)
	tenantRepo := repository.NewTenantRepository(db)
	svc := &userService{
		userRepo:         repository.NewUserRepository(db),
		tokenRepo:        repository.NewAuthTokenRepository(db),
		tenantRepo:       tenantRepo,
		tenantService:    NewTenantService(tenantRepo),
		iframeNonceRepo:  repository.NewIframeNonceRepository(db),
		organizationRepo: repository.NewOrganizationRepository(db),
	}
	return svc, db
}

// seedOrganization inserts an organization with the given external_id and plaintext iframe_secret.
func seedOrganization(t *testing.T, db *gorm.DB, cid, plaintextSecret string) *types.Organization {
	t.Helper()
	// We need a placeholder owner user first (OwnerID is required NOT NULL).
	ownerUser := &types.User{
		ID:       "owner-" + cid,
		Username: "owner_" + cid,
		Email:    "owner_" + cid + "@test.invalid",
		IsActive: true,
	}
	if err := db.Create(ownerUser).Error; err != nil {
		t.Fatalf("create owner user: %v", err)
	}
	org := &types.Organization{
		ID:           "org-" + cid,
		Name:         "Test-" + cid,
		ExternalID:   cid,
		IframeSecret: plaintextSecret,
		OwnerID:      ownerUser.ID,
	}
	if err := db.Create(org).Error; err != nil {
		t.Fatalf("create organization: %v", err)
	}
	return org
}

func TestIframeLogin_HappyPath_CreatesUser(t *testing.T) {
	svc, db := newIframeTestService(t)
	seedOrganization(t, db, "ACME", "secret1")
	req := &types.IframeLoginRequest{
		CID:    "ACME",
		CName:  "ACME Org",
		Mobile: "13812345678",
		TS:     "1000",
		Nonce:  "n1",
		Role:   "editor",
		Sig:    SignIframeMessage("secret1", "ACME", "ACME Org", "13812345678", "1000", "n1", "editor"),
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
	// Verify personal tenant was created and returned.
	if resp.Tenant == nil || resp.Tenant.ID == 0 {
		t.Fatalf("expected personal tenant to be created and returned")
	}
	// Verify OrganizationMember was created with correct role.
	var member types.OrganizationMember
	if err := db.Where("user_id = ? AND organization_id = ?", resp.User.ID, "org-ACME").First(&member).Error; err != nil {
		t.Fatalf("expected org member to be created: %v", err)
	}
	if member.Role != types.OrgRoleEditor {
		t.Fatalf("expected role editor, got %q", member.Role)
	}
}

func TestIframeLogin_Replay(t *testing.T) {
	svc, db := newIframeTestService(t)
	seedOrganization(t, db, "ACME", "secret1")
	req := &types.IframeLoginRequest{
		CID:    "ACME",
		CName:  "ACME Org",
		Mobile: "13812345678",
		TS:     "1000",
		Nonce:  "n1",
		Role:   "editor",
	}
	req.Sig = SignIframeMessage("secret1", req.CID, req.CName, req.Mobile, req.TS, req.Nonce, req.Role)

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
	seedOrganization(t, db, "ACME", "secret1")
	req := &types.IframeLoginRequest{
		CID:    "ACME",
		CName:  "ACME Org",
		Mobile: "13812345678",
		TS:     "1000",
		Nonce:  "n2",
		Role:   "viewer",
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
		CName:  "UNKNOWN Org",
		Mobile: "13812345678",
		TS:     "1000",
		Nonce:  "n3",
		Role:   "viewer",
		Sig:    SignIframeMessage("any", "UNKNOWN", "UNKNOWN Org", "13812345678", "1000", "n3", "viewer"),
	}
	_, err := svc.IframeLogin(context.Background(), req)
	ilErr, ok := err.(*types.IframeLoginError)
	if !ok || ilErr.Code != types.IframeErrTenantNotFound {
		t.Fatalf("expected IFRAME_TENANT_NOT_FOUND, got %v", err)
	}
}

func TestIframeLogin_NotEnabled(t *testing.T) {
	svc, db := newIframeTestService(t)
	seedOrganization(t, db, "ACME2", "") // empty secret means iframe not enabled
	req := &types.IframeLoginRequest{
		CID:    "ACME2",
		CName:  "ACME2 Org",
		Mobile: "13812345678",
		TS:     "1000",
		Nonce:  "n4",
		Role:   "viewer",
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
	seedOrganization(t, db, "ACME3", "secret")
	req := &types.IframeLoginRequest{
		CID:    "ACME3",
		CName:  "ACME3 Org",
		Mobile: "not-a-number",
		TS:     "1000",
		Nonce:  "n5",
		Role:   "editor",
		Sig:    SignIframeMessage("secret", "ACME3", "ACME3 Org", "not-a-number", "1000", "n5", "editor"),
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
		CName:  "",
		Mobile: "13812345678",
		TS:     "1000",
		Nonce:  "n6",
		Role:   "viewer",
		Sig:    "s",
	}
	_, err := svc.IframeLogin(context.Background(), req)
	ilErr, ok := err.(*types.IframeLoginError)
	if !ok || ilErr.Code != types.IframeErrParamsMissing {
		t.Fatalf("expected IFRAME_PARAMS_MISSING, got %v", err)
	}
}

func TestIframeLogin_MissingRole(t *testing.T) {
	svc, _ := newIframeTestService(t)
	// Missing Role — must fail before DB lookup
	req := &types.IframeLoginRequest{
		CID:    "ACME",
		CName:  "ACME Org",
		Mobile: "13812345678",
		TS:     "1000",
		Nonce:  "n6b",
		Role:   "",
		Sig:    "s",
	}
	_, err := svc.IframeLogin(context.Background(), req)
	ilErr, ok := err.(*types.IframeLoginError)
	if !ok || ilErr.Code != types.IframeErrParamsMissing {
		t.Fatalf("expected IFRAME_PARAMS_MISSING for missing role, got %v", err)
	}
}

func TestIframeLogin_NonIntegerTS(t *testing.T) {
	svc, _ := newIframeTestService(t)
	req := &types.IframeLoginRequest{
		CID:    "ACME",
		CName:  "ACME Org",
		Mobile: "13812345678",
		TS:     "abc",
		Nonce:  "n7",
		Role:   "editor",
		Sig:    "s",
	}
	_, err := svc.IframeLogin(context.Background(), req)
	ilErr, ok := err.(*types.IframeLoginError)
	if !ok || ilErr.Code != types.IframeErrParamsMissing {
		t.Fatalf("expected IFRAME_PARAMS_MISSING for non-integer ts, got %v", err)
	}
}

func TestIframeLogin_InvalidRole(t *testing.T) {
	svc, db := newIframeTestService(t)
	seedOrganization(t, db, "ACME5", "secret5")
	req := &types.IframeLoginRequest{
		CID:    "ACME5",
		CName:  "ACME5 Org",
		Mobile: "13812345678",
		TS:     "1000",
		Nonce:  "n_role",
		Role:   "banana",
		Sig:    SignIframeMessage("secret5", "ACME5", "ACME5 Org", "13812345678", "1000", "n_role", "banana"),
	}
	_, err := svc.IframeLogin(context.Background(), req)
	ilErr, ok := err.(*types.IframeLoginError)
	if !ok || ilErr.Code != types.IframeErrRoleInvalid {
		t.Fatalf("expected IFRAME_ROLE_INVALID, got %v", err)
	}
}

func TestIframeLogin_ExistingUserReturned(t *testing.T) {
	svc, db := newIframeTestService(t)
	seedOrganization(t, db, "ACME4", "secret4")

	// First login creates the user.
	req := &types.IframeLoginRequest{
		CID:    "ACME4",
		CName:  "ACME4 Org",
		Mobile: "13800000001",
		TS:     "2000",
		Nonce:  "n8",
		Role:   "editor",
		Sig:    SignIframeMessage("secret4", "ACME4", "ACME4 Org", "13800000001", "2000", "n8", "editor"),
	}
	resp1, err := svc.IframeLogin(context.Background(), req)
	if err != nil {
		t.Fatalf("first login error: %v", err)
	}
	userID := resp1.User.ID

	// Second login with different nonce → same user returned.
	req2 := &types.IframeLoginRequest{
		CID:    "ACME4",
		CName:  "ACME4 Org",
		Mobile: "13800000001",
		TS:     "3000",
		Nonce:  "n9",
		Role:   "editor",
	}
	req2.Sig = SignIframeMessage("secret4", req2.CID, req2.CName, req2.Mobile, req2.TS, req2.Nonce, req2.Role)
	resp2, err := svc.IframeLogin(context.Background(), req2)
	if err != nil {
		t.Fatalf("second login error: %v", err)
	}
	if resp2.User.ID != userID {
		t.Fatalf("expected same user ID %q, got %q", userID, resp2.User.ID)
	}
}

func TestIframeLogin_RoleSync(t *testing.T) {
	svc, db := newIframeTestService(t)
	seedOrganization(t, db, "ACME6", "secret6")

	// First login creates user as editor.
	req := &types.IframeLoginRequest{
		CID:    "ACME6",
		CName:  "ACME6 Org",
		Mobile: "13900000002",
		TS:     "4000",
		Nonce:  "n10",
		Role:   "editor",
		Sig:    SignIframeMessage("secret6", "ACME6", "ACME6 Org", "13900000002", "4000", "n10", "editor"),
	}
	resp1, err := svc.IframeLogin(context.Background(), req)
	if err != nil {
		t.Fatalf("first login error: %v", err)
	}

	// Second login with role=admin → member role should be updated.
	req2 := &types.IframeLoginRequest{
		CID:    "ACME6",
		CName:  "ACME6 Org",
		Mobile: "13900000002",
		TS:     "5000",
		Nonce:  "n11",
		Role:   "admin",
	}
	req2.Sig = SignIframeMessage("secret6", req2.CID, req2.CName, req2.Mobile, req2.TS, req2.Nonce, req2.Role)
	if _, err := svc.IframeLogin(context.Background(), req2); err != nil {
		t.Fatalf("second login error: %v", err)
	}

	// Verify role was synced in DB.
	var member types.OrganizationMember
	if err := db.Where("user_id = ? AND organization_id = ?", resp1.User.ID, "org-ACME6").First(&member).Error; err != nil {
		t.Fatalf("member lookup: %v", err)
	}
	if member.Role != types.OrgRoleAdmin {
		t.Fatalf("expected role to be synced to admin, got %q", member.Role)
	}
}
