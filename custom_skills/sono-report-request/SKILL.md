---
name: sono-report-request
description: Primary and authoritative workflow for all SONO report generation requests. Use when the user asks to generate/export/create any agricultural report, including overall plot reports, growth analysis, 3D phenotype, WOFOST growth dynamics, or seedling monitoring. Directly call this skill's request flow and do not invoke sono-report, call-mcp-tools, chart-visualization, or agri-operation-workflow first.
---

# SONO 报告请求

## Quick start

本 Skill 是 SONO 报告生成意图的**唯一入口**，只负责**调用报告生成服务**，不生成报告正文、不渲染 HTML。

## Routing rule

当普通用户表达“生成报告 / 导出报告 / 创建报告 / 生成苗情监控报告 / 生成长势分析报告 / 生成整体地块报告 / 生成三维表型报告 / 生成生长动态报告”等意图时，必须直接执行本 Skill 的请求流程。

不要先调用，且本 Skill 执行过程中禁止转交或触发：

- `sono-report`
- `call-mcp-tools`
- `chart-visualization`
- `agri-operation-workflow`

例外：如果当前 prompt 已包含 `##用户问题`、`##系统参数`、`report_no` 和 `report_url`，说明已经进入后端第二次 LLM 报告渲染对话；不要再次调用本 Skill，改用 `sono-report` 真正生成报告文件。

本 Skill 的 API 后端负责保存报告记录，并用本 Skill 传入的 `query` 再发起一次内部 LLM 对话；第二次对话应调用 `sono-report` 取数、渲染、保存报告并回写状态。脚本会在 `query` 中写入 `##Skill访问机制`、`force_skill: sono-report`、`forbidden_skills: sono-report-request, agri-operation-workflow` 和固定 `final_response`，用于强制第二次对话进入 `sono-report`，避免回调本 Skill。整个两阶段报告流程都不使用 `agri-operation-workflow`。

使用 `execute_skill_script` 执行 Python 脚本；由脚本统一生成 `report_no`、从用户问题推断 `report_type`、组装 header/body、发起 POST。脚本默认 stdout 只输出 `<sono-report>...</sono-report>`，LLM 必须原样返回这一行：

```json
{
  "skill_name": "sono-report-request",
  "script_path": "scripts/request_report.py",
  "input": "{\"query\":\"生成苗情监控报告\",\"user_id\":\"u123\",\"plot_id\":123,\"cid\":456,\"entity-id\":789,\"entity-info-id\":101,\"plot_name\":\"一号地块\"}"
}
```

脚本默认使用内部写死的 `DEFAULT_REPORT_ENDPOINT`，不要从环境变量读取 endpoint；如需临时联调，可用 `--endpoint` 显式覆盖。`--json-output` 只允许手动排查时使用，正式 Skill 执行不要使用，避免 LLM 把 JSON 或说明文字返回给前端。

## Required input

从服务端/会话/页面路由/用户输入/历史对话提取：

- `query`：用户原始问题，用于推断 `report_type`。
- `user_id`：对话中的用户 ID；脚本会作为 body 的 `tgzn_user_id` 传递。也接受 `tgzn_user_id`、`userId`、`user-id`。
- `plot_id`：也接受 `plotId`、`plot-id`。
- `cid`。
- `entity-id`：也接受 `entity_id`、`entityId`。
- `entity-info-id`：也接受 `entity_info_id`、`entityInfoId`。
- `plot_name`：也接受 `plotName`、`plot-name`。

缺字段时先追问，不要猜测 ID。无法从 `query` 判断报告类型时，先追问具体报告类型，不要猜测。

## Report type mapping

脚本按用户原始问题推断 `report_type`，并用中文名称生成 `title`：`plot_name【report_type_cn_name】`。

| 用户意图/中文名称 | body.report_type |
| --- | --- |
| 整体地块报告 | `overall_report` |
| 长势分析 | `plot_growth_analysis` |
| 三维表型 | `plot_3d_phenotype` |
| 生长动态（wofost） | `plot_growth_dynamics` |
| 苗情监控 | `plot_seedling_monitoring` |

示例：用户问题是“生成苗情监控报告”，`report_type` 必须为 `plot_seedling_monitoring`，`title` 为 `{plot_name}【苗情监控】`。

## Request contract

脚本组装 header：

```text
Content-Type: application/json
plot-id: {plot_id}
cid: {cid}
entity-id: {entity-id}
entity-info-id: {entity-info-id}
```

脚本组装 JSON body：

```json
{
  "related_id": "{plot_id}",
  "report_no": "{uuid}",
  "report_url": "https://sonoagi.com/report/{report_no}.html",
  "agent_id": "builtin-wiki-fixer",
  "query": "##用户问题\n{query}\n\n##Skill访问机制\n- force_skill: sono-report\n- route_stage: backend_internal_report_render\n- forbidden_skills: sono-report-request, agri-operation-workflow\n- final_response: <sono-report>https://sonoagi.com/report/{report_no}.html</sono-report>\n- instruction: 本次内部对话必须调用 sono-report skill 生成并保存报告；禁止回调 sono-report-request；禁止调用 agri-operation-workflow。生成完成后只返回 final_response 指定格式。\n\n##系统参数\n- plot_id: {plot_id}\n- cid: {cid}\n- entity-id: {entity-id}\n- entity-info-id: {entity-info-id}\n- plot_name: {plot_name}\n- report_type: {report_type}\n- report_no: {report_no}\n- report_url: https://sonoagi.com/report/{report_no}.html",
  "tgzn_user_id": "{user_id}",
  "title": "{plot_name}【{report_type_cn_name}】",
  "report_type": "{report_type}"
}
```

`agent_id` 可通过输入覆盖；默认必须是 `builtin-wiki-fixer`。

## Output rules

- 成功时最终回复必须是**唯一一行**：`<sono-report>{report_url}</sono-report>`。
- 直接原样返回脚本 stdout；不要添加“已生成”“正在生成”、Markdown、代码块、JSON、解释文字、标点或换行后的补充说明。
- 如果脚本使用默认模式，stdout 已经是 `<sono-report>...</sono-report>`；如果手动调试使用了 `--json-output`，也只能取其中 `sono_report` 的值作为最终回复。
- 不向前端展示 header、body、endpoint、响应 JSON、token、内部参数或调试日志。
- 失败时不要伪造 URL，只提示报告生成失败并请稍后重试或联系管理员。
