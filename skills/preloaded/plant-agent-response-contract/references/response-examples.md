# 返回示例与自检

示例中的数值表示“已由 SONO-MCP 返回”的数据形态；实际输出必须替换为当前任务真实读取的数据。

## 企业报告示例

```json
{
  "schemaVersion": "plant-agent.message.v1",
  "markdown": "当前主要风险集中在东区基地设备离线和 B-07 地块墒情偏低。",
  "blocks": [
    {
      "kind": "report",
      "title": "企业经营风险概览",
      "cards": [
        {
          "type": "metric",
          "cardId": "metric_enterprise_overview_20260514",
          "data": {
            "items": [
              { "label": "基地数量", "value": 4, "unit": "个" },
              { "label": "在线设备率", "value": 91.3, "unit": "%" },
              { "label": "高风险地块", "value": 2, "unit": "块" }
            ]
          }
        },
        {
          "type": "chart",
          "cardId": "chart_enterprise_risks_20260514",
          "data": {
            "title": "重点风险强度",
            "chartType": "bar",
            "option": {
              "title": { "text": "重点风险强度" },
              "tooltip": { "trigger": "axis" },
              "xAxis": {
                "type": "category",
                "data": ["东区基地", "B-07 地块"]
              },
              "yAxis": {
                "type": "value",
                "name": "风险等级",
                "min": 0,
                "max": 3
              },
              "series": [
                {
                  "type": "bar",
                  "name": "风险强度",
                  "data": [3, 3],
                  "label": { "show": true, "position": "top" }
                }
              ]
            },
            "sourceSummary": "高风险按 3 分映射，仅用于风险强度可视化；风险事实来自 SONO-MCP 返回的设备离线和地块墒情异常。"
          }
        },
        {
          "type": "recommendation",
          "cardId": "rec_enterprise_actions_20260514",
          "data": {
            "title": "建议动作",
            "items": [
              {
                "id": "check-east-devices",
                "title": "优先排查东区基地离线设备",
                "reason": "SONO-MCP 返回 3 台设备离线，影响东区基地环境监测连续性",
                "priority": "high"
              }
            ]
          }
        }
      ]
    },
    {
      "kind": "quick-reply",
      "prompts": [
        { "label": "查看东区基地", "fillText": "生成东区基地设备运行分析报告" },
        { "label": "查看 B-07", "fillText": "分析 B-07 地块近 14 天墒情变化" }
      ]
    }
  ],
  "focusEntities": []
}
```

## 地块详情示例

```json
{
  "schemaVersion": "plant-agent.message.v1",
  "markdown": "B-07 当前墒情低于阈值，短期降雨不足，建议优先关注灌溉。",
  "blocks": [
    {
      "kind": "report",
      "title": "B-07 地块墒情风险报告",
      "cards": [
        {
          "type": "metric",
          "cardId": "metric_plot_b07_soil_20260514",
          "data": {
            "items": [
              { "label": "当前墒情", "value": 15.2, "unit": "%", "trend": "down" },
              { "label": "阈值差", "value": -2.8, "unit": "%" }
            ]
          }
        },
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
              "reason": "day 是连续日期字段，soilMoisture 是同一地块连续数值，适合用 line 展示趋势。"
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
        },
        {
          "type": "recommendation",
          "cardId": "rec_plot_b07_irrigation",
          "data": {
            "title": "建议动作",
            "items": [
              {
                "id": "irrigate-b07",
                "title": "优先安排 B-07 滴灌",
                "reason": "当前墒情低于阈值，且近 7 天无有效降雨",
                "priority": "high",
                "targetEntity": { "kind": "plot", "id": "plot-b07", "name": "B-07 地块" }
              }
            ]
          }
        }
      ]
    }
  ],
  "focusEntities": [
    { "kind": "plot", "id": "plot-b07", "name": "B-07 地块" }
  ]
}
```

## 设备详情示例

```json
{
  "schemaVersion": "plant-agent.message.v1",
  "markdown": "1 号气象站当前在线，但近 24 小时存在一次数据中断。",
  "blocks": [
    {
      "kind": "card",
      "card": {
        "type": "metric",
        "cardId": "metric_device_weather_001_status",
        "data": {
          "items": [
            { "label": "当前状态", "value": "在线" },
            { "label": "24 小时中断", "value": 25, "unit": "分钟" }
          ]
        }
      }
    }
  ],
  "focusEntities": [
    { "kind": "device", "id": "weather-001", "name": "1 号气象站" }
  ]
}
```

## 缺数据示例

```json
{
  "schemaVersion": "plant-agent.message.v1",
  "markdown": "SONO-MCP 未返回指定时间范围内的作业轨迹，因此不能生成轨迹地图或作业效率图。",
  "blocks": [
    {
      "kind": "card",
      "card": {
        "type": "metric",
        "cardId": "metric_machinery_m12_status",
        "data": {
          "items": [
            { "label": "当前状态", "value": "在线" }
          ]
        }
      }
    }
  ],
  "focusEntities": [
    { "kind": "machinery", "id": "machinery-m12", "name": "M-12 农机" }
  ]
}
```

## 反例

### blocks 里放正文

```json
{ "kind": "text", "markdown": "## 今日重点\n\nB-07 地块需要灌溉。" }
```

错误。正文写到顶层 `markdown`，不要作为 block。

### blocks 里放推理说明

```json
{ "kind": "reasoning", "text": "先读取地块墒情，再判断风险。" }
```

错误。业务级分析过程写到 Markdown 的“数据来源”或“判断依据”段落。

### MCP 成功后仍只输出 Markdown

```json
{
  "schemaVersion": "plant-agent.message.v1",
  "markdown": "## 地块分析总览\n\nB-07 当前墒情低于阈值。\n\n## 核心依据\n\n- 当前墒情 15.2%\n- 近 7 天无有效降雨\n\n## 农事建议\n\n建议优先安排滴灌。",
  "blocks": []
}
```

错误。SONO-MCP 已返回地块数据且用户意图是分析/建议/报告时，必须优先生成 `report` 或 `card` block。Markdown 只能保留极短摘要或必要缺口。

### 报告前重复报告正文

```json
{
  "schemaVersion": "plant-agent.message.v1",
  "markdown": "## 地块分析总览\n\nB-07 墒情偏低。\n\n## 核心依据\n\n当前墒情 15.2%，近 7 天无有效降雨。\n\n## 详细分析报告",
  "blocks": [
    { "kind": "report", "title": "B-07 墒情风险报告", "cards": [] }
  ]
}
```

错误。report 已经是报告主体，不要在 report 前写一套重复的 Markdown 报告章节。

### 编造数据

```json
{ "label": "土壤墒情", "value": 15.2, "unit": "%" }
```

如果 SONO-MCP/API/工具/用户事实没有提供 `15.2`，就是错误。

### 单位写进 value

```json
{ "label": "土壤墒情", "value": "15.2%" }
```

错误。使用 `value: 15.2` 和 `unit: "%"`。

### 未支持的聚焦对象

```json
{ "kind": "base", "id": "base-east", "name": "东区基地" }
```

错误，除非前后端已经扩展 `focusEntities.kind`。企业和基地作为分析范围写入 Markdown、report 标题或卡片数据。

### chart 缺少 option

```json
{
  "type": "chart",
  "cardId": "chart_plot_b07_soil_14d",
  "data": {
    "title": "B-07 近 14 天墒情",
    "variant": "line",
    "xAxis": ["05-01", "05-02"],
    "series": [{ "name": "墒情", "data": [18.2, 17.6] }]
  }
}
```

错误。`chart` 卡片必须输出完整纯 JSON `data.option`。只给 `variant/xAxis/series` 不能作为合规输出。

### ECharts option 包含函数

```json
{
  "tooltip": {
    "formatter": "(params) => params[0].value + '%'"
  }
}
```

错误。`option` 必须是纯 JSON，不写函数字段；需要格式化时使用 ECharts 字符串模板或默认格式。

## 最终自检

- 是否先读取或接收了 SONO-MCP/API/工具数据？
- 如果 SONO-MCP/API/工具数据读取成功，是否优先生成了 `report` 或 `card` block？
- Markdown 是否只保留 1-2 句摘要或必要缺口，而不是完整分析正文？
- `blocks[].kind` 是否只包含 `card`、`report`、`quick-reply`？
- 是否完全避免了 `text` block 和 `reasoning` block？
- card 类型是否只用了当前注册类型？
- `chart` 卡片是否包含纯 JSON `data.option`？复杂图表是否按需补充了 `chartRequest`？
- 是否在可视化数据场景优先生成了 `chart`，没有把趋势、对比、占比、分布、多指标对比默认做成 `table`？
- 所有数字、坐标、对象 ID、状态、任务结果是否都有来源？
- 数据不足时是否说明缺口，而不是生成占位卡片？
- 后端即使只校验不修复，当前输出是否仍然可用？
