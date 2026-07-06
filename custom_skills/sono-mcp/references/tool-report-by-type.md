# get_report_by_type 字段提取规则

农业报告聚焦**报告结论 + 时间范围 + 关键指标 + 多天趋势 + 挖掘分析项 + 可下载链接**，不要原样倾倒完整 `payload`。

## 参数与报告类型

| `type` | 报告含义 | `id` 含义 | 回答重点 |
|---|---|---|---|
| `plot_growth_analysis` | 地块长势分析 | 地块 ID | 长势结论、评级、异常指标、建议 |
| `plot_3d_phenotype` | 地块 3D 表型 | 地块 ID | 株高、冠层、LAI、生物量等表型指标 |
| `plot_growth_dynamics` | 地块长势动态 | 地块 ID | 趋势变化、环比/同比、异常日期 |
| `plot_seedling_monitoring` | 苗情监测 | 地块 ID | 出苗率、密度、整齐度、缺苗风险 |
| `plot_wofost` | WOFOST 报告 | 地块 ID | 模型模拟、生育进程、产量/水分指标 |
| `device_analysis` | 设备分析报告 | 设备 ID | 设备状态、遥测统计、异常时段 |

`period_type` 仅支持 `7d`、`week`、`month`；未指定时服务端默认 `7d` 且 `days=7`。

## Payload 结构

上游不同报告类型的 `payload` 结构可能不同，优先按以下通用字段提取：

```
payload
├── report_no / reportNo       # 报告编号
├── report_name / title / name  # 报告名称
├── report_date / date          # 报告日期
├── start_date / end_date       # 报告周期
├── period_type                 # 周期类型
├── plot_id / device_id / id     # 业务对象 ID
├── plot / device / base         # 业务对象信息
├── conclusion / summary         # 结论摘要
├── metrics / index / data       # 指标集合
├── warnings / risks / alerts    # 风险或异常
├── suggestions / recommendations# 建议
└── report_url / reportUrl / url / file_url / pdf_url
```

## 必须提取的字段

| 关注维度 | 字段路径候选 | 空值处理 |
|---|---|---|
| 报告身份 | `report_no`、`reportNo`、`report_name`、`title`、`name` | 全空则只说明报告类型 |
| 报告范围 | `report_date`、`date`、`start_date`、`end_date`、`period_type` | 全空则不展示 |
| 业务对象 | `plot.name`、`plot_id`、`device.name`、`device_id`、`base.name` | 只展示非空字段 |
| 结论摘要 | `conclusion`、`summary`、`overview`、`result` | 优先用短文本，不输出大段原文 |
| 关键指标 | `metrics`、`index`、`data` 中的数值项 | 跳过空值、0 占位、内部字段 |
| 风险异常 | `warnings`、`risks`、`alerts`、`abnormal` | 有则优先展示 |
| 建议 | `suggestions`、`recommendations`、`advice` | 最多 3 条 |
| 报告链接 | `report_url`、`reportUrl`、`url`、`file_url`、`pdf_url` | 用 Markdown 链接，不展开长 URL |

## 类型专属提取重点

- `plot_growth_analysis`：优先提取长势等级、作物/批次、NDVI/LAI/覆盖度、异常区域、农事建议。
- `plot_3d_phenotype`：优先提取株高、冠层覆盖、LAI、生物量、三维重建结论、表型异常。
- `plot_growth_dynamics`：优先提取趋势曲线的最近值、最大/最小值、变化幅度、异常日期；不要逐点展示全量序列。
- `plot_seedling_monitoring`：优先提取出苗率、苗数/密度、缺苗断垄、整齐度、补苗建议。
- `plot_wofost`：优先按 `tool-wofost-report.md` 的口径解释模型模拟结果；不要把模型值说成实际测产。
- `device_analysis`：优先提取设备在线状态、最后通信时间、核心遥测统计、异常时段和维护建议。

## 用于 HTML 报告生成时

当上层 `sono-report` 要生成整体地块报告或单独专业分析报告时，不要只返回短摘要。应从 `payload` 中主动构造更开放的 `moduleReports[]`：

- 多天/多期数组：抽取 5~12 个关键点写入 `trendSeries`、`timeSeries`、`dailyData` 或 `charts[]`，用于页面出趋势图。
- 分析项：从趋势、极值、异常、环比/阶段变化、阈值命中、风险原因中挖掘 `analysisItems[]` / `insights[]` / `findings[]`。
- 解释段落和表格：有必要时写入 `sections[]`、`tables[]`，保留可读的证据摘要。
- 字段可以自由扩展，但每个结论都必须来源于 payload 中的真实数据；不要为了固定字段名丢弃有价值的数据。
- 单独专业分析报告应比整体报告中的模块更详细，优先多图表、多分析项、少泛化话术。

## 空值与跳过规则

- `payload = null`、`{}`、`[]` → 说明"未查询到相关报告数据"。
- 值为 `null`、`""`、`"0"`、`"0000-00-00"`、`"0000-00-00 00:00:00"` → 跳过，不生成占位。
- 图片、坐标、边界、`tgzn_*`、内部 ID、原始轨迹、完整时序明细默认跳过。
- 长数组不要原样倾倒；用于报告时应抽样/聚合为趋势图、分析项或精简表格。用户明确要求明细时才生成更完整表格。

## 输出格式建议

1. 先用 1 句说明报告类型、对象和时间范围。
2. 提取 3~5 个关键指标或结论。
3. 有风险/异常时优先列出风险和处理建议。
4. 有报告链接时用 Markdown 链接给出。
5. 不确定字段含义时按字段名做保守解释，不扩写成未证实结论。
