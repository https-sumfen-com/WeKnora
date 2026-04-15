package types

// IframeLoginRequest carries HMAC-signed parameters from an embedding parent system.
type IframeLoginRequest struct {
	CID    string `json:"cid"    binding:"required"`
	CName  string `json:"c_name" binding:"required"`
	Mobile string `json:"mobile" binding:"required"`
	TS     string `json:"ts"     binding:"required"`
	Nonce  string `json:"nonce"  binding:"required"`
	Role   string `json:"role"   binding:"required"`
	Sig    string `json:"sig"    binding:"required"`
}

// IframeErrorCode is the `code` field returned to clients for iframe-login failures.
type IframeErrorCode string

const (
	IframeErrParamsMissing  IframeErrorCode = "IFRAME_PARAMS_MISSING"
	IframeErrMobileInvalid  IframeErrorCode = "IFRAME_MOBILE_INVALID"
	IframeErrBadSignature   IframeErrorCode = "IFRAME_BAD_SIGNATURE"
	IframeErrReplay         IframeErrorCode = "IFRAME_REPLAY"
	IframeErrUserDisabled   IframeErrorCode = "IFRAME_USER_DISABLED"
	IframeErrNotEnabled     IframeErrorCode = "IFRAME_NOT_ENABLED"
	IframeErrTenantNotFound IframeErrorCode = "IFRAME_TENANT_NOT_FOUND"
	IframeErrRoleInvalid    IframeErrorCode = "IFRAME_ROLE_INVALID"
	IframeErrInternal       IframeErrorCode = "IFRAME_INTERNAL"
)

// IframeLoginError wraps a user-visible iframe-login failure with a stable code.
type IframeLoginError struct {
	Code    IframeErrorCode
	Message string
}

// Error satisfies the error interface.
func (e *IframeLoginError) Error() string { return string(e.Code) + ": " + e.Message }

// NewIframeLoginError constructs a typed iframe-login error.
func NewIframeLoginError(code IframeErrorCode, message string) *IframeLoginError {
	return &IframeLoginError{Code: code, Message: message}
}
