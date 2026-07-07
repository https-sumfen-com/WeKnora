# SONO 地块报告生成工作流

## 目录

- 触发与边界
- 地块报告章节
- 执行步骤
- 地块名称规则
- 失败处理
- 验证清单

## 触发与边界

使用 `sono-report` 仅限后端内部第二次 LLM 报告渲染对话：prompt 必须包含 `##用户问题`、`##系统参数`、`report_no` 和 `report_url`。普通用户首次要求生成/导出/创建报告时，必须先使用 `sono-report-request` 保存报告记录，不要直接使用本 Skill。

普通查询仍使用 `call-mcp-tools`：一次问题只调最匹配的一个 MCP 工具，不生成 HTML。

本 Skill 不生成基地报告、企业报告、全局概览报告，也不使用 `get_summary_base`。如果用户要求基地/企业报告，应说明当前 Skill 只支持地块报告，并请用户提供地块名称或 `plot_id`。整体地块报告指同一地块下的基础信息、预警和 4 类专项模块综合，不是基地/企业整体报告。所有报告都按 `demo.html` 风格生成论文式技术报告。

## 地块报告章节

| 章节 | 工具 | 说明 |
|---|---|---|
| 地块基础与长势 | `get_plot_info` | 必须调用；用于获取真实地块名称、面积、作物、生长阶段、评级和建议 |
| 地块预警 | `get_plot_warning` | 整体报告默认调用；预警/风险报告必须调用 |
| 细分模块报告 | `get_report_by_type` | 整体地块报告默认包含地块类模块；单独细分报告只调用指定 `type` |
| 天气与作业窗口 | `get_weather` | 用户要求天气/预警/作业窗口时调用；未来/本周传 `days=7` |
| 设备状态 | `get_plot_device_info` | 仅当用户提供明确 `device_id` 时调用 |
| WOFOST 模型 | `get_wofost_report` | 用户要求模型/预测/WOFOST 时调用；必须有 `cid + plot_id` |

## 执行步骤

1. 确认当前是后端内部第二次 LLM 对话，并从 `##系统参数` 提取 `plot_id`、`cid`、`entity-id`、`entity-info-id`、`plot_name`、`report_type`、`report_no`、`report_url`；缺少 `report_no` 或 `report_url` 时停止，不要自行创建新地址。
2. 判断 `##用户问题` 是否要求地块报告；若是基地/企业报告，停止并请用户提供地块范围。
3. 读取 `sono-mcp/SKILL.md`，按其参数纪律调用 MCP。
4. 必须先调用或取得 `get_plot_info` 结果，以获得真实 `payload.name`。
5. 判断报告范围：
   - 整体地块报告：调用 `get_plot_warning`，并用同一 `plot_id` 调用地块类 `get_report_by_type`：`plot_growth_analysis`、`plot_3d_phenotype`、`plot_growth_dynamics`、`plot_seedling_monitoring`。空结果或失败模块跳过；有多天数据时必须转成趋势图和分析项。`plot_growth_dynamics` 归入 WOFOST 生长动态，不再默认追加 `plot_wofost`。
   - 细分模块报告：只调用用户指定的 `get_report_by_type.type`，但报告正文要比整体报告中的卡片更深入，必须形成完整论文式结构，仍要从多天数据中挖掘趋势、异常点、极值、变化幅度、原因和建议。
   - 天气、设备、WOFOST 模型日报：只有用户明确要求对应内容时追加。
6. 按已调用工具读取对应 reference：`tool-plot-info.md`、`tool-plot-warning.md`、`tool-report-by-type.md`、`tool-weather.md`、`tool-device-info.md`、`tool-wofost-report.md`。
7. 构造原始 `REPORT_DATA` JSON：`get_plot_warning` 写入 `plotWarnings[]`，`get_report_by_type` 写入 `moduleReports[]`。`moduleReports[]` 内部字段开放，可写 `trendSeries`、`timeSeries`、`dailyData`、`charts[]`、`analysisItems`、`insights`、`findings`、`sections`、`tables`；可选写入 `paper.abstract`、`paper.keywords`、`paper.methods`、`paper.findings`、`paper.discussion`、`paper.conclusions`、`paper.limitations`。不要为了贴合固定字段而丢掉可分析数据。
8. 用 `execute_skill_script` 执行一体化脚本，并把 `REPORT_DATA` 放入 `input` 字段：

```json
{
  "skill_name": "sono-report",
  "script_path": "scripts/generate_report.py",
  "args": [
    "--output-dir", "/app/report/",
    "--strict",
    "--report-no", "{report_no}",
    "--report-url", "{report_url}",
    "--plot-id", "{plot_id}",
    "--cid", "{cid}",
    "--entity-id", "{entity-id}",
    "--entity-info-id", "{entity-info-id}"
  ],
  "input": "<REPORT_DATA JSON>"
}
```

9. 读取脚本输出 JSON 中的 `sono_report`，原样返回给调用方。格式必须是 `<sono-report>{report_url}</sono-report>`，不要把本地 `final_html` 路径作为用户可见结果。

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
- 保存脚本失败：报告保存失败；脚本应尽量回写 `status=2`，说明原因并保留 `$WORKDIR` 路径供排查。

## 验证清单

- 已创建唯一 `WORKDIR`。
- 中间文件位于 `$WORKDIR`，不在 Skill 根目录。
- HTML 以 `<!DOCTYPE html>` 开头。
- `dataSources` 不包含 `get_summary_base`。
- 整体地块报告已尝试写入 `plotWarnings[]` 和 4 类专项 `moduleReports[]`：长势分析、三维表型、生长动态、苗情监控。
- 报告包含标题页、摘要、数据来源与处理方法、结果与分析、讨论与农事建议、结论与附录。
- 不展示播种进度图或地块结构图；相关信息只作为 KPI、文本或地块生长状态进度条呈现。
- 细分模块报告只写入用户指定的 `moduleReports[].type`，但模块内部要包含足够详细的趋势图和分析项。
- 标题不是 `plot_id` 风格。
- 不显示 `undefined`、`null`、`NaN`。
- 风险、建议、分析项必须有真实标题或正文；没有有效内容时跳过，不能渲染空白风险事项。
- 表格和图表必须有有效行、有效列和真实数值；字段不匹配或全空时跳过，不展示空表或空图。
- `level`、`green`、`blue`、`amber`、`red` 等状态值只作内部等级/样式，不作为页面可见说明直接输出。
- WOFOST 数据表述为“模型模拟/预测”。
- 页脚不展示 `get_plot_info`、`get_report_by_type` 等具体接口名，只写真实地块数据记录来源。
- 最终文件路径位于 `/app/report/`，且文件名来自 `report_url`。
- 成功时已回写 `status=1`；失败时已尽量回写 `status=2`。
- 用户可见结果使用 `<sono-report>{report_url}</sono-report>` 包裹。
