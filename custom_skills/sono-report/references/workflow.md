# SONO 地块报告生成工作流

## 目录

- 触发与边界
- 地块报告章节
- 执行步骤
- 地块名称规则
- 失败处理
- 验证清单

## 触发与边界

使用 `sono-report` 仅限用户明确要求生成**地块**报告、地块 HTML、地块日报/周报/月报、导出或保存地块报告。

普通查询仍使用 `call-mcp-tools`：一次问题只调最匹配的一个 MCP 工具，不生成 HTML。

本 Skill 不生成基地报告、企业报告、全局概览报告，也不使用 `get_summary_base`。如果用户要求基地/企业报告，应说明当前 Skill 只支持地块报告，并请用户提供地块名称或 `plot_id`。

## 地块报告章节

| 章节 | 工具 | 说明 |
|---|---|---|
| 地块基础与长势 | `get_plot_info` | 必须调用；用于获取真实地块名称、面积、作物、生长阶段、评级和建议 |
| 天气与作业窗口 | `get_weather` | 用户要求天气/预警/作业窗口时调用；未来/本周传 `days=7` |
| 设备状态 | `get_plot_device_info` | 仅当用户提供明确 `device_id` 时调用 |
| WOFOST 模型 | `get_wofost_report` | 用户要求模型/预测/WOFOST 时调用；必须有 `cid + plot_id` |

## 执行步骤

1. 判断用户是否要求地块报告；若是基地/企业报告，停止并请用户提供地块范围。
2. 读取 `sono-mcp/SKILL.md`，按其参数纪律调用 MCP。
3. 必须先调用或取得 `get_plot_info` 结果，以获得真实 `payload.name`。
4. 按已调用工具读取对应 reference：`tool-plot-info.md`、`tool-weather.md`、`tool-device-info.md`、`tool-wofost-report.md`。
5. 构造原始 `REPORT_DATA` JSON。
6. 用 `execute_skill_script` 执行一体化脚本，并把 `REPORT_DATA` 放入 `input` 字段：

```json
{
  "skill_name": "sono-report",
  "script_path": "scripts/generate_report.py",
  "args": ["--output-dir", "/app/report/", "--strict"],
  "input": "<REPORT_DATA JSON>"
}
```

7. 读取脚本输出 JSON 中的 `sono_report`，原样返回给用户。格式必须是 `<sono-report>https://sonoagi.com/report/{file}</sono-report>`，不要把本地 `final_html` 路径作为用户可见结果。

### 手动命令行排查

只有在不通过 `execute_skill_script`、而是在 shell 中手动排查时，才分步运行：

```bash
WORKDIR=$(python scripts/create_report_workspace.py --base-dir /app/report/)
python scripts/preprocess_report_data.py "$WORKDIR/input-report-data.json" "$WORKDIR/normalized-report-data.json" --strict
python scripts/render_report_html.py template.html "$WORKDIR/normalized-report-data.json" "$WORKDIR/generated-report.html"
python scripts/save_report_html.py "$WORKDIR/generated-report.html" "$WORKDIR/normalized-report-data.json" --output-dir /app/report/
```

不要把 `$WORKDIR/generated-report.html` 当最终报告路径。

## 地块名称规则

地块报告的用户可见标题和最终文件名必须使用真实地块名称。

允许用 `plot_id` 作为 MCP 入参，但禁止把 `plot_id`、`plot_no` 或 `地块 23181` 作为：

- `meta.subjectName`
- `meta.plotName`
- HTML 标题
- 保存文件名

如果只有 `plot_id`：先调用 `get_plot_info` 获取 `payload.name`；获取不到则追问用户补充地块名称。

## 失败处理

- MCP `isError=true`：该模块写空状态，不暴露 token、内部 URL 或内部配置。
- MCP 空结果：不是错误；隐藏模块或写“暂无相关数据”。
- 预置脚本失败：不要生成报告，先补齐数据。
- 渲染脚本失败：修正 `REPORT_DATA` 或模板占位符后重试。
- 保存脚本失败：报告保存失败；说明原因并保留 `$WORKDIR` 路径供排查。

## 验证清单

- 已创建唯一 `WORKDIR`。
- 中间文件位于 `$WORKDIR`，不在 Skill 根目录。
- HTML 以 `<!DOCTYPE html>` 开头。
- `dataSources` 不包含 `get_summary_base`。
- 标题不是 `plot_id` 风格。
- 不显示 `undefined`、`null`、`NaN`。
- WOFOST 数据表述为“模型模拟/预测”。
- 最终文件路径位于 `/app/report/`。
- 用户可见结果使用 `<sono-report>https://sonoagi.com/report/{file}</sono-report>` 包裹。
