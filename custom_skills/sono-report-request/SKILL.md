---
name: sono-report-request
description: Primary and authoritative workflow for all SONO report generation requests. Use when the user asks to generate/export/create any agricultural report, including overall plot reports, growth analysis, 3D phenotype, WOFOST growth dynamics, or seedling monitoring. Directly call this skill's request flow and do not invoke sono-report, call-mcp-tools, chart-visualization, or agri-operation-workflow first.
---

# SONO 报告请求

## 地块勘察与专题报告

## 勘察请求与单年度分析

首次圈选创建只传`geometry`、`name`、`provider_name`、`company_id`、`site_id`、`entity_id`、`entity_info_id`；`site_id=0`表示未绑定业务地块。归属来自可信会话，不由模型猜测。客户端兼容会话的`cid`、`entity-id`、`entity-info-id`并映射到请求体。无需询问或传递`start_date/end_date`；平台冻结上海时区昨日为截止日，重试不移动日期。

主分析只选一个年度。当年已发生观测满足部署模型时序与有效覆盖要求时使用当年；季前或观测不足时直接使用上一年度完整观测季，最多回退一次。网络、模型或文件故障仍作为执行失败，不能冒充观测不足。当季已到达资料作为独立参考。必须沿用服务端reference_year、observation_period和current_reference_period，不把去年类别、生育或产量模拟值改写成今年事实或预测。专题及整体报告均不展示历史种植、五年占比和轮作。

当前遥感仅作为截止日30m/10m参考，不生成跨年度逐日融合序列。系统独立形成天气、土壤及主分析年度作物生长情景。未完成时返回真实进度；遥感、识别和分析检查点全部完成后才返回报告成功标签。查询、retry和报告data只传资源编号，不带归属或site查询参数。鉴权Key仍只取服务端固定配置；创建请求的业务字段保留。进度直接读取API的progress_detail，说明实际日期、年度、切片、波段及重试；心跳不是完成量，不由对话模型补造百分比。

专题与整体报告复用相同冻结数据和完整模板。地图按实际坐标绘制矢量分割边界和异常候选，带编号、比例尺、坐标及图例；不补造高分辨率影像、道路或经营记录。对话模型不得重写固定科学章节或复制推断为事实。

服务端需配置`MLGROWTH_BUSINESS_API_KEY`；密钥不得传给模型、放入脚本参数或输出。联调可在服务端设置`MLGROWTH_SURVEY_API_BASE_URL`。业务Key只供受信业务后端使用，归属信息来自已经授权的会话。

未完成时脚本返回JSON中的`survey_id`、`status`、进度百分比、遥感/识别/分析就绪状态，`report_url=null`；向用户说明已受理及任务编号，不得输出成功报告标签。用户查进度时仍调用本脚本并传`survey_id`。只有三个检查点全部完成时原样返回`<sono-report>...</sono-report>`。失败说明失败，不把预建地址当作成功。

整体报告仍走原有后台二次LLM流程；上下文存在`survey_id`时，脚本先取得同一联合专题的`survey_report_id`，写入后端提示。`sono-report`将该报告的遥感、识别、气象、土壤、WOFOST、异常、病虫害、气候灾害、长势、产量与品质状态固定章节加入原有整体报告，取数和渲染逻辑不另写一套。勘察尚未完成时先返回真实进度。没有明确关联的`survey_id`时，不按相似名称或区域猜测其他任务。

本节的勘察分支优先于下文旧地块分支的必填字段及唯一标签输出规则。仅已有地块整体报告仍要求旧业务字段；勘察专题不调用旧地块MCP或旧`common`整数`related_id`接口。

本地沙箱过滤环境变量时，脚本也支持固定只读凭据挂载`/app/config/credentials/mlgrowth-survey-api-key`（目录0700、文件0400）；不把凭据放入Skill目录或模型输入。当前部署保持现有沙箱策略。

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


## 统一正文与既有监测成果

关联勘察的整体报告按固定report_id读取evidence；生成器将服务端完整勘察分析章节嵌入原结果正文，沿用原960px纸张，不追加另一张报告或模型JSON。圈选地块不要求原`plot_id`或既有监测周期。气象与土壤由勘察任务独立获取；识别出可映射作物时运行明确标注假设的WOFOST机理情景，并形成规则风险、长势和产量相关结果。模型不得复制固定章节的指标或推导确定病因、已确认作物、实收产量、品质或准确率。


## 联合专题的完整地块内容

`report_type=field_survey`同时具备`plot_id`、`user_id`、`plot_name`及归属上下文时，请求脚本在勘察完成后按整体报告流程创建完整报告，固定同一`survey_report_id`和摘要。该专题包含地块基础、气象、土壤、历史长势及遥感、分割识别、异常和WOFOST；只改变标题，取数、模板、后台生成和状态回写完全共用。

纯区域勘察没有业务地块关联时，签名链接直接显示与整体报告共用的完整模板：封面、摘要、来源与方法、结果、建议、结论及PDF导出，仍展示本地块的完整冻结勘察成果，不借用其他地块数据。专题标题可不同，正文数据范围一致。生成尚未完成时预建URL只代表已受理，不能声称文件已保存。
