---
name: call-mcp-tools
description: "Use when the server-side Agent must precisely choose and call currently registered SONO-MCP tools: get_plot_info, get_weather, get_summary_base, or get_plot_device_info."
---

# 服务端 Agent 精确调用本服务 MCP 工具

目标：少调用、准调用、不猜参数、不把空结果当错误。

## 核心原则

- 只调用已注册工具：`get_plot_info`、`get_weather`、`get_summary_base`、`get_plot_device_info`。
- 禁止调用 `get_data_list`、`get_data_detail`（代码存在但注册已注释，不可用）。
- 不猜测 `plot_id`、`device_id`、`dept_id`、`base_id`、token；能从上下文取到的不要让用户重复填。
- 用户意图不清晰或缺少关键 ID 时，先追问，不盲目调用。
- `isError=false` 且文本为空 = 空结果，不是错误。
- 有数据时基于 `payload` 简洁回答，不原样倾倒 JSON。
- 错误时不暴露 token、内部 URL、内部配置。

## 参数规则

所有数字字段用 `FlexibleInt64` 解码：JSON 数字 `123` 或整数字符串 `"123"` 均可；非整数字符串报错。

**参数优先级**：服务端/会话/网关上下文 → 当前页面路由 → 用户本轮输入 → 历史对话。

**字段映射速查**：

| 参数 | 说明 |
|---|---|
| `cid` | 四个工具均需要，企业标识 |
| `dept_id` | 仅 `get_summary_base`；`0`=全部门（企业管理员），`-1`=无可用部门 |
| `base_id` | 仅 `get_summary_base`；有值时优先于 `dept_id` |
| `plot_id` | `get_plot_info`、`get_weather` |
| `keyword` | `get_plot_info`、`get_weather`；传地块名/区域名，不传天气词/时间词 |
| `device_id` | 仅 `get_plot_device_info` |
| `days` | 仅 `get_weather`；传未来天数，MCP 支持后生效 |

## 工具选择

### get_plot_info

触发：用户查地块状态、作物、长势、面积、当前阶段、农事建议。

- 有 `plot_id` 传 `plot_id`；有地块名传 `keyword`；两者都有可同时传。
- 用户问天气 → `get_weather`；问设备 → `get_plot_device_info`；不要先查地块再联动。

### get_weather

触发：用户查天气、气象、降雨温湿风，或问"适不适合打药/喷灌/作业"。

- `days` 参数：明确要求未来 N 天预报时传入，当前只返回实时天气。
- 不要把"今天""下雨""适合打药"当作 `keyword`。
- 有 `plot_id` 或 `keyword` 直接调用，不要先查地块。

### get_summary_base

触发：用户查基地汇总、基地看板、基地统计、发起"基地报告"。

- `dept_id=0` 直接传，表示全部门权限。
- `dept_id=-1` 且无 `base_id` 时先追问。
- 返回成功后**必须按用户角色定向提取字段**，详见 `references/tool-summary-base.md`。

### get_plot_device_info

触发：用户查设备详情、设备数据、设备所属地块，上下文有 `device_id`。

- 必须有明确 `device_id`；无时先追问，不用地块工具替代。
- `cid > 0` 必须满足；`entity_info_id > 0` 时上游才发送 `enterpriseId`。

## 工具参数格式

### get_plot_info / get_weather

```json
{
  "plot_id": 123,
  "keyword": "东区地块",
  "cid": 2007,
  "token": "optional-token",
  "entity_id": 1,
  "entity_info_id": 0
}
```

- `plot_id <= 0` 且 `keyword` 为空 → 返回空成功（`source=default`，`payload={}`）。
- `get_weather` 额外支持 `"days": 7`（MCP 支持后生效）。

### get_summary_base

```json
{
  "cid": 2007,
  "dept_id": 0,
  "base_id": 88,
  "token": "optional-token",
  "entity_id": 1,
  "entity_info_id": 0
}
```

- `deptId` / `baseId` 为兼容别名；snake_case 优先。
- `cid <= 0` 或无有效 `dept_id`/`base_id` → 返回空成功（`payload=[]`）。
- `base_id > 0` 时忽略 `dept_id`，按基地查。

### get_plot_device_info

```json
{
  "device_id": 456,
  "cid": 2007,
  "token": "optional-token",
  "entity_id": 1,
  "entity_info_id": 99
}
```

- `device_id <= 0` → 返回空成功（`payload={}`）。

## 不要调用工具的情况

- 用户闲聊、打招呼、询问接口说明。
- 纯文本任务（总结、翻译、推理）不依赖业务数据。
- 缺关键 ID 且上下文无法补齐。
- 多工具都可能匹配但意图不明。

处理：简短追问最关键的缺失字段，或说明当前不支持该类查询。

## 调用策略

**单工具优先**：能用一个工具回答就只调一个。

**禁止默认联动**：查地块不自动查天气/设备；查天气不自动查地块；查设备不自动查地块/天气；查基地汇总不联动其他工具。

## 返回结果处理

1. `isError=true` → 说明服务异常，不暴露敏感信息。
2. `isError=false` 且文本为空 → 说明"未查询到相关数据"。
3. `isError=false` 且文本非空 → 解析 JSON，基于 `payload` 回答。

空结果话术：`未查询到相关数据。`
参数不足话术：`请补充地块名称、地块 ID、设备 ID、部门 ID 或基地 ID。`
错误话术：`工具调用失败，可能是配置或上游服务异常，请稍后重试。`

## 懒加载字段提取规则

获取到数据后，按当前工具加载对应参考文档：

- `get_plot_info` 返回处理 → `references/tool-plot-info.md`
- `get_weather` 返回处理 → `references/tool-weather.md`
- `get_summary_base` 返回处理 → `references/tool-summary-base.md`
- `get_plot_device_info` 返回处理 → `references/tool-device-info.md`
