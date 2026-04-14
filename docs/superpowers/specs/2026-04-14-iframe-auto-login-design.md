# WeKnora iframe 嵌入免登 + 前端品牌清理 设计文档

**日期**：2026-04-14
**作者**：chinesehui + Claude
**状态**：待实施

---

## 1. 背景与目标

WeKnora 需要作为 iframe 嵌入外部自维护的业务系统。外部系统为每个组织生成一条签名 URL，用户进入 WeKnora 时无需再次登录，由 URL 中的 `cid`（组织 ID）+ `mobile`（手机号）自动完成租户与用户的按需创建并签发 JWT。同时，嵌入场景下需要隐藏 WeKnora 自身的 logo、外链（GitHub / 官网 / 文档）、语言切换器等品牌元素。

两个可独立交付但在本期一并实现的子需求：

- **R1 iframe 免登**：URL 带 `cid + mobile + ts + nonce + sig` → 自动鉴权 → 发 JWT → 进入应用主页。
- **R2 前端嵌入模式**：URL 进入后置位 embedded 标志，所有 logo/外链/语言切换器按标志隐藏；独立部署访问路径保持原样。

## 2. 关键决策（已在 brainstorming 阶段确认）

| # | 决策 | 结论 | 理由 |
|---|---|---|---|
| D1 | `cid` 映射到什么？ | Tenant（租户）ID | 跨 cid 数据**完全隔离**；同一 mobile 在不同 cid 下视为不同账号 |
| D2 | iframe 鉴权模型 | 共享密钥 + HMAC 签名 URL | 不额外开发换票接口，URL 失效靠 nonce 一次性 |
| D3 | secret 粒度 | 每个 cid 一把 | 外部多系统接入，泄漏面可控 |
| D4 | 前端隐藏策略 | 运行时 embedded 开关 | 保留独立部署入口；开关关闭时完全等价于当前版本 |
| D5 | 会话过期 | JWT 7 天长期有效 | 过期后父系统刷新 iframe src |
| D6 | 多语言 | 保留 i18n 基础设施，隐藏切换器，嵌入模式锁 zh-CN | 工作量和需求匹配 |
| D7 | tenant 自动创建 | **不**自动创建；必须通过 CLI 预先 provision | 管理面动作走管理面，避免任意创建 |
| D8 | 签名时间窗 | **不校验 ts 新鲜度** | 父系统自身 auth 过期会重跳；iframe URL 过期不是安全边界 |
| D9 | nonce 存储 | DB 表 `iframe_nonces` + 定时清理 | 30+ 天 TTL 用 Redis 风险大；Lite 同表 |

## 3. 架构

```
┌──────────────────────────────────────────────────────────────┐
│  外部业务系统（自维护，持有本 cid 对应的 iframe_secret）           │
│    生成签名 URL → 渲染 <iframe src="...">                      │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
       /iframe-login?cid=X&mobile=Y&ts=..&nonce=..&sig=..
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  WeKnora Frontend                                            │
│    路由 /iframe-login → IframeLogin.vue                       │
│      1. embeddedStore.enable()  (sessionStorage)              │
│      2. POST /api/v1/auth/iframe-login  (透传 query)          │
│      3. 保存 token，router.replace('/platform/knowledge-bases') │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  WeKnora Backend  (Gin + dig)                                 │
│    POST /api/v1/auth/iframe-login  (middleware 免鉴权白名单)    │
│      → UserService.IframeLogin(ctx, req)                       │
│        1. 查 tenant by external_id → 不存在返回 404             │
│        2. tenant.iframe_secret 非空 → 校验 HMAC-SHA256          │
│        3. 插入 iframe_nonces（tenant_id, nonce）→ 冲突返回 replay │
│        4. 查 user by (tenant_id, mobile) → 不存在则创建占位用户   │
│        5. generateTokens(user) → 7 天 JWT                      │
│        6. 返回 LoginResponse                                   │
└──────────────────────────────────────────────────────────────┘

                ╔══════════════════════════════════╗
                ║  weknora-admin  (新增 CLI 二进制)   ║
                ║  iframe provision --cid X --name Y  ║
                ║    └→ 创建 tenant + 生成 secret     ║
                ║  iframe rotate --cid X              ║
                ║  iframe revoke --cid X              ║
                ╚══════════════════════════════════╝
```

## 4. 数据模型变更

### 4.1 `users` 表

| 变更 | 说明 |
|---|---|
| 新增列 `mobile VARCHAR(20) NULL` | 国际区号最长 16 位，留余量 |
| 新增唯一索引 `uk_users_tenant_mobile` | `(tenant_id, mobile) WHERE mobile IS NOT NULL AND deleted_at IS NULL`（Postgres 部分索引；MySQL 走联合唯一索引 + 应用层保证 NULL 不写入） |
| `email` / `username` | 维持全局唯一不变；iframe 创建时填充占位值 |

### 4.2 `tenants` 表

| 变更 | 说明 |
|---|---|
| 新增列 `external_id VARCHAR(128) NULL` | 业务 cid；唯一索引允许 NULL |
| 新增列 `iframe_secret TEXT NULL` | 明文 32 字节 hex（64 字符），存库前由 `Tenant.BeforeSave` 走 AES-256-GCM 加密，读出时 `AfterFind` 解密——复用现有 `api_key` 加密机制 |
| 新增唯一索引 `uk_tenants_external_id` | `external_id WHERE external_id IS NOT NULL AND deleted_at IS NULL` |

### 4.3 `iframe_nonces` 表（新增）

```sql
CREATE TABLE iframe_nonces (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   BIGINT      NOT NULL,
    nonce       VARCHAR(64) NOT NULL,
    ts          BIGINT      NOT NULL,      -- URL 里的时间戳，用于清理
    consumed_at TIMESTAMP   NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, nonce)
);
CREATE INDEX idx_iframe_nonces_ts ON iframe_nonces(ts);
```

- 消费 URL 时：`INSERT ... ON CONFLICT DO NOTHING`；影响行数为 0 视为重放
- 定时清理：每天删 `ts < now - 90 天` 的老记录（容器 cleanup 或 Asynq 任务）

### 4.4 占位用户字段规则

iframe 自动创建的用户填充：

| 字段 | 值 |
|---|---|
| `id` | `uuid.NewString()` |
| `username` | `iframe_{tenant_id}_{mobile}` |
| `email` | `iframe_{tenant_id}_{mobile}@iframe.invalid`（RFC 2606 保留域） |
| `password_hash` | `bcrypt(random 32 bytes)`（不可用于密码登录） |
| `mobile` | 原样 |
| `tenant_id` | 查到的 tenant.id |
| `is_active` | `true` |
| `can_access_all_tenants` | `false` |

## 5. HMAC 签名协议

### 5.1 URL 参数

```
/iframe-login
    ?cid=ACME-2024
    &mobile=13812345678
    &ts=1713081234
    &nonce=8f3a1c9b4d2e7f01
    &sig=<64 hex>
```

### 5.2 算法

```
message = "cid={cid}&mobile={mobile}&nonce={nonce}&ts={ts}"   # 字段按字典序
secret  = tenants.iframe_secret 解密后的明文
sig     = hex(HMAC-SHA256(secret, message))
```

- 字段按**字典序升序**（`cid < mobile < nonce < ts`）拼接，键名键值原样不 URL 编码
- 签名失败用 `hmac.Equal` 做常量时间比较

### 5.3 服务端校验顺序

1. 5 个字段完整性，`mobile` 正则 `^\+?[0-9]{6,20}$`
2. 查 tenant by external_id；不存在 → 404 `IFRAME_TENANT_NOT_FOUND`
3. tenant.iframe_secret 非空；空 → 403 `IFRAME_NOT_ENABLED`
4. HMAC 校验；不等 → 401 `IFRAME_BAD_SIGNATURE`
5. `INSERT INTO iframe_nonces ... ON CONFLICT DO NOTHING`；0 行 → 401 `IFRAME_REPLAY`
6. 查 user；存在但 is_active=false → 403 `IFRAME_USER_DISABLED`；不存在 → 创建
7. 签 7 天 JWT（复用 `UserService.generateTokens`），写 `auth_tokens` 表
8. 返回 `LoginResponse{success, user, tenant, token, refresh_token}`

### 5.4 外部系统生成 URL 的示例（文档用）

```python
import hmac, hashlib, time, secrets
def build_iframe_url(base, cid, mobile, secret):
    ts = str(int(time.time()))
    nonce = secrets.token_hex(16)
    msg = f"cid={cid}&mobile={mobile}&nonce={nonce}&ts={ts}"
    sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return (f"{base}/iframe-login?cid={cid}&mobile={mobile}"
            f"&ts={ts}&nonce={nonce}&sig={sig}")
```

## 6. weknora-admin CLI 工具

新增二进制 `cmd/weknora-admin/main.go`，复用 `container.BuildContainer` 获取 DB/config。

| 子命令 | 作用 |
|---|---|
| `iframe provision --cid X --name Y` | 创建 tenant（external_id=X, name=Y）+ 生成 `crypto/rand` 32 字节 hex secret，加密存库，**stdout 打印明文一次** |
| `iframe rotate --cid X` | 重新生成 secret，旧 secret 立即失效（所有已签 URL 作废） |
| `iframe revoke --cid X` | 将 `iframe_secret` 置 NULL，iframe-login 返回 403 `IFRAME_NOT_ENABLED` |

Makefile 加 `build-admin` 目标：`go build -o weknora-admin ./cmd/weknora-admin`

## 7. 前端 embedded 模式

### 7.1 Pinia store `frontend/src/stores/embedded.ts`

```ts
export const useEmbeddedStore = defineStore('embedded', {
  state: () => ({
    embedded: sessionStorage.getItem('weknora_embedded') === '1',
  }),
  actions: {
    enable() {
      this.embedded = true
      sessionStorage.setItem('weknora_embedded', '1')
    },
  },
})
```

sessionStorage 生命周期跟随 iframe tab；用户关闭自动清除。

### 7.2 新路由 `/iframe-login`

组件 `frontend/src/views/auth/IframeLogin.vue`：

1. 读 `route.query`，缺参展示"链接参数不完整"错误
2. `embeddedStore.enable()`
3. `i18n.global.locale.value = 'zh-CN'`
4. `api.auth.iframeLogin(params)` → 存 token 到 localStorage
5. `router.replace('/platform/knowledge-bases')`
6. 错误时按 `code` 显示对应中文文案

页面 UI：居中 loading spinner，无 logo。

### 7.3 路由守卫改动

`frontend/src/router/index.ts`：
- 新增路由 `{ path: '/iframe-login', component: IframeLogin, meta: { requiresAuth: false } }`
- `beforeEach`：如果 `embeddedStore.embedded && to.path === '/login'` → 跳 `/iframe-expired` 提示页（**不**回到独立登录界面）
- 不对 `/iframe-login` 本身做"已登录则跳走"的处理，允许覆盖旧 token

### 7.4 元素隐藏清单

实施阶段需用 grep 扫 `github.com`、`<img .*logo`、外链 `<a href="https?://`、`LanguageSwitcher` 等关键词，确认全部命中位置。已知：

| 位置 | 文件 | 隐藏方式 |
|---|---|---|
| 登录页左上 GitHub logo | `views/auth/Login.vue:96-98` | `v-if="!embedded"` |
| 登录页右上外链 + 语言切换器 | `views/auth/Login.vue:102-141` | `v-if="!embedded"` |
| 主布局 logo / 品牌文字 | `App.vue` + layout 组件 | `v-if="!embedded"` |
| 设置页"关于"区 | 待核实 | `v-if="!embedded"` |
| 404/错误页 logo | 待核实 | `v-if="!embedded"` |
| 浏览器 title | 不动 | — |

composable `frontend/src/composables/useEmbedded.ts` 暴露 `{ embedded }`，组件 `v-if="!embedded"`。

### 7.5 CSP 响应头

新增中间件 `internal/middleware/frame_ancestors.go`：
- 读 env `WEKNORA_FRAME_ANCESTORS`
- 非空 → 加 `Content-Security-Policy: frame-ancestors <value>` 响应头
- 空 → 不加（允许任意嵌入，适合内网）
- **不设 `X-Frame-Options`**（与 CSP 冲突时浏览器行为不一致）

## 8. 错误响应契约

统一格式 `{ success: false, code: "IFRAME_*", message: "..." }`。

| HTTP | code | 前端文案 |
|---|---|---|
| 400 | `IFRAME_PARAMS_MISSING` | 链接参数不完整，请联系系统管理员 |
| 400 | `IFRAME_MOBILE_INVALID` | 手机号格式非法 |
| 401 | `IFRAME_BAD_SIGNATURE` | 鉴权失败 |
| 401 | `IFRAME_REPLAY` | 请求重复，请重新发起 |
| 403 | `IFRAME_USER_DISABLED` | 账号已被禁用 |
| 403 | `IFRAME_NOT_ENABLED` | 该组织未启用 iframe 登录 |
| 404 | `IFRAME_TENANT_NOT_FOUND` | 组织未开通，请联系系统管理员 |
| 500 | `IFRAME_INTERNAL` | 服务暂时不可用 |

## 9. 日志与限流

### 9.1 日志

- 成功：`INFO iframe_login.success tenant_id=42 user_id=<uuid> mobile_suffix=5678 is_new_user=true`
- 失败：`WARN iframe_login.reject code=IFRAME_BAD_SIGNATURE cid=ACME ip=1.2.3.4`
- `mobile` 只打后 4 位，cid 完整打

### 9.2 速率限制

同一 IP 连续 5 次 `IFRAME_BAD_SIGNATURE` → 冷却 60 秒。
**只计 BAD_SIGNATURE**，`IFRAME_REPLAY` / `IFRAME_TENANT_NOT_FOUND` / `IFRAME_PARAMS_MISSING` 等**不计数**——这些都可能由用户正常交互触发（后退按钮、错配 cid 等），限流会误伤。REPLAY 虽然也是"异常"，但只要 secret 未泄漏就无法构造其他非法 URL，限它意义不大。

实现放在 iframe-login handler 内部（不在全局中间件），用 `golang.org/x/time/rate` 每 IP 限流器（内存 LRU 保存，进程重启清零即可）。多实例部署时允许窗口翻倍，不追求严格分布式一致。

## 10. 安全风险与缓解

| 风险 | 缓解 |
|---|---|
| secret 泄漏 | 存库加密；CLI 仅打印一次；支持 `rotate` 作废历史 URL |
| URL 被窃取（浏览器历史、日志） | nonce 一次性消费；无法被再次使用 |
| URL 抢跑 | nonce 冲突拒绝；合法用户失败后父系统重签 |
| 伪造 cid 创建野 tenant | iframe-login **不**自动建 tenant，tenant 必须经 CLI provision |
| 跨 cid 横向探测 mobile | (tenant_id, mobile) 隔离，无全局 mobile 索引 |
| 签名常量时间比较 | 使用 `hmac.Equal` / `subtle.ConstantTimeCompare` |
| 爆破 secret | IP 级 5次/60s 冷却 |
| JWT 盗用 | 复用现有 JWT 风险；7 天过期，手工 revoke 通过吊销 `auth_tokens.is_revoked` |

## 11. 测试策略

### 11.1 单元测试

- `internal/application/service/iframe_auth_test.go`
  - HMAC 签名对称
  - 任一字段篡改（cid/mobile/ts/nonce）→ 签名失效
  - query 顺序打乱 → 结果一致（字典序保证）
  - nonce 二次消费 → 被拒

- `internal/application/service/user_iframe_login_test.go`
  - tenant 不存在 → `IFRAME_TENANT_NOT_FOUND`
  - iframe_secret NULL → `IFRAME_NOT_ENABLED`
  - user 不存在 → 创建（断言占位字段）
  - user 存在 is_active=false → `IFRAME_USER_DISABLED`
  - 成功 → 返回 LoginResponse 且 JWT 有效

### 11.2 集成测试

- `internal/handler/auth_test.go` 扩展：
  - 端到端：provision → 生成 URL → POST → 200 + 合法 JWT
  - rotate 后旧 URL → `IFRAME_BAD_SIGNATURE`
  - revoke 后同 URL → `IFRAME_NOT_ENABLED`

### 11.3 手工验收步骤

1. `make build-admin && ./weknora-admin iframe provision --cid T1 --name "Test Org"`
2. 用文档里 Python 示例生成 URL（secret 从上一步 stdout 取）
3. 浏览器访问 URL → 跳转到 `/platform/knowledge-bases`，页面无 logo/外链/语言切换器
4. 查 DB：`SELECT * FROM users WHERE tenant_id=<T1.id>`，新行字段符合规则
5. **同一个 URL 再用第二次** → 401 `IFRAME_REPLAY`
6. 修改 `sig` 任一字符 → 401 `IFRAME_BAD_SIGNATURE`
7. 独立访问 `/login` → 页面**仍显示** logo/外链（embedded=false）
8. 父系统场景：修改 `WEKNORA_FRAME_ANCESTORS=https://parent.test` → 浏览器 devtools 查响应头

### 11.4 前端

项目当前无前端测试框架，不强求，依赖手工验收。

## 12. 回滚方案

- 迁移提供完整 `.down.sql`：`make migrate-down` 回退
- 代码改动分 commit 粒度以便 revert：后端 handler、前端组件、CLI 工具各自独立 commit
- 前端 `embedded` 默认 false，后端挂掉不影响独立登录
- tenant.iframe_secret 为 NULL 视为未启用，不影响存量 tenant

## 13. 文档产出

实施期间同步产出：
- `docs/iframe-integration.md` — 外部系统接入文档（含签名示例、provisioning 流程、错误码）
- 更新 `docs/api/` Swagger 注解 → `make docs` 重新生成

## 14. 非目标（本期不做）

- postMessage 双向通信（语言联动、会话过期通知）
- 管理端 REST API（provision/rotate/revoke），本期仅 CLI
- mobile 变更接口（占位邮箱用户的二次绑定）
- 监控 Prometheus 指标（日志字段已留够，后续可采）
- 多语言在 embedded 下动态切换（当前锁 zh-CN）

## 15. 实施范围清单

### 后端文件改动

| 文件 | 类型 |
|---|---|
| `migrations/versioned/000035_iframe_login.up.sql` | 新增 |
| `migrations/versioned/000035_iframe_login.down.sql` | 新增 |
| `migrations/mysql/000035_*.sql` | 新增 |
| `migrations/sqlite/000000_init.up.sql` | 修改（合并新字段） |
| `internal/types/user.go` | 增加 `Mobile` 字段 |
| `internal/types/tenant.go` | 增加 `ExternalID` `IframeSecret` 字段 + 加解密钩子 |
| `internal/types/iframe_login.go` | 新增 DTO |
| `internal/types/interfaces/user.go` | 接口增加 `IframeLogin` |
| `internal/application/repository/user_repository.go` | 增 `GetByTenantAndMobile` |
| `internal/application/repository/tenant_repository.go` | 增 `GetByExternalID` / secret 写回 |
| `internal/application/repository/iframe_nonce_repository.go` | 新增 |
| `internal/application/service/iframe_auth.go` | 新增 HMAC + nonce 校验 |
| `internal/application/service/user.go` | 增 `IframeLogin` 方法 |
| `internal/handler/auth.go` | 增 `IframeLogin` handler |
| `internal/middleware/auth.go` | 白名单加 `/auth/iframe-login` |
| `internal/middleware/frame_ancestors.go` | 新增 |
| `internal/router/router.go` | 挂载路由 + 中间件 |
| `internal/container/container.go` | 注入新 repository/service |
| `cmd/weknora-admin/main.go` | 新增 |
| `Makefile` | 增 `build-admin` |

### 前端文件改动

| 文件 | 类型 |
|---|---|
| `frontend/src/views/auth/IframeLogin.vue` | 新增 |
| `frontend/src/stores/embedded.ts` | 新增 |
| `frontend/src/composables/useEmbedded.ts` | 新增 |
| `frontend/src/api/auth.ts` | 增 `iframeLogin` |
| `frontend/src/router/index.ts` | 加路由 + 守卫 |
| `frontend/src/views/auth/Login.vue` | logo/外链条件渲染 |
| `frontend/src/App.vue` 及各 layout 组件 | 条件渲染 |
| 设置页"关于"区（待定位） | 条件渲染 |

### 文档

- `docs/iframe-integration.md` 新增
- `docs/api/` Swagger 注解更新

## 16. 配置项（新增环境变量）

| 名 | 默认 | 说明 |
|---|---|---|
| `WEKNORA_FRAME_ANCESTORS` | 空 | 非空则设 CSP `frame-ancestors` 允许的父域，多个以空格分隔；空时允许任意域嵌入 |

无其他新增 env。`WEKNORA_JWT_SECRET` 等沿用现有。
