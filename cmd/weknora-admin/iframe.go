package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"flag"
	"fmt"
	"os"
	"time"

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

	err := c.Invoke(func(tenantRepo interfaces.TenantRepository) error {
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
	if err == nil && existing != nil {
		return fmt.Errorf("tenant with cid=%s already exists (id=%d); use 'rotate' to refresh secret", cid, existing.ID)
	}
	// if err is ErrTenantNotFound, proceed to create
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
