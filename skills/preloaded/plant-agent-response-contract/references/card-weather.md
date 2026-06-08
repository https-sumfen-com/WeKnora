# 天气局部卡片结构（get_weather）

本参考只用于非报告天气展示。用户明确要求天气报告、地块报告、基地报告或企业报告时，本文件不适用，由主路由转入明确报告 reference。

## 触发场景

- 用户询问“天气趋势”“未来天气走势”“7天预报趋势”“降水变化”“气温变化”等，但没有明确要求报告。
- 用户要求天气图表、天气卡片、天气可视化、作业窗口、天气风险关注。
- 已读取到异常、风险、预警或阈值越界天气数据，需要局部高亮。

## 7天预报趋势（payload.days[]）

已有 `payload.days[]` 时，默认生成：

1. `chart` card：用 ECharts 展示温度、降水、湿度或风力趋势。
2. `recommendation` card：仅在有预警、阈值越界、明显降水、大风、低温、高温、低湿或高湿时生成。
3. `quick-reply`：给出 2-3 个后续追问。

图表规则：

- 日期作为 x 轴，7 天全部展示，不截断。
- 最高/最低温适合双折线；降水适合柱状；湿度/风力可用折线或独立坐标轴。
- 有阈值越界的日期，用 `markPoint`、`markLine`、标签或 `visualMap` 标注。
- 不要用逐日 Markdown 表格替代图表；用户明确要求逐日明细时，才补充 `table` card。

recommendation 规则：

- 多个预警按风险类型合并，不要每天一条。
- `reason` 必须引用具体日期和数值。
- 有连续安全作业窗口时，可以追加低优先级建议。
- 全部 7 天无预警且无明显作业建议时，跳过 recommendation。

quick-reply 示例：

- "结合墒情" -> `"结合地块墒情分析未来7天作业窗口"`
- "查看作业计划" -> `"根据未来7天天气安排农事作业计划"`
- "看当前天气" -> `"查询当前实时天气"`

## 实时天气（payload.now）

实时天气默认生成 `metric` card；有预警或阈值越界时追加 `recommendation`，否则不强行生成 recommendation。

metric items 按序：

| label | value 来源 | unit |
|---|---|---|
| 天气状况 | `text` | - |
| 温度 | `temp` | °C |
| 体感温度 | `feelsLike` | °C |
| 风力 | `windScale`级 + `windDir` | - |
| 湿度 | `humidity` | % |
| 降水 | `precip` | mm |

预警阈值：

- `windScale >= 5`
- `temp <= 5` 或 `temp >= 35`
- `humidity <= 30` 或 `humidity >= 85`
- `precip >= 10`

## 禁止项

- 不生成 `report`。
- 不加载任何报告 reference。
- 不把天气字段塞进地块基础 metric；需要天气就生成独立 weather card。
- 不输出 `icon`、`wind360`、`pressure`、`fxLink`、`refer`。
- 不用整段 Markdown 承载天气趋势，图形化数据必须进入 `chart` card。
