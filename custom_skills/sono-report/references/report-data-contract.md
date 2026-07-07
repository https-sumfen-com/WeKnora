# 地块 REPORT_DATA 契约

本契约只用于基于地块的报告，包括整体地块报告和细分模块报告。禁止包含 `get_summary_base`、基地报告、企业报告或全局概览内容。

## 目录

- 顶层结构
- `meta`
- 模块字段
- 契约规则
- 示例

## 顶层结构

```json
{
  "meta": {},
  "paper": { "abstract": "", "keywords": [], "methods": [], "findings": [], "discussion": [], "conclusions": [], "limitations": [], "appendixLinks": [] },
  "overview": { "kpis": [] },
  "charts": { "biomassTrend": [] },
  "weather": { "now": null, "forecast": [], "alerts": [] },
  "plotWarnings": [],
  "plots": [],
  "moduleReports": [],
  "devices": { "summary": {}, "items": [] },
  "wofost": { "phenology": [], "kpis": [], "waterBalance": [], "links": {} },
  "recommendations": [],
  "emptyStates": []
}
```

## `meta`

```json
{
  "reportType": "plot_report",
  "reportSubtype": "",
  "title": "地块报告",
  "subjectName": "真实地块名称",
  "plotName": "真实地块名称",
  "reportDate": "YYYY-MM-DD",
  "generatedAt": "YYYY-MM-DD HH:mm:ss",
  "periodStart": "",
  "periodEnd": "",
  "batchTitle": "",
  "dataSources": ["get_plot_info"]
}
```

规则：

- 地块相关报告必须同时设置 `subjectName` 和 `plotName` 为真实地块名称。
- 禁止把 `plot_id`、`plot_no`、`地块 {id}` 写入 `subjectName` 或 `plotName`。
- `dataSources` 只列实际使用的地块相关 MCP 工具或细分来源标记。
- `reportType` 可用 `plot_report`、`plot_overall_report`、`plot_module_report`；无论哪种都必须围绕单个真实地块。
- `reportSubtype` 用于记录细分报告类型，例如 `plot_growth_analysis`、`plot_seedling_monitoring`；整体报告可留空。
- `dataSources` 不做窄白名单限制，允许 `get_report_by_type:plot_growth_analysis` 这类细分来源标记。
- `dataSources` 必须包含 `get_plot_info`，禁止包含 `get_summary_base`。
- `dataSources` 仅供内部校验和追溯；HTML 页脚不得展示这些接口名，只写“本报告数据来源：{plotName}地块真实数据记录”。

## 论文式内容字段

`paper` 是可选的学术报告叙事层。模板会优先使用该字段；缺失时会从 `meta`、`overview`、`plots`、`moduleReports`、`plotWarnings` 和 `recommendations` 自动组织基础论文结构。

```json
{
  "abstract": "基于真实数据形成的摘要，不编造缺失指标。",
  "keywords": ["长势分析", "NDVI", "LAI"],
  "methods": ["说明数据来源、指标口径和处理方法。"],
  "findings": [{ "title": "关键发现", "body": "证据化表述。", "level": "green" }],
  "discussion": ["讨论数据含义与管理影响。"],
  "conclusions": ["编号结论。"],
  "limitations": ["数据质量、模型适用性和现场复核说明。"],
  "appendixLinks": []
}
```

规则：

- `paper` 中所有结论必须能追溯到真实地块数据、专项报告、模型序列或用户明确事实。
- 不写未计算的显著性检验、p 值或因果断言。
- WOFOST 相关内容必须标注“模型模拟/预测”。

## 模块字段

### `overview.kpis[]`

```json
{ "label": "地块面积", "value": 120, "unit": "亩", "tag": "喷灌", "level": "green" }
```

`level` 可用：`green`、`amber`、`red`、`blue`、`gray`。

### `charts`

```json
{
  "biomassTrend": [{ "label": "第0天", "tagp": 0, "twso": 0, "lai": 0, "sm": 0 }]
}
```

规则：

- 不要填 `sowingProgress` / `plotTypes`；模板不展示播种进度或地块结构图。
- 播种进度、地块面积、地块结构等信息需要展示时，放入 `overview.kpis[]` 或 `plots[]` 的文本字段。
- WOFOST 趋势图不会从摘要 KPI 自动推断；需要从有效 `csv_content[]` 或 `../sono-mcp/wofost-daily-report.csv` 抽取少量点写入 `biomassTrend`。`wofost-daily-report.csv` 归属 `plot_growth_dynamics` 生长动态报告。
- 不要把完整原始 `csv_content[]` 放进最终报告 JSON。

### `weather`

```json
{
  "now": { "text": "晴", "temp": 28, "feelsLike": 31, "humidity": 62, "windScale": 3, "windDir": "东南", "windSpeed": 12, "precip": 0, "vis": 18, "obsTime": "2026-06-23 08:00" },
  "forecast": [{ "date": "2026-06-24", "textDay": "多云", "tempMax": 29, "tempMin": 18, "precip": 0, "windScaleDay": 3, "humidity": 60 }],
  "alerts": [{ "level": "warn", "title": "橙色预警", "body": "未来 2 天预计降水量 ≥ 10mm", "icon": "ti-alert-triangle" }]
}
```

### `plotWarnings[]`

来自 `get_plot_warning` 的地块预警，聚焦预警等级、类型、时间、状态和处置建议：

```json
{
  "level": "高风险",
  "title": "水分含量低",
  "body": "土壤水分偏低，可能影响幼苗生长。",
  "time": "2026-07-03 09:00",
  "status": "未处理",
  "suggestions": ["安排现场核查", "结合天气窗口补水"],
  "source": "get_plot_warning"
}
```

规则：

- 无预警时 `plotWarnings` 留空，不生成泛化风险提醒。
- 需要处置的预警同步提炼到 `recommendations[]`，`source` 指向 `get_plot_warning`。
- 不展示内部 ID、坐标、边界、图片 URL 或处理日志明细。

### `plots[]`

```json
{ "name": "真实地块名称", "crop": "甜菜", "stage": "叶丛期", "days": 58, "progress": 47, "grade": "水分偏低", "level": "amber" }
```

### `devices`

```json
{
  "summary": { "total": 46, "online": 40, "offline": 3, "abnormal": 3 },
  "items": [
    { "name": "气象站 #A01", "type": "气象站", "status": "online", "plotName": "真实地块名称", "lastTime": "2026-06-23 08:00", "metrics": [{ "label": "温度", "value": "27.8°C" }] }
  ]
}
```

`status` 可用：`online`、`offline`、`fault`、`abnormal`、`unknown`。

### `wofost`

```json
{
  "reportDate": "2026-06-23",
  "reportNo": "",
  "plotNo": "",
  "plotName": "真实地块名称",
  "stageText": "模型模拟：营养生长期",
  "phenology": [{ "label": "播种（DOS）", "value": "2026-03-10" }],
  "kpis": [{ "label": "最大叶面积指数 LAIMAX", "value": "3.84", "sub": "模型模拟值" }],
  "waterBalance": [{ "label": "总降雨 RAINT", "value": "182 mm" }],
  "links": { "pdf": "", "csv": "" }
}
```

### `moduleReports[]`

来自 `get_report_by_type` 的细分模块报告。整体地块报告应包含可取得的地块类模块；单独细分报告只放用户指定模块。

```json
{
  "type": "plot_growth_analysis",
  "title": "地块长势分析",
  "reportDate": "2026-07-03",
  "periodType": "7d",
  "conclusion": "长势整体正常，局部水分偏低。",
  "metrics": [{ "label": "NDVI", "value": "0.72" }],
  "trendSeries": [
    { "label": "06-27", "ndvi": 0.68, "lai": 1.8, "coverage": 62 },
    { "label": "07-03", "ndvi": 0.72, "lai": 2.1, "coverage": 69 }
  ],
  "analysisItems": [
    { "title": "NDVI 回升", "body": "NDVI 近 7 天上升 0.04，冠层活力恢复。", "level": "green" }
  ],
  "sections": [{ "title": "数据挖掘说明", "items": ["LAI 与覆盖度同步上升", "低水分区域仍需复核"] }],
  "tables": [{ "title": "关键观测点", "headers": ["label", "ndvi", "lai"], "rows": [{ "label": "06-27", "ndvi": 0.68, "lai": 1.8 }] }],
  "risks": [{ "level": "warn", "title": "局部水分偏低", "body": "建议巡田确认。" }],
  "suggestions": ["关注低水分区域", "按计划巡田"],
  "link": "https://example.com/report.pdf",
  "source": "get_report_by_type"
}
```

允许的 `type`：`plot_growth_analysis`、`plot_3d_phenotype`、`plot_growth_dynamics`、`plot_seedling_monitoring`、`plot_wofost`、`device_analysis`。

规则：

- `plot_wofost` 必须表述为模型模拟/报告口径，不得写成实际测产。
- 不要只放指标摘要；应从多天数据中挖掘趋势、异常点、极值、环比/阶段变化、原因和建议。
- `trendSeries`、`timeSeries`、`dailyData`、`charts[]`、`analysisItems`、`insights`、`findings`、`sections`、`tables` 都是允许的开放扩展字段。模板会尽量渲染，不要求字段名完全固定。
- 长数组不要原样全量倾倒；抽样或聚合为图表序列、摘要表和分析项。
- 有下载链接时放 `link`；不要展开长 URL 或原始文件内容。
- 模块返回空或失败时跳过，不填示例值。

### `recommendations[]`

```json
{ "priority": "high", "badge": "紧急", "title": "补水建议", "body": "水分含量偏低，建议安排灌溉。", "source": "get_plot_info.grade[]" }
```

`priority` 可用：`high`、`mid`、`low`。

## 契约规则

- 没有真实数据的模块留空，不填示例值。
- 空值、`NaN`、`undefined`、`null` 不作为业务展示值。
- 风险、建议、分析项、表格行和图表序列必须包含真实可展示字段；全空行、全空列、字段不匹配表格或无数值图表应跳过。
- `level`、`green`、`blue`、`amber`、`red` 等状态值只作为内部等级或样式字段；页面可见说明必须转成专业中文表达。
- 建议必须来源可追溯，不能写泛化模板建议。
- WOFOST 值必须表述为“模型模拟/预测”，不能说成实测。
- 整体地块报告应尝试包含 `plotWarnings[]` 和 4 类地块专项 `moduleReports[]`：`plot_growth_analysis`、`plot_3d_phenotype`、`plot_growth_dynamics`、`plot_seedling_monitoring`；细分模块报告只包含用户指定的 `moduleReports[]`，但模块内部同样要尽量深挖多天数据和分析项。
- `overall_report` 必须是四模块综合研判，不是四份报告简单拼接；默认不把 `plot_wofost` 作为第五模块。
- 每种报告都按论文式结构生成：摘要与关键词、数据来源与处理方法、结果与分析、讨论与农事建议、结论与附录。
- 预处理脚本只禁止基地/汇总类来源；地块级新模块来源可以扩展，避免专业分析被固定白名单限制。

## 示例

```json
{
  "meta": {
    "reportType": "plot_report",
    "title": "地块周报",
    "subjectName": "东区一号地",
    "plotName": "东区一号地",
    "reportDate": "2026-06-23",
    "generatedAt": "2026-06-23 14:17:03",
    "dataSources": ["get_plot_info", "get_weather"]
  },
  "overview": { "kpis": [{ "label": "地块面积", "value": 120, "unit": "亩", "level": "blue" }] },
  "plots": [{ "name": "东区一号地", "crop": "甜菜", "stage": "叶丛期", "days": 58, "progress": 47, "grade": "正常", "level": "green" }],
  "recommendations": []
}
```
