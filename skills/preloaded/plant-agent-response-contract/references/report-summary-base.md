# 企业 / 基地报告结构（get_summary_base）

角色判断方式见 `sono-mcp/references/tool-summary-base.md`。

---

## 企业管理员报告（dept_id=0）

关注意图：全企业效益、整体种植情况、多基地横向对比、关键风险。

### 卡片顺序（2-5 张）

**1. metric — 企业 KPI 概览**
- 来源：`index_v2`
- items：基地数（base_count 个）、总种植面积（plot_area 万亩）、水浇地面积（water_area 万亩，delta: water_area_rate%）

**2. chart(pie) — 作物种植结构**
- 来源：`crop_statistics`
- 各作物 `name` 为系列，`area`（亩）为数据
- 标题绑定批次年份（`batch_contrast_count[0].batch_info.title`）

**3. table — 各基地概览对比**
- 来源：`summary.base` + `wisdom_machine.machine_summary`
- 列：基地名称 | 总面积（万亩）| 农机台数 | 当年作业面积
- 按总面积降序

**4. chart(bar) — 近年产量趋势（可选）**
- 来源：`batch`（2020-2025年各作物产量）
- x 轴：年份；系列：主要作物（小麦、油菜类、甜菜）
- `batch` 为空或不足 3 年数据点 → 跳过，Markdown 说明缺口

**5. recommendation — 关键风险与建议**
- 来源：`wisdom_irrigation.device`（abnormal_count>0 的基地）+ `batch_contrast_count`（当年投入对比）
- 每条必须有 `reason`（引用字段值）和 `priority`
- 示例触发：某基地设备全部异常、当年关键投入为0、播种进度全为0

### quick-reply（2-3 个）

- "查看{基地名}基地详情" → `"生成{基地名}基地运营报告"`
- "分析{最大面积作物}种植分布" → `"分析{作物名}在各基地的种植面积分布"`

---

## 基地管理员报告（dept_id>0 或 base_id>0）

关注意图：本基地运营状态、地块作业、设备可用性、天气与作业安排。

定位：从 `summary.base` 找到当前基地，用其 `tgzn_dept_id`（=dept_id）或 `id`（=base_id）在 `wisdom_*`、`weather` 中取数。

### 卡片顺序（2-5 张）

**1. metric — 本基地 KPI**
- 来源：`wisdom_base.plot[base_id]`
- items：地块数（plot_count）、总面积（area 万亩）、水浇地面积（water_area 万亩，delta: water_area_rate%）
- 补充：农机台数（`machine_summary.total`）、当年作业面积（`machine_summary.work_area`）

**2. chart(pie) — 作物种植结构**
- 来源：`wisdom_base.plant_structure[base_id]`
- 各作物面积为 pie 数据

**3. chart(pie 或 bar) — 地块类型分布**
- 来源：`wisdom_base.plot_type[base_id]`
- 旱地 / 喷灌地块 / 滴灌地块面积对比
- 影响灌溉建议，必须展示

**4. table — 农机与设备状态**
- 来源：`wisdom_machine.machine_summary[base_id]`（农机行）+ `wisdom_irrigation.device[base_id]`（设备行）
- 列：类型 | 总数 | 在线/作业数 | 异常数

**5. recommendation — 作业建议**
- 来源：`weather[base_id].now`（当前气象）+ `wisdom_base.sowing_progress[base_id]`（播种进度）
- `windScale ≥ 5` → 暂缓喷药/喷灌
- 播种进度为 0 且 `generated_at` 月份在 4-6 月 → 建议核查播种计划
- `abnormal_count > 0` → 建议优先排查设备

### quick-reply（2-3 个）

- "查看本基地地块列表"
- "查询本基地农机作业详情"
- "查看本基地天气预报"

---

## 共同禁止项

- 企业管理员报告里不展示单基地设备遥测明细
- 基地管理员报告里不展示跨年历史产量趋势（除非用户主动追问）
- 不展示坐标、边界、tgzn_* 字段
