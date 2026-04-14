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
