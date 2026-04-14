# WeKnora iframe 嵌入接入指南

本文档面向自维护的外部业务系统，说明如何将 WeKnora 作为 iframe 嵌入并免登。

## 概念

WeKnora 的 iframe 嵌入走 HMAC 签名 URL 免登流程：
- `cid` 对应一个 **Organization**（共享空间），而不是 tenant
- 每个 `(cid, mobile)` 会创建一个独立的 **Tenant**（个人工作空间）
- 用户通过 OrganizationMember 加入 org，角色由 URL 的 `role` 参数决定
- 同一 org 下的成员可以通过原生"共享空间"能力共享知识库和智能体（由管理员在 WeKnora 前端配置）
- 每个 `cid` 独立持有一把 HMAC secret，外部系统用它给 URL 签名
- 同一 `cid` 下的用户数据完全隔离，不同 `cid` 之间无法互相访问
- WeKnora 按 `(cid, mobile)` 查找用户，不存在时自动创建占位用户并签发 JWT
- 同一 iframe URL 只能消费一次（nonce 防重放）

## 1. 前置步骤（运维，在 WeKnora 部署机上执行）

在 WeKnora 部署机上预先为每个组织创建 tenant 并生成 iframe secret：

```bash
make build-admin
./weknora-admin iframe provision --cid ACME-2024 --name "ACME 公司"
# 输出（仅显示一次，请妥善保存）:
#   Tenant created: id=N, external_id=ACME-2024
#   iframe_secret (SAVE THIS, shown only once):
#   ────────────────────────────────────────
#   <64-char hex secret>
#   ────────────────────────────────────────
```

轮换（怀疑泄漏或定期轮换时）：
```bash
./weknora-admin iframe rotate --cid ACME-2024
# 原 secret 立即失效，之前签发的所有 URL 立即无法再使用
```

吊销（暂停 iframe 登录功能）：
```bash
./weknora-admin iframe revoke --cid ACME-2024
# iframe_secret 置空；iframe-login 端点返回 IFRAME_NOT_ENABLED
```

拿到 secret 后通过**带外渠道**（密钥管理系统 / 环境变量 / Secret Manager）告知对应的外部系统；**严禁**放在外部系统前端代码里。

## 2. 签名协议

URL 格式：
```
https://weknora.example.com/iframe-login
    ?cid=ACME-2024
    &mobile=13812345678
    &role=editor
    &ts=<unix 时间戳>
    &nonce=<随机 hex 16+ 字符>
    &sig=<hex 64 字符 HMAC-SHA256>
```

签名消息（字段按**字典序**升序拼接，值不做 URL 编码）：
```
cid={cid}&mobile={mobile}&nonce={nonce}&role={role}&ts={ts}
```

签名：
```
sig = hex( HMAC-SHA256(secret, message) )
```

参数要求：
- `mobile` 必须是中国大陆 11 位手机号，正则 `^1[3-9][0-9]{9}$`
- `role` 必填，取值 `admin` / `editor` / `viewer`，决定 user 加入 organization 时的权限。父系统为 URL 源头，每次登录 WeKnora 会同步更新用户在该 org 的角色
- `ts` 必须是整数字符串（Unix 秒时间戳）
- `nonce` 任意字符串，建议 16-32 字符 hex 或 base62 随机值
- `sig` 必须是 hex 编码的 64 字符（对应 32 字节 HMAC-SHA256 输出）

注意：**ts 不做新鲜度校验**——WeKnora 不拒绝"旧时间戳"的 URL。防重放完全依赖 nonce 一次性消费。

## 3. 参考实现

### Python

```python
import hmac, hashlib, time, secrets

def build_iframe_url(base_url: str, cid: str, mobile: str, role: str, secret: str) -> str:
    ts = str(int(time.time()))
    nonce = secrets.token_hex(16)
    msg = f"cid={cid}&mobile={mobile}&nonce={nonce}&role={role}&ts={ts}"
    sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return (
        f"{base_url}/iframe-login?cid={cid}&mobile={mobile}"
        f"&role={role}&ts={ts}&nonce={nonce}&sig={sig}"
    )

# 用法
url = build_iframe_url(
    "https://weknora.example.com",
    "ACME-2024",
    "13812345678",
    "editor",
    "<64-char secret from weknora-admin provision>",
)
# 在外部系统模板里：<iframe :src="url" ...>
```

### Node.js

```js
const crypto = require('crypto');

function buildIframeUrl(baseUrl, cid, mobile, role, secret) {
  const ts = Math.floor(Date.now() / 1000).toString();
  const nonce = crypto.randomBytes(16).toString('hex');
  const msg = `cid=${cid}&mobile=${mobile}&nonce=${nonce}&role=${role}&ts=${ts}`;
  const sig = crypto.createHmac('sha256', secret).update(msg).digest('hex');
  return `${baseUrl}/iframe-login?cid=${cid}&mobile=${mobile}&role=${role}&ts=${ts}&nonce=${nonce}&sig=${sig}`;
}
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

func BuildIframeURL(baseURL, cid, mobile, role, secret string) string {
    ts := fmt.Sprintf("%d", time.Now().Unix())
    nonceBytes := make([]byte, 16)
    _, _ = rand.Read(nonceBytes)
    nonce := hex.EncodeToString(nonceBytes)
    msg := "cid=" + cid + "&mobile=" + mobile + "&nonce=" + nonce + "&role=" + role + "&ts=" + ts
    h := hmac.New(sha256.New, []byte(secret))
    h.Write([]byte(msg))
    sig := hex.EncodeToString(h.Sum(nil))
    return fmt.Sprintf("%s/iframe-login?cid=%s&mobile=%s&role=%s&ts=%s&nonce=%s&sig=%s",
        baseURL, cid, mobile, role, ts, nonce, sig)
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
| 403 | `IFRAME_NOT_ENABLED` | 对应 cid 未启用 iframe 登录（可能是未 provision 或已 revoke），联系运维 |
| 404 | `IFRAME_TENANT_NOT_FOUND` | cid 未 provision，运维执行 `weknora-admin iframe provision` |
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

- **secret 长度固定 64 hex 字符**（32 字节），由 WeKnora 的 `crypto/rand` 生成，不可替换成自己造的
- 严禁在外部系统前端 JS / HTML 中持有 secret——只应在后端服务器上签 URL
- 父系统应**每次渲染 iframe 时生成新的 nonce**，同一 URL 不支持复用
- 怀疑 secret 泄漏时立即 `weknora-admin iframe rotate --cid X`——无需重启 WeKnora
- 数据库里 `tenants.iframe_secret` 字段是 AES-256-GCM 加密存储的，即使数据库泄漏 secret 也不会裸露（前提是 `SYSTEM_AES_KEY` 未泄漏）
- iframe URL 会出现在浏览器历史、访问日志、Referer 里——风险靠 "nonce 一次性" 缓解，不靠 URL 机密性

## 9. 故障排查

| 现象 | 排查点 |
|---|---|
| 401 IFRAME_BAD_SIGNATURE，但 secret 确认没错 | 检查签名消息字典序是否正确（`cid < mobile < nonce < role < ts`）；检查字段值是否做了 URL 编码后再签（应该原样） |
| 401 IFRAME_REPLAY，第一次就失败 | 父系统是否把同一 URL 复用（模板缓存、iframe reload 等）；给每次渲染都生成新 nonce |
| 403 IFRAME_NOT_ENABLED | 运维跑 `weknora-admin iframe provision --cid X --name Y`；如果之前 revoke 过，rotate 而不是 provision |
| 404 IFRAME_TENANT_NOT_FOUND | cid 拼错（大小写敏感）；或运维没 provision |
| iframe 里完全白屏 | 打开浏览器 devtools → Console 看有无 CSP `frame-ancestors` 阻塞信息；Network 看 `/api/v1/auth/iframe-login` 响应是什么 |
| logo / 外链还在显示 | 检查 `sessionStorage.weknora_embedded` 是否为 `"1"`；如果是 `null`，说明 URL 没经过 `/iframe-login` 路由入口 |
| access token 很快过期 | 前端是否正确启用了 refresh 机制（现有 OIDC/密码登录用同一套），debug 可以手动观察 `localStorage.weknora_token` 是否在 24h 后被 refresh |

## 10. 版本

- v0.3.7（TBD）：初版 iframe 嵌入免登支持
- 迁移版本：`000035_iframe_login.up.sql`（users.mobile / tenants.external_id+iframe_secret / iframe_nonces 表）

---

**相关文档**：
- [`docs/superpowers/specs/2026-04-14-iframe-auto-login-design.md`](superpowers/specs/2026-04-14-iframe-auto-login-design.md) — 完整设计文档
- [`docs/api/`](api/) — REST API 参考（含 iframe-login 端点 Swagger 注解）
