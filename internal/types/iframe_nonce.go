package types

import "time"

// IframeNonce records a consumed HMAC URL nonce to prevent replay.
type IframeNonce struct {
	ID         uint64    `gorm:"primaryKey" json:"id"`
	TenantID   uint64    `gorm:"index;not null;uniqueIndex:uk_iframe_nonce" json:"tenant_id"`
	Nonce      string    `gorm:"type:varchar(64);not null;uniqueIndex:uk_iframe_nonce" json:"nonce"`
	TS         int64     `gorm:"not null;index" json:"ts"`
	ConsumedAt time.Time `gorm:"not null;default:CURRENT_TIMESTAMP" json:"consumed_at"`
}

// TableName returns the table name for IframeNonce.
func (IframeNonce) TableName() string { return "iframe_nonces" }
