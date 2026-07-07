---
name: call-mcp-tools
description: "Use when the server-side Agent must precisely choose and call currently registered SONO-MCP tools: get_plot_info, get_weather, get_summary_base, get_plot_device_info, get_wofost_report, get_plot_warning, get_report_by_type, add_farming_record, get_agri_input_list, get_formula_list, or get_farming_operation_list."
---

# 服务端 Agent 精确调用 SONO-MCP 工具

目标：普通问答一次提问只调最匹配的一个工具；不扫接口、不猜参数、不把空结果当错误。普通用户要求生成/导出/创建报告时，不调用本 Skill 的 MCP 工具，必须交给 `sono-report-request` 直接发起报告生成请求；但后端第二次 LLM 已进入 `sono-report` 渲染流程并带有 `report_no`/`report_url` 时，允许 `sono-report` 按章节调用本 Skill 的 MCP 工具取数。

## 第零步：先判断要不要调用工具

以下情况**不调用任何 MCP 工具**，直接回答或追问：

- 闲聊、打招呼、询问功能说明。
- 纯文本任务（总结、翻译、推理）和农业知识问答，不依赖业务数据。
- 缺关键 ID 且上下文无法补齐 → 简短追问最关键的缺失字段。
- 多个工具都可能匹配但意图不明 → 先追问，不试调。

参数不足话术：`请补充地块名称、地块 ID、设备 ID、部门 ID、基地 ID、农事事项或作业时间。`

## 第一步：意图 → 工具（一一对应，只选一个）

仅注册以下 11 个工具。禁止调用 `get_data_list`、`get_data_detail`（代码存在但注册已注释，不可用）。

| 用户意图 | 唯一匹配工具 | 必要参数 |
|---|---|---|
| 某个地块的状态、作物、长势、面积、生长阶段、农事建议 | `get_plot_info` | `plot_id` 或地块名 `keyword` |
| 天气、气象、降雨温湿风、适不适合打药/喷灌/作业 | `get_weather` | `plot_id` 或地块名 `keyword`；未来/预报追加 `days=7` |
| 基地汇总、基地看板、基地统计、基地报告；以及全局概览（见下） | `get_summary_base` | `cid` + `dept_id` 或 `base_id` |
| 某个设备的详情、遥测数据、所属地块 | `get_plot_device_info` | `device_id` |
| WOFOST、作物模型/生长模拟报告、模型预测产量、模拟生物量、LAI、根深、氮吸收、水分平衡 | `get_wofost_report` | `cid` + `plot_id` |
| 地块预警、风险告警、病虫害/气象/设备/长势异常提醒 | `get_plot_warning` | `cid` + `plot_id`；无地块上下文先追问 |
| 查询/查看已有细分报告、模块报告：长势分析、3D 表型、长势动态、苗情监测、WOFOST 分析、设备分析 | `get_report_by_type` | `type` + `id`；地块类 `id=plot_id`，设备类 `id=device_id` |
| 新增/保存/提交农事记录、作业记录、施肥/用药/灌溉等农事操作记录 | `add_farming_record` | `cid` 或 `tgzn_entity_id`；记录字段必须来自上下文/表单/用户 |
| 查询/选择农资库存、农资/肥料/药剂/物料列表 | `get_agri_input_list` | `cid` + `base_id` |
| 查询/选择农资配方/套餐/施肥配方 | `get_formula_list` | `cid` + `base_id` |
| 查询/选择农事操作、作业事项、事项列表 | `get_farming_operation_list` | `cid` |

**全局概览意图**（归 `get_summary_base`）：

- "今天有哪些值得关注的事情" / "今天情况怎么样" / "最近有什么需要关注的"
- "整体情况" / "每日动态" / "今日概览" / "有什么异常" / "有什么需要处理的"
- 用户进入系统后的首条打招呼式问询，且上下文无特定 `plot_id` / `device_id`

### 常见误选纠正

- 问天气/适合打药吗 → 只调 `get_weather`，**不要**先调 `get_plot_info` 定位地块。
- 问地块状态/长势 → 只调 `get_plot_info`，**不要**调 `get_wofost_report`（除非用户明确提 WOFOST/模型/模拟）。
- 问地块预警/风险/异常提醒 → 只调 `get_plot_warning`，**不要**用 `get_summary_base` 或天气工具替代。
- 问“查询/查看已有”长势分析报告、3D 表型报告、苗情监测报告、按类型报告 → 只调 `get_report_by_type`，**不要**把 `get_plot_info` 的基础长势当作细分报告；问“生成/导出/创建报告” → 不调用 MCP，交给 `sono-report-request`。
- 问新增/保存农事记录 → 只在用户明确要写入时调 `add_farming_record`；用户只是问"怎么记录/需要哪些字段"时不要写入。
- 问农资、配方、农事事项可选项 → 分别只调 `get_agri_input_list`、`get_formula_list`、`get_farming_operation_list`，**不要**用地块、基地汇总或报告工具替代。
- 全局概览 → 只调 `get_summary_base`；其响应已内嵌实时天气和 7 天预报（`summary.weather` / `summary.weather_7days`），**禁止再追加 `get_weather` 或任何其他工具**。
- 上下文存在 `device_id` 不构成调用理由：用户没有明确设备查询意图时，禁止调 `get_plot_device_info`。
- 没有明确地块分析意图时，禁止调 `get_plot_info` 和 `get_wofost_report`；"可能有帮助"或"补全信息"不是调用理由。

### 调用纪律

- **单工具优先**：能用一个工具回答就只调一个。
- **禁止全量扫描**：不得在单次用户问题中把多个工具都调一遍"以防遗漏"。
- **禁止默认联动**：查地块不自动查天气/设备；查天气不自动查地块；查设备不自动查地块/天气；查 WOFOST 报告不自动查地块/天气；查基地汇总不联动其他工具。
- **农事辅助列表不默认联动**：新增农事记录不自动查农资/配方/事项列表；只有用户明确要选项，或缺少对应 ID 且上下文允许列选项时，才单独调用对应列表工具。
- **写操作更谨慎**：`add_farming_record` 会新增/更新上游农事记录；用户未明确要求保存、提交、新增时禁止调用。
- **用户侧报告生成不走 MCP**：当普通用户要求生成/导出/创建报告时，必须交给 `sono-report-request`；本 Skill 不预先调用 `get_plot_info`、`get_plot_warning`、`get_report_by_type` 或其他 MCP 工具。
- **内部渲染例外**：当上层明确处于 `sono-report` 后端内部渲染流程，且已带 `report_no` / `report_url` 时，允许按 `sono-report` 的章节规则调用地块级 MCP 工具取数。

## 第二步：参数纪律（不猜参数）

参数只能来自：服务端/会话/网关上下文 → 当前页面路由 → 用户本轮输入 → 历史对话（按此优先级取值）。**禁止编造或猜测** `plot_id`、`device_id`、`dept_id`、`base_id`、`cid`、`matter_id`、`report_date`、token；能从上下文取到的不要让用户重复填。

所有数字字段用 `FlexibleInt64` 解码：JSON 数字 `123` 或整数字符串 `"123"` 均可；非整数字符串报错。

**字段映射速查**：

| 参数        | 说明                                                                                                                                                    |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cid`       | 各工具均需要，企业标识                                                                                                                                  |
| `dept_id`   | 仅 `get_summary_base`；`0`=全部门（企业管理员），`-1`=无可用部门                                                                                        |
| `base_id`   | `get_summary_base`、`add_farming_record`、`get_agri_input_list`、`get_formula_list`；在 `get_summary_base` 中有值时优先于 `dept_id`                    |
| `plot_id`   | `get_plot_info`、`get_weather`、`get_wofost_report`、`get_plot_warning`、`add_farming_record`；`get_report_by_type` 的地块类报告用作 `id`             |
| `keyword`   | `get_plot_info`、`get_weather`：只传地块名/区域名，**不传天气词/时间词**（"今天""下雨""适合打药"不是 keyword）；`get_summary_base`：**仅**当用户明确提到基地名称且无 `base_id` 时才传，其余情况不传 |
| `device_id` | 仅 `get_plot_device_info`                                                                                                                               |
| `report_date` | 仅 `get_wofost_report`；格式 `YYYY-MM-DD`，只接受明确日期语义，不要把"今天/最新"原样传入；不传时服务端默认当天                                       |
| `days`      | 仅 `get_weather`；`7` = 7天预报（`payload.days[]`）；不传或传 `0` = 仅返回实时天气（`payload.now`）                                                     |
| `type`      | 仅 `get_report_by_type`；只允许 `plot_growth_analysis`、`plot_3d_phenotype`、`plot_growth_dynamics`、`plot_seedling_monitoring`、`plot_wofost`、`device_analysis` |
| `id`        | 仅 `get_report_by_type`；地块类报告传 `plot_id`，设备分析传 `device_id`                                                                                  |
| `period_type` | 仅 `get_report_by_type`；只允许 `7d`、`week`、`month`，不明确时不传，让服务端默认 `7d`                                                               |
| `start_date` / `end_date` | `get_plot_warning`、`get_report_by_type`；只接受明确日期范围，不明确时不传                                                                  |
| `planting_start_date` | 仅 `get_report_by_type`；只在上层已有明确种植开始日期时传                                                                                  |
| `limit`     | 仅 `get_plot_warning`；不明确时不传，让服务端默认 `20`                                                                                                  |
| `address` / `location` | 仅 `add_farming_record`；作业地址和经纬度/位置文本，缺失时不要编造                                                                        |
| `area` / `area_unit` | 仅 `add_farming_record`；作业面积和单位，必须来自用户或表单                                                                                |
| `matter_id` | 仅 `add_farming_record`；农事操作事项 ID，可从 `get_farming_operation_list` 的用户选择结果取得                                                         |
| `operate_time` | 仅 `add_farming_record`；作业时间，传明确日期时间字符串，不把模糊时间原样传入                                                                      |
| `goodsList` | 仅 `add_farming_record`；提交条目使用 `goods_name`、`stock_goods_id`、`is_formula`、`num`、`price`、`unit`、`dosage` 等字段，值必须来自用户/表单/配方计算结果 |
| `tgzn_user_id` / `tgzn_entity_id` / `tgzn_dept_id` | 仅 `add_farming_record`；来自网关/会话/表单，不要猜测                                                            |

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

触发：用户明确查询/查看已有细分报告、模块报告、按类型报告。用户要求生成/导出/创建报告时不触发本工具，改用 `sono-report-request`。

- `type` 只能取：`plot_growth_analysis`、`plot_3d_phenotype`、`plot_growth_dynamics`、`plot_seedling_monitoring`、`plot_wofost`、`device_analysis`。
- 地块类报告使用 `id=plot_id`；`device_analysis` 使用 `id=device_id`。
- `period_type` 只在用户指定 7 天/周/月时传为 `7d`、`week`、`month`；未指定时不传。
- 返回成功后提取报告结论、时间范围、关键指标、风险异常、建议和下载链接，详见 `references/tool-report-by-type.md`。
- 如果上层明确在执行旧版/内部 `sono-report` HTML 渲染流程，必须保留可图表化的多天序列和开放分析结构（如 `trendSeries`、`charts[]`、`analysisItems`、`sections`、`tables`），不要压缩成普通问答短摘要。
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

### add_farming_record

触发：用户明确要求新增、保存、提交农事记录/作业记录/施肥用药灌溉记录。用户只是咨询"怎么记录"、"需要哪些字段"或"有哪些可选项"时不触发写入。

- 这是写操作；必须确认用户有明确保存/提交意图。
- 必须有企业标识：优先传 `cid`；没有 `cid` 但有 `tgzn_entity_id` 时，服务端会用 `tgzn_entity_id` 作为上游 companyId。
- 关键字段只能来自上下文/页面表单/用户输入/用户选择结果。缺少地块或基地、作业事项、作业时间、操作人、必要农资明细时先追问。
- `goodsList` 提交格式详见下例；`num`、`dosage` 是本次作业提交值，必须来自用户/表单/配方计算结果，不要把农资列表返回的库存余量直接当成本次用量。
- 返回成功后聚焦是否保存成功、记录 ID/编号、地块/基地、事项、时间和农资明细，详见 `references/tool-farming-record.md`。

```json
{
  "cid": 2007,
  "plot_id": 130,
  "base_id": 3,
  "matter_id": 207,
  "operate_time": "2026-07-07 14:32",
  "address": "内蒙古自治区呼和浩特市赛罕区金河镇入口西南约306米",
  "location": "111.79055065635646,40.723395173915904",
  "area": 2.65,
  "area_unit": "亩",
  "goodsList": [
    {
      "goods_name": "吡虫啉",
      "stock_goods_id": 15,
      "is_formula": 0,
      "num": 642,
      "price": 10,
      "unit": "",
      "dosage": 5304.47
    }
  ],
  "tgzn_user_id": 73,
  "tgzn_entity_id": 1,
  "tgzn_dept_id": 1,
  "token": "optional-token",
  "entity_id": 1,
  "entity_info_id": 0
}
```

- 无 `cid` 且无 `tgzn_entity_id` → 返回空成功（`source=default`，`payload={}`）。

### get_agri_input_list

触发：用户要查询/选择农资库存、农资、肥料、药剂、物料列表，尤其是新增农事记录前需要选择 `goodsList`。

- 必须有明确 `cid` 和 `base_id`；无 `base_id` 时先追问，除非上层明确允许查询企业全部农资。
- 用户没有要求选择农资时，不要为了新增记录自动调用。
- 返回成功后提取农资名称、库存/单位、规格、价格、关联 ID 和可用于 `goodsList` 的字段，详见 `references/tool-agri-input-list.md`。

```json
{
  "cid": 2007,
  "base_id": 75,
  "token": "optional-token",
  "entity_id": 1,
  "entity_info_id": 0
}
```

- `cid <= 0` → 返回空列表成功（`payload=[]`）。

### get_formula_list

触发：用户要查询/选择配方、农资配方、施肥配方、套餐，尤其是新增农事记录前需要按配方生成/选择农资明细。

- 必须有明确 `cid` 和 `base_id`；无 `base_id` 时先追问，除非上层明确允许查询企业全部配方。
- 不要把配方当成普通农资库存；问库存/单个物料时用 `get_agri_input_list`。
- 返回成功后提取配方名称、组成农资、配比/用量、适用作物/阶段和可用于 `goodsList` 的字段，详见 `references/tool-formula-list.md`。

```json
{
  "cid": 2007,
  "base_id": 75,
  "token": "optional-token",
  "entity_id": 1,
  "entity_info_id": 0
}
```

- `cid <= 0` → 返回空列表成功（`payload=[]`）。

### get_farming_operation_list

触发：用户要查询/选择农事操作、作业事项、事项列表，尤其是新增农事记录前需要确定 `matter_id`。

- 必须有明确 `cid`。
- 不要把事项列表当作农事记录；用户要保存记录时用 `add_farming_record`，用户要选事项时才用本工具。
- 返回成功后提取事项 ID、事项名称、分类、适用作物/阶段和备注，详见 `references/tool-farming-operation-list.md`。

```json
{
  "cid": 2007,
  "token": "optional-token",
  "entity_id": 1,
  "entity_info_id": 0
}
```

- `cid <= 0` → 返回空列表成功（`payload=[]`）。

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
- `add_farming_record` 返回处理 → `references/tool-farming-record.md`
- `get_agri_input_list` 返回处理 → `references/tool-agri-input-list.md`
- `get_formula_list` 返回处理 → `references/tool-formula-list.md`
- `get_farming_operation_list` 返回处理 → `references/tool-farming-operation-list.md`
