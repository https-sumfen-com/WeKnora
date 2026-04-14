package interfaces

import (
	"context"

	"github.com/Tencent/WeKnora/internal/types"
)

// IframeNonceRepository persists consumed iframe-login nonces for replay protection.
type IframeNonceRepository interface {
	// Consume atomically records a (tenant, nonce) tuple.
	// Returns (true, nil) if inserted (first consumption);
	// (false, nil) if already existed (replay detected);
	// (false, err) on any other database error.
	Consume(ctx context.Context, nonce *types.IframeNonce) (inserted bool, err error)
	// DeleteOlderThan prunes nonces with ts < cutoff (Unix seconds).
	// Returns the number of rows deleted.
	DeleteOlderThan(ctx context.Context, cutoff int64) (int64, error)
}
