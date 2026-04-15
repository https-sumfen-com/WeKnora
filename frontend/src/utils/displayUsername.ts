/**
 * Display-name helpers for iframe-auto-login users.
 *
 * Backend stores iframe users as:
 *   user.username = "iframe_<org.ID-uuid>_<mobile>"
 *   user.mobile   = "<mobile>"
 *   tenant.name   = "iframe-user-<org.Name>-<mobile>"  (where org.Name = c_name at provision)
 *
 * For UI display we want a human-readable form: "<orgName>_<mobile>".
 * Non-iframe users (email/password, OIDC) keep their original username.
 */

const IFRAME_USERNAME_RE = /^iframe_.+_(\d{11})$/
const IFRAME_TENANT_NAME_RE = /^iframe-user-(.+)-(\d{11})$/

interface UserLike {
  username?: string | null
  mobile?: string | null
}

interface TenantLike {
  name?: string | null
}

/**
 * Returns the friendly display name for an iframe-auto-provisioned user.
 * Falls through unchanged if the user is not iframe-created.
 */
export function displayUsername(
  user?: UserLike | null,
  tenant?: TenantLike | null,
): string {
  const raw = user?.username?.trim() ?? ''
  if (!raw) return ''

  const m = IFRAME_USERNAME_RE.exec(raw)
  if (!m) return raw // non-iframe user: show backend username as-is

  const mobile = user?.mobile?.trim() || m[1]

  // Extract the original c_name from tenant.name when available.
  const tName = tenant?.name?.trim() ?? ''
  const tm = IFRAME_TENANT_NAME_RE.exec(tName)
  if (tm) {
    return `${tm[1]}_${mobile}`
  }

  // Defensive fallback: just the mobile.
  return mobile
}
