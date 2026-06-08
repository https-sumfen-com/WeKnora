---
name: plant-agent-response-contract
description: Use when 需要判断农业分析回答是否应走业务卡片、quick-reply、结构化渲染、报告组合模板或自然回复路径。
---

# 农业分析响应意图路由

## 边界

本文件只做意图判断和懒加载路由。

这是一个可运行 skill。结构化输出的常态是 `card` 和 `quick-reply`；`report` 只是把多张 card 组合起来的模板。card、report、chart、字段、取数、示例和运行时结构化输出检查，全部放在对应 reference 中。默认由大模型自然回复。

## 判定顺序

### 1. 局部结构化

用户明确要求卡片、图表、地图、表格、指标面板、局部分析卡片、可视化或后续追问按钮，询问“今天有哪些值得关注”“今日重点”“风险概览”等关注事项，或读取到的数据存在异常、风险、预警、离线、缺口、阈值越界、需要局部高亮呈现时，走 `card` / `quick-reply` 路径。

命中结构化路径后，最终回答只能输出结构化 payload，不要再输出整段自然语言正文或 Markdown 表格。异常、风险、预警、离线、阈值越界等场景必须至少生成一张 `recommendation` card，并默认追加 `quick-reply`。

加载：

- `references/blocks-cards-reports.md`
- 图表场景加载 `references/echarts-options.md`
- 需要事实数据时加载 `references/data-grounding.md`

### 2. 明确报告

用户明确要求生成、查看、导出、形成、打开或按报告格式输出时，走 `report` 组合模板路径。

加载：

- `references/blocks-cards-reports.md`
- 对应对象或工具的报告参考
- 需要事实数据时加载 `references/data-grounding.md`

不要因为普通分析、统计、建议或单张卡片需求生成 report。

### 3. 合约审查

用户要求审查、校验或修改结构化输出合约时，加载 `references/blocks-cards-reports.md` 和 `references/response-examples.md`。

### 4. 自然回复

其余情况保持自然回复，包括单值查询、是否/确认类、普通分析、建议、统计、汇总、知识问答、闲聊、续接追问和用户明确要求简洁文字的场景。

意图不明确时也走自然回复。分析、统计、建议、地块情况这些词本身不是 report 触发器。

## 懒加载参考

| 场景 | 参考 |
| --- | --- |
| 事实来源、缺口处理 | `references/data-grounding.md` |
| report / card / quick-reply | `references/blocks-cards-reports.md` |
| 图表 | `references/echarts-options.md` |
| 示例、反例、自检 | `references/response-examples.md` |
| 企业 / 基地报告 | `references/report-summary-base.md` |
| 地块基础快照 | `references/report-plot-info.md` |
| 地块 WOFOST 报告 | `references/report-wofost-report.md` |
| 天气报告 | `references/report-weather.md` |
| 设备报告 | `references/report-device-info.md` |
| 结构化输出检查 | `references/blocks-cards-reports.md`、`references/response-examples.md` |
