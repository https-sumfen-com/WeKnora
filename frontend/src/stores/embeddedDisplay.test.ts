import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { runInNewContext } from 'node:vm'
import * as vue from 'vue'
import * as pinia from 'pinia'
import ts from 'typescript'
import * as sidebarWidth from '../utils/sidebarWidth.ts'
import * as sequencedRefresh from './sequencedRefresh.ts'

function storage() {
  const values = new Map<string, string>()
  return { getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value) },
    removeItem: (key: string) => { values.delete(key) } }
}

function fixture() {
  const localStorage = storage(), sessionStorage = storage()
  const dependencies: Record<string, unknown> = {
    vue, pinia,
    '@/api/auth': { userInfoFromApi: (user: unknown) => user },
    '@/i18n': { default: { global: { t: (key: string) => key } } },
    '@/composables/useFont': { reloadFontFromStorage() {} },
    '@/composables/useTheme': { reloadThemeFromStorage() {} },
    '@/composables/preferenceStorage': { resetMigrationLatch() {}, safeRemoveItem() {}, userKey: (key: string) => key },
    '@/api/agent': { BUILTIN_QUICK_ANSWER_ID: 'quick-answer' },
    '@/stores/chatResources': { useChatResourcesStore: () => ({ invalidate() {} }) },
    '@/stores/editorResources': { useEditorResourcesStore: () => ({ invalidate() {} }) },
    '@/stores/organization': { useOrganizationStore: () => ({ clearState() {} }) },
    '@/stores/sequencedRefresh': sequencedRefresh,
    '@/utils/authRefresh': { invalidateAuthRefresh() {} },
    '../utils/sidebarWidth': sidebarWidth,
  }
  function load(file: string) {
    const exports: any = {}
    const compiled = ts.transpileModule(readFileSync(new URL(file, import.meta.url), 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    }).outputText
    runInNewContext(compiled, { exports, localStorage, sessionStorage, console,
      require(name: string) {
        if (name in dependencies) return dependencies[name]
        throw new Error(`Unexpected dependency: ${name}`)
      } })
    return exports
  }
  const { useAuthStore } = load('./auth.ts')
  const { useUIStore } = load('./ui.ts')
  return { localStorage, sessionStorage,
    reload: () => { pinia.setActivePinia(pinia.createPinia()); return { auth: useAuthStore(), ui: useUIStore() } } }
}

test('Sumfen menu mode survives refresh for the same account and clears on logout', () => {
  const f = fixture()
  let { auth } = f.reload()
  assert.equal(auth.isSumfenLogin, false)
  auth.setUser({ id: 'sumfen-user' })
  auth.setToken('login-token')
  auth.setSumfenLogin(true)
  assert.equal(auth.isSumfenLogin, true)
  auth = f.reload().auth
  assert.equal(auth.isSumfenLogin, true)
  auth.logout()
  assert.equal(auth.isSumfenLogin, false)
  assert.equal(f.reload().auth.isSumfenLogin, false)
})

test('Sumfen menu mode does not leak to another account or a normal login', () => {
  const f = fixture()
  const { auth } = f.reload()
  assert.equal(auth.isSumfenLogin, false)
  auth.setUser({ id: 'sumfen-user' })
  auth.setToken('login-token')
  auth.setSumfenLogin(true)
  auth.setUser({ id: 'other-user' })
  assert.equal(auth.isSumfenLogin, false)
  auth.setSumfenLogin(true)
  auth.setSumfenLogin(false)
  assert.equal(f.reload().auth.isSumfenLogin, false)
})

test('hidden navigation survives refresh and restores the original sidebar width', () => {
  const f = fixture()
  let { ui } = f.reload()
  assert.equal(ui.hideNavMode, false)
  ui.resizeSidebar(270)
  ui.setHideNavMode(true)
  assert.equal(ui.sidebarDisplayWidth, 0)
  ui = f.reload().ui
  assert.equal(ui.hideNavMode, true)
  assert.equal(ui.sidebarDisplayWidth, 0)
  ui.setHideNavMode(false)
  assert.equal(ui.sidebarDisplayWidth, 270)
  assert.equal(f.reload().ui.hideNavMode, false)
})
