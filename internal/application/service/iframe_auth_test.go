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

func TestVerifyIframeSignature_HappyPath(t *testing.T) {
	secret := "testsecret"
	sig := SignIframeMessage(secret, "ACME", "13812345678", "1000", "abcd")
	if !VerifyIframeSignature(secret, "ACME", "13812345678", "1000", "abcd", sig) {
		t.Fatal("verify should pass with identical params")
	}
}

func TestVerifyIframeSignature_TamperedFields(t *testing.T) {
	secret := "testsecret"
	sig := SignIframeMessage(secret, "ACME", "13812345678", "1000", "abcd")
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

func TestVerifyIframeSignature_WrongSig(t *testing.T) {
	secret := "testsecret"
	correct := SignIframeMessage(secret, "ACME", "138", "1", "n")
	wrong := "0" + correct[1:] // flip first char (still 64 hex chars)
	if VerifyIframeSignature(secret, "ACME", "138", "1", "n", wrong) {
		t.Fatal("wrong sig must fail")
	}
}

func TestVerifyIframeSignature_WrongSecret(t *testing.T) {
	s1 := SignIframeMessage("secret1", "ACME", "138", "1", "n")
	if VerifyIframeSignature("secret2", "ACME", "138", "1", "n", s1) {
		t.Fatal("different secret must fail verification")
	}
}

func TestVerifyIframeSignature_MalformedSig(t *testing.T) {
	secret := "testsecret"
	// Non-hex characters
	if VerifyIframeSignature(secret, "ACME", "138", "1", "n", "xyz") {
		t.Fatal("malformed sig should not verify")
	}
	// Wrong length
	if VerifyIframeSignature(secret, "ACME", "138", "1", "n", "abcd") {
		t.Fatal("short sig should not verify")
	}
	// Empty sig
	if VerifyIframeSignature(secret, "ACME", "138", "1", "n", "") {
		t.Fatal("empty sig should not verify")
	}
}

func expectedHMAC(secret, msg string) string {
	m := hmac.New(sha256.New, []byte(secret))
	m.Write([]byte(msg))
	return hex.EncodeToString(m.Sum(nil))
}
