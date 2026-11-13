import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { runInNewContext } from 'node:vm'
import ts from 'typescript'
import type { sumfenAutoLogin } from './index.ts'

const compiled = ts.transpileModule(
  readFileSync(new URL('./index.ts', import.meta.url), 'utf8').replaceAll('import.meta.env', '__env'),
  { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } },
).outputText

const headers = {
  cid: 'channel', token: 'channel-token', 'terminal-id': 'terminal',
  'entity-id': 'entity', 'entity-info-id': 'entity-info',
}

for (const scenario of [
  { name: 'default', dev: false, expected: 'knowage' },
  { name: 'root .env for local development', dev: true, env: 'local-instance', expected: 'local-instance' },
  { name: 'runtime overrides build', dev: false, env: 'build-instance', runtime: 'deployment-instance', expected: 'deployment-instance' },
  { name: 'empty runtime falls back to build', dev: false, env: 'build-instance', runtime: '', expected: 'build-instance' },
  { name: 'blank configuration', dev: true, env: '  ', runtime: '  ', expected: 'knowage' },
  { name: 'trim whitespace', dev: false, runtime: '  deployment-instance  ', expected: 'deployment-instance' },
]) {
  test(`Sumfen auto-login sends instance_id from ${scenario.name}`, async () => {
    const calls: Array<{ url: string, options: RequestInit }> = []
    const raw = { token: 'login-token', user: { id: 'user' }, active_tenant: { id: 1 } }
    const exports = {} as { sumfenAutoLogin: typeof sumfenAutoLogin }
    runInNewContext(compiled, {
      exports,
      __env: { DEV: scenario.dev },
      __SUMFEN_INSTANCE_ID__: scenario.env,
      window: { __RUNTIME_CONFIG__: scenario.runtime === undefined ? undefined : { SUMFEN_INSTANCE_ID: scenario.runtime } },
      require(name: string) {
        if (name === '@/utils/request') return {}
        if (name === '@/i18n') return { default: { global: { t: (key: string) => key } } }
        throw new Error(`Unexpected import: ${name}`)
      },
      fetch: async (url: string, options: RequestInit) => {
        calls.push({ url, options })
        return { json: async () => ({ code: 1, data: { token: 'login-token', raw } }) }
      },
    })
    const result = await exports.sumfenAutoLogin(headers)
    assert.equal(result.success, true)
    assert.equal(result.loginData, raw)
    assert.equal(calls.length, 1)
    assert.equal(calls[0].url, scenario.dev
      ? '/sumfen-api/api/support/llm/weknora/login'
      : 'https://api.sumfen.com/api/support/llm/weknora/login')
    assert.equal(calls[0].options.method, 'POST')
    assert.deepEqual(JSON.parse(String(calls[0].options.body)), { instance_id: scenario.expected })
    assert.deepEqual({ ...calls[0].options.headers }, { 'Content-Type': 'application/json', ...headers })
  })
}
