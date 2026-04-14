package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"flag"
	"fmt"
	"os"
	"time"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"

	"github.com/Tencent/WeKnora/internal/application/repository"
	"github.com/Tencent/WeKnora/internal/types"
	"github.com/Tencent/WeKnora/internal/types/interfaces"
)

// newDB opens a minimal GORM connection using DB_* env vars, bypassing the full
// WeKnora dig container. The admin CLI only needs tenant CRUD; it does not need
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
	cid := fs.String("cid", "", "tenant external id (required)")
	name := fs.String("name", "", "tenant display name (provision only)")
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
	tenantRepo := repository.NewTenantRepository(db)

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	switch sub {
	case "provision":
		if *name == "" {
			fmt.Fprintln(os.Stderr, "--name is required for provision")
			os.Exit(2)
		}
		err = provision(ctx, tenantRepo, *cid, *name)
	case "rotate":
		err = rotate(ctx, tenantRepo, *cid)
	case "revoke":
		err = revoke(ctx, tenantRepo, *cid)
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

func provision(ctx context.Context, repo interfaces.TenantRepository, cid, name string) error {
	existing, err := repo.GetByExternalID(ctx, cid)
	if err == nil && existing != nil {
		return fmt.Errorf("tenant with cid=%s already exists (id=%d); use 'rotate' to refresh secret", cid, existing.ID)
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
	if err != nil || t == nil {
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
	if err != nil || t == nil {
		return fmt.Errorf("cid=%s not found", cid)
	}
	if err := repo.UpdateIframeSecret(ctx, t.ID, ""); err != nil {
		return err
	}
	fmt.Printf("iframe access revoked for cid=%s\n", cid)
	return nil
}

