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
- **分析类**：综合分析、种植分析、长势分析、效益分析、对比分析、多维度分析
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
- `blocks` 中禁止生成 `text` 或 `reasoning` 类型

**仅当意图命中结构化输出类型时**：SONO-MCP 成功返回数据 → 必须优先生成 block，Markdown 只能做极短摘要或缺口说明。

## 强制流程

1. 确定范围：企业、基地、地块、设备、农机。
2. 需要事实数据时先调用 SONO-MCP，不凭模型常识补指标、面积、状态、坐标。
3. 识别用户角色（见各工具报告参考），从 payload 定向提取该角色关注的字段。
4. MCP 成功且意图是报告/分析/建议 → block-first：先生成 `report` 或 `card`，再生成 `quick-reply`。Markdown 不得作为主输出。
5. Markdown 只用于：1-2 句总览、必要数据缺口、block 无法表达的边界说明。
6. MCP 返回数据不足时 → Markdown 说明缺口，只生成有数据支撑的 block。

## 懒加载参考

按当前任务按需加载，不要一次全加载：

| 任务                              | 加载参考                                                      |
| --------------------------------- | ------------------------------------------------------------- |
| 数据来源、缺口处理                | `references/data-grounding.md`                                |
| block / card / report 规范        | `references/blocks-cards-reports.md`                          |
| 返回示例、反例、自检              | `references/response-examples.md`                             |
| 企业/基地报告（get_summary_base） | `references/report-summary-base.md`                           |
| 地块报告（get_plot_info）         | `references/report-plot-info.md`                              |
| 天气报告（get_weather）           | `references/report-weather.md`                                |
| 设备报告（get_plot_device_info）  | `references/report-device-info.md`                            |
| 后端校验规范                      | `packages/plant-agent/docs/backend-message-block-contract.md` |

## 硬约束

- `blocks[].kind` 只允许 `card`、`report`、`quick-reply`
- MCP 成功后的报告/分析类回答必须含 `report` 或 `card`；用户明确只要纯文字时除外
- 不要在 report/card 前写完整 Markdown 分析章节；最多 1-2 句
- `final_answer` 提交内容必须是结构化 payload 本身，不要提交自然语言版报告
- 所有事实值必须可追溯到 SONO-MCP/工具输出/用户明确事实
- 不编造指标、面积、边界、长势、状态、坐标、时间序列、建议依据
- 卡片类型只用：`metric`、`chart`、`map`、`table`、`recommendation`、`retrospect`、`phase-summary`
- 数字放 `value`，单位放 `unit`；禁止把 `"15.2%"` 当数值
- `focusEntities.kind` 只用 `plot`、`device`、`machinery`；企业和基地写进 Markdown 或 report 标题
