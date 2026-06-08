# ECharts Chart Option 规范

当业务数据需要趋势、对比、结构、分布、关系、流向、空间轨迹或多维指标展示时，输出 `type: "chart"` 卡片，并在 `chart.data.option` 中提供可直接传给 ECharts 的完整纯 JSON option。

本规则借鉴 `Echarts-AI-Skill` 的稳定链路：先明确图表目标和字段映射，再生成完整 ECharts `option`，最后放入 chart card。`ChartRequest` 是推荐的可追溯中间规格，不是渲染必需字段。外部 skill 可作为本地生成/预览工具，但生产回答必须内联最终 payload，不依赖用户再运行脚本。

图表优先级高于表格。只要数据能表达为趋势、对比、占比、分布、关系、强度矩阵、多指标结构或空间轨迹，就先生成 `chart`；`table` 只用于补充明细或无法有效图形化的逐行文本数据。

## Card 结构

```ts
type ChartCard = {
  type: 'chart'
  cardId: string
  data: ChartCardData
}

type ChartCardData =
  {
    title?: string
    chartType?: string
    chartRequest?: ChartRequest
    option: EChartsOptionJson
    sourceSummary?: string
  }
```

字段要求：

| 字段 | 要求 |
|---|---|
| `type` | 固定为 `chart` |
| `cardId` | 稳定小写 ID，如 `chart_plot_b07_soil_14d` |
| `data.chartType` | 可选，LLM 根据数据语义选择的 ECharts 图表类型；建议与主 `series[].type` 一致 |
| `data.chartRequest` | 可选，生成 option 前的中间规格，保留字段映射和选择理由；payload 过长或不确定时优先省略 |
| `data.option` | 必需，可直接传给 `echarts.setOption(option, true)` 的纯 JSON 对象 |
| `data.sourceSummary` | 可选，简述数据来源，不写推理过程 |

## ChartRequest

```ts
type ChartRequest = {
  title?: string
  subtitle?: string
  goal:
    | 'trend'
    | 'comparison'
    | 'composition'
    | 'distribution'
    | 'relationship'
    | 'flow'
    | 'spatial'
    | 'status'
    | 'unknown'
  chartType: string
  dataset: Record<string, string | number | boolean | null>[]
  categoryField?: string
  xField?: string
  yField?: string
  valueField?: string
  groupField?: string
  series?: { name: string; field: string }[]
  dimensions?: string[]
  indicators?: { name: string; max?: number; min?: number }[]
  nodes?: { name: string; value?: number; category?: string | number; symbolSize?: number }[]
  links?: { source: string; target: string; value?: number }[]
  reason: string
}
```

`reason` 只解释图表选择和字段映射，例如“时间字段 day + 多个数值指标，适合用 line 展示趋势”。不要写模型思考链。

## 图表类型选择

不要限制在 `line`、`bar`、`pie`。由 LLM 根据数据形态选择最合适的 ECharts 类型或组合：

| 数据语义 | 常见选择 |
|---|---|
| 时间序列、连续趋势 | `line`、`bar`、`line` + `areaStyle`、组合 `line` + `bar` |
| 类别对比、排名 | `bar`，必要时横向柱状 |
| 占比、组成 | `pie`、`treemap`、`sunburst` |
| 两个数值变量关系 | `scatter`、`effectScatter` |
| 多指标能力/评级 | `radar` |
| 单指标状态或达成率 | `gauge` |
| 强度矩阵、日历/二维分布 | `heatmap` |
| 层级结构 | `treemap`、`sunburst` |
| 流向、投入产出、作业路径关系 | `sankey`、`graph`、`lines` |
| 空间点位、轨迹、区域 | `map`、`lines`，仅在有坐标/地图注册数据时使用 |
| 金融或区间分布 | `candlestick`、`boxplot` |
| 多维数值对比 | `parallel` |

可以使用 ECharts 支持的其他纯 JSON 图表类型，但禁止使用需要 JS 函数的 `custom` series，除非前端已为该场景注册固定 renderer。

## Option 稳定性规则

- `option` 必须是合法 JSON：不能有函数、`undefined`、`NaN`、`Infinity`、`Date` 对象、正则、注释或尾逗号。
- `option` 中每个属性都必须有完整 JSON value。不要输出 `"top"`、`"left"`、`"smooth"`、`"yAxisIndex"`、`"max"` 这类无值 key；值不确定时直接省略该属性。
- ECharts 布尔属性必须写完整，例如 `"smooth": true`；轴索引必须写 number，例如 `"yAxisIndex": 1`；布局值必须写 number 或 string，例如 `"top": 28` 或 `"top": "8%"`。
- 不输出 `tooltip.formatter`、`label.formatter` 等函数字段；需要格式化时用 ECharts 支持的字符串模板，或交给前端默认格式。
- 优先使用 `dataset.source` + `series[].encode` 表达字段映射；复杂图表如 `graph`、`sankey`、`radar`、`gauge` 可直接使用图表所需的 `series[].data`。
- 数字保持 number，单位放在 `axisLabel.formatter` 字符串、`name`、`title` 或 `sourceSummary` 中；不要把 `"15.2%"` 放进数值列。
- `title.text`、`legend`、`tooltip`、坐标轴、`series` 必须与图表类型匹配。需要笛卡尔坐标时才输出 `xAxis`/`yAxis`；饼图、雷达、桑基、关系图不要带无意义坐标轴。
- `radar.indicator[].max`、`series[].data[]`、`dataset.source[]` 中的数值必须是 number 或明确允许的 `null`。缺少评级分值、最大值或序列值时，跳过该指标/点位，或在 `sourceSummary` 说明缺口，不要输出空 key。
- 大于 200 行的明细数据不要全塞进 option；先聚合、采样或输出 table，并由自然回复说明图表只展示 Top N 或聚合结果。
- `chartRequest` 是可选追溯信息，不是渲染必需字段。为了保证 JSON 合法性，可以只输出 `title`、`chartType`、`option`、`sourceSummary`。
- 地图、迁徙线、轨迹图必须有真实 `[lng, lat]` 坐标和前端已注册地图名；缺任一项则不要生成对应 option。
- 多系列图表必须保证每个 `series[].name`、`encode` 或 `data` 都能追溯到 `chartRequest` 和原始数据字段。

## 生成流程

1. 从 SONO-MCP/API/工具结果中抽取图表所需字段，删除无关系统字段。
2. 判断 `goal` 和字段类型。复杂图表建议构造最小可解释 `ChartRequest`；简单图表可省略。
3. 由 LLM 选择最合适的 ECharts 图表类型，不限制为 `line`、`bar`、`pie`。
4. 生成完整 `option`，确保是纯 JSON，能直接 `setOption`。
5. 把 `option` 放入 `chart.data.option`。如已构造 `ChartRequest`，一并放入 `chart.data`，便于后端/前端校验和追溯。
6. 提交前校验整张 chart card：`data.option`、`data.chartRequest`、`series[].data`、`dataset.source` 都必须是合法 JSON；任一可选字段无值时删除该字段。

## 示例

最小合法示例:

```json
{
  "type": "chart",
  "cardId": "chart_custom",
  "data": {
    "title": "自定义图表",
    "option": {
      "xAxis": { "type": "category", "data": ["A", "B"] },
      "yAxis": { "type": "value" },
      "series": [{ "type": "scatter", "name": "样本", "data": [12, 19] }]
    }
  }
}
```

带追溯元数据的业务示例:

```json
{
  "type": "chart",
  "cardId": "chart_plot_b07_soil_14d",
  "data": {
    "title": "B-07 近 14 天墒情趋势",
    "chartType": "line",
    "chartRequest": {
      "title": "B-07 近 14 天墒情趋势",
      "goal": "trend",
      "chartType": "line",
      "dataset": [
        { "day": "05-01", "soilMoisture": 18.2 },
        { "day": "05-02", "soilMoisture": 17.6 }
      ],
      "xField": "day",
      "yField": "soilMoisture",
      "series": [{ "name": "墒情", "field": "soilMoisture" }],
      "reason": "day 是连续日期字段，soilMoisture 是同一地块的连续数值，适合用 line 展示趋势。"
    },
    "option": {
      "title": { "text": "B-07 近 14 天墒情趋势" },
      "tooltip": { "trigger": "axis" },
      "legend": { "top": 28 },
      "grid": { "left": 40, "right": 24, "top": 72, "bottom": 36 },
      "dataset": {
        "source": [
          { "day": "05-01", "soilMoisture": 18.2 },
          { "day": "05-02", "soilMoisture": 17.6 }
        ]
      },
      "xAxis": { "type": "category" },
      "yAxis": { "type": "value", "name": "墒情（%）" },
      "series": [
        {
          "name": "墒情",
          "type": "line",
          "encode": { "x": "day", "y": "soilMoisture" },
          "smooth": true
        }
      ]
    },
    "sourceSummary": "数据来自 SONO-MCP 返回的 B-07 地块近 14 天墒情序列。"
  }
}
```

## 自检

- 图表类型是否由数据语义决定？
- `option` 是否是纯 JSON，且没有函数字段？
- `option` 和 `chartRequest` 是否没有任何无值 key、`undefined`、`NaN`、`Infinity` 或尾逗号？
- 如果提供了 `chartRequest`，它的 `dataset` 是否与 `option.dataset.source` 或 `series[].data` 一致？
- 每个数值、类别、坐标、节点、边是否都有 SONO-MCP/API/工具来源？
- 前端只拿 `card.data.option` 调用 ECharts 时是否能独立渲染？
