# 地块 WOFOST 报告结构（get_wofost_report）

WOFOST 是地块情况、地块分析、地块报告中的重点分析来源，聚焦**作物模型模拟结果、生育进程、产量/生物量、水分/养分平衡和模型风险建议**。字段提取规则见 `sono-mcp/references/tool-wofost-report.md`。

所有 WOFOST 数值必须表述为“模型模拟/预测”，不能写成实际测产、实测产量或已经发生的业务结果。

---

## 适用意图

以下地块级意图优先使用 WOFOST：

- “这个地块情况怎么样”
- “分析这个地块”
- “生成地块报告”
- “地块长势/生育进程/产量预测/水分平衡”
- “WOFOST 报告/作物模型/生长模拟”

如果缺少 `cid` 或 `plot_id`，用 Markdown 说明缺口；不要用 `get_plot_info` 冒充 WOFOST 模型报告。

---

## 卡片顺序（3-5 张）

### 1. metric — WOFOST 模型摘要

来源：`report_date`、`summary_report_json`、`terminal_report_json`

items 推荐：

| label | value 来源 | 说明 |
|---|---|---|
| 报告日期 | `report_date` | YYYY-MM-DD |
| 发育阶段 | `summary_report_json.DVS` | 可按 DVS 范围补充阶段描述 |
| 最大叶面积指数 | `summary_report_json.LAIMAX` | 跳过 NaN/null |
| 根深 | `summary_report_json.RD` | 单位按源数据或模型约定展示 |
| 地上总生物量 | `summary_report_json.TAGP` | 模型模拟值 |
| 贮藏器官干物质 | `summary_report_json.TWSO` | 产量形成关注指标 |
| 总氮吸收 | `summary_report_json.NuptakeTotal` | 跳过 NaN/null |

字段为空、`NaN`、空字符串时跳过，不生成占位 item。

### 2. chart — 生育进程与生物量趋势

来源：`csv_content[]` 有效日序列。

- 图表优先：生成 ECharts `chart`，常见选择为 `line` 或组合图。
- 优先字段：`DVS`、`LAI`、`TAGP`、`WSO`、`RD`、`NuptakeTotal`。
- 只提取有效值；不要输出完整 `csv_content[]`。
- 如果没有日期字段，用序号或“模型日序列”作为 x 轴，不要臆造日期。

### 3. chart — 水分平衡

来源：`terminal_report_json`。

- 图表优先：生成 ECharts `chart`，常见选择为 `bar`、堆叠 `bar` 或 waterfall 风格表达。
- 推荐字段：`RAINT`、`TOTIRR`、`TOTINF`、`PERCT`、`WTRAT`、`EVST`、`EVWT`、`LOSST`、`TSR`。
- 降雨、灌溉、入渗、渗漏、蒸腾、蒸发、损失/径流要分清，不要合并为模糊“水分”。

### 4. recommendation — 模型风险与管理建议

建议必须引用 WOFOST 字段值或规则，最多 3 条，按优先级排序。

| 条件 | priority | title 模板 |
|---|---|---|
| 最后有效 `SM < 0.20` | high | "模型土壤含水量偏低，建议关注补水" |
| `0.20 <= SM < 0.25` | mid | "模型土壤含水量偏低，建议持续监测" |
| `TOTIRR = 0` 且 `WTRAT` 明显大于 `RAINT` | mid | "模型期主要依赖降雨，需关注灌溉安排" |
| `PERCT > 0` 且降雨/入渗较高 | low | "存在渗漏消耗，关注水肥淋失风险" |
| `DVS >= 1` 且 `TWSO` 增加 | low | "处于产量形成阶段，关注水肥供应稳定性" |

无明显风险时，生成低优先级建议或 Markdown 一句：`"WOFOST 模型结果未显示明显水分或生长异常，建议按当前生育阶段继续跟踪。"`

### 5. metric 或 Markdown — 报告链接

来源：`daily_report_pdf`、`daily_report_csv`。

- 链接存在时优先在顶层 Markdown 用短句给出：`[WOFOST PDF 报告](...)`、`[CSV 明细](...)`。
- 不展开长 URL。
- `json_file` 为空时跳过。

---

## 与 get_plot_info 的关系

地块情况综合报告可同时包含：

1. WOFOST 模型摘要和趋势（重点）。
2. `get_plot_info` 基础快照：面积、作物、当前阶段、评级。
3. WOFOST 风险建议优先；`get_plot_info` 的阶段注意事项作为补充建议。

不要让基础快照卡片挤掉 WOFOST 图表。报告容量有限时优先保留 WOFOST 摘要、趋势图、水分平衡图和模型建议。

---

## 禁止项

- 不要原样输出完整 `csv_content[]`。
- 不要输出 `NaN`、空值或 0 占位指标。
- 不要把 `plot_no`、`report_no` 当成地块业务名称。
- 不要把模型模拟值表述为实际测产或已经发生结果。
- 不要用 table 替代 WOFOST 趋势、水分平衡、生物量/产量结构图。
