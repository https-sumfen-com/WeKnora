---
name: call-mcp-tools
description: "Use when the server-side Agent must precisely choose and call currently registered SONO-MCP tools: get_plot_info, get_weather, get_summary_base, get_plot_device_info, get_wofost_report, get_plot_warning, or get_report_by_type."
---

# 服务端 Agent 精确调用 SONO-MCP 工具

目标：普通问答一次提问只调最匹配的一个工具；不扫接口、不猜参数、不把空结果当错误。仅当进入 `sono-report` HTML 报告生成工作流时，才允许围绕同一地块按章节组合多个地块相关工具。

## 第零步：先判断要不要调用工具

以下情况**不调用任何 MCP 工具**，直接回答或追问：

- 闲聊、打招呼、询问功能说明。
- 纯文本任务（总结、翻译、推理）和农业知识问答，不依赖业务数据。
- 缺关键 ID 且上下文无法补齐 → 简短追问最关键的缺失字段。
- 多个工具都可能匹配但意图不明 → 先追问，不试调。

参数不足话术：`请补充地块名称、地块 ID、设备 ID、部门 ID 或基地 ID。`

## 第一步：意图 → 工具（一一对应，只选一个）

仅注册以下 7 个工具。禁止调用 `get_data_list`、`get_data_detail`（代码存在但注册已注释，不可用）。

| 用户意图 | 唯一匹配工具 | 必要参数 |
|---|---|---|
| 某个地块的状态、作物、长势、面积、生长阶段、农事建议 | `get_plot_info` | `plot_id` 或地块名 `keyword` |
| 天气、气象、降雨温湿风、适不适合打药/喷灌/作业 | `get_weather` | `plot_id` 或地块名 `keyword`；未来/预报追加 `days=7` |
| 基地汇总、基地看板、基地统计、基地报告；以及全局概览（见下） | `get_summary_base` | `cid` + `dept_id` 或 `base_id` |
| 某个设备的详情、遥测数据、所属地块 | `get_plot_device_info` | `device_id` |
| WOFOST、作物模型/生长模拟报告、模型预测产量、模拟生物量、LAI、根深、氮吸收、水分平衡 | `get_wofost_report` | `cid` + `plot_id` |
| 地块预警、风险告警、病虫害/气象/设备/长势异常提醒 | `get_plot_warning` | `cid` + `plot_id`；无地块上下文先追问 |
| 细分报告、模块报告、按类型生成报告：长势分析、3D 表型、长势动态、苗情监测、WOFOST 分析、设备分析 | `get_report_by_type` | `type` + `id`；地块类 `id=plot_id`，设备类 `id=device_id` |

**全局概览意图**（归 `get_summary_base`）：

- "今天有哪些值得关注的事情" / "今天情况怎么样" / "最近有什么需要关注的"
- "整体情况" / "每日动态" / "今日概览" / "有什么异常" / "有什么需要处理的"
- 用户进入系统后的首条打招呼式问询，且上下文无特定 `plot_id` / `device_id`

### 常见误选纠正

- 问天气/适合打药吗 → 只调 `get_weather`，**不要**先调 `get_plot_info` 定位地块。
- 问地块状态/长势 → 只调 `get_plot_info`，**不要**调 `get_wofost_report`（除非用户明确提 WOFOST/模型/模拟）。
- 问地块预警/风险/异常提醒 → 只调 `get_plot_warning`，**不要**用 `get_summary_base` 或天气工具替代。
- 问长势分析报告、3D 表型报告、苗情监测报告、按类型报告 → 只调 `get_report_by_type`，**不要**把 `get_plot_info` 的基础长势当作细分报告。
- 全局概览 → 只调 `get_summary_base`；其响应已内嵌实时天气和 7 天预报（`summary.weather` / `summary.weather_7days`），**禁止再追加 `get_weather` 或任何其他工具**。
- 上下文存在 `device_id` 不构成调用理由：用户没有明确设备查询意图时，禁止调 `get_plot_device_info`。
- 没有明确地块分析意图时，禁止调 `get_plot_info` 和 `get_wofost_report`；"可能有帮助"或"补全信息"不是调用理由。

### 调用纪律

- **单工具优先**：能用一个工具回答就只调一个。
- **禁止全量扫描**：不得在单次用户问题中把多个工具都调一遍"以防遗漏"。
- **禁止默认联动**：查地块不自动查天气/设备；查天气不自动查地块；查设备不自动查地块/天气；查 WOFOST 报告不自动查地块/天气；查基地汇总不联动其他工具。
- **报告生成例外**：当 `sono-report` 技能正在生成地块 HTML 报告时，允许同一地块内调用 `get_plot_info`、`get_plot_warning`、`get_report_by_type` 以及用户要求的天气/设备/WOFOST 工具；普通聊天问答不适用这个例外。

## 第二步：参数纪律（不猜参数）

参数只能来自：服务端/会话/网关上下文 → 当前页面路由 → 用户本轮输入 → 历史对话（按此优先级取值）。**禁止编造或猜测** `plot_id`、`device_id`、`dept_id`、`base_id`、`cid`、`report_date`、token；能从上下文取到的不要让用户重复填。

所有数字字段用 `FlexibleInt64` 解码：JSON 数字 `123` 或整数字符串 `"123"` 均可；非整数字符串报错。

**字段映射速查**：

| 参数        | 说明                                                                                                                                                    |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cid`       | 各工具均需要，企业标识                                                                                                                                  |
| `dept_id`   | 仅 `get_summary_base`；`0`=全部门（企业管理员），`-1`=无可用部门                                                                                        |
| `base_id`   | 仅 `get_summary_base`；有值时优先于 `dept_id`                                                                                                           |
| `plot_id`   | `get_plot_info`、`get_weather`、`get_wofost_report`、`get_plot_warning`；`get_report_by_type` 的地块类报告用作 `id`                                     |
| `keyword`   | `get_plot_info`、`get_weather`：只传地块名/区域名，**不传天气词/时间词**（"今天""下雨""适合打药"不是 keyword）；`get_summary_base`：**仅**当用户明确提到基地名称且无 `base_id` 时才传，其余情况不传 |
| `device_id` | 仅 `get_plot_device_info`                                                                                                                               |
| `report_date` | 仅 `get_wofost_report`；格式 `YYYY-MM-DD`，只接受明确日期语义，不要把"今天/最新"原样传入；不传时服务端默认当天                                       |
| `days`      | 仅 `get_weather`；`7` = 7天预报（`payload.days[]`）；不传或传 `0` = 仅返回实时天气（`payload.now`）                                                     |
| `type`      | 仅 `get_report_by_type`；只允许 `plot_growth_analysis`、`plot_3d_phenotype`、`plot_growth_dynamics`、`plot_seedling_monitoring`、`plot_wofost`、`device_analysis` |
| `id`        | 仅 `get_report_by_type`；地块类报告传 `plot_id`，设备分析传 `device_id`                                                                                  |
| `period_type` | 仅 `get_report_by_type`；只允许 `7d`、`week`、`month`，不明确时不传，让服务端默认 `7d`                                                               |

## 各工具触发与参数

### get_plot_info

触发：用户**明确**查地块状态、作物、长势、面积、当前阶段、农事建议。

- 有 `plot_id` 传 `plot_id`；有地块名传 `keyword`；两者都有可同时传。
- 用户问天气 → `get_weather`；问设备 → `get_plot_device_info`；不要先查地块再联动。

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

### get_weather

触发：用户查天气、气象、降雨温湿风，或问"适不适合打药/喷灌/作业"。

- **`days=7` 传入条件**：用户意图为未来天气分析、未来预警、明天/这周/几天后天气、作业窗口安排；仅问当前/今天天气时不传。
- 有 `plot_id` 或 `keyword` 直接调用，不要先查地块。

参数同 `get_plot_info`；未来预报追加 `"days": 7`，返回 `payload.days[]`；不传则仅返回 `payload.now`。

### get_plot_warning

触发：用户明确查地块预警、风险告警、病虫害/气象/设备/长势异常提醒，或在生成地块报告时需要补充预警模块。

- 必须有明确 `cid` 和 `plot_id`；无地块上下文时先追问，不用基地汇总替代。
- 返回成功后聚焦预警等级、风险类型、发生时间、影响地块和处置建议，详见 `references/tool-plot-warning.md`。
- 空列表表示未查询到相关预警，不要生成泛化风险提醒。

```json
{
  "plot_id": 123,
  "cid": 2007,
  "token": "optional-token",
  "entity_id": 1,
  "entity_info_id": 0
}
```

### get_summary_base

触发：基地汇总、基地看板、基地统计、"基地报告"，以及上文列出的全局概览意图。

- `dept_id=0` 直接传，表示全部门权限。
- `dept_id=-1` 且无 `base_id` 时先追问。
- `base_id > 0` 时忽略 `dept_id`，按基地查。
- **`keyword` 传入条件（严格）**：用户明确提到基地名称（如"查一下苏沁基地"）**且**上下文无对应 `base_id` → 才传；其他所有情况不传，让服务端按 `dept_id`/`base_id` 处理。
- 返回成功后**必须按用户角色（department_id）定向提取字段**，详见 `references/tool-summary-base.md`。

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

### get_plot_device_info

触发：用户**明确**查设备详情、设备数据、设备所属地块，且上下文有 `device_id`。

- 必须有明确 `device_id`；无时先追问，不用地块工具替代。
- `cid > 0` 必须满足；`entity_info_id > 0` 时上游才发送 `enterpriseId`。

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

### get_wofost_report

触发：用户**明确**查 WOFOST、作物模型/生长模拟报告、模型预测产量、生育进程、模拟生物量、LAI、根深、氮吸收、水分平衡。

- 必须有明确 `cid` 和 `plot_id`；缺任一项时先追问，不用地块工具替代。
- `report_date` 仅在用户指定报告日期时传；未指定则不传，让服务端默认当天。
- 返回成功后聚焦报告摘要、关键生育日期、产量/生物量、水分平衡和报告链接，详见 `references/tool-wofost-report.md`。

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

### get_report_by_type

触发：用户明确查细分报告、模块报告、按类型报告，或要求生成地块 HTML 报告且需要补齐地块级细分模块。

- `type` 只能取：`plot_growth_analysis`、`plot_3d_phenotype`、`plot_growth_dynamics`、`plot_seedling_monitoring`、`plot_wofost`、`device_analysis`。
- 地块类报告使用 `id=plot_id`；`device_analysis` 使用 `id=device_id`。
- `period_type` 只在用户指定 7 天/周/月时传为 `7d`、`week`、`month`；未指定时不传。
- 返回成功后提取报告结论、时间范围、关键指标、风险异常、建议和下载链接，详见 `references/tool-report-by-type.md`。
- `plot_wofost` 是细分报告口径；`get_wofost_report` 是 WOFOST 模型日报口径。用户只说“WOFOST 模型模拟/预测”时优先 `get_wofost_report`；用户说“细分报告/模块报告/按类型报告”时用本工具。

```json
{
  "type": "plot_growth_analysis",
  "id": 123,
  "period_type": "7d",
  "cid": 2007,
  "token": "optional-token",
  "entity_id": 1,
  "entity_info_id": 0
}
```

## 返回结果处理

1. `isError=true` → 说明服务异常，不暴露 token、内部 URL、内部配置。话术：`工具调用失败，可能是配置或上游服务异常，请稍后重试。`
2. `isError=false` 且文本为空 → 空结果，**不是错误**。话术：`未查询到相关数据。`
3. `isError=false` 且文本非空 → 解析 JSON，基于 `payload` 简洁回答，不原样倾倒 JSON。

## 懒加载字段提取规则

获取到数据后，按当前工具加载对应参考文档：

- `get_plot_info` 返回处理 → `references/tool-plot-info.md`
- `get_weather` 返回处理 → `references/tool-weather.md`
- `get_summary_base` 返回处理 → `references/tool-summary-base.md`
- `get_plot_device_info` 返回处理 → `references/tool-device-info.md`
- `get_wofost_report` 返回处理 → `references/tool-wofost-report.md`
- `get_plot_warning` 返回处理 → `references/tool-plot-warning.md`
- `get_report_by_type` 返回处理 → `references/tool-report-by-type.md`
