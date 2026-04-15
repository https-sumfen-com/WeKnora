# WeKnora iframe 嵌入接入指南

本文档面向自维护的外部业务系统，说明如何将 WeKnora 作为 iframe 嵌入并免登。

## 概念

WeKnora 的 iframe 嵌入走 HMAC 签名 URL 免登流程：
- `cid` 对应一个 **Organization**（共享空间），而不是 tenant
- 每个 `(cid, mobile)` 会创建一个独立的 **Tenant**（个人工作空间）
- 用户通过 OrganizationMember 加入 org，角色由 URL 的 `role` 参数决定
- 同一 org 下的成员可以通过原生"共享空间"能力共享知识库和智能体（由管理员在 WeKnora 前端配置）
- 同一 org 下用户数据按**个人 tenant** 隔离（不同 mobile 互相看不到对话/知识库）
- 跨 org（不同 cid）之间数据完全隔离
- WeKnora 按 `(cid, mobile)` 查找用户，不存在时自动创建个人 tenant + 用户 + OrganizationMember
- 同一 iframe URL 只能消费一次（nonce 防重放）

## 运行模式（两选一）

**模式 A · master secret 自动 provision（推荐，适合外部系统动态生成 cid 的场景）**
- 在 WeKnora 部署 `.env` 设 `WEKNORA_IFRAME_MASTER_SECRET=<hex 64>`
- 外部系统用**同一把** master 派生 per-cid secret：`derived = HMAC-SHA256(master, cid)`
- 用 `derived` 签 URL 消息
- 未知 cid 首次访问时 WeKnora 用同公式重算 `derived` 验签，通过后**自动创建** org
- 无需运维手动 provision，cid 可实时生成

**模式 B · 每 cid 独立 secret（更严格的安全边界，适合 cid 数量少且可预知）**
- 运维为每个 cid 执行 `weknora-admin iframe provision --cid X --name Y` 获取独立 secret
- 外部系统为每个 cid 存对应 secret
- 单 cid 泄漏不影响其他 cid；可单独 rotate

两种模式可共存：已 provision 的 org 用自己的 stored secret，未 provision 的走 master 派生。

## 1. 前置步骤（运维，在 WeKnora 部署机上执行）

### 1.A 模式 A：设置 master secret（推荐）

在 `.env` 中加：
```bash
# 生成：openssl rand -hex 32
WEKNORA_IFRAME_MASTER_SECRET=<64-char hex>
```
重启 backend 使其生效。通过**带外渠道**（密钥管理系统 / Secret Manager）告知所有外部业务系统；**严禁**放在外部系统前端代码里。

设置后未知 cid 首次访问即自动创建 org，无需每次 provision。

### 1.B 模式 B：为特定 cid 手动 provision

当某个 cid 需要独立 secret（不派生于 master），运维执行：
```bash
make build-admin
./weknora-admin iframe provision --cid ACME-2024 --name "ACME 公司"
# 输出（仅显示一次，请妥善保存）:
#   Organization created: id=<uuid>, external_id=ACME-2024
#   iframe_secret (SAVE THIS, shown only once):
#   ────────────────────────────────────────
#   <64-char hex secret>
#   ────────────────────────────────────────
```

### 1.C 轮换与吊销（两种模式通用）

轮换单 cid secret（怀疑泄漏或定期轮换）：
```bash
./weknora-admin iframe rotate --cid ACME-2024
# 原 secret 立即失效；该 cid 之前签发的所有 URL 立即无法再使用
# 若用模式 A，轮换后这个 cid 用的是新 stored secret，不再等于 master 派生值
```

吊销（禁用某 cid 的 iframe 登录）：
```bash
./weknora-admin iframe revoke --cid ACME-2024
# iframe_secret 置空；iframe-login 端点返回 IFRAME_NOT_ENABLED
# 即使 master secret 已配置，也不会重新自动创建（org 行仍在，块自动 provision）
```

Master 全局轮换：改 `.env` 的 `WEKNORA_IFRAME_MASTER_SECRET` → 重启 backend。
- 尚未手动 rotate 的 org 仍用旧 derived secret，照常工作（不影响已有 URL）
- 新 cid 用新 master 派生
- 彻底失效所有旧 URL：需对每个 org 执行 `iframe rotate`

## 2. 签名协议

URL 格式：
```
https://weknora.example.com/iframe-login
    ?company_id=ACME-2024
    &c_name=ACME 公司
    &mobile=13812345678
    &role=editor
    &ts=<unix 时间戳>
    &nonce=<随机 hex 16+ 字符>
    &sig=<hex 64 字符 HMAC-SHA256>
```

签名消息（字段按**字典序**升序拼接，值不做 URL 编码）：
```
c_name={c_name}&cid={company_id}&mobile={mobile}&nonce={nonce}&role={role}&ts={ts}
```
- URL 上这个字段叫 `company_id`，签名 canonical message 里的 key 仍是 `cid`（两边指的是同一个值——组织业务标识）
- `c_name` 排在 `cid` 前是因 ASCII 中 `_` (0x5F) < `i` (0x69)

签名：
```
sig = hex( HMAC-SHA256(secret, message) )
```

参数要求：
- `company_id` 必填，组织业务标识（稳定、大小写敏感）。**签名消息里这个字段仍写作 `cid=`，仅 URL 参数名叫 `company_id`。**
- `c_name` 必填，共享空间（Organization）人类可读显示名——模式 A 自动 provision 时作为 `organizations.name` 存入；已存在的 org 以**数据库里的 name 为准**（不会被 URL 覆盖，如需改名走 WeKnora 前端或 CLI）
- `mobile` 必须是中国大陆 11 位手机号，正则 `^1[3-9][0-9]{9}$`
- `role` 必填，取值 `admin` / `editor` / `viewer`，决定 user 加入 organization 时的权限。父系统为 URL 源头，每次登录 WeKnora 会同步更新用户在该 org 的角色
- `ts` 必须是整数字符串（Unix 秒时间戳）
- `nonce` 任意字符串，建议 16-32 字符 hex 或 base62 随机值
- `sig` 必须是 hex 编码的 64 字符（对应 32 字节 HMAC-SHA256 输出）

注意：**ts 不做新鲜度校验**——WeKnora 不拒绝"旧时间戳"的 URL。防重放完全依赖 nonce 一次性消费。

## 3. 参考实现

下面示例覆盖两种模式：
- **模式 A**：传 master secret，函数内部先 `derived = HMAC(master, cid)` 再签 URL
- **模式 B**：直接传 provision 得到的 per-cid secret

### Python

```python
import hmac, hashlib, time, secrets

from urllib.parse import quote

def derive_secret(master: str, cid: str) -> str:
    """模式 A 用：master secret 派生 per-cid secret。与 WeKnora 后端公式一致。"""
    return hmac.new(master.encode(), cid.encode(), hashlib.sha256).hexdigest()

def build_iframe_url(base_url: str, cid: str, c_name: str, mobile: str, role: str, secret: str) -> str:
    """secret 可以是 master 派生的 derived（模式 A）或 provision 得到的 per-cid secret（模式 B）。"""
    ts = str(int(time.time()))
    nonce = secrets.token_hex(16)
    # 字典序：c_name < cid < mobile < nonce < role < ts（_ < i in ASCII）
    msg = f"c_name={c_name}&cid={cid}&mobile={mobile}&nonce={nonce}&role={role}&ts={ts}"
    sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    # URL 上值需要 URL 编码（c_name 可能有中文/空格）
    # 注意：URL 查询参数名是 company_id，但签名消息里仍用 cid=
    return (
        f"{base_url}/iframe-login?company_id={quote(cid)}&c_name={quote(c_name)}"
        f"&mobile={mobile}&role={role}&ts={ts}&nonce={nonce}&sig={sig}"
    )

# 模式 A 用法（推荐）：外部系统只存 master 一把 key
MASTER = "<WEKNORA_IFRAME_MASTER_SECRET 同一值>"
cid = "ACME-2024"
url = build_iframe_url(
    "https://weknora.example.com",
    cid, "ACME 公司", "13812345678", "editor",
    derive_secret(MASTER, cid),
)

# 模式 B 用法：外部系统持有 per-cid secret
url = build_iframe_url(
    "https://weknora.example.com",
    "ACME-2024", "ACME 公司", "13812345678", "editor",
    "<64-char secret from weknora-admin provision>",
)
# 在外部系统模板里：<iframe :src="url" ...>
```

### Node.js

```js
const crypto = require('crypto');

function deriveSecret(master, cid) {
  return crypto.createHmac('sha256', master).update(cid).digest('hex');
}
  /*
    c_name  团队名称
    cid     平台cid+用户体系+团队
    mobile   账号手机号
    role    'admin' | 'editor'

 */


function buildIframeUrl(baseUrl, cid, cName, mobile, role, secret) {
  const ts = Math.floor(Date.now() / 1000).toString();
  const nonce = crypto.randomBytes(16).toString('hex');
  // 字典序：c_name < cid < mobile < nonce < role < ts

  const msg = `c_name=${cName}&cid=${cid}&mobile=${mobile}&nonce=${nonce}&role=${role}&ts=${ts}`;
  const sig = crypto.createHmac('sha256', secret).update(msg).digest('hex');
  // URL 查询参数名是 company_id，签名消息里仍用 cid=
  const qs = new URLSearchParams({ company_id: cid, c_name: cName, mobile, role, ts, nonce, sig });
  return `${baseUrl}/iframe-login?${qs.toString()}`;
}

// 示例
const MASTER = 'bf09f51aeca6c93d3cbe5be3600e2aaf4317c94840aba9689';
const cid = '1000-158-1';
const url = buildIframeUrl(
  'http://localhost:5173',
  cid, '甜菜团队', '13726214776', 'admin',
  deriveSecret(MASTER, cid),
);

console.log(url);
```

### Go

```go
package iframe

import (
    "crypto/hmac"
    "crypto/rand"
    "crypto/sha256"
    "encoding/hex"
    "fmt"
    "time"
)

import "net/url"

// DeriveSecret 模式 A 用：master 派生 per-cid secret。
func DeriveSecret(master, cid string) string {
    h := hmac.New(sha256.New, []byte(master))
    h.Write([]byte(cid))
    return hex.EncodeToString(h.Sum(nil))
}

// BuildIframeURL 的 secret 参数可以是派生值（模式 A）或 provision 得到的值（模式 B）。
func BuildIframeURL(baseURL, cid, cName, mobile, role, secret string) string {
    ts := fmt.Sprintf("%d", time.Now().Unix())
    nonceBytes := make([]byte, 16)
    _, _ = rand.Read(nonceBytes)
    nonce := hex.EncodeToString(nonceBytes)
    // 字典序：c_name < cid < mobile < nonce < role < ts
    msg := "c_name=" + cName + "&cid=" + cid + "&mobile=" + mobile +
        "&nonce=" + nonce + "&role=" + role + "&ts=" + ts
    h := hmac.New(sha256.New, []byte(secret))
    h.Write([]byte(msg))
    sig := hex.EncodeToString(h.Sum(nil))
    q := url.Values{}
    // URL 查询参数名是 company_id，签名消息里仍用 cid=
    q.Set("company_id", cid); q.Set("c_name", cName); q.Set("mobile", mobile)
    q.Set("role", role); q.Set("ts", ts); q.Set("nonce", nonce); q.Set("sig", sig)
    return baseURL + "/iframe-login?" + q.Encode()
}
```

## 4. 错误码

`POST /api/v1/auth/iframe-login` 响应体统一格式：

```json
{
  "success": false,
  "code": "IFRAME_*",
  "message": "..."
}
```

| HTTP | code | 处理建议 |
|---|---|---|
| 400 | `IFRAME_PARAMS_MISSING` | 检查 URL 参数是否齐全、ts 是否为整数 |
| 400 | `IFRAME_MOBILE_INVALID` | 手机号须为中国大陆 11 位，正则 `^1[3-9][0-9]{9}$` |
| 400 | `IFRAME_ROLE_INVALID` | role 必须是 admin / editor / viewer |
| 401 | `IFRAME_BAD_SIGNATURE` | secret 不对、签名拼接顺序错误，或 message 做了 URL 编码 |
| 401 | `IFRAME_REPLAY` | 同一 URL 不可复用——父系统每次渲染 iframe 都要重新生成 nonce |
| 403 | `IFRAME_USER_DISABLED` | 用户被管理员禁用，联系 WeKnora 管理员 |
| 403 | `IFRAME_NOT_ENABLED` | 对应 cid 已 revoke（org 行存在但 secret 清空）。即使配置了 master secret 也不会自动重建，运维需 `iframe rotate` 或删 org |
| 404 | `IFRAME_TENANT_NOT_FOUND` | cid 未开通。若用模式 A：检查 `WEKNORA_IFRAME_MASTER_SECRET` 是否配置、签名是否用正确的 derived secret。若用模式 B：运维执行 `weknora-admin iframe provision` |
| 429 | `IFRAME_BAD_SIGNATURE` | 同一 IP 连续 5 次签名失败后触发冷却，60 秒后可重试 |
| 500 | `IFRAME_INTERNAL` | WeKnora 内部错误，查服务端日志 |

## 5. 会话管理

- WeKnora 签发 **24h access token + 7d refresh token**，前端存 `localStorage`
- 用户关闭 iframe tab 后 `sessionStorage.weknora_embedded` 标志自动清除；下次新 URL 进入会重新激活 embedded 模式
- access token 过期时，前端会用 refresh token 自动续期——父系统无需介入
- 父系统自身会话过期时，由父系统负责导走用户；**WeKnora 不主动校验父系统状态**
- **用户主动切换 cid**：父系统直接用新 cid 生成新 URL 加载 iframe，WeKnora 会覆盖旧 token

## 6. 嵌入模式 UI 说明

访问 `/iframe-login` 后，前端在 `sessionStorage` 置位 `weknora_embedded=1`，整个 tab 生命周期内：
- 登录页 / 主应用 / 设置页的 **所有 logo / GitHub 链接 / 官网链接 / 文档链接 / 语言切换器** 都自动隐藏
- 语言固定为简体中文（`zh-CN`），不受浏览器 `Accept-Language` 影响
- 独立直接访问 `/login` 不受影响，logo 和外链照常显示

## 7. 父域名白名单（可选）

默认任意父域名都可把 WeKnora 嵌入 iframe（适合内网）。要限制允许嵌入的父域名，在 WeKnora 部署环境变量里设：

```bash
WEKNORA_FRAME_ANCESTORS="https://parent.example.com https://another.example.com"
```

多个父域名用空格分隔。设置后 WeKnora 会加响应头：
```
Content-Security-Policy: frame-ancestors https://parent.example.com https://another.example.com
```

浏览器会拒绝把 WeKnora 嵌入到白名单外的页面。

## 8. 安全注意事项

- **secret 长度固定 64 hex 字符**（32 字节）：`openssl rand -hex 32` 生成
- 严禁在外部系统前端 JS / HTML 中持有 secret / master——只应在后端服务器上签 URL
- 父系统应**每次渲染 iframe 时生成新的 nonce**，同一 URL 不支持复用
- 单 cid 怀疑泄漏：`weknora-admin iframe rotate --cid X`——无需重启 WeKnora
- **Master secret 泄漏 = 所有 cid 失守**，是模式 A 的固有风险。缓解：强随机生成、严格限制只部署机 .env + 外部系统 secret manager 持有；定期轮换（轮换需协调所有外部系统同步更新）
- 数据库里 `organizations.iframe_secret` 是 AES-256-GCM 加密存储的，即使 DB 泄漏 secret 也不会裸露（前提是 `SYSTEM_AES_KEY` 未泄漏）
- iframe URL 会出现在浏览器历史、访问日志、Referer 里——风险靠 "nonce 一次性" 缓解，不靠 URL 机密性

## 9. 故障排查

| 现象 | 排查点 |
|---|---|
| 401 IFRAME_BAD_SIGNATURE，但 secret 确认没错 | 检查签名消息字典序是否正确（`cid < mobile < nonce < role < ts`）；检查字段值是否做了 URL 编码后再签（应该原样） |
| 401 IFRAME_REPLAY，第一次就失败 | 父系统是否把同一 URL 复用（模板缓存、iframe reload 等）；给每次渲染都生成新 nonce |
| 403 IFRAME_NOT_ENABLED | org 已 revoke；运维 `iframe rotate` 恢复，或从数据库删除该 org 行以允许自动重建 |
| 404 IFRAME_TENANT_NOT_FOUND | **模式 A**：master env 未设置或 master 值不一致；检查外部系统派生公式 `HMAC(master, cid)` 是否和后端同一把 master。**模式 B**：cid 未 provision 或拼错（大小写敏感） |
| iframe 里完全白屏 | 打开浏览器 devtools → Console 看有无 CSP `frame-ancestors` 阻塞信息；Network 看 `/api/v1/auth/iframe-login` 响应是什么 |
| logo / 外链还在显示 | 检查 `sessionStorage.weknora_embedded` 是否为 `"1"`；如果是 `null`，说明 URL 没经过 `/iframe-login` 路由入口 |
| access token 很快过期 | 前端是否正确启用了 refresh 机制（现有 OIDC/密码登录用同一套），debug 可以手动观察 `localStorage.weknora_token` 是否在 24h 后被 refresh |

## 10. 版本

- v0.3.7（TBD）：
  - 初版 iframe 嵌入免登支持（迁移 000035：users.mobile / iframe_nonces 表）
  - cid → Organization 架构重构（迁移 000036：iframe_secret 从 tenant 移到 organization，sessions/KB 按 user-level personal tenant 隔离）
  - URL 必填 `role` 参数（admin/editor/viewer），父系统权威同步
  - 嵌入模式 UI 品牌隐藏 + 默认模板天工智农定制
  - **`WEKNORA_IFRAME_MASTER_SECRET` 自动 provision**（模式 A）
- 新环境变量：
  - `WEKNORA_IFRAME_MASTER_SECRET`（可选）：启用模式 A 自动 provision
  - `WEKNORA_FRAME_ANCESTORS`（可选）：限制允许嵌入的父域名

---

**相关文档**：
- [`docs/superpowers/specs/2026-04-14-iframe-auto-login-design.md`](superpowers/specs/2026-04-14-iframe-auto-login-design.md) — 完整设计文档
- [`docs/api/`](api/) — REST API 参考（含 iframe-login 端点 Swagger 注解）
