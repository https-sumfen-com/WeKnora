# SONO-MCP 到地块 REPORT_DATA 映射

## 目录

- `get_plot_info`
- `get_plot_warning`
- `get_report_by_type`
- `get_weather`
- `get_plot_device_info`
- `get_wofost_report`
- 禁止展示字段

读取本文件前，先按实际调用工具读取对应 `sono-mcp/references/tool-*.md`，本文件只说明报告层映射。

禁止使用或展示 `get_summary_base`。本 Skill 只生成基于地块的报告。整体地块报告不是基地/企业全局报告，而是在同一真实地块下组合基础信息、预警和细分模块。

## `get_plot_info`

参考：`custom_skills/sono-mcp/references/tool-plot-info.md`

映射：

- `name` → `meta.plotName`、`meta.subjectName`、`plots[].name`
- `area`、`area_unit`、`base.name`、`plot_type.name` → `overview.kpis`
- `plot_crop.crop.name` → `plots[].crop`
- `plot_crop.already_days` → `plots[].days`
- `plot_crop.progress` → `plots[].progress`
- `plot_crop.current_crop_model_cycle.name` → `plots[].stage`
- `grade[]` → `plots[].grade` 和 `recommendations[]`
- `accumulated_tp` → 积温积雨 KPI 或专项分析项
- `iot_device` → 设备摘要或建议
- `current_crop_model_cycle.remark` 中“注意事项” → `recommendations[]`

展示规则：

- 不生成播种进度图或地块结构图。
- `plots[].progress` 只用于地块作物生长状态进度条或概览 KPI。
- “地块面积”、地块类型、作物等只进入 `overview.kpis[]` 或 `plots[]` 文本字段。

如果 `plot_crop` 为空，不输出作物、阶段、播种日期、预计收获等占位字段。

## `get_weather`

参考：`custom_skills/sono-mcp/references/tool-weather.md`

映射：

- `payload.now` → `weather.now`
- `payload.days[]` → `weather.forecast`
- 预警阈值命中 → `weather.alerts[]` 和 `recommendations[]`
- 连续无预警日期 → 作业窗口 recommendation

未来/本周/作业窗口报告传 `days=7`；当前天气不传 `days`。

## `get_plot_device_info`

参考：`custom_skills/sono-mcp/references/tool-device-info.md`

映射：

- `device_detail.name` → `devices.items[].name`
- `device_detail.deviceType.name` → `devices.items[].type`
- `plot.name` → `devices.items[].plotName`
- `device_detail.is_online` → `devices.items[].status`（0=offline，1=online）
- `device_detail.last_device_time` → `devices.items[].lastTime`
- `device_detail.device_data[]` 中 `is_open=1` → `devices.items[].metrics[]`
- 离线、低电量、通信延迟、风速过大 → `recommendations[]`

没有明确 `device_id` 时不要调用该工具。

## `get_wofost_report`

参考：`custom_skills/sono-mcp/references/tool-wofost-report.md`

映射：

- `report_date` → `wofost.reportDate` 和 `meta.reportDate`
- `report_no` → `wofost.reportNo`
- `daily_report_pdf` / `daily_report_csv` → `wofost.links`
- `summary_report_json.DOS/DOE/DOA/DOM/DOH/DOV` → `wofost.phenology`
- `summary_report_json.DVS/LAIMAX/RD/TAGP/TWSO/NuptakeTotal` → `wofost.kpis`
- `terminal_report_json.RAINT/TOTIRR/TOTINF/PERCT/WTRAT/EVST/EVWT/LOSST/TSR` → `wofost.waterBalance`
- `csv_content[]` 的有效 `DVS/LAI/TAGP/WSO/SM/TRA/RD/NuptakeTotal` → `charts.biomassTrend` 或趋势摘要

如果需要页面中出现 WOFOST 趋势图，必须把 `csv_content[]` 抽样或聚合成 `charts.biomassTrend[]`。不要把完整 `csv_content[]` 原样保留在最终报告 JSON 中。

如 WOFOST 结果只有 `plot_id`/`plot_no` 没有地块名称，先调用 `get_plot_info` 获取地块名称，再生成报告。

## `get_plot_warning`

参考：`custom_skills/sono-mcp/references/tool-plot-warning.md`

映射：

- `plot_name` / `plotName` / `plot.name` → `plotWarnings[].plotName`，但标题仍以 `meta.plotName` 为准
- `title` / `name` / `warning_type` / `type` / `category` → `plotWarnings[].title`
- `warning_level` / `level` / `grade` / `severity` → `plotWarnings[].level`
- `content` / `message` / `description` / `reason` → `plotWarnings[].body`
- `warning_time` / `start_date` / `startDate` / `created_at` → `plotWarnings[].time`
- `status` / `state` / `is_handled` → `plotWarnings[].status`
- `suggestion` / `advice` / `handle_suggestion` / `recommendation` → `plotWarnings[].suggestions[]`

需要处置的高风险/严重风险同步写入 `recommendations[]`，`source` 使用 `get_plot_warning`。空列表表示未查询到预警，不写泛化提醒。

## `get_report_by_type`

参考：`custom_skills/sono-mcp/references/tool-report-by-type.md`

整体地块报告默认尝试地块类模块：

- `plot_growth_analysis`
- `plot_3d_phenotype`
- `plot_growth_dynamics`
- `plot_seedling_monitoring`
- `plot_wofost`

`device_analysis` 只有在有明确 `device_id` 且用户要求设备分析时调用。用户只要求某个细分报告时，只调用并展示该 `type`。

通用映射到 `moduleReports[]`：

- `type` → `moduleReports[].type`
- `report_name` / `title` / `name` → `moduleReports[].title`
- `report_date` / `date` → `moduleReports[].reportDate`
- `start_date` / `end_date` → `moduleReports[].startDate` / `moduleReports[].endDate`
- `period_type` → `moduleReports[].periodType`
- `conclusion` / `summary` / `overview` / `result` → `moduleReports[].conclusion`
- `metrics` / `index` / `data` 中的关键数值项 → `moduleReports[].metrics[]`
- `warnings` / `risks` / `alerts` / `abnormal` → `moduleReports[].risks[]`
- `suggestions` / `recommendations` / `advice` → `moduleReports[].suggestions[]`
- `report_url` / `reportUrl` / `url` / `file_url` / `pdf_url` → `moduleReports[].link`
- 多天数组、日报数组、趋势数据、曲线数据 → `moduleReports[].trendSeries` 或 `moduleReports[].charts[]`
- 从多天数据挖掘出的结论、异常点、极值、变化幅度、原因判断 → `moduleReports[].analysisItems[]`
- 需要保留的解释段落和小表格 → `moduleReports[].sections[]` / `moduleReports[].tables[]`

开放规则：

- 不要被字段名限制。`trendSeries`、`timeSeries`、`dailyData`、`rows`、`records`、`charts[].rows`、`charts[].labels + series[]` 都可以进入 `moduleReports`；模板会尽量渲染。
- Agent 可以自由挖掘更多分析项，但每一项必须能追溯到 payload 中的时间序列、指标、风险或建议字段。
- Python 预处理只做底线校验，不会因为细分模块来源或开放字段名不同而丢弃内容；不要把真实分析数据压缩成一句泛泛结论。

类型专属处理：

- `plot_growth_analysis`：挖掘 NDVI/LAI/覆盖度多天趋势、阶段变化、异常区域、作物/批次关联和建议。
- `plot_3d_phenotype`：挖掘株高、冠层覆盖、LAI、生物量的分布/变化，识别表型异常或空间差异。
- `plot_growth_dynamics`：必须形成趋势图或趋势分析项，包含最近值、极值、变化幅度、异常日期；不要逐点展示全量序列。
- `plot_seedling_monitoring`：挖掘出苗率、苗数/密度、整齐度、缺苗断垄的多天变化和补苗优先级。
- `plot_wofost`：按模型模拟/报告口径展示，多天模型序列进入 `trendSeries` 或 `charts[]`；不要说成实测产量。
- `device_analysis`：挖掘在线率、最后通信、核心遥测、异常时段、连续离线/波动规律和维护建议。

如果 `get_report_by_type` 返回下载链接，只放到 `moduleReports[].link`，不要展开原始报告全文或完整时序数据。

## 禁止展示字段

- `get_summary_base` 相关内容、基地/企业/全局概览数据。
- token、内部 URL、内部配置。
- 坐标、边界、图片 URL、系统内部 ID。
- `tgzn_*`、`sync_id`、`member_id` 等内部字段。
- 完整 `csv_content[]`。
- `icon`、`wind360`、`pressure`、`fxLink`、`refer`。
- `NaN`、空字符串、`null`、`undefined`。
