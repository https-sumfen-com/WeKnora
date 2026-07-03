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
  "overview": { "kpis": [] },
  "charts": { "sowingProgress": [], "plotTypes": [], "biomassTrend": [] },
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
- `dataSources` 只列实际使用的地块相关 MCP 工具。
- `reportType` 可用 `plot_report`、`plot_overall_report`、`plot_module_report`；无论哪种都必须围绕单个真实地块。
- `reportSubtype` 用于记录细分报告类型，例如 `plot_growth_analysis`、`plot_seedling_monitoring`；整体报告可留空。
- `dataSources` 只允许：`get_plot_info`、`get_plot_warning`、`get_report_by_type`、`get_weather`、`get_plot_device_info`、`get_wofost_report`。
- `dataSources` 必须包含 `get_plot_info`，禁止包含 `get_summary_base`。

## 模块字段

### `overview.kpis[]`

```json
{ "label": "地块面积", "value": 120, "unit": "亩", "tag": "喷灌", "level": "green" }
```

`level` 可用：`green`、`amber`、`red`、`blue`、`gray`。

### `charts`

```json
{
  "sowingProgress": [{ "name": "甜菜", "value": 90 }],
  "plotTypes": [{ "name": "喷灌", "value": 1600, "unit": "亩" }],
  "biomassTrend": [{ "label": "第0天", "tagp": 0, "twso": 0, "lai": 0, "sm": 0 }]
}
```

规则：

- `sowingProgress` / `plotTypes` 有真实数据时优先显式填写。
- 单地块报告只有 `plots[].progress` 和面积 KPI 时可以不填这两项，模板会从已有真实字段派生基础图表。
- WOFOST 趋势图不会从摘要 KPI 自动推断；需要从有效 `csv_content[]` 抽取少量点写入 `biomassTrend`。
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
  "risks": [{ "level": "warn", "title": "局部水分偏低", "body": "建议巡田确认。" }],
  "suggestions": ["关注低水分区域", "按计划巡田"],
  "link": "https://example.com/report.pdf",
  "source": "get_report_by_type"
}
```

允许的 `type`：`plot_growth_analysis`、`plot_3d_phenotype`、`plot_growth_dynamics`、`plot_seedling_monitoring`、`plot_wofost`、`device_analysis`。

规则：

- `plot_wofost` 必须表述为模型模拟/报告口径，不得写成实际测产。
- 指标只放 3~6 个关键项；长数组只摘要最近值、极值、趋势或异常点。
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
- 建议必须来源可追溯，不能写泛化模板建议。
- WOFOST 值必须表述为“模型模拟/预测”，不能说成实测。
- 整体地块报告应尝试包含 `plotWarnings[]` 和可取得的地块类 `moduleReports[]`；细分模块报告只包含用户指定的 `moduleReports[]`。

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
