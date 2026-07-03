---
name: sono-report-request
description: Builds and sends SONO report-generation POST requests. Use when the user asks to generate/export/create a report and the conversation contains plot_id, cid, entity-id, entity-info-id, and plot_name.
---

# SONO 报告请求

## Quick start

本 Skill 只负责**调用报告生成服务**，不生成报告正文、不渲染 HTML。

使用 `execute_skill_script` 执行 Python 脚本；由脚本统一生成 `report_no`、组装 header/body、发起 POST，并输出 `<sono-report>...</sono-report>`：

```json
{
  "skill_name": "sono-report-request",
  "script_path": "scripts/request_report.py",
  "input": "{\"query\":\"用户原始问题\",\"plot_id\":123,\"cid\":456,\"entity-id\":789,\"entity-info-id\":101,\"plot_name\":\"一号地块\"}"
}
```

脚本默认使用内部写死的 `DEFAULT_REPORT_ENDPOINT`，不要从环境变量读取 endpoint；如需临时联调，可用 `--endpoint` 显式覆盖。

## Required input

从服务端/会话/页面路由/用户输入/历史对话提取：

- `query`：用户原始问题。
- `plot_id`：也接受 `plotId`、`plot-id`。
- `cid`。
- `entity-id`：也接受 `entity_id`、`entityId`。
- `entity-info-id`：也接受 `entity_info_id`、`entityInfoId`。
- `plot_name`：也接受 `plotName`。

缺字段时先追问，不要猜测 ID。

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
  "query": "#用户提问\n{query}\n\n#系统参数\n- plot_id: {plot_id}\n- cid: {cid}\n- entity-id: {entity-id}\n- entity-info-id: {entity-info-id}\n- plot_name: {plot_name}\n- report_no: {report_no}"
}
```

`agent_id` 可通过输入覆盖；默认必须是 `builtin-wiki-fixer`。

## Output rules

- 成功时只把脚本输出中的 `sono_report` 返回给前端，例如：`<sono-report>https://sonoagi.com/report/{report_no}.html</sono-report>`。
- 不向前端展示 header、body、endpoint、响应 JSON、token、内部参数或调试日志。
- 失败时不要伪造 URL，只提示报告生成失败并请稍后重试或联系管理员。
