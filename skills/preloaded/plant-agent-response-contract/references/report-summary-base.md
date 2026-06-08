# 企业 / 基地报告结构（get_summary_base）

角色判断方式见 `sono-mcp/references/tool-summary-base.md`。

天气数据已内嵌在响应中（`summary.weather.now` / `summary.weather_7days.daily[]`），**不需要额外调用 `get_weather`**。

---

## 企业管理员报告（department_id=0）

关注意图：全企业效益、整体种植情况、多作物横向对比、关键风险。

### 卡片顺序（3-5 张）

**1. metric — 企业 KPI 概览**

来源：`index_v2` + `wisdom_base.plot` + `wisdom_machine.machine_summary`

| label | value 来源 | unit |
|---|---|---|
| 基地数 | `index_v2.base_count` | 个 |
| 总种植面积 | `index_v2.plot_area` | 万亩，delta: `plot_area_rate`% |
| 水浇地面积 | `index_v2.water_area` | 万亩，delta: `water_area_rate`% |
| 地块数 | `wisdom_base.plot.plot_count` | 块，delta: `plot_count_rate`% |
| 农机台数 | `wisdom_machine.machine_summary.total` | 台 |
| 累计作业面积 | `wisdom_machine.machine_summary.work_area` | 亩次 |

值为 `0` 的 item 跳过（如 `total_cost=0`）

**2. chart — 作物种植结构**

来源：`crop_statistics[]`
- 各作物 `name` + `area`（亩）；`area=0` 跳过
- 标题绑定当前批次：`"{batch_id对应年份}作物种植结构"`
- 图表类型由 LLM 按数据语义选择；常见选择为 `pie` / `treemap` / `sunburst`；输出完整 `data.option`

**3. chart — 地块类型分布**

来源：`wisdom_base.plot_type[]`
- 旱地 / 喷灌地块 / 滴灌地块面积对比
- 影响灌溉建议，必须展示
- 图表类型由 LLM 按数据语义选择；少量组成可用 `pie`，排序/对比可用 `bar`；输出完整 `data.option`

**4. chart — 近年产量趋势**

来源：`batch[]`（过滤 `value > 0`）
- x 轴：年份；系列：主要作物（甜菜/小麦/油菜类）
- 同一年份同一作物只取一条
- 不足 2 年有效数据 → 跳过此卡片，自然回复说明"历史产量记录不足"
- 图表类型由 LLM 按数据语义选择；跨年趋势通常适合 `line` 或 `bar`，多作物可组合；输出完整 `data.option`

**5. chart — 当年生产投入**

来源：`batch_contrast_count[0]`（当前批次，如"2026年"）
- 标题：`"{batch_info.title}生产投入汇总"`
- 图表优先：用 ECharts 展示投入类型与合计/覆盖面积对比，常见选择为 `bar` 或双轴组合图
- 只展示 `total > 0` 的行；`plot_type_water` / `plot_type_dry` 单产为 0 时跳过
- 上年（`batch_contrast_count[1]`）水浇地单产 + 旱地单产 avg 对比，如需补充交由自然回复一句话表达

**6. recommendation — 关键风险与建议**

触发条件与示例：

| 来源 | 触发条件 | priority | title 模板 |
|---|---|---|---|
| `wisdom_irrigation.device.summary` | `abnormal_count > 0` | `high` | "设备全部离线，需立即排查" |
| `wisdom_base.sowing_progress[]` | 全为 0 且 `generated_at` 月份在 4-6 月 | `mid` | "播种进度未记录，建议核查计划" |
| `batch_contrast_count[0].count[]` | 种子类（id=14/15）`total=0` 且当月在播种季 | `mid` | "当年种子投入未记录，建议核查" |

每条 `reason` 必须引用具体数值，如"当前 7 台设备中 7 台离线（在线率 0%）"。

### quick-reply（2-3 个）

- "查看7天天气预报" → `"查询本区域未来7天天气预报"`（使用内嵌 weather_7days）
- "分析{最大面积作物}种植分布" → `"分析{作物名}在各基地的种植面积分布"`
- "查看农机作业详情" → `"查询全场农机作业情况"`

---

## 基地管理员报告（department_id>0 或按 base_id 查询）

关注意图：本基地运营状态、地块作业、设备可用性、天气与作业安排。

### 卡片顺序（2-4 张）

**1. metric — 本基地 KPI**

来源：`wisdom_base.plot` + `wisdom_machine.machine_summary`

| label | value 来源 | unit |
|---|---|---|
| 地块数 | `wisdom_base.plot.plot_count` | 块 |
| 总面积 | `wisdom_base.plot.area` | 万亩 |
| 水浇地面积 | `wisdom_base.plot.water_area` | 万亩，delta: `water_area_rate`% |
| 农机台数 | `wisdom_machine.machine_summary.total` | 台 |
| 累计作业面积 | `wisdom_machine.machine_summary.work_area` | 亩次 |

**2. chart — 作物种植结构**

来源：`wisdom_base.plant_structure[]`
- 各作物 `name` + `value`（亩）
- 图表类型由 LLM 按数据语义选择；常见选择为 `pie` / `treemap` / `sunburst`；输出完整 `data.option`

**3. chart — 地块类型分布**

来源：`wisdom_base.plot_type[]`
- 旱地 / 喷灌地块 / 滴灌地块
- 图表类型由 LLM 按数据语义选择；少量组成可用 `pie`，排序/对比可用 `bar`；输出完整 `data.option`

**4. recommendation — 作业建议**

来源：`weather.now`（预警） + `wisdom_base.sowing_progress[]` + `wisdom_irrigation.device.summary`

- `weather.now.windScale ≥ 5` → 暂缓喷药/喷灌（按 tool-weather.md 阈值）
- `sowing_progress[]` 全为 0 且当前月份在 4-6 月 → 建议核查播种计划
- `wisdom_irrigation.device.summary.abnormal_count > 0` → 建议优先排查设备

### quick-reply（2-3 个）

- "查看本基地地块列表"
- "查询本基地农机作业详情"
- "查看本基地7天天气预报"（使用内嵌 `weather_7days`，无需额外调用）

---

## 天气说明

- 实时天气：`summary.weather.now`（字段同 `get_weather` 实时字段，见 tool-weather.md）
- 7天预报：`summary.weather_7days.daily[]`（字段同 `get_weather` 预报字段）
- 有预警时按 tool-weather.md 阈值判断，追加 recommendation
- **不需要为基地汇总报告额外调用 `get_weather`**

---

## 共同禁止项

- 企业管理员报告里不展示单基地设备遥测明细
- 基地管理员报告里不展示跨年历史产量趋势（除非用户主动追问）
- `machine_task[]` / `machine_oil[]` 全为 0 时不生成月度趋势图
- `batch_contrast_count[].count[].total = 0` 的行不展示
- 不展示坐标、边界、`tgzn_*` 字段
- `wisdom_base.sowing_progress[].value = 0` 不展示为"0%"，说明"进度暂无记录"
