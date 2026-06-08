---
name: plant-agent-response-contract
description: Use when 需要为农业数据选择合理的多 schema 业务渲染片段：card、chart、table、map、quick-reply 或 report。
---

# 农业数据多 schema 渲染片段选择

## 边界

这是一个可运行 skill，用于把农业业务数据映射到合适的多 schema 渲染片段。

本文件只做片段选择和懒加载路由；各片段的字段、合法性、示例和校验规则放在对应 reference 中。

## 片段选择

### card

常态结构化片段。用于单个对象、单类指标或单个风险点的局部渲染。

- `metric`: 数值快照、状态概览、关键指标。
- `chart`: 趋势、对比、占比、分布、多指标关系。
- `table`: 明细清单、审计记录、编号状态、逐行文本字段。
- `map`: 坐标、边界、轨迹、空间图层。
- `recommendation`: 异常、风险、预警、离线、缺口、阈值越界、下一步建议。
- `retrospect`: 作业历史、告警历史、任务变化复盘。
- `phase-summary`: 生产周期阶段摘要。

### quick-reply

用于承接下一步可操作问题。出现风险、缺口、异常、详情钻取或可继续分析的数据时，默认搭配 quick-reply。

### report

report 是多张 card 的组合模板，不是默认片段。只有数据需要以成组报告形式聚合，或用户明确要求报告格式时才使用。

### 不生成片段

没有可视化价值、没有局部高亮信息、没有可操作后续问题，或数据不足以支撑片段字段时，不强行生成片段。

## 懒加载参考

| 场景 | 参考 |
| --- | --- |
| 事实来源、缺口处理 | `references/data-grounding.md` |
| card / quick-reply / report 结构 | `references/blocks-cards-reports.md` |
| 图表 | `references/echarts-options.md` |
| 示例、反例、自检 | `references/response-examples.md` |
| 企业 / 基地报告 | `references/report-summary-base.md` |
| 地块基础快照 | `references/report-plot-info.md` |
| 地块 WOFOST 报告 | `references/report-wofost-report.md` |
| 天气报告 | `references/report-weather.md` |
| 设备报告 | `references/report-device-info.md` |
