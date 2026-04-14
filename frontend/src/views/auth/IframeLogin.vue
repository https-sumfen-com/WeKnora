<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useEmbeddedStore } from '@/stores/embedded'
import { useAuthStore } from '@/stores/auth'
import { iframeLogin } from '@/api/auth'

const route = useRoute()
const router = useRouter()
const embedded = useEmbeddedStore()
const authStore = useAuthStore()
const { locale } = useI18n()

const loading = ref(true)
const errorMsg = ref<string>('')

const errorMap: Record<string, string> = {
  IFRAME_PARAMS_MISSING: '链接参数不完整，请联系系统管理员',
  IFRAME_MOBILE_INVALID: '手机号格式非法',
  IFRAME_BAD_SIGNATURE: '鉴权失败，请联系系统管理员',
  IFRAME_REPLAY: '请求重复，请刷新页面后重试',
  IFRAME_USER_DISABLED: '账号已被禁用',
  IFRAME_NOT_ENABLED: '该组织未启用 iframe 登录',
  IFRAME_TENANT_NOT_FOUND: '组织未开通，请联系系统管理员',
  IFRAME_INTERNAL: '服务暂时不可用，请稍后重试',
}

function pickError(e: any): string {
  // The project's axios interceptor rejects with { status, message, ...data }
  // so the IFRAME_* code is directly on the error object as e.code.
  // Fall back to nested paths in case the shape changes in tests/mocks.
  const code = e?.code ?? e?.data?.code ?? e?.response?.data?.code
  if (code && errorMap[code]) return errorMap[code]
  return '登录失败，请刷新页面重试'
}

onMounted(async () => {
  embedded.enable()
  locale.value = 'zh-CN'

  const q = route.query
  const params = {
    cid: String(q.cid ?? ''),
    mobile: String(q.mobile ?? ''),
    ts: String(q.ts ?? ''),
    nonce: String(q.nonce ?? ''),
    sig: String(q.sig ?? ''),
  }
  if (!params.cid || !params.mobile || !params.ts || !params.nonce || !params.sig) {
    errorMsg.value = errorMap.IFRAME_PARAMS_MISSING
    loading.value = false
    return
  }

  try {
    const data = await iframeLogin(params)
    if (!data?.success || !data?.token) {
      errorMsg.value = pickError(data)
      loading.value = false
      return
    }
    // 使用 authStore 方法持久化登录状态（与路由守卫的 persistLoginResponse 保持一致）
    if (data.user) {
      authStore.setUser({
        id: data.user.id || '',
        username: data.user.username || '',
        email: data.user.email || '',
        avatar: data.user.avatar,
        tenant_id: String(data.tenant?.id) || '',
        can_access_all_tenants: data.user.can_access_all_tenants || false,
        created_at: data.user.created_at || new Date().toISOString(),
        updated_at: data.user.updated_at || new Date().toISOString(),
      })
    }
    if (data.tenant) {
      authStore.setTenant({
        id: String(data.tenant.id) || '',
        name: data.tenant.name || '',
        api_key: data.tenant.api_key || '',
        owner_id: data.user?.id || '',
        created_at: data.tenant.created_at || new Date().toISOString(),
        updated_at: data.tenant.updated_at || new Date().toISOString(),
      })
    }
    authStore.setToken(data.token)
    if (data.refresh_token) {
      authStore.setRefreshToken(data.refresh_token)
    }
    router.replace('/platform/knowledge-bases')
  } catch (e: any) {
    errorMsg.value = pickError(e)
    loading.value = false
  }
})
</script>

<template>
  <div class="iframe-login-root">
    <div v-if="loading" class="loading">
      <div class="spinner" />
      <div class="hint">正在登录…</div>
    </div>
    <div v-else class="error">
      <div class="msg">{{ errorMsg }}</div>
    </div>
  </div>
</template>

<style scoped>
.iframe-login-root {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: #f5f7fa;
}
.spinner {
  width: 48px;
  height: 48px;
  border: 4px solid #ddd;
  border-top-color: #4e6b99;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto;
}
.hint,
.msg {
  margin-top: 16px;
  color: #666;
  text-align: center;
}
.msg {
  color: #d54;
  font-weight: 500;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
