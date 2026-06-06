---
name: plant-agent-response-contract
description: Use when 需要生成或审查 packages/plant-agent 的企业、基地、地块、设备、农机数据分析、SONO-MCP 取数、Markdown 正文、业务卡片、报告 blocks 或后端校验规范。
---

# Plant Agent 响应约束

## 意图判断门控

**本约束不是所有回复的默认格式。只有意图命中结构化输出类型时才加载并执行 block 规范。**

### 结构化输出意图（进入 block 格式路径）

以下意图触发本约束：

- **报告类**：生成报告、查看报告、基地报告、地块分析报告、设备运行报告、企业经营报告
- **分析类**：综合分析、种植分析、长势分析、地块情况、地块状态综合分析、效益分析、对比分析、多维度分析
- **统计类**：汇总数据、统计情况、整体情况、全局情况、各基地对比
- **建议类**：农事建议、作业建议、管理建议（需要多个指标联合支撑的）
- **多维展示**：同时涉及 2 个以上指标/对象的综合展示
- **风险预警类**：风险评估、异常判断、预警分析

### 普通回答意图（直接 Markdown，不走 block）

以下意图**即使 MCP 成功返回数据也直接 Markdown 回答**，不走报告格式：

- **单值查询**："这个地块叫什么？"、"面积多少亩？"、"当前温度多少？"、"设备在线吗？"
- **是否类**："今天适合打药吗？"、"设备有没有异常？"
- **简单确认**："还有多少天收获？"、"播种日期是什么时候？"
- **闲聊/打招呼/感谢**
- **知识性问题**：不需要系统数据的农业知识、概念解释
- **用户明确要简洁**："直接告诉我"、"简单说一下"
- **续接对话**：对上一条回复的追问或补充

### 判断歧义时

意图不明确时优先用 Markdown 简洁回答；**用户没有主动要求报告/分析，不要主动生成 report block**。

---

## 核心原则

- 通用叙述、推理说明、数据来源、缺口说明 → Markdown
- 结构化业务展示 → `blocks`（只允许 `card`、`report`、`quick-reply`）
- 结构化最终输出 → 必须是严格 JSON object，整体可被 `JSON.parse()` 解析；禁止输出半截 JSON、JS 对象字面量或缺值字段
- ECharts 图表 → 使用 `type: "chart"` 卡片，`data.option` 必须是完整纯 JSON ECharts option；由 LLM 按数据语义选择最合适的 ECharts 图表类型
- 图表优先级高于表格：时间序列、分类对比、占比、分布、多指标对比、风险强度、空间轨迹等可视化数据必须优先生成 `chart`，不要用 `table` 替代图表
- 一次综合分析/报告默认只生成一份主 `report`；同一地块/基地/企业的天气、设备、积温、WOFOST、评级、建议等是分析维度，放进同一个 `report.cards[]`
- `blocks` 中禁止生成 `text` 或 `reasoning` 类型

**仅当意图命中结构化输出类型时**：SONO-MCP 成功返回数据 → 必须优先生成 block，Markdown 只能做极短摘要或缺口说明。

## 强制流程

1. 确定范围：企业、基地、地块、设备、农机。
2. 需要事实数据时先调用 SONO-MCP，不凭模型常识补指标、面积、状态、坐标。
3. 地块情况、地块分析、地块报告类意图中，若上下文已有 `cid` 和 `plot_id`，`get_wofost_report` 是重点分析来源；先提取 WOFOST 生育进程、产量/生物量、水分/养分平衡和模型建议，再补充 `get_plot_info` 基础快照。
4. 识别用户角色（见各工具报告参考），从 payload 定向提取该角色关注的字段。
5. MCP 成功且意图是报告/分析/建议 → block-first：先生成 `report` 或 `card`，再生成 `quick-reply`。Markdown 不得作为主输出。
6. 同一用户问题只确定一个主分析范围；若主范围是地块，天气/设备/作业/积温/WOFOST 都作为该地块报告的 cards，不拆成“地块综合分析报告 + 未来天气报告”等多份 report。
7. Markdown 只用于：1-2 句总览、必要数据缺口、block 无法表达的边界说明。
8. MCP 返回数据不足时 → Markdown 说明缺口，只生成有数据支撑的 block。
9. 提交前必须做 JSON 合法性自检：最终 payload 整体可解析，所有 key 都有合法 value，所有 `chart.data.option` 都是纯 JSON 对象；任一字段缺值时跳过该字段/item/card，不得留下空 key。

## 懒加载参考

按当前任务按需加载，不要一次全加载：

| 任务                              | 加载参考                                                      |
| --------------------------------- | ------------------------------------------------------------- |
| 数据来源、缺口处理                | `references/data-grounding.md`                                |
| block / card / report 规范        | `references/blocks-cards-reports.md`                          |
| ECharts chart option 规范         | `references/echarts-options.md`                               |
| 返回示例、反例、自检              | `references/response-examples.md`                             |
| 企业/基地报告（get_summary_base） | `references/report-summary-base.md`                           |
| 地块基础快照（get_plot_info）     | `references/report-plot-info.md`                              |
| 地块 WOFOST 报告（get_wofost_report） | `references/report-wofost-report.md`                       |
| 天气报告（get_weather）           | `references/report-weather.md`                                |
| 设备报告（get_plot_device_info）  | `references/report-device-info.md`                            |
| 后端校验规范                      | `packages/plant-agent/docs/backend-message-block-contract.md` |

## 硬约束

- `blocks[].kind` 只允许 `card`、`report`、`quick-reply`
- MCP 成功后的报告/分析类回答必须含 `report` 或 `card`；用户明确只要纯文字时除外
- 同一主分析对象的一次综合报告只生成一个 `report` block；除非用户明确要求“分别生成/拆开多个报告”或同时比较多个互不从属对象
- 不要在 report/card 前写完整 Markdown 分析章节；最多 1-2 句
- `final_answer` 提交内容必须是结构化 payload 本身，不要提交自然语言版报告
- `final_answer` 必须是严格 JSON：双引号 key/string、完整冒号和值、数组/对象闭合、无尾逗号、无注释、无 Markdown 代码围栏
- 禁止出现缺值字段或 JS 简写字段，例如 `"value"`、`"top"`、`"smooth"`、`"yAxisIndex"` 后面没有 `: <value>`；布尔值必须写成 `true/false`
- 禁止在最终 payload 中输出 `undefined`、`NaN`、`Infinity`、函数、`Date` 对象、正则；未知值不要占位，直接省略对应字段/item/card，并在 Markdown 简短说明数据缺口
- JSON 合法性优先级高于卡片数量、图表丰富度和 `chartRequest` 追溯字段；payload 过长或不确定时，减少 card、聚合数据、删除可选 `chartRequest`，也不能提交不完整 JSON
- 所有事实值必须可追溯到 SONO-MCP/工具输出/用户明确事实
- 不编造指标、面积、边界、长势、状态、坐标、时间序列、建议依据
- 卡片类型只用：`metric`、`chart`、`map`、`table`、`recommendation`、`retrospect`、`phase-summary`
- `chart` 卡片必须输出 `data.option` 纯 JSON ECharts option；`chartType` / `chartRequest` 是推荐元数据但不是渲染必需；不要只输出 `variant/xAxis/series` 简化结构
- 能用图表表达趋势、对比、占比、分布、关系、轨迹或多指标结构时，必须优先用 `chart`；`table` 只用于明细清单、审计记录、精确逐行字段或图表无法表达的文本型行数据
- 数字放 `value`，单位放 `unit`；禁止把 `"15.2%"` 当数值
- `focusEntities.kind` 只用 `plot`、`device`、`machinery`；企业和基地写进 Markdown 或 report 标题
- `recommendation` 卡片：`data.title` 和每条 `items[].title` 均为**必需**，不能省略也不能为空字符串
- WOFOST 模型输出必须表述为“模型模拟/预测”，不能写成实际测产、实测产量或已发生结果
