---
name: plant-agent-response-contract
description: Use when 需要为农业数据选择合理的多 schema 业务渲染片段：card、chart、table、map、quick-reply 或 report。
---

# 农业数据多 schema 渲染片段选择

## 边界

这是一个可运行 skill，用于把农业业务数据映射到合适的多 schema 渲染片段。

本文件只做片段选择和懒加载路由；各片段的字段、合法性、示例和校验规则放在对应 reference 中。

本 skill 不定义最终 answer 的组织方式，也不要求把自然回复和所有片段攒成一次性完整输出。需要局部渲染时，每次结构化输出都必须使用带 `schemaVersion` 和 `blocks` 的小 payload；不要输出裸 `{ "kind": "card" }`、裸 quick-reply 或裸 report。

## 片段选择

### card

常态结构化片段。用于单个对象、单类指标或单个风险点的局部渲染。

- `metric`: 数值快照、状态概览、关键指标。
- `chart`: 趋势、走势、变化、对比、占比、分布、多指标关系；已有可图形化序列数据时必须优先生成 chart。
- `table`: 明细清单、审计记录、编号状态、逐行文本字段。
- `map`: 坐标、边界、轨迹、空间图层。
- `recommendation`: 异常、风险、预警、离线、缺口、阈值越界、下一步建议。
- `retrospect`: 作业历史、告警历史、任务变化复盘。
- `phase-summary`: 生产周期阶段摘要。

### quick-reply

用于承接下一步可操作问题。出现风险、缺口、异常、详情钻取或可继续分析的数据时，默认搭配 quick-reply。

### report

report 是多张 card 的组合模板，不是默认片段。只有用户明确要求生成、查看或输出报告时才使用；不要因为数据较多、需要聚合或已有多张 card 就自动生成 report。

### 不生成片段

没有可视化价值、没有局部高亮信息、没有可操作后续问题，或数据不足以支撑片段字段时，不强行生成片段。

用户询问趋势、走势、变化、对比或分布，且已经读取到时间序列、分类对比、多指标或空间数据时，不属于“无片段”场景。

## 懒加载参考

先判断是否是明确报告意图，再选择 reference。不要为了判断普通 card/chart/quick-reply 去加载 `report-*.md`。

| 场景 | 参考 |
| --- | --- |
| 事实来源、缺口处理 | `references/data-grounding.md` |
| card / quick-reply / block 通用结构 | `references/blocks-cards-reports.md` |
| 图表 | `references/echarts-options.md` |
| 天气趋势、实时天气、天气风险局部卡片 | `references/card-weather.md` |
| 示例、反例、自检 | `references/response-examples.md` |

### 明确报告才加载

`references/report-*.md` 只在用户明确要求生成、查看或输出报告时加载。普通分析、趋势、走势、变化、对比、分布、天气预报、设备状态、风险关注、可视化、局部卡片或 quick-reply 意图，不加载 `report-*.md`。

| 明确报告场景 | 参考 |
| --- | --- |
| 企业 / 基地报告 | `references/report-summary-base.md` |
| 地块报告中的基础快照维度 | `references/report-plot-info.md` |
| 地块 WOFOST 报告或地块报告中的模型维度 | `references/report-wofost-report.md` |
| 天气报告或明确报告中的天气维度 | `references/report-weather.md` |
| 设备报告或明确报告中的设备维度 | `references/report-device-info.md` |
