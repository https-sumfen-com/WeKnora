// Package middleware — iframe_ratelimit: per-IP rate limiter for iframe login bad-signature
// attempts. Separate from the generic auth middleware to keep policy explicit.
package middleware

import (
	"sync"
	"time"

	"golang.org/x/time/rate"
)

// iframeBadSigLimiter tracks per-IP limiters for IFRAME_BAD_SIGNATURE events.
// Allowed rate: 5 attempts per minute per IP.
type iframeBadSigLimiter struct {
	mu       sync.Mutex
	limiters map[string]*rate.Limiter
}

// Limit per IP: 5 events burst, 1 event every 12 seconds steady state.
// After 5 bad attempts within ~minute, subsequent attempts fail until refill.
const (
	iframeBadSigBurst    = 5
	iframeBadSigInterval = 12 * time.Second
)

var globalIframeBadSigLimiter = &iframeBadSigLimiter{
	limiters: make(map[string]*rate.Limiter),
}

// AllowBadSignature returns true when the IP may make another bad-signature attempt.
// Called by the iframe-login handler ONLY AFTER a BAD_SIGNATURE error.
// Returning false means: too many attempts, throttle (HTTP 429).
func AllowBadSignature(ip string) bool {
	return globalIframeBadSigLimiter.allow(ip)
}

func (l *iframeBadSigLimiter) allow(ip string) bool {
	l.mu.Lock()
	lim, ok := l.limiters[ip]
	if !ok {
		lim = rate.NewLimiter(rate.Every(iframeBadSigInterval), iframeBadSigBurst)
		l.limiters[ip] = lim
	}
	l.mu.Unlock()
	return lim.Allow()
}
