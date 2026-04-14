package repository

import (
	"context"
	"errors"
	"strings"

	"github.com/jackc/pgx/v5/pgconn"
	"gorm.io/gorm"

	"github.com/Tencent/WeKnora/internal/types"
	"github.com/Tencent/WeKnora/internal/types/interfaces"
)

type iframeNonceRepository struct {
	db *gorm.DB
}

// NewIframeNonceRepository constructs a new IframeNonceRepository.
func NewIframeNonceRepository(db *gorm.DB) interfaces.IframeNonceRepository {
	return &iframeNonceRepository{db: db}
}

// Consume attempts to INSERT the nonce.
// Returns (false, nil) when the (tenant_id, nonce) pair already exists (replay).
func (r *iframeNonceRepository) Consume(ctx context.Context, n *types.IframeNonce) (bool, error) {
	err := r.db.WithContext(ctx).Create(n).Error
	if err == nil {
		return true, nil
	}
	if isUniqueViolation(err) {
		return false, nil
	}
	return false, err
}

// DeleteOlderThan deletes nonces whose ts < cutoff.
func (r *iframeNonceRepository) DeleteOlderThan(ctx context.Context, cutoff int64) (int64, error) {
	res := r.db.WithContext(ctx).
		Where("ts < ?", cutoff).
		Delete(&types.IframeNonce{})
	return res.RowsAffected, res.Error
}

// isUniqueViolation identifies PG unique_violation and SQLite UNIQUE constraint errors,
// so callers can distinguish replay from other failures.
func isUniqueViolation(err error) bool {
	if err == nil {
		return false
	}
	// Postgres
	var pgErr *pgconn.PgError
	if errors.As(err, &pgErr) && pgErr.Code == "23505" {
		return true
	}
	// SQLite (gorm maps back to generic Error with the driver message)
	msg := err.Error()
	if strings.Contains(msg, "UNIQUE constraint failed") {
		return true
	}
	// GORM generic duplicated-key (some drivers/versions)
	if errors.Is(err, gorm.ErrDuplicatedKey) {
		return true
	}
	return false
}
