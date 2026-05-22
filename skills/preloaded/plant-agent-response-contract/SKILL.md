---
name: plant-agent-response-contract
description: Use when 需要生成或审查 packages/plant-agent 的企业、基地、地块、设备、农机数据分析、SONO-MCP 取数、Markdown 正文、业务卡片、报告 blocks 或后端校验规范。
---

# Plant Agent 响应约束

## 核心原则

Agent 约束是主合同，后端只是校验、归一化和拒绝异常输出。只要遵守本 Skill，回答应能独立满足企业、基地、地块、设备、农机的数据分析和报告需求。

通用叙述、推理说明、数据来源、缺口说明都用 Markdown。`blocks` 用于结构化业务渲染，禁止在 `blocks` 中生成 `text` 或 `reasoning` 类型。

当 SONO-MCP 已成功返回企业、基地、地块、设备、农机相关数据，并且用户意图是分析、详情、建议、报告或结构化业务输出时，必须优先生成 `report`、`card`、`quick-reply` 等固定格式 block。Markdown 只能作为极短摘要或必要缺口说明，不允许替代 block 成为主输出。

## 强制流程

1. 确定分析范围: 企业、基地、地块、设备、农机，或这些对象下的细节数据、趋势、风险、建议、复盘、报告。
2. 需要事实数据时，先调用当前环境可用的 SONO-MCP 资源、工具或 connector 读取数据。不要凭模型常识补企业指标、地块面积、设备状态、农机任务、坐标或趋势点。
3. 如果 SONO-MCP 成功返回当前意图所需数据，并且任务属于分析、详情、建议、报告或结构化输出，立即进入 block-first 固定格式: 优先生成 `report` 或 `card`，再按需生成 `quick-reply`。此时 Markdown 不得作为主输出。
4. Markdown 只用于三类内容: 1-2 句总览、必要数据缺口、报告/card 无法表达的补充边界。不要在 report/card 前另写“地块分析总览”“核心依据”“详细分析报告”“农事建议”等完整章节。
5. `blocks` 只允许 `card`、`report`、`quick-reply`。MCP 成功且具备结构化展示价值时，Markdown-only 输出视为不合规。
6. 返回前按任务需要懒加载 references: 数据来源看 `data-grounding.md`，block/card/report 看 `blocks-cards-reports.md`，示例和自检看 `response-examples.md`。
7. SONO-MCP 没有返回足够数据时，用 Markdown 说明缺口，只生成已被数据支撑的 card/report。

## 懒加载参考

- SONO-MCP 数据来源与缺口处理: `references/data-grounding.md`
- 当前允许的 block、card、report 规范: `references/blocks-cards-reports.md`
- 返回示例、反例、自检清单: `references/response-examples.md`
- 后端把关规范: `packages/plant-agent/docs/backend-message-block-contract.md`

## 硬约束

- `blocks[].kind` 只允许 `card`、`report`、`quick-reply`。
- 禁止输出 `text` block 和 `reasoning` block；这两类内容归入 Markdown。
- MCP 成功后的分析、详情、建议、报告类回答必须包含 `report` 或 `card` block；除非用户明确只要纯文字解释，否则不得 Markdown-only。
- 不要在 report/card 前重复写一套完整 Markdown 分析；Markdown 最多 1-2 句，或只写数据缺口。
- 如果运行环境使用 `final_answer` 作为最终提交动作，提交内容必须是本 contract 的结构化 payload 本身，不要提交自然语言版报告或对 JSON 的解释。
- 所有事实值必须可追溯到 SONO-MCP、当前工具/API 输出、用户明确给出的事实或已归一化历史块。
- 不编造企业经营指标、基地面积、地块边界、作物长势、设备在线状态、农机作业结果、坐标、时间序列或建议依据。
- 卡片只使用已注册类型: `metric`、`chart`、`map`、`table`、`recommendation`、`retrospect`、`phase-summary`。
- 数字放 `value`，单位放 `unit`；不要把 `"15.2%"` 当作数值。
- Skill 内可用“实体”作抽象分类；面向用户可见文案优先写具体对象: 地块、设备、农机。
