package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"flag"
	"fmt"
	"os"
	"time"

	"github.com/google/uuid"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"

	"github.com/Tencent/WeKnora/internal/application/repository"
	"github.com/Tencent/WeKnora/internal/types"
)

// newDB opens a minimal GORM connection using DB_* env vars, bypassing the full
// WeKnora dig container. The admin CLI only needs organization CRUD; it does not need
// Redis, asynq, docreader, or any other backend-only infrastructure.
func newDB() (*gorm.DB, error) {
	host := envOr("DB_HOST", "localhost")
	port := envOr("DB_PORT", "5432")
	user := envOr("DB_USER", "postgres")
	pass := envOr("DB_PASSWORD", "postgres123!@#")
	name := envOr("DB_NAME", "WeKnora")
	sslmode := envOr("DB_SSLMODE", "disable")

	dsn := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=%s",
		host, port, user, pass, name, sslmode)
	return gorm.Open(postgres.Open(dsn), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Silent),
	})
}

func envOr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func runIframe(sub string, args []string) {
	fs := flag.NewFlagSet("iframe "+sub, flag.ExitOnError)
	cid := fs.String("cid", "", "organization external id (required)")
	name := fs.String("name", "", "organization display name (provision only)")
	_ = fs.Parse(args)
	if *cid == "" {
		fmt.Fprintln(os.Stderr, "--cid is required")
		os.Exit(2)
	}

	db, err := newDB()
	if err != nil {
		fmt.Fprintf(os.Stderr, "db connect failed: %v\n", err)
		os.Exit(1)
	}
	orgRepo := repository.NewOrganizationRepository(db)

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	switch sub {
	case "provision":
		if *name == "" {
			fmt.Fprintln(os.Stderr, "--name is required for provision")
			os.Exit(2)
		}
		err = provision(ctx, orgRepo, *cid, *name)
	case "rotate":
		err = rotate(ctx, orgRepo, *cid)
	case "revoke":
		err = revoke(ctx, orgRepo, *cid)
	default:
		fmt.Fprintf(os.Stderr, "unknown subcommand: %s\n", sub)
		os.Exit(2)
	}
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

// generateInviteCode returns a 32-character hex string for organizations.invite_code (required unique column).
func generateInviteCode() (string, error) {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return hex.EncodeToString(b), nil
}

func provision(ctx context.Context, repo interface {
	Create(context.Context, *types.Organization) error
	GetByExternalID(context.Context, string) (*types.Organization, error)
}, cid, name string) error {
	existing, err := repo.GetByExternalID(ctx, cid)
	if err == nil && existing != nil {
		return fmt.Errorf("organization with cid=%s already exists (id=%s); use 'rotate' to refresh secret", cid, existing.ID)
	}
	if err != nil && !errors.Is(err, repository.ErrOrganizationNotFound) {
		return fmt.Errorf("lookup failed: %w", err)
	}

	secret, err := generateSecret()
	if err != nil {
		return err
	}
	invite, err := generateInviteCode()
	if err != nil {
		return err
	}

	org := &types.Organization{
		ID:           uuid.New().String(),
		Name:         name,
		Description:  "iframe-provisioned",
		OwnerID:      "", // no user yet; first admin-role login promotes themselves
		InviteCode:   invite,
		ExternalID:   cid,
		IframeSecret: secret,
		CreatedAt:    time.Now(),
		UpdatedAt:    time.Now(),
	}
	if err := repo.Create(ctx, org); err != nil {
		return fmt.Errorf("create failed: %w", err)
	}

	fmt.Printf("Organization created: id=%s, external_id=%s\n", org.ID, cid)
	fmt.Println("iframe_secret (SAVE THIS, shown only once):")
	fmt.Println("────────────────────────────────────────")
	fmt.Println(secret)
	fmt.Println("────────────────────────────────────────")
	return nil
}

func rotate(ctx context.Context, repo interface {
	GetByExternalID(context.Context, string) (*types.Organization, error)
	UpdateIframeSecret(context.Context, string, string) error
}, cid string) error {
	org, err := repo.GetByExternalID(ctx, cid)
	if err != nil || org == nil {
		return fmt.Errorf("cid=%s not found; provision first", cid)
	}
	secret, err := generateSecret()
	if err != nil {
		return err
	}
	if err := repo.UpdateIframeSecret(ctx, org.ID, secret); err != nil {
		return err
	}
	fmt.Printf("Secret rotated for cid=%s (org_id=%s)\n", cid, org.ID)
	fmt.Println("new iframe_secret (SAVE THIS, shown only once):")
	fmt.Println("────────────────────────────────────────")
	fmt.Println(secret)
	fmt.Println("────────────────────────────────────────")
	return nil
}

func revoke(ctx context.Context, repo interface {
	GetByExternalID(context.Context, string) (*types.Organization, error)
	UpdateIframeSecret(context.Context, string, string) error
}, cid string) error {
	org, err := repo.GetByExternalID(ctx, cid)
	if err != nil || org == nil {
		return fmt.Errorf("cid=%s not found", cid)
	}
	if err := repo.UpdateIframeSecret(ctx, org.ID, ""); err != nil {
		return err
	}
	fmt.Printf("iframe access revoked for cid=%s\n", cid)
	return nil
}

