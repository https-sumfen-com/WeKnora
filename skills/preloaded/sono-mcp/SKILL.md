---
name: call-mcp-tools
description: "Use when the server-side Agent must precisely choose and call currently registered SONO-MCP tools: get_plot_info, get_weather, get_summary_base, get_plot_device_info, get_wofost_report, get_report_by_type, or get_plot_warning."
---

# 服务端 Agent 精确调用本服务 MCP 工具

目标：少调用、准调用、不猜参数、不把空结果当错误。

## 核心原则

- 只调用已注册工具：`get_plot_info`、`get_weather`、`get_summary_base`、`get_plot_device_info`、`get_wofost_report`、`get_report_by_type`、`get_plot_warning`。
- 禁止调用 `get_data_list`、`get_data_detail`（代码存在但注册已注释，不可用）。
- 不猜测 `plot_id`、`device_id`、`dept_id`、`base_id`、`report_date`、token；能从上下文取到的不要让用户重复填。
- 用户意图不清晰或缺少关键 ID 时，先追问，不盲目调用。
- `isError=false` 且文本为空 = 空结果，不是错误。
- 有数据时基于 `payload` 简洁回答，不原样倾倒 JSON。
- 错误时不暴露 token、内部 URL、内部配置。

## 参数规则

所有数字字段用 `FlexibleInt64` 解码：JSON 数字 `123` 或整数字符串 `"123"` 均可；非整数字符串报错。

**参数优先级**：服务端/会话/网关上下文 → 当前页面路由 → 用户本轮输入 → 历史对话。

**字段映射速查**：

| 参数        | 说明                                                                                                                                                    |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cid`       | 各工具均需要，企业标识                                                                                                                                  |
| `dept_id`   | 仅 `get_summary_base`；`0`=全部门（企业管理员），`-1`=无可用部门                                                                                        |
| `base_id`   | 仅 `get_summary_base`；有值时优先于 `dept_id`                                                                                                           |
| `plot_id`   | `get_plot_info`、`get_weather`、`get_wofost_report`、`get_plot_warning`                                                                                  |
| `keyword`   | `get_plot_info`、`get_weather`：传地块名/区域名，不传天气词/时间词；`get_summary_base`：**仅**当用户明确提到基地名称且无 `base_id` 时才传，其余情况不传 |
| `device_id` | 仅 `get_plot_device_info`                                                                                                                               |
| `report_date` | 仅 `get_wofost_report`；报告日期，格式 `YYYY-MM-DD`；不传时服务端默认当天                                                                           |
| `days`      | 仅 `get_weather`；`7` = 7天预报（`payload.days[]`）；不传或传 `0` = 仅返回实时天气（`payload.now`）                                                     |
| `type`      | 仅 `get_report_by_type`；支持 `plot_growth_analysis`、`plot_3d_phenotype`、`plot_growth_dynamics`、`plot_seedling_monitoring`、`plot_wofost`、`device_analysis` |
| `id`        | 仅 `get_report_by_type`；报告对应 ID，地块类报告传地块 ID，设备报告传设备 ID                                                                            |
| `period_type` | 仅 `get_report_by_type`；支持 `7d`、`week`、`month`，不传默认 `7d`                                                                                   |
| `start_date` / `end_date` | `get_report_by_type`、`get_plot_warning`；明确日期范围才传，格式 `YYYY-MM-DD`                                                           |
| `planting_start_date` | 仅 `get_report_by_type`；用户明确指定种植开始日期时才传                                                                                       |
| `limit`     | 仅 `get_plot_warning`；不传或传 `0` 时服务端默认 `20`                                                                                                   |

## 工具选择

### get_plot_info

触发：用户查地块状态、作物、长势、面积、当前阶段、农事建议。

- 有 `plot_id` 传 `plot_id`；有地块名传 `keyword`；两者都有可同时传。
- 用户问天气 → `get_weather`；问设备 → `get_plot_device_info`；不要先查地块再联动。

### get_weather

触发：用户查天气、气象、降雨温湿风，或问"适不适合打药/喷灌/作业"。

- **`days=7`**（传入条件）：用户意图为**未来天气分析、未来预警、明天/这周/几天后天气**时传入 `days=7`；仅问当前/今天天气时不传。
- 不要把"今天""下雨""适合打药"当作 `keyword`。
- 有 `plot_id` 或 `keyword` 直接调用，不要先查地块。

### get_wofost_report

触发：用户查 WOFOST、作物模型/生长模拟报告、模型预测产量、生育进程、模拟生物量、LAI、根深、氮吸收、水分平衡，或明确要求某地块的 WOFOST 报告。

- 必须有明确 `cid` 和 `plot_id`；缺任一项时先追问，不用地块工具替代。
- `report_date` 仅在用户指定报告日期时传；未指定则不传，让服务端默认当天。
- 返回成功后聚焦报告摘要、关键生育日期、产量/生物量、水分平衡和报告链接，详见 `references/tool-wofost-report.md`。

### get_report_by_type

触发：用户明确查询某类农业报告，如地块长势分析、3D 表型、长势动态、苗情监测、WOFOST 报告，或设备分析报告。

- 必须有明确 `cid`、`type` 和 `id`；缺任一项时先追问，不用其他报告/地块/设备工具替代。
- `period_type` 仅在用户指定最近7条、按周、按月时传对应 `7d`、`week`、`month`；未指定可不传，让服务端默认 `7d`。
- `start_date`、`end_date`、`planting_start_date`、`days` 仅在用户明确指定日期范围、种植开始日期或条数时传。

### get_plot_warning

触发：用户查地块预警、告警、风险、异常提醒、病虫害/气象/农事风险等。

- 必须有明确 `cid` 和 `plot_id`；缺任一项时先追问，不用地块信息或天气工具替代。
- `start_date`、`end_date` 仅在用户指定日期范围时传。
- `limit` 仅在用户指定条数时传；未指定可不传，让服务端默认 `20`。

### get_summary_base

触发：用户查基地汇总、基地看板、基地统计、发起"基地报告"；**以及以下全局概览意图**：

- "今天有哪些值得关注的事情" / "今天情况怎么样" / "最近有什么需要关注的"
- "整体情况" / "每日动态" / "今日概览" / "有什么异常" / "有什么需要处理的"
- 用户进入系统后的首条打招呼式问询，且上下文无特定 `plot_id` / `device_id`

**全局概览意图专属规则**：上下文中无明确 `plot_id`、`device_id` 时，**只调用 `get_summary_base`，不调用其他工具**。`get_summary_base` 响应已内嵌实时天气和7天预报（`summary.weather`/`summary.weather_7days`），**不需要额外调用 `get_weather`**。

- `dept_id=0` 直接传，表示全部门权限。
- `dept_id=-1` 且无 `base_id` 时先追问。
- **`keyword` 传入条件（严格）**：
  - 用户在问题中明确提到了基地名称（如"查一下苏沁基地"）**且**上下文中没有对应的 `base_id` → 才传 `keyword`
  - 其他所有情况（默认汇总、按 dept_id/base_id 查询、用户未提基地名）→ **不传 `keyword`**，让服务端按 `dept_id`/`base_id` 处理
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
- `get_weather` 未来预报：追加 `"days": 7`，返回 `payload.days[]`；不传则仅返回 `payload.now`。

### get_wofost_report

```json
{
  "plot_id": 123,
  "cid": 2007,
  "report_date": "2026-06-03",
  "token": "optional-token",
  "entity_id": 1,
  "entity_info_id": 0
}
```

- 必须传有效 `cid` 和 `plot_id`；`report_date` 可省略。
- `report_date` 只接受明确日期语义，不要把“今天/最新”等词原样传入。

### get_report_by_type

```json
{
  "type": "plot_growth_analysis",
  "id": 123,
  "period_type": "7d",
  "start_date": "2026-06-01",
  "end_date": "2026-06-30",
  "planting_start_date": "2026-05-01",
  "days": 7,
  "cid": 2007,
  "token": "optional-token",
  "entity_id": 1,
  "entity_info_id": 0
}
```

- `type`、`id`、`cid` 必须有效；`type` 不在支持列表内会失败。
- 日期、`planting_start_date`、`days` 均为可选；不要把“最新/最近”等词原样传给日期字段。

### get_plot_warning

```json
{
  "plot_id": 123,
  "start_date": "2026-06-01",
  "end_date": "2026-06-30",
  "limit": 20,
  "cid": 2007,
  "token": "optional-token",
  "entity_id": 1,
  "entity_info_id": 0
}
```

- 必须传有效 `cid` 和 `plot_id`；`start_date`、`end_date`、`limit` 可省略。

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
- **默认不传 `keyword`**；仅用户明确说出基地名称且无 `base_id` 时才追加 `"keyword": "基地名"`。

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

**禁止默认联动**：查地块不自动查天气/设备；查天气不自动查地块；查设备不自动查地块/天气；查 WOFOST 报告不自动查地块/天气；查农业报告不自动查地块/天气/设备；查地块预警不自动查地块/天气；查基地汇总不联动其他工具。

**禁止全量扫描**：不得在单次用户问题中同时调用多个工具"以防遗漏"。特别是全局概览意图（如"今天有哪些值得关注"）触发 `get_summary_base` 后，**禁止再追加调用 `get_weather`、`get_plot_info`、`get_plot_device_info`、`get_wofost_report`、`get_report_by_type`、`get_plot_warning`**。

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
- `get_wofost_report` 返回处理 → `references/tool-wofost-report.md`
- `get_report_by_type` 返回处理 → `references/tool-report-by-type.md`
- `get_plot_warning` 返回处理 → `references/tool-plot-warning.md`
