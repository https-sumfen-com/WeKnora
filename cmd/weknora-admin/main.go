// Package main is the entry for weknora-admin — a server-side operator CLI.
// Subcommands:
//
//	iframe provision --cid <cid> --name <display-name>
//	iframe rotate    --cid <cid>
//	iframe revoke    --cid <cid>
package main

import (
	"fmt"
	"os"

	"github.com/joho/godotenv"
)

func main() {
	// Load .env / .env.lite from CWD if present so the CLI sees DB_DRIVER etc.
	// Matches the backend's convention (scripts/dev.sh sources .env before go run).
	for _, f := range []string{".env", ".env.lite"} {
		if _, err := os.Stat(f); err == nil {
			_ = godotenv.Load(f)
			// DB_HOST defaults to the docker service name inside compose; when running
			// the CLI on the host the backend uses localhost overrides from dev.sh.
			// Apply the same localhost overrides here so the CLI hits the dev infra.
			applyDevLocalhostOverrides()
			break
		}
	}

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

// applyDevLocalhostOverrides mirrors scripts/dev.sh: when running against the
// docker-compose dev infrastructure from the host, service hostnames must
// resolve to localhost. Only sets values not already present in env.
func applyDevLocalhostOverrides() {
	overrides := map[string]string{
		"DB_HOST":         "localhost",
		"DOCREADER_ADDR":  "localhost:50051",
		"MINIO_ENDPOINT":  "localhost:9000",
		"REDIS_ADDR":      "localhost:6379",
		"MILVUS_ADDRESS":  "localhost:19530",
		"NEO4J_URI":       "bolt://localhost:7687",
		"QDRANT_HOST":     "localhost",
	}
	for k, v := range overrides {
		if os.Getenv(k) == "" {
			_ = os.Setenv(k, v)
		}
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, `weknora-admin — operator CLI

Usage:
  weknora-admin iframe provision --cid <cid> --name <display-name>
  weknora-admin iframe rotate    --cid <cid>
  weknora-admin iframe revoke    --cid <cid>`)
}
