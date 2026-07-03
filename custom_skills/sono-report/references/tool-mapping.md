# SONO-MCP 到地块 REPORT_DATA 映射

## 目录

- `get_plot_info`
- `get_weather`
- `get_plot_device_info`
- `get_wofost_report`
- 禁止展示字段

读取本文件前，先按实际调用工具读取对应 `sono-mcp/references/tool-*.md`，本文件只说明报告层映射。

禁止使用或展示 `get_summary_base`。本 Skill 只生成基于地块的报告。

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
- `accumulated_tp` → 积温积雨 KPI 或图表
- `iot_device` → 设备摘要或建议
- `current_crop_model_cycle.remark` 中“注意事项” → `recommendations[]`

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

如 WOFOST 结果只有 `plot_id`/`plot_no` 没有地块名称，先调用 `get_plot_info` 获取地块名称，再生成报告。

## 禁止展示字段

- `get_summary_base` 相关内容、基地/企业/全局概览数据。
- token、内部 URL、内部配置。
- 坐标、边界、图片 URL、系统内部 ID。
- `tgzn_*`、`sync_id`、`member_id` 等内部字段。
- 完整 `csv_content[]`。
- `icon`、`wind360`、`pressure`、`fxLink`、`refer`。
- `NaN`、空字符串、`null`、`undefined`。
