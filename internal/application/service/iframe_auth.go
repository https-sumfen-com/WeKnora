// Package service - iframe_auth: HMAC sign/verify primitives for iframe login URLs.
package service

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
)

// SignIframeMessage builds the canonical message string (fields in dictionary order,
// no URL encoding) and returns hex(HMAC-SHA256(secret, message)).
//
// The canonical message format is:
//
//	"c_name={c_name}&cid={cid}&mobile={mobile}&nonce={nonce}&role={role}&ts={ts}"
//
// Fields are sorted by key ASCII-ascending order: '_' (0x5F) < 'i' (0x69),
// so `c_name` sorts before `cid`.
// External integrators produce the same string to generate a URL signature.
func SignIframeMessage(secret, cid, cName, mobile, ts, nonce, role string) string {
	msg := "c_name=" + cName +
		"&cid=" + cid +
		"&mobile=" + mobile +
		"&nonce=" + nonce +
		"&role=" + role +
		"&ts=" + ts
	m := hmac.New(sha256.New, []byte(secret))
	m.Write([]byte(msg))
	return hex.EncodeToString(m.Sum(nil))
}

// VerifyIframeSignature performs constant-time comparison of the expected and provided
// signatures. Returns false on any decoding error, length mismatch, or hmac mismatch.
func VerifyIframeSignature(secret, cid, cName, mobile, ts, nonce, role, providedSig string) bool {
	expected := SignIframeMessage(secret, cid, cName, mobile, ts, nonce, role)
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
