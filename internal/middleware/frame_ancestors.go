// Package middleware — frame_ancestors: sets CSP frame-ancestors header to control
// which parent origins can embed WeKnora in an iframe.
package middleware

import (
	"os"
	"strings"

	"github.com/gin-gonic/gin"
)

// FrameAncestors returns middleware that sets Content-Security-Policy: frame-ancestors <value>
// when WEKNORA_FRAME_ANCESTORS env is non-empty. Empty env → header not set (any origin may embed).
// Multiple parent origins can be passed space-separated, e.g. "https://a.com https://b.com".
func FrameAncestors() gin.HandlerFunc {
	raw := strings.TrimSpace(os.Getenv("WEKNORA_FRAME_ANCESTORS"))
	if raw == "" {
		return func(c *gin.Context) { c.Next() }
	}
	header := "frame-ancestors " + raw
	return func(c *gin.Context) {
		c.Writer.Header().Set("Content-Security-Policy", header)
		c.Next()
	}
}
