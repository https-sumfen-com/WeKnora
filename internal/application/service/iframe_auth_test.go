package service

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"testing"
)

func TestSignIframeMessage_Deterministic(t *testing.T) {
	secret := "testsecret"
	got := SignIframeMessage(secret, "ACME", "13812345678", "1713081234", "nonce123", "admin")
	want := expectedHMAC(secret, "cid=ACME&mobile=13812345678&nonce=nonce123&role=admin&ts=1713081234")
	if got != want {
		t.Fatalf("sig mismatch\n got=%s\nwant=%s", got, want)
	}
}

func TestVerifyIframeSignature_HappyPath(t *testing.T) {
	secret := "testsecret"
	sig := SignIframeMessage(secret, "ACME", "13812345678", "1000", "abcd", "admin")
	if !VerifyIframeSignature(secret, "ACME", "13812345678", "1000", "abcd", "admin", sig) {
		t.Fatal("verify should pass with identical params")
	}
}

func TestVerifyIframeSignature_TamperedFields(t *testing.T) {
	secret := "testsecret"
	sig := SignIframeMessage(secret, "ACME", "13812345678", "1000", "abcd", "admin")
	cases := []struct{ name, cid, mobile, ts, nonce, role string }{
		{"cid", "ACMEX", "13812345678", "1000", "abcd", "admin"},
		{"mobile", "ACME", "13812345679", "1000", "abcd", "admin"},
		{"ts", "ACME", "13812345678", "1001", "abcd", "admin"},
		{"nonce", "ACME", "13812345678", "1000", "abce", "admin"},
		{"role", "ACME", "13812345678", "1000", "abcd", "editor"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if VerifyIframeSignature(secret, c.cid, c.mobile, c.ts, c.nonce, c.role, sig) {
				t.Fatalf("tampered %s should not verify", c.name)
			}
		})
	}
}

func TestVerifyIframeSignature_WrongSig(t *testing.T) {
	secret := "testsecret"
	correct := SignIframeMessage(secret, "ACME", "138", "1", "n", "viewer")
	wrong := "0" + correct[1:] // flip first char (still 64 hex chars)
	if VerifyIframeSignature(secret, "ACME", "138", "1", "n", "viewer", wrong) {
		t.Fatal("wrong sig must fail")
	}
}

func TestVerifyIframeSignature_WrongSecret(t *testing.T) {
	s1 := SignIframeMessage("secret1", "ACME", "138", "1", "n", "editor")
	if VerifyIframeSignature("secret2", "ACME", "138", "1", "n", "editor", s1) {
		t.Fatal("different secret must fail verification")
	}
}

func TestVerifyIframeSignature_MalformedSig(t *testing.T) {
	secret := "testsecret"
	// Non-hex characters
	if VerifyIframeSignature(secret, "ACME", "138", "1", "n", "viewer", "xyz") {
		t.Fatal("malformed sig should not verify")
	}
	// Wrong length
	if VerifyIframeSignature(secret, "ACME", "138", "1", "n", "viewer", "abcd") {
		t.Fatal("short sig should not verify")
	}
	// Empty sig
	if VerifyIframeSignature(secret, "ACME", "138", "1", "n", "viewer", "") {
		t.Fatal("empty sig should not verify")
	}
}

func expectedHMAC(secret, msg string) string {
	m := hmac.New(sha256.New, []byte(secret))
	m.Write([]byte(msg))
	return hex.EncodeToString(m.Sum(nil))
}
