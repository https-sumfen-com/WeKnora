/**
 * Display-name helpers for iframe-auto-login users.
 *
 * Backend stores iframe users as:
 *   user.username = "iframe_<org.ID-uuid>_<mobile>"
 *   user.mobile   = "<mobile>"
 *   tenant.name   = "iframe-user-<org.Name>-<mobile>"  (org.Name = c_name at provision)
 *
 * For UI we render "<cName>_<mobile>" for iframe users, and pass through
 * the raw username for regular (password/OIDC) users.
 *
 * Two call sites use this helper:
 *   - Self rendering (UserMenu, ApiInfo): c_name resolved from authStore.tenant.name
 *   - Org member list: c_name taken directly from the current organization.name
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
 *
 * c_name resolution precedence:
 *   1. `context.orgName` if provided (most reliable — directly from current org)
 *   2. Parsed from `context.tenant.name` (self-login case, tenant loaded at login)
 *   3. None → fall back to showing just the mobile
 */
export function displayUsername(
  user?: UserLike | null,
  context?: {
    tenant?: TenantLike | null
    orgName?: string | null
  },
): string {
  const raw = user?.username?.trim() ?? ''
  if (!raw) return ''

  const m = IFRAME_USERNAME_RE.exec(raw)
  if (!m) return raw // non-iframe user: show backend username as-is

  const mobile = user?.mobile?.trim() || m[1]

  // 1. Explicit orgName wins (e.g. current organization in member list)
  const explicit = context?.orgName?.trim()
  if (explicit) return `${explicit}_${mobile}`

  // 2. Parse from tenant.name
  const tName = context?.tenant?.name?.trim() ?? ''
  const tm = IFRAME_TENANT_NAME_RE.exec(tName)
  if (tm) return `${tm[1]}_${mobile}`

  // 3. Defensive fallback: just the mobile
  return mobile
}
